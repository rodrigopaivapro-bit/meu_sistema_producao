from django.contrib import admin
from django.urls import path, include
from .producao import views
from django.contrib.auth import views as auth_views
from django.views.generic.base import RedirectView
from .producao.forms import CustomLoginForm, OrdemProducaoForm

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='login/', permanent=False)),
    path('login/', auth_views.LoginView.as_view(template_name='producao/login.html', authentication_form=CustomLoginForm), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('captcha/', include('captcha.urls')),
    path('menu/', views.menu_view, name='menu'),
    path('planejamento/', views.planejamento_view, name='planejamento'),
    path('producao/', views.view_producao, name='view_producao'),
    path('api/get-pns/', views.get_pns_api, name='get_pns_api'),
    path('api/criar-op/', views.criar_op_api, name='criar_op_api'),
    path('api/salvar-agendamento/', views.salvar_agendamento_api, name='salvar_agendamento_api'),
    path('api/remover-agendamento/', views.remover_agendamento_api, name='remover_agendamento_api'),
    path('api/get_week_data/', views.get_week_data_api, name='get_week_data_api'),
    path('api/producao/dados_maquina/', views.get_dados_maquina_api, name='get_dados_maquina_api'),
    path('api/producao/iniciar_op/', views.iniciar_op_api, name='iniciar_op_api'),
    path('api/producao/apontar/', views.apontar_producao_api, name='apontar_producao_api'),
    path('api/producao/registrar_parada/', views.registrar_parada_api, name='registrar_parada_api'),
    path('api/producao/finalizar_op/', views.finalizar_op_api, name='finalizar_op_api'),
    path('api/producao/get_tipos_parada/', views.get_tipos_parada_api, name='get_tipos_parada_api'),
    path('api/get_tipos_refugo/', views.get_tipos_refugo_api, name='get_tipos_refugo_api'),
    path('api/registrar_refugo/', views.registrar_refugo_api, name='registrar_refugo_api'),
    path('gerenciamento/', views.gerenciamento_view, name='gerenciamento_view'),
    path('api/get_op_details/', views.get_op_details_api, name='get_op_details_api'),
]