from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0025_contato_dtalter'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='origem',
            field=models.CharField(default='SANKHYA', max_length=50, verbose_name='Origem'),
        ),
        migrations.AlterField(
            model_name='pedido',
            name='codigo_nota',
            field=models.IntegerField(verbose_name='Código da Nota'),
        ),
        migrations.AlterUniqueTogether(
            name='pedido',
            unique_together={('origem', 'codigo_nota')},
        ),
        migrations.RemoveIndex(
            model_name='pedido',
            name='sankhya_ped_codigo__8594dc_idx',
        ),
        migrations.AddIndex(
            model_name='pedido',
            index=models.Index(fields=['origem', 'codigo_nota'], name='sankhya_ped_origem_4a1b2c_idx'),
        ),
    ]
