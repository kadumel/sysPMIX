# Generated by Django 5.0.14 on 2025-04-20 19:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('controleBI', '0003_ajudante_sincronizado_cliente_sincronizado_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='ajudante',
            name='apelido',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='motorista',
            name='apelido',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='vendedor',
            name='apelido',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
