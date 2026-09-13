# Google Group integration — trial active

Activated: 2026-09-13T17:45:39.642062+00:00
Group: info@zahnarzt-jaghsi.de
Delegated Workspace administrator: tamer@tameronline.com
Project: website-mail-platform; service account: jaghsi-group-reader.

Google Directory membership read succeeded for two direct USER members.
Both subscriptions were verified as ALL_MAIL. The group sync timer runs every
minute and publishes a signed membership snapshot readable by the website.
If members.list omits status, the sync checks members.get for the same user;
only a verified ACTIVE user is authorized. Missing/denied/mismatched detail fails closed.
Reference: https://developers.google.com/workspace/admin/directory/reference/rest/v1/members

Website restarted and verified running with group configuration. Public/local
health OK and no recent application errors. 67 isolated tests passed.
The existing trial remains tamerfaour@gmail.com; MAIL_RELAY_ENABLED remains 0.
All other new form submissions still use ordinary direct Reply-To delivery.
Existing relay conversations use group membership authorization after this activation.
No live test email was sent as part of this activation.

Pending: submit a new trial inquiry; verify group delivery preserves token Reply-To;
reply as the doctor and verify clinic From at the patient; reply back as patient.
Only after successful live verification enable the all-patient switch and verify health.
Old ordinary messages keep their old direct Reply-To and cannot be updated retroactively.

Private configuration/code backups: /etc/zahnarzt/backups/group-activation-20260913T172521Z
Configuration rollback: restore mail-relay-before-group.env to
/etc/zahnarzt/mail-relay.env (root 0600), then restart zahnarzt with approval.
If group-mode conversations have been created, prefer repairing group mode because
those conversations store the group destination. Do not replay or rewrite database data.
The membership timer may remain running during rollback; it cannot send mail.
