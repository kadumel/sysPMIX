import requests
import json
from datetime import datetime
from .models import Funcionario, Veiculo, Pedido, ItemPedido, ClienteERP, EnderecoCliente
from dotenv import load_dotenv
import os
import logging

load_dotenv()

BASE_URL = os.getenv('BASE_URL')
login = os.getenv('login')
senha = os.getenv('senha')

logger = logging.getLogger(__name__)

class FuncionarioService:

   
    @staticmethod
    def formatar_dados(funcionario):
        return [{
            "campo_alt": funcionario.campo_alt or "NEW_825",
            "seq_id": funcionario.seq_id or "",
            "codigo_erp": funcionario.codigo_erp,
            "nome": funcionario.nome,
            "cpf": funcionario.cpf,
            "tipo": funcionario.tipo,
            "situacao": funcionario.status
        }]
    
    @staticmethod
    def enviar_dados(funcionario):
        try:
            dados = FuncionarioService.formatar_dados(funcionario)
            
            json_data = json.dumps(dados, ensure_ascii=False)
            # Monta o envelope SOAP
            soap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                            xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                            xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                            xmlns:urn="urn:myInputNamespace">
            <soapenv:Header/>
            <soapenv:Body>
                <urn:sendMotoristas soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                    <login xsi:type="xsd:string">{login}</login>
                    <senha xsi:type="xsd:string">{senha}</senha>
                    <array_dados xsi:type="xsd:string"><![CDATA[{json_data}]]></array_dados>
                </urn:sendMotoristas>
            </soapenv:Body>
            </soapenv:Envelope>"""

            headers = {
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "urn:sendMotoristas"
                }

            # print(soap_xml)
        
            # Enviar requisição
            response = requests.post(BASE_URL, data=soap_xml.encode('utf-8'), headers=headers)

            # Verificar resposta
            if response.status_code == 200:
                Funcionario.objects.filter(pk=funcionario.pk).update(sincronizado=True)
                return True, "Dados enviados com sucesso"
            else:
                return False, f"Erro ao enviar dados: {response.text}"
                
        except Exception as e:
            return False, f"Erro ao enviar dados: {str(e)}"
        

class VeiculoService:
    
    @staticmethod
    def formatar_dados(veiculo):
        return [{
            "campo_alt": veiculo.campo_alt or "NEW_762",
            "seq_id": veiculo.seq_id or "",
            "codigo_erp": veiculo.codigo_erp or "",
            "placa": veiculo.placa or "",
            "descricao": veiculo.descricao or "",
            "kmAtual": str(veiculo.km_atual) if veiculo.km_atual is not None else "0",
            "modelo": veiculo.modelo or "",
            "anoModelo": str(veiculo.ano_modelo) if veiculo.ano_modelo is not None else "0",
            "anoFabricacao": str(veiculo.ano_fabricacao) if veiculo.ano_fabricacao is not None else "0",
            "qtdMaxEntregas": str(veiculo.qtd_max_entregas) if veiculo.qtd_max_entregas is not None else "0",
            "velocidade_maxima": str(veiculo.velocidade_maxima) if veiculo.velocidade_maxima is not None else "0",
            "tipo_combustivel": veiculo.tipo_combustivel or "",
            "status_inicial": veiculo.status_inicial or "",
            "peso_max_entregas": str(veiculo.peso_max_entregas) if veiculo.peso_max_entregas is not None else "0",
            "volume_max_entregas": str(veiculo.volume_max_entregas) if veiculo.volume_max_entregas is not None else "0",
            "qtd_pallets_veiculo": str(veiculo.qtd_pallets_veiculo) if veiculo.qtd_pallets_veiculo is not None else "0",
            "filiais": [{"codigo_erp": veiculo.filial, "principal": "N"}]
        }
        ]
    
    @staticmethod
    def enviar_dados(veiculo):
        try:
            dados = VeiculoService.formatar_dados(veiculo)
            
            json_data = json.dumps(dados, ensure_ascii=False)
            # Monta o envelope SOAP
            soap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                            xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                            xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                            xmlns:urn="urn:myInputNamespace">
            <soapenv:Header/>
            <soapenv:Body>
                <urn:sendVeiculos soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                    <login xsi:type="xsd:string">{login}</login>
                    <senha xsi:type="xsd:string">{senha}</senha>
                    <array_dados xsi:type="xsd:string"><![CDATA[{json_data}]]></array_dados>
                </urn:sendVeiculos>
            </soapenv:Body>
            </soapenv:Envelope>"""

            headers = {
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "urn:sendVeiculos"
                }
        
            # print(soap_xml)
            # Enviar requisição
            response = requests.post(BASE_URL, data=soap_xml, headers=headers)
            # Verificar resposta
            if response.status_code == 200:
                Veiculo.objects.filter(pk=veiculo.pk).update(sincronizado=True)
                return True, "Dados enviados com sucesso"
            else:
                return False, f"Erro ao enviar dados: {response.text}"
                
        except Exception as e:
            return False, f"Erro ao enviar dados: {str(e)}"
        

