# Generated by Django 5.0.14 on 2025-05-27 09:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('controleBI', '0034_clienteerp_alter_cliente_options_enderecocliente'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clienteerp',
            name='bairro_cliente',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='cep_cliente',
            field=models.CharField(blank=True, max_length=8, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='cidade_cliente',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='cliente_cod_rota_erp',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='cliente_descricao_rota',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='cod_segmento',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='data_cadastro_cliente',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='descr_segmento',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='end_cliente',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='forma_pgto_cliente',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='num_end_cliente',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='rede_loja_cliente',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='saldo_disp_cliente',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='status_cred_cliente',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='turnos_entrega',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='uf_cliente',
            field=models.CharField(blank=True, max_length=2, null=True),
        ),
        migrations.AlterField(
            model_name='clienteerp',
            name='vlr_credito_cliente',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
