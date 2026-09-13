# Unified form email presentation

Activated 2026-09-13T15:04:39.535428+00:00 after user approval and a successful zahnarzt restart.

Both ordinary contact delivery and the trial relay use the shared HTML/plain-text template.
Ordinary form mail keeps CONTACT_TO and the patient's direct Reply-To, includes patient email
in the clinic-facing metadata, and uses the same clinic display name and reference-style subject.
Relay token routing remains unchanged. Google group membership mode remains unconfigured.
The group synchronization timer and Google credentials have not been installed by this change.

Validation: 59 isolated tests passed, including non-trial senders, Arabic and HTML escaping,
SMTP/TLS and reply routing. Production Python MIME preflight passed with SMTP mocked.
New process running, local/public health OK, no recent service errors. No live test email sent.
Google Groups can still append its own subscription footer; that is a separate group setting.
Old messages in existing inboxes are unchanged.

Backup: /tmp/zahnarzt-all-form-format-20260913T145132Z
Rollback: restore backend/app/contact.py, backend/app/mail_presentation.py and
backend/app/relay_mail.py from this backup, then restart zahnarzt with approval.
Do not change or replay the database.
