"""Directory list responses can omit external user status; get must verify it."""
import unittest
from unittest.mock import Mock
from scripts.sync_relay_group import fetch_members
from backend.app.relay_group import MembershipUnavailable


class MemberDetailsTests(unittest.TestCase):
    def user(self, email='doctor@gmail.com', **fields):
        return dict(type='USER', role='MEMBER', email=email, **fields)

    def session(self, detail, status=200):
        return Mock(get=Mock(side_effect=[
            Mock(status_code=200,json=Mock(return_value={'members':[self.user()]})),
            Mock(status_code=status,json=Mock(return_value=detail))]))

    def test_external_status_verified_by_get(self):
        session=self.session(self.user(status='ACTIVE'))
        self.assertEqual(fetch_members(session,'info@example.org'),{'doctor@gmail.com'})
        self.assertTrue(session.get.call_args.args[0].endswith('/members/doctor%40gmail.com'))
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])

    def test_missing_mismatched_inactive_or_denied_detail_never_authorizes(self):
        for detail,status in [(self.user(),200),(self.user('other@gmail.com',status='ACTIVE'),200),
                              (self.user(status='SUSPENDED'),200),(self.user(status='ACTIVE'),403),
                              (self.user(status='ACTIVE'),404)]:
            with self.subTest(detail=detail,status=status), self.assertRaises(MembershipUnavailable):
                fetch_members(self.session(detail,status),'info@example.org')
