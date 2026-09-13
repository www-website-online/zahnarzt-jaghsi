# Wrapped reply attribution cleanup

Activated 2026-09-13T18:35:44.370387+00:00 after 74 isolated tests and production preflight.
The relay removes wrapped Arabic/German/English Gmail attribution headers from
rebuilt replies, including direction marks. Detection is bounded to four adjacent
lines, does not cross empty paragraphs and requires a dated wrapped attribution.
HTML gmail_attr blocks are excluded along with quoted history.
Ordinary reply text, clinic presentation and all-patient group routing are preserved.
This affects messages rebuilt by the relay; it cannot change Gmail's own composer
or historical messages already delivered.

Production service running with a new process, public/local health OK, no recent
application errors. No real email sent during verification. SMTP acceptance is
not being claimed as live recipient verification.
Backup: /tmp/zahnarzt-quote-format-20260913T183312Z/relay_mail.py
Rollback: restore this file to backend/app/relay_mail.py and restart zahnarzt with
approval. No configuration or database changes were made by this formatting fix.
