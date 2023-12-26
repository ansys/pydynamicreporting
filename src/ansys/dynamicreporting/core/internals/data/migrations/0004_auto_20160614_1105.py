# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0003_auto_20160614_1033'),
    ]

    operations = [
        migrations.AlterField(
            model_name='item',
            name='payloaddata',
            field=models.TextField(verbose_name='raw payload data', blank=True),
        ),
    ]
