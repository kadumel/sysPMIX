from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db.models import Max
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
import os

import requests

from controleBI.decorators import requer_acesso_bi

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


def _sync_paginated(url: str, list_key: str, callback: Callable[[dict[str, Any]], tuple[bool, bool]], start_page: int = 0):
    page = start_page
    has_more = True
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}
    headers = getToken()
    while has_more:
        resp = requests.get(url, headers=headers, params={"page": page}, timeout=120)
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
    def cb(v):
        codigo = _to_int(v.get("codigoCliente"))
        if not codigo:
            return False, False
        defaults = {"tipo": _to_str(v.get("tipo"), 10), "cnpj_cpf": _to_str(v.get("cnpjCpf"), 20), "nome": _to_str(v.get("nome"), 200), "razao": _to_str(v.get("razao"), 200), "email": _to_str(v.get("email"), 100)}
        _, created = Cliente.objects.update_or_create(codigo_cliente=codigo, defaults=defaults)
        return created, True

    return _sync_paginated(_get_env_or_setting("SANKHYA_URL_CLIENTES"), "clientes", cb)


def getPrecos():
    def cb(v):
        codigo_produto = _to_int(v.get("codigoProduto"))
        codigo_tabela = _to_int(v.get("codigoTabela"))
        if codigo_produto is None or codigo_tabela is None:
            return False, False
        _, created = Preco.objects.update_or_create(
            codigo_produto=codigo_produto,
            codigo_local_estoque=_to_int(v.get("codigoLocalEstoque")) or 0,
            codigo_tabela=codigo_tabela,
            defaults={"valor": _to_decimal(v.get("valor")) or Decimal("0"), "controle": _to_str(v.get("controle"), 50), "unidade": _to_str(v.get("unidade"), 10)},
        )
        return created, True

    return _sync_paginated(_get_env_or_setting("SANKHYA_URL_PRECOS"), "precos", cb)


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
    """
    Busca grupos de produtos na API Sankhya e faz merge no banco (mesma lógica que testeApi.getGruposProduto):
    URL v1/grupos-produto, paginação com/sem bloco pagination, campos grau/grupo_icms/analitico e defaults sem None.
    """
    url = (
        getattr(settings, "SANKHYA_URL_GRUPOS_PRODUTO", None)
        or os.getenv("SANKHYA_URL_GRUPOS_PRODUTO")
    )
    page = 0
    has_more = True
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}
    headers = getToken()

    while has_more:
        resp = requests.get(url, headers=headers, params={"page": page}, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list):
            pagination = {}
            grupos = data
        else:
            pagination = data.get("pagination") or {}
            grupos = data.get("grupos", [])

        if not pagination:
            has_more = False
        else:
            hm = pagination.get("hasMore", "false")
            if isinstance(hm, str):
                has_more = hm.lower() == "true"
            else:
                has_more = bool(hm)

        for grupo_data in grupos:
            try:
                codigo = _to_int(grupo_data.get("codigoGrupoProduto"))
                if not codigo:
                    continue

                dados = {
                    "nome": _to_str(grupo_data.get("nome"), 200),
                    "codigo_grupo_produto_pai": _to_int(grupo_data.get("codigoGrupoProdutoPai")),
                    "grau": _to_int(grupo_data.get("grau")),
                    "grupo_icms": _to_int(grupo_data.get("grupoIcms")),
                    "analitico": grupo_data.get("analitico", False),
                    "ativo": grupo_data.get("ativo", True),
                }
                dados = {k: v for k, v in dados.items() if v is not None}
                _, created = GrupoProduto.objects.update_or_create(
                    codigo_grupo_produto=codigo,
                    defaults=dados,
                )
                out["total_processados"] += 1
                if created:
                    out["total_inseridos"] += 1
                else:
                    out["total_atualizados"] += 1
            except Exception:
                continue

        if pagination:
            page += 1
        else:
            break

    return out


def getPedidosJson():
    page = 1
    has_more = True
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}
    headers = getToken()
    while has_more:
        resp = requests.get(_get_env_or_setting("SANKHYA_URL_PEDIDOS"), headers=headers, params={"page": page}, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        has_more = str((data.get("pagination") or {}).get("hasMore", "false")).lower() == "true"
        for p in data.get("pedido") or data.get("pedidos") or []:
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
    while has_more:
        body = {
            "serviceName": "CRUDServiceProvider.loadRecords",
            "requestBody": {"dataSet": {"rootEntity": "Contato", "includePresentationFields": "S", "offsetPage": str(page), "entity": {"fieldset": {"list": "CODPARC,CODCONTATO,NOMECONTATO,EMAIL,TELEFONE,CELULAR"}}}},
        }
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        entities = (data.get("responseBody") or data).get("entities") or {}
        has_more = str(entities.get("hasMoreResult", "false")).lower() in {"1", "true", "s"}
        records = entities.get("entity") or []
        if isinstance(records, dict):
            records = [records]
        for row in records:
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
            _, created = Contato.objects.update_or_create(codparc=codparc, codcontato=codcontato, defaults=defaults)
            out["total_processados"] += 1
            if created:
                out["total_inseridos"] += 1
            else:
                out["total_atualizados"] += 1
        page += 1
    return out


def getFuncionarios():
    headers = getToken()
    page = 0
    has_more = True
    out = {"total_processados": 0, "total_inseridos": 0, "total_atualizados": 0}
    while has_more:
        resp = requests.get(_get_env_or_setting("SANKHYA_URL_FUNCIONARIOS"), headers=headers, params={"page": page}, timeout=120)
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
            det = requests.get(
                detalhe_url_template.format(
                    codigo_funcionario=codigo_funcionario,
                    codigo_empresa=codigo_empresa,
                ),
                headers=headers,
                timeout=120,
            )
            det.raise_for_status()
            detalhe = det.json()
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
    return render(
        request,
        "api_sankhya/gestao_integracoes.html",
        {"integracoes": _status_integracoes()},
    )


@login_required
@requer_acesso_bi
@require_POST
def atualizar_integracao(request, chave: str):
    if chave not in INTEGRACOES:
        messages.error(request, "Integração inválida.")
        return redirect("api_sankhya_gestao_integracoes")
    integracao = INTEGRACOES[chave]
    nome = integracao["nome"]
    try:
        resultado = integracao["runner"]()
        if not isinstance(resultado, dict):
            resultado = {}
        messages.success(
            request,
            (
                f"{nome} atualizado com sucesso. "
                f"Processados: {resultado.get('total_processados', resultado.get('total_registros', '-'))} | "
                f"Inseridos: {resultado.get('total_inseridos', '-')} | "
                f"Atualizados: {resultado.get('total_atualizados', '-')}"
            ),
        )
    except Exception as exc:
        messages.error(request, f"Erro ao atualizar {nome}: {exc}")
    return redirect("api_sankhya_gestao_integracoes")


@login_required
@requer_acesso_bi
@require_POST
def atualizar_todas_integracoes(request):
    erros: list[str] = []
    for _chave, integracao in INTEGRACOES.items():
        nome = integracao["nome"]
        try:
            integracao["runner"]()
        except Exception as exc:
            erros.append(f"{nome}: {exc}")
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
    return redirect("api_sankhya_gestao_integracoes")
