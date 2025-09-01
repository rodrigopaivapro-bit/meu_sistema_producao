# meu_sistema_producao/producao/views.py

# Adicionado 'get_object_or_404' que estava faltando na importação
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
import json
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Pn, Maquina, OrdemProducao, Agendamento, ApontamentoProducao, Parada, TipoParada
from datetime import date


@login_required(login_url='login')
def menu_view(request):
    return render(request, 'producao/menu.html')


# =========================================================================
#             FUNÇÃO 'planejamento_view' CORRIGIDA E UNIFICADA
# =========================================================================
@login_required(login_url='login')
@permission_required('producao.can_view_planejamento', raise_exception=True)
def planejamento_view(request):
    maquinas = Maquina.objects.all()
    
    # Filtro para OPs relevantes para o planejamento
    ordens_disponiveis_qs = OrdemProducao.objects.filter(
        status__in=['Disponível', 'Planejada']
    ).order_by('delivery_date')

    ordens_disponiveis = []
    for op in ordens_disponiveis_qs:
        ordens_disponiveis.append({
            'op': op,
            'tempo_producao_horas': op.get_duracao_horas()
        })
    
    agendamentos_qs = Agendamento.objects.select_related('ordem_producao__pn', 'maquina').all()
    todos_ids_agendados = list(Agendamento.objects.values_list('ordem_producao_id', flat=True))
    
    agendamentos_iniciais_formatado = []
    for agendamento in agendamentos_qs:
        if agendamento.ordem_producao.status in ['Disponível', 'Planejada']:
            
            # =======================================================================
            # CORREÇÃO FINAL DE HORA E DURAÇÃO
            # =======================================================================
            
            # 1. Converte o datetime do banco (que está em UTC) para o fuso horário local
            local_start_time = timezone.localtime(agendamento.start_datetime)
            
            agendamentos_iniciais_formatado.append({
                'opId': agendamento.ordem_producao.id,
                'maquinaId': agendamento.maquina.id,
                'day': local_start_time.weekday(), # Pega o dia da semana do horário local
                'hour': local_start_time.hour,     # <<< USA A HORA LOCAL CORRETA
            })

            todos_ids_agendados = list(Agendamento.objects.values_list('ordem_producao_id', flat=True))
            # =======================================================================

    context = {
        'maquinas': maquinas,
        'ordens_disponiveis': ordens_disponiveis,
        'agendamentos_iniciais': json.dumps(agendamentos_iniciais_formatado),
        'todos_ids_agendados': json.dumps(todos_ids_agendados),
    }
    
    return render(request, 'producao/planejamento_view.html', context)

# =========================================================================
#                     VIEWS PARA A API DO PLANEJADOR
# =========================================================================

@require_POST
@login_required
def salvar_agendamento_api(request):
    try:
        data = json.loads(request.body)
        op_id = data.get('op_id')
        maquina_id = data.get('maquina_id')
        start_date_str = data.get('start_date')
        start_hour = int(data.get('start_hour'))

        op = get_object_or_404(OrdemProducao, id=op_id)
        maquina = get_object_or_404(Maquina, id=maquina_id)

        tempo_producao_horas = (op.quantity * op.pn.cycle_time_seconds) / 3600
        start_datetime = datetime.strptime(start_date_str, '%Y-%m-%d').replace(hour=start_hour)
        end_datetime = start_datetime + timedelta(hours=tempo_producao_horas)

        op.status = 'Planejada'
        op.save()

        agendamento, created = Agendamento.objects.update_or_create(
            ordem_producao=op,
            defaults={
                'maquina': maquina,
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
            }
        )
        return JsonResponse({'status': 'sucesso', 'mensagem': 'OP agendada com sucesso!'})
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)


@require_POST
@login_required
def remover_agendamento_api(request):
    try:
        data = json.loads(request.body)
        op_id = data.get('op_id')
        
        # Busca o agendamento usando o ID da Ordem de Produção
        agendamento = get_object_or_404(Agendamento, ordem_producao__id=op_id)
        
        # =======================================================================
        # AJUSTE: ATUALIZAR O STATUS DA OP ANTES DE REMOVER O AGENDAMENTO
        # =======================================================================
        # 1. Pega a Ordem de Produção a partir do agendamento que encontramos
        op = agendamento.ordem_producao
        
        # 2. Altera o status dela de volta para 'Disponível'
        op.status = 'Disponível'
        
        # 3. Salva a alteração na Ordem de Produção
        op.save()
        # =======================================================================

        # Agora, remove o agendamento
        agendamento.delete()
        
        return JsonResponse({'status': 'sucesso', 'mensagem': 'Agendamento removido com sucesso!'})
        
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)