class PedidoService:
    
    @staticmethod
    def formatar_dados(pedidos):
        dados = []
        for pedido in pedidos:
            # Buscar itens do pedido usando o modelo ItemPedido
            itens = ItemPedido.objects.filter(pedido=pedido)
            
            dados.append({
                "nf": pedido.nf,
                "chave_nfe": pedido.chave_nfe or '',
                "serie": pedido.serie or '',
                "tipo": pedido.tipo or '',
                "ent_ou_serv": pedido.ent_ou_serv or '',
                "prioridade": pedido.prioridade or '',
                "data_pedido": pedido.data_pedido.strftime('%Y-%m-%d') if pedido.data_pedido else '',
                "pedido_erp": pedido.pedido_erp,
                "vendedor_erp": pedido.vendedor_erp or '',
                "forma_pgto": pedido.forma_pgto or '',
                "status": pedido.status or '',
                "obs": pedido.obs or '',
                "num_ped_conf": pedido.num_ped_conf or '',
                "carga": pedido.carga or '',
                "cubagem": str(pedido.cubagem) if pedido.cubagem else '',
                "podeformarcarga": pedido.podeformarcarga or '',
                "valor": str(pedido.valor) if pedido.valor else '',
                "peso": str(pedido.peso) if pedido.peso else '',
                "qtd_pallets_entrega": pedido.qtd_pallets_entrega or '',
                "valor_st": str(pedido.valor_st) if pedido.valor_st else '',
                "empresa_fat": pedido.empresa_fat or '',
                "empresa_log": pedido.empresa_log or '',
                "empresa_digit": pedido.empresa_digit or '',
                "pedido_orig": pedido.pedido_orig or '',
                "dt_list_nf": pedido.dt_list_nf.strftime('%Y-%m-%d') if pedido.dt_list_nf else '',
                "codigo_cliente": pedido.codigo_cliente or '',
                "descr_cliente": pedido.descr_cliente or '',
                "razao_cliente": pedido.razao_cliente or '',
                "cnpj_cliente": pedido.cnpj_cliente or '',
                "end_cliente": pedido.end_cliente or '',
                "bairro_cliente": pedido.bairro_cliente or '',
                "num_end_cliente": pedido.num_end_cliente or '',
                "uf_cliente": pedido.uf_cliente or '',
                "cidade_cliente": pedido.cidade_cliente or '',
                "cep_cliente": pedido.cep_cliente or '',
                "retem_icms_cliente": pedido.retem_icms_cliente or '',
                "permite_retira_cliente": pedido.permite_retira_cliente or '',
                "rede_loja_cliente": pedido.rede_loja_cliente or '',
                "email1_cliente": pedido.email1_cliente or '',
                "email2_cliente": pedido.email2_cliente or '',
                "email3_cliente": pedido.email3_cliente or '',
                "tel1_cliente": pedido.tel1_cliente or '',
                "tel2_cliente": pedido.tel2_cliente or '',
                "tel3_cliente": pedido.tel3_cliente or '',
                "vlr_credito_cliente": str(pedido.vlr_credito_cliente) if pedido.vlr_credito_cliente else '',
                "data_cadastro_cliente": pedido.data_cadastro_cliente.strftime('%Y-%m-%d') if pedido.data_cadastro_cliente else '',
                "saldo_disp_cliente": str(pedido.saldo_disp_cliente) if pedido.saldo_disp_cliente else '',
                "vlr_tits_vencido_cliente": str(pedido.vlr_tits_vencido_cliente) if pedido.vlr_tits_vencido_cliente else '',
                "vlr_tits_vencer_cliente": str(pedido.vlr_tits_vencer_cliente) if pedido.vlr_tits_vencer_cliente else '',
                "status_cred_cliente": pedido.status_cred_cliente or '',
                "praca_cod_erp": '1',
                "praca_descricao": 'Praça Padrão',
                "rota_cod_erp": pedido.rota_cod_erp or '',
                "rota_descricao": pedido.rota_descricao or '',
                "cod_segmento": pedido.cod_segmento or '',
                "descr_segmento": pedido.descr_segmento or '',
                "filial_padrao": pedido.filial_padrao or '',
                "data_ult_compra": pedido.data_ult_compra.strftime('%Y-%m-%d') if pedido.data_ult_compra else '',
                "forma_pgto_cliente": pedido.forma_pgto_cliente or '',
                "codigo_endereco_alt": pedido.codigo_endereco_alt or '',
                "referencia_entrega": pedido.referencia_entrega or '',
                "restricao_transp": pedido.restricao_transp or '',
                "latitude": pedido.latitude or '',
                "longitude": pedido.longitude or '',
                "valor_adic_number_1": str(pedido.valor_adic_number_1) if pedido.valor_adic_number_1 else '',
                "valor_adic_number_2": str(pedido.valor_adic_number_2) if pedido.valor_adic_number_2 else '',
                "tipo_nota_fiscal": pedido.tipo_nota_fiscal or '',
                "itens": [
                    {
                        "cod_produto_erp": item.cod_produto_erp or '',
                        "descricao": item.descricao or '',
                        "unidade": item.unidade or '',
                        "qtd": str(item.qtd) if item.qtd else '',
                        "preco": str(item.preco) if item.preco else '',
                        "subtotal": str(item.subtotal) if item.subtotal else '',
                        "peso": str(item.peso) if item.peso else ''
                    } for item in itens
                ]
            })
        return dados

    @staticmethod
    def enviar_dados(pedidos):
        """Envia os dados dos pedidos para o web service"""
        try:
          
            # Formatar dados
            pedidos_formatados = PedidoService.formatar_dados(pedidos)
           
            json_data = json.dumps(pedidos_formatados, ensure_ascii=False)
            
            # Construir envelope SOAP
            soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                            xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                            xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                            xmlns:urn="urn:myInputNamespace">
            <soapenv:Header/>
            <soapenv:Body>
                <urn:saveEntregaServico soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                    <login xsi:type="xsd:string">{login}</login>
                    <senha xsi:type="xsd:string">{senha}</senha>
                    <array_dados xsi:type="xsd:string"><![CDATA[{json_data}]]></array_dados>
                </urn:saveEntregaServico>
            </soapenv:Body>
            </soapenv:Envelope>"""
            
            # Enviar requisição
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'urn:saveEntregaServico'
            }

            # print(soap_envelope)
            
            response = requests.post(
                BASE_URL,
                data=soap_envelope.encode('utf-8'),
                headers=headers,
                timeout=30
            )
            
            # Verificar resposta
            if response.status_code == 200:
                # Verificar se a resposta contém erro
                if 'Error' in response.text:
                    error_msg = response.text.split('<Error>')[1].split('</Error>')[0]
                    logger.error(f"Erro no web service: {error_msg}")
                    return False, error_msg
                return True, "Pedidos enviados com sucesso"
            else:
                error_msg = f"Erro HTTP {response.status_code}: {response.text}"
                logger.error(error_msg)
                return False, error_msg
                
        except requests.exceptions.Timeout:
            error_msg = "Timeout ao conectar com o web service"
            logger.error(error_msg)
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "Erro de conexão com o web service"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Erro ao enviar pedidos: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

class ClienteService:
    
    @staticmethod
    def atualizar_status_sincronizacao():
        """
        Atualiza o status de sincronização dos clientes baseado nos endereços.
        Se algum endereço estiver com sincronizado=False, o cliente também será marcado como não sincronizado.
        """
        # Busca todos os endereços não sincronizados
        enderecos_nao_sincronizados = EnderecoCliente.objects.filter(sincronizado=False).values_list('clienteERP_id', flat=True)
        
        # Atualiza os clientes que possuem endereços não sincronizados
        if enderecos_nao_sincronizados:
            ClienteERP.objects.filter(id__in=enderecos_nao_sincronizados).update(sincronizado=False)
            return True, f"Atualizados {len(enderecos_nao_sincronizados)} clientes com endereços não sincronizados"
        
        return False, "Nenhum cliente precisou ser atualizado"

    @staticmethod
    def formatar_dados():

        ClienteService.atualizar_status_sincronizacao()
        clientes = ClienteERP.objects.filter(sincronizado=False)
        dados = []
        if clientes:
            for cliente in clientes:
                # Buscar endereços alternativos do cliente
                enderecos = cliente.enderecos.all()
            
                # Formatar endereços alternativos
                end_alt = []
                for endereco in enderecos:
                    if not endereco.sincronizado:  # Apenas inclui endereços não sincronizados
                        end_alt.append({
                            "cod_end_erp": endereco.cod_end_erp or '',
                            "cod_praca_erp": endereco.cod_praca_erp or '',
                            "descr_praca_erp": endereco.descr_praca_erp or '',
                            "uf": endereco.uf or '',
                            "cidade": endereco.cidade or '',
                            "bairro": endereco.bairro or '',
                            "end": endereco.end or '',
                            "num_end": endereco.num_end or '',
                            "cep": endereco.cep or '',
                            "ref_entrega": endereco.ref_entrega or '',
                            "sn_padrao": endereco.sn_padrao or 'N',
                            "latitude": float(endereco.latitude) if endereco.latitude else 0,
                            "longitude": float(endereco.longitude) if endereco.longitude else 0
                        })
                
                # Formatar dados do cliente
                dados.append({
                    "campo_alt": cliente.campo_alt or '',
                    "seq_id": cliente.seq_id or '',
                    "codigo_cliente": cliente.codigo_cliente or '',
                    "filial_padrao": cliente.filial_padrao or '',
                    "descr_cliente": cliente.descr_cliente or '',
                    "razao_cliente": cliente.razao_cliente or '',
                    "cnpj_cpf_cliente": cliente.cnpj_cpf_cliente or '',
                    "cliente_cod_rota_erp": cliente.cliente_cod_rota_erp or '',
                    "cliente_descricao_rota": cliente.cliente_descricao_rota or '',
                    "cod_segmento": cliente.cod_segmento or '',
                    "descr_segmento": cliente.descr_segmento or '',
                    "cep_cliente": cliente.cep_cliente or '',
                    "end_cliente": cliente.end_cliente or '',
                    "num_end_cliente": cliente.num_end_cliente or '',
                    "bairro_cliente": cliente.bairro_cliente or '',
                    "cidade_cliente": cliente.cidade_cliente or '',
                    "uf_cliente": cliente.uf_cliente or '',
                    "email1_cliente": cliente.email1_cliente or '',
                    "email2_cliente": cliente.email2_cliente or '',
                    "email3_cliente": cliente.email3_cliente or '',
                    "tel1_cliente": cliente.tel1_cliente or '',
                    "tel2_cliente": cliente.tel2_cliente or '',
                    "tel3_cliente": cliente.tel3_cliente or '',
                    "data_cadastro_cliente": cliente.data_cadastro_cliente.strftime('%Y-%m-%d %H:%M:%S') if cliente.data_cadastro_cliente else '',
                    "vlr_credito_cliente": str(cliente.vlr_credito_cliente) if cliente.vlr_credito_cliente else '0',
                    "saldo_disp_cliente": str(cliente.saldo_disp_cliente) if cliente.saldo_disp_cliente else '0',
                    "vlr_tits_vencido_cliente": str(cliente.vlr_tits_vencido_cliente) if cliente.vlr_tits_vencido_cliente else '0',
                    "vlr_tits_vencer_cliente": str(cliente.vlr_tits_vencer_cliente) if cliente.vlr_tits_vencer_cliente else '0',
                    "status_cred_cliente": cliente.status_cred_cliente or '',
                    "data_ult_compra": cliente.data_ult_compra.strftime('%Y-%m-%d %H:%M:%S') if cliente.data_ult_compra else '',
                    "forma_pgto_cliente": cliente.forma_pgto_cliente or '',
                    "turnos_entrega": cliente.turnos_entrega or '',
                    "prioritario": cliente.prioritario or 'N',
                    "bloqueiosefaz": cliente.bloqueiosefaz or 'N',
                    "rede_loja_cliente": cliente.rede_loja_cliente or '',
                    "end_alt": end_alt
                })
            
            return dados
        else:
            return False

    @staticmethod
    def enviar_dados():
         """Envia os dados dos pedidos para o web service"""
        status = ClienteService.formatar_dados()
        if status:
            try:
                # Formatar dados
                json_data = json.dumps(status, ensure_ascii=False)
                
                # Construir envelope SOAP
                soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
                <soapenv:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                                xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                                xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                                xmlns:urn="urn:myInputNamespace">
                <soapenv:Header/>
                <soapenv:Body>
                    <urn:sendClientes soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                        <login xsi:type="xsd:string">{login}</login>
                        <senha xsi:type="xsd:string">{senha}</senha>
                        <array_dados xsi:type="xsd:string"><![CDATA[{json_data}]]></array_dados>
                    </urn:sendClientes>
                </soapenv:Body>
                </soapenv:Envelope>"""
                
                # Enviar requisição
                headers = {
                    'Content-Type': 'text/xml; charset=utf-8',
                    'SOAPAction': 'urn:sendClientes'
                }

                # print(soap_envelope)
                
                response = requests.post(
                    BASE_URL,
                    data=soap_envelope.encode('utf-8'),
                    headers=headers,
                    timeout=30
                )
                
                # Verificar resposta
                if response.status_code == 200:


                    # Verificar se a resposta contém erro
                    if 'Error' in response.text:
                        error_msg = response.text.split('<Error>')[1].split('</Error>')[0]
                        logger.error(f"Erro no web service: {error_msg}")
                        return False, error_msg
                    return True, "Pedidos enviados com sucesso"
                else:
                    error_msg = f"Erro HTTP {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    return False, error_msg
                    
            except requests.exceptions.Timeout:
                error_msg = "Timeout ao conectar com o web service"
                logger.error(error_msg)
                return False, error_msg
            except requests.exceptions.ConnectionError:
                error_msg = "Erro de conexão com o web service"
                logger.error(error_msg)
                return False, error_msg
            except Exception as e:
                error_msg = f"Erro ao enviar pedidos: {str(e)}"
                logger.error(error_msg)
                return False, error_msg