import os
import sys
import django

# Configura o Django para poder usar os modelos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

import requests, json
from api_sankhya.models import (
    Veiculo, Empresa, Cidade, Logradouro, Bairro, Vendedor, Cliente, Motorista,
    Preco, Produto, GrupoProduto, Pedido, ItemPedido
)
from datetime import datetime




def getToken():
    url = "https://api.sankhya.com.br/authenticate"

    payload = {'grant_type': 'client_credentials',
    'client_id': '3f3a35a6-537b-48ae-b77b-6c387f768ebe',
    'client_secret': '8MgAIJ7e1TrKkGJJVk8ecacyHnuNytjY'}

    headers = {
    'accept': 'application/x-www-form-urlencoded',
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-Token': '5d1b7c08-283d-492c-9a45-8fc99502260a'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    # Faz o parse do JSON da resposta
    response_data = response.json()
    
    # Retorna apenas o access_token
    return  {
                    "accept": "application/json",
                    "Authorization": f"Bearer {response_data['access_token']}"
            }


def getClientesGeral():
    url = "https://api.sankhya.com.br/v1/parceiros/clientes"

    page = 0
    hasMore = True

    headers = getToken()

    while hasMore:

        # Adiciona parâmetros de paginação na URL (ajuste conforme a API requer)
        params = {'page': page}  # ou 'offset': offset, dependendo da API
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response
        pagination = response['pagination']
        
        # Pega os valores da paginação
        page_num = pagination['page']
        offset = pagination['offset']
        total = pagination['total']
        hasMore_str = pagination['hasMore']
        
        # Converte hasMore de string para boolean
        hasMore = hasMore_str.lower() == 'true'
        
        print(f'Page: {page_num}, Offset: {offset}, Total: {total}, HasMore: {hasMore}')
        
        # Aqui você pode processar os dados da resposta (response['data'] ou similar)
        # Exemplo: clientes = response.get('data', [])
        
        if not hasMore:
            print(json.dumps(response['clientes'], indent=4))
        page += 1


def getPedidosOld(data_negociacao=None, offset_page=0, campos=None):

    url = "https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=CRUDServiceProvider.loadRecords&outputType=json"  # Ajuste o endpoint conforme necessário
    # Campos padrão se não especificados
    if campos is None:
        campos = ["NUNOTA", "CODEMP", "CODPARC", "DTNEG", "TIPMOV","LOCALENTREGA","QTDVOL"]
    
    # Data padrão se não especificada
    if data_negociacao is None:
        from datetime import datetime
        data_negociacao = datetime.now().strftime("%d/%m/%Y")
    
    # Constrói o corpo da requisição
    request_body = {
        "serviceName": "CRUDServiceProvider.loadRecords",
        "requestBody": {
            "dataSet": {
                "rootEntity": "CabecalhoNota",
                "includePresentationFields": "S",
                "offsetPage": str(offset_page),
                 "criteria": {
                        "expression": {
                            "$": "(this.NUNOTA = ? )"
                        },
                        "parameter": {
                            "$": "35139",
                            "type": "I"
                        }
                    },
                "entity": {
                    "fieldset": {
                        "list": ",".join(campos)
                    }
                }
            }
        }
    }
    
    # Obtém o token de autenticação
    headers = getToken()
    # Faz a requisição POST
    response = requests.get(url, headers=headers, json=request_body)
    # Retorna a resposta parseada
    return response.json()


def _parse_date(value):
    """Converte string 'YYYY-MM-DD' ou 'DD/MM/YYYY' em date ou None."""
    if value is None or value == '':
        return None
    if hasattr(value, 'year'):
        return value
    s = str(value).strip()[:10]
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _decimal_val(val):
    """Retorna valor para DecimalField (número ou None)."""
    if val is None or val == '':
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _int_val(val):
    """Retorna valor inteiro ou None."""
    if val is None or val == '':
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def getPedidosJson():
    """
    Consome a API https://api.sankhya.com.br/v1/vendas/pedidos,
    faz merge dos pedidos e itens no banco (Pedido + ItemPedido).
    """
    url = "https://api.sankhya.com.br/v1/vendas/pedidos"
    page = 1
    hasMore = True
    total_pedidos = 0
    total_itens = 0
    headers = getToken()
    print("Iniciando sincronização de pedidos (getPedidosJson)...")

    while hasMore:
        params = {'page': page}
        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"Erro na requisição página {page}: {e}")
            break

        pagination = data.get('pagination') or {}
        lista = data.get('pedido') or data.get('pedidos') or []

        if isinstance(pagination.get('hasMore'), str):
            hasMore = pagination.get('hasMore', 'false').lower() == 'true'
        else:
            hasMore = bool(pagination.get('hasMore', False))

        print(f"Página {page} - offset: {pagination.get('offset')}, total: {pagination.get('total')}, hasMore: {hasMore}")

        for p in lista:
            try:
                codigo_nota = _int_val(p.get('codigoNota'))
                if not codigo_nota:
                    print("  ⚠ Pedido sem codigoNota ignorado.")
                    continue

                cliente = p.get('cliente') or {}
                endereco = cliente.get('endereco') or {}

                def s(v, max_len=None):
                    if v is None: return None
                    v = str(v).strip()
                    if v == '' or v.lower() == 'null': return None
                    if max_len and len(v) > max_len: return v[:max_len]
                    return v

                pedido_defaults = {
                    'codigo_empresa': _int_val(p.get('codigoEmpresa')),
                    'nome_empresa': s(p.get('nomeEmpresa'), 200),
                    'codigo_cliente': _int_val(p.get('codigoCliente')),
                    'cliente_tipo': s(cliente.get('tipo'), 10),
                    'cliente_cnpj_cpf': s(cliente.get('cnpjCpf'), 20),
                    'cliente_ie_rg': s(cliente.get('ieRg'), 20),
                    'cliente_nome': s(cliente.get('nome'), 200),
                    'cliente_razao': s(cliente.get('razao'), 200),
                    'cliente_email': s(cliente.get('email'), 100),
                    'cliente_telefone': s(cliente.get('telefoneNumero'), 20),
                    'endereco_logradouro': s(endereco.get('logradouro'), 200),
                    'endereco_numero': s(endereco.get('numero'), 20),
                    'endereco_complemento': s(endereco.get('complemento'), 100),
                    'endereco_bairro': s(endereco.get('bairro'), 100),
                    'endereco_cidade': s(endereco.get('cidade'), 100),
                    'endereco_codigo_ibge': s(endereco.get('codigoIbge'), 20),
                    'endereco_uf': s(endereco.get('uf'), 2),
                    'endereco_cep': s(endereco.get('cep'), 10),
                    'entrega': bool(endereco.get('entrega', False)),
                    'confirmada': bool(p.get('confirmada', False)),
                    'pendente': bool(p.get('pendente', True)),
                    'data_negociacao': _parse_date(p.get('dataNegociacao')),
                    'data_hora_alteracao': s(p.get('dataHoraAlteracao'), 50),
                    'numero_nota': _int_val(p.get('numeroNota')),
                    'serie_nota': s(p.get('serieNota'), 10),
                    'codigo_tipo_negociacao': _int_val(p.get('codigoTipoNegociacao')),
                    'nome_tipo_negociacao': s(p.get('nomeTipoNegociacao'), 100),
                    'codigo_tipo_operacao': _int_val(p.get('codigoTipoOperacao')),
                    'nome_tipo_operacao': s(p.get('nomeTipoOperacao'), 100),
                    'codigo_natureza': _int_val(p.get('codigoNatureza')),
                    'codigo_centro_resultado': _int_val(p.get('codigoCentroResultado')),
                    'nome_centro_resultado': s(p.get('nomeCentroResultado'), 200),
                    'codigo_projeto': _int_val(p.get('codigoProjeto')),
                    'nome_projeto': s(p.get('nomeProjeto'), 200),
                    'codigo_contrato': _int_val(p.get('codigoContrato')),
                    'codigo_vendedor': _int_val(p.get('codigoVendedor')),
                    'nome_vendedor': s(p.get('nomeVendedor'), 200),
                    'codigo_contato': _int_val(p.get('codigoContato')),
                    'nome_contato': s(p.get('nomeContato'), 200),
                    'codigo_moeda': _int_val(p.get('codigoMoeda')),
                    'nome_moeda': s(p.get('nomeMoeda'), 50),
                    'valor_moeda': _decimal_val(p.get('valorMoeda')),
                    'valor_nota': _decimal_val(p.get('valorNota')),
                    'desconto_total': _decimal_val(p.get('descontoTotal')),
                    'valor_seguro': _decimal_val(p.get('valorSeguro')),
                    'valor_destaque': _decimal_val(p.get('valorDestaque')),
                    'valor_vendor': _decimal_val(p.get('valorVendor')),
                    'valor_juro': _decimal_val(p.get('valorJuro')),
                    'valor_outros': _decimal_val(p.get('valorOutros')),
                    'valor_embalagem': _decimal_val(p.get('valorEmbalagem')),
                    'valor_frete': _decimal_val(p.get('valorFrete')),
                    'vencimento_frete': s(p.get('vencimentoFrete'), 50),
                    'codigo_ordem_carga': _int_val(p.get('codigoOrdemCarga')),
                    'codigo_veiculo': _int_val(p.get('codigoVeiculo')),
                    'placa_veiculo': s(p.get('placaVeiculo'), 10),
                    'codigo_motorista': _int_val(p.get('codigoMotorista')),
                    'nome_motorista': s(p.get('nomeMotorista'), 200),
                    'codigo_transportadora': _int_val(p.get('codigoTransportadora')),
                    'nome_transportadora': s(p.get('nomeTransportadora'), 200),
                    'codigo_remetente': _int_val(p.get('codigoRemetente')),
                    'nome_remetente': s(p.get('nomeRemetente'), 200),
                    'codigo_destinatario': _int_val(p.get('codigoDestinatario')),
                    'nome_destinatario': s(p.get('nomeDestinatario'), 200),
                    'quantidade_volumes': _int_val(p.get('quantidadeVolumes')),
                    'numeracao_volumes': s(p.get('numeracaoVolumes'), 200),
                    'lacres': s(p.get('lacres'), 200),
                    'peso_bruto': _decimal_val(p.get('pesoBruto')),
                    'cif_fob': s(p.get('cifFob'), 1),
                    'tipo_frete': s(p.get('tipoFrete'), 1),
                    'base_icms_frete': _decimal_val(p.get('baseICMSFrete')),
                    'icms_frete': _decimal_val(p.get('icmsFrete')),
                    'status_wms': s(p.get('statusWMS'), 10),
                    'situacao_wms': _int_val(p.get('situacaoWMS')),
                    'status_conferencia': _int_val(p.get('statusConferencia')),
                }
                pedido_defaults = {k: v for k, v in pedido_defaults.items() if v is not None}

                pedido_obj, created = Pedido.objects.update_or_create(
                    codigo_nota=codigo_nota,
                    defaults=pedido_defaults
                )
                total_pedidos += 1
                if created:
                    print(f"  ✓ Pedido inserido: nota {codigo_nota}")
                else:
                    print(f"  ↻ Pedido atualizado: nota {codigo_nota}")

                # Itens: manter em sync (remover itens antigos e recriar a partir da API)
                ItemPedido.objects.filter(pedido=pedido_obj).delete()
                for item in (p.get('itens') or []):
                    seq = _int_val(item.get('sequencia')) or 0
                    ItemPedido.objects.create(
                        pedido=pedido_obj,
                        sequencia=seq,
                        cod_produto=_int_val(item.get('codProduto')),
                        descricao_produto=s(item.get('descricaoProduto'), 300),
                        quantidade=_decimal_val(item.get('quantidade')),
                        unidade=s(item.get('unidade'), 10),
                        valor_unitario=_decimal_val(item.get('valorUnitario')),
                        valor_total=_decimal_val(item.get('valorTotal')),
                        cfop=_int_val(item.get('cfop')),
                        ncm=s(item.get('ncm'), 20),
                        cst=s(item.get('cst'), 10),
                        valor_desconto=_decimal_val(item.get('valorDesconto')),
                        valor_icms=_decimal_val(item.get('valorICMS')),
                        valor_ipi=_decimal_val(item.get('valorIPI')),
                    )
                    total_itens += 1

            except Exception as ex:
                print(f"  ✗ Erro ao processar pedido: {ex}")
                continue

        page += 1

    print(f"Sincronização concluída: {total_pedidos} pedidos, {total_itens} itens.")
    return {'total_pedidos': total_pedidos, 'total_itens': total_itens}


