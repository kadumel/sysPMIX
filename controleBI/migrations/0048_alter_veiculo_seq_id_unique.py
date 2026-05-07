from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("controleBI", "0047_alter_funcionario_cpf_unique"),
    ]

    operations = [
        migrations.AlterField(
            model_name="veiculo",
            name="seq_id",
            field=models.CharField(blank=True, max_length=10, null=True, unique=True),
        ),
    ]
