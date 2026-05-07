from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api_sankhya", "0023_cliente_dataalter"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
IF COL_LENGTH('sankhya_cliente', 'dataalter') IS NOT NULL
   AND COL_LENGTH('sankhya_cliente', 'dtalter') IS NULL
BEGIN
    EXEC sp_rename 'sankhya_cliente.dataalter', 'dtalter', 'COLUMN';
END
""",
            reverse_sql="""
IF COL_LENGTH('sankhya_cliente', 'dtalter') IS NOT NULL
   AND COL_LENGTH('sankhya_cliente', 'dataalter') IS NULL
BEGIN
    EXEC sp_rename 'sankhya_cliente.dtalter', 'dataalter', 'COLUMN';
END
""",
        ),
    ]
