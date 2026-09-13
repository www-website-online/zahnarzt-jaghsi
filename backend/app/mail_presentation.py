"""Clinic email layout: escaped HTML and an equivalent plain-text alternative."""
from html import escape
import os
import re


def presentation(text, reference, patient_name='', target_role='p', *, patient_email='', relay=True):
    """Use Arabic when predominant in the message, otherwise clinic-default German."""
    arabic = len(re.findall(r'[\u0621-\u064a\u066e-\u06d3]', text))
    latin = len(re.findall(r'[A-Za-zÄÖÜäöüß]', text))
    lang = 'ar' if arabic > latin else 'de'
    labels = {
        'ar': ('مراسلات العيادة', 'رقم الطلب', 'اسم المريض', 'رسالة المريض', 'رد العيادة',
               'للمتابعة، اضغط «رد» على هذه الرسالة.', 'يرجى إرسال نص فقط دون مرفقات.', 'الهاتف'),
        'de': ('Praxis-Korrespondenz', 'Anfragenummer', 'Patient/in', 'Nachricht der Patientin / des Patienten',
               'Antwort der Praxis', 'Für Rückfragen antworten Sie einfach auf diese E-Mail.',
               'Bitte senden Sie nur Text, keine Anhänge.', 'Telefon')
    }[lang]
    caption, ref_label, name_label, from_patient, from_clinic, reply_hint, attachment_hint, phone_label = labels
    if not relay:
        reply_hint = ('للتواصل مع المريض، اضغط «رد» أو استخدم بريده الموضح أعلاه.' if lang == 'ar'
                      else 'Antworten Sie über die Antwortfunktion oder an die oben angegebene E-Mail-Adresse der Patientin / des Patienten.')
        attachment_hint = ''
    heading = from_patient if target_role == 'd' else from_clinic
    clinic = os.getenv('CLINIC_NAME', 'ZAHNARZTPRAXIS – M.Sc. Abdulaziz Jaghsi')
    address = os.getenv('CLINIC_ADDRESS', 'Karl-Marx-Straße 214, 12055 Berlin')
    phone = os.getenv('CLINIC_PHONE_LANDLINE', '(030) 685 10 44')
    website = 'https://zahnarzt-jaghsi.de'
    metadata = [f'{ref_label}: {reference}']
    if patient_name:
        metadata.append(f'{name_label}: {patient_name}')
    if patient_email:
        metadata.append(f"{'البريد الإلكتروني' if lang == 'ar' else 'E-Mail'}: {patient_email}")
    footer = f'{clinic}\n{address}\n{phone_label}: {phone}\n{website}\n\n{reply_hint}\n{attachment_hint}'
    plain = f'{heading}\n' + '\n'.join(metadata) + f'\n\n{text}\n\n-- \n{footer}\n'
    direction, align = ('rtl', 'right') if lang == 'ar' else ('ltr', 'left')
    # Untrusted names and messages never become URLs, styles, or attributes.
    rows = ''.join(f'<div style="margin:4px 0">{escape(item)}</div>' for item in metadata)
    safe_text = escape(text).replace('\n', '<br>')
    html = f'''<!doctype html>
<html lang="{lang}" dir="{direction}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f2f7f6;color:#173d3e;font-family:Arial,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border:1px solid #d8e6e3;border-radius:12px;text-align:{align}" dir="{direction}">
<tr><td style="padding:26px 28px;border-top:5px solid #0d8980;border-bottom:1px solid #e1ece9">
<div dir="ltr" style="font-size:20px;font-weight:bold;color:#087c74">Zahnarztpraxis Jaghsi</div>
<div style="font-size:13px;color:#526e6b;margin-top:8px">{escape(caption)}</div></td></tr>
<tr><td style="padding:24px 28px 18px"><h1 style="font-size:19px;line-height:1.5;margin:0 0 12px">{escape(heading)}</h1>
<div style="font-size:13px;line-height:1.7;color:#526e6b">{rows}</div></td></tr>
<tr><td style="padding:0 28px 28px;font-size:16px;line-height:1.8;color:#203735;overflow-wrap:anywhere">{safe_text}</td></tr>
<tr><td class="clinic-footer" style="padding:22px 28px;background:#f6faf9;border-top:1px solid #e1ece9;font-size:13px;line-height:1.8">
<div dir="ltr" style="font-weight:bold">{escape(clinic)}</div>
<div dir="ltr">{escape(address)}</div><div>{escape(phone_label)}: <span dir="ltr" style="display:inline-block;direction:ltr;unicode-bidi:embed">{escape(phone)}</span></div>
<a href="{website}" style="color:#087c74;text-decoration:underline" dir="ltr">zahnarzt-jaghsi.de</a>
<div style="margin-top:16px">{escape(reply_hint)}</div><div style="color:#526e6b">{escape(attachment_hint)}</div>
</td></tr></table></td></tr></table></body></html>'''
    return plain, html, lang