def getVeiculos():
    """
    Busca veículos da API Sankhya e salva/atualiza no banco de dados.
    Faz merge dos dados: atualiza se existir, insere se for novo.
    """
    url = "https://api.sankhya.com.br/v1/veiculos"

    page = 0
    hasMore = True
    total_processados = 0
    total_inseridos = 0
    total_atualizados = 0

    headers = getToken()

    print("Iniciando sincronização de veículos...")
    
    while hasMore:
        # Adiciona parâmetros de paginação na URL
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response
        pagination = response['pagination']
        
        # Pega os valores da paginação
        page_num = pagination['page']
        offset = pagination['offset']
        total = pagination['total']
        hasMore_str = pagination['hasMore']
        
        # Converte hasMore de string para boolean
        hasMore = hasMore_str.lower() == 'true'
        
        print(f'Processando página {page_num} - Offset: {offset}, Total: {total}, HasMore: {hasMore}')
        
        # Processa os veículos da resposta atual
        veiculos = response.get('veiculos', [])
        
        for veiculo_data in veiculos:
            try:
                # Valida se tem código do veículo (campo obrigatório)
                codigo_veiculo = veiculo_data.get('codigoVeiculo')
                if not codigo_veiculo:
                    print(f"  ⚠ Veículo sem código ignorado: {veiculo_data.get('placa', 'N/A')}")
                    continue
                
                # Prepara os dados para o modelo
                dados_veiculo = {
                    'placa': veiculo_data.get('placa', ''),
                    'marca_modelo': veiculo_data.get('marcaModelo'),
                    'numero_motor': veiculo_data.get('numeroMotor'),
                    'renavam': veiculo_data.get('renavam'),
                    'chassis': veiculo_data.get('chassis'),
                    'categoria': veiculo_data.get('categoria'),
                    'peso_maximo': veiculo_data.get('pesoMaximo'),
                    'combustivel': veiculo_data.get('combustivel'),
                    'cor': veiculo_data.get('cor'),
                    'ano_fabricacao': veiculo_data.get('anoFabricacao'),
                    'ano_modelo': veiculo_data.get('anoModelo'),
                    'codigo_cidade': veiculo_data.get('codigoCidade'),
                    'nome_cidade': veiculo_data.get('nomeCidade'),
                    'codigo_funcionario': veiculo_data.get('codigoFuncionario'),
                    'nome_funcionario': veiculo_data.get('nomeFuncionario'),
                    'codigo_motorista': veiculo_data.get('codigoMotorista'),
                    'nome_motorista': veiculo_data.get('nomeMotorista'),
                    'codigo_parceiro': veiculo_data.get('codigoParceiro'),
                    'nome_parceiro': veiculo_data.get('nomeParceiro'),
                    'ativo': veiculo_data.get('ativo', True),
                }
                
                # Remove valores None para não sobrescrever campos existentes com None
                # Mantém apenas campos com valores válidos
                dados_veiculo = {k: v for k, v in dados_veiculo.items() if v is not None}
                
                # Faz merge: atualiza se existir, cria se não existir
                veiculo, created = Veiculo.objects.update_or_create(
                    codigo_veiculo=codigo_veiculo,
                    defaults=dados_veiculo
                )
                
                if created:
                    total_inseridos += 1
                    print(f"  ✓ Inserido: {veiculo.placa} (Código: {veiculo.codigo_veiculo})")
                else:
                    total_atualizados += 1
                    print(f"  ↻ Atualizado: {veiculo.placa} (Código: {veiculo.codigo_veiculo})")
                
                total_processados += 1
                
            except Exception as e:
                print(f"  ✗ Erro ao processar veículo {veiculo_data.get('codigoVeiculo', 'N/A')}: {str(e)}")
                continue
        
        page += 1
    
    print(f"\n{'='*50}")
    print(f"Sincronização concluída!")
    print(f"Total processados: {total_processados}")
    print(f"Total inseridos: {total_inseridos}")
    print(f"Total atualizados: {total_atualizados}")
    print(f"{'='*50}")
    
    return {
        'total_processados': total_processados,
        'total_inseridos': total_inseridos,
        'total_atualizados': total_atualizados
    }


