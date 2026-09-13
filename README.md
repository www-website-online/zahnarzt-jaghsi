# Zahnarztpraxis

German/Arabic clinic website using FastAPI, Jinja2 and a small, private JSON content store.

## Local development and checks

Python 3.12+ and uv 0.8.22 are required. Install the locked environment with `uv sync --locked`.
Run `uv run --locked python -B -m unittest discover -s tests -v`. Tests create temporary
storage and mock mail; they never use production content or send real email.

For a local server, configure `ZAHNARZT_DATA_DIR` to a writable local directory,
`SITE_URL=http://127.0.0.1:8001`, and an `ADMIN_UPLOAD_PASSWORD` supplied securely from
the environment. Then run `uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8001`.
Admin access fails closed when no password is configured. Do not store credentials in git.

## Layout

- `backend/app/main.py`: routes, gallery processing and presentation contexts.
- `backend/app/translations.py`: German and Arabic copy.
- `backend/app/storage.py`: file locks, atomic JSON writes and private revision backups.
- `backend/app/security.py`: signed CSRF tokens, throttling and request size limits.
- `backend/app/contact.py`: SMTP delivery with TLS and redacted failure logs.
- `backend/app/templates/`, `backend/app/static/`: website templates and assets.
- `scripts/content_backup.py`: verified snapshots and isolated restore checks.
- `deploy/`: reviewed Nginx candidate and daily backup units; files are not auto-applied.

## Content and recovery

`ZAHNARZT_DATA_DIR` defaults to `/var/lib/zahnarzt`. Only `optimized/` is served publicly
under `/uploads/optimized/`. `manifest.json`, `articles.json`, `backups/` and
`deleted-images/` must remain private. The service user must be able to write the directory.
Do not place secrets or content under `backend/app/static/`.

Before changing storage, copy the legacy `/tmp/zahnarzt-gallery` to the durable directory
and verify every copied file by SHA-256. Keep the legacy directory as a rollback source.
The migration must occur during the approved deployment window to avoid concurrent edits.
Never replace existing destination content without a separate recovery decision.

Each content mutation holds a per-store process/thread-safe lock. Writes retain the previous
JSON version under `backups/`, fsync a temporary file and atomically replace the store.
Invalid JSON produces HTTP 503 rather than silently starting an empty store. Image deletion
archives files in private storage; there is no automatic irreversible cleanup.
Missing historic images are omitted from the lightbox or replaced by a section illustration;
original records are preserved. Missing originals cannot be recreated without source files.

Create a snapshot:

```sh
.venv/bin/python scripts/content_backup.py create --data-dir /var/lib/zahnarzt --output-dir /var/backups/zahnarzt
```

Verify an archive and restore it only into a NEW, isolated directory:

```sh
.venv/bin/python scripts/content_backup.py verify --archive /path/to/content-snapshot.tar.gz
.venv/bin/python scripts/content_backup.py restore-test --archive /path/to/content-snapshot.tar.gz --destination /tmp/clinic-restore-new
```

Archives contain checksums and are verified after creation. A production restore requires
an approved maintenance window and a fresh backup of the current data. Daily timer templates
are provided; installation and enablement are part of deployment. Backups are retained without
auto-deletion. Monitor free disk space and arrange a separate encrypted off-server copy.
A backup on the same server does not protect against loss of that server.

## Contact mail

Without complete SMTP settings, the contact page offers telephone/Doctolib contact and does
not show a nonfunctional message form. Required settings:

- `SMTP_HOST`, `SMTP_FROM`, `CONTACT_TO`.
- `SMTP_SECURITY`: `starttls` (default) or `ssl`; unencrypted SMTP is rejected.
- `SMTP_PORT`: defaults to 587 for STARTTLS or 465 for SSL.
- `SMTP_USER`, `SMTP_PASSWORD`: when authentication is required by the provider.

The sender is fixed by configuration; the visitor email is `Reply-To`. Validation, CSRF,
a honeypot and per-client throttling precede sending. Success means the SMTP server accepted
the message, not that the recipient read it. Bodies and SMTP response text are not logged.
A real delivery test to the approved clinic recipient remains necessary after configuring mail.

## Limits and security

Uploads allow 10 MiB per image (or a lower `MAX_UPLOAD_MB`), 8 files and 30 MiB aggregate.
Nginx and the app cap admin request bodies at 32 MiB. Decoded images are limited to 25 megapixels.
Images are re-encoded into uniquely named WebP files. Removed assets are archived privately.
Admin failures are limited to 5 per client per 5 minutes; contact requests to 5 per 10 minutes.
The in-process limiter resets on restart; Nginx provides an additional admin request limit.

Browser forms use signed, two-hour CSRF tokens and strict same-site cookies. `SITE_URL` is the
trusted origin. If using a second hostname, redirect it to the canonical hostname before form
use or add an explicitly reviewed origin policy; do not trust arbitrary Host headers.
`CSRF_SECRET` can be set separately; otherwise it derives from the configured admin password.
HTML article content is treated as plain text with preserved line breaks. Inline JavaScript
uses CSP nonces. Runtime API documentation is disabled.

## Deployment validation and rollback

The deployment candidate must pass unit tests and `nginx -t` before applying it. Back up the
current code and Nginx file, copy and checksum content into durable storage, then deploy code
and reload Nginx. Restarting the single application worker may briefly interrupt service and
requires explicit approval under the production administration rules.

Check `systemctl is-active zahnarzt nginx`, `/healthz`, German/Arabic pages, unauthenticated
admin access (401), private JSON URLs (404), and recent service/error logs. A missing optimized
image must return 404 with `Cache-Control: no-store`, not a long immutable cache lifetime.

Rollback: restore the code and Nginx snapshot from the deployment's recorded backup directory,
validate Nginx, then restart the application and reload Nginx within the approved window.
If content was edited after deployment, preserve both data directories and reconcile new
changes before returning to the legacy store. Never overwrite newer content during rollback.

Cloudflare's external response must be checked from an ordinary visitor connection; a 403
from one automated source is not proof of a general outage. Legal page content and clinic
registration details require the clinic's verified information before publication.
