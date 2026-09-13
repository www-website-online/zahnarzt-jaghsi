# Release candidate — 2026-09-12

Status: implemented and tested in isolation; NOT deployed to the running service.

Candidate: `/tmp/zahnarzt-fix-work`
Baseline rollback archive: `/tmp/zahnarzt-fix-backup-20260912T223803Z`
Verified content snapshot: `/tmp/zahnarzt-verified-backups/content-20260912T232140822936Z-bb0dafde.tar.gz`
Verified isolated restore: `/tmp/zahnarzt-restore-verified`
Browser results: `/tmp/zahnarzt-fix-tools/screenshots/results.json`

## Validation completed

- 19 behavior/security tests passed with production-compatible locked dependencies.
- Desktop 1440px and mobile 390px tested in Chromium in German and Arabic.
- Mobile navigation and gallery dialog work; no JavaScript errors, broken rendered images,
  or horizontal overflow in the checked home/admin views.
- Candidate Nginx configuration passes `nginx -t` using current shared HTTP configuration.
- Backup service/timer pass `systemd-analyze verify`.
- Snapshot restored 27 files to a new directory and verified SHA-256 for every file.
- Logo web rendition is 12,268 bytes; original 1,427,329-byte PNG is retained.

## Approved deployment window required

The existing service has one worker. Publishing requires a short interruption to prevent
concurrent legacy content writes while copying storage and switching code/templates together.
The production administration instructions require explicit approval for this service stop/start.

Concrete actions after approval:

1. Recheck `release-manifest.json` against both candidate and live files; stop if either changed.
   Save fresh timestamped snapshots of live code, content and Nginx configuration.
2. Stop ONLY `zahnarzt.service`; retain Nginx and all other services.
3. Copy all current `/tmp/zahnarzt-gallery` files to NEW `/var/lib/zahnarzt`.
   Refuse to overwrite a populated destination. Compare SHA-256 for every copied file.
   Preserve all original files and all 18 image records. Create private `backups/` directory.
   Give only the newly created data tree the service user's ownership and private modes.
4. Copy the changed candidate files into `/var/www/zahnarzt-jaghsi`, preserving unrelated files
   and existing user changes included in the baseline. Keep the existing production virtualenv:
   runtime dependency versions match the candidate's compatibility constraints.
5. Install `deploy/nginx-zahnarzt.conf` as the site's configuration; run `nginx -t`.
6. Start `zahnarzt.service`, check local `/healthz`, then safely reload Nginx.
7. Verify the home/contact/article pages, private JSON 404s, unauthenticated admin 401s,
   existing images, missing image 404 with no-store, and recent application/Nginx error logs.
8. Install the backup units, create private `/var/backups/zahnarzt`, daemon-reload,
   run one verified backup, and enable `zahnarzt-backup.timer` without restarting other services.

Immediate rollback if activation fails: restore the fresh code and site configuration snapshots,
validate Nginx, start the original app and reload Nginx. Keep the new data copy for inspection.
For later rollback, first preserve/reconcile content created after deployment; the old application
reads the legacy directory and must not silently discard newer durable-store edits.

## Remaining external inputs / limitations

- No SMTP settings or recipient were present. The mail adapter is implemented and tested with
  mocks. Until configured, visitors see working telephone and booking links rather than an
  inoperative contact form. An authorized real delivery test is still required afterward.
- Missing original gallery files have not been fabricated or deleted. Available variants and
  section illustrations prevent broken rendered links; originals require a source/backup.
- Cloudflare returned 403 to the audit environment; account rules were not available for review.
- Legal pages require verified clinic registration/contact/privacy information before publication.
- Daily backups remain on the server; off-server backup destination and retention policy are
  not configured, and no existing backups are deleted.
