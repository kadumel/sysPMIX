from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

import requests
from django.conf import settings
from django.db.models import Max

from .models import (
    Bairro,
    Cidade,
    Cliente,
    Contato,
    Empresa,
    Funcionario,
    GrupoProduto,
    ItemPedido,
    Logradouro,
    Motorista,
    Pedido,
    Preco,
    Produto,
    Vendedor,
    Veiculo,
)


def _get_token_headers() -> dict[str, str]:
    client_id = getattr(settings, "SANKHYA_CLIENT_ID", None)
    client_secret = getattr(settings, "SANKHYA_CLIENT_SECRET", None)
    x_token = getattr(settings, "SANKHYA_X_TOKEN", None)
    if not client_id or not client_secret or not x_token:
        raise RuntimeError(
            "Credenciais Sankhya não configuradas. Defina SANKHYA_CLIENT_ID, "
            "SANKHYA_CLIENT_SECRET e SANKHYA_X_TOKEN nas variáveis de ambiente."
        )

    url = "https://api.sankhya.com.br/authenticate"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    headers = {
        "accept": "application/x-www-form-urlencoded",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Token": x_token,
    }
    resp = requests.post(url, headers=headers, data=payload, timeout=60)
    resp.raise_for_status()
    body = resp.json()
    return {"accept": "application/json", "Authorization": f"Bearer {body['access_token']}"}


def _request_with_token_retry(method: str, url: str, headers: dict[str, str], **kwargs):
    resp = requests.request(method, url, headers=headers, **kwargs)
    if resp.status_code not in (401, 403):
        return resp, headers
    refreshed_headers = {**headers, **_get_token_headers()}
    resp = requests.request(method, url, headers=refreshed_headers, **kwargs)
    return resp, refreshed_headers


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_str(value: Any, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    val = str(value).strip()
    if not val or val.lower() == "null":
        return None
    if max_len and len(val) > max_len:
        return val[:max_len]
    return val


def _to_date(value: Any):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        try:
            return datetime.strptime(str(value)[:10], "%d/%m/%Y").date()
        except ValueError:
            return None


@dataclass
class SyncResult:
    total_processados: int = 0
    total_inseridos: int = 0
    total_atualizados: int = 0
    total_erros: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "total_processados": self.total_processados,
            "total_inseridos": self.total_inseridos,
            "total_atualizados": self.total_atualizados,
            "total_erros": self.total_erros,
        }


