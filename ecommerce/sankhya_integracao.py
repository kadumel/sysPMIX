"""Montagem e envio de pedidos da loja para a API Sankhya (POST /v1/vendas/pedidos)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.conf import settings
from django.utils import timezone

from api_sankhya.models import Cidade, Cliente
from api_sankhya.services import _get_token_headers, _request_with_token_retry

from .models import LocalEstoqueEcommerce, PedidoLoja, TopEnvioSankhya

logger = logging.getLogger(__name__)

SANKHYA_PEDIDOS_URL = 'https://api.sankhya.com.br/v1/vendas/pedidos'
SANKHYA_DB_EXPLORER_SERVICE = 'DbExplorerSP.executeQuery'

SQL_FINANCEIROS_CLIENTE = """
SELECT t.codParc, t.sugtipnegsaid, p.codtiptitpad, p.sequencia, p.prazo, p.percentual
FROM TGFCPL t
JOIN TGFPPG p ON p.Codtipvenda = t.sugtipnegsaid
WHERE t.codParc = {codparc}
""".strip()


class IntegracaoSankhyaError(Exception):
    """Erro de validação ou integração com o Sankhya."""


def _valor_api(valor: Decimal | float | int) -> float:
    return float(valor)


def _formatar_data_sankhya(dt: datetime) -> str:
    local = timezone.localtime(dt) if timezone.is_aware(dt) else dt
    return local.strftime('%d/%m/%Y')


def _formatar_hora_sankhya(dt: datetime) -> str:
    local = timezone.localtime(dt) if timezone.is_aware(dt) else dt
    return local.strftime('%H:%M')


def _to_int_opcional(valor) -> int | None:
    if valor in (None, ''):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def obter_uf_cliente(cliente: Cliente) -> str:
    codigo_cidade = _to_int_opcional(cliente.cidade)
    if not codigo_cidade:
        raise IntegracaoSankhyaError(
            'Cliente sem código de cidade (campo cidade / CODCID). Atualize o cadastro do cliente.'
        )

    cidade = Cidade.objects.filter(codigo_cidade=codigo_cidade).only('uf').first()
    if not cidade or not (cidade.uf or '').strip():
        raise IntegracaoSankhyaError(
            f'UF não encontrada para a cidade {codigo_cidade} do cliente.'
        )
    return cidade.uf.strip().upper()


def obter_codigo_local_estoque_cliente(cliente: Cliente) -> int:
    uf = obter_uf_cliente(cliente)
    mapeamento = (
        LocalEstoqueEcommerce.objects.filter(uf=uf, ativo=True)
        .only('codigo_local')
        .first()
    )
    if not mapeamento:
        raise IntegracaoSankhyaError(
            f'Nenhum local de estoque ativo cadastrado para a UF {uf}. '
            'Cadastre em Admin → Locais de estoque (e-commerce).'
        )

    codigo_local = (mapeamento.codigo_local or '').strip()
    if not codigo_local:
        raise IntegracaoSankhyaError(
            f'Local de estoque vazio para a UF {uf}.'
        )
    try:
        return int(codigo_local)
    except (TypeError, ValueError) as exc:
        raise IntegracaoSankhyaError(
            f'Local de estoque da UF {uf} deve ser o código numérico (CODLOCAL) do Sankhya. '
            f'Valor cadastrado: {codigo_local!r}. Atualize em Admin → Locais de estoque (e-commerce).'
        ) from exc


def _sankhya_gateway_url(service_name: str) -> str:
    base = getattr(settings, 'SANKHYA_URL_GENERIC', None) or (
        'https://api.sankhya.com.br/gateway/v1/mge/service.sbr'
    )
    base = base.split('?', 1)[0]
    return f'{base}?serviceName={service_name}&outputType=json'


def _data_base_local(dt: datetime) -> datetime:
    local = timezone.localtime(dt) if timezone.is_aware(dt) else dt
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _rows_execute_query_para_dicts(response_body: dict[str, Any]) -> list[dict[str, Any]]:
    campos = [
        str(meta.get('name') or '').strip().upper()
        for meta in (response_body.get('fieldsMetadata') or [])
    ]
    linhas = response_body.get('rows') or []
    resultado: list[dict[str, Any]] = []
    for linha in linhas:
        if not isinstance(linha, (list, tuple)):
            continue
        if campos:
            resultado.append(
                {
                    campos[i]: linha[i]
                    for i in range(min(len(campos), len(linha)))
                    if campos[i]
                }
            )
            continue
        if len(linha) >= 6:
            resultado.append(
                {
                    'CODPARC': linha[0],
                    'SUGTIPNEGSAID': linha[1],
                    'CODTIPTITPAD': linha[2],
                    'SEQUENCIA': linha[3],
                    'PRAZO': linha[4],
                    'PERCENTUAL': linha[5],
                }
            )
        elif len(linha) >= 4:
            resultado.append(
                {
                    'CODTIPTITPAD': linha[0],
                    'SEQUENCIA': linha[1],
                    'PRAZO': linha[2],
                    'PERCENTUAL': linha[3],
                }
            )
    return resultado


def _consultar_financeiros_cliente_sankhya(codigo_cliente: int) -> list[dict[str, Any]]:
    headers = _get_token_headers()
    headers['Content-Type'] = 'application/json'
    url = _sankhya_gateway_url(SANKHYA_DB_EXPLORER_SERVICE)
    body = {
        'serviceName': SANKHYA_DB_EXPLORER_SERVICE,
        'requestBody': {
            'sql': SQL_FINANCEIROS_CLIENTE.format(codparc=int(codigo_cliente)),
            'offsetPage': 0,
            'pageSize': 100,
        },
    }
    resp, _ = _request_with_token_retry('POST', url, headers, json=body, timeout=120)
    try:
        data = resp.json()
    except ValueError as exc:
        raise IntegracaoSankhyaError(
            f'Resposta inválida ao consultar financeiros (HTTP {resp.status_code}).'
        ) from exc

    if resp.status_code >= 400:
        mensagem = data.get('mensagem') or data.get('message') or resp.text[:500]
        raise IntegracaoSankhyaError(
            f'Erro ao consultar financeiros no Sankhya (HTTP {resp.status_code}): {mensagem}'
        )

    status = str(data.get('status', '')).strip().lower()
    if status not in {'1', 'true', 's'}:
        mensagem = data.get('statusMessage') or data.get('mensagem') or data
        raise IntegracaoSankhyaError(f'Consulta financeira Sankhya retornou status inválido: {mensagem}')

    response_body = data.get('responseBody') or {}
    linhas = _rows_execute_query_para_dicts(response_body)
    if not linhas:
        raise IntegracaoSankhyaError(
            f'Cliente {codigo_cliente} sem plano de pagamento configurado no Sankhya.'
        )
    return linhas


def _montar_financeiros_payload(
    linhas: list[dict[str, Any]],
    valor_total: Decimal,
    data_pedido: datetime,
) -> list[dict[str, Any]]:
    ordenadas = sorted(linhas, key=lambda row: int(row.get('SEQUENCIA') or 0))
    total = Decimal(str(valor_total)).quantize(Decimal('0.01'))
    base = _data_base_local(data_pedido)
    financeiros: list[dict[str, Any]] = []
    soma_parcelas = Decimal('0')

    for idx, linha in enumerate(ordenadas):
        try:
            sequencia = int(linha.get('SEQUENCIA'))
            tipo_pagamento = int(linha.get('CODTIPTITPAD'))
            prazo = int(linha.get('PRAZO') or 0)
            percentual = Decimal(str(linha.get('PERCENTUAL') or 0))
        except (TypeError, ValueError) as exc:
            raise IntegracaoSankhyaError(
                f'Linha financeira inválida retornada pelo Sankhya: {linha}'
            ) from exc

        if idx == len(ordenadas) - 1:
            valor_parcela = (total - soma_parcelas).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            valor_parcela = (total * percentual / Decimal('100')).quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP,
            )
            soma_parcelas += valor_parcela

        vencimento = base + timedelta(days=prazo)
        financeiros.append(
            {
                'sequencia': sequencia,
                'tipoPagamento': tipo_pagamento,
                'dataVencimento': vencimento.strftime('%d/%m/%Y'),
                'valorParcela': float(valor_parcela),
            }
        )

    return financeiros


def buscar_financeiros_pedido_sankhya(
    pedido: PedidoLoja,
    cliente: Cliente,
    valor_total: Decimal,
    aprovado_em: datetime | None = None,
) -> list[dict[str, Any]]:
    """Consulta TGFCPL/TGFPPG no Sankhya e monta o array financeiros do pedido."""
    if not cliente.codigo_cliente:
        raise IntegracaoSankhyaError('Cliente sem código (CODPARC) para consulta financeira.')

    momento = aprovado_em or timezone.now()
    linhas = _consultar_financeiros_cliente_sankhya(int(cliente.codigo_cliente))
    financeiros = _montar_financeiros_payload(linhas, valor_total, momento)
    logger.info(
        'Financeiros pedido loja #%s (cliente %s): %s parcela(s).',
        pedido.pk,
        cliente.codigo_cliente,
        len(financeiros),
    )
    return financeiros


def montar_payload_pedido_sankhya(
    pedido: PedidoLoja,
    top_envio: TopEnvioSankhya,
    aprovado_em: datetime,
    financeiros: list[dict[str, Any]],
) -> dict[str, Any]:
    cliente = pedido.cliente
    if not cliente:
        raise IntegracaoSankhyaError('Pedido sem cliente Sankhya vinculado.')

    codigo_vendedor = getattr(cliente, 'codvend', None)
    if not codigo_vendedor:
        raise IntegracaoSankhyaError(
            'Cliente sem vendedor (CODVEND) cadastrado. Atualize o cadastro do cliente.'
        )

    if not cliente.codigo_cliente:
        raise IntegracaoSankhyaError('Cliente sem código (CODPARC).')

    if not financeiros:
        raise IntegracaoSankhyaError('É necessário informar ao menos um financeiro para o pedido.')

    codigo_local_estoque = obter_codigo_local_estoque_cliente(cliente)
    itens_db = list(pedido.itens.all().order_by('id'))
    if not itens_db:
        raise IntegracaoSankhyaError('Pedido sem itens para envio ao Sankhya.')

    itens: list[dict[str, Any]] = []
    for sequencia, item in enumerate(itens_db, start=1):
        itens.append(
            {
                'sequencia': sequencia,
                'codigoProduto': item.codigo_produto,
                'quantidade': _valor_api(item.quantidade),
                'valorUnitario': _valor_api(item.preco_unitario),
                'codigoLocalEstoque': codigo_local_estoque,
                'controle': '',
            }
        )

    return {
        'notaModelo': top_envio.codigo_modelo,
        'data': _formatar_data_sankhya(aprovado_em),
        'hora': _formatar_hora_sankhya(aprovado_em),
        'codigoVendedor': int(codigo_vendedor),
        'codigoCliente': int(cliente.codigo_cliente),
        'valorTotal': _valor_api(pedido.valor_total),
        'itens': itens,
        'financeiros': financeiros,
    }


def _extrair_codigo_pedido_resposta(data: dict[str, Any]) -> str | None:
    retorno = data.get('retorno')
    if isinstance(retorno, dict):
        codigo = retorno.get('codigoPedido')
        if codigo is not None and str(codigo).strip():
            return str(codigo).strip()

    for chave in ('codigoPedido', 'codigo'):
        valor = data.get(chave)
        if valor is not None and str(valor).strip():
            return str(valor).strip()
    return None


def _resposta_pedido_sankhya_ok(data: dict[str, Any]) -> bool:
    if str(data.get('tipo') or '').strip().lower() == 'pedido':
        codigo = _extrair_codigo_pedido_resposta(data)
        if codigo:
            return True
    mensagem = str(data.get('mensagem') or data.get('message') or '').lower()
    return 'sucesso' in mensagem and _extrair_codigo_pedido_resposta(data) is not None


def _imprimir_json_envio_pedido_terminal(payload: dict[str, Any], pedido_id: int | None = None) -> None:
    payload_json = json.dumps(payload, indent=2, ensure_ascii=False)
    cabecalho = f'JSON envio Sankhya — pedido #{pedido_id}' if pedido_id else 'JSON envio Sankhya (pedido)'
    print(f'\n=== {cabecalho} ===\n{payload_json}\n===\n', flush=True)
    logger.info('Payload envio pedido Sankhya:\n%s', payload_json)


def enviar_pedido_sankhya(payload: dict[str, Any], pedido_id: int | None = None) -> str:
    headers = _get_token_headers()
    headers['Content-Type'] = 'application/json'
    url = getattr(settings, 'SANKHYA_URL_PEDIDOS_POST', SANKHYA_PEDIDOS_URL)

    _imprimir_json_envio_pedido_terminal(payload, pedido_id=pedido_id)
    print(f'POST {url}', flush=True)

    resp, _ = _request_with_token_retry('POST', url, headers, json=payload, timeout=120)
    try:
        data = resp.json()
    except ValueError as exc:
        logger.exception('Resposta inválida do Sankhya ao incluir pedido.')
        raise IntegracaoSankhyaError(
            f'Resposta inválida do Sankhya (HTTP {resp.status_code}).'
        ) from exc

    if resp.status_code >= 400:
        mensagem = data.get('mensagem') or data.get('message') or resp.text[:500]
        raise IntegracaoSankhyaError(
            f'Sankhya retornou erro HTTP {resp.status_code}: {mensagem}'
        )

    print(f'Resposta Sankhya (pedido):\n{json.dumps(data, indent=2, ensure_ascii=False)}\n', flush=True)

    if not _resposta_pedido_sankhya_ok(data):
        mensagem = data.get('mensagem') or data.get('message') or data
        raise IntegracaoSankhyaError(f'Sankhya não confirmou inclusão do pedido: {mensagem}')

    codigo_pedido = _extrair_codigo_pedido_resposta(data)
    if not codigo_pedido:
        raise IntegracaoSankhyaError(
            f'Sankhya não retornou o código do pedido. Resposta: {data}'
        )
    return codigo_pedido


def integrar_pedido_loja_sankhya(
    pedido: PedidoLoja,
    top_envio: TopEnvioSankhya,
    aprovado_em: datetime | None = None,
) -> str:
    """Monta o payload e envia o pedido ao Sankhya. Retorna o código do pedido no ERP."""
    if not top_envio:
        raise IntegracaoSankhyaError('TOP de envio não informada.')

    pedido = (
        PedidoLoja.objects.select_related('cliente')
        .prefetch_related('itens')
        .get(pk=pedido.pk)
    )
    cliente = pedido.cliente
    if not cliente:
        raise IntegracaoSankhyaError('Pedido sem cliente vinculado.')

    momento = aprovado_em or timezone.now()
    logger.info('Integração Sankhya pedido loja #%s iniciada.', pedido.pk)
    print(f'Integração Sankhya pedido #{pedido.pk} iniciada...', flush=True)
    financeiros = buscar_financeiros_pedido_sankhya(
        pedido,
        cliente,
        pedido.valor_total,
        aprovado_em=momento,
    )
    payload = montar_payload_pedido_sankhya(pedido, top_envio, momento, financeiros)
    logger.info('Enviando pedido loja #%s ao Sankhya (notaModelo=%s).', pedido.pk, top_envio.codigo_modelo)
    codigo_sankhya = enviar_pedido_sankhya(payload, pedido_id=pedido.pk)
    pedido.codigo_pedido_sankhya = codigo_sankhya
    pedido.save(update_fields=['codigo_pedido_sankhya', 'atualizado_em'])
    return codigo_sankhya