def getEmpresas():
    """
    Busca empresas da API Sankhya e salva/atualiza no banco de dados.
    Faz merge dos dados: atualiza se existir, insere se for novo.
    """
    url = "https://api.sankhya.com.br/v1/empresas"

    page = 0
    hasMore = True
    total_processados = 0
    total_inseridos = 0
    total_atualizados = 0

    headers = getToken()

    print("Iniciando sincronização de empresas...")
    
    while hasMore:
        # Adiciona parâmetros de paginação na URL
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response
        pagination = response.get('pagination', {})
        
        # Pega os valores da paginação
        page_num = pagination.get('page', page)
        offset = pagination.get('offset', 0)
        total = pagination.get('total', 0)
        hasMore_str = pagination.get('hasMore', 'false')
        
        # Converte hasMore de string para boolean
        hasMore = hasMore_str.lower() == 'true'
        
        print(f'Processando página {page_num} - Offset: {offset}, Total: {total}, HasMore: {hasMore}')
        
        # Processa as empresas da resposta atual
        empresas = response.get('empresas', [])
        
        for empresa_data in empresas:
            try:
                # Valida se tem código da empresa (campo obrigatório)
                codigo_empresa = empresa_data.get('codigoEmpresa')
                if not codigo_empresa:
                    print(f"  ⚠ Empresa sem código ignorada: {empresa_data.get('nomeFantasia', 'N/A')}")
                    continue
                
                # Prepara os dados para o modelo
                dados_empresa = {
                    'nome_fantasia': empresa_data.get('nomeFantasia'),
                    'razao_social': empresa_data.get('razaoSocial'),
                    'razao_abreviada': empresa_data.get('razaoAbreviada'),
                    'cnpj_cpf': empresa_data.get('cnpjCpf'),
                    'inscricao_estadual': empresa_data.get('inscricaoEstadual'),
                    'inscricao_municipal': empresa_data.get('inscricaoMunicipal'),
                    'telefone': empresa_data.get('telefone'),
                    'email': empresa_data.get('email'),
                    'homepage': empresa_data.get('homepage'),
                    'codigo_logradouro': empresa_data.get('codigoLogradouro'),
                    'nome_logradouro': empresa_data.get('nomeLogradouro'),
                    'numero': empresa_data.get('numero'),
                    'complemento': empresa_data.get('complemento'),
                    'codigo_bairro': empresa_data.get('codigoBairro'),
                    'nome_bairro': empresa_data.get('nomeBairro'),
                    'codigo_cidade': empresa_data.get('codigoCidade'),
                    'nome_cidade': empresa_data.get('nomeCidade'),
                    'cep': empresa_data.get('cep'),
                    'codigo_empresa_matriz': empresa_data.get('codigoEmpresaMatriz'),
                }
                
                # Remove valores None para não sobrescrever campos existentes com None
                # Mantém apenas campos com valores válidos
                dados_empresa = {k: v for k, v in dados_empresa.items() if v is not None}
                
                # Faz merge: atualiza se existir, cria se não existir
                empresa, created = Empresa.objects.update_or_create(
                    codigo_empresa=codigo_empresa,
                    defaults=dados_empresa
                )
                
                if created:
                    total_inseridos += 1
                    print(f"  ✓ Inserido: {empresa.nome_fantasia or empresa.razao_social or 'N/A'} (Código: {empresa.codigo_empresa})")
                else:
                    total_atualizados += 1
                    print(f"  ↻ Atualizado: {empresa.nome_fantasia or empresa.razao_social or 'N/A'} (Código: {empresa.codigo_empresa})")
                
                total_processados += 1
                
            except Exception as e:
                print(f"  ✗ Erro ao processar empresa {empresa_data.get('codigoEmpresa', 'N/A')}: {str(e)}")
                continue
        
        page += 1
    
    print(f"\n{'='*50}")
    print(f"Sincronização concluída!")
    print(f"Total processados: {total_processados}")
    print(f"Total inseridos: {total_inseridos}")
    print(f"Total atualizados: {total_atualizados}")
    print(f"{'='*50}")
    
    return {
        'total_processados': total_processados,
        'total_inseridos': total_inseridos,
        'total_atualizados': total_atualizados
    }


def getCidades():
    """
    Busca cidades da API Sankhya e salva/atualiza no banco de dados.
    Faz merge dos dados: atualiza se existir, insere se for novo.
    """
    url = "https://api.sankhya.com.br/v1/cidades"

    page = 0
    hasMore = True
    total_processados = 0
    total_inseridos = 0
    total_atualizados = 0

    headers = getToken()

    print("Iniciando sincronização de cidades...")
    
    while hasMore:
        # Adiciona parâmetros de paginação na URL
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response (pode não ter paginação, então verifica)
        pagination = response.get('pagination', {})
        
        # Se não tiver paginação, assume que é uma lista direta
        if not pagination:
            # Se a resposta for uma lista direta
            cidades = response if isinstance(response, list) else response.get('cidades', [])
            hasMore = False
        else:
            # Pega os valores da paginação
            page_num = pagination.get('page', page)
            offset = pagination.get('offset', 0)
            total = pagination.get('total', 0)
            hasMore_str = pagination.get('hasMore', 'false')
            
            # Converte hasMore de string para boolean
            hasMore = hasMore_str.lower() == 'true'
            
            print(f'Processando página {page_num} - Offset: {offset}, Total: {total}, HasMore: {hasMore}')
            
            # Processa as cidades da resposta atual
            cidades = response.get('cidades', [])
        
        for cidade_data in cidades:
            try:
                # Valida se tem código da cidade (campo obrigatório)
                codigo_cidade = cidade_data.get('codigoCidade')
                if not codigo_cidade:
                    print(f"  ⚠ Cidade sem código ignorada: {cidade_data.get('nome', 'N/A')}")
                    continue
                
                # Prepara os dados para o modelo
                dados_cidade = {
                    'nome': cidade_data.get('nome', ''),
                    'uf': cidade_data.get('uf'),
                    'codigo_regiao': cidade_data.get('codigoRegiao'),
                    'nome_regiao': cidade_data.get('nomeRegiao'),
                    'nome_correio': cidade_data.get('nomeCorreio'),
                    'codigo_municipio_fiscal': cidade_data.get('codigoMunicipioFiscal'),
                }
                
                # Remove valores None para não sobrescrever campos existentes com None
                # Mantém apenas campos com valores válidos
                dados_cidade = {k: v for k, v in dados_cidade.items() if v is not None}
                
                # Faz merge: atualiza se existir, cria se não existir
                cidade, created = Cidade.objects.update_or_create(
                    codigo_cidade=codigo_cidade,
                    defaults=dados_cidade
                )
                
                if created:
                    total_inseridos += 1
                    print(f"  ✓ Inserido: {cidade.nome} - {cidade.uf or 'N/A'} (Código: {cidade.codigo_cidade})")
                else:
                    total_atualizados += 1
                    print(f"  ↻ Atualizado: {cidade.nome} - {cidade.uf or 'N/A'} (Código: {cidade.codigo_cidade})")
                
                total_processados += 1
                
            except Exception as e:
                print(f"  ✗ Erro ao processar cidade {cidade_data.get('codigoCidade', 'N/A')}: {str(e)}")
                continue
        
        if pagination:
            page += 1
        else:
            break
    
    print(f"\n{'='*50}")
    print(f"Sincronização concluída!")
    print(f"Total processados: {total_processados}")
    print(f"Total inseridos: {total_inseridos}")
    print(f"Total atualizados: {total_atualizados}")
    print(f"{'='*50}")
    
    return {
        'total_processados': total_processados,
        'total_inseridos': total_inseridos,
        'total_atualizados': total_atualizados
    }


