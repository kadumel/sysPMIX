# Generated by Django 5.0.14 on 2025-05-27 09:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('controleBI', '0035_alter_clienteerp_bairro_cliente_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clienteerp',
            name='cnpj_cpf_cliente',
            field=models.CharField(blank=True, max_length=14, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='codigo_cliente',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='descr_cliente',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='filial_padrao',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='razao_cliente',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='seq_id',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]
