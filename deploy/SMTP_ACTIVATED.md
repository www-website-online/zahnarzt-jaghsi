# Contact mail activated — 2026-09-13

The contact form is enabled in German and Arabic. Configuration is in
`/etc/systemd/system/zahnarzt.service.d/smtp-relay.conf`.

- SMTP host: `smtp-relay.gmail.com`, port 587, mandatory STARTTLS.
- Sender and recipient: `info@zahnarzt-jaghsi.de`.
- Authentication: Google Workspace IP relay; no mailbox password is configured.
- The application restart took approximately 1 second.
- Exactly one test was submitted through the live form at 07:32 UTC.
- Google SMTP accepted it; the form returned HTTP 200 and its success message.
- Subject: `Kontaktanfrage / رسالة تواصل — Zahnarztpraxis`.
- The message contains `SMTP activation test 2026-09-13 07:32 UTC` and synthetic test text.
- Inbox delivery has not been independently verified; a group member must confirm receipt.
- Public Arabic contact page returned 200 in Chromium and the message form was visible.
- App health is OK, relevant services remain active and checked logs show no new errors.

Preparation, activation and single-send records are in:
`/var/backups/zahnarzt-smtp-20260913T071829Z`.

## Rollback

In an approved maintenance window, move the SMTP drop-in into a NEW filename under the
backup directory (do not overwrite an existing rollback file), run `systemctl daemon-reload`,
then `systemctl restart zahnarzt`. The form will again show telephone/booking contact until
mail is configured. Verify `/healthz`, the contact page and recent logs afterward.
The Google Workspace relay rule is separate and is not removed by this server rollback.
