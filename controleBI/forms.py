from django import forms
from django.contrib.auth.models import User

from api_sankhya.models import Cliente as ClienteSankhya
from ecommerce.models import Campanha

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