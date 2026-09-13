# Group relay enabled for all form patients

Activated: 2026-09-13T17:56:25.461254+00:00
User explicitly requested all-patient rollout after group integration was installed.
MAIL_RELAY_ENABLED=1; MAIL_RELAY_TEST_PATIENT removed.
Group: info@zahnarzt-jaghsi.de. Two current direct members are synchronized.

Verified running process uses the new flag, group and signed fresh membership.
Both previously used patient addresses and an unrelated synthetic address select
relay delivery. Public/local health OK; no recent application errors. Sync timer
active and latest synchronization successful. No database rewrite or queue replay.
The 67 isolated behavior tests passed during group activation; no code changed
for this rollout. SMTP settings, webhook/token secrets and DNS were preserved.

Live delivery through Google Groups, preservation of Reply-To, and the complete
member-to-patient roundtrip still require a new test message after rollout.
No live test email was sent as part of this rollout. Historical ordinary emails
retain direct Reply-To; test using a new form inquiry, not an old message.

Verified configuration rollback copy: /etc/zahnarzt/backups/all-patients-20260913T175540Z/mail-relay.env
Restore it to /etc/zahnarzt/mail-relay.env (root 0600) and restart zahnarzt with
approval to return to group trial mode. The membership timer can stay running.
Existing relay conversations remain receivable; do not modify database records.
This activation supersedes the trial-only status in GROUP_ACTIVATED.md.
