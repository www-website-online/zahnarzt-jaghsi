# Selected existing group: info@zahnarzt-jaghsi.de

The user requested all website conversations through the existing website group.
Use `info@zahnarzt-jaghsi.de`; the earlier `team@` proposal is not the selected target.
No live group configuration has been applied.

Read-only inspection found MAIL_RELAY_ENABLED=0, trial-only selection, CONTACT_TO=info@zahnarzt-jaghsi.de,
and no Google Directory credential, synchronization configuration or membership snapshot.
Enabling group mode before provisioning membership would reject new form submissions.

Follow GROUPS.md using this existing group instead of creating team@.
The missing external prerequisite is Workspace administrator authorization for
`https://www.googleapis.com/auth/admin.directory.group.member.readonly` and its
dedicated service-account credentials on the server. Never place the key in chat.
Google reference: https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority

Verify the group's Reply-To preservation and actual distribution from the website
sender (which is also the group address). Confirm clinic members receive mail;
membership API access alone does not prove delivery or subscription settings.
Then activate and test group routing before setting MAIL_RELAY_ENABLED=1 for everyone.
Existing ordinary emails have a direct patient Reply-To that cannot be changed
retroactively; use a new form inquiry for acceptance testing.

Production flags, service and database remain unchanged during preparation.
