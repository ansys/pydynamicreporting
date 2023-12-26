# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0003_template_children_order'),
    ]

    operations = [
        migrations.AlterField(
            model_name='template',
            name='params',
            field=models.CharField(max_length=4096, verbose_name='parameters', blank=True),
        ),
    ]
