# Deployment completed — 2026-09-12

Update 2026-09-13: contact SMTP is now enabled; see [SMTP_ACTIVATED.md](SMTP_ACTIVATED.md).
The report below records the original deployment state.

Published at 23:35:59 UTC. The application switch took approximately 0.91 seconds.
25 release files were deployed and checksum-verified. All 27 legacy content files
were copied and checksum-verified under `/var/lib/zahnarzt`; the originals remain
in `/tmp/zahnarzt-gallery`. Existing production Python dependencies were retained.

## Verification

- `zahnarzt.service` and Nginx are active; health endpoint returns `200` / `ok`.
- German and Arabic pages and all seven rendered homepage image URLs return 200.
- Arabic canonical links and RTL markup are correct; HTML responses have nonce CSP.
- Unauthenticated admin pages return 401; JSON data URLs and API docs return 404.
- Missing optimized images return 404 with `Cache-Control: no-store` and nosniff.
- Nginx syntax is valid; checked post-deploy application and relevant Nginx logs show no errors.
- Public `https://zahnarzt-jaghsi.de/` returned 200 in Chromium with the clinic page title.
  Python's automated request received a Cloudflare 403; this was not reproduced in the browser.
- `zahnarzt-backup.timer` is enabled and active, scheduled daily at 03:15 UTC plus up to
  15 minutes randomized delay. First run succeeded; all 27 files were verified and restored
  into `/tmp/zahnarzt-production-restore-20260912` for comparison.

## Backup locations

Deployment rollback files: `/var/backups/zahnarzt-deploy-20260912T233559Z`
Daily verified content archives: `/var/backups/zahnarzt`
First content archive: `content-20260912T233932536245Z-6c707f5b.tar.gz`
Checksums, original ownership/modes and the deployment result are recorded in the deployment
backup directory. No previous backups or legacy content were deleted.

## Rollback procedure

Requires an approved maintenance window. Before reverting, compare current durable content
with `content-checksums.json` in the deployment backup. If it changed after deployment,
first snapshot and reconcile the new content into the legacy store: the old app reads `/tmp`.
Do not revert code while silently discarding newer article/gallery changes.

If no newer content requires reconciliation and the legacy copy is intact, the code/config
rollback commands are:

```sh
systemctl stop zahnarzt
tar -xzf /var/backups/zahnarzt-deploy-20260912T233559Z/project.tar.gz -C /var/www/zahnarzt-jaghsi
cp /var/backups/zahnarzt-deploy-20260912T233559Z/nginx-zahnarzt.conf /etc/nginx/sites-available/zahnarzt
nginx -t
systemctl start zahnarzt
systemctl reload nginx
```

Only reload Nginx if its syntax test passes. Check service status, page responses and logs
again. Retain the durable copy and backup archives. The new backup timer backs up the durable
store; a rollback must also reassess its data path to avoid backing up stale content.

## Remaining configuration

SMTP recipient/provider settings are still needed to enable real contact form delivery.
Until then the contact page presents telephone and Doctolib links. The adapter is tested
with mocked SMTP, but no real clinic email has been sent.
Missing historic image originals were not fabricated: rendering uses available variants or
section illustrations, retaining original metadata. Off-server backups and legal page content
still require the clinic's destination and verified information.
