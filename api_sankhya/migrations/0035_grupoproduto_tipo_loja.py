from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0034_cliente_cidade_codcid'),
    ]

    operations = [
        migrations.AddField(
            model_name='grupoproduto',
            name='tipo_loja',
            field=models.CharField(
                blank=True,
                choices=[('mercadoria', 'Mercadoria'), ('revenda', 'Revenda')],
                default='',
                help_text='Classificação Mercadoria ou Revenda para filtro no e-commerce.',
                max_length=20,
                verbose_name='Tipo na loja',
            ),
        ),
        migrations.AddIndex(
            model_name='grupoproduto',
            index=models.Index(fields=['tipo_loja'], name='sankhya_gru_tipo_lo_8a1f2d_idx'),
        ),
    ]
