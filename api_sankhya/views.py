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

from .models import (
    Bairro,
    Cidade,
    Cliente,
    Contato,
    Empresa,
    Funcionario,
    GrupoProduto,
    ItemNotaFiscal,
    ItemPedido,
    Logradouro,
    NotaFiscal,
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


NOTA_FISCAL_DTALTER_BASE = datetime(2026, 5, 1, 0, 0, 0)


def _max_dtalter_nota_fiscal_iso():
    """
    Maior DTALTER persistido; se a tabela não tiver nenhum, usa 01/05/2026 como base.
    """
    maior_data = None
    for valor in NotaFiscal.objects.exclude(dtalter__isnull=True).exclude(dtalter="").values_list("dtalter", flat=True):
        dt = _parse_datetime_flexible(valor)
        if dt and (maior_data is None or dt > maior_data):
            maior_data = dt
    if maior_data is None:
        return NOTA_FISCAL_DTALTER_BASE.strftime("%Y-%m-%dT%H:%M:%S")
    return maior_data.strftime("%Y-%m-%dT%H:%M:%S")


def _crud_cell_val(cell):
    if cell == {}:
        return None
    if isinstance(cell, dict) and "$" in cell:
        val = cell.get("$")
        return None if val == {} else val
    return cell


def _crud_normalize_field_name(name: str) -> str:
    s = str(name).strip().upper()
    if "." in s:
        s = s.rsplit(".", 1)[-1]
    for prefix in ("CABECALHONOTA_", "ITEMNOTA_", "ITEM_NOTA_"):
        if s.startswith(prefix):
            return s[len(prefix) :]
    return s


def _crud_idx_to_name_from_entities(entities: dict, fallback_fields: list[str]) -> dict[str, str]:
    metadata = entities.get("metadata") or {}
    fields_meta = metadata.get("fields") or {}
    field_list = fields_meta.get("field") or []
    if isinstance(field_list, dict):
        field_list = [field_list]
    idx_to_name: dict[str, str] = {}
    for i, field in enumerate(field_list):
        if isinstance(field, dict) and field.get("name"):
            idx_to_name[f"f{i}"] = _crud_normalize_field_name(field.get("name"))
    if not idx_to_name:
        idx_to_name = {f"f{i}": name for i, name in enumerate(fallback_fields)}
    return idx_to_name


def _crud_row_to_record(row: Any, idx_to_name: dict[str, str]) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    if any(str(k).startswith("f") for k in row.keys()):
        out: dict[str, Any] = {}
        for fk, name in idx_to_name.items():
            if fk in row:
                val = _crud_cell_val(row.get(fk))
                if val is not None and val != "":
                    out[name] = val
        return out
    return {
        str(k).upper(): _crud_cell_val(v)
        for k, v in row.items()
        if not str(k).startswith("_")
    }


def _crud_row_to_flat_record(row: Any, idx_to_name: dict[str, str]) -> dict[str, Any]:
    """
    Achata linha CRUD com tryJoinedFields (f0..fN ou nós aninhados CabecalhoNota).
    Ignora metadados auxiliares (_rmd, etc.) e prioriza mapeamento fN -> campo.
    """
    if not isinstance(row, dict):
        return {}
    if any(str(k).startswith("f") for k in row.keys()):
        return _crud_row_to_record(row, idx_to_name)
    out: dict[str, Any] = {}

    def absorb(data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            return
        if any(str(k).startswith("f") for k in data.keys()):
            for name, val in _crud_row_to_record(data, idx_to_name).items():
                if val is not None and val != "":
                    out[name] = val
            return
        for k, v in data.items():
            ku = str(k).upper()
            if ku.startswith("_"):
                continue
            if ku in {"CABECALHONOTA", "CABECALHO_NOTA"} and isinstance(v, dict):
                absorb(v)
                continue
            if isinstance(v, dict) and "$" not in v:
                absorb(v)
                continue
            name = _crud_normalize_field_name(ku)
            val = _crud_cell_val(v)
            if val is not None and val != "":
                out[name] = val

    absorb(row)
    return out


def _build_notas_fiscais_load_records_body(page: int, criteria_date: str | None = None) -> dict[str, Any]:
    """Payload CRUD ItemNota + CabecalhoNota (estrutura exigida pelo gateway Sankhya)."""
    data_set: dict[str, Any] = {
        "rootEntity": "ItemNota",
        "includePresentationFields": "N",
        "tryJoinedFields": "true",
        "offsetPage": str(page),
        "entity": [
            {
                "path": "",
                "fieldset": {
                    "list": "NUNOTA,SEQUENCIA,CODPROD,QTDNEG,VLRUNIT,VLRTOT,VLRDESC,USOPROD,STATUSNOTA",
                },
            },
            {
                "path": "CabecalhoNota",
                "fieldset": {
                    "list": (
                        "NUNOTA,CODEMP,NUMNOTA,DTENTSAI,DTNEG,CODTIPOPER,CODPARC,CODVEND,TIPMOV,"
                        "PENDENTE,STATUSNFE,STATUSNOTA,APROVADO,DTALTER"
                    ),
                },
            },
        ],
    }
    if criteria_date:
        data_set["criteria"] = {
            "expression": {"$": "DTALTER >= ?"},
            "parameter": [{"type": "D", "$": criteria_date}],
        }
    return {
        "serviceName": "CRUDServiceProvider.loadRecords",
        "requestBody": {
            "dataSet": data_set,
        },
    }


def _crud_record_get(row: dict[str, Any], *keys: str):
    for key in keys:
        name = key.upper()
        candidates = (
            name,
            f"CABECALHONOTA.{name}",
            f"CABECALHONOTA_{name}",
            f"ITEMNOTA.{name}",
            f"ITEMNOTA_{name}",
        )
        for candidate in candidates:
            if candidate in row and row[candidate] not in (None, ""):
                return row[candidate]
    return None


def _crud_item_field_value(row_raw: dict, idx_to_name: dict[str, str], field: str):
    """Valor do item (ItemNota), evitando colisão com campos do CabecalhoNota no join."""
    field_u = field.upper()
    item_val = None
    any_val = None
    for fk, name in idx_to_name.items():
        if fk not in row_raw:
            continue
        nu = name.upper()
        if field_u not in nu and nu != field_u:
            continue
        val = _crud_cell_val(row_raw.get(fk))
        if val in (None, ""):
            continue
        any_val = val
        if "ITEMNOTA" in nu:
            return val
        if not nu.startswith("CABECALHONOTA"):
            item_val = val
    return item_val if item_val is not None else any_val


def _iso_to_criteria_date_start_of_day(value):
    dt = _parse_datetime_flexible(value)
    if dt is None:
        return None
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def _user_input_to_criteria_date(value: str | None) -> str | None:
    """Converte entrada do formulário (date ou datetime-local) para critério Sankhya."""
    if not value:
        return None
    valor = value.strip()
    if not valor:
        return None
    if "T" in valor:
        try:
            dt = datetime.fromisoformat(valor)
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        except ValueError:
            pass
    if len(valor) == 10 and valor[4] == "-" and valor[7] == "-":
        try:
            y, m, d = (int(valor[0:4]), int(valor[5:7]), int(valor[8:10]))
            return datetime(y, m, d).strftime("%d/%m/%Y %H:%M:%S")
        except (TypeError, ValueError):
            pass
    return _iso_to_criteria_date_start_of_day(valor)


def _clientes_sync_modal_context() -> dict[str, str | None]:
    iso = _max_dtalter_cliente_iso()
    criteria = _iso_to_criteria_date_start_of_day(iso) if iso else None
    dt = _parse_datetime_flexible(iso) if iso else None
    return {
        "ultima_dtalter_iso": iso,
        "ultima_dtalter_exibicao": dt.strftime("%d/%m/%Y %H:%M:%S") if dt else None,
        "dtalter_criteria_padrao": criteria,
        "dtalter_input_padrao": dt.strftime("%Y-%m-%dT%H:%M") if dt else "",
    }


def _resolve_dtalter_desde_clientes(dtalter_desde: str | None) -> str | None:
    """
    None -> usa maior DTALTER local (incremental padrão).
    '__full__' -> sem filtro (carga completa).
    Outro valor -> data informada pelo usuário.
    """
    if dtalter_desde is None:
        return None
    valor = str(dtalter_desde).strip()
    if not valor or valor == "__default__":
        return None
    if valor == "__full__":
        return "__full__"
    return valor


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


def getClientes(dtalter_desde=None):
    headers = getToken()
    headers["Content-Type"] = "application/json"
    page = 0
    has_more = True
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}
    url = _get_env_or_setting("SANKHYA_URL_GENERIC")

    modo = _resolve_dtalter_desde_clientes(dtalter_desde)
    if modo == "__full__":
        ultima_alteracao = None
        print("Sincronização de clientes: sem filtro DTALTER (carga completa).")
    elif modo:
        ultima_alteracao = _user_input_to_criteria_date(str(modo))
        if ultima_alteracao:
            print(f"Filtro DTALTER customizado: {ultima_alteracao}")
        else:
            ultima_alteracao = _iso_to_criteria_date_start_of_day(_max_dtalter_cliente_iso())
            print(f"Filtro DTALTER (fallback automático): {ultima_alteracao}")
    else:
        ultima_alteracao = _iso_to_criteria_date_start_of_day(_max_dtalter_cliente_iso())
        if ultima_alteracao:
            print(f"Filtro DTALTER incremental: {ultima_alteracao}")
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
                        "COMPLEMENTO,CODBAI,CODCID,CEP,CODTAB,CODVEND,DTALTER"
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
                (row.get("f20") or {}).get("$") if isinstance(row.get("f20"), dict) else row.get("f20")
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
                "codvend": _to_int((row.get("f19") or {}).get("$") if isinstance(row.get("f19"), dict) else row.get("f19")),
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


def getPrecos(codigo_tabela: int | None = None):
    base_url = _get_env_or_setting("SANKHYA_URL_PRECOS").strip()
    headers = getToken()
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}

    if codigo_tabela is None:
        codtabs = (
            Cliente.objects.exclude(codtab__isnull=True)
            .exclude(codtab=0)
            .order_by()
            .values_list("codtab", flat=True)
            .distinct()
        )
        codtabs = list(codtabs)
    else:
        codtabs = [codigo_tabela]
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
            codigo_empresa = _to_int(p.get("codigoEmpresa"))
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
            pedido, created = Pedido.objects.update_or_create(
                codigo_nota=codigo_nota,
                codigo_empresa=codigo_empresa,
                origem=Pedido.ORIGEM_SANKHYA,
                defaults=defaults,
            )
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


