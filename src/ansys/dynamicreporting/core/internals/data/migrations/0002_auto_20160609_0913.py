# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='height',
            field=models.IntegerField(default=0, verbose_name='height'),
        ),
        migrations.AddField(
            model_name='item',
            name='width',
            field=models.IntegerField(default=0, verbose_name='width'),
        ),
    ]
