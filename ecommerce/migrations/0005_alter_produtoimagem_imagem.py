import ecommerce.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ecommerce', '0004_produtoimagem'),
    ]

    operations = [
        migrations.AlterField(
            model_name='produtoimagem',
            name='imagem',
            field=models.ImageField(
                upload_to=ecommerce.models._produto_imagem_upload_to,
                verbose_name='Imagem',
            ),
        ),
    ]
