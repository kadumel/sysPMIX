from django import forms
from django.contrib.auth.models import User

from api_sankhya.models import Cliente as ClienteSankhya
from ecommerce.models import AlertaLoja, Campanha

from .models import Veiculo


class CampanhaForm(forms.ModelForm):
    class Meta:
        model = Campanha
        fields = ['nome', 'descricao', 'data_inicio', 'data_fim']
        labels = {
            'nome': 'Nome da campanha',
            'descricao': 'Descrição',
            'data_inicio': 'Data de início',
            'data_fim': 'Data de fim',
        }
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'data_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def clean(self):
        data = super().clean()
        ini = data.get('data_inicio')
        fim = data.get('data_fim')
        if ini and fim and fim < ini:
            raise forms.ValidationError('A data de fim deve ser igual ou posterior à data de início.')
        return data


class AlertaLojaForm(forms.ModelForm):
    ALCANCE_TODOS = 'todos'
    ALCANCE_CLIENTE = 'cliente'

    alcance = forms.ChoiceField(
        label='Destinatário',
        choices=(
            (ALCANCE_TODOS, 'Todos os clientes'),
            (ALCANCE_CLIENTE, 'Clientes específicos'),
        ),
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial=ALCANCE_TODOS,
    )

    class Meta:
        model = AlertaLoja
        fields = [
            'titulo',
            'mensagem',
            'tipo',
            'ativo',
            'ordem',
            'data_inicio',
            'data_fim',
            'hora_inicio',
            'hora_fim',
        ]
        labels = {
            'titulo': 'Título',
            'mensagem': 'Mensagem',
            'tipo': 'Tipo',
            'ativo': 'Ativo',
            'ordem': 'Ordem',
            'data_inicio': 'Data de início',
            'data_fim': 'Data de fim',
            'hora_inicio': 'Horário de início',
            'hora_fim': 'Horário de fim',
        }
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: Horário de entrega'}),
            'mensagem': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Ex.: Pedidos feitos após as 12h serão entregues no próximo dia útil.',
                }
            ),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'data_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'data_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'hora_inicio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}, format='%H:%M'),
            'hora_fim': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}, format='%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hora_inicio'].required = False
        self.fields['hora_fim'].required = False
        self.fields['titulo'].required = False
        instance = self.instance
        tem_clientes = False
        if instance and instance.pk:
            tem_clientes = instance.clientes.exists()
        if tem_clientes:
            self.fields['alcance'].initial = self.ALCANCE_CLIENTE
        elif not self.data:
            self.fields['alcance'].initial = self.ALCANCE_TODOS

    @staticmethod
    def ids_clientes_from_data(data):
        ids = []
        seen = set()
        for raw in data.getlist('clientes_ids'):
            try:
                cid = int(raw)
            except (TypeError, ValueError):
                continue
            if cid not in seen:
                seen.add(cid)
                ids.append(cid)
        return ids

    def clean(self):
        data = super().clean()
        ini = data.get('data_inicio')
        fim = data.get('data_fim')
        if ini and fim and fim < ini:
            self.add_error('data_fim', 'A data de fim deve ser igual ou posterior à data de início.')
        hora_ini = data.get('hora_inicio')
        hora_fim = data.get('hora_fim')
        if hora_ini and hora_fim and hora_fim < hora_ini:
            self.add_error('hora_fim', 'O horário de fim deve ser igual ou posterior ao horário de início.')
        alcance = data.get('alcance')
        ids = self.ids_clientes_from_data(self.data) if self.data else []
        if ids:
            validos = set(ClienteSankhya.objects.filter(pk__in=ids).values_list('id', flat=True))
            ids = [cid for cid in ids if cid in validos]
        if alcance == self.ALCANCE_CLIENTE and not ids:
            self.add_error('alcance', 'Adicione pelo menos um cliente ou marque "Todos os clientes".')
        if alcance != self.ALCANCE_CLIENTE:
            ids = []
        data['clientes_ids'] = ids
        return data

    def save(self, commit=True):
        obj = super().save(commit=commit)
        if commit:
            obj.clientes.set(self.cleaned_data.get('clientes_ids') or [])
        return obj


