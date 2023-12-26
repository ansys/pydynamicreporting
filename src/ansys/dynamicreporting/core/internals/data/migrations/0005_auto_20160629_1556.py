# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0004_auto_20160614_1105'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='filename',
            field=models.CharField(max_length=256, verbose_name='dataset filename', blank=True),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='format',
            field=models.CharField(max_length=50, verbose_name='dataset format', blank=True),
        ),
        migrations.AlterField(
            model_name='item',
            name='type',
            field=models.CharField(default='none', max_length=16, verbose_name='item type'),
        ),
        migrations.AlterField(
            model_name='session',
            name='application',
            field=models.CharField(max_length=40, verbose_name='capture application', blank=True),
        ),
        migrations.AlterField(
            model_name='session',
            name='version',
            field=models.CharField(max_length=20, verbose_name='application version', blank=True),
        ),
    ]
