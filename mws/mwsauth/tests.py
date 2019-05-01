from datetime import datetime
import uuid
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.test import TestCase
import mock
from ucamwebauth.tests import create_wls_response

from apimws.models import Cluster, Host
from apimws.xen import which_cluster
from mwsauth import views
from mwsauth.models import MWSUser
from ucamlookup import (
    user_in_groups,
    get_or_create_user_by_crsid, validate_crsid_list,
    get_or_create_group_by_groupid, validate_groupid_list
)
from sitesmanagement.models import Site, Suspension, VirtualMachine, NetworkConfig, Service, Vhost, ServerType
from ucamlookup.models import LookupGroup


def do_test_login(self, user="user1"):
    with self.settings(UCAMWEBAUTH_CERTS={901: """-----BEGIN CERTIFICATE-----
MIIDzTCCAzagAwIBAgIBADANBgkqhkiG9w0BAQQFADCBpjELMAkGA1UEBhMCR0Ix
EDAOBgNVBAgTB0VuZ2xhbmQxEjAQBgNVBAcTCUNhbWJyaWRnZTEgMB4GA1UEChMX
VW5pdmVyc2l0eSBvZiBDYW1icmlkZ2UxLTArBgNVBAsTJENvbXB1dGluZyBTZXJ2
aWNlIERFTU8gUmF2ZW4gU2VydmljZTEgMB4GA1UEAxMXUmF2ZW4gREVNTyBwdWJs
aWMga2V5IDEwHhcNMDUwNzI2MTMyMTIwWhcNMDUwODI1MTMyMTIwWjCBpjELMAkG
A1UEBhMCR0IxEDAOBgNVBAgTB0VuZ2xhbmQxEjAQBgNVBAcTCUNhbWJyaWRnZTEg
MB4GA1UEChMXVW5pdmVyc2l0eSBvZiBDYW1icmlkZ2UxLTArBgNVBAsTJENvbXB1
dGluZyBTZXJ2aWNlIERFTU8gUmF2ZW4gU2VydmljZTEgMB4GA1UEAxMXUmF2ZW4g
REVNTyBwdWJsaWMga2V5IDEwgZ8wDQYJKoZIhvcNAQEBBQADgY0AMIGJAoGBALhF
i9tIZvjYQQRfOzP3cy5ujR91ZntQnQehldByHlchHRmXwA1ot/e1WlHPgIjYkFRW
lSNcSDM5r7BkFu69zM66IHcF80NIopBp+3FYqi5uglEDlpzFrd+vYllzw7lBzUnp
CrwTxyO5JBaWnFMZrQkSdspXv89VQUO4V4QjXV7/AgMBAAGjggEHMIIBAzAdBgNV
HQ4EFgQUgjC6WtA4jFf54kxlidhFi8w+0HkwgdMGA1UdIwSByzCByIAUgjC6WtA4
jFf54kxlidhFi8w+0HmhgaykgakwgaYxCzAJBgNVBAYTAkdCMRAwDgYDVQQIEwdF
bmdsYW5kMRIwEAYDVQQHEwlDYW1icmlkZ2UxIDAeBgNVBAoTF1VuaXZlcnNpdHkg
b2YgQ2FtYnJpZGdlMS0wKwYDVQQLEyRDb21wdXRpbmcgU2VydmljZSBERU1PIFJh
dmVuIFNlcnZpY2UxIDAeBgNVBAMTF1JhdmVuIERFTU8gcHVibGljIGtleSAxggEA
MAwGA1UdEwQFMAMBAf8wDQYJKoZIhvcNAQEEBQADgYEAsdyB+9szctHHIHE+S2Kg
LSxbGuFG9yfPFIqaSntlYMxKKB5ba/tIAMzyAOHxdEM5hi1DXRsOok3ElWjOw9oN
6Psvk/hLUN+YfC1saaUs3oh+OTfD7I4gRTbXPgsd6JgJQ0TQtuGygJdaht9cRBHW
wOq24EIbX5LquL9w+uvnfXw=
-----END CERTIFICATE-----"""}):
        # HACK: Django >= 1.10 disabled login if is_active=False and *even if*
        # you set is_active=True on the user model, it is set *back* to False by
        # mwsauth.models.add_name_to_user if there isn't a corresponding
        # MWSUser for the user. Hence we, need to create both before login can
        # proceed.
        u, u_created = get_user_model().objects.get_or_create(username=user)
        mu = MWSUser.objects.filter(user=u).first()

        if not mu:
            # If the MWSUser did not previously exist, set the uid by some
            # super clever means to ensure different users get different uids.
            # This, by the way is a HACK within the HACK above...
            mu = MWSUser.objects.create(
                user=u, uid=MWSUser.objects.count() + 10000)

        if u_created:
            # Now, if the user was also created, set them to active in a move
            # which is now *not* undone but the pre-save hook.
            u.is_active = True
            u.save()

        self.client.get(reverse('raven_return'),
                        {'WLS-Response': create_wls_response(raven_issue=datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'),
                                                             raven_url=settings.UCAMWEBAUTH_RETURN_URL,
                                                             raven_principal=user)})
        self.assertIn('_auth_user_id', self.client.session)


