from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db.models import Max
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
import os

import requests
from django_q.tasks import async_task
import json

from controleBI.decorators import requer_acesso_bi
from controleBI.models import PerfilUsuario
from controleBI.perfil_utils import ensure_perfil

from django_q.models import Task

from .tasks import run_integracao_sankhya, run_todas_integracoes_sankhya
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
    Pedido,
    Preco,
    Produto,
    Veiculo,
)


def _wants_json(request: HttpRequest) -> bool:
    return "application/json" in (request.headers.get("Accept") or "")


def _require_admin_integracoes(request: HttpRequest):
    perfil = ensure_perfil(request.user)
    if perfil and perfil.perfil == PerfilUsuario.Perfil.ADMINISTRADOR:
        return None
    if _wants_json(request):
        return JsonResponse({"error": "Apenas administradores podem acessar Integrações."}, status=403)
    messages.error(request, "Apenas administradores podem acessar Integrações.")
    return redirect("dashboard")


def _json_safe(value: Any):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(x) for x in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def getToken():
    url = _get_env_or_setting("SANKHYA_URL_AUTH")
    client_id = _get_env_or_setting("SANKHYA_CLIENT_ID")
    client_secret = _get_env_or_setting("SANKHYA_CLIENT_SECRET")
    x_token = _get_env_or_setting("SANKHYA_X_TOKEN")
    payload = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
    headers = {"accept": "application/x-www-form-urlencoded", "Content-Type": "application/x-www-form-urlencoded", "X-Token": x_token}
    response = requests.request("POST", url, headers=headers, data=payload, timeout=60)
    response.raise_for_status()
    response_data = response.json()
    return {"accept": "application/json", "Authorization": f"Bearer {response_data['access_token']}"}


def _request_with_token_retry(method: str, url: str, headers: dict[str, str], **kwargs):
    print(url)
    print(kwargs)
    resp = requests.request(method, url, headers=headers, **kwargs)
    if resp.status_code not in (401, 403):
        return resp, headers
    refreshed_headers = {**headers, **getToken()}
    resp = requests.request(method, url, headers=refreshed_headers, **kwargs)
    print(json.dumps(resp.json(), indent=4))
    return resp, refreshed_headers


def _is_no_records_not_found(resp: requests.Response) -> bool:
    if resp.status_code != 404:
        return False
    try:
        payload = resp.json()
    except ValueError:
        return False
    error = payload.get("error") or {}
    code = str(error.get("code") or "").upper()
    details = str(error.get("details") or "").lower()
    message = str(error.get("message") or "").lower()
    return code == "RESOURCE_NOT_FOUND" and (
        "nenhum registro" in details
        or "nenhum registro" in message
    )


def _is_no_records_payload(payload: Any) -> bool:
    # Alguns endpoints retornam 0 quando não há dados.
    if payload == 0:
        return True
    # Em alguns casos o erro vem no corpo, mesmo sem HTTP 404.
    if isinstance(payload, dict):
        error = payload.get("error") or {}
        code = str(error.get("code") or "").upper()
        status_code = payload.get("statusCode")
        details = str(error.get("details") or "").lower()
        message = str(error.get("message") or "").lower()
        if (status_code == 404 or code == "RESOURCE_NOT_FOUND") and (
            "nenhum registro" in details
            or "nenhum registro" in message
        ):
            return True
    return False


def _get_env_or_setting(name: str) -> str:
    value = getattr(settings, name, None) or os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} não configurada nas variáveis de ambiente.")
    return value



def _to_int(val):
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _to_decimal(val):
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _to_str(val, max_len=None):
    if val is None:
        return None
    v = str(val).strip()
    if not v or v.lower() == "null":
        return None
    if max_len and len(v) > max_len:
        return v[:max_len]
    return v


def _to_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value)[:10], fmt).date()
        except ValueError:
            continue
    return None


