from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Funcionario, Veiculo, Pedido
from .services import FuncionarioService, VeiculoService, PedidoService

@receiver(post_save, sender=Funcionario)
def enviar_dados_ao_salvar(sender, instance, created, **kwargs):
    if not instance.sincronizado:  # Só envia se ainda não foi sincronizado
        sucesso, mensagem = FuncionarioService.enviar_dados(instance)
        if not sucesso:
            print(f"Erro ao sincronizar funcionário {instance.nome}: {mensagem}")

@receiver(post_save, sender=Veiculo)
def enviar_dados_veiculo_ao_salvar(sender, instance, created, **kwargs):
    if not instance.sincronizado:  # Só envia se ainda não foi sincronizado
        sucesso, mensagem = VeiculoService.enviar_dados(instance)
        if not sucesso:
            print(f"Erro ao sincronizar veículo {instance.placa}: {mensagem}")


@receiver(post_save, sender=Pedido)
def enviar_dados_pedido_ao_salvar(sender, instance, created, **kwargs):
    if not instance.sincronizado:  # Só envia se ainda não foi sincronizado
        print(100*'*','\n', instance, '\n', '*'*100)
        sucesso, mensagem = PedidoService.enviar_dados([instance])
        instance.sincronizado = True
        Pedido.objects.filter(id=instance.id).update(sincronizado=True)
        if not sucesso:
            print(f"Erro ao sincronizar pedido {instance.pedido_erp}: {mensagem}")
    else:
        print(f"Pedido {instance.pedido_erp} não sincronizado por coluna 'sincronizado' estar como TRUES")