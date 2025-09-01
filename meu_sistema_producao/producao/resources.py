# meu_sistema_producao/producao/resources.py

from import_export import resources
from .models import Pn

class PnResource(resources.ModelResource):
    class Meta:
        model = Pn
        # Mapeie os nomes das colunas da sua planilha para os campos do modelo.
        # Caso os nomes sejam diferentes, ajuste aqui. Ex: 'PN': 'pn_code'
        fields = ('cliente', 'pn_code', 'description', 'type_piece', 'property',
                  'capacity_liters', 'min_weight_kg', 'max_weight_kg',
                  'sold_weight_kg', 'cycle_time_seconds', 'cavity',
                  'dim_c', 'dim_a', 'dim_l',)
        # A sua planilha já está no formato certo, então não precisa de um mapeamento
        # complexo, mas é bom ter em mente essa funcionalidade.