def _to_datetime_iso_seconds(value):
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw.lower() == "null":
        return None
    if " " in raw and "T" not in raw:
        raw = raw.replace(" ", "T", 1)
    if "." in raw:
        raw = raw.split(".", 1)[0]
    # Converte de dd/mm/yyyyTHH:MM:SS para yyyy-mm-ddTHH:MM:SS
    if "/" in raw:
        try:
            return datetime.strptime(raw, "%d/%m/%YT%H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    return raw


def _parse_datetime_flexible(value):
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw.lower() == "null":
        return None
    if " " in raw and "T" not in raw:
        raw = raw.replace(" ", "T", 1)
    if "." in raw:
        raw = raw.split(".", 1)[0]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%d/%m/%YT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _pagination_has_more(pagination: dict | None) -> bool:
    """Interpreta hasMore da API Sankhya (string, bool, int, etc.)."""
    if not pagination:
        return False
    hm = pagination.get("hasMore")
    if hm is None:
        hm = pagination.get("has_more")
    if isinstance(hm, bool):
        return hm
    if isinstance(hm, (int, float)):
        return int(hm) != 0
    if isinstance(hm, str):
        return hm.strip().lower() in ("true", "1", "s", "sim", "yes")
    return bool(hm)


def _pedidos_list_from_api_payload(data: dict[str, Any]) -> list[Any]:
    """Extrai a lista de pedidos do JSON (chaves variam por versão/endpoint)."""
    if not isinstance(data, dict):
        return []
    for key in ("pedido", "pedidos", "registros", "lista", "items", "data"):
        v = data.get(key)
        if v is None:
            continue
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            inner = v.get("pedido") or v.get("pedidos") or v.get("items") or v.get("lista")
            if isinstance(inner, list):
                return inner
            if isinstance(inner, dict):
                return [inner]
            return [v]
    return []


def _codigo_nota_from_pedido_payload(p: dict[str, Any]) -> int | None:
    """Identificador único do documento na API (vários nomes possíveis)."""
    for k in (
        "codigoNota",
        "codigo_nota",
        "codNota",
        "nuNota",
        "nroUnico",
        "nroNota",
        "id",
        "ID",
    ):
        cod = _to_int(p.get(k))
        if cod:
            return cod
    return None


def _max_pedido_data_hora_alteracao_for_modified_since() -> str | None:
    """
    Maior data_hora_alteracao real (campo texto); evita Max() SQL incorreto
    e modifiedSince que deixa registros de fora.
    """
    maior: datetime | None = None
    qs = Pedido.objects.exclude(data_hora_alteracao__isnull=True).exclude(data_hora_alteracao="").values_list(
        "data_hora_alteracao", flat=True
    )
    for valor in qs:
        dt = _parse_datetime_flexible(valor)
        if dt and (maior is None or dt > maior):
            maior = dt
    if maior is None:
        return None
    return maior.strftime("%Y-%m-%dT%H:%M:%S")


def _max_dtalter_cliente_iso():
    # dtalter é CharField e pode conter formatos diferentes; por isso
    # o MAX em banco pode ser incorreto. Calculamos a maior data real.
    maior_data = None
    for valor in Cliente.objects.exclude(dtalter__isnull=True).exclude(dtalter="").values_list("dtalter", flat=True):
        dt = _parse_datetime_flexible(valor)
        if dt and (maior_data is None or dt > maior_data):
            maior_data = dt
    if maior_data is None:
        return None
    return maior_data.strftime("%Y-%m-%dT%H:%M:%S")


def _max_dtalter_contato_iso():
    maior_data = None
    for valor in Contato.objects.exclude(dtalter__isnull=True).exclude(dtalter="").values_list("dtalter", flat=True):
        dt = _parse_datetime_flexible(valor)
        if dt and (maior_data is None or dt > maior_data):
            maior_data = dt
    if maior_data is None:
        return None
    return maior_data.strftime("%Y-%m-%dT%H:%M:%S")


def _iso_to_criteria_date_start_of_day(value):
    dt = _parse_datetime_flexible(value)
    if dt is None:
        return None
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def _sync_paginated(url: str, list_key: str, callback: Callable[[dict[str, Any]], tuple[bool, bool]], start_page: int = 0):
    page = start_page
    has_more = True
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}
    headers = getToken()
    while has_more:
        resp, headers = _request_with_token_retry("GET", url, headers, params={"page": page}, timeout=360)
        if _is_no_records_not_found(resp):
            break
        resp.raise_for_status()
        data = resp.json()
        pagination = data.get("pagination", {})
        has_more = str(pagination.get("hasMore", "false")).lower() == "true"
        for raw in data.get(list_key, []):
            created, touched = callback(raw)
            if touched:
                out["total_processados"] += 1
                if created:
                    out["total_inseridos"] += 1
                else:
                    out["total_atualizados"] += 1
        page += 1
        if not pagination:
            has_more = False
    return out


def getVeiculos():
    def cb(v):
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
        _, created = Veiculo.objects.update_or_create(codigo_veiculo=codigo, defaults=defaults)
        return created, True

    return _sync_paginated(_get_env_or_setting("SANKHYA_URL_VEICULOS"), "veiculos", cb)


def getEmpresas():
    def cb(v):
        codigo = _to_int(v.get("codigoEmpresa"))
        if not codigo:
            return False, False
        defaults = {"nome_fantasia": _to_str(v.get("nomeFantasia"), 200), "razao_social": _to_str(v.get("razaoSocial"), 200), "cnpj_cpf": _to_str(v.get("cnpjCpf"), 20)}
        _, created = Empresa.objects.update_or_create(codigo_empresa=codigo, defaults=defaults)
        return created, True

    return _sync_paginated(_get_env_or_setting("SANKHYA_URL_EMPRESAS"), "empresas", cb)


