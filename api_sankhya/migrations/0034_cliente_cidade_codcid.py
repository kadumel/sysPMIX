from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0033_cliente_codvend_codigo_empresa'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cliente',
            name='cidade',
            field=models.CharField(
                blank=True,
                help_text='Código da cidade no Sankhya (CODCID), relacionado a sankhya_cidade.codigo_cidade.',
                max_length=100,
                null=True,
                verbose_name='Cidade (CODCID)',
            ),
        ),
    ]
