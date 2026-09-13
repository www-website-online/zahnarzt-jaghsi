# Clinic email relay — activation runbook

Status: implemented, disabled by default. Offline tests do not establish live
Cloudflare authentication, DNS, SMTP delivery or inbox placement. Do not enable
new website conversations until the acceptance checks below pass.

## Addresses and behavior

- Public From: `info@zahnarzt-jaghsi.de`.
- Doctor mailbox: `tamerfaowr@gmail.com`.
- Patient test mailbox: `tamerfaour@gmail.com` (different spelling).
- Incoming replies: unique signed addresses at `reply.zahnarzt-jaghsi.de`.

Website form -> server durable queue -> doctor. Doctor's ordinary Reply ->
Cloudflare inbound Worker -> signed HTTPS webhook -> server queue -> patient.
Patient's ordinary Reply follows the reverse path. Outbound messages are rebuilt
with the clinic From address and a conversation-specific Reply-To; private
addresses are not copied into the other party's headers. The recipient sees
the reply subdomain when inspecting Reply-To. Replying manually to the root
`info@` address does not select a conversation.

The existing Google SMTP relay sends outbound mail. Cloudflare is used only for
inbound routing and Worker execution within its free allowance. Do not activate
Cloudflare Email Sending, purchase a Workspace license, or change a paid plan.
Reference: https://developers.cloudflare.com/email-service/platform/pricing/

Version 1 accepts text only (512 KiB raw message, 20,000 text characters).
Attachments are explicitly rejected, not silently dropped. Quotes and email
addresses in text are removed to limit disclosure; this is not a guarantee that
free text contains no identifying information. Reply addresses expire after 180
days; expiry does not delete records. Initial form submissions: 10 per patient
per day and 200 total per day; replies: 30 per conversation per hour.

## Prepared files

- `worker.mjs`, `wrangler.jsonc`: inbound Cloudflare Worker; no secrets included.
- `systemd.conf`: additional app environment and writable directory.
- `zahnarzt-relay-backup.service`, `.timer`: daily consistent SQLite snapshot.
- `scripts/relay_admin.py`: config preflight, backup checks and explicit recovery.

## Activation order

1. Keep `MAIL_RELAY_ENABLED=0`. Back up the existing code and service drop-ins.
   Obtain the production approval required by AGENTS.md before creating the
   production database, changing DNS or restarting the service.
2. Create `/etc/zahnarzt/mail-relay.env` using `scripts/relay_admin.py create-config`
   (exclusive creation, mode 0600). Never paste its contents into chat or logs.
   Preflight using `--env-file /etc/zahnarzt/mail-relay.env preflight` is read-only.
   Create `/var/lib/zahnarzt-relay` owned by the app user `www-data`, mode 0700.
   Install the prepared systemd drop-in, retaining existing SMTP settings.
   Generated config has receive enabled but new website conversations disabled.
3. In Cloudflare, create Worker `zahnarzt-reply-relay` from `worker.mjs` or deploy
   with the supplied Wrangler config from an authenticated administrator session.
   Add secret `RELAY_WEBHOOK_SECRET` equal to `MAIL_RELAY_WEBHOOK_SECRET` in the
   private server configuration. Transfer directly over an authenticated channel;
   never display it in tool output. Set the two plain variables from wrangler.jsonc.
   Do not upload `MAIL_RELAY_TOKEN_SECRET`: it remains exclusively on the server.
4. Email Routing -> domain -> Settings -> Subdomains: add
   `reply.zahnarzt-jaghsi.de`. Cloudflare creates the subdomain's mail DNS records.
   Route its incoming addresses to the Worker. If only a zone-wide catch-all is
   available, it may be used only after checking apex mail goes exclusively to
   Google; the Worker explicitly rejects other domains and unknown token shapes.
   Preserve Google root reception and the existing info group. Export DNS before
   any changes. Do not let a setup wizard replace Google apex MX with Cloudflare.
   Reference: https://developers.cloudflare.com/email-service/configuration/subdomains/
5. Activate the receive-only server deployment with an approved service restart.
   Validate health and recent error logs. An unsigned webhook must be rejected
   with 401; a disabled receiver gives 404. There must be no queued real patient
   mail during setup. Create only an explicitly authorized test conversation.
6. **Authentication acceptance gate:** Worker currently expects Cloudflare's own
   newest `ARC-Authentication-Results` entry with `mx.cloudflare.net` and aligned
   `dmarc=pass`. Confirm this header is generated before the email handler runs,
   and confirm forged/pre-existing ARC results cannot override a failed or missing
   provider result. Test both valid Gmail and a controlled forged-header message.
   Do not enable the relay if provenance/ordering cannot be established; replace
   the adapter with a verified provider authentication mechanism first. A header
   name alone is not cryptographic proof. Do not bypass this gate by accepting
   arbitrary Authentication-Results or by allowing all senders.
7. Exercise all three legs using the distinct doctor/patient test addresses.
   Check actual From, Reply-To, threading, authentication and received body at
   both inboxes. Test duplicate webhook delivery, wrong sender and attachment
   rejection. Check outbox is accepted and has no failed/uncertain deliveries.
   SMTP acceptance is not proof of inbox delivery; check both test inboxes.
8. Review current root DNS independently: screenshots had three duplicate DMARC
   records and mixed Google/Cloudflare MX. Re-read DNS, back it up, consolidate
   DMARC and configure aligned Google DKIM with explicit DNS authorization.
   Never copy a DKIM key from another domain or infer values from screenshots.
9. Install and verify the backup timer; verify a snapshot using `verify-backup`.
   Only after all gates pass set `MAIL_RELAY_ENABLED=1` and perform the approved
   restart. Submit one authorized live form test and check both reply directions.

## Operations and recovery

`GET /admin/mail-relay/status` uses existing administrator authentication and
returns queue counts and review IDs without email addresses or bodies. The CLI
`status` uses private server configuration. Check failed/uncertain items and logs
regularly; no new alert delivery service is configured.

Known temporary SMTP failures retry with backoff. A lost connection after DATA
or an expired in-flight lease is held as `uncertain` to avoid duplicate delivery.
Investigate SMTP delivery evidence before `resolve ID --action retry|accepted|cancel
--confirm-delivery-checked`. This records an audit event; no content is deleted.
`accepted` means SMTP acceptance, not a read receipt. Closing a conversation
blocks new replies and preserves history; already queued messages remain queued.

Backup command creates private timestamped SQLite snapshots with integrity
checking. Also preserve the private environment file separately: restoring the
database without its original token secret invalidates existing reply addresses.
Restore must be explicitly approved: stop app writes, preserve current database,
verify the snapshot, restore under the original filename and ownership, then
restart and check status. Old in-flight items require delivery review before retry.
No automatic retention deletion is installed.

Rollback for new inquiries: set `MAIL_RELAY_ENABLED=0` while retaining
`MAIL_RELAY_RECEIVE_ENABLED=1`; approved restart returns the contact form to its
previous behavior while existing conversations can still receive replies.
Full code rollback also stops relay reception; retain the new database, secrets
and backups, and notify the operator that old reply addresses will stop working.
Restore only files changed by this deployment from the timestamped source backup;
never overwrite unrelated edits or delete stored conversations.