def getCidadeLegado():
    def cb(v):
        codigo = _to_int(v.get("codigoCidade"))
        if not codigo:
            return False, False
        defaults = {"nome": _to_str(v.get("nome"), 200) or f"Cidade {codigo}", "uf": _to_str(v.get("uf"), 2), "codigo_regiao": _to_int(v.get("codigoRegiao"))}
        _, created = Cidade.objects.update_or_create(codigo_cidade=codigo, defaults=defaults)
        return created, True

    return _sync_paginated(_get_env_or_setting("SANKHYA_URL_CIDADES"), "cidades", cb)


def getLogradouros():
    def cb(v):
        codigo = _to_int(v.get("codigoLogradouro"))
        nome = _to_str(v.get("nome"), 200)
        if not codigo or not nome:
            return False, False
        _, created = Logradouro.objects.update_or_create(codigo_logradouro=codigo, defaults={"nome": nome, "tipo": _to_str(v.get("tipo"), 50)})
        return created, True

    return _sync_paginated(_get_env_or_setting("SANKHYA_URL_LOGRADOUROS"), "logradouros", cb)


def getBairros():
    def cb(v):
        codigo = _to_int(v.get("codigoBairro"))
        nome = _to_str(v.get("nome"), 200)
        if not codigo or not nome:
            return False, False
        _, created = Bairro.objects.update_or_create(codigo_bairro=codigo, defaults={"nome": nome, "nome_regiao": _to_str(v.get("nomeRegiao"), 100)})
        return created, True

    return _sync_paginated(_get_env_or_setting("SANKHYA_URL_BAIRROS"), "bairros", cb)


def getClientes():
    headers = getToken()
    headers["Content-Type"] = "application/json"
    page = 0
    has_more = True
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}
    url = _get_env_or_setting("SANKHYA_URL_GENERIC")
    ultima_alteracao = _iso_to_criteria_date_start_of_day(_max_dtalter_cliente_iso())
    if ultima_alteracao:
        print(f"Filtro DTALTER formatado: {ultima_alteracao}")
    while has_more:
        data_set = {
            "rootEntity": "Parceiro",
            "includePresentationFields": "S",
            "offsetPage": str(page),
            "entity": {
                "fieldset": {
                    "list": (
                        "CODPARC,TIPPESSOA,CGC_CPF,IDENTINSCESTAD,NOMEPARC,RAZAOSOCIAL,EMAIL,"
                        "TELEFONE,LIMCREDMENSAL,GRUPOAUTOR,LATITUDE,LONGITUDE,CODEND,NUMEND,"
                        "COMPLEMENTO,CODBAI,CODCID,CEP,CODTAB,DTALTER"
                    )
                }
            },
        }
        if ultima_alteracao:
            data_set["criteria"] = {
                "expression": {"$": "DTALTER >= ? "},
                "parameter": [{"type": "D", "$": f"{ultima_alteracao}"}],
            }

        body = {
            "serviceName": "CRUDServiceProvider.loadRecords",
            "requestBody": {
                "dataSet": data_set
            },
        }
        resp, headers = _request_with_token_retry("POST", url, headers, json=body, timeout=360)
        resp.raise_for_status()
        data = resp.json()
        entities = (data.get("responseBody") or data).get("entities") or {}
        has_more = str(entities.get("hasMoreResult", "false")).lower() in {"1", "true", "s"}
        records = entities.get("entity") or []
        if isinstance(records, dict):
            records = [records]

        for row in records:
            codparc = _to_int((row.get("f0") or {}).get("$") if isinstance(row.get("f0"), dict) else row.get("f0"))
            if codparc is None:
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
            dtalter = _to_datetime_iso_seconds(
                (row.get("f19") or {}).get("$") if isinstance(row.get("f19"), dict) else row.get("f19")
            )
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
                "dtalter": _to_str(dtalter, 50),
            }
            defaults = {k: v for k, v in defaults.items() if v is not None}
            _, created = Cliente.objects.update_or_create(codigo_cliente=codparc, defaults=defaults)
            out["total_processados"] += 1
            if created:
                out["total_inseridos"] += 1
            else:
                out["total_atualizados"] += 1
        page += 1
    return out


