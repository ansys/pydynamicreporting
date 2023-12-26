# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0002_auto_20160812_1428'),
    ]

    operations = [
        migrations.AddField(
            model_name='template',
            name='children_order',
            field=models.CharField(default='', max_length=1024, verbose_name='children order'),
        ),
    ]
