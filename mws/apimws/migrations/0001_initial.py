# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sitesmanagement', '0005_site_disabled'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnsibleConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('key', models.CharField(max_length=250, db_index=True)),
                ('value', models.TextField()),
                ('site', models.ForeignKey(to='sitesmanagement.Site')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