def getPrecos():
    base_url = _get_env_or_setting("SANKHYA_URL_PRECOS").strip()
    headers = getToken()
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}

    codtabs = (
        Cliente.objects.exclude(codtab__isnull=True)
        .exclude(codtab=0)
        .order_by()
        .values_list("codtab", flat=True)
        .distinct()
    )
    codtabs = list(codtabs)
    print(f"Processando {len(codtabs)} tabelas de preço")
    for codtab in codtabs:
        print(f"Processando tabela {codtab}")
        if "{codigo_tabela}" in base_url:
            url = base_url.format(codigo_tabela=codtab).rstrip("/")
        else:
            clean_base = base_url.rstrip("/")
            url = clean_base if clean_base.endswith(f"/{codtab}") else f"{clean_base}/{codtab}"


        pagina = 1
        tem_mais = True
        while tem_mais:
            print(f"URL: {url} - Página {pagina}")
            resp, headers = _request_with_token_retry("GET", url, headers, params={"pagina": pagina}, timeout=360)
            if resp.status_code == 404:
                resp, headers = _request_with_token_retry("GET", url, headers, params={"page": pagina}, timeout=360)
            if _is_no_records_not_found(resp):
                break
            resp.raise_for_status()
            data = resp.json()

            for v in data.get("produtos", []):
                codigo_produto = _to_int(v.get("codigoProduto"))
                codigo_tabela = _to_int(codtab)
                if codigo_produto is None or codigo_tabela is None:
                    continue
                _, created = Preco.objects.update_or_create(
                    codigo_produto=codigo_produto,
                    codigo_local_estoque=_to_int(v.get("codigoLocalEstoque")) or 0,
                    codigo_tabela=codigo_tabela,
                    defaults={
                        "valor": _to_decimal(v.get("valor")) or Decimal("0"),
                        "controle": _to_str(v.get("controle"), 50),
                        "unidade": _to_str(v.get("unidade"), 10),
                    },
                )
                out["total_processados"] += 1
                if created:
                    out["total_inseridos"] += 1
                else:
                    out["total_atualizados"] += 1

            tem_mais_raw = data.get("temMaisRegistros", False)
            if isinstance(tem_mais_raw, str):
                tem_mais = tem_mais_raw.strip().lower() == "true"
            else:
                tem_mais = bool(tem_mais_raw)
            pagina += 1

    return out


def getProdutos():
    def cb(v):
        codigo = _to_int(v.get("codigoProduto"))
        if not codigo:
            return False, False
        defaults = {"nome": _to_str(v.get("nome"), 200), "referencia": _to_str(v.get("referencia"), 100), "codigo_grupo_produto": _to_int(v.get("codigoGrupoProduto")), "ativo": bool(v.get("ativo", True))}
        _, created = Produto.objects.update_or_create(codigo_produto=codigo, defaults=defaults)
        return created, True

    return _sync_paginated(_get_env_or_setting("SANKHYA_URL_PRODUTOS"), "produtos", cb)


def getGruposProduto():
    def cb(v):
        codigo = _to_int(v.get("codigoGrupoProduto"))
        nome = _to_str(v.get("nome"), 200)
        if not codigo or not nome:
            return False, False
        defaults = {"nome": nome, "codigo_grupo_produto_pai": _to_int(v.get("codigoGrupoProdutoPai")), "ativo": bool(v.get("ativo", True))}
        _, created = GrupoProduto.objects.update_or_create(codigo_grupo_produto=codigo, defaults=defaults)
        return created, True

    return _sync_paginated(_get_env_or_setting("SANKHYA_URL_GRUPOS_PRODUTO"), "grupos", cb)