def getLogradouros():
    """
    Busca logradouros da API Sankhya e salva/atualiza no banco de dados.
    Faz merge dos dados: atualiza se existir, insere se for novo.
    """
    url = "https://api.sankhya.com.br/v1/logradouros"

    page = 0
    hasMore = True
    total_processados = 0
    total_inseridos = 0
    total_atualizados = 0

    headers = getToken()

    print("Iniciando sincronização de logradouros...")
    
    while hasMore:
        # Adiciona parâmetros de paginação na URL
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response (pode não ter paginação, então verifica)
        pagination = response.get('pagination', {})
        
        # Se não tiver paginação, assume que é uma lista direta
        if not pagination:
            # Se a resposta for uma lista direta
            logradouros = response if isinstance(response, list) else response.get('logradouros', [])
            hasMore = False
        else:
            # Pega os valores da paginação
            page_num = pagination.get('page', page)
            offset = pagination.get('offset', 0)
            total = pagination.get('total', 0)
            hasMore_str = pagination.get('hasMore', 'false')
            
            # Converte hasMore de string para boolean
            hasMore = hasMore_str.lower() == 'true'
            
            print(f'Processando página {page_num} - Offset: {offset}, Total: {total}, HasMore: {hasMore}')
            
            # Processa os logradouros da resposta atual
            logradouros = response.get('logradouros', [])
        
        for logradouro_data in logradouros:
            try:
                # Valida se tem código do logradouro (campo obrigatório)
                codigo_logradouro = logradouro_data.get('codigoLogradouro')
                if not codigo_logradouro:
                    print(f"  ⚠ Logradouro sem código ignorado: {logradouro_data.get('nome', 'N/A')}")
                    continue
                
                # Prepara os dados para o modelo
                dados_logradouro = {
                    'nome': logradouro_data.get('nome', ''),
                    'tipo': logradouro_data.get('tipo'),
                    'descricao_correio': logradouro_data.get('descricaoCorreio'),
                }
                
                # Remove valores None para não sobrescrever campos existentes com None
                # Mantém apenas campos com valores válidos
                dados_logradouro = {k: v for k, v in dados_logradouro.items() if v is not None}
                
                # Faz merge: atualiza se existir, cria se não existir
                logradouro, created = Logradouro.objects.update_or_create(
                    codigo_logradouro=codigo_logradouro,
                    defaults=dados_logradouro
                )
                
                if created:
                    total_inseridos += 1
                    print(f"  ✓ Inserido: {logradouro.tipo or ''} {logradouro.nome}".strip() + f" (Código: {logradouro.codigo_logradouro})")
                else:
                    total_atualizados += 1
                    print(f"  ↻ Atualizado: {logradouro.tipo or ''} {logradouro.nome}".strip() + f" (Código: {logradouro.codigo_logradouro})")
                
                total_processados += 1
                
            except Exception as e:
                print(f"  ✗ Erro ao processar logradouro {logradouro_data.get('codigoLogradouro', 'N/A')}: {str(e)}")
                continue
        
        if pagination:
            page += 1
        else:
            break
    
    print(f"\n{'='*50}")
    print(f"Sincronização concluída!")
    print(f"Total processados: {total_processados}")
    print(f"Total inseridos: {total_inseridos}")
    print(f"Total atualizados: {total_atualizados}")
    print(f"{'='*50}")
    
    return {
        'total_processados': total_processados,
        'total_inseridos': total_inseridos,
        'total_atualizados': total_atualizados
    }


def getBairros():
    """
    Busca bairros da API Sankhya e salva/atualiza no banco de dados.
    Faz merge dos dados: atualiza se existir, insere se for novo.
    """
    url = "https://api.sankhya.com.br/v1/bairros"

    page = 0
    hasMore = True
    total_processados = 0
    total_inseridos = 0
    total_atualizados = 0

    headers = getToken()

    print("Iniciando sincronização de bairros...")
    
    while hasMore:
        # Adiciona parâmetros de paginação na URL
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response (pode não ter paginação, então verifica)
        pagination = response.get('pagination', {})
        
        # Se não tiver paginação, assume que é uma lista direta
        if not pagination:
            # Se a resposta for uma lista direta
            bairros = response if isinstance(response, list) else response.get('bairros', [])
            hasMore = False
        else:
            # Pega os valores da paginação
            page_num = pagination.get('page', page)
            offset = pagination.get('offset', 0)
            total = pagination.get('total', 0)
            hasMore_str = pagination.get('hasMore', 'false')
            
            # Converte hasMore de string para boolean
            hasMore = hasMore_str.lower() == 'true'
            
            print(f'Processando página {page_num} - Offset: {offset}, Total: {total}, HasMore: {hasMore}')
            
            # Processa os bairros da resposta atual
            bairros = response.get('bairros', [])
        
        for bairro_data in bairros:
            try:
                # Valida se tem código do bairro (campo obrigatório)
                codigo_bairro = bairro_data.get('codigoBairro')
                if not codigo_bairro:
                    print(f"  ⚠ Bairro sem código ignorado: {bairro_data.get('nome', 'N/A')}")
                    continue
                
                # Prepara os dados para o modelo
                dados_bairro = {
                    'nome': bairro_data.get('nome', ''),
                    'nome_regiao': bairro_data.get('nomeRegiao'),
                    'nome_correio': bairro_data.get('nomeCorreio'),
                }
                
                # Remove valores None para não sobrescrever campos existentes com None
                # Mantém apenas campos com valores válidos
                dados_bairro = {k: v for k, v in dados_bairro.items() if v is not None}
                
                # Faz merge: atualiza se existir, cria se não existir
                bairro, created = Bairro.objects.update_or_create(
                    codigo_bairro=codigo_bairro,
                    defaults=dados_bairro
                )
                
                if created:
                    total_inseridos += 1
                    print(f"  ✓ Inserido: {bairro.nome} - {bairro.nome_regiao or 'N/A'} (Código: {bairro.codigo_bairro})")
                else:
                    total_atualizados += 1
                    print(f"  ↻ Atualizado: {bairro.nome} - {bairro.nome_regiao or 'N/A'} (Código: {bairro.codigo_bairro})")
                
                total_processados += 1
                
            except Exception as e:
                print(f"  ✗ Erro ao processar bairro {bairro_data.get('codigoBairro', 'N/A')}: {str(e)}")
                continue
        
        if pagination:
            page += 1
        else:
            break
    
    print(f"\n{'='*50}")
    print(f"Sincronização concluída!")
    print(f"Total processados: {total_processados}")
    print(f"Total inseridos: {total_inseridos}")
    print(f"Total atualizados: {total_atualizados}")
    print(f"{'='*50}")
    
    return {
        'total_processados': total_processados,
        'total_inseridos': total_inseridos,
        'total_atualizados': total_atualizados
    }


