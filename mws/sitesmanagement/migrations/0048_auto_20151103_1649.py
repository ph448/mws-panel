# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sitesmanagement', '0047_auto_20151021_1137'),
    ]

    operations = [
        migrations.AlterField(
            model_name='service',
            name='status',
            field=models.CharField(max_length=50, choices=[(b'requested', b'Requested'), (b'accepted', b'Accepted'),
                                                           (b'denied', b'Denied'), (b'installing', b'Installing OS'),
                                                           (b'postinstall', b'Post Installing OS'),
                                                           (b'ansible', b'Running Ansible'),
                                                           (b'ansible_queued', b'Ansible queued'),
                                                           (b'ready', b'Ready')]),
            preserve_default=True,
        ),
    ]