# =========================================================================
#                     VIEWS PARA A API DO MODAL
# =========================================================================

@login_required(login_url='login')
@require_http_methods(["GET"])
def get_pns_api(request):
    pns = Pn.objects.all().values('id', 'pn_code', 'capacity_liters')
    return JsonResponse(list(pns), safe=False)


@require_POST
def criar_op_api(request):
    # =========================================================================
    # CORREÇÃO: Verificação de login e permissão feita manualmente para a API
    # =========================================================================
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'erro', 'mensagem': 'Autenticação necessária.'}, status=401)
    
    if not request.user.has_perm('producao.add_ordemproducao'):
        return JsonResponse({'status': 'erro', 'mensagem': 'Você não tem permissão para criar uma OP.'}, status=403)
    # =========================================================================

    try:
        data = json.loads(request.body)
        pn_id = data.get('pn_id')
        quantity = data.get('quantity')
        delivery_date = data.get('delivery_date')

        if not all([pn_id, quantity, delivery_date]):
            return JsonResponse({'status': 'erro', 'mensagem': 'Todos os campos são obrigatórios.'}, status=400)

        pn = Pn.objects.get(id=pn_id)
        
        nova_op = OrdemProducao.objects.create(
            pn=pn,
            quantity=int(quantity),
            delivery_date=delivery_date,
            status='Disponível'
        )
        return JsonResponse({'status': 'sucesso', 'mensagem': f'OP {nova_op.id} criada com sucesso!'})

    except Pn.DoesNotExist:
        return JsonResponse({'status': 'erro', 'mensagem': 'O Produto (PN) selecionado não existe.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': f'Ocorreu um erro no servidor: {str(e)}'}, status=500)


# =======================================================================
# NOVA API PARA BUSCAR DADOS DA SEMANA
# =======================================================================
def get_week_data_api(request):
    # Pega a data de início da semana que veio do JavaScript
    start_date_str = request.GET.get('start_date')
    if not start_date_str:
        return JsonResponse({'status': 'erro', 'mensagem': 'Data de início não fornecida.'}, status=400)

    # Converte a string de data (YYYY-MM-DD) para um objeto date do Python
    start_of_week = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
    # Calcula o fim da semana (início + 6 dias)
    end_of_week = start_of_week + timedelta(days=6)

    # Filtra os agendamentos que estão DENTRO do intervalo da semana
    agendamentos_da_semana = Agendamento.objects.filter(
        start_datetime__date__range=[start_of_week, end_of_week]
    ).select_related('ordem_producao__pn', 'maquina')

    # Formata os dados para enviar de volta ao JavaScript (mesmo formato de antes)
    agendamentos_formatados = []
    for agendamento in agendamentos_da_semana:
        local_start_time = timezone.localtime(agendamento.start_datetime)
        agendamentos_formatados.append({
            'opId': agendamento.ordem_producao.id,
            'maquinaId': agendamento.maquina.id,
            'day': local_start_time.weekday(),
            'hour': local_start_time.hour,
            'duration': agendamento.ordem_producao.get_duracao_horas(),
        })

    return JsonResponse(agendamentos_formatados, safe=False)

# =======================================================================
# NOVAS VIEWS E APIS PARA A TELA DE PRODUÇÃO
# =======================================================================

@login_required(login_url='login')
# Protege a view com uma nova permissão que você precisa criar
@permission_required('producao.can_view_producao', raise_exception=True) 
def view_producao(request):
    """Renderiza a página principal de produção para o operador."""
    maquinas = Maquina.objects.all()
    context = {
        'maquinas': maquinas
    }
    return render(request, 'producao/view_producao.html', context)


# --- APIs ---