def getVendedores():
    """
    Busca vendedores da API Sankhya e salva/atualiza no banco de dados.
    Faz merge dos dados: atualiza se existir, insere se for novo.
    """
    url = "https://api.sankhya.com.br/v1/vendedores"

    page = 0
    hasMore = True
    total_processados = 0
    total_inseridos = 0
    total_atualizados = 0

    headers = getToken()

    print("Iniciando sincronização de vendedores...")
    
    while hasMore:
        # Adiciona parâmetros de paginação na URL
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response (pode não ter paginação, então verifica)
        pagination = response.get('pagination', {})
        
        # Se não tiver paginação, assume que é uma lista direta
        if not pagination:
            # Se a resposta for uma lista direta
            vendedores = response if isinstance(response, list) else response.get('vendedores', [])
            hasMore = False
        else:
            # Pega os valores da paginação
            page_num = pagination.get('page', page)
            offset = pagination.get('offset', 0)
            total = pagination.get('total', 0)
            hasMore_str = pagination.get('hasMore', 'false')
            
            # Converte hasMore de string para boolean
            hasMore = hasMore_str.lower() == 'true'
            
            print(f'Processando página {page_num} - Offset: {offset}, Total: {total}, HasMore: {hasMore}')
            
            # Processa os vendedores da resposta atual
            vendedores = response.get('vendedores', [])
        
        for vendedor_data in vendedores:
            try:
                # Valida se tem código do vendedor (campo obrigatório)
                codigo_vendedor = vendedor_data.get('codigoVendedor')
                if not codigo_vendedor:
                    print(f"  ⚠ Vendedor sem código ignorado: {vendedor_data.get('nome', 'N/A')}")
                    continue
                
                # Prepara os dados para o modelo
                dados_vendedor = {
                    'nome': vendedor_data.get('nome', ''),
                    'ativo': vendedor_data.get('ativo', True),
                    'tipo': vendedor_data.get('tipo'),
                    'comissao_gerencia': vendedor_data.get('comissaoGerencia'),
                    'comissao_venda': vendedor_data.get('comissaoVenda'),
                    'email': vendedor_data.get('email'),
                    'codigo_empresa': vendedor_data.get('codigoEmpresa'),
                    'nome_empresa': vendedor_data.get('nomeEmpresa'),
                    'codigo_parceiro': vendedor_data.get('codigoParceiro'),
                    'nome_parceiro': vendedor_data.get('nomeParceiro'),
                    'codigo_funcionario': vendedor_data.get('codigoFuncionario'),
                    'nome_funcionario': vendedor_data.get('nomeFuncionario'),
                    'codigo_gerente': vendedor_data.get('codigoGerente'),
                    'nome_gerente': vendedor_data.get('nomeGerente'),
                    'codigo_centro_resultado': vendedor_data.get('codigoCentroResultado'),
                    'nome_centro_resultado': vendedor_data.get('nomeCentroResultado'),
                    'codigo_regiao': vendedor_data.get('codigoRegiao'),
                    'nome_regiao': vendedor_data.get('nomeRegiao'),
                }
                
                # Remove valores None para não sobrescrever campos existentes com None
                # Mantém apenas campos com valores válidos
                dados_vendedor = {k: v for k, v in dados_vendedor.items() if v is not None}
                
                # Faz merge: atualiza se existir, cria se não existir
                vendedor, created = Vendedor.objects.update_or_create(
                    codigo_vendedor=codigo_vendedor,
                    defaults=dados_vendedor
                )
                
                if created:
                    total_inseridos += 1
                    print(f"  ✓ Inserido: {vendedor.nome} (Código: {vendedor.codigo_vendedor})")
                else:
                    total_atualizados += 1
                    print(f"  ↻ Atualizado: {vendedor.nome} (Código: {vendedor.codigo_vendedor})")
                
                total_processados += 1
                
            except Exception as e:
                print(f"  ✗ Erro ao processar vendedor {vendedor_data.get('codigoVendedor', 'N/A')}: {str(e)}")
                continue
        
        if pagination:
            page += 1
        else:
            break
    
    print(f"\n{'='*50}")
    print(f"Sincronização concluída!")
    print(f"Total processados: {total_processados}")
    print(f"Total inseridos: {total_inseridos}")
    print(f"Total atualizados: {total_atualizados}")
    print(f"{'='*50}")
    
    return {
        'total_processados': total_processados,
        'total_inseridos': total_inseridos,
        'total_atualizados': total_atualizados
    }


def getClientes():
    """
    Busca clientes da API Sankhya e salva/atualiza no banco de dados.
    Faz merge dos dados: atualiza se existir, insere se for novo.
    """
    url = "https://api.sankhya.com.br/v1/parceiros/clientes"

    page = 0
    hasMore = True
    total_processados = 0
    total_inseridos = 0
    total_atualizados = 0

    headers = getToken()

    print("Iniciando sincronização de clientes...")
    
    while hasMore:
        # Adiciona parâmetros de paginação na URL
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response
        pagination = response.get('pagination', {})
        
        # Verifica se tem paginação ou se é uma estrutura diferente
        if not pagination:
            # Tenta pegar a paginação da estrutura alternativa
            tem_mais_registros = response.get('temMaisRegistros', False)
            page_num = response.get('page', page)
            numero_registros = response.get('numeroRegistros', 0)
            
            if isinstance(tem_mais_registros, str):
                hasMore = tem_mais_registros.lower() == 'true'
            else:
                hasMore = bool(tem_mais_registros)
            
            print(f'Processando página {page_num} - Registros: {numero_registros}, Tem mais: {hasMore}')
            
            # Processa os clientes da resposta atual
            clientes = response.get('clientes', [])
        else:
            # Pega os valores da paginação padrão
            page_num = pagination.get('page', page)
            offset = pagination.get('offset', 0)
            total = pagination.get('total', 0)
            hasMore_str = pagination.get('hasMore', 'false')
            
            # Converte hasMore de string para boolean
            hasMore = hasMore_str.lower() == 'true'
            
            print(f'Processando página {page_num} - Offset: {offset}, Total: {total}, HasMore: {hasMore}')
            
            # Processa os clientes da resposta atual
            clientes = response.get('clientes', [])
        
        for cliente_data in clientes:
            try:
                # Valida se tem código do cliente (campo obrigatório)
                codigo_cliente = cliente_data.get('codigoCliente')
                if not codigo_cliente:
                    print(f"  ⚠ Cliente sem código ignorado: {cliente_data.get('nome', 'N/A')}")
                    continue
                
                # Extrai dados do endereço (pode estar aninhado)
                endereco = cliente_data.get('endereco', {})
                
                # Prepara os dados para o modelo
                # Função auxiliar para validar e converter limite_credito
                def validar_limite_credito(valor):
                    if valor is None:
                        return None
                    if isinstance(valor, (int, float)):
                        return valor
                    if isinstance(valor, str):
                        valor = valor.strip()
                        if not valor or valor == '':
                            return None
                        try:
                            return float(valor)
                        except (ValueError, TypeError):
                            return None
                    return None
                
                # Função auxiliar para limpar e validar strings
                def limpar_string(valor, max_length=None):
                    if valor is None:
                        return None
                    if isinstance(valor, (int, float)):
                        valor = str(valor)
                    if isinstance(valor, str):
                        valor = valor.strip()
                        if not valor or valor == '':
                            return None
                        if max_length and len(valor) > max_length:
                            valor = valor[:max_length]
                        return valor
                    return None
                
                limite_credito_val = validar_limite_credito(cliente_data.get('limiteCredito'))
                telefone_ddd_val = limpar_string(cliente_data.get('telefoneDdd'), max_length=5)
                
                dados_cliente = {
                    'tipo': limpar_string(cliente_data.get('tipo')),
                    'cnpj_cpf': limpar_string(cliente_data.get('cnpjCpf')),
                    'ie_rg': limpar_string(cliente_data.get('ieRg')),
                    'nome': limpar_string(cliente_data.get('nome')),
                    'razao': limpar_string(cliente_data.get('razao')),
                    'email': limpar_string(cliente_data.get('email')),
                    'telefone_ddd': telefone_ddd_val,
                    'telefone_numero': limpar_string(cliente_data.get('telefoneNumero')),
                    'limite_credito': limite_credito_val,
                    'grupo_autorizacao': limpar_string(cliente_data.get('grupoAutorizacao')),
                    # Campos do endereço
                    'latitude': limpar_string(endereco.get('latitude')) if isinstance(endereco, dict) else None,
                    'longitude': limpar_string(endereco.get('longitude')) if isinstance(endereco, dict) else None,
                    'logradouro': limpar_string(endereco.get('logradouro')) if isinstance(endereco, dict) else None,
                    'numero': limpar_string(endereco.get('numero')) if isinstance(endereco, dict) and endereco.get('numero') is not None else None,
                    'complemento': limpar_string(endereco.get('complemento')) if isinstance(endereco, dict) else None,
                    'bairro': limpar_string(endereco.get('bairro')) if isinstance(endereco, dict) else None,
                    'cidade': limpar_string(endereco.get('cidade')) if isinstance(endereco, dict) else None,
                    'codigo_ibge': endereco.get('codigoIbge') if isinstance(endereco, dict) and isinstance(endereco.get('codigoIbge'), (int, type(None))) else None,
                    'uf': limpar_string(endereco.get('uf'), max_length=2) if isinstance(endereco, dict) else None,
                    'cep': limpar_string(endereco.get('cep')) if isinstance(endereco, dict) and endereco.get('cep') is not None else None,
                }
                
                # Remove valores None para não sobrescrever campos existentes com None
                # Mantém apenas campos com valores válidos
                dados_cliente = {k: v for k, v in dados_cliente.items() if v is not None}
                
                # Faz merge: atualiza se existir, cria se não existir
                cliente, created = Cliente.objects.update_or_create(
                    codigo_cliente=codigo_cliente,
                    defaults=dados_cliente
                )
                
                if created:
                    total_inseridos += 1
                    print(f"  ✓ Inserido: {cliente.nome or cliente.razao or 'N/A'} (Código: {cliente.codigo_cliente})")
                else:
                    total_atualizados += 1
                    print(f"  ↻ Atualizado: {cliente.nome or cliente.razao or 'N/A'} (Código: {cliente.codigo_cliente})")
                
                total_processados += 1
                
            except Exception as e:
                print(f"  ✗ Erro ao processar cliente {cliente_data.get('codigoCliente', 'N/A')}: {str(e)}")
                continue
        
        if pagination or response.get('temMaisRegistros'):
            page += 1
        else:
            break
    
    print(f"\n{'='*50}")
    print(f"Sincronização concluída!")
    print(f"Total processados: {total_processados}")
    print(f"Total inseridos: {total_inseridos}")
    print(f"Total atualizados: {total_atualizados}")
    print(f"{'='*50}")
    
    return {
        'total_processados': total_processados,
        'total_inseridos': total_inseridos,
        'total_atualizados': total_atualizados
    }


