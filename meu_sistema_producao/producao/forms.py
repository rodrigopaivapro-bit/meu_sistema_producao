# meu_sistema_producao/producao/forms.py

from django import forms
from captcha.fields import CaptchaField
from django.contrib.auth.forms import AuthenticationForm
from .models import OrdemProducao # Importe o modelo

class CustomLoginForm(AuthenticationForm):
    captcha = CaptchaField()
# NOVO FORMULÁRIO
class OrdemProducaoForm(forms.ModelForm):
    class Meta:
        model = OrdemProducao
        fields = ['pn', 'quantity', 'delivery_date'] # Escolha os campos que você quer exibir