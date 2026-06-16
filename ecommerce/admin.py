from django.contrib import admin, messages
from django.utils import timezone

from .models import (
    BannerPromocional,
    Campanha,
    ItemCampanha,
    ItemPedidoLoja,
    NotificacaoLoja,
    PedidoLoja,
    ProdutoImagem,
    RotaDia,
    RotaDiaAjudante,
    RotaDiaCliente,
    RotaPadrao,
    RotaPadraoAjudante,
    RotaPadraoCliente,
    TopEnvioSankhya,
    LocalEstoqueEcommerce,
)
from .services import criar_notificacao, integrar_pedido_no_sistema_externo
from .sankhya_integracao import IntegracaoSankhyaError


class ItemPedidoLojaInline(admin.TabularInline):
    model = ItemPedidoLoja
    extra = 0
    readonly_fields = ('codigo_produto', 'nome_produto', 'quantidade', 'preco_unitario', 'valor_total')
    can_delete = False


@admin.register(PedidoLoja)
class PedidoLojaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'cliente',
        'codtab',
        'top_envio',
        'valor_total',
        'status',
        'codigo_pedido_sankhya',
        'criado_em',
    )
    list_filter = ('status', 'criado_em')
    search_fields = (
        'user__username',
        'user__email',
        'codigo_pedido_sankhya',
    )
    readonly_fields = (
        'aprovado_por',
        'aprovado_em',
        'codtab',
        'codigo_pedido_sankhya',
        'top_envio',
        'valor_total',
        'criado_em',
        'atualizado_em',
    )
    inlines = [ItemPedidoLojaInline]
    actions = ('acao_autorizar_integrar', 'acao_rejeitar')

    fieldsets = (
        (None, {'fields': ('user', 'cliente', 'status', 'codtab', 'valor_total')}),
        ('Comercial', {'fields': ('observacao_comercial',)}),
        ('Integração Sankhya', {'fields': ('codigo_pedido_sankhya', 'top_envio')}),
        (
            'Auditoria',
            {'fields': ('aprovado_por', 'aprovado_em', 'criado_em', 'atualizado_em')},
        ),
    )

    def save_model(self, request, obj, form, change):
        old_obs = ''
        old_status = PedidoLoja.Status.PENDENTE
        if change and obj.pk:
            prev = (
                PedidoLoja.objects.filter(pk=obj.pk)
                .values('observacao_comercial', 'status')
                .first()
            )
            if prev:
                old_obs = prev['observacao_comercial'] or ''
                old_status = prev['status']
        super().save_model(request, obj, form, change)
        new_obs = (obj.observacao_comercial or '').strip()
        if change and new_obs and new_obs != (old_obs or '').strip():
            criar_notificacao(
                obj.user,
                f'Mensagem sobre o pedido #{obj.pk}',
                new_obs,
                pedido=obj,
            )
        if change and old_status != obj.status:
            if obj.status == PedidoLoja.Status.AUTORIZADO:
                criar_notificacao(
                    obj.user,
                    f'Pedido #{obj.pk} autorizado',
                    (
                        'Seu pedido foi autorizado.'
                        + (
                            f' Pedido Sankhya: {obj.codigo_pedido_sankhya}.'
                            if obj.codigo_pedido_sankhya
                            else ''
                        )
                    ),
                    pedido=obj,
                )
            elif obj.status == PedidoLoja.Status.REJEITADO:
                criar_notificacao(
                    obj.user,
                    f'Pedido #{obj.pk} não aprovado',
                    obj.observacao_comercial
                    or 'Entre em contato com o comercial para mais informações.',
                    pedido=obj,
                )

    @admin.action(description='Autorizar e integrar ao sistema externo')
    def acao_autorizar_integrar(self, request, queryset):
        ok = 0
        for pedido in queryset:
            if pedido.status != PedidoLoja.Status.PENDENTE:
                continue
            if not pedido.top_envio_id:
                self.message_user(
                    request,
                    f'Pedido #{pedido.pk} sem TOP de envio. Aprove pela gestão de notificações.',
                    level=messages.ERROR,
                )
                continue
            try:
                aprovado_em = timezone.now()
                ref = integrar_pedido_no_sistema_externo(pedido, aprovado_em=aprovado_em)
            except IntegracaoSankhyaError as exc:
                self.message_user(
                    request,
                    f'Pedido #{pedido.pk}: {exc}',
                    level=messages.ERROR,
                )
                continue
            pedido.codigo_pedido_sankhya = str(ref)[:20]
            pedido.status = PedidoLoja.Status.AUTORIZADO
            pedido.aprovado_por = request.user
            pedido.aprovado_em = aprovado_em
            pedido.save(
                update_fields=[
                    'codigo_pedido_sankhya',
                    'status',
                    'aprovado_por',
                    'aprovado_em',
                    'atualizado_em',
                ]
            )
            criar_notificacao(
                pedido.user,
                f'Pedido #{pedido.pk} autorizado',
                f'Seu pedido foi aprovado e registrado no Sankhya. Pedido: {ref}.',
                pedido=pedido,
            )
            ok += 1
        if ok:
            self.message_user(request, f'{ok} pedido(s) autorizado(s) e integrado(s).')

    @admin.action(description='Rejeitar pedidos pendentes selecionados')
    def acao_rejeitar(self, request, queryset):
        n = 0
        for pedido in queryset.filter(status=PedidoLoja.Status.PENDENTE):
            pedido.status = PedidoLoja.Status.REJEITADO
            pedido.save(update_fields=['status', 'atualizado_em'])
            criar_notificacao(
                pedido.user,
                f'Pedido #{pedido.pk} não aprovado',
                pedido.observacao_comercial
                or 'Seu pedido não foi aprovado. Consulte o comercial.',
                pedido=pedido,
            )
            n += 1
        if n:
            self.message_user(request, f'{n} pedido(s) rejeitado(s).')


