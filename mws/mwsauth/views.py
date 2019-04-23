import subprocess
from tempfile import NamedTemporaryFile
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.urlresolvers import reverse
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from ucamlookup import validate_crsid_list, validate_groupid_list
from apimws.ansible import launch_ansible_site, launch_ansible_by_user
from mwsauth.models import MWSUser
from mwsauth.utils import privileges_check, remove_supporter
from sitesmanagement.views.sites import warning_messages


@login_required
def auth_change(request, site_id):
    site = privileges_check(site_id, request.user)

    if site is None:
        return HttpResponseForbidden()

    if not site.production_service or site.production_service.virtual_machines.count() == 0 \
            or site.production_service.is_busy:
        return redirect(site)

    if request.method == 'POST':
        authuserlist = validate_crsid_list(request.POST.getlist('users_crsids'))
        sshuserlist = validate_crsid_list(request.POST.getlist('sshusers_crsids'))
        authgrouplist = validate_groupid_list(request.POST.getlist('groupids'))
        sshauthgrouplist = validate_groupid_list(request.POST.getlist('sshgroupids'))
        site.users.clear()
        site.users.add(*authuserlist)
        site.ssh_users.clear()
        site.ssh_users.add(*sshuserlist)
        site.groups.clear()
        site.groups.add(*authgrouplist)
        site.ssh_groups.clear()
        site.ssh_groups.add(*sshauthgrouplist)
        launch_ansible_site(site)  # to add or delete users from the ssh/login auth list of the server
        return redirect(site)

    breadcrumbs = {
        0: dict(name='Managed Web Server: ' + str(site.name), url=site.get_absolute_url()),
        1: dict(name='Authorisation', url=reverse(auth_change, kwargs={'site_id': site.id}))
    }

    return render(request, 'mws/auth.html', {
        'authorised_users': site.users.all(),
        'sshuserlist': site.ssh_users.all(),
        'authorised_groups': site.groups.all(),
        'sshusers_groups': site.ssh_groups.all(),
        'breadcrumbs': breadcrumbs,
        'sidebar_messages': warning_messages(site),
        'site': site
    })


@login_required
def force_update(request, site_id):
    site = privileges_check(site_id, request.user)

    if site is None:
        return HttpResponseForbidden()

    if request.method == 'POST':
        launch_ansible_site(site)  # to refresh lookup lists
        # TODO add message to the user

    return redirect(site)


@login_required
def user_panel(request):
    breadcrumbs = {
        0: dict(name='User panel', url=reverse(user_panel))
    }
    error_message = None

    if request.method == 'POST':
        if 'ssh_public_key' in request.FILES:
            try:
                ssh_public_key = request.FILES['ssh_public_key'].file.read()
                ssh_public_key_temp_file = NamedTemporaryFile()
                ssh_public_key_temp_file.write(ssh_public_key)
                ssh_public_key_temp_file.flush()
                subprocess.check_output(["ssh-keygen", "-lf", ssh_public_key_temp_file.name])
                ssh_public_key_temp_file.close()
                mws_user = MWSUser.objects.get(user=request.user)
                mws_user.ssh_public_key = ssh_public_key
                mws_user.save()
                launch_ansible_by_user(request.user)
            except subprocess.CalledProcessError:
                error_message = "The key file is invalid"
        else:
            error_message = "SSH key not present"

    mws_user = MWSUser.objects.get(user=request.user)

    return render(request, 'user/panel.html', {
        'breadcrumbs': breadcrumbs,
        'ssh_public_key': mws_user.ssh_public_key,
        'error_message': error_message
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_supporter(request, site_id):
    site = privileges_check(site_id, request.user)

    if site is None:
        return HttpResponseForbidden()

    if request.method == 'POST':
        site.supporters.add(request.user)
        launch_ansible_site(site)
        remove_supporter.apply_async(args=(site.id, request.user.username),
                                     countdown=3600)  # Remove supporter after 1 hour

    return redirect(site)