def getMotoristas():
    """
    Busca motoristas da API Sankhya e salva/atualiza no banco de dados.
    Faz merge dos dados: atualiza se existir, insere se for novo.
    """
    url = "https://api.sankhya.com.br/v1/motoristas"

    page = 0
    hasMore = True
    total_processados = 0
    total_inseridos = 0
    total_atualizados = 0

    headers = getToken()

    print("Iniciando sincronização de motoristas...")
    
    while hasMore:
        # Adiciona parâmetros de paginação na URL
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response
        pagination = response.get('pagination', {})
        
        # Pega os valores da paginação
        page_num = pagination.get('page', page)
        offset = pagination.get('offset', 0)
        total = pagination.get('total', 0)
        hasMore_str = pagination.get('hasMore', 'false')
        
        # Converte hasMore de string para boolean
        if isinstance(hasMore_str, str):
            hasMore = hasMore_str.lower() == 'true'
        else:
            hasMore = bool(hasMore_str)
        
        print(f'Processando página {page_num} - Offset: {offset}, Total: {total}, HasMore: {hasMore}')
        
        # Processa os motoristas da resposta atual
        motoristas = response.get('motoristas', [])
        
        for motorista_data in motoristas:
            try:
                # Valida se tem código do motorista (campo obrigatório)
                codigo_motorista = motorista_data.get('codigoMotorista')
                if not codigo_motorista:
                    print(f"  ⚠ Motorista sem código ignorado: {motorista_data.get('nome', 'N/A')}")
                    continue
                
                # Extrai dados do endereço (pode estar aninhado)
                endereco = motorista_data.get('endereco', {})
                
                # Função auxiliar para limpar e validar strings
                def limpar_string(valor, max_length=None):
                    if valor is None:
                        return None
                    if isinstance(valor, (int, float)):
                        valor = str(valor)
                    if isinstance(valor, str):
                        valor = valor.strip()
                        if not valor or valor == '':
                            return None
                        if max_length and len(valor) > max_length:
                            valor = valor[:max_length]
                        return valor
                    return None
                
                # Prepara os dados para o modelo
                dados_motorista = {
                    'nome': limpar_string(motorista_data.get('nome')),
                    'cpf': limpar_string(motorista_data.get('cpf')),
                    'rg': limpar_string(motorista_data.get('rg')),
                    'cnh': limpar_string(motorista_data.get('cnh')),
                    'categoria_cnh': limpar_string(motorista_data.get('categoriaCnh')),
                    'data_vencimento_cnh': limpar_string(motorista_data.get('dataVencimentoCnh')),
                    'email': limpar_string(motorista_data.get('email')),
                    'telefone': limpar_string(motorista_data.get('telefone')),
                    # Campos do endereço
                    'logradouro': limpar_string(endereco.get('logradouro')) if isinstance(endereco, dict) else None,
                    'numero': limpar_string(endereco.get('numero')) if isinstance(endereco, dict) else None,
                    'complemento': limpar_string(endereco.get('complemento')) if isinstance(endereco, dict) else None,
                    'bairro': limpar_string(endereco.get('bairro')) if isinstance(endereco, dict) else None,
                    'cidade': limpar_string(endereco.get('cidade')) if isinstance(endereco, dict) else None,
                    'codigo_ibge': limpar_string(endereco.get('codigoIbge')) if isinstance(endereco, dict) else None,
                    'uf': limpar_string(endereco.get('uf'), max_length=2) if isinstance(endereco, dict) else None,
                    'cep': limpar_string(endereco.get('cep')) if isinstance(endereco, dict) else None,
                }
                
                # Remove valores None para não sobrescrever campos existentes com None
                # Mantém apenas campos com valores válidos
                dados_motorista = {k: v for k, v in dados_motorista.items() if v is not None}
                
                # Faz merge: atualiza se existir, cria se não existir
                motorista, created = Motorista.objects.update_or_create(
                    codigo_motorista=codigo_motorista,
                    defaults=dados_motorista
                )
                
                if created:
                    total_inseridos += 1
                    print(f"  ✓ Inserido: {motorista.nome or 'N/A'} (Código: {motorista.codigo_motorista})")
                else:
                    total_atualizados += 1
                    print(f"  ↻ Atualizado: {motorista.nome or 'N/A'} (Código: {motorista.codigo_motorista})")
                
                total_processados += 1
                
            except Exception as e:
                print(f"  ✗ Erro ao processar motorista {motorista_data.get('codigoMotorista', 'N/A')}: {str(e)}")
                continue
        
        page += 1
    
    print(f"\n{'='*50}")
    print(f"Sincronização concluída!")
    print(f"Total processados: {total_processados}")
    print(f"Total inseridos: {total_inseridos}")
    print(f"Total atualizados: {total_atualizados}")
    print(f"{'='*50}")
    
    return {
        'total_processados': total_processados,
        'total_inseridos': total_inseridos,
        'total_atualizados': total_atualizados
    }


