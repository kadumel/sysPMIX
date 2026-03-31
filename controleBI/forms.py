from django import forms
from django.contrib.auth.models import User

from .models import Veiculo


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