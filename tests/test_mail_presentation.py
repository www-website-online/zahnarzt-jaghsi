"""Mail layout must preserve routing, text safety, and reply extraction."""
from email import policy
from email.parser import BytesParser
import unittest

from backend.app import relay_mail
from backend.app.mail_presentation import presentation


class MailPresentationTests(unittest.TestCase):
    def test_html_is_escaped_and_plaintext_is_equivalent(self):
        text = 'Vielen Dank.\n<script>alert(1)</script> & weitere Fragen'
        plain, html, lang = presentation(text, 'ABC12345', '<img src=x onerror=alert(1)>', 'd')
        self.assertEqual(lang, 'de')
        self.assertIn(text, plain)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img', html)
        for body in (plain, html):
            self.assertIn('ABC12345', body)
            self.assertIn('Karl-Marx-Straße 214', body)
            self.assertIn('685 10 44', body)
        self.assertNotIn('مراسلات العيادة', plain)

    def test_arabic_uses_rtl_and_single_language_instructions(self):
        plain, html, lang = presentation('شكرًا لتواصلكم مع العيادة. يمكنكم الرد على هذه الرسالة.', 'ABC12345', 'اسم تجريبي')
        self.assertEqual(lang, 'ar')
        self.assertIn('lang="ar" dir="rtl"', html)
        self.assertIn('رد العيادة', plain)
        self.assertIn('اضغط «رد»', plain)
        self.assertNotIn('Für Rückfragen', plain)

    def test_multipart_keeps_reply_address_and_thread_headers(self):
        raw = relay_mail.compose('info@clinic.example', 'patient@example.test',
            'p.token@reply.clinic.example', 'ABC12345', 'Vielen Dank.', 'new',
            '<relay.old@clinic.example>', patient_name='Example Patient')
        mail = BytesParser(policy=policy.default).parsebytes(raw)
        self.assertEqual(mail.get_content_type(), 'multipart/alternative')
        self.assertEqual(mail['Reply-To'].addresses[0].addr_spec, 'p.token@reply.clinic.example')
        self.assertEqual(mail['Reply-To'].addresses[0].display_name, 'Zahnarztpraxis Jaghsi')
        self.assertEqual(mail['References'], '<relay.old@clinic.example>')
        self.assertEqual(mail['In-Reply-To'], '<relay.old@clinic.example>')
        self.assertEqual(mail['Message-ID'], '<relay.new@clinic.example>')
        self.assertIn('Vielen Dank.', mail.get_body(preferencelist=('plain',)).get_content())
        self.assertIn('Vielen Dank.', mail.get_body(preferencelist=('html',)).get_content())
        self.assertEqual(list(mail.iter_attachments()), [])

    def test_old_and_new_footers_and_arabic_gmail_quotes_are_stripped(self):
        for tail in (
            relay_mail.MARKER + '\nLegacy footer',
            '-- \nZAHNARZTPRAXIS\nNew footer',
            'في الأحد، 13 سبتمبر 2026، تمت كتابة ما يلي بواسطة العيادة:\nOld message',
        ):
            self.assertEqual(relay_mail.sanitize_text('شكرًا لكم\n\n' + tail), 'شكرًا لكم')
        parser = relay_mail.TextHTML()
        parser.feed('<div>New reply</div><table><tr><td class="clinic-footer">Old signature</td></tr></table>')
        self.assertEqual(''.join(parser.parts).strip(), 'New reply')


if __name__ == '__main__':
    unittest.main()