def getPrecos():
    """
    Busca preços da API Sankhya e salva/atualiza no banco de dados.
    Faz merge dos dados: atualiza se existir, insere se for novo.
    """
    url = "https://api.sankhya.com.br/v1/precos"

    page = 0
    hasMore = True
    total_processados = 0
    total_inseridos = 0
    total_atualizados = 0

    headers = getToken()

    print("Iniciando sincronização de preços...")
    
    while hasMore:
        # Adiciona parâmetros de paginação na URL
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response
        pagination = response.get('pagination', {})
        
        # Verifica se tem paginação ou se é uma estrutura diferente
        if not pagination:
            # Tenta pegar a paginação da estrutura alternativa
            tem_mais_registros = response.get('temMaisRegistros', False)
            page_num = response.get('page', page)
            numero_registros = response.get('numeroRegistros', 0)
            
            if isinstance(tem_mais_registros, str):
                hasMore = tem_mais_registros.lower() == 'true'
            else:
                hasMore = bool(tem_mais_registros)
            
            print(f'Processando página {page_num} - Registros: {numero_registros}, Tem mais: {hasMore}')
            
            # Processa os preços da resposta atual
            precos = response.get('precos', [])
        else:
            # Pega os valores da paginação padrão
            page_num = pagination.get('page', page)
            offset = pagination.get('offset', 0)
            total = pagination.get('total', 0)
            hasMore_str = pagination.get('hasMore', 'false')
            
            # Converte hasMore de string para boolean
            hasMore = hasMore_str.lower() == 'true'
            
            print(f'Processando página {page_num} - Offset: {offset}, Total: {total}, HasMore: {hasMore}')
            
            # Processa os preços da resposta atual
            precos = response.get('precos', [])
        
        for preco_data in precos:
            try:
                # Valida campos obrigatórios
                codigo_produto = preco_data.get('codigoProduto')
                codigo_tabela = preco_data.get('codigoTabela')
                codigo_local_estoque = preco_data.get('codigoLocalEstoque', 0)
                
                if not codigo_produto or codigo_tabela is None:
                    print(f"  ⚠ Preço sem código de produto ou tabela ignorado")
                    continue
                
                # Função auxiliar para validar e converter valor
                def validar_valor(valor):
                    if valor is None:
                        return None
                    if isinstance(valor, (int, float)):
                        return valor
                    if isinstance(valor, str):
                        valor = valor.strip()
                        if not valor or valor == '':
                            return None
                        try:
                            return float(valor)
                        except (ValueError, TypeError):
                            return None
                    return None
                
                # Função auxiliar para limpar e validar strings
                def limpar_string(valor, max_length=None):
                    if valor is None:
                        return None
                    if isinstance(valor, (int, float)):
                        valor = str(valor)
                    if isinstance(valor, str):
                        valor = valor.strip()
                        if not valor or valor == '':
                            return None
                        if max_length and len(valor) > max_length:
                            valor = valor[:max_length]
                        return valor
                    return None
                
                valor_preco = validar_valor(preco_data.get('valor'))
                if valor_preco is None:
                    print(f"  ⚠ Preço sem valor ignorado: Produto {codigo_produto}, Tabela {codigo_tabela}")
                    continue
                
                # Prepara os dados para o modelo
                dados_preco = {
                    'codigo_produto': codigo_produto,
                    'codigo_local_estoque': codigo_local_estoque,
                    'codigo_tabela': codigo_tabela,
                    'valor': valor_preco,
                    'controle': limpar_string(preco_data.get('controle')),
                    'unidade': limpar_string(preco_data.get('unidade'), max_length=10),
                }
                
                # Remove valores None para não sobrescrever campos existentes com None
                # Mantém apenas campos com valores válidos
                dados_preco = {k: v for k, v in dados_preco.items() if v is not None}
                
                # Faz merge: atualiza se existir, cria se não existir
                # Usa a combinação única de codigo_produto, codigo_local_estoque e codigo_tabela
                preco, created = Preco.objects.update_or_create(
                    codigo_produto=codigo_produto,
                    codigo_local_estoque=codigo_local_estoque,
                    codigo_tabela=codigo_tabela,
                    defaults=dados_preco
                )
                
                if created:
                    total_inseridos += 1
                    print(f"  ✓ Inserido: Produto {preco.codigo_produto} - Tabela {preco.codigo_tabela} - R$ {preco.valor}")
                else:
                    total_atualizados += 1
                    print(f"  ↻ Atualizado: Produto {preco.codigo_produto} - Tabela {preco.codigo_tabela} - R$ {preco.valor}")
                
                total_processados += 1
                
            except Exception as e:
                print(f"  ✗ Erro ao processar preço {preco_data.get('codigoProduto', 'N/A')}: {str(e)}")
                continue
        
        if pagination or response.get('temMaisRegistros'):
            page += 1
        else:
            break
    
    print(f"\n{'='*50}")
    print(f"Sincronização concluída!")
    print(f"Total processados: {total_processados}")
    print(f"Total inseridos: {total_inseridos}")
    print(f"Total atualizados: {total_atualizados}")
    print(f"{'='*50}")
    
    return {
        'total_processados': total_processados,
        'total_inseridos': total_inseridos,
        'total_atualizados': total_atualizados
    }


def getProdutos():
    """
    Busca produtos da API Sankhya e salva/atualiza no banco de dados.
    Faz merge dos dados: atualiza se existir, insere se for novo.
    """
    url = "https://api.sankhya.com.br/v1/produtos"

    page = 0
    hasMore = True
    total_processados = 0
    total_inseridos = 0
    total_atualizados = 0

    headers = getToken()

    print("Iniciando sincronização de produtos...")
    
    while hasMore:
        # Adiciona parâmetros de paginação na URL
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response (pode não ter paginação, então verifica)
        pagination = response.get('pagination', {})
        
        # Se não tiver paginação, assume que é uma lista direta
        if not pagination:
            # Se a resposta for uma lista direta
            produtos = response if isinstance(response, list) else response.get('produtos', [])
            hasMore = False
        else:
            # Pega os valores da paginação
            page_num = pagination.get('page', page)
            offset = pagination.get('offset', 0)
            total = pagination.get('total', 0)
            hasMore_str = pagination.get('hasMore', 'false')
            
            # Converte hasMore de string para boolean
            if isinstance(hasMore_str, str):
                hasMore = hasMore_str.lower() == 'true'
            else:
                hasMore = bool(hasMore_str)
            
            print(f'Processando página {page_num} - Offset: {offset}, Total: {total}, HasMore: {hasMore}')
            
            # Processa os produtos da resposta atual
            produtos = response.get('produtos', [])
        
        for produto_data in produtos:
            try:
                # Valida se tem código do produto (campo obrigatório)
                codigo_produto = produto_data.get('codigoProduto')
                if not codigo_produto:
                    print(f"  ⚠ Produto sem código ignorado: {produto_data.get('nome', 'N/A')}")
                    continue
                
                # Função auxiliar para validar e converter valores decimais
                def validar_decimal(valor):
                    if valor is None:
                        return None
                    if isinstance(valor, (int, float)):
                        return valor
                    if isinstance(valor, str):
                        valor = valor.strip()
                        if not valor or valor == '':
                            return None
                        try:
                            return float(valor)
                        except (ValueError, TypeError):
                            return None
                    return None
                
                # Função auxiliar para validar e converter valores inteiros
                def validar_inteiro(valor):
                    if valor is None:
                        return None
                    if isinstance(valor, (int, float)):
                        return int(valor)
                    if isinstance(valor, str):
                        valor = valor.strip()
                        if not valor or valor == '':
                            return None
                        try:
                            return int(float(valor))
                        except (ValueError, TypeError):
                            return None
                    return None
                
                # Função auxiliar para limpar e validar strings
                def limpar_string(valor, max_length=None):
                    if valor is None:
                        return None
                    if isinstance(valor, (int, float)):
                        valor = str(valor)
                    if isinstance(valor, str):
                        valor = valor.strip()
                        if not valor or valor == '':
                            return None
                        if max_length and len(valor) > max_length:
                            valor = valor[:max_length]
                        return valor
                    return None
                
                # Prepara os dados para o modelo
                dados_produto = {
                    'data_alteracao': limpar_string(produto_data.get('dataAltercao')),
                    'nome': limpar_string(produto_data.get('nome')),
                    'complemento': limpar_string(produto_data.get('complemento')),
                    'caracteristicas': limpar_string(produto_data.get('caracteristicas')),
                    'referencia': limpar_string(produto_data.get('referencia')),
                    'codigo_grupo_produto': validar_inteiro(produto_data.get('codigoGrupoProduto')),
                    'nome_grupo_produto': limpar_string(produto_data.get('nomeGrupoProduto')),
                    'volume': limpar_string(produto_data.get('volume'), max_length=10),
                    'marca': limpar_string(produto_data.get('marca')),
                    'decimais_valor': validar_inteiro(produto_data.get('decimaisValor')),
                    'decimais_quantidade': validar_inteiro(produto_data.get('decimaisQuantidade')),
                    'peso_bruto': validar_decimal(produto_data.get('pesoBruto')),
                    'agrupamento_minimo': validar_decimal(produto_data.get('agrupamentoMinimo')),
                    'quantidade_embalagem': validar_inteiro(produto_data.get('quantidadeEmbalagem')),
                    'tipo_controle_estoque': validar_inteiro(produto_data.get('tipoControleEstoque')),
                    'ativo': produto_data.get('ativo', True),
                    'estoque_maximo': validar_inteiro(produto_data.get('estoqueMaximo')),
                    'estoque_minimo': validar_inteiro(produto_data.get('estoqueMinimo')),
                    'homepage': limpar_string(produto_data.get('homepage')),
                    'grupo_desconto': limpar_string(produto_data.get('grupoDesconto')),
                    'referencia_fornecedor': limpar_string(produto_data.get('referenciaFornecedor')),
                    'usado_como': validar_inteiro(produto_data.get('usadoComo')),
                    'cnae': validar_inteiro(produto_data.get('cnae')),
                    'metro_cubico': validar_decimal(produto_data.get('metroCubico')),
                    'altura': validar_decimal(produto_data.get('altura')),
                    'largura': validar_decimal(produto_data.get('largura')),
                    'espessura': validar_decimal(produto_data.get('espessura')),
                    'unidade_medida': limpar_string(produto_data.get('unidadeMedida'), max_length=10),
                    'utiliza_balanca': produto_data.get('utilizaBalanca', False),
                    'codigo_pais': validar_inteiro(produto_data.get('codigoPais')),
                    'ncm': limpar_string(produto_data.get('ncm'), max_length=20),
                    'cest': limpar_string(produto_data.get('cest'), max_length=20),
                }
                
                # Remove valores None para não sobrescrever campos existentes com None
                # Mantém apenas campos com valores válidos
                dados_produto = {k: v for k, v in dados_produto.items() if v is not None}
                
                # Faz merge: atualiza se existir, cria se não existir
                produto, created = Produto.objects.update_or_create(
                    codigo_produto=codigo_produto,
                    defaults=dados_produto
                )
                
                if created:
                    total_inseridos += 1
                    print(f"  ✓ Inserido: {produto.nome or 'N/A'} (Código: {produto.codigo_produto})")
                else:
                    total_atualizados += 1
                    print(f"  ↻ Atualizado: {produto.nome or 'N/A'} (Código: {produto.codigo_produto})")
                
                total_processados += 1
                
            except Exception as e:
                print(f"  ✗ Erro ao processar produto {produto_data.get('codigoProduto', 'N/A')}: {str(e)}")
                continue
        
        if pagination:
            page += 1
        else:
            break
    
    print(f"\n{'='*50}")
    print(f"Sincronização concluída!")
    print(f"Total processados: {total_processados}")
    print(f"Total inseridos: {total_inseridos}")
    print(f"Total atualizados: {total_atualizados}")
    print(f"{'='*50}")
    
    return {
        'total_processados': total_processados,
        'total_inseridos': total_inseridos,
        'total_atualizados': total_atualizados
    }


