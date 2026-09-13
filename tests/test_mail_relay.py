"""Isolated relay behavior tests. No production data or real email access."""
import base64
from concurrent.futures import ThreadPoolExecutor
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from backend.app import mail_relay as mod, relay_mail


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='relay-test-')
        self.addCleanup(self.tmp.cleanup)
        self.now = 1789300000.0
        self.sent = []
        self.result = ('accepted', '')
        self.settings = mod.Settings(Path(self.tmp.name) / 'data', 'info@clinic.example',
            'doctor@gmail.com', 'reply.clinic.example', 'w'*64, 't'*64, smtp_host='smtp.example')
        self.relay = mod.Relay(self.settings, clock=lambda:self.now, transport=self.transport)

    def transport(self, settings, recipient, raw):
        self.sent.append((recipient, BytesParser(policy=policy.default).parsebytes(raw)))
        return self.result

    def conversation(self):
        return self.relay.submit('Patient', 'patient@gmail.com', 'I need an appointment.')

    def raw(self, sender='doctor@gmail.com', body='Appointment confirmed.', mid='<one@gmail.com>', html=False):
        message = EmailMessage()
        message['From'] = sender
        message['To'] = 'irrelevant@example.com'
        message['Message-ID'] = mid
        message.set_content(body, subtype='html' if html else 'plain')
        return message

    def signed(self, cid, role='d', message=None, domain='gmail.com', nonce=None):
        message = message or self.raw()
        body = json.dumps({'recipient':self.relay.reply_address(cid, role),
            'envelope_from':str(message['From']), 'authenticated_domain':domain,
            'raw':base64.b64encode(message.as_bytes()).decode()}).encode()
        timestamp, nonce = str(int(self.now)), nonce or secrets.token_hex(16)
        digest = hashlib.sha256(body).hexdigest()
        signature = hmac.new(self.settings.webhook_secret.encode(),
            f'POST\n{mod.ENDPOINT}\n{timestamp}\n{nonce}\n{digest}'.encode(), hashlib.sha256).hexdigest()
        return body, timestamp, nonce, signature

    def test_complete_three_leg_conversation_with_private_headers(self):
        cid = self.conversation()
        self.assertTrue(self.relay.drain_one())
        to_doctor = self.sent[-1][1]
        self.assertEqual(self.sent[-1][0], 'doctor@gmail.com')
        self.assertEqual(to_doctor['From'].addresses[0].addr_spec, 'info@clinic.example')
        self.assertEqual(to_doctor['Reply-To'].addresses[0].addr_spec, self.relay.reply_address(cid, 'd'))
        self.assertNotIn('patient@gmail.com', to_doctor.as_string())
        self.assertIn('I need an appointment.', to_doctor.get_body(preferencelist=('plain',)).get_content())
        self.assertEqual(self.relay.receive(*self.signed(cid)), 'queued')
        self.relay.drain_one()
        to_patient = self.sent[-1][1]
        self.assertEqual(self.sent[-1][0], 'patient@gmail.com')
        self.assertEqual(to_patient['From'].addresses[0].addr_spec, 'info@clinic.example')
        self.assertNotIn('doctor@gmail.com', to_patient.as_string())
        self.assertEqual(to_patient['Reply-To'].addresses[0].addr_spec, self.relay.reply_address(cid, 'p'))
        self.relay.receive(*self.signed(cid, 'p', self.raw('patient@gmail.com', 'Thank you!', '<two@gmail.com>')))
        self.relay.drain_one()
        followup = self.sent[-1][1]
        self.assertEqual(self.sent[-1][0], 'doctor@gmail.com')
        self.assertEqual(followup['In-Reply-To'], to_doctor['Message-ID'])
        self.assertEqual(followup['Subject'], to_doctor['Subject'])
        self.assertEqual(self.relay.status()['outbox'], {'accepted':3})

    def test_wrong_sender_and_auth_domain_never_route(self):
        cid = self.conversation()
        for packet in (self.signed(cid, message=self.raw('intruder@gmail.com')),
                       self.signed(cid, domain='attacker.example')):
            with self.assertRaises(mod.RelayError):
                self.relay.receive(*packet)
        self.assertEqual(self.relay.status()['outbox'], {'queued':1})

    def test_wrong_role_and_random_recipient_never_route(self):
        cid = self.conversation()
        with self.assertRaises(mod.RelayError):
            self.relay.receive(*self.signed(cid, 'p'))
        with self.assertRaises(mod.RelayError):
            self.relay.resolve(self.relay.reply_address(cid, 'd').replace(cid, '0'*24))
        self.assertLessEqual(len(self.relay.reply_address(cid, 'd').split('@')[0]), 64)

    def test_duplicate_webhook_and_mail_id_are_not_relayed_twice(self):
        cid = self.conversation()
        packet = self.signed(cid)
        self.assertEqual(self.relay.receive(*packet), 'queued')
        self.assertEqual(self.relay.receive(*packet), 'duplicate')
        self.assertEqual(self.relay.receive(*self.signed(cid)), 'duplicate')
        self.assertEqual(self.relay.status()['outbox'], {'queued':2})

    def test_cross_conversation_reply_token_cannot_be_swapped(self):
        cid = self.conversation()
        other = self.relay.submit('Other', 'other@gmail.com', 'Another question')
        with self.assertRaises(mod.RelayError):
            self.relay.receive(*self.signed(other, 'p', self.raw('patient@gmail.com')))
        self.assertNotEqual(self.relay.reply_address(cid, 'd'), self.relay.reply_address(other, 'd'))

    def test_signed_request_cannot_be_modified_or_replayed_with_new_message(self):
        cid = self.conversation()
        body, stamp, nonce, signature = self.signed(cid)
        for packet in ((body+b' ',stamp,nonce,signature),(body,str(int(stamp)-301),nonce,signature),
                       (body,stamp,nonce,'0'*64)):
            with self.assertRaises(mod.RelayError): self.relay.receive(*packet)
        self.relay.receive(body,stamp,nonce,signature)
        with self.assertRaises(mod.RelayError):
            self.relay.receive(*self.signed(cid,message=self.raw(mid='<new@gmail.com>'),nonce=nonce))

    def test_expired_and_closed_conversations_rejected(self):
        cid = self.conversation()
        self.now += 181*86400
        with self.assertRaises(mod.RelayError): self.relay.receive(*self.signed(cid))

    def test_auto_reply_and_mailing_list_do_not_loop(self):
        cid = self.conversation()
        for header,value in [('Auto-Submitted','auto-replied'),('Precedence','bulk'),
                             ('X-Clinic-Relay','1'),('List-Id','list.example'),('X-Autoreply','yes')]:
            message = self.raw()
            message[header]=value
            with self.assertRaises(mod.RelayError): self.relay.receive(*self.signed(cid,message=message))

    def test_multiple_from_and_header_injection_rejected(self):
        cid = self.conversation()
        message = self.raw('doctor@gmail.com, attacker@example.com')
        with self.assertRaises(mod.RelayError): self.relay.receive(*self.signed(cid,message=message))
        with self.assertRaises(mod.RelayError): self.relay.submit('Name\nBcc: attacker@example.com','patient@gmail.com','hi')

    def test_attachments_are_rejected_without_silently_losing_them(self):
        cid = self.conversation()
        message = self.raw()
        message.add_attachment(b'%PDF-test',maintype='application',subtype='pdf',filename='medical.pdf')
        with self.assertRaisesRegex(mod.RelayError,'attachments_not_supported'):
            self.relay.receive(*self.signed(cid,message=message))
        self.assertEqual(self.relay.status()['outbox'], {'queued':1})

    def test_html_and_plain_quotes_removed_addresses_masked(self):
        cid = self.conversation()
        message = self.raw(body='<div>Hello doctor@gmail.com</div><script>secret</script><blockquote>Private quoted patient@gmail.com</blockquote>',html=True)
        self.relay.receive(*self.signed(cid,message=message))
        self.relay.drain_one(); self.relay.drain_one()
        body = self.sent[-1][1].get_body(preferencelist=('plain',)).get_content()
        self.assertIn('Hello [E-Mail]', body)
        self.assertNotIn('secret', body)
        self.assertNotIn('Private quoted', body)
        self.assertEqual(relay_mail.sanitize_text('New reply\nOn Sunday someone wrote:\nOld private text'), 'New reply')
        self.assertEqual(relay_mail.sanitize_text('Reply\n'+relay_mail.MARKER+'\nFooter'), 'Reply')

    def test_oversized_and_empty_replies_not_accepted(self):
        cid = self.conversation()
        for message in (self.raw(body='> quoted only'), self.raw(body='a'*(relay_mail.MAX_TEXT+1))):
            with self.assertRaises(mod.RelayError): self.relay.receive(*self.signed(cid,message=message))

    def test_smtp_temporary_failure_retries_and_persists_across_restarts(self):
        self.conversation()
        self.result = ('retry','smtp_connection')
        self.relay.drain_one()
        self.assertFalse(self.relay.drain_one())
        self.now += 61
        restarted=mod.Relay(self.settings,clock=lambda:self.now,transport=self.transport)
        self.result=('accepted','')
        self.assertTrue(restarted.drain_one())
        self.assertEqual(restarted.status()['outbox'], {'accepted':1})
        self.assertEqual(self.sent[0][1]['Message-ID'], self.sent[1][1]['Message-ID'])

    def test_uncertain_delivery_is_not_automatically_resent(self):
        self.conversation()
        self.result=('uncertain','smtp_connection')
        with self.assertLogs(mod.logger,level='ERROR'): self.relay.drain_one()
        self.now += 10000
        self.assertFalse(self.relay.drain_one())
        self.assertEqual(len(self.sent),1)
        self.assertEqual(len(self.relay.status()['review']),1)

    def test_crashed_inflight_delivery_is_held_for_review(self):
        self.conversation()
        with self.relay.db() as db:
            db.execute("UPDATE outbox SET status='inflight',lease_until=?",(self.now-1,))
        self.assertFalse(self.relay.drain_one())
        self.assertEqual(self.relay.status()['outbox'], {'uncertain':1})

    def test_parallel_workers_claim_once(self):
        self.conversation()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.relay.drain_one(),range(4)))
        self.assertEqual(sum(results),1)
        self.assertEqual(len(self.sent),1)

    def test_backup_can_restore_queue_without_production_data(self):
        cid=self.conversation()
        target=Path(self.tmp.name)/'backup.sqlite3'
        self.relay.backup(target)
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('SELECT id FROM conversations').fetchone()[0],cid)
            self.assertEqual(db.execute('SELECT count(*) FROM outbox').fetchone()[0],1)
        self.assertEqual(target.stat().st_mode & 0o777,0o600)
        with self.assertRaises(FileExistsError): self.relay.backup(target)

    def test_patient_cannot_be_clinician_or_relay_address(self):
        for email in ('doctor@gmail.com','info@clinic.example','anything@reply.clinic.example'):
            with self.assertRaises(mod.RelayError): self.relay.submit('Name',email,'Hi')

    def test_daily_submission_limit_is_durable(self):
        for _ in range(10): self.conversation()
        with self.assertRaisesRegex(mod.RelayError,'rate_limited'): self.conversation()

    def test_http_webhook_authentication_commit_and_disabled_state(self):
        from fastapi.testclient import TestClient
        from backend.app import main
        client = TestClient(main.app, base_url='https://testserver')
        previous = getattr(main.app.state, 'mail_relay', None)
        main.app.state.mail_relay = self.relay
        self.addCleanup(setattr, main.app.state, 'mail_relay', previous)
        cid = self.conversation()
        body, stamp, nonce, signature = self.signed(cid)
        headers = {'X-Relay-Timestamp':stamp, 'X-Relay-Nonce':nonce,
                   'X-Relay-Signature':signature, 'Content-Type':'application/json'}
        with patch.dict(os.environ, {'MAIL_RELAY_RECEIVE_ENABLED':'1'}):
            self.assertEqual(client.post(mod.ENDPOINT, content=body).status_code, 401)
            result = client.post(mod.ENDPOINT, content=body, headers=headers)
            self.assertEqual(result.status_code, 202)
            self.assertEqual(result.json(), {'status':'queued'})
            self.assertEqual(result.headers['Cache-Control'], 'no-store')
            self.assertEqual(client.post(mod.ENDPOINT, content=body, headers=headers).json(), {'status':'duplicate'})
            self.assertEqual(client.post(mod.ENDPOINT, content=b'x'*(mod.MAX_WEBHOOK+1)).status_code, 413)
        with patch.dict(os.environ, {'MAIL_RELAY_RECEIVE_ENABLED':'0', 'MAIL_RELAY_ENABLED':'0'}):
            self.assertEqual(client.post(mod.ENDPOINT, content=body, headers=headers).status_code, 404)
        self.assertEqual(self.relay.status()['outbox'], {'queued':2})

    def test_transport_distinguishes_ambiguous_data_from_safe_retry(self):
        smtp=MagicMock()
        smtp.mail.return_value=(250,b'ok'); smtp.rcpt.return_value=(250,b'ok')
        smtp.data.side_effect=TimeoutError()
        with patch.object(relay_mail.smtplib,'SMTP',return_value=smtp):
            self.assertEqual(relay_mail.smtp_send(self.settings,'patient@gmail.com',b'mail')[0],'uncertain')
        smtp.mail.side_effect=TimeoutError()
        with patch.object(relay_mail.smtplib,'SMTP',return_value=smtp):
            self.assertEqual(relay_mail.smtp_send(self.settings,'patient@gmail.com',b'mail')[0],'retry')


if __name__=='__main__': unittest.main()
