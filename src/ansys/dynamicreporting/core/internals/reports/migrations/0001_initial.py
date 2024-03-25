# -*- coding: utf-8 -*-

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Template',
            fields=[
                ('guid', models.UUIDField(serialize=False, verbose_name='uid', primary_key=True)),
                ('tags', models.CharField(max_length=256, verbose_name='userdata', blank=True)),
                ('date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='timestamp')),
                ('name', models.CharField(max_length=50, verbose_name='report name', blank=True)),
                ('type', models.CharField(max_length=50, verbose_name='report type', blank=True)),
                ('params', models.CharField(max_length=2048, verbose_name='parameters', blank=True)),
                ('master', models.BooleanField(default=True, verbose_name='master template')),
                ('parent', models.ForeignKey(related_name='children', blank=True, to='reports.Template', null=True,
                                             on_delete=models.CASCADE)),
            ],
        ),
    ]
