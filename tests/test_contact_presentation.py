"""Formatting on the ordinary form path must not depend on trial membership."""
import os
import unittest
from unittest.mock import patch

from backend.app import contact


class ContactPresentationTests(unittest.TestCase):
    def test_every_sender_gets_html_and_preserves_direct_reply_routing(self):
        environment = {'SMTP_HOST':'smtp.example.test', 'SMTP_FROM':'info@clinic.example',
                       'CONTACT_TO':'team@clinic.example', 'MAIL_RELAY_TEST_PATIENT':'trial@example.test',
                       'SMTP_SECURITY':'starttls'}
        with patch.dict(os.environ,environment), patch.object(contact.smtplib,'SMTP') as smtp:
            client=smtp.return_value.__enter__.return_value
            client.send_message.return_value={}
            for sender in ('trial@example.test','another@example.test'):
                self.assertTrue(contact.deliver('Example Patient',sender,'Guten Tag, ich habe eine Frage.'))
                message=client.send_message.call_args.args[0]
                self.assertEqual(message['To'],'team@clinic.example')
                self.assertEqual(message['Reply-To'].addresses[0].addr_spec,sender)
                self.assertEqual(message.get_content_type(),'multipart/alternative')
                self.assertEqual(message['From'].addresses[0].display_name,'Zahnarztpraxis Dr. Jaghsi')
                for kind in ('html','plain'):
                    body=message.get_body(preferencelist=(kind,)).get_content()
                    self.assertIn('Example Patient',body)
                    self.assertIn(sender,body)
                    self.assertIn('Karl-Marx-Straße 214',body)
                self.assertEqual(list(message.iter_attachments()),[])

    def test_arabic_contact_message_escapes_markup_without_losing_patient_details(self):
        environment = {'SMTP_HOST':'smtp.example.test','SMTP_FROM':'info@clinic.example',
                       'CONTACT_TO':'team@clinic.example','SMTP_SECURITY':'starttls'}
        with patch.dict(os.environ,environment), patch.object(contact.smtplib,'SMTP') as smtp:
            client=smtp.return_value.__enter__.return_value
            client.send_message.return_value={}
            self.assertTrue(contact.deliver('<img src=x>', 'patient@example.test', 'مرحبًا بكم في العيادة، لدي استفسار <b>وشكرًا</b>'))
            message=client.send_message.call_args.args[0]
            html=message.get_body(preferencelist=('html',)).get_content()
            self.assertEqual(message['Content-Language'],'ar')
            self.assertIn('dir="rtl"',html)
            self.assertIn('&lt;img src=x&gt;',html)
            self.assertIn('&lt;b&gt;وشكرًا&lt;/b&gt;',html)
            self.assertIn('patient@example.test',html)
            self.assertNotIn('مرفقات',html)  # Direct replies do not use the text-only relay.


if __name__=='__main__':
    unittest.main()