def _sync_paginated(
    *,
    url: str,
    list_key: str,
    process_item: Callable[[dict[str, Any]], tuple[bool, bool]],
    start_page: int = 0,
) -> SyncResult:
    headers = _get_token_headers()
    page = start_page
    has_more = True
    result = SyncResult()
    while has_more:
        resp, headers = _request_with_token_retry("GET", url, headers, params={"page": page}, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        pagination = data.get("pagination", {})
        has_more = _as_bool(pagination.get("hasMore", False))
        for item in data.get(list_key, []):
            try:
                created, touched = process_item(item)
                if touched:
                    result.total_processados += 1
                    if created:
                        result.total_inseridos += 1
                    else:
                        result.total_atualizados += 1
            except Exception:
                result.total_erros += 1
        page += 1
        if not pagination:
            has_more = False
    return result


def sync_veiculos() -> dict[str, int]:
    def process(v: dict[str, Any]):
        codigo = _to_int(v.get("codigoVeiculo"))
        if not codigo:
            return False, False
        defaults = {
            "placa": _to_str(v.get("placa"), 10) or "",
            "marca_modelo": _to_str(v.get("marcaModelo"), 100),
            "nome_motorista": _to_str(v.get("nomeMotorista"), 100),
            "codigo_motorista": _to_int(v.get("codigoMotorista")),
            "ativo": bool(v.get("ativo", True)),
        }
        obj, created = Veiculo.objects.update_or_create(codigo_veiculo=codigo, defaults=defaults)
        return created, bool(obj)

    return _sync_paginated(url="https://api.sankhya.com.br/v1/veiculos", list_key="veiculos", process_item=process).as_dict()


def sync_empresas() -> dict[str, int]:
    def process(v: dict[str, Any]):
        codigo = _to_int(v.get("codigoEmpresa"))
        if not codigo:
            return False, False
        defaults = {
            "nome_fantasia": _to_str(v.get("nomeFantasia"), 200),
            "razao_social": _to_str(v.get("razaoSocial"), 200),
            "cnpj_cpf": _to_str(v.get("cnpjCpf"), 20),
            "telefone": _to_str(v.get("telefone"), 20),
        }
        obj, created = Empresa.objects.update_or_create(codigo_empresa=codigo, defaults=defaults)
        return created, bool(obj)

    return _sync_paginated(url="https://api.sankhya.com.br/v1/empresas", list_key="empresas", process_item=process).as_dict()


def sync_cidades() -> dict[str, int]:
    def process(v: dict[str, Any]):
        codigo = _to_int(v.get("codigoCidade"))
        if not codigo:
            return False, False
        defaults = {
            "nome": _to_str(v.get("nome"), 200) or f"Cidade {codigo}",
            "uf": _to_str(v.get("uf"), 2),
            "codigo_regiao": _to_int(v.get("codigoRegiao")),
        }
        obj, created = Cidade.objects.update_or_create(codigo_cidade=codigo, defaults=defaults)
        return created, bool(obj)

    return _sync_paginated(url="https://api.sankhya.com.br/v1/cidades", list_key="cidades", process_item=process).as_dict()


def sync_logradouros() -> dict[str, int]:
    def process(v: dict[str, Any]):
        codigo = _to_int(v.get("codigoLogradouro"))
        nome = _to_str(v.get("nome"), 200)
        if not codigo or not nome:
            return False, False
        defaults = {"nome": nome, "tipo": _to_str(v.get("tipo"), 50)}
        obj, created = Logradouro.objects.update_or_create(codigo_logradouro=codigo, defaults=defaults)
        return created, bool(obj)

    return _sync_paginated(url="https://api.sankhya.com.br/v1/logradouros", list_key="logradouros", process_item=process).as_dict()


def sync_bairros() -> dict[str, int]:
    def process(v: dict[str, Any]):
        codigo = _to_int(v.get("codigoBairro"))
        nome = _to_str(v.get("nome"), 200)
        if not codigo or not nome:
            return False, False
        defaults = {"nome": nome, "nome_regiao": _to_str(v.get("nomeRegiao"), 100)}
        obj, created = Bairro.objects.update_or_create(codigo_bairro=codigo, defaults=defaults)
        return created, bool(obj)

    return _sync_paginated(url="https://api.sankhya.com.br/v1/bairros", list_key="bairros", process_item=process).as_dict()


def sync_vendedores() -> dict[str, int]:
    def process(v: dict[str, Any]):
        codigo = _to_int(v.get("codigoVendedor"))
        nome = _to_str(v.get("nome"), 200)
        if not codigo or not nome:
            return False, False
        defaults = {"nome": nome, "ativo": bool(v.get("ativo", True))}
        obj, created = Vendedor.objects.update_or_create(codigo_vendedor=codigo, defaults=defaults)
        return created, bool(obj)

    return _sync_paginated(url="https://api.sankhya.com.br/v1/vendedores", list_key="vendedores", process_item=process).as_dict()


def sync_clientes() -> dict[str, int]:
    headers = _get_token_headers()
    headers["Content-Type"] = "application/json"
    page = 0
    has_more = True
    result = SyncResult()
    url = getattr(settings, "SANKHYA_URL_GENERIC", None) or (
        "https://api.sankhya.com.br/gateway/v1/mge/service.sbr"
        "?serviceName=CRUDServiceProvider.loadRecords&outputType=json"
    )

    while has_more:
        body = {
            "serviceName": "CRUDServiceProvider.loadRecords",
            "requestBody": {
                "dataSet": {
                    "rootEntity": "Parceiro",
                    "includePresentationFields": "S",
                    "offsetPage": str(page),
                    "entity": {
                        "fieldset": {
                            "list": (
                                "CODPARC,TIPPESSOA,CGC_CPF,IDENTINSCESTAD,NOMEPARC,RAZAOSOCIAL,EMAIL,"
                                "TELEFONE,LIMCREDMENSAL,GRUPOAUTOR,LATITUDE,LONGITUDE,CODEND,NUMEND,"
                                "COMPLEMENTO,CODBAI,CODCID,CEP,CODTAB"
                            )
                        }
                    },
                }
            },
        }
        resp, headers = _request_with_token_retry("POST", url, headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        entities = (data.get("responseBody") or data).get("entities") or {}
        has_more = str(entities.get("hasMoreResult", "false")).lower() in {"1", "true", "s"}
        rows = entities.get("entity") or []
        if isinstance(rows, dict):
            rows = [rows]

        for row in rows:
            try:
                codigo = _to_int((row.get("f0") or {}).get("$") if isinstance(row.get("f0"), dict) else row.get("f0"))
                if codigo is None:
                    continue

                telefone_raw = (row.get("f7") or {}).get("$") if isinstance(row.get("f7"), dict) else row.get("f7")
                telefone = _to_str(telefone_raw, 20)
                ddd = None
                numero = None
                if telefone:
                    digits = "".join(ch for ch in telefone if ch.isdigit())
                    if len(digits) >= 10:
                        ddd = digits[:2]
                        numero = digits[2:20]
                    else:
                        numero = telefone

                defaults = {
                    "tipo": _to_str((row.get("f1") or {}).get("$") if isinstance(row.get("f1"), dict) else row.get("f1"), 10),
                    "cnpj_cpf": _to_str((row.get("f2") or {}).get("$") if isinstance(row.get("f2"), dict) else row.get("f2"), 20),
                    "ie_rg": _to_str((row.get("f3") or {}).get("$") if isinstance(row.get("f3"), dict) else row.get("f3"), 20),
                    "nome": _to_str((row.get("f4") or {}).get("$") if isinstance(row.get("f4"), dict) else row.get("f4"), 200),
                    "razao": _to_str((row.get("f5") or {}).get("$") if isinstance(row.get("f5"), dict) else row.get("f5"), 200),
                    "email": _to_str((row.get("f6") or {}).get("$") if isinstance(row.get("f6"), dict) else row.get("f6"), 100),
                    "telefone_ddd": _to_str(ddd, 5),
                    "telefone_numero": _to_str(numero, 20),
                    "limite_credito": _to_decimal((row.get("f8") or {}).get("$") if isinstance(row.get("f8"), dict) else row.get("f8")),
                    "grupo_autorizacao": _to_str((row.get("f9") or {}).get("$") if isinstance(row.get("f9"), dict) else row.get("f9"), 10),
                    "latitude": _to_str((row.get("f10") or {}).get("$") if isinstance(row.get("f10"), dict) else row.get("f10"), 50),
                    "longitude": _to_str((row.get("f11") or {}).get("$") if isinstance(row.get("f11"), dict) else row.get("f11"), 50),
                    "codend": _to_int((row.get("f12") or {}).get("$") if isinstance(row.get("f12"), dict) else row.get("f12")),
                    "numero": _to_str((row.get("f13") or {}).get("$") if isinstance(row.get("f13"), dict) else row.get("f13"), 20),
                    "complemento": _to_str((row.get("f14") or {}).get("$") if isinstance(row.get("f14"), dict) else row.get("f14"), 100),
                    "bairro": _to_str((row.get("f15") or {}).get("$") if isinstance(row.get("f15"), dict) else row.get("f15"), 100),
                    "cidade": _to_str((row.get("f16") or {}).get("$") if isinstance(row.get("f16"), dict) else row.get("f16"), 100),
                    "cep": _to_str((row.get("f17") or {}).get("$") if isinstance(row.get("f17"), dict) else row.get("f17"), 10),
                    "codtab": _to_int((row.get("f18") or {}).get("$") if isinstance(row.get("f18"), dict) else row.get("f18")),
                }
                defaults = {k: v for k, v in defaults.items() if v is not None}

                obj, created = Cliente.objects.update_or_create(codigo_cliente=codigo, defaults=defaults)
                result.total_processados += 1
                if created:
                    result.total_inseridos += 1
                else:
                    result.total_atualizados += 1
                _ = obj
            except Exception:
                result.total_erros += 1
        page += 1
    return result.as_dict()


def sync_motoristas() -> dict[str, int]:
    def process(v: dict[str, Any]):
        codigo = _to_int(v.get("codigoMotorista"))
        nome = _to_str(v.get("nome"), 200)
        if not codigo or not nome:
            return False, False
        defaults = {"nome": nome, "cpf": _to_str(v.get("cpf"), 14), "cidade": _to_str(v.get("cidade"), 100)}
        obj, created = Motorista.objects.update_or_create(codigo_motorista=codigo, defaults=defaults)
        return created, bool(obj)

    return _sync_paginated(url="https://api.sankhya.com.br/v1/motoristas", list_key="motoristas", process_item=process).as_dict()


def sync_precos() -> dict[str, int]:
    headers = _get_token_headers()
    result = SyncResult()
    base_url = (getattr(settings, "SANKHYA_URL_PRECOS", None) or "https://api.sankhya.com.br/v1/precos").strip()

    codtabs = (
        Cliente.objects.exclude(codtab__isnull=True)
        .exclude(codtab=0)
        .order_by()
        .values_list("codtab", flat=True)
        .distinct()
    )
    codtabs = list(codtabs)

    for codtab in codtabs:
        try:
            if "{codigo_tabela}" in base_url:
                url = base_url.format(codigo_tabela=codtab).rstrip("/")
            else:
                clean_base = base_url.rstrip("/")
                url = clean_base if clean_base.endswith(f"/tabela/{codtab}") else f"{clean_base}/tabela/{codtab}"
            pagina = 1
            tem_mais = True
            while tem_mais:
                resp, headers = _request_with_token_retry("GET", url, headers, params={"pagina": pagina}, timeout=120)
                if resp.status_code == 404:
                    resp, headers = _request_with_token_retry("GET", url, headers, params={"page": pagina}, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                for v in data.get("produtos", []):
                    produto = _to_int(v.get("codigoProduto"))
                    tabela = _to_int(codtab)
                    if produto is None or tabela is None:
                        continue
                    defaults = {
                        "valor": _to_decimal(v.get("valor")) or Decimal("0"),
                        "controle": _to_str(v.get("controle"), 50),
                        "unidade": _to_str(v.get("unidade"), 10),
                    }
                    _, created = Preco.objects.update_or_create(
                        codigo_produto=produto,
                        codigo_local_estoque=_to_int(v.get("codigoLocalEstoque")) or 0,
                        codigo_tabela=tabela,
                        defaults=defaults,
                    )
                    result.total_processados += 1
                    if created:
                        result.total_inseridos += 1
                    else:
                        result.total_atualizados += 1

                tem_mais_raw = data.get("temMaisRegistros", False)
                if isinstance(tem_mais_raw, str):
                    tem_mais = tem_mais_raw.strip().lower() == "true"
                else:
                    tem_mais = bool(tem_mais_raw)
                pagina += 1
        except Exception:
            result.total_erros += 1

    return result.as_dict()


def sync_produtos() -> dict[str, int]:
    def process(v: dict[str, Any]):
        codigo = _to_int(v.get("codigoProduto"))
        if not codigo:
            return False, False
        defaults = {
            "nome": _to_str(v.get("nome"), 200),
            "referencia": _to_str(v.get("referencia"), 100),
            "codigo_grupo_produto": _to_int(v.get("codigoGrupoProduto")),
            "ativo": bool(v.get("ativo", True)),
        }
        obj, created = Produto.objects.update_or_create(codigo_produto=codigo, defaults=defaults)
        return created, bool(obj)

    return _sync_paginated(url="https://api.sankhya.com.br/v1/produtos", list_key="produtos", process_item=process).as_dict()


def sync_grupos_produto() -> dict[str, int]:
    def process(v: dict[str, Any]):
        codigo = _to_int(v.get("codigoGrupoProduto"))
        nome = _to_str(v.get("nome"), 200)
        if not codigo or not nome:
            return False, False
        defaults = {
            "nome": nome,
            "codigo_grupo_produto_pai": _to_int(v.get("codigoGrupoProdutoPai")),
            "ativo": bool(v.get("ativo", True)),
        }
        obj, created = GrupoProduto.objects.update_or_create(codigo_grupo_produto=codigo, defaults=defaults)
        return created, bool(obj)

    return _sync_paginated(
        url="https://api.sankhya.com.br/v1/grupos-produto",
        list_key="grupos",
        process_item=process,
    ).as_dict()


def sync_pedidos() -> dict[str, int]:
    headers = _get_token_headers()
    page = 1
    has_more = True
    result = SyncResult()
    while has_more:
        resp, headers = _request_with_token_retry(
            "GET", "https://api.sankhya.com.br/v1/vendas/pedidos", headers, params={"page": page}, timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        pagination = data.get("pagination") or {}
        has_more = _as_bool(pagination.get("hasMore", False))
        for p in data.get("pedido") or data.get("pedidos") or []:
            try:
                codigo_nota = _to_int(p.get("codigoNota"))
                if not codigo_nota:
                    continue
                cliente = p.get("cliente") or {}
                defaults = {
                    "codigo_empresa": _to_int(p.get("codigoEmpresa")),
                    "codigo_cliente": _to_int(p.get("codigoCliente")),
                    "cliente_nome": _to_str(cliente.get("nome"), 200),
                    "cliente_razao": _to_str(cliente.get("razao"), 200),
                    "confirmada": bool(p.get("confirmada", False)),
                    "pendente": bool(p.get("pendente", True)),
                    "data_negociacao": _to_date(p.get("dataNegociacao")),
                    "valor_nota": _to_decimal(p.get("valorNota")),
                }
                defaults = {k: v for k, v in defaults.items() if v is not None}
                pedido, created = Pedido.objects.update_or_create(codigo_nota=codigo_nota, defaults=defaults)
                ItemPedido.objects.filter(pedido=pedido).delete()
                for item in p.get("itens") or []:
                    ItemPedido.objects.create(
                        pedido=pedido,
                        sequencia=_to_int(item.get("sequencia")) or 0,
                        cod_produto=_to_int(item.get("codProduto")),
                        descricao_produto=_to_str(item.get("descricaoProduto"), 300),
                        quantidade=_to_decimal(item.get("quantidade")),
                        valor_unitario=_to_decimal(item.get("valorUnitario")),
                        valor_total=_to_decimal(item.get("valorTotal")),
                    )
                result.total_processados += 1
                if created:
                    result.total_inseridos += 1
                else:
                    result.total_atualizados += 1
            except Exception:
                result.total_erros += 1
        page += 1
    return result.as_dict()


def sync_contatos() -> dict[str, int]:
    headers = _get_token_headers()
    headers["Content-Type"] = "application/json"
    page = 0
    has_more = True
    result = SyncResult()
    url = "https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=CRUDServiceProvider.loadRecords&outputType=json"
    while has_more:
        body = {
            "serviceName": "CRUDServiceProvider.loadRecords",
            "requestBody": {
                "dataSet": {
                    "rootEntity": "Contato",
                    "includePresentationFields": "S",
                    "offsetPage": str(page),
                    "entity": {"fieldset": {"list": "CODPARC,CODCONTATO,NOMECONTATO,EMAIL,TELEFONE,CELULAR"}},
                }
            },
        }
        resp, headers = _request_with_token_retry("POST", url, headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        entities = (data.get("responseBody") or data).get("entities") or {}
        has_more = str(entities.get("hasMoreResult", "false")).lower() in {"1", "true", "s"}
        raw = entities.get("entity") or []
        if isinstance(raw, dict):
            raw = [raw]
        for row in raw:
            try:
                codparc = _to_int((row.get("f0") or {}).get("$") if isinstance(row.get("f0"), dict) else row.get("f0"))
                codcontato = _to_int((row.get("f1") or {}).get("$") if isinstance(row.get("f1"), dict) else row.get("f1"))
                if codparc is None or codcontato is None:
                    continue
                defaults = {
                    "nomecontato": _to_str((row.get("f2") or {}).get("$") if isinstance(row.get("f2"), dict) else row.get("f2"), 200),
                    "email": _to_str((row.get("f3") or {}).get("$") if isinstance(row.get("f3"), dict) else row.get("f3"), 100),
                    "telefone": _to_str((row.get("f4") or {}).get("$") if isinstance(row.get("f4"), dict) else row.get("f4"), 20),
                    "celular": _to_str((row.get("f5") or {}).get("$") if isinstance(row.get("f5"), dict) else row.get("f5"), 20),
                }
                obj, created = Contato.objects.update_or_create(codparc=codparc, codcontato=codcontato, defaults=defaults)
                result.total_processados += 1
                if created:
                    result.total_inseridos += 1
                else:
                    result.total_atualizados += 1
                _ = obj
            except Exception:
                result.total_erros += 1
        page += 1
    return result.as_dict()


def sync_funcionarios() -> dict[str, int]:
    from api_sankhya.views import _funcionario_defaults_from_api_detalhe

    headers = _get_token_headers()
    result = SyncResult()
    page = 0
    has_more = True
    while has_more:
        resp, headers = _request_with_token_retry(
            "GET", "https://api.sankhya.com.br/v1/pessoal/funcionarios", headers, params={"page": page}, timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        bloco = data[0] if isinstance(data, list) and data else data
        codigos = bloco.get("codigos", [])
        has_more = _as_bool((bloco.get("pagination") or {}).get("hasMore", False))
        for resumo in codigos:
            codigo_empresa = _to_int(resumo.get("codigoEmpresa"))
            codigo_funcionario = _to_int(resumo.get("codigoFuncionario"))
            if codigo_empresa is None or codigo_funcionario is None:
                continue
            try:
                dresp, headers = _request_with_token_retry(
                    "GET",
                    f"https://api.sankhya.com.br/v1/pessoal/funcionarios/{codigo_funcionario}/empresa/{codigo_empresa}",
                    headers,
                    timeout=120,
                )
                dresp.raise_for_status()
                detalhe = dresp.json()
                if not isinstance(detalhe, dict):
                    result.total_erros += 1
                    continue
                defaults = _funcionario_defaults_from_api_detalhe(detalhe, resumo)
                obj, created = Funcionario.objects.update_or_create(
                    empresa_codigo=codigo_empresa,
                    codigo_funcionario=codigo_funcionario,
                    defaults=defaults,
                )
                result.total_processados += 1
                if created:
                    result.total_inseridos += 1
                else:
                    result.total_atualizados += 1
                _ = obj
            except Exception:
                result.total_erros += 1
        page += 1
    return result.as_dict()


INTEGRACOES = {
    "veiculos": ("Veículos", Veiculo, sync_veiculos),
    "empresas": ("Empresas", Empresa, sync_empresas),
    "cidades": ("Cidades", Cidade, sync_cidades),
    "logradouros": ("Logradouros", Logradouro, sync_logradouros),
    "bairros": ("Bairros", Bairro, sync_bairros),
    "vendedores": ("Vendedores", Vendedor, sync_vendedores),
    "clientes": ("Clientes", Cliente, sync_clientes),
    "motoristas": ("Motoristas", Motorista, sync_motoristas),
    "precos": ("Preços", Preco, sync_precos),
    "produtos": ("Produtos", Produto, sync_produtos),
    "grupos_produto": ("Grupos de Produto", GrupoProduto, sync_grupos_produto),
    "pedidos": ("Pedidos", Pedido, sync_pedidos),
    "contatos": ("Contatos", Contato, sync_contatos),
    "funcionarios": ("Funcionários", Funcionario, sync_funcionarios),
}


def executar_integracao(chave: str) -> dict[str, Any]:
    _, _, runner = INTEGRACOES[chave]
    return runner()


def obter_status_integracoes() -> list[dict[str, Any]]:
    linhas: list[dict[str, Any]] = []
    for chave, (nome, model, _) in INTEGRACOES.items():
        agregado = model.objects.aggregate(ultima_atualizacao=Max("updated_at"), total=Max("id"))
        linhas.append(
            {
                "chave": chave,
                "nome": nome,
                "ultima_atualizacao": agregado.get("ultima_atualizacao"),
                "total_registros": model.objects.count(),
                "permite_execucao": True,
            }
        )
    if not any(l["chave"] == "itens_pedido" for l in linhas):
        linhas.append(
            {
                "chave": "itens_pedido",
                "nome": "Itens do Pedido",
                "ultima_atualizacao": ItemPedido.objects.aggregate(ultima=Max("updated_at")).get("ultima"),
                "total_registros": ItemPedido.objects.count(),
                "permite_execucao": False,
                "observacao": "Atualizada junto com a integração de Pedidos.",
            }
        )
    return linhas
