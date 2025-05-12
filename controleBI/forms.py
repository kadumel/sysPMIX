from django import forms
from .models import Veiculo

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