def getNotasFiscais():
    """
    Importa notas fiscais emitidas via CRUD ItemNota + CabecalhoNota (SANKHYA_URL_GENERIC).
    Carga incremental pelo maior DTALTER já persistido; sem DTALTER na base, filtra a partir de 01/05/2026.
    """
    headers = getToken()
    headers["Content-Type"] = "application/json"
    page = 0
    has_more = True
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}
    url = _get_env_or_setting("SANKHYA_URL_GENERIC")
    tem_dtalter_local = NotaFiscal.objects.exclude(dtalter__isnull=True).exclude(dtalter="").exists()
    ultima_alteracao = _iso_to_criteria_date_start_of_day(_max_dtalter_nota_fiscal_iso())
    usar_filtro = bool(ultima_alteracao)
    if ultima_alteracao:
        origem = "maior DTALTER local" if tem_dtalter_local else "base 01/05/2026 (sem DTALTER na tabela)"
        print(f"Notas fiscais — filtro DTALTER ({origem}): {ultima_alteracao}")

    fallback_fields = [
        "NUNOTA",
        "SEQUENCIA",
        "CODPROD",
        "QTDNEG",
        "VLRUNIT",
        "VLRTOT",
        "VLRDESC",
        "USOPROD",
        "STATUSNOTA",
        "CODEMP",
        "NUMNOTA",
        "DTENTSAI",
        "DTNEG",
        "CODTIPOPER",
        "CODPARC",
        "CODVEND",
        "TIPMOV",
        "PENDENTE",
        "STATUSNFE",
        "STATUSNOTA",
        "APROVADO",
        "DTALTER",
    ]

    while has_more:
        criteria = ultima_alteracao if usar_filtro else None
        body = _build_notas_fiscais_load_records_body(page, criteria_date=criteria)
        resp, headers = _request_with_token_retry("POST", url, headers, json=body, timeout=360)
        resp.raise_for_status()
        data = resp.json()
        response_body = data.get("responseBody") or data
        entities = response_body.get("entities") or {}
        raw_records = entities.get("entity") or entities.get("record") or entities.get("records") or []
        if isinstance(raw_records, dict):
            raw_records = [raw_records]

        idx_to_name = _crud_idx_to_name_from_entities(entities, fallback_fields)
        records = [_crud_row_to_flat_record(r, idx_to_name) for r in raw_records]
        raw_rows = list(raw_records)
        com_nunota = sum(1 for r in records if _to_int(_crud_record_get(r, "NUNOTA")))
        print(
            f"Notas fiscais page={page} api={len(raw_records)} mapeados={len(records)} "
            f"com_nunota={com_nunota} hasMore={entities.get('hasMoreResult')!r}"
        )
        if records and com_nunota == 0:
            print("AVISO: mapeamento sem NUNOTA — amostra:", json.dumps(records[0], ensure_ascii=False, default=str))

        if page == 0 and usar_filtro and not records and tem_dtalter_local:
            base_criteria = _iso_to_criteria_date_start_of_day(
                NOTA_FISCAL_DTALTER_BASE.strftime("%Y-%m-%dT%H:%M:%S")
            )
            if ultima_alteracao != base_criteria:
                ultima_alteracao = base_criteria
                has_more = True
                print("Notas fiscais: reconsulta a partir de 01/05/2026.")
                continue

        has_more = str(entities.get("hasMoreResult", "false")).lower() in {"1", "true", "s"}
        ignorados_sem_nunota = 0
        for i, row in enumerate(records):
            row_raw = raw_rows[i] if i < len(raw_rows) else {}
            nunota = _to_int(_crud_record_get(row, "NUNOTA"))
            if not nunota:
                ignorados_sem_nunota += 1
                if ignorados_sem_nunota <= 3:
                    print(f"Linha ignorada (sem NUNOTA): {json.dumps(row, ensure_ascii=False, default=str)}")
                continue
            sequencia = _to_int(_crud_record_get(row, "SEQUENCIA"))
            if sequencia is None:
                sequencia = 0
            dtalter = _to_datetime_iso_seconds(_crud_record_get(row, "DTALTER"))
            nota_defaults = {
                "codigo_empresa": _to_int(_crud_record_get(row, "CODEMP")),
                "numero_nota": _to_int(_crud_record_get(row, "NUMNOTA")),
                "data_entrada_saida": _to_date(_crud_record_get(row, "DTENTSAI")),
                "data_negociacao": _to_date(_crud_record_get(row, "DTNEG")),
                "codigo_tipo_operacao": _to_int(_crud_record_get(row, "CODTIPOPER")),
                "codigo_parceiro": _to_int(_crud_record_get(row, "CODPARC")),
                "codigo_vendedor": _to_int(_crud_record_get(row, "CODVEND")),
                "tipo_movimento": _to_str(_crud_record_get(row, "TIPMOV"), 10),
                "pendente": _to_str(_crud_record_get(row, "PENDENTE"), 5),
                "status_nfe": _to_str(_crud_record_get(row, "STATUSNFE"), 30),
                "status_nota": _to_str(_crud_record_get(row, "STATUSNOTA"), 30),
                "aprovado": _to_str(_crud_record_get(row, "APROVADO"), 5),
                "dtalter": _to_str(dtalter, 50),
            }
            nota_defaults = {k: v for k, v in nota_defaults.items() if v is not None}
            nota, nota_created = NotaFiscal.objects.update_or_create(nunota=nunota, defaults=nota_defaults)

            item_defaults = {
                "cod_produto": _to_int(_crud_record_get(row, "CODPROD")),
                "quantidade": _to_decimal(_crud_record_get(row, "QTDNEG")),
                "valor_unitario": _to_decimal(_crud_record_get(row, "VLRUNIT")),
                "valor_total": _to_decimal(_crud_record_get(row, "VLRTOT")),
                "valor_desconto": _to_decimal(_crud_record_get(row, "VLRDESC")),
                "uso_produto": _to_str(_crud_record_get(row, "USOPROD"), 10),
                "status_nota": _to_str(
                    _crud_item_field_value(row_raw, idx_to_name, "STATUSNOTA") or _crud_record_get(row, "STATUSNOTA"),
                    30,
                ),
            }
            item_defaults = {k: v for k, v in item_defaults.items() if v is not None}
            _, item_created = ItemNotaFiscal.objects.update_or_create(
                nota_fiscal=nota,
                sequencia=sequencia,
                defaults=item_defaults,
            )
            out["total_processados"] += 1
            if nota_created or item_created:
                out["total_inseridos"] += 1
            else:
                out["total_atualizados"] += 1
        print(
            f"Página {page} resumo: processados={out['total_processados']} "
            f"inseridos={out['total_inseridos']} atualizados={out['total_atualizados']} "
            f"ignorados_sem_nunota={ignorados_sem_nunota}"
        )
        page += 1
    print(f"\nNotas fiscais — fim: {out}")
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


