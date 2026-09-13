"""Public-address group routing and all-patient form behavior, without live mail."""
from dataclasses import replace
import os
import unittest
from unittest.mock import Mock, patch

from backend.app import contact, mail_relay
from tests import test_relay_group as group_tests


class PublicGroupTests(unittest.TestCase):
    setUp = group_tests.GroupRelayTests.setUp
    transport = group_tests.GroupRelayTests.transport
    conversation = group_tests.GroupRelayTests.conversation
    raw = group_tests.GroupRelayTests.raw
    signed = group_tests.GroupRelayTests.signed
    refresh = group_tests.GroupRelayTests.refresh
    enable_group = group_tests.GroupRelayTests.enable_group

    def test_group_can_equal_public_sender_in_both_directions(self):
        self.enable_group()
        self.settings = replace(self.settings, group_address=self.settings.sender)
        self.refresh(('doctor@gmail.com',))
        self.settings.validate()
        self.relay = mail_relay.Relay(self.settings, clock=lambda: self.now, transport=self.transport)
        cid = self.conversation()
        self.relay.drain_one()
        recipient, initial = self.sent[-1]
        self.assertEqual(recipient, self.settings.group_address)
        self.assertEqual(initial['Reply-To'].addresses[0].addr_spec, self.relay.reply_address(cid, 'd'))
        self.relay.receive(*self.signed(cid))
        self.relay.drain_one()
        recipient, reply = self.sent[-1]
        self.assertEqual(recipient, 'patient@gmail.com')
        self.assertEqual(reply['From'].addresses[0].addr_spec, self.settings.sender)
        self.assertNotIn('doctor@gmail.com', reply.as_string())
        self.assertEqual(reply['Reply-To'].addresses[0].addr_spec, self.relay.reply_address(cid, 'p'))
        self.relay.receive(*self.signed(cid, 'p', self.raw('patient@gmail.com', 'Follow up', '<follow>')))
        self.relay.drain_one()
        self.assertEqual(self.sent[-1][0], self.settings.group_address)


class AllPatientFormTests(unittest.TestCase):
    def check_form(self, failure=None):
        from backend.app import main
        from starlette.requests import Request
        relay = Mock()
        relay.submit.side_effect = failure
        request = Request({'type': 'http', 'app': main.app, 'client': ('127.0.0.1', 1)})
        with patch.dict(os.environ, {'MAIL_RELAY_ENABLED': '1', 'MAIL_RELAY_TEST_PATIENT': 'trial@example.com'}), \
             patch.object(main.app.state, 'mail_relay', relay, create=True), \
             patch.object(main, 'base_context', return_value={'lang': 'de'}), \
             patch.object(main.limiter, 'allow', return_value=True), \
             patch.object(contact, 'configured', return_value=True), \
             patch.object(contact, 'deliver') as direct, \
             patch.object(main.templates, 'TemplateResponse') as render:
            for patient in ('first@example.com', 'second@example.org'):
                main.contact_submit(request, name='Patient', email=patient, message='Inquiry', website='')
            self.assertEqual(relay.submit.call_count, 2)
            direct.assert_not_called()
            if failure:
                self.assertEqual(render.call_args.kwargs['status_code'], 503)

    def test_all_patients_use_relay_instead_of_direct_reply_to(self):
        self.check_form()

    def test_missing_membership_does_not_fall_back_to_direct_delivery(self):
        self.check_form(mail_relay.RelayError('group_members_unavailable', 503))
