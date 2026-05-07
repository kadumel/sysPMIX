from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("controleBI", "0049_alter_clienteerp_codigo_cliente_unique"),
    ]

    operations = [
        migrations.AlterField(
            model_name="enderecocliente",
            name="cod_end_erp",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="enderecocliente",
            name="cod_praca_erp",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
    ]