def _funcionario_defaults_from_api_detalhe(detalhe: dict[str, Any], resumo: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Monta defaults para sankhya_funcionario a partir do JSON de detalhe da API
    /v1/pessoal/funcionarios/{cod}/empresa/{emp} (objetos aninhados).
    """
    resumo = resumo or {}
    dados_pessoais = detalhe.get("dadosPessoais") or {}
    endereco = detalhe.get("endereco") or {}
    bairro = endereco.get("bairro") or {}
    cidade = endereco.get("cidade") or {}
    dados_contratuais = detalhe.get("dadosContratuais") or {}
    emp = dados_contratuais.get("empresa") or {}
    depto = dados_contratuais.get("departamento") or {}
    cargo = dados_contratuais.get("cargo") or {}
    funcao = dados_contratuais.get("funcao") or {}
    local_trabalho = dados_contratuais.get("localTrabalho") or {}
    cidade_trab = dados_contratuais.get("cidadeTrabalho") or {}
    sindicato = dados_contratuais.get("sindicato") or {}
    carga_horaria = dados_contratuais.get("cargaHoraria") or {}
    afast = detalhe.get("afastamento") or {}
    causa_afast = afast.get("causaAfastamento") or {}
    tipo_rescisao = afast.get("tipoRescisao") or {}
    transf = detalhe.get("transferencia") or {}

    defaults: dict[str, Any] = {
        "cpf": _to_str(detalhe.get("cpf"), 14),
        "nome": _to_str(detalhe.get("nome"), 200),
        "matricula": _to_int(detalhe.get("matricula")),
        "nascimento": _to_str(dados_pessoais.get("nascimento"), 10),
        "sexo": _to_str(dados_pessoais.get("sexo"), 1),
        "celular": _to_str(dados_pessoais.get("celular"), 20),
        "email": _to_str(dados_pessoais.get("email"), 150),
        "nome_mae": _to_str(dados_pessoais.get("nomeMae") or detalhe.get("nomeMae"), 200),
        "endereco_cep": _to_str(endereco.get("cep"), 10),
        "endereco_codigo": _to_int(endereco.get("codigo")),
        "endereco_descricao": _to_str(endereco.get("descricao"), 200),
        "endereco_numero": _to_str(endereco.get("numero"), 20),
        "endereco_complemento": _to_str(endereco.get("complemento"), 100),
        "bairro_codigo": _to_int(bairro.get("codigo")),
        "bairro_descricao": _to_str(bairro.get("descricao"), 150),
        "cidade_codigo": _to_int(cidade.get("codigo")),
        "cidade_descricao": _to_str(cidade.get("descricao"), 150),
        "cidade_codigo_ibge": _to_int(cidade.get("codigoIBGE")),
        "empresa_cnpj": _to_str(emp.get("cnpj"), 20),
        "empresa_razao_social": _to_str(emp.get("razaoSocial"), 200),
        "data_admissao": _to_str(dados_contratuais.get("dataAdmissao"), 10),
        "codigo_categoria_esocial": _to_int(dados_contratuais.get("codigoCategoriaEsocial")),
        "situacao": _to_str(dados_contratuais.get("situacao") or resumo.get("situacao"), 2),
        "salario_base": _to_decimal(dados_contratuais.get("salarioBase")),
        "bolsa_estagio_ou_pro_labore": _to_decimal(dados_contratuais.get("bolsaEstagioOuProLabore")),
        "departamento_codigo": _to_int(depto.get("codigo")),
        "departamento_descricao": _to_str(depto.get("descricao"), 150),
        "cargo_codigo": _to_int(cargo.get("codigo")),
        "cargo_descricao": _to_str(cargo.get("descricao"), 150),
        "cargo_cbo": _to_int(cargo.get("cbo")),
        "funcao_codigo": _to_int(funcao.get("codigo")),
        "funcao_descricao": _to_str(funcao.get("descricao"), 150),
        "funcao_cbo": _to_int(funcao.get("cbo")),
        "local_trabalho_codigo": _to_int(local_trabalho.get("codigo")),
        "local_trabalho_descricao": _to_str(local_trabalho.get("descricao"), 150),
        "cidade_trabalho_codigo": _to_int(cidade_trab.get("codigo")),
        "cidade_trabalho_descricao": _to_str(cidade_trab.get("descricao"), 150),
        "cidade_trabalho_codigo_ibge": _to_int(cidade_trab.get("codigoIBGE")),
        "sindicato_codigo": _to_int(sindicato.get("codigo")),
        "sindicato_nome": _to_str(sindicato.get("nome"), 200),
        "sindicato_cnpj": _to_str(sindicato.get("cnpj"), 20),
        "carga_horaria_codigo": _to_int(carga_horaria.get("codigo")),
        "carga_horaria_descricao": _to_str(carga_horaria.get("descricao"), 150),
        "afast_motivo_desligamento_esocial": _to_str(afast.get("motivoDesligamentoEsocial"), 200),
        "afast_data_afastamento": _to_str(afast.get("dataAfastamento"), 10),
        "afast_causa_codigo": _to_int(causa_afast.get("codigo")),
        "afast_causa_descricao": _to_str(causa_afast.get("descricao"), 200),
        "afast_tipo_rescisao_codigo": _to_int(tipo_rescisao.get("codigo")),
        "afast_tipo_rescisao_descricao": _to_str(tipo_rescisao.get("descricao"), 200),
        "afast_data_desligamento": _to_str(afast.get("dataDesligamento"), 10),
        "afast_data_aviso_previo": _to_str(afast.get("dataAvisoPrevio"), 10),
        "transf_data_transferencia_destino": _to_str(transf.get("dataTransferenciaDestino"), 10),
        "transf_empresa_destino": _to_int(transf.get("empresaDestino")),
        "transf_cnpj_empresa_destino": _to_str(transf.get("cnpjEmpresaDestino"), 20),
        "transf_codigo_funcionario_destino": _to_int(transf.get("codigoFuncionarioDestino")),
        "transf_motivo_desligamento": _to_str(transf.get("motivoDesligamento"), 200),
        "transf_data_transferencia": _to_str(transf.get("dataTransferencia"), 10),
        "transf_empresa_origem": _to_int(transf.get("empresaOrigem")),
        "transf_codigo_funcionario_origem": _to_int(transf.get("codigoFuncionarioOrigem")),
        "transf_data_inicio_vinculo": _to_str(transf.get("dataInicioVinculo"), 10),
        "transf_cnpj_empresa_anterior": _to_str(transf.get("cnpjNaEmpresaAnterior"), 20),
        "transf_matricula_empresa_anterior": _to_int(transf.get("matriculaNaEmpresaAnterior")),
    }
    return {k: v for k, v in defaults.items() if v is not None}


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
        has_more = _pagination_has_more(bloco.get("pagination") if isinstance(bloco.get("pagination"), dict) else None)
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
            if not isinstance(detalhe, dict):
                continue
            defaults = _funcionario_defaults_from_api_detalhe(detalhe, resumo)
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
    "notas_fiscais": {"nome": "Notas Fiscais", "model": NotaFiscal, "runner": getNotasFiscais},
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
    itens.append(
        {
            "chave": "itens_nota_fiscal",
            "nome": "Itens da Nota Fiscal",
            "ultima_atualizacao": ItemNotaFiscal.objects.aggregate(ultima=Max("updated_at")).get("ultima"),
            "total_registros": ItemNotaFiscal.objects.count(),
            "permite_execucao": False,
            "observacao": "Atualizada junto com a integração de Notas Fiscais.",
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
        {
            "integracoes": _status_integracoes(),
            "clientes_sync": _clientes_sync_modal_context(),
        },
    )


def _dispatch_q_task(func_path: str, *args, task_name: str) -> dict:
    """
    Enfileira no django-q2. Com Q_CLUSTER['sync']=True, o próprio django-q2 executa inline (_sync).
    """
    task_id = async_task(func_path, *args, task_name=task_name)
    q_sync = getattr(settings, "Q_CLUSTER", {}).get("sync", False)
    if not q_sync:
        return {"completed": False, "sync": False, "task_id": task_id}
    t = Task.objects.filter(id=task_id).first()
    payload = _json_safe(t.result) if t and t.result is not None else None
    success = bool(t and t.success)
    if success and isinstance(payload, dict):
        if payload.get("erro"):
            success = False
        elif payload.get("erros"):
            success = False
    out: dict[str, Any] = {
        "completed": True,
        "sync": True,
        "success": success,
        "task_id": task_id,
        "resultado": payload,
    }
    if not success:
        if isinstance(payload, dict) and payload.get("erro"):
            out["error"] = payload.get("erro")
        elif isinstance(payload, dict) and payload.get("erros"):
            out["erros"] = payload.get("erros")
        elif t and t.result is not None:
            out["error"] = str(t.result)
        else:
            out["error"] = "Falha na tarefa"
    return out


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
    codigo_tabela: int | None = None
    dtalter_desde: str | None = None
    if chave == "precos":
        codigo_tabela_raw = (request.POST.get("codigo_tabela") or "").strip()
        if not codigo_tabela_raw:
            if _wants_json(request):
                return JsonResponse({"error": "Informe o código da tabela para atualizar os preços."}, status=400)
            messages.error(request, "Informe o código da tabela para atualizar os preços.")
            return redirect("api_sankhya_gestao_integracoes")
        codigo_tabela = _to_int(codigo_tabela_raw)
        if codigo_tabela is None:
            if _wants_json(request):
                return JsonResponse({"error": "Código da tabela inválido."}, status=400)
            messages.error(request, "Código da tabela inválido.")
            return redirect("api_sankhya_gestao_integracoes")
        if codigo_tabela == 9999:
            codigo_tabela = None
    if chave == "clientes":
        if request.POST.get("sincronizar_tudo") in ("1", "true", "on", "yes"):
            dtalter_desde = "__full__"
        else:
            custom = (request.POST.get("dtalter_desde") or "").strip()
            if custom:
                dtalter_desde = custom
    try:
        dispatch = _dispatch_q_task(
            "api_sankhya.tasks.run_integracao_sankhya",
            chave,
            codigo_tabela,
            dtalter_desde,
            task_name=f"Sankhya: {nome}",
        )
        if _wants_json(request):
            payload = {
                "chave": chave,
                "nome": nome,
                **dispatch,
            }
            if dispatch.get("completed") and not dispatch.get("success"):
                return JsonResponse(payload, status=400)
            return JsonResponse(payload)
        if dispatch.get("completed"):
            resultado = dispatch.get("resultado") or {}
            if dispatch.get("success"):
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
                messages.error(request, f"Erro ao atualizar {nome}: {dispatch.get('error', 'Falha na tarefa')}")
        else:
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
    try:
        dispatch = _dispatch_q_task(
            "api_sankhya.tasks.run_todas_integracoes_sankhya",
            task_name="Sankhya: todas as integrações",
        )
        if _wants_json(request):
            payload = {
                "chave": "__todas__",
                "nome": "Todas as integrações",
                **dispatch,
            }
            if dispatch.get("completed") and not dispatch.get("success"):
                return JsonResponse(payload, status=400)
            return JsonResponse(payload)
        if dispatch.get("completed"):
            erros = (dispatch.get("erros") or (dispatch.get("resultado") or {}).get("erros") or [])
            if erros:
                messages.warning(
                    request,
                    "Algumas integrações falharam: " + " | ".join(erros[:5]),
                )
            else:
                messages.success(
                    request,
                    "Atualização completa concluída com sucesso.",
                )
        else:
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