@login_required
def get_dados_maquina_api(request):
    """
    Retorna as OPs (em produção e próxima) para uma máquina específica,
    incluindo detalhes técnicos completos do PN.
    """
    maquina_id = request.GET.get('maquina_id')
    hoje = date.today() # Mantendo sua lógica atual de buscar por hoje

    agendamentos_hoje = Agendamento.objects.filter(
        maquina_id=maquina_id,
        start_datetime__date=hoje
    ).select_related('ordem_producao__pn').order_by('start_datetime')

    op_em_producao_ag = agendamentos_hoje.filter(ordem_producao__status='Em Produção').first()
    proxima_op_ag = agendamentos_hoje.filter(ordem_producao__status='Planejada').first()

    def formatar_op(agendamento):
        if not agendamento:
            return None
        
        op = agendamento.ordem_producao
        pn = op.pn

        # =======================================================================
        # CORREÇÃO DOS ERROS DE DIGITAÇÃO APLICADA ABAIXO
        # 'wheight' foi trocado por 'weight'
        # =======================================================================
        return {
            'agendamento_id': agendamento.id,
            'op_id': op.id,
            'pn_code': pn.pn_code,
            'description': pn.description,
            'capacity_liters': pn.capacity_liters,
            'cycle_time_seconds': pn.cycle_time_seconds,
            'min_weight_kg': pn.min_weight_kg,   # Corrigido
            'max_weight_kg': pn.max_weight_kg,   # Corrigido
            'sold_weight_kg': pn.sold_weight_kg,    # Corrigido
            'quantidade_total': op.quantity,
            'quantidade_produzida': op.quantidade_produzida,
            'status': op.status
        }
        # =======================================================================

    dados = {
        'op_em_producao': formatar_op(op_em_producao_ag),
        'proxima_op': formatar_op(proxima_op_ag)
    }
    return JsonResponse(dados)

@login_required
def iniciar_op_api(request):
    data = json.loads(request.body)
    op = get_object_or_404(OrdemProducao, id=data.get('op_id'))
    op.status = 'Em Produção'
    op.save()
    return JsonResponse({'status': 'sucesso', 'mensagem': 'OP iniciada!'})

@login_required
def apontar_producao_api(request):
    data = json.loads(request.body)
    agendamento = get_object_or_404(Agendamento, id=data.get('agendamento_id'))
    quantidade = int(data.get('quantidade'))
    
    ApontamentoProducao.objects.create(
        agendamento=agendamento,
        quantidade=quantidade,
        operador=request.user
    )
    
    # Atualiza o total produzido na OP
    op = agendamento.ordem_producao
    op.quantidade_produzida += quantidade
    op.save()
    
    return JsonResponse({
        'status': 'sucesso', 
        'mensagem': 'Apontamento registrado!',
        'nova_quantidade_produzida': op.quantidade_produzida
    })

@login_required
def get_tipos_parada_api(request):
    """Retorna uma lista de todos os tipos de parada cadastrados."""
    tipos_parada = TipoParada.objects.all().values('id', 'codigo', 'descricao')
    return JsonResponse(list(tipos_parada), safe=False) 

# =======================================================================
# API DE REGISTRAR PARADA ATUALIZADA PARA RECEBER DATAS MANUAIS
# =======================================================================
@login_required
def registrar_parada_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            agendamento = get_object_or_404(Agendamento, id=data.get('agendamento_id'))
            tipo_parada_id = data.get('tipo_parada_id')
            
            # 1. Recebe as datas de início e fim como strings
            inicio_parada_str = data.get('inicio_parada')
            fim_parada_str = data.get('fim_parada')

            # 2. Valida se todos os campos necessários foram enviados
            if not all([tipo_parada_id, inicio_parada_str, fim_parada_str]):
                return JsonResponse({'status': 'erro', 'mensagem': 'Todos os campos são obrigatórios.'}, status=400)

            # 3. Converte as strings para objetos datetime "cientes" do fuso horário
            inicio_parada = timezone.make_aware(datetime.fromisoformat(inicio_parada_str))
            fim_parada = timezone.make_aware(datetime.fromisoformat(fim_parada_str))

            # 4. Valida se a data de fim é posterior à de início
            if fim_parada <= inicio_parada:
                return JsonResponse({'status': 'erro', 'mensagem': 'O horário de fim deve ser posterior ao de início.'}, status=400)
            
            # 5. Cria o objeto Parada com os dados fornecidos pelo usuário
            Parada.objects.create(
                agendamento=agendamento,
                tipo_parada_id=tipo_parada_id,
                inicio_parada=inicio_parada,
                fim_parada=fim_parada,
                operador=request.user
            )

            return JsonResponse({'status': 'sucesso', 'mensagem': 'Parada registrada com sucesso!'})

        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)
            
    return JsonResponse({'status': 'erro', 'mensagem': 'Método inválido.'}, status=405)

@login_required
def finalizar_op_api(request):
    data = json.loads(request.body)
    op = get_object_or_404(OrdemProducao, id=data.get('op_id'))
    op.status = 'Concluída'
    op.save()

    # Finaliza paradas abertas para esta OP, se houver
    agendamento = Agendamento.objects.filter(ordem_producao=op).first()
    if agendamento:
        Parada.objects.filter(agendamento=agendamento, fim_parada__isnull=True).update(fim_parada=timezone.now())

    return JsonResponse({'status': 'sucesso', 'mensagem': 'OP finalizada!'})