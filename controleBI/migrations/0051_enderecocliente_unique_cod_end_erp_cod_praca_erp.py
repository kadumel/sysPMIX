from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("controleBI", "0050_alter_enderecocliente_cod_end_erp_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="enderecocliente",
            name="cod_end_erp",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name="enderecocliente",
            name="cod_praca_erp",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddConstraint(
            model_name="enderecocliente",
            constraint=models.UniqueConstraint(
                fields=("cod_end_erp", "cod_praca_erp"),
                name="uniq_enderecocliente_cod_end_praca_erp",
            ),
        ),
    ]
