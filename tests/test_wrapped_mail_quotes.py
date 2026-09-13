"""Keep real reply text while removing wrapped Gmail attribution headers."""
from email.message import EmailMessage
from email import policy
from email.parser import BytesParser
import unittest
from backend.app import relay_mail


class WrappedQuoteTests(unittest.TestCase):
    def message(self, text, html=False):
        msg=EmailMessage()
        msg['From']='doctor@example.com'
        msg['To']='d.token@reply.example.com'
        msg['Message-ID']='<wrapped@example.com>'
        msg.set_content(text,subtype='html' if html else 'plain')
        return msg.as_bytes(policy=policy.SMTP)

    def test_arabic_wrapped_attribution_and_direction_controls(self):
        header='في الأحد، 13 سبتمبر 2026 في 7:58 م، تمت كتابة ما يلي بواسطة Zahnarztpraxis\nDr. Jaghsi <info@example.com>:'
        for prefix in ('','\u200f','\u202b'):
            text='تم تأكيد موعدكم.\nيرجى الحضور قبل الموعد بعشر دقائق.\n\n'+prefix+header+'\n> old message'
            self.assertEqual(relay_mail.sanitize_text(text),'تم تأكيد موعدكم.\nيرجى الحضور قبل الموعد بعشر دقائق.')

    def test_wrapped_german_and_english_headers(self):
        for header in ('On Sun, Sep 13, 2026, Clinic\n<info@example.com> wrote:',
                       'Am 13.09.2026 schrieb\nZahnarztpraxis Jaghsi\n<info@example.com>:'):
            self.assertEqual(relay_mail.sanitize_text('Your appointment is confirmed.\n\n'+header+'\nOld text'), 'Your appointment is confirmed.')

    def test_ordinary_dated_paragraphs_are_preserved(self):
        text='في 13 سبتمبر 2026 سأزور العيادة.\nأرجو تأكيد المعلومات التالية:\nالساعة الثامنة صباحًا.'
        self.assertEqual(relay_mail.sanitize_text(text),text)
        text='On 13 September I have an appointment.\nPlease confirm the time:\n08:00.'
        self.assertEqual(relay_mail.sanitize_text(text),text)

    def test_detection_does_not_cross_paragraph_boundary(self):
        text='On 13 September I visited the clinic.\n\nThis is what I wrote:\nPlease check my appointment.'
        self.assertEqual(relay_mail.sanitize_text(text),text)

    def test_html_attribution_outside_blockquote_is_removed(self):
        body='<div>Vielen Dank für Ihre Nachricht.</div><div class="gmail_attr">في الأحد 13 سبتمبر بواسطة Clinic:</div><blockquote>Old message</blockquote>'
        text,_=relay_mail.parse_reply(self.message(body,html=True),'doctor@example.com',())
        self.assertEqual(text,'Vielen Dank für Ihre Nachricht.')

    def test_quote_only_reply_remains_rejected(self):
        body='في الأحد، 13 سبتمبر 2026، تمت كتابة ما يلي بواسطة Clinic\n<info@example.com>:\nOld message'
        with self.assertRaisesRegex(relay_mail.InvalidMail,'empty_reply'):
            relay_mail.parse_reply(self.message(body),'doctor@example.com',())

    def test_rebuilt_reply_keeps_text_and_token_without_old_attribution(self):
        body='شكرًا، موعدكم مؤكد.\n\nفي الأحد، 13 سبتمبر 2026، تمت كتابة ما يلي بواسطة Clinic\nDr. Jaghsi <info@example.com>:\nOld message'
        text,_=relay_mail.parse_reply(self.message(body),'doctor@example.com',())
        raw=relay_mail.compose('info@clinic.example','patient@example.org','p.token@reply.clinic.example','ABC12345',text,'wrapped')
        msg=BytesParser(policy=policy.default).parsebytes(raw)
        self.assertEqual(msg['Reply-To'].addresses[0].addr_spec,'p.token@reply.clinic.example')
        self.assertEqual(msg['From'].addresses[0].addr_spec,'info@clinic.example')
        for kind in ('plain','html'):
            content=msg.get_body(preferencelist=(kind,)).get_content()
            self.assertIn('شكرًا، موعدكم مؤكد.',content)
            self.assertNotIn('تمت كتابة',content)
            self.assertNotIn('[E-Mail]',content)
