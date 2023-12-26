# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0002_auto_20160609_0913'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='dirname',
            field=models.CharField(max_length=256, verbose_name='dataset directory name', blank=True),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='tags',
            field=models.CharField(max_length=256, verbose_name='userdata', blank=True),
        ),
        migrations.AlterField(
            model_name='item',
            name='name',
            field=models.CharField(max_length=80, verbose_name='item name', blank=True),
        ),
        migrations.AlterField(
            model_name='item',
            name='payloaddata',
            field=models.TextField(verbose_name='raw payload data'),
        ),
        migrations.AlterField(
            model_name='item',
            name='source',
            field=models.CharField(max_length=80, verbose_name='name of the source', blank=True),
        ),
        migrations.AlterField(
            model_name='item',
            name='tags',
            field=models.CharField(max_length=256, verbose_name='userdata', blank=True),
        ),
        migrations.AlterField(
            model_name='session',
            name='hostname',
            field=models.CharField(max_length=50, verbose_name='host machine name', blank=True),
        ),
        migrations.AlterField(
            model_name='session',
            name='platform',
            field=models.CharField(max_length=50, verbose_name='system architecture', blank=True),
        ),
        migrations.AlterField(
            model_name='session',
            name='tags',
            field=models.CharField(max_length=256, verbose_name='userdata', blank=True),
        ),
    ]