def getGruposProduto():
    """
    Busca grupos de produtos da API Sankhya e salva/atualiza no banco de dados.
    Faz merge dos dados: atualiza se existir, insere se for novo.
    """
    url = "https://api.sankhya.com.br/v1/grupos-produto"

    page = 0
    hasMore = True
    total_processados = 0
    total_inseridos = 0
    total_atualizados = 0

    headers = getToken()

    print("Iniciando sincronização de grupos de produtos...")
    
    while hasMore:
        # Adiciona parâmetros de paginação na URL
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Acessa a paginação do response (pode não ter paginação, então verifica)
        pagination = response.get('pagination', {})
        
        # Se não tiver paginação, assume que é uma lista direta
        if not pagination:
            # Se a resposta for uma lista direta
            grupos = response if isinstance(response, list) else response.get('grupos', [])
            hasMore = False
        else:
            # Pega os valores da paginação
            page_num = pagination.get('page', page)
            offset = pagination.get('offset', 0)
            total = pagination.get('total', 0)
            hasMore_str = pagination.get('hasMore', 'false')
            
            # Converte hasMore de string para boolean
            if isinstance(hasMore_str, str):
                hasMore = hasMore_str.lower() == 'true'
            else:
                hasMore = bool(hasMore_str)
            
            print(f'Processando página {page_num} - Offset: {offset}, Total: {total}, HasMore: {hasMore}')
            
            # Processa os grupos da resposta atual
            grupos = response.get('grupos', [])
        
        for grupo_data in grupos:
            try:
                # Valida se tem código do grupo (campo obrigatório)
                codigo_grupo_produto = grupo_data.get('codigoGrupoProduto')
                if not codigo_grupo_produto:
                    print(f"  ⚠ Grupo sem código ignorado: {grupo_data.get('nome', 'N/A')}")
                    continue
                
                # Função auxiliar para validar e converter valores inteiros
                def validar_inteiro(valor):
                    if valor is None:
                        return None
                    if isinstance(valor, (int, float)):
                        return int(valor)
                    if isinstance(valor, str):
                        valor = valor.strip()
                        if not valor or valor == '':
                            return None
                        try:
                            return int(float(valor))
                        except (ValueError, TypeError):
                            return None
                    return None
                
                # Função auxiliar para limpar e validar strings
                def limpar_string(valor, max_length=None):
                    if valor is None:
                        return None
                    if isinstance(valor, (int, float)):
                        valor = str(valor)
                    if isinstance(valor, str):
                        valor = valor.strip()
                        if not valor or valor == '':
                            return None
                        if max_length and len(valor) > max_length:
                            valor = valor[:max_length]
                        return valor
                    return None
                
                # Prepara os dados para o modelo
                dados_grupo = {
                    'nome': limpar_string(grupo_data.get('nome')),
                    'codigo_grupo_produto_pai': validar_inteiro(grupo_data.get('codigoGrupoProdutoPai')),
                    'grau': validar_inteiro(grupo_data.get('grau')),
                    'grupo_icms': validar_inteiro(grupo_data.get('grupoIcms')),
                    'analitico': grupo_data.get('analitico', False),
                    'ativo': grupo_data.get('ativo', True),
                }
                
                # Remove valores None para não sobrescrever campos existentes com None
                # Mantém apenas campos com valores válidos
                dados_grupo = {k: v for k, v in dados_grupo.items() if v is not None}
                
                # Faz merge: atualiza se existir, cria se não existir
                grupo, created = GrupoProduto.objects.update_or_create(
                    codigo_grupo_produto=codigo_grupo_produto,
                    defaults=dados_grupo
                )
                
                if created:
                    total_inseridos += 1
                    print(f"  ✓ Inserido: {grupo.nome or 'N/A'} (Código: {grupo.codigo_grupo_produto})")
                else:
                    total_atualizados += 1
                    print(f"  ↻ Atualizado: {grupo.nome or 'N/A'} (Código: {grupo.codigo_grupo_produto})")
                
                total_processados += 1
                
            except Exception as e:
                print(f"  ✗ Erro ao processar grupo {grupo_data.get('codigoGrupoProduto', 'N/A')}: {str(e)}")
                continue
        
        if pagination:
            page += 1
        else:
            break
    
    print(f"\n{'='*50}")
    print(f"Sincronização concluída!")
    print(f"Total processados: {total_processados}")
    print(f"Total inseridos: {total_inseridos}")
    print(f"Total atualizados: {total_atualizados}")
    print(f"{'='*50}")
    
    return {
        'total_processados': total_processados,
        'total_inseridos': total_inseridos,
        'total_atualizados': total_atualizados
    }

#print(json.dumps(getPedidos(), indent=4)) 

print(getToken())