@admin.register(NotificacaoLoja)
class NotificacaoLojaAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'titulo', 'lida', 'criado_em', 'pedido')
    list_filter = ('lida', 'criado_em')
    search_fields = ('user__username', 'titulo', 'mensagem')
    readonly_fields = ('user', 'pedido', 'titulo', 'mensagem', 'criado_em')

    def has_add_permission(self, request):
        return False


@admin.register(TopEnvioSankhya)
class TopEnvioSankhyaAdmin(admin.ModelAdmin):
    list_display = ('codigo_top', 'codigo_modelo', 'descricao', 'ativo', 'atualizado_em')
    list_filter = ('ativo',)
    search_fields = ('codigo_top', 'codigo_modelo', 'descricao')
    list_editable = ('ativo',)


@admin.register(LocalEstoqueEcommerce)
class LocalEstoqueEcommerceAdmin(admin.ModelAdmin):
    list_display = ('uf', 'codigo_local', 'ativo', 'atualizado_em')
    list_filter = ('ativo', 'uf')
    search_fields = ('uf', 'codigo_local')
    list_editable = ('ativo',)


class ItemCampanhaInline(admin.TabularInline):
    model = ItemCampanha
    extra = 1
    autocomplete_fields = ('produto',)


@admin.register(Campanha)
class CampanhaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'data_inicio', 'data_fim', 'criado_em')
    list_filter = ('data_inicio', 'data_fim')
    search_fields = ('nome', 'descricao')
    readonly_fields = ('criado_em', 'atualizado_em')
    inlines = [ItemCampanhaInline]
    fieldsets = (
        (None, {'fields': ('nome', 'descricao', 'data_inicio', 'data_fim')}),
        ('Auditoria', {'fields': ('criado_em', 'atualizado_em')}),
    )


@admin.register(BannerPromocional)
class BannerPromocionalAdmin(admin.ModelAdmin):
    list_display = ('id', 'titulo', 'descricao_curta', 'ordem', 'ativo', 'criado_em')
    list_editable = ('ordem', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('titulo', 'descricao_curta', 'descricao_longa', 'call_to_action')


@admin.register(ProdutoImagem)
class ProdutoImagemAdmin(admin.ModelAdmin):
    list_display = ('id', 'produto', 'nome_imagem', 'ativo', 'criado_em')
    list_filter = ('ativo', 'criado_em')
    search_fields = ('produto__codigo_produto', 'produto__nome', 'nome_imagem')
    readonly_fields = ('nome_imagem', 'criado_em', 'atualizado_em')


class RotaPadraoClienteInline(admin.TabularInline):
    model = RotaPadraoCliente
    extra = 0
    autocomplete_fields = ('cliente',)
    ordering = ('ordem', 'id')


class RotaPadraoAjudanteInline(admin.TabularInline):
    model = RotaPadraoAjudante
    extra = 0
    autocomplete_fields = ('funcionario',)
    ordering = ('ordem', 'id')


@admin.register(RotaPadrao)
class RotaPadraoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'responsavel', 'veiculo', 'motorista', 'ativa', 'criado_em')
    list_filter = ('ativa', 'criado_em')
    search_fields = ('nome', 'responsavel__username', 'responsavel__first_name', 'responsavel__last_name')
    autocomplete_fields = ('responsavel', 'veiculo', 'motorista')
    inlines = [RotaPadraoAjudanteInline, RotaPadraoClienteInline]


class RotaDiaClienteInline(admin.TabularInline):
    model = RotaDiaCliente
    extra = 0
    autocomplete_fields = ('cliente',)
    ordering = ('ordem', 'id')


class RotaDiaAjudanteInline(admin.TabularInline):
    model = RotaDiaAjudante
    extra = 0
    autocomplete_fields = ('funcionario',)
    ordering = ('ordem', 'id')


@admin.register(RotaDia)
class RotaDiaAdmin(admin.ModelAdmin):
    list_display = ('id', 'data', 'rota_padrao', 'veiculo', 'motorista', 'criado_por', 'criado_em')
    list_filter = ('data', 'criado_em')
    search_fields = ('data', 'criado_por__username', 'rota_padrao__nome')
    autocomplete_fields = ('rota_padrao', 'criado_por', 'veiculo', 'motorista')
    inlines = [RotaDiaAjudanteInline, RotaDiaClienteInline]