class AuthTestCases(TestCase):

    def test_validate_crsid_list(self):
        with self.assertRaises(ValidationError):
            validate_crsid_list(["wrongwrongwrong"])

        users = validate_crsid_list(["amc203"])
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].username, "amc203")
        self.assertIsNotNone(users[0].id)
        self.assertFalse(users[0].has_usable_password())
        self.assertIsNot(users[0].last_name, "")
        self.assertIsNot(users[0].last_name, None)

        users = validate_crsid_list(["amc203", "jw35"])
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0].username, "amc203")
        self.assertIsNotNone(users[0].id)
        self.assertFalse(users[0].has_usable_password())
        self.assertIsNot(users[0].last_name, "")
        self.assertIsNot(users[0].last_name, None)
        self.assertEqual(users[1].username, "jw35")
        self.assertIsNotNone(users[1].id)
        self.assertFalse(users[1].has_usable_password())
        self.assertIsNot(users[1].last_name, "")
        self.assertIsNot(users[1].last_name, None)

        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username="wrongwrongwrong")

        users = validate_crsid_list([""])
        self.assertEqual(len(users), 0)

    def test_validate_groupid_list(self):
        with self.assertRaises(ValidationError):
            validate_groupid_list(["wrongwrongwrong"])

        with self.assertRaises(ValidationError):
            validate_groupid_list(["123456"])

        groups = validate_groupid_list(["101888"])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].lookup_id, "101888")
        self.assertIsNot(groups[0].name, "")
        self.assertIsNot(groups[0].name, None)

        groups = validate_groupid_list(["101888", "101923"])
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].lookup_id, "101888")
        self.assertIsNot(groups[0].name, "")
        self.assertIsNot(groups[0].name, None)
        self.assertEqual(groups[1].lookup_id, "101923")
        self.assertIsNot(groups[1].name, "")
        self.assertIsNot(groups[1].name, None)

        groups = validate_groupid_list([""])
        self.assertEqual(len(groups), 0)

    def test_get_or_create_user_or_group(self):
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username="amc203")
        user1 = get_or_create_user_by_crsid("amc203")
        user2 = User.objects.get(username="amc203")
        self.assertEqual(user1.id, user2.id)

        with self.assertRaises(LookupGroup.DoesNotExist):
            LookupGroup.objects.get(lookup_id="101888")
        group1 = get_or_create_group_by_groupid(101888)
        group2 = LookupGroup.objects.get(lookup_id="101888")
        self.assertEqual(group1.lookup_id, group2.lookup_id)

    def test_user_in_groups(self):
        amc203 = get_or_create_user_by_crsid("amc203")
        information_systems_group = get_or_create_group_by_groupid(101888)
        self.assertTrue(user_in_groups(amc203, [information_systems_group]))
        finance_group = get_or_create_group_by_groupid(101923)
        self.assertFalse(user_in_groups(amc203, [finance_group]))

    def test_auth_change(self):
        response = self.client.get(reverse(views.auth_change, kwargs={'site_id': 1}))
        self.assertEqual(response.status_code, 302)  # Not logged in, redirected to login
        self.assertTrue(response.url.endswith(
            '%s?next=%s' % (reverse('raven_login'), reverse(views.auth_change, kwargs={'site_id': 1}))))

        do_test_login(self, user="amc203")
        amc203_user = User.objects.get(username="amc203")

        response = self.client.get(reverse(views.auth_change, kwargs={'site_id': 1}))
        self.assertEqual(response.status_code, 404)  # Site does not exists

        cluster = Cluster.objects.create(name="mws-test-1")
        Host.objects.create(hostname="mws-test-1.dev.mws3.cam.ac.uk", cluster=cluster)

        NetworkConfig.objects.create(IPv4='131.111.58.253', IPv6='2001:630:212:8::8c:253', type='ipvxpub',
                                     name="mws-66424.mws3.csx.cam.ac.uk")
        NetworkConfig.objects.create(IPv4='172.28.18.253', type='ipv4priv',
                                     name='mws-46250.mws3.csx.private.cam.ac.uk')
        NetworkConfig.objects.create(IPv6='2001:630:212:8::8c:ff4', name='mws-client1', type='ipv6')
        NetworkConfig.objects.create(IPv6='2001:630:212:8::8c:ff3', name='mws-client2', type='ipv6')

        site_without_auth_users = Site.objects.create(name="test_site1", start_date=datetime.today(),
                                                      type=ServerType.objects.get(id=1))
        service_a = Service.objects.create(type='production', network_configuration=NetworkConfig.
                                           get_free_prod_service_config(), site=site_without_auth_users, status='ready')
        VirtualMachine.objects.create(token=uuid.uuid4(), service=service_a,
                                      network_configuration=NetworkConfig.get_free_host_config(),
                                      cluster=which_cluster())
        Vhost.objects.create(name="default", service=service_a)

        response = self.client.get(reverse(views.auth_change, kwargs={'site_id': site_without_auth_users.id}))
        self.assertEqual(response.status_code, 403)  # User is not authorised

        site_without_auth_users.users.add(amc203_user)
        information_systems_group = get_or_create_group_by_groupid(101888)
        site_with_auth_users = site_without_auth_users

        response = self.client.get(reverse(views.auth_change, kwargs={'site_id': site_with_auth_users.id}))
        self.assertContains(
            response, '<option selected=selected value="amc203">', status_code=200
        )  # User is authorised


        with mock.patch("apimws.vm.change_vm_power_state") as mock_change_vm_power_state:
            mock_change_vm_power_state.return_value = True
            mock_change_vm_power_state.delay.return_value = True
            site_with_auth_users.disable()
        suspension = Suspension.objects.create(reason="test_suspension", site=site_with_auth_users,
                                               start_date=datetime.today())
        response = self.client.get(reverse(views.auth_change, kwargs={'site_id': site_with_auth_users.id}))
        self.assertEqual(response.status_code, 403)  # Site is suspended
        suspension.delete()

        with mock.patch("apimws.vm.change_vm_power_state") as mock_change_vm_power_state:
            mock_change_vm_power_state.return_value = True
            mock_change_vm_power_state.delay.return_value = True
            with mock.patch("apimws.ansible_impl.subprocess") as mock_subprocess:
                mock_subprocess.check_output.return_value.returncode = 0
                site_with_auth_users.enable()

        self.assertEqual(len(site_with_auth_users.users.all()), 1)
        self.assertEqual(site_with_auth_users.users.first(), amc203_user)
        self.assertEqual(len(site_with_auth_users.groups.all()), 0)
        with mock.patch("apimws.ansible_impl.subprocess") as mock_subprocess:
            mock_subprocess.check_output.return_value.returncode = 0
            response = self.client.post(reverse(views.auth_change, kwargs={'site_id': site_with_auth_users.id}), {
                'users_crsids': "amc203",
                'groupids': "101888"
                # we authorise amc203 user and 101888 group
            })
            mock_subprocess.check_output.assert_called_with([
                "userv", "mws-admin", "mws_ansible_host",
                site_with_auth_users.production_service.virtual_machines.first().network_configuration.name
            ], stderr=mock_subprocess.STDOUT)
        self.assertRedirects(response, expected_url=site_with_auth_users.get_absolute_url())
        self.assertEqual(len(site_with_auth_users.users.all()), 1)
        self.assertEqual(site_with_auth_users.users.first(), amc203_user)
        self.assertEqual(len(site_with_auth_users.groups.all()), 1)
        self.assertEqual(site_with_auth_users.groups.first(), information_systems_group)

        with mock.patch("apimws.ansible_impl.subprocess") as mock_subprocess:
            mock_subprocess.check_output.return_value.returncode = 0
            # remove all users and groups authorised, we do not send any crsids or groupids
            response = self.client.post(reverse(views.auth_change, kwargs={'site_id': site_with_auth_users.id}), {})
            mock_subprocess.check_output.assert_called_with([
                "userv", "mws-admin", "mws_ansible_host",
                site_with_auth_users.production_service.virtual_machines.first().network_configuration.name
            ], stderr=mock_subprocess.STDOUT)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(site_with_auth_users.get_absolute_url()))
        self.assertEqual(self.client.get(response.url).status_code, 403)  # User is no longer authorised
        self.assertEqual(len(site_with_auth_users.users.all()), 0)
        self.assertEqual(len(site_with_auth_users.groups.all()), 0)

    def test_group_auth_change(self):
        do_test_login(self, user="amc203")
        amc203_user = User.objects.get(username="amc203")

        cluster = Cluster.objects.create(name="mws-test-1")
        Host.objects.create(hostname="mws-test-1.dev.mws3.cam.ac.uk", cluster=cluster)

        NetworkConfig.objects.create(IPv4='131.111.58.253', IPv6='2001:630:212:8::8c:253', type='ipvxpub',
                                     name="mws-66424.mws3.csx.cam.ac.uk")
        NetworkConfig.objects.create(IPv4='172.28.18.253', type='ipv4priv',
                                     name='mws-46250.mws3.csx.private.cam.ac.uk')
        NetworkConfig.objects.create(IPv6='2001:630:212:8::8c:ff4', name='mws-client1', type='ipv6')
        NetworkConfig.objects.create(IPv6='2001:630:212:8::8c:ff3', name='mws-client2', type='ipv6')

        site_with_auth_groups = Site.objects.create(name="test_site2", start_date=datetime.today(),
                                                    type=ServerType.objects.get(id=1))
        service_a = Service.objects.create(type='production', network_configuration=NetworkConfig.
                                           get_free_prod_service_config(), site=site_with_auth_groups,
                                           status='ready')
        VirtualMachine.objects.create(token=uuid.uuid4(), service=service_a,
                                      network_configuration=NetworkConfig.get_free_host_config(),
                                      cluster=which_cluster())
        Vhost.objects.create(name="default", service=service_a)
        information_systems_group = get_or_create_group_by_groupid(101888)
        site_with_auth_groups.groups.add(information_systems_group)

        response = self.client.get(reverse(views.auth_change, kwargs={'site_id': site_with_auth_groups.id}))
        self.assertContains(response, "101888", status_code=200)  # User is in an authorised group
        self.assertNotContains(response, 'crsid: "amc203"', status_code=200)

        self.assertEqual(len(site_with_auth_groups.users.all()), 0)
        self.assertEqual(len(site_with_auth_groups.groups.all()), 1)
        self.assertEqual(site_with_auth_groups.groups.first(), information_systems_group)
        with mock.patch("apimws.ansible_impl.subprocess") as mock_subprocess:
            mock_subprocess.check_output.return_value.returncode = 0
            response = self.client.post(reverse(views.auth_change, kwargs={'site_id': site_with_auth_groups.id}), {
                'users_crsids': "amc203",
                'groupids': "101888"
                # we authorise amc203 user and 101888 group
            })
            mock_subprocess.check_output.assert_called_with([
                "userv", "mws-admin", "mws_ansible_host",
                site_with_auth_groups.production_service.virtual_machines.first().network_configuration.name
            ], stderr=mock_subprocess.STDOUT)
        self.assertRedirects(response, expected_url=site_with_auth_groups.get_absolute_url())
        self.assertEqual(len(site_with_auth_groups.users.all()), 1)
        self.assertEqual(site_with_auth_groups.users.first(), amc203_user)
        self.assertEqual(len(site_with_auth_groups.groups.all()), 1)
        self.assertEqual(site_with_auth_groups.groups.first(), information_systems_group)

        with mock.patch("apimws.ansible_impl.subprocess") as mock_subprocess:
            mock_subprocess.check_output.return_value.returncode = 0
            # remove all users and groups authorised, we do not send any crsids or groupids
            response = self.client.post(reverse(views.auth_change, kwargs={'site_id': site_with_auth_groups.id}), {})
            mock_subprocess.check_output.assert_called_with([
                "userv", "mws-admin", "mws_ansible_host",
                site_with_auth_groups.production_service.virtual_machines.first().network_configuration.name
            ], stderr=mock_subprocess.STDOUT)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(site_with_auth_groups.get_absolute_url()))
        self.assertEqual(self.client.get(response.url).status_code, 403)  # User is no longer authorised
        self.assertEqual(len(site_with_auth_groups.users.all()), 0)
        self.assertEqual(len(site_with_auth_groups.groups.all()), 0)

    def test_banned_users_middleware(self):
        with self.settings(MIDDLEWARE_CLASSES=settings.MIDDLEWARE_CLASSES+('mwsauth.middleware.CheckBannedUsers',)):
            do_test_login(self, user="amc203")

            # Delete the corresponding MWSUser and re-save the user
            MWSUser.objects.filter(user__username="amc203").delete()
            User.objects.get(username="amc203").save()

            response = self.client.get(reverse('listsites'))
            self.assertEqual(response.status_code, 302)  # There user was created without its corresponding mws_user
            self.assertFalse(User.objects.get(username="amc203").is_active)  # therefore is deactivated by default

            User.objects.filter(username="amc203").update(is_active=True)
            response = self.client.get(reverse('listsites'))
            self.assertEqual(response.status_code, 403)  # There is no corresponding mws_user
            self.assertTrue(User.objects.get(username="amc203").is_active)

            MWSUser.objects.create(uid="9999999", ssh_public_key="testestestestest", user_id="amc203")
            response = self.client.get(reverse('listsites'))
            self.assertEqual(response.status_code, 200)  # There is a corresponding mws_user

            User.objects.filter(username="amc203").update(is_active=False)
            response = self.client.get(reverse('listsites'))
            self.assertEqual(response.status_code, 302)  # There user is not active
