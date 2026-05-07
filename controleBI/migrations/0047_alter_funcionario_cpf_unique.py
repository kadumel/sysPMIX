from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("controleBI", "0046_alter_perfilusuario_perfil_gerente_comercial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="funcionario",
            name="cpf",
            field=models.CharField(max_length=14, unique=True),
        ),
    ]
