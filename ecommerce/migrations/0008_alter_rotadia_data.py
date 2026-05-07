from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce', '0007_rotas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rotadia',
            name='data',
            field=models.DateField(db_index=True, verbose_name='Data'),
        ),
    ]
