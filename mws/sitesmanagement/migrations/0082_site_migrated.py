# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-04-24 15:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sitesmanagement', '0081_auto_20190204_0911'),
    ]

    operations = [
        migrations.AddField(
            model_name='site',
            name='migrated',
            field=models.BooleanField(default=False),
        ),
    ]
