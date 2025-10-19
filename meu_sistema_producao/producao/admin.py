from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Pn, Maquina, OrdemProducao, TipoParada, TipoRefugo, Refugo
from .resources import PnResource

@admin.register(Pn)
class PnAdmin(ImportExportModelAdmin):
    resource_class = PnResource
    class Media:
        css = {
            'all': ('producao/admin_custom.css',)
        }

@admin.register(Maquina)
class MaquinaAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('producao/admin_custom.css',)
        }

@admin.register(OrdemProducao)
class OrdemProducaoAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('producao/admin_custom.css',)
        }

@admin.register(TipoParada)
class TipoParadaAdmin(admin.ModelAdmin):
    """
    Customiza a exibição dos Tipos de Parada no admin.
    """
    list_display = ('codigo', 'descricao')
    search_fields = ('codigo', 'descricao')
    ordering = ('codigo',)

@admin.register(TipoRefugo)
class TipoRefugoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descricao')
    search_fields = ('codigo', 'descricao')
    ordering = ('codigo',)

@admin.register(Refugo)
class RefugoAdmin(admin.ModelAdmin):
    list_display = ('agendamento', 'tipo_refugo', 'quantidade', 'data_apontamento', 'operador')
    list_filter = ('tipo_refugo', 'data_apontamento', 'operador')
    search_fields = ('agendamento__ordem_producao__id', 'tipo_refugo__codigo', 'tipo_refugo__descricao')
    # readonly_fields = ('data_apontamento',) # Opcional: tornar a data apenas leitura

    # Opcional: Se quiser linkar para o agendamento
    def get_agendamento_link(self, obj):
        # Implemente se quiser um link para a página de admin do Agendamento
        pass
    # get_agendamento_link.short_description = 'Agendamento'