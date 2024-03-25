# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='template',
            old_name='type',
            new_name='report_type',
        ),
        migrations.AddField(
            model_name='template',
            name='item_filter',
            field=models.CharField(max_length=1024, verbose_name='filter', blank=True),
        ),
    ]
