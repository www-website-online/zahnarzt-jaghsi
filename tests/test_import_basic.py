"""Behavior tests: all content and mail are isolated from production."""
import atexit
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import unittest
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory(prefix='zahnarzt-tests-')
atexit.register(TEMP.cleanup)
os.environ['ZAHNARZT_DATA_DIR'] = TEMP.name
os.environ['ADMIN_UPLOAD_PASSWORD'] = secrets.token_hex(32)
os.environ['SITE_URL'] = 'https://testserver'
for key in ('SMTP_HOST', 'SMTP_FROM', 'CONTACT_TO'):
    os.environ.pop(key, None)

from fastapi.testclient import TestClient
from PIL import Image
from backend.app import main, storage, security, contact


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        storage.initialize()
        storage.MANIFEST_PATH.write_text('{}')
        storage.ARTICLES_PATH.write_text('[]')
        security.limiter.rows.clear()
        self.client = TestClient(main.app, base_url='https://testserver')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.auth = ('admin', os.environ['ADMIN_UPLOAD_PASSWORD'])
        self.client.get('/admin/articles', auth=self.auth)
        self.token = self.client.cookies.get(security.COOKIE)

    def post(self, path, data=None, **kwargs):
        return self.client.post(path, data={'csrf_token': self.token, **(data or {})}, auth=self.auth, **kwargs)

    def article(self, **kwargs):
        return self.post('/admin/articles', {'slug': 'test-article', 'title_de': 'Test', 'content_de': 'Example content', 'status': 'published', **kwargs})

    def image_bytes(self):
        data = BytesIO()
        Image.new('RGB', (480, 320), 'green').save(data, format='PNG')
        return data.getvalue()

    def test_public_pages_languages_and_health(self):
        for path in ('/', '/leistungen', '/ueber-uns', '/kontakt', '/articles'):
            for lang in ('de', 'ar'):
                result = self.client.get(path, params={'lang': lang})
                self.assertEqual(result.status_code, 200)
                self.assertIn(f'lang="{lang}"', result.text)
                self.assertIn(f'href="https://testserver{path}?lang={lang}"', result.text)
        self.assertEqual(self.client.get('/healthz').json(), {'status': 'ok'})

    def test_private_data_and_api_docs_are_not_public(self):
        for path in ('/uploads/manifest.json', '/uploads/articles.json', '/uploads/backups/x.json', '/openapi.json', '/docs'):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get('/admin/articles').status_code, 401)
        with patch.object(main, 'ADMIN_PASSWORD', ''):
            self.assertEqual(self.client.get('/admin/articles', auth=self.auth).status_code, 503)

    def test_csrf_is_required_and_cross_origin_rejected(self):
        result = self.client.post('/admin/articles', data={'title_de': 'Bad'}, auth=self.auth)
        self.assertEqual(result.status_code, 403)
        result = self.post('/admin/articles', {'title_de': 'Bad'}, headers={'Origin': 'https://evil.example'})
        self.assertEqual(result.status_code, 403)
        self.assertEqual(storage.read_json(storage.ARTICLES_PATH, []), [])
        self.assertEqual(self.article().status_code, 200)

    def test_admin_failed_attempts_are_throttled(self):
        for _ in range(5):
            self.assertEqual(self.client.get('/admin/articles', auth=('admin', 'invalid')).status_code, 401)
        self.assertEqual(self.client.get('/admin/articles', auth=('admin', 'invalid')).status_code, 429)

    def test_article_text_is_escaped_and_csp_has_nonce(self):
        content = '<script>alert(1)</script>\n<b>text</b>'
        self.assertEqual(self.article(content_de=content).status_code, 200)
        result = self.client.get('/articles/test-article')
        self.assertNotIn(content, result.text)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', result.text)
        policy = result.headers['content-security-policy']
        self.assertNotIn("script-src 'self' 'unsafe-inline'", policy)
        nonce = re.search(r"nonce-([^']+)", policy).group(1)
        self.assertIn(f'nonce="{nonce}"', result.text)

    def test_draft_is_not_public_or_in_sitemap(self):
        self.article(status='draft')
        self.assertEqual(self.client.get('/articles/test-article').status_code, 404)
        self.assertNotIn('/articles/test-article', self.client.get('/sitemap.xml').text)

    def test_duplicate_slug_does_not_overwrite_and_edits_check_revision(self):
        self.article()
        original = main.get_article('test-article')
        self.assertEqual(self.article(title_de='Overwrite').status_code, 409)
        self.assertEqual(main.get_article('test-article')['title_de'], 'Test')
        self.assertEqual(self.article(original_slug='test-article', revision=original['revision'], title_de='Updated').status_code, 200)
        self.assertEqual(self.article(original_slug='test-article', revision=original['revision'], title_de='Stale').status_code, 409)
        current = main.get_article('test-article')
        self.assertEqual(self.article(slug='changed-link', original_slug='test-article', revision=current['revision']).status_code, 409)
        self.assertEqual(len(main.load_articles()), 1)

    def test_publication_requires_content_and_translation_is_complete(self):
        self.assertEqual(self.article(content_de='').status_code, 409)
        self.assertEqual(self.article(title_ar='عنوان').status_code, 409)
        self.assertEqual(self.article().status_code, 200)
        html = self.client.get('/articles/test-article?lang=ar').text
        self.assertIn('Example content', html)
        self.assertIn('هذا المقال متاح', html)
        self.assertIn('class="article-body" lang="de" dir="ltr"', html)

    def test_contact_without_configuration_shows_phone_and_never_success(self):
        result = self.client.get('/kontakt')
        self.assertNotIn('name="message"', result.text)
        self.assertIn('href="tel:', result.text)
        result = self.post('/kontakt', {'name': 'Test', 'email': 'test@example.com', 'message': 'Hello'})
        self.assertEqual(result.status_code, 503)

    def test_contact_validation_and_delivery_results(self):
        data = {'name': 'Test', 'email': 'test@example.com', 'message': 'Hello'}
        with patch.object(contact, 'configured', return_value=True), patch.object(contact, 'deliver', return_value=False) as deliver:
            self.assertEqual(self.post('/kontakt', {**data, 'email': 'invalid'}).status_code, 422)
            deliver.assert_not_called()
            self.assertEqual(self.post('/kontakt', data).status_code, 502)
            deliver.return_value = True
            result = self.post('/kontakt', data)
            self.assertEqual(result.status_code, 200)
            self.assertIn('Mailserver', result.text)
            self.assertEqual(deliver.call_count, 2)

    def test_contact_smtp_acceptance_refusal_and_tls(self):
        environment = {'SMTP_HOST': 'smtp.example.com', 'SMTP_FROM': 'site@example.com', 'CONTACT_TO': 'clinic@example.com', 'SMTP_SECURITY': 'starttls'}
        with patch.dict(os.environ, environment), patch('backend.app.contact.smtplib.SMTP') as smtp:
            connection = smtp.return_value.__enter__.return_value
            connection.send_message.return_value = {}
            self.assertTrue(contact.deliver('Name', 'patient@example.com', 'Test message'))
            connection.starttls.assert_called_once()
            mail = connection.send_message.call_args.args[0]
            self.assertEqual(mail['Reply-To'], 'patient@example.com')
            self.assertEqual(mail['To'], 'clinic@example.com')
            connection.send_message.return_value = {'clinic@example.com': (550, b'refused')}
            self.assertFalse(contact.deliver('Name', 'patient@example.com', 'Test message'))

    def test_image_upload_names_unique_and_invalid_section_has_no_writes(self):
        image = self.image_bytes()
        for _ in range(2):
            response = self.post('/admin/upload-images', {'section': 'reception'}, files={'images': ('same.png', image, 'image/png')})
            self.assertEqual(response.status_code, 200)
        rows = main.load_manifest()['reception']['images']
        self.assertEqual(len({row['full_url'] for row in rows}), 2)
        for row in rows:
            self.assertEqual(self.client.get(row['full_url']).status_code, 200)
        before = len(list(storage.OPTIMIZED_DIR.iterdir()))
        self.post('/admin/upload-images', {'section': '../invalid'}, files={'images': ('x.png', image, 'image/png')})
        self.assertEqual(before, len(list(storage.OPTIMIZED_DIR.iterdir())))
        self.assertNotIn('../invalid', main.load_manifest())

    def test_missing_gallery_files_do_not_produce_broken_public_links(self):
        storage.MANIFEST_PATH.write_text(json.dumps({'reception': {'main_image_id': 'missing', 'images': [{'id': 'missing', 'full_url': '/uploads/optimized/missing.webp', 'thumb_url': '/uploads/optimized/missing.webp', 'srcset': '/uploads/optimized/missing.webp 800w'}]}}))
        html = self.client.get('/').text
        self.assertNotIn('/uploads/optimized/missing.webp', html)
        self.assertIn('/static/gallery/praxis-empfang.svg', html)
        self.assertEqual(len(main.load_manifest()['reception']['images']), 1)

    def test_corrupt_storage_fails_closed_without_overwriting(self):
        storage.ARTICLES_PATH.write_text('{broken')
        with self.assertLogs('backend.app.storage', level='ERROR'):
            self.assertEqual(self.client.get('/articles').status_code, 503)
            self.assertEqual(self.article().status_code, 503)
        self.assertEqual(storage.ARTICLES_PATH.read_text(), '{broken')

    def test_snapshot_restores_previous_valid_content(self):
        self.article()
        original = main.get_article('test-article')
        self.article(original_slug='test-article', revision=original['revision'], title_de='Changed')
        snapshots = sorted((storage.DATA_DIR / 'backups').glob('articles-*.json'))
        previous = json.loads(snapshots[-1].read_text())
        self.assertEqual(previous[0]['title_de'], 'Test')
        restored = Path(TEMP.name) / 'restore-check.json'
        restored.write_bytes(snapshots[-1].read_bytes())
        self.assertEqual(json.loads(restored.read_text()), previous)

    def test_concurrent_content_updates_are_not_lost(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda i: self.article(slug=f'article-{i}').status_code, range(8)))
        self.assertEqual(results, [200] * 8)
        self.assertEqual(len(main.load_articles()), 8)

    def test_deleted_image_is_archived_and_no_longer_public(self):
        self.post('/admin/upload-images', {'section': 'reception'}, files={'images': ('delete-me.png', self.image_bytes(), 'image/png')})
        row = main.load_manifest()['reception']['images'][0]
        original = self.client.get(row['full_url']).content
        result = self.post('/admin/upload-images/delete-image', {'section': 'reception', 'image_id': row['id']})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.get(row['full_url']).status_code, 404)
        archived = list((storage.DATA_DIR / 'deleted-images').rglob(Path(row['full_url']).name))
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0].read_bytes(), original)
        self.assertNotIn('reception', main.load_manifest())

    def test_chunked_request_size_limit(self):
        def chunks():
            for _ in range(33):
                yield b'x' * 1024 * 1024
        result = self.client.post('/kontakt', content=chunks(), headers={'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(result.status_code, 413)

    def test_request_size_limit(self):
        result = self.client.post('/kontakt', content=b'x', headers={'Content-Length': str(security.MAX_REQUEST_BYTES + 1)})
        self.assertEqual(result.status_code, 413)


if __name__ == '__main__':
    unittest.main()
