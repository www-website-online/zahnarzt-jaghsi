"""Isolated group routing, revocation and membership synchronization tests."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from backend.app import mail_relay, relay_group
from scripts.sync_relay_group import fetch_members, write_snapshot
from tests import test_mail_relay as base_tests


class GroupRelayTests(unittest.TestCase):
    setUp = base_tests.RelayTests.setUp
    transport = base_tests.RelayTests.transport
    conversation = base_tests.RelayTests.conversation
    raw = base_tests.RelayTests.raw
    signed = base_tests.RelayTests.signed

    def enable_group(self, members=('doctor@gmail.com', 'second@example.org')):
        self.memberfile = Path(self.tmp.name) / 'members.json'
        self.settings = replace(self.settings, group_address='team@clinic.example', group_members_file=self.memberfile)
        self.refresh(members)
        self.relay = mail_relay.Relay(self.settings, clock=lambda:self.now, transport=self.transport)

    def refresh(self, members):
        self.memberfile.write_text(json.dumps(relay_group.snapshot(self.settings.group_address, members,
                                                                  self.settings.token_secret, self.now)))

    def test_group_accepts_two_members_and_patient_replies_to_group(self):
        self.enable_group()
        cid=self.conversation();self.relay.drain_one()
        initial=self.sent[-1][1]
        self.assertEqual(self.sent[-1][0], 'team@clinic.example')
        for sender,domain,mid in [('doctor@gmail.com','gmail.com','<d1>'), ('second@example.org','example.org','<d2>')]:
            self.relay.receive(*self.signed(cid,message=self.raw(sender,'Reply',mid),domain=domain))
            self.relay.drain_one()
            self.assertEqual(self.sent[-1][0], 'patient@gmail.com')
            self.assertNotIn(sender,self.sent[-1][1].as_string())
        self.relay.receive(*self.signed(cid,'p',self.raw('patient@gmail.com','Thank you','<p1>')))
        self.relay.drain_one()
        self.assertEqual(self.sent[-1][0],'team@clinic.example')
        self.assertEqual(self.sent[-1][1]['References'],initial['Message-ID'])

    def test_removed_member_cannot_reply_to_old_direct_conversation(self):
        cid=self.conversation();self.relay.drain_one()
        self.enable_group()
        self.refresh(('second@example.org',))
        with self.assertRaisesRegex(mail_relay.RelayError,'not_group_member'):
            self.relay.receive(*self.signed(cid))
        self.relay.receive(*self.signed(cid,message=self.raw('second@example.org','New doctor','<new>'),domain='example.org'))
        self.relay.drain_one()
        self.assertEqual(self.sent[-1][0],'patient@gmail.com')
        self.relay.receive(*self.signed(cid,'p',self.raw('patient@gmail.com','Follow up','<follow>')))
        self.relay.drain_one()
        self.assertEqual(self.sent[-1][0],'team@clinic.example')

    def test_group_membership_never_replaces_domain_authentication(self):
        self.enable_group();cid=self.conversation()
        with self.assertRaisesRegex(mail_relay.RelayError,'sender_not_authenticated'):
            self.relay.receive(*self.signed(cid,message=self.raw('second@example.org'),domain='gmail.com'))
        with self.assertRaisesRegex(mail_relay.RelayError,'not_group_member'):
            self.relay.receive(*self.signed(cid,message=self.raw('stranger@gmail.com')))
        with self.assertRaises(mail_relay.RelayError):
            self.relay.receive(*self.signed(cid,'p',self.raw('second@example.org'),domain='example.org'))

    def test_stale_membership_blocks_new_submissions_and_both_reply_directions(self):
        self.enable_group();cid=self.conversation()
        self.now += relay_group.MAX_AGE+1
        for action in (lambda:self.conversation(), lambda:self.relay.receive(*self.signed(cid)),
                       lambda:self.relay.receive(*self.signed(cid,'p',self.raw('patient@gmail.com')))):
            with self.assertRaisesRegex(mail_relay.RelayError,'group_members_unavailable'):
                action()
        self.assertEqual(self.relay.status()['outbox'],{'queued':1})
        self.refresh(('doctor@gmail.com',))
        self.assertEqual(self.relay.receive(*self.signed(cid)),'queued')

    def test_group_mode_does_not_need_a_fixed_personal_mailbox(self):
        self.enable_group()
        self.settings = replace(self.settings, clinician='')
        self.relay = mail_relay.Relay(self.settings, clock=lambda:self.now, transport=self.transport)
        self.conversation(); self.relay.drain_one()
        self.assertEqual(self.sent[-1][0], 'team@clinic.example')
        plain = self.sent[-1][1].get_body(preferencelist=('plain',)).get_content()
        self.assertIn('I need an appointment.', plain)
        self.assertNotIn('[E-Mail]', plain)

    def test_staff_and_group_cannot_be_patient(self):
        self.enable_group()
        for address in ('doctor@gmail.com','second@example.org','team@clinic.example'):
            with self.assertRaisesRegex(mail_relay.RelayError,'invalid_patient'):
                self.relay.submit('Staff',address,'Hello')


class MembershipSnapshotTests(unittest.TestCase):
    def test_only_fresh_correctly_signed_matching_group_members_are_trusted(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'members.json'
            valid=relay_group.snapshot('team@example.org',['One@gmail.com'],'s'*64,1000)
            path.write_text(json.dumps(valid))
            self.assertEqual(relay_group.load_members(path,'team@example.org','s'*64,1100),{'one@gmail.com'})
            for group,secret,now in [('other@example.org','s'*64,1100),('team@example.org','x'*64,1100),
                                     ('team@example.org','s'*64,1400),('team@example.org','s'*64,900)]:
                with self.assertRaises(relay_group.MembershipUnavailable):
                    relay_group.load_members(path,group,secret,now)
            valid['payload']['members'].append('attacker@gmail.com')
            path.write_text(json.dumps(valid))
            with self.assertRaises(relay_group.MembershipUnavailable):
                relay_group.load_members(path,'team@example.org','s'*64,1100)

    def test_invalid_empty_and_partial_membership_snapshots_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'members.json'
            for value in ('{', '{}', json.dumps(relay_group.snapshot('team@example.org',[],'s'*64,1000)),
                          json.dumps(relay_group.snapshot('team@example.org',['invalid'],'s'*64,1000))):
                path.write_text(value)
                with self.assertRaises(relay_group.MembershipUnavailable):
                    relay_group.load_members(path,'team@example.org','s'*64,1100)

    def test_snapshot_written_atomically_with_restricted_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'members.json'
            value=relay_group.snapshot('team@example.org',['one@gmail.com'],'s'*64,1000)
            write_snapshot(path,value)
            self.assertEqual(path.stat().st_mode & 0o777,0o640)
            self.assertEqual(relay_group.load_members(path,'team@example.org','s'*64,1100),{'one@gmail.com'})


class DirectorySyncTests(unittest.TestCase):
    def user(self,email,status='ACTIVE'):
        return {'type':'USER','role':'MEMBER','status':status,'email':email}

    def session(self,*pages):
        session=Mock()
        session.get.side_effect=[Mock(status_code=200,json=Mock(return_value=p)) for p in pages]
        return session

    def test_pagination_and_inactive_members(self):
        session=self.session({'members':[self.user('one@gmail.com')],'nextPageToken':'page2'},
                             {'members':[self.user('two@example.org'),self.user('old@example.org','SUSPENDED')]})
        self.assertEqual(fetch_members(session,'team@example.org'),{'one@gmail.com','two@example.org'})
        self.assertEqual(session.get.call_count,2)
        self.assertEqual(session.get.call_args.kwargs['allow_redirects'],False)
        self.assertIn('team%40example.org',session.get.call_args.args[0])

    def test_nested_empty_and_denied_group_are_not_published(self):
        for session in (self.session({'members':[{'type':'GROUP','email':'nested@example.org'}]}),
                        self.session({'members':[]}), Mock(get=Mock(return_value=Mock(status_code=403)))):
            with self.assertRaises(relay_group.MembershipUnavailable):
                fetch_members(session,'team@example.org')

    def test_pagination_loop_fails_without_publishing_partial_membership(self):
        page={'members':[self.user('one@gmail.com')],'nextPageToken':'repeat'}
        with self.assertRaises(relay_group.MembershipUnavailable):
            fetch_members(self.session(page,page),'team@example.org')


if __name__=='__main__':
    unittest.main()