def getPedidosJson():
    page = 0
    has_more = True
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}
    headers = getToken()

    # Watermark incremental: maior data/hora parseada (evita Max em string e perda de registros).
    modified_since = _max_pedido_data_hora_alteracao_for_modified_since()

    while has_more:
        params = {"page": page}
        if modified_since:
            params["modifiedSince"] = modified_since

        resp, headers = _request_with_token_retry(
            "GET", _get_env_or_setting("SANKHYA_URL_PEDIDOS"), headers, params=params, timeout=360
        )
        if _is_no_records_not_found(resp):
            break
        resp.raise_for_status()
        data = resp.json()
        if _is_no_records_payload(data):
            break
        if not isinstance(data, dict):
            raise RuntimeError(f"Resposta inesperada da API de pedidos: {type(data).__name__}")
        pagination = data.get("pagination")
        if isinstance(pagination, dict):
            has_more = _pagination_has_more(pagination)
        else:
            has_more = False
        lista = _pedidos_list_from_api_payload(data)
        for p in lista:
            if not isinstance(p, dict):
                continue
            codigo_nota = _codigo_nota_from_pedido_payload(p)
            if not codigo_nota:
                continue
            cliente = p.get("cliente") or {}
            endereco = cliente.get("endereco") or {}
            defaults = {
                "codigo_empresa": _to_int(p.get("codigoEmpresa")),
                "nome_empresa": _to_str(p.get("nomeEmpresa"), 200),
                "codigo_cliente": _to_int(p.get("codigoCliente")),
                "cliente_tipo": _to_str(cliente.get("tipo"), 10),
                "cliente_cnpj_cpf": _to_str(cliente.get("cnpjCpf"), 20),
                "cliente_ie_rg": _to_str(cliente.get("ieRg"), 20),
                "cliente_nome": _to_str(cliente.get("nome"), 200),
                "cliente_razao": _to_str(cliente.get("razao"), 200),
                "cliente_email": _to_str(cliente.get("email"), 100),
                "cliente_telefone": _to_str(cliente.get("telefoneNumero"), 20),
                "endereco_logradouro": _to_str(endereco.get("logradouro"), 200),
                "endereco_numero": _to_str(endereco.get("numero"), 20),
                "endereco_complemento": _to_str(endereco.get("complemento"), 100),
                "endereco_bairro": _to_str(endereco.get("bairro"), 100),
                "endereco_cidade": _to_str(endereco.get("cidade"), 100),
                "endereco_codigo_ibge": _to_str(endereco.get("codigoIbge"), 20),
                "endereco_uf": _to_str(endereco.get("uf"), 2),
                "endereco_cep": _to_str(endereco.get("cep"), 10),
                "entrega": bool(endereco.get("entrega", False)),
                "confirmada": bool(p.get("confirmada", False)),
                "pendente": bool(p.get("pendente", True)),
                "data_negociacao": _to_date(p.get("dataNegociacao")),
                "data_hora_alteracao": _to_datetime_iso_seconds(p.get("dataHoraAlteracao")),
                "numero_nota": _to_int(p.get("numeroNota")),
                "serie_nota": _to_str(p.get("serieNota"), 10),
                "codigo_tipo_negociacao": _to_int(p.get("codigoTipoNegociacao")),
                "nome_tipo_negociacao": _to_str(p.get("nomeTipoNegociacao"), 100),
                "codigo_tipo_operacao": _to_int(p.get("codigoTipoOperacao")),
                "nome_tipo_operacao": _to_str(p.get("nomeTipoOperacao"), 100),
                "codigo_natureza": _to_int(p.get("codigoNatureza")),
                "codigo_centro_resultado": _to_int(p.get("codigoCentroResultado")),
                "nome_centro_resultado": _to_str(p.get("nomeCentroResultado"), 200),
                "codigo_projeto": _to_int(p.get("codigoProjeto")),
                "nome_projeto": _to_str(p.get("nomeProjeto"), 200),
                "codigo_contrato": _to_int(p.get("codigoContrato")),
                "codigo_vendedor": _to_int(p.get("codigoVendedor")),
                "nome_vendedor": _to_str(p.get("nomeVendedor"), 200),
                "codigo_contato": _to_int(p.get("codigoContato")),
                "nome_contato": _to_str(p.get("nomeContato"), 200),
                "codigo_moeda": _to_int(p.get("codigoMoeda")),
                "nome_moeda": _to_str(p.get("nomeMoeda"), 50),
                "valor_moeda": _to_decimal(p.get("valorMoeda")),
                "valor_nota": _to_decimal(p.get("valorNota")),
                "desconto_total": _to_decimal(p.get("descontoTotal")),
                "valor_seguro": _to_decimal(p.get("valorSeguro")),
                "valor_destaque": _to_decimal(p.get("valorDestaque")),
                "valor_vendor": _to_decimal(p.get("valorVendor")),
                "valor_juro": _to_decimal(p.get("valorJuro")),
                "valor_outros": _to_decimal(p.get("valorOutros")),
                "valor_embalagem": _to_decimal(p.get("valorEmbalagem")),
                "valor_frete": _to_decimal(p.get("valorFrete")),
                "vencimento_frete": _to_str(p.get("vencimentoFrete"), 50),
                "codigo_ordem_carga": _to_int(p.get("codigoOrdemCarga")),
                "codigo_veiculo": _to_int(p.get("codigoVeiculo")),
                "placa_veiculo": _to_str(p.get("placaVeiculo"), 10),
                "codigo_motorista": _to_int(p.get("codigoMotorista")),
                "nome_motorista": _to_str(p.get("nomeMotorista"), 200),
                "codigo_transportadora": _to_int(p.get("codigoTransportadora")),
                "nome_transportadora": _to_str(p.get("nomeTransportadora"), 200),
                "codigo_remetente": _to_int(p.get("codigoRemetente")),
                "nome_remetente": _to_str(p.get("nomeRemetente"), 200),
                "codigo_destinatario": _to_int(p.get("codigoDestinatario")),
                "nome_destinatario": _to_str(p.get("nomeDestinatario"), 200),
                "quantidade_volumes": _to_int(p.get("quantidadeVolumes")),
                "numeracao_volumes": _to_str(p.get("numeracaoVolumes"), 200),
                "lacres": _to_str(p.get("lacres"), 200),
                "peso_bruto": _to_decimal(p.get("pesoBruto")),
                "cif_fob": _to_str(p.get("cifFob"), 1),
                "tipo_frete": _to_str(p.get("tipoFrete"), 1),
                "base_icms_frete": _to_decimal(p.get("baseICMSFrete")),
                "icms_frete": _to_decimal(p.get("icmsFrete")),
                "status_wms": _to_str(p.get("statusWMS"), 10),
                "situacao_wms": _to_int(p.get("situacaoWMS")),
                "status_conferencia": _to_int(p.get("statusConferencia")),
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
                    unidade=_to_str(item.get("unidade"), 10),
                    valor_unitario=_to_decimal(item.get("valorUnitario")),
                    valor_total=_to_decimal(item.get("valorTotal")),
                    cfop=_to_int(item.get("cfop")),
                    ncm=_to_str(item.get("ncm"), 20),
                    cst=_to_str(item.get("cst"), 10),
                    valor_desconto=_to_decimal(item.get("valorDesconto")),
                    valor_icms=_to_decimal(item.get("valorICMS")),
                    valor_ipi=_to_decimal(item.get("valorIPI")),
                )
            out["total_processados"] += 1
            if created:
                out["total_inseridos"] += 1
            else:
                out["total_atualizados"] += 1
        page += 1
    return out


