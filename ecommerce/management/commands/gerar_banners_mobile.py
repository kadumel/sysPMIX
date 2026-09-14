from django.core.management.base import BaseCommand

from ecommerce.models import BannerPromocional


class Command(BaseCommand):
    help = 'Gera (ou regenera) a imagem mobile dos banners promocionais.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--forcar',
            action='store_true',
            help='Regenera mesmo quando já existe imagem mobile.',
        )

    def handle(self, *args, **options):
        forcar = options['forcar']
        qs = BannerPromocional.objects.exclude(imagem='')
        total = qs.count()
        ok = 0
        falhas = 0
        for banner in qs.iterator():
            try:
                if banner.gerar_imagem_mobile(forcar=forcar):
                    banner.save(update_fields=['imagem_mobile'])
                    ok += 1
            except Exception as exc:
                falhas += 1
                self.stderr.write(f'Banner #{banner.pk}: {exc}')
        self.stdout.write(self.style.SUCCESS(
            f'Banners: {total}. Gerados/atualizados: {ok}. Falhas: {falhas}.'
        ))
