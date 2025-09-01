from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Pn, Maquina, OrdemProducao, TipoParada
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