def getContatos():
    headers = getToken()
    headers["Content-Type"] = "application/json"
    page = 0
    has_more = True
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}
    url = _get_env_or_setting("SANKHYA_URL_GENERIC")
    ultima_alteracao = _iso_to_criteria_date_start_of_day(_max_dtalter_contato_iso())
    usar_filtro = bool(ultima_alteracao)
    while has_more:
        data_set = {
            "rootEntity": "Contato",
            "includePresentationFields": "S",
            "offsetPage": str(page),
            "entity": {
                "fieldset": {
                    "list": "CODPARC,CODCONTATO,NOMECONTATO,APELIDO,CODEND,NUMEND,COMPLEMENTO,CODBAI,CODCID,CEP,TELEFONE,EMAIL,CELULAR,LATITUDE,LONGITUDE,DHALTER"
                }
            },
        }
        if usar_filtro and ultima_alteracao:
            data_set["criteria"] = {
                "expression": {"$": "DHALTER >= ? "},
                "parameter": [{"type": "D", "$": f"{ultima_alteracao}"}],
            }

        body = {
            "serviceName": "CRUDServiceProvider.loadRecords",
            "requestBody": {"dataSet": data_set},
        }
        resp, headers = _request_with_token_retry("POST", url, headers, json=body, timeout=360)
        resp.raise_for_status()
        data = resp.json()
        entities = (data.get("responseBody") or data).get("entities") or {}
        raw_records = entities.get("entity") or entities.get("record") or []
        if isinstance(raw_records, dict):
            raw_records = [raw_records]

        # Em Contato, a posição dos f0..fN pode variar; monta mapeamento
        # pelo metadata.fields para evitar desalinhamento.
        metadata = entities.get("metadata") or {}
        fields_meta = metadata.get("fields") or {}
        field_list = fields_meta.get("field") or []
        if isinstance(field_list, dict):
            field_list = [field_list]

        idx_to_name = {}
        for i, field in enumerate(field_list):
            if isinstance(field, dict) and field.get("name"):
                idx_to_name[f"f{i}"] = str(field.get("name")).upper()
        if not idx_to_name:
            ordered_fields = [
                "CODPARC",
                "CODCONTATO",
                "NOMECONTATO",
                "APELIDO",
                "CODEND",
                "NUMEND",
                "COMPLEMENTO",
                "CODBAI",
                "CODCID",
                "CEP",
                "TELEFONE",
                "EMAIL",
                "CELULAR",
                "LATITUDE",
                "LONGITUDE",
                "DTALTER",
            ]
            idx_to_name = {f"f{i}": name for i, name in enumerate(ordered_fields)}

        def _cell_val(cell):
            if cell == {}:
                return None
            if isinstance(cell, dict) and "$" in cell:
                val = cell.get("$")
                return None if val == {} else val
            return cell

        def _row_to_record(row):
            if not isinstance(row, dict):
                return {}
            # fallback para payloads que já vêm nomeados
            if any(k and not str(k).startswith("f") for k in row.keys()):
                return {str(k).upper(): _cell_val(v) for k, v in row.items()}
            out = {}
            for fk, name in idx_to_name.items():
                if fk in row:
                    out[name] = _cell_val(row.get(fk))
            return out

        records = [_row_to_record(r) for r in raw_records]
        print(f"Contatos page={page} raw_records={len(raw_records)} mapped_records={len(records)}")

        # Se a primeira página com filtro vier vazia, faz fallback automático
        # para carga completa (sem filtro), evitando falso negativo por critério.
        if page == 0 and usar_filtro and not records:
            usar_filtro = False
            has_more = True
            print("Contatos: fallback para carga completa (sem filtro DTALTER).")
            continue

        has_more = str(entities.get("hasMoreResult", "false")).lower() in {"1", "true", "s"}
        ignorados_sem_chave = 0
        upserts_pagina = 0
        for row in records:
            codparc = _to_int(row.get("CODPARC"))
            codcontato = _to_int(row.get("CODCONTATO"))
            if codparc is None or codcontato is None:
                ignorados_sem_chave += 1
                continue
            defaults = {
                "nomecontato": _to_str(row.get("NOMECONTATO"), 200),
                "apelido": _to_str(row.get("APELIDO"), 100),
                "codend": _to_int(row.get("CODEND")),
                "numend": _to_str(row.get("NUMEND"), 20),
                "complemento": _to_str(row.get("COMPLEMENTO"), 100),
                "codbai": _to_int(row.get("CODBAI")),
                "codcid": _to_int(row.get("CODCID")),
                "cep": _to_str(row.get("CEP"), 10),
                "telefone": _to_str(row.get("TELEFONE"), 20),
                "email": _to_str(row.get("EMAIL"), 100),
                "celular": _to_str(row.get("CELULAR"), 20),
                "latitude": _to_str(row.get("LATITUDE"), 50),
                "longitude": _to_str(row.get("LONGITUDE"), 50),
                "dtalter": _to_datetime_iso_seconds(row.get("DHALTER")),
            }
            _, created = Contato.objects.update_or_create(codparc=codparc, codcontato=codcontato, defaults=defaults)
            upserts_pagina += 1
            out["total_processados"] += 1
            if created:
                out["total_inseridos"] += 1
            else:
                out["total_atualizados"] += 1
        print(
            f"Contatos page={page} upserts={upserts_pagina} "
            f"ignorados_sem_chave={ignorados_sem_chave} has_more={has_more}"
        )
        page += 1
    return out


