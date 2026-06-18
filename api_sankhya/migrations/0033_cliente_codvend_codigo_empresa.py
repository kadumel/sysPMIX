from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0032_cliente_tempo_analise'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='codvend',
            field=models.IntegerField(blank=True, null=True, verbose_name='Código do Vendedor (CODVEND)'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='codigo_empresa',
            field=models.IntegerField(blank=True, null=True, verbose_name='Código da Empresa (CODEMP)'),
        ),
        migrations.AddIndex(
            model_name='cliente',
            index=models.Index(fields=['codvend'], name='sankhya_cli_codvend_idx'),
        ),
        migrations.AddIndex(
            model_name='cliente',
            index=models.Index(fields=['codigo_empresa'], name='sankhya_cli_codemp_idx'),
        ),
    ]
