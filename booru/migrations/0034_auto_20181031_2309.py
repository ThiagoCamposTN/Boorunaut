# Generated by Django 2.1.2 on 2018-10-31 23:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('booru', '0033_configuration'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='configuration',
            options={'permissions': (('change_configurations', 'Can change the configurations of the booru'),)},
        ),
        migrations.AlterModelOptions(
            name='gallery',
            options={'verbose_name_plural': 'Galleries'},
        ),
    ]
