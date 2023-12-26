# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('guid', models.UUIDField(serialize=False, verbose_name='uid', primary_key=True)),
                ('tags', models.CharField(max_length=256, verbose_name='userdata')),
                ('filename', models.CharField(max_length=256, verbose_name='dataset filename')),
                ('dirname', models.CharField(max_length=256, verbose_name='dataset directory name')),
                ('format', models.CharField(max_length=50, verbose_name='dataset format')),
                ('numparts', models.IntegerField(default=0, verbose_name='number of parts')),
                ('numelements', models.IntegerField(default=0, verbose_name='number of elements')),
            ],
        ),
        migrations.CreateModel(
            name='Item',
            fields=[
                ('guid', models.UUIDField(serialize=False, verbose_name='uid', primary_key=True)),
                ('tags', models.CharField(max_length=256, verbose_name='userdata')),
                ('sequence', models.IntegerField(default=0, verbose_name='index number for a set of items')),
                ('date', models.DateTimeField(verbose_name='timestamp')),
                ('source', models.CharField(max_length=80, verbose_name='name of the source')),
                ('name', models.CharField(max_length=80, verbose_name='item name')),
                ('type', models.CharField(max_length=16, verbose_name='item type')),
                ('payloaddata', models.BinaryField(verbose_name='raw payload data')),
                ('payloadfile', models.FileField(upload_to='', verbose_name='uploaded payload data file')),
                ('dataset', models.ForeignKey(verbose_name='item dataset', to='data.Dataset',
                                              on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Session',
            fields=[
                ('guid', models.UUIDField(serialize=False, verbose_name='uid', primary_key=True)),
                ('tags', models.CharField(max_length=256, verbose_name='userdata')),
                ('date', models.DateTimeField(verbose_name='timestamp')),
                ('hostname', models.CharField(max_length=50, verbose_name='host machine name')),
                ('platform', models.CharField(max_length=50, verbose_name='system architecture')),
                ('application', models.CharField(max_length=40, verbose_name='capture application')),
                ('version', models.CharField(max_length=20, verbose_name='application version')),
            ],
        ),
        migrations.AddField(
            model_name='item',
            name='session',
            field=models.ForeignKey(verbose_name='item session', to='data.Session', on_delete=models.CASCADE),
        ),
    ]
