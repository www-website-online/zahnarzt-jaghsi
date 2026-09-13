"""Regression for Google Directory omitting account status on external members."""
import unittest
from unittest.mock import Mock
from scripts.sync_relay_group import fetch_members


class ExternalMemberTests(unittest.TestCase):
    def session(self, members):
        def get(url, **kwargs):
            if url.endswith('/members'):
                value={'members':members}
            else:
                from urllib.parse import unquote
                email=unquote(url.rsplit('/',1)[-1])
                value=next((dict(m,status='ACTIVE') for m in members if m['email']==email), {})
            return Mock(status_code=200,json=Mock(return_value=value))
        return Mock(get=Mock(side_effect=get))

    def member(self, email, **fields):
        return dict(type='USER', role='MEMBER', email=email, **fields)

    def test_external_member_without_status_is_included(self):
        session=self.session([self.member('admin@example.org',status='ACTIVE'),self.member('doctor@gmail.com')])
        self.assertEqual(fetch_members(session,'info@example.org'),{'admin@example.org','doctor@gmail.com'})

    def test_explicit_inactive_or_malformed_status_is_excluded(self):
        rows=[self.member('doctor@gmail.com')]
        rows.extend(self.member('excluded'+str(i)+'@example.org',status=s) for i,s in enumerate(['SUSPENDED','ARCHIVED','UNKNOWN','',None]))
        self.assertEqual(fetch_members(self.session(rows),'info@example.org'),{'doctor@gmail.com'})

    def test_removed_external_member_disappears_on_next_read(self):
        rows=[self.member('admin@example.org',status='ACTIVE'),self.member('doctor@gmail.com')]
        session=self.session(rows)
        self.assertIn('doctor@gmail.com',fetch_members(session,'info@example.org'))
        rows.pop()
        self.assertNotIn('doctor@gmail.com',fetch_members(session,'info@example.org'))