def getFuncionarios():
    headers = getToken()
    page = 0
    has_more = True
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}
    while has_more:
        resp, headers = _request_with_token_retry(
            "GET", _get_env_or_setting("SANKHYA_URL_FUNCIONARIOS"), headers, params={"page": page}, timeout=360
        )
        if _is_no_records_not_found(resp):
            break
        resp.raise_for_status()
        data = resp.json()
        bloco = data[0] if isinstance(data, list) and data else data
        codigos = bloco.get("codigos", [])
        has_more = str((bloco.get("pagination") or {}).get("hasMore", "false")).lower() == "true"
        for resumo in codigos:
            codigo_empresa = _to_int(resumo.get("codigoEmpresa"))
            codigo_funcionario = _to_int(resumo.get("codigoFuncionario"))
            if codigo_empresa is None or codigo_funcionario is None:
                continue
            detalhe_url_template = _get_env_or_setting("SANKHYA_URL_FUNCIONARIO_DETALHE")
            det, headers = _request_with_token_retry(
                "GET",
                detalhe_url_template.format(
                    codigo_funcionario=codigo_funcionario,
                    codigo_empresa=codigo_empresa,
                ),
                headers,
                timeout=120,
            )
            # Não usar det.ok: em requests, .ok chama raise_for_status() e dispara exceção em 4xx/5xx.
            if det.status_code >= 400:
                continue
            try:
                detalhe = det.json()
            except ValueError:
                continue
            defaults = {"cpf": _to_str(detalhe.get("cpf"), 14), "nome": _to_str(detalhe.get("nome"), 200), "matricula": _to_int(detalhe.get("matricula"))}
            _, created = Funcionario.objects.update_or_create(
                empresa_codigo=codigo_empresa,
                codigo_funcionario=codigo_funcionario,
                defaults=defaults,
            )
            out["total_processados"] += 1
            if created:
                out["total_inseridos"] += 1
            else:
                out["total_atualizados"] += 1
        page += 1
    return out


INTEGRACOES = {
    "veiculos": {"nome": "Veículos", "model": Veiculo, "runner": getVeiculos},
    "empresas": {"nome": "Empresas", "model": Empresa, "runner": getEmpresas},
    "cidades": {"nome": "Cidades", "model": Cidade, "runner": getCidadeLegado},
    "logradouros": {"nome": "Logradouros", "model": Logradouro, "runner": getLogradouros},
    "bairros": {"nome": "Bairros", "model": Bairro, "runner": getBairros},
    "clientes": {"nome": "Clientes", "model": Cliente, "runner": getClientes},
    "precos": {"nome": "Preços", "model": Preco, "runner": getPrecos},
    "produtos": {"nome": "Produtos", "model": Produto, "runner": getProdutos},
    "grupos_produto": {"nome": "Grupos de Produto", "model": GrupoProduto, "runner": getGruposProduto},
    "pedidos": {"nome": "Pedidos", "model": Pedido, "runner": getPedidosJson},
    "contatos": {"nome": "Contatos", "model": Contato, "runner": getContatos},
    "funcionarios": {"nome": "Funcionários", "model": Funcionario, "runner": getFuncionarios},
}


def _status_integracoes():
    itens = []
    for chave, item in INTEGRACOES.items():
        model = item["model"]
        ultima_atualizacao = model.objects.aggregate(ultima=Max("updated_at")).get("ultima")
        itens.append(
            {
                "chave": chave,
                "nome": item["nome"],
                "ultima_atualizacao": ultima_atualizacao,
                "total_registros": model.objects.count(),
                "permite_execucao": True,
            }
        )
    itens.append(
        {
            "chave": "itens_pedido",
            "nome": "Itens do Pedido",
            "ultima_atualizacao": ItemPedido.objects.aggregate(ultima=Max("updated_at")).get("ultima"),
            "total_registros": ItemPedido.objects.count(),
            "permite_execucao": False,
            "observacao": "Atualizada junto com a integração de Pedidos.",
        }
    )
    return itens


