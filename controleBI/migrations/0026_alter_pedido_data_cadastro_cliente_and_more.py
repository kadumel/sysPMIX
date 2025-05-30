# Generated by Django 5.0.14 on 2025-04-27 22:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('controleBI', '0025_alter_pedido_data_pedido'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pedido',
            name='data_cadastro_cliente',
            field=models.DateField(blank=True, null=True, verbose_name='Data Cadastro Cliente'),
        ),
        migrations.AlterField(
            model_name='pedido',
            name='data_pedido',
            field=models.DateField(blank=True, null=True, verbose_name='Data do Pedido'),
        ),
        migrations.AlterField(
            model_name='pedido',
            name='data_ult_compra',
            field=models.DateField(blank=True, null=True, verbose_name='Última Compra'),
        ),
        migrations.AlterField(
            model_name='pedido',
            name='dt_list_nf',
            field=models.DateField(blank=True, null=True, verbose_name='Data da Coleta'),
        ),
    ]
