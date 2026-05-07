from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ecommerce', '0002_bannerpromocional'),
    ]

    operations = [
        migrations.AddField(
            model_name='bannerpromocional',
            name='call_to_action',
            field=models.CharField(blank=True, max_length=120, verbose_name='Call-to-action'),
        ),
        migrations.AddField(
            model_name='bannerpromocional',
            name='descricao_curta',
            field=models.CharField(blank=True, max_length=220, verbose_name='Descrição curta'),
        ),
        migrations.AddField(
            model_name='bannerpromocional',
            name='descricao_longa',
            field=models.TextField(blank=True, verbose_name='Descrição longa'),
        ),
    ]
