from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce', '0005_alter_produtoimagem_imagem'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedidoloja',
            name='codtab',
            field=models.IntegerField(
                blank=True,
                null=True,
                verbose_name='Código da tabela de preço',
            ),
        ),
        migrations.AddField(
            model_name='pedidoloja',
            name='valor_total',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=15,
                verbose_name='Valor total',
            ),
        ),
        migrations.AddField(
            model_name='itempedidoloja',
            name='preco_unitario',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=15,
                verbose_name='Preço unitário',
            ),
        ),
        migrations.AddField(
            model_name='itempedidoloja',
            name='valor_total',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=15,
                verbose_name='Valor total do item',
            ),
        ),
    ]
