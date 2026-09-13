# Google Group routing — implementation prepared, not activated

## Behavior

The website sends clinic-facing mail to a stable Google Group. Authorized
direct USER members (excluding explicit inactive account states) can reply from their own mailboxes. Patients receive the
rebuilt reply from `info@zahnarzt-jaghsi.de`. The patient-side sender check stays
bound to the original patient. A group member cannot substitute another patient.

`MAIL_RELAY_GROUP` enables this mode. With no group configured the existing
single-clinician route works unchanged. In group mode, even existing conversations
route their next clinic-facing message to the current group and verify the
doctor against current group members. No database migration or history rewrite.
Already composed outbox messages retain their existing destinations; deploy
only with no pending/inflight messages (review failures separately).

The existing trial flag stays in place until the live group test is complete.

## Google setup required from the Workspace administrator

1. Create a dedicated private group, proposed `team@zahnarzt-jaghsi.de`.
   The selected address must be a real Google Group, not a Cloudflare forwarding rule.
   Add clinic staff as direct individual members; allow the required external
   Gmail accounts. Set their subscription to **Each email / All mail**.
   Conversation visibility is members only; joining and member management are
   controlled by the owner/managers. Do not add patients. Nested groups are not
   supported by this implementation and stop membership synchronization.
2. Ensure the website's `info@zahnarzt-jaghsi.de` sender may post to the group.
   Verify this with a controlled message before changing posting permissions.
   In Email options → Post replies to, select **A recipient that the sender
   chooses** (`REPLY_TO_IGNORE` in Groups Settings API). Verify the delivered
   `Reply-To` remains the exact per-conversation address at `reply.zahnarzt-jaghsi.de`.
   Disable group automatic replies and avoid subject prefixes/footer modifications.
3. In an existing Google Cloud project, enable **Admin SDK API**, create a dedicated
   service account and configure Workspace domain-wide delegation. Grant only:
   `https://www.googleapis.com/auth/admin.directory.group.member.readonly`
   The delegated Workspace admin needs permission to read group memberships.
   This scope can read group memberships in the organization; the sync code
   requests only the configured clinic group. It cannot read mail or change members.
   Administrator consent is required; do not substitute a general Gmail/Drive token.
4. Place the service-account JSON directly on the server at
   `/etc/zahnarzt/group-directory-service-account.json`, root-owned 0600. Do not
   paste its private key into chat, source control, screenshots or logs. Fill the
   admin email and group address in the separate 0600 `group-sync.env` template.

Google references:
- https://developers.google.com/workspace/admin/directory/reference/rest/v1/members/list
- https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority
- https://support.google.com/groups/answer/2464926
- https://developers.google.com/workspace/admin/groups-settings/v1/reference/groups

## Server deployment, after Google setup

1. Preserve timestamped copies of the live environment and service configuration.
   Current code rollback backup: `/tmp/zahnarzt-group-backup-20260913T141206Z/`.
   Verify it contains `backend/app/mail_relay.py`, `backend/app/relay_mail.py`,
   and `scripts/relay_admin.py`. The presentation feature remains in that backup.
2. Install `group-sync-requirements.txt` into an isolated virtualenv at
   `/opt/zahnarzt-group-sync`. Do not change the website virtualenv.
3. Provision `/var/lib/zahnarzt-relay-members` as root:www-data 0750. Snapshots
   are root:www-data 0640; the website must have read access and no write access
   to this directory. The sync service alone reads the Google private key.
4. Stage `group-sync.env`, the supplied sync service and timer. Validate the units
   with `systemd-analyze verify` before installing/enabling them.
   Load the existing relay environment and the group-sync environment for a
   `sync_relay_group.py --check` invocation. It prints only status/member count.
   After a successful check, run the sync service once and verify the resulting
   snapshot as www-data. No patient data is sent to the Directory API.
5. Add the same `MAIL_RELAY_GROUP` and `MAIL_RELAY_GROUP_MEMBERS_FILE` to the
   existing private relay environment. Keep existing keys, SMTP and trial flags.
   The timer refreshes every minute; the backend refuses snapshots older than
   five minutes (plus upstream Google propagation time for membership changes).
   A refresh failure keeps the last snapshot only until that deadline. Empty,
   malformed, nested, mismatched and unauthorized membership lists are not published.
6. Run `scripts/relay_admin.py --env-file /etc/zahnarzt/mail-relay.env preflight`.
   Check the queue, start the timer, then restart `zahnarzt` with explicit approval.
   Check health, timer/service state and recent errors.

No DNS changes have been made for this feature. Previously observed root MX
records mixed Google and Cloudflare. Verify actual Google Group delivery and
resolve conflicting root mail routing before rollout, with explicit approval
and a DNS rollback record. Keep `reply.zahnarzt-jaghsi.de` directed to Cloudflare.

## Required live acceptance test before all-patient rollout

- Use synthetic administrative text only and an explicitly authorized test inbox.
- Submit a form inquiry and confirm two direct group members receive it.
- Inspect actual group-delivered Reply-To; it must retain the conversation token.
- Reply from each member; each reply must reach only the original patient and
  show the clinic From address and current presentation.
- Reply as patient; both current group members must receive it via the group.
- Replace one test member. After Google propagation and a successful refresh,
  the new member's reply must work and the removed member's old-token reply must
  be rejected. Group restrictions also control access to archived conversations.
- Verify nonmembers cannot use a doctor token and patient authentication remains exact.
- Check receipt in inbox/spam separately; group routing does not fix sender reputation.

After these pass, set `MAIL_RELAY_ENABLED=1`, remove the trial-only selector, and
restart with approval. This is the final rollout step, not part of code staging.

## Verification and rollback

Run the isolated test suite:
`python -m unittest tests.test_relay_group tests.test_mail_relay tests.test_mail_presentation tests.test_import_basic`

Restore the backed-up configuration and code with approval if deployment fails;
stop/disable the new timer only if it has been installed. Keep credentials,
snapshots, database and backups. Do not replay accepted messages. Conversations
created while group mode is active store the group as clinician; switching back
to direct mode will not authorize personal replies for those group conversations.
Prefer restoring/fixing group mode so all conversation history stays usable.
