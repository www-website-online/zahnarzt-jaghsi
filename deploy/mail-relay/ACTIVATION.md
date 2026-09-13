# Receive-only activation — 2026-09-13

## Update: contact-form trial at 2026-09-13 12:03 UTC

The user requested execution of the website reply flow. Added and tested
`MAIL_RELAY_TEST_PATIENT`: only the selected patient address uses the new relay
while `MAIL_RELAY_ENABLED=0`. Production configuration selects
`tamerfaour@gmail.com` with receiving enabled. Other website inquiries retain
legacy delivery. This supersedes the receive-only form behavior described below.

41 Python tests pass, including real form routing tests for the selected patient,
other patients and receiver-disabled behavior. The service restarted successfully
and public health remains ok, with no error log lines after the live test.

Authorized website submission `20260913T120312Z` created conversation
`b85138827b4192e98994cf08`. Outbox SMTP status is accepted, first attempt.
Subject: `Zahnarztpraxis Dr. Jaghsi – Anfrage B8513882`.
From is the clinic address; recipient is the configured doctor and Reply-To is a
signed doctor-role address under reply.zahnarzt-jaghsi.de. Inbox arrival and the
reply through Cloudflare remain unverified. Catch-all must be active for the reply.

Rollback for this trial: remove the MAIL_RELAY_TEST_PATIENT setting (or restore
its private before-trial environment backup) and perform an approved service
restart. Existing conversation reception can remain enabled. No records need
removal. Original files and private configuration are backed up at
`/var/backups/zahnarzt-relay-deploy/form-test-20260913T115354Z/`.

The user explicitly approved installing receive-only configuration, initializing
the separate conversation database, backups and restarting the production app.

Installed:

- `/etc/zahnarzt/mail-relay.env` (0600; values never included here).
- `/etc/systemd/system/zahnarzt.service.d/mail-relay.conf`.
- `/var/lib/zahnarzt-relay/relay.sqlite3` (0600, owned by www-data; directory 0700).
- `zahnarzt-relay-backup.service` and enabled daily backup timer.

`MAIL_RELAY_RECEIVE_ENABLED=1`, `MAIL_RELAY_ENABLED=0`: existing website form
delivery remains in use. No test conversation or outgoing email was created in
this activation. Catch-all was saved to the Worker but still disabled in the
latest user screenshot.

Validation:

- All three systemd unit files passed `systemd-analyze verify` before restart.
- App restarted successfully; local and public `/healthz` return 200 and status ok.
- Public unsigned webhook returns 401.
- Signed empty test payload returns 400/invalid_payload, proving signature
  acceptance and application validation without adding messages to the queue.
- Queue and review list empty.
- First consistent backup: `/var/backups/zahnarzt-relay/relay-20260913T113419879250Z.sqlite3`;
  45056 bytes, mode 0600, integrity ok, zero conversations/outbox rows.
- Backup timer active. This verifies snapshot integrity, not delivery to an inbox.
- Python urllib public requests returned 403; equivalent curl requests succeeded.
  Real Worker-to-server delivery still needs testing; no WAF changes were made.

Deployment rollback material (private):
`/var/backups/zahnarzt-relay-deploy/20260913T113231Z/` contains verified service
backup, original source archive and a separate private copy of relay secrets.
Original service configuration and source were preserved; no DNS was changed
by the server activation.

For an approved rollback, move the new mail-relay.conf drop-in into this private
backup directory, reload systemd, restart zahnarzt and check /healthz. Preserve
the database and secret file. This stops all relay reception; the contact form
already follows the legacy path in receive-only mode. Do not delete relay data.

Remaining gates from README.md: enable the saved catch-all for controlled tests,
prove provider authentication-header provenance, test actual doctor/patient
message flow and SMTP authentication/inbox delivery, review mixed apex MX and
duplicate DMARC records, then explicitly activate new website conversations.
Cloudflare REPLY_DOMAIN is stored as a Secret in the dashboard; its string value
is still the configured reply subdomain. Preserve this when changing deployment
methods. The partial screenshot exposure of the original webhook key was
identified; rotation was declined, so the server uses the original copied key.


## Worker transport correction — 2026-09-13 13:04 UTC

The doctor reply for test B8513882 bounced with `Clinic relay unavailable`.
The local Worker used `redirect: error`, which workerd rejects before the
HTTP request. Changed only the transport option to `redirect: manual`; the
existing status check still acknowledges only HTTP 202 and rejects redirects.
No server configuration, secrets, DNS, or production services changed.

Validation: the original Worker reproduced the exact rejection in the isolated
workerd runtime; the corrected Worker passed the same signed-webhook test and
refused a redirect. All four Node tests passed. Public health returned OK.
Runtime test (install workerd in a temporary directory, not production deps):
`workerd test deploy/mail-relay/worker.runtime-test.capnp relay-test`.

Backup: `/tmp/zahnarzt-worker-fix-20260913T130134Z/`.
**Cloudflare deployment remains pending:** in the dashboard Worker code replace
`redirect: 'error'` with `redirect: 'manual'` and Deploy. Then have the doctor
reply again to the original B8513882 inquiry (not the delivery failure email).
Live patient delivery remains unverified until that test completes.
