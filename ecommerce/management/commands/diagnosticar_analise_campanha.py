import json

from django.core.management.base import BaseCommand, CommandError

from api_sankhya.models import Cliente
from ecommerce.analise_pedido import calcular_analise_pedido, diagnosticar_novidades_campanha


class Command(BaseCommand):
    help = 'Diagnostica sugestões de campanha na análise do pedido (novidades).'

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, required=True, help='ID do Cliente Sankhya (api_sankhya).')
        parser.add_argument(
            '--codigo-produto',
            type=int,
            default=None,
            help='Filtra o relatório para um código de produto.',
        )

    def handle(self, *args, **options):
        cliente = Cliente.objects.filter(pk=options['cliente_id']).first()
        if not cliente:
            raise CommandError(f'Cliente id={options["cliente_id"]} não encontrado.')

        cart: list[dict] = []
        diag = diagnosticar_novidades_campanha(cliente, cart)
        resultado = calcular_analise_pedido(cliente, cart)

        codigo_filtro = options.get('codigo_produto')
        if codigo_filtro:
            diag['produtos'] = [
                p for p in diag.get('produtos', []) if p['codigo_produto'] == codigo_filtro
            ]

        self.stdout.write(self.style.SUCCESS(f'Cliente: {cliente} (codtab={diag.get("codtab")})'))
        self.stdout.write(f'Novidades calculadas: {len(resultado.novidades)}')
        self.stdout.write(json.dumps(diag, indent=2, ensure_ascii=False))
