# Clinic mail presentation

Prepared 2026-09-13. Activated with explicit user approval at 2026-09-13T13:48:51.511127+00:00; service zahnarzt restarted successfully.

- Multipart alternative: styled HTML and equivalent plain text.
- Existing subject, Message-ID references, recipients and reply token preserved.
- Reply-To display name: Zahnarztpraxis Jaghsi. Mail clients may still show the full routing address.
- Patient name and request reference appear in both directions.
- Clinic signature uses the same CLINIC_NAME, CLINIC_ADDRESS and CLINIC_PHONE_LANDLINE variables/defaults as the website.
- Arabic layout when Arabic letters predominate in message text; German otherwise. Language is selected per message, not persisted as a patient preference.
- Old bilingual footer and new signature delimiter are stripped from replies; Arabic Gmail quotation headers also recognized.
- Escaped user text; no embedded remote images, tracking, scripts or attachments.

Validation: 45 isolated unittest tests passed; desktop German and 390px Arabic previews had no horizontal overflow. Browser review is not a live Gmail/Outlook rendering guarantee.

Previews (fictional data): /tmp/zahnarzt-mail-preview/clinic-reply-de.html and clinic-reply-ar.html.
Backup: /tmp/zahnarzt-mail-presentation-backup-20260913T132934Z/
Rollback after deployment: restore backend/app/relay_mail.py and backend/app/mail_relay.py from this backup, then restart zahnarzt with approval. No database schema/configuration changes or message replay required.

Existing queued mail keeps its previously composed format. Only messages composed after activation use the new format. Gmail account avatar and domain verification are separate settings. The existing restricted form trial remains in place.

Activation verification: new process running, local and public health endpoints OK, relay receiver enabled, no recent service errors. No live test email was sent during this deployment. A fresh conversation reply can verify the recipient’s email-client rendering.
