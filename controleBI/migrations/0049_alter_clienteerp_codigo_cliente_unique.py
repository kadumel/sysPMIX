from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("controleBI", "0048_alter_veiculo_seq_id_unique"),
    ]

    operations = [
        migrations.AlterField(
            model_name="clienteerp",
            name="codigo_cliente",
            field=models.CharField(blank=True, max_length=10, null=True, unique=True),
        ),
    ]