@login_required
@requer_acesso_bi
def gestao_integracoes(request):
    denied = _require_admin_integracoes(request)
    if denied:
        return denied
    return render(
        request,
        "api_sankhya/gestao_integracoes.html",
        {"integracoes": _status_integracoes()},
    )


@login_required
@requer_acesso_bi
@require_GET
def integracao_task_status(request, task_id: str):
    """JSON para polling: tarefa pendente na fila/worker ou finalizada (django_q.Task)."""
    denied = _require_admin_integracoes(request)
    if denied:
        return denied
    t = Task.objects.filter(id=task_id).first()
    if not t:
        return JsonResponse({"status": "pending"})
    payload = _json_safe(t.result) if t.result is not None else None
    return JsonResponse(
        {
            "status": "done",
            "success": t.success,
            "result": payload,
        }
    )


@login_required
@requer_acesso_bi
@require_POST
def atualizar_integracao(request, chave: str):
    denied = _require_admin_integracoes(request)
    if denied:
        return denied
    if chave not in INTEGRACOES:
        if _wants_json(request):
            return JsonResponse({"error": "Integração inválida."}, status=400)
        messages.error(request, "Integração inválida.")
        return redirect("api_sankhya_gestao_integracoes")
    integracao = INTEGRACOES[chave]
    nome = integracao["nome"]
    q_sync = getattr(settings, "Q_CLUSTER", {}).get("sync", False)
    try:
        if q_sync:
            resultado = run_integracao_sankhya(chave)
            if resultado.get("erro"):
                if _wants_json(request):
                    return JsonResponse(
                        {"completed": True, "sync": True, "success": False, "nome": nome, "error": resultado.get("erro")},
                        status=400,
                    )
                messages.error(request, f"Erro ao atualizar {nome}: {resultado.get('erro')}")
            else:
                if _wants_json(request):
                    return JsonResponse(
                        {
                            "completed": True,
                            "sync": True,
                            "success": True,
                            "nome": nome,
                            "resultado": _json_safe(resultado),
                        }
                    )
                messages.success(
                    request,
                    (
                        f"{nome} atualizado com sucesso. "
                        f"Processados: {resultado.get('total_processados', resultado.get('total_registros', '-'))} | "
                        f"Inseridos: {resultado.get('total_inseridos', '-')} | "
                        f"Atualizados: {resultado.get('total_atualizados', '-')}"
                    ),
                )
        else:
            task_id = async_task(
                "api_sankhya.tasks.run_integracao_sankhya",
                chave,
                task_name=f"Sankhya: {nome}",
            )
            if _wants_json(request):
                return JsonResponse(
                    {
                        "completed": False,
                        "sync": False,
                        "task_id": task_id,
                        "chave": chave,
                        "nome": nome,
                    }
                )
            messages.success(
                request,
                f"{nome}: sincronização enfileirada e executada em segundo plano pelo worker "
                "(python manage.py qcluster). Atualize esta página em alguns minutos para ver os totais.",
            )
    except Exception as exc:
        if _wants_json(request):
            return JsonResponse({"error": str(exc), "nome": nome}, status=500)
        messages.error(request, f"Erro ao atualizar {nome}: {exc}")
    return redirect("api_sankhya_gestao_integracoes")


@login_required
@requer_acesso_bi
@require_POST
def atualizar_todas_integracoes(request):
    denied = _require_admin_integracoes(request)
    if denied:
        return denied
    q_sync = getattr(settings, "Q_CLUSTER", {}).get("sync", False)
    try:
        if q_sync:
            resultado = run_todas_integracoes_sankhya()
            erros = resultado.get("erros") or []
            if erros:
                if _wants_json(request):
                    return JsonResponse(
                        {
                            "completed": True,
                            "sync": True,
                            "success": False,
                            "erros": erros,
                        },
                        status=400,
                    )
                messages.warning(
                    request,
                    "Algumas integrações falharam: " + " | ".join(erros[:5]),
                )
            else:
                if _wants_json(request):
                    return JsonResponse(
                        {"completed": True, "sync": True, "success": True, "resultado": _json_safe(resultado)}
                    )
                messages.success(
                    request,
                    "Atualização completa concluída com sucesso.",
                )
        else:
            task_id = async_task(
                "api_sankhya.tasks.run_todas_integracoes_sankhya",
                task_name="Sankhya: todas as integrações",
            )
            if _wants_json(request):
                return JsonResponse(
                    {
                        "completed": False,
                        "sync": False,
                        "task_id": task_id,
                        "chave": "__todas__",
                        "nome": "Todas as integrações",
                    }
                )
            messages.success(
                request,
                "Todas as integrações foram enfileiradas; o worker processará em sequência. "
                "Confira o serviço qcluster (Railway) ou use DJANGO_Q_SYNC=1 só para testes locais.",
            )
    except Exception as exc:
        if _wants_json(request):
            return JsonResponse({"error": str(exc)}, status=500)
        messages.error(request, f"Erro ao enfileirar integrações: {exc}")
    return redirect("api_sankhya_gestao_integracoes")