class ClienteSankhyaConfigForm(forms.ModelForm):
    class Meta:
        model = ClienteSankhya
        fields = ['tempo_analise']
        labels = {
            'tempo_analise': 'Tempo de análise (meses)',
        }
        widgets = {
            'tempo_analise': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 1}),
        }

    def clean_tempo_analise(self):
        valor = self.cleaned_data['tempo_analise']
        if valor is not None and valor < 1:
            raise forms.ValidationError('Informe pelo menos 1 mês.')
        return valor


class CriarUsuarioClienteSankhyaForm(forms.Form):
    username = forms.CharField(
        label='Usuário (login)',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'username'}),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )
    first_name = forms.CharField(
        label='Nome',
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    password_confirm = forms.CharField(
        label='Confirmar senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    def clean_username(self):
        u = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError('Já existe um usuário com este login.')
        return u

    def clean(self):
        data = super().clean()
        p1 = data.get('password')
        p2 = data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('As senhas não conferem.')
        return data


class ImportarUsuariosClienteSankhyaForm(forms.Form):
    planilha = forms.FileField(
        label='Planilha',
        help_text='Excel (.xlsx) ou CSV com as colunas Codigo_Cliente, Usuario, Nome, E-mail Gerado e Senha Gerada.',
        error_messages={'required': 'Selecione a planilha para importar.'},
        widget=forms.FileInput(
            attrs={
                'class': 'form-control',
                'accept': '.xlsx,.xlsm,.csv',
            }
        ),
    )

    def clean_planilha(self):
        arquivo = self.cleaned_data['planilha']
        nome = (arquivo.name or '').lower()
        if not nome.endswith(('.xlsx', '.xlsm', '.csv')):
            raise forms.ValidationError('Envie um arquivo .xlsx ou .csv.')
        if arquivo.size and arquivo.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Arquivo maior que 10 MB.')
        return arquivo


class AlterarSenhaUsuarioClienteForm(forms.Form):
    new_password = forms.CharField(
        label='Nova senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    new_password_confirm = forms.CharField(
        label='Confirmar nova senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    def clean(self):
        data = super().clean()
        p1 = data.get('new_password')
        p2 = data.get('new_password_confirm')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('As senhas não conferem.')
        return data

class VeiculoForm(forms.ModelForm):
    class Meta:
        model = Veiculo
        fields = [
            'placa',
            'codigo_erp',
            'descricao',
            'filial',
            'modelo',
            'tipo_veiculo',
            'ano_modelo',
            'ano_fabricacao',
            'tipo_combustivel',
            'qtd_max_entregas',
            'peso_max_entregas',
            'volume_max_entregas',
            'qtd_pallets_veiculo',
            'status_inicial',
            'km_atual',
            'velocidade_maxima'
        ]
        widgets = {
            'placa': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_erp': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'filial': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_veiculo': forms.Select(attrs={'class': 'form-select'}),
            'ano_modelo': forms.NumberInput(attrs={'class': 'form-control'}),
            'ano_fabricacao': forms.NumberInput(attrs={'class': 'form-control'}),
            'tipo_combustivel': forms.TextInput(attrs={'class': 'form-control'}),
            'qtd_max_entregas': forms.NumberInput(attrs={'class': 'form-control'}),
            'peso_max_entregas': forms.NumberInput(attrs={'class': 'form-control'}),
            'volume_max_entregas': forms.NumberInput(attrs={'class': 'form-control'}),
            'qtd_pallets_veiculo': forms.NumberInput(attrs={'class': 'form-control'}),
            'status_inicial': forms.Select(attrs={'class': 'form-select'}),
            'km_atual': forms.NumberInput(attrs={'class': 'form-control'}),
            'velocidade_maxima': forms.NumberInput(attrs={'class': 'form-control'})
        } 