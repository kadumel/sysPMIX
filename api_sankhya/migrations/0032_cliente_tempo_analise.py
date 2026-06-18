from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0031_itemnotafiscal_vlrdesc_statusnota'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='tempo_analise',
            field=models.PositiveIntegerField(
                default=2,
                help_text='Período padrão em meses para análise comercial do cliente.',
                verbose_name='Tempo de análise (meses)',
            ),
        ),
    ]
