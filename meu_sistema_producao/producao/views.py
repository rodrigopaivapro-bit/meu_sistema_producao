# meu_sistema_producao/producao/views.py

# Adicionado 'get_object_or_404' que estava faltando na importação
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
import json
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Pn, Maquina, OrdemProducao, Agendamento, ApontamentoProducao, Parada, TipoParada, TipoRefugo, Refugo
from datetime import date
from django.db.models import Sum, F, ExpressionWrapper, fields
from django.db.models.functions import Coalesce


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
                'id': agendamento.id, # [CORREÇÃO] Envia o ID do agendamento
                'opId': agendamento.ordem_producao.id,
                'maquinaId': agendamento.maquina.id,
                'day': local_start_time.weekday(), 
                'hour': local_start_time.hour,
                'duration': agendamento.ordem_producao.get_duracao_horas(), # [CORREÇÃO] Envia a duração
                'lado': agendamento.lado # [CORREÇÃO] Envia o lado
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
        lado_recebido = data.get('lado')

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
                'lado': lado_recebido,
                'real_start_datetime': None
            }
        )
        
        agendamento_data = {
            'opId': op.id,
            'maquinaId': maquina.id,
            'day': start_datetime.weekday(),  # Monday=0, Sunday=6 (corresponde ao JS)
            'hour': start_datetime.hour,
            'duration': round(tempo_producao_horas, 4), # Retorna a duração precisa
            'lado': agendamento.lado
        }

        return JsonResponse({
            'status': 'sucesso', 
            'mensagem': f'OP-{op.id} agendada com sucesso!',
            'agendamento': agendamento_data  # <-- A MUDANÇA PRINCIPAL!
        })

    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)


@require_POST
@login_required
def remover_agendamento_api(request):
    try:
        data = json.loads(request.body)
        agendamento_id = data.get('agendamento_id')
        
        # Busca o agendamento usando o ID da Ordem de Produção
        agendamento = get_object_or_404(Agendamento, id=agendamento_id)
        
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
        agendamento.real_start_datetime = None
        agendamento.save()
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
            'id': agendamento.id, # [CORREÇÃO] Envia o ID do agendamento
            'opId': agendamento.ordem_producao.id,
            'maquinaId': agendamento.maquina.id,
            'day': local_start_time.weekday(),
            'hour': local_start_time.hour,
            'duration': agendamento.ordem_producao.get_duracao_horas(),
            'lado': agendamento.lado # [CORREÇÃO] Envia o lado
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
    hoje = date.today() 
    
    # =======================================================================
    # CORREÇÃO APLICADA AQUI
    # =======================================================================

    # 1. BUSCA OPs EM PRODUÇÃO:
    #    Filtra apenas pela máquina e pelo status, IGNORANDO a data.
    #    A OP só sairá daqui quando o status for 'Concluída'.
    ops_em_producao_ag = Agendamento.objects.filter(
        maquina_id=maquina_id,
        ordem_producao__status='Em Produção'
    ).select_related('ordem_producao__pn').order_by('start_datetime')

    # 2. BUSCA PRÓXIMAS OPs:
    #    Filtra pela máquina, status 'Planejada' e data A PARTIR DE HOJE.
    #    Usar '__gte=hoje' (maior ou igual) garante que OPs planejadas
    #    para hoje ou dias futuros sejam listadas.
    proximas_ops_ag = Agendamento.objects.filter(
        maquina_id=maquina_id,
        ordem_producao__status='Planejada',
        start_datetime__date__gte=hoje 
    ).select_related('ordem_producao__pn').order_by('start_datetime')

    # =======================================================================
    # FIM DA CORREÇÃO
    # =======================================================================

    def formatar_op(agendamento):
        if not agendamento:
            return None
        
        op = agendamento.ordem_producao
        pn = op.pn

        inicio_local = timezone.localtime(agendamento.start_datetime)
        inicio_formatado = inicio_local.strftime('%d/%m %H:%M')

        return {
            'agendamento_id': agendamento.id,
            'op_id': op.id,
            'lado': agendamento.lado, 
            'pn_code': pn.pn_code,
            'description': pn.description,
            'capacity_liters': pn.capacity_liters,
            'cycle_time_seconds': pn.cycle_time_seconds,
            'min_weight_kg': pn.min_weight_kg,
            'max_weight_kg': pn.max_weight_kg,
            'sold_weight_kg': pn.sold_weight_kg,
            'quantidade_total': op.quantity,
            'quantidade_produzida': op.quantidade_produzida,
            'status': op.status,
            'inicio_agendado': inicio_formatado
        }

    # Esta parte já estava correta, pois o JS espera listas
    dados = {
        'ops_em_producao': [formatar_op(ag) for ag in ops_em_producao_ag],
        'proximas_ops': [formatar_op(ag) for ag in proximas_ops_ag]
    }
    return JsonResponse(dados)

@require_POST # Adicionado decorador de segurança
@login_required
def iniciar_op_api(request):
    try:
        data = json.loads(request.body)
        maquina_id = data.get('maquina_id')
        if not maquina_id:
            return JsonResponse({'status': 'erro', 'mensagem': 'ID da máquina não fornecido.'}, status=400)

        # 1. Encontra todos os agendamentos "Planejados" para esta máquina
        #    (Removido o filtro de 'start_datetime__date=hoje' que causava o bug)
        agendamentos_para_iniciar = Agendamento.objects.filter(
            maquina_id=maquina_id,
            ordem_producao__status='Planejada'
        )
        
        if not agendamentos_para_iniciar.exists():
            # Retorna 404 (Não Encontrado) para o frontend detectar o erro
            return JsonResponse({'status': 'info', 'mensagem': 'Nenhuma OP "Planejada" encontrada para esta máquina.'}, status=404)

        # =======================================================================
        # CORREÇÃO DE LÓGICA (INVERTER ORDEM)
        # =======================================================================

        # 1. PRIMEIRO, grava o 'real_start_datetime'
        #    (Enquanto o status ainda é 'Planejada' e a query funciona)
        agendamentos_para_iniciar.filter(real_start_datetime__isnull=True).update(
            real_start_datetime=timezone.now()
        )
        
        # 2. SEGUNDO, atualiza o status das OPs
        op_ids_para_iniciar = agendamentos_para_iniciar.values_list('ordem_producao_id', flat=True)
        OrdemProducao.objects.filter(id__in=op_ids_para_iniciar).update(status='Em Produção')
        
        # =======================================================================
        # FIM DA CORREÇÃO DE LÓGICA
        # =======================================================================

        return JsonResponse({'status': 'sucesso', 'mensagem': 'OPs iniciadas com sucesso!'})
        
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)

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

@login_required
def get_tipos_refugo_api(request):
    """Retorna uma lista de todos os tipos de refugo cadastrados."""
    tipos_refugo = TipoRefugo.objects.all().values('id', 'codigo', 'descricao')
    return JsonResponse(list(tipos_refugo), safe=False)

@require_POST
@login_required
def registrar_refugo_api(request):
    """Registra um novo apontamento de refugo."""
    try:
        data = json.loads(request.body)
        agendamento_id = data.get('agendamento_id')
        tipo_refugo_id = data.get('tipo_refugo_id')
        quantidade = data.get('quantidade')

        # Validações básicas
        if not all([agendamento_id, tipo_refugo_id, quantidade]):
            return JsonResponse({'status': 'erro', 'mensagem': 'Dados incompletos.'}, status=400)
        
        try:
            quantidade_int = int(quantidade)
            if quantidade_int <= 0:
                raise ValueError("Quantidade deve ser positiva.")
        except ValueError:
            return JsonResponse({'status': 'erro', 'mensagem': 'Quantidade inválida.'}, status=400)

        # Busca os objetos no banco
        agendamento = get_object_or_404(Agendamento, id=agendamento_id)
        tipo_refugo = get_object_or_404(TipoRefugo, id=tipo_refugo_id)

        # Cria o registro de Refugo
        Refugo.objects.create(
            agendamento=agendamento,
            tipo_refugo=tipo_refugo,
            quantidade=quantidade_int,
            operador=request.user 
        )

        return JsonResponse({'status': 'sucesso', 'mensagem': 'Refugo registrado com sucesso!'})

    except Exception as e:
        # Logar o erro aqui seria uma boa prática
        print(f"Erro ao registrar refugo: {e}") 
        return JsonResponse({'status': 'erro', 'mensagem': 'Erro interno ao registrar refugo.'}, status=500)

@login_required(login_url='login')
@permission_required('producao.can_view_gerenciamento', raise_exception=True)
def gerenciamento_view(request):
    """
    MODIFICADO (Passo 2):
    Exibe o dashboard com lógica de OEE corrigida (Peças Brutas) e
    usa o 'real_start_datetime' para o cálculo de Eficiência.
    """
    
    # Busca IDs de máquinas com OPs "Em Produção"
    maquinas_ativas_set = set(Agendamento.objects.filter(
        ordem_producao__status='Em Produção'
    ).values_list('maquina_id', flat=True).distinct())

    # Busca TODAS as máquinas
    maquinas = Maquina.objects.all()
    maquinas_com_kpi = []
    agora = timezone.now()

    for maquina in maquinas:
        
        if maquina.id in maquinas_ativas_set:
            # --- MÁQUINA ATIVA ---
            
            # Pega os agendamentos desta máquina que estão "Em Produção"
            agendamentos_da_maquina = Agendamento.objects.filter(
                maquina=maquina,
                ordem_producao__status='Em Produção'
            ).select_related('ordem_producao__pn')

            # Variáveis para acumular os totais da MÁQUINA
            total_pecas_boas = 0
            total_pecas_ruins = 0
            total_produzido_bruto = 0
            total_pecas_teoricas = 0 # Denominador da Eficiência

            for ag in agendamentos_da_maquina:
                op = ag.ordem_producao
                pn = op.pn

                # --- 1. LÓGICA DE DEFINIÇÃO DE PEÇAS (CORRIGIDA) ---
                
                # Peças Boas = Total de apontamentos de produção
                pecas_boas_ag = op.quantidade_produzida
                
                # Peças Ruins = Total de apontamentos de refugo
                refugo_do_ag = Refugo.objects.filter(agendamento=ag).aggregate(
                    total=Coalesce(Sum('quantidade'), 0)
                )['total']
                pecas_ruins_ag = refugo_do_ag

                # Acumula totais
                total_pecas_boas += pecas_boas_ag
                total_pecas_ruins += pecas_ruins_ag
                
                # Peças Brutas = Soma das boas + ruins
                total_produzido_bruto += (pecas_boas_ag + pecas_ruins_ag)

                # --- 2. EFICIÊNCIA (Cálculo do Denominador - PEÇAS TEÓRICAS) ---
                
                # [MODIFICADO] Usa o tempo de início REAL
                inicio_real_da_op = ag.real_start_datetime 
                
                # Se a OP não foi iniciada (não tem data real) ou se o PN não tem ciclo,
                # não podemos calcular a eficiência para este agendamento.
                if not inicio_real_da_op or not pn.cycle_time_seconds or pn.cycle_time_seconds <= 0:
                    continue

                ciclo_teorico_segundos = pn.cycle_time_seconds

                # 2. Calcular o "Tempo Medido" (desde o início real até agora)
                duracao_bruta = agora - inicio_real_da_op
                tempo_total_bruto_segundos = duracao_bruta.total_seconds()
                if tempo_total_bruto_segundos < 0:
                    tempo_total_bruto_segundos = 0

                # 3. Calcular o "Tempo Parado" (soma das paradas registradas)
                duracao_parada_expr = ExpressionWrapper(
                    F('fim_parada') - F('inicio_parada'), 
                    output_field=fields.DurationField()
                )
                soma_paradas = Parada.objects.filter(
                    agendamento=ag, 
                    fim_parada__isnull=False # Apenas paradas concluídas
                ).aggregate(
                    total=Coalesce(Sum(duracao_parada_expr), timedelta(seconds=0))
                )
                tempo_parado_segundos = soma_paradas['total'].total_seconds()

                # 4. Calcular o "Tempo Operacional" (Tempo Medido - Tempo Parado)
                tempo_produzindo_segundos = tempo_total_bruto_segundos - tempo_parado_segundos
                if tempo_produzindo_segundos < 0:
                    tempo_produzindo_segundos = 0

                # 5. Calcular o Denominador (Qtd Teórica = Tempo Operacional / Ciclo Teórico)
                qtd_deveria_produzir_ag = tempo_produzindo_segundos / ciclo_teorico_segundos
                
                total_pecas_teoricas += qtd_deveria_produzir_ag

            # --- FIM DO LOOP DE AGENDAMENTOS DA MÁQUINA ---

            # --- CÁLCULO FINAL DOS KPIs DA MÁQUINA (CORRIGIDO) ---
            
            # A. QUALIDADE (Corrigida)
            # (Peças Boas / Peças Brutas)
            if total_produzido_bruto > 0:
                qualidade = (total_pecas_boas / total_produzido_bruto) * 100
            else:
                qualidade = 100.0 # Se não fez nada (bruto=0), qualidade é 100%

            # B. EFICIÊNCIA (Corrigida)
            # (Peças Brutas / Peças Teóricas)
            if total_pecas_teoricas > 0:
                eficiencia = (total_produzido_bruto / total_pecas_teoricas) * 100
            else:
                # Se o tempo foi 0 (ou ciclo 0), não deveria produzir nada.
                # Se produziu 0 (bruto=0), eficiência 100%. Se produziu >0, eficiência >100%.
                eficiencia = 100.0 if total_produzido_bruto == 0 else 200.0 # Define um teto ou 100%
            
            # C. DISPONIBILIDADE (Placeholder)
            # TODO: Substituir pela fórmula real quando definida.
            disponibilidade = 95.0 # Mantido fixo, conforme solicitado.
            
            # D. OEE
            oee = (disponibilidade / 100) * (eficiencia / 100) * (qualidade / 100) * 100
            
            maquinas_com_kpi.append({
                'status': 'Ativa',
                'nome': maquina.number,
                'oee': oee,
                'disponibilidade': disponibilidade,
                'eficiencia': eficiencia,
                'qualidade': qualidade,
            })
            
        else:
            # --- MÁQUINA INATIVA ---
            maquinas_com_kpi.append({
                'status': 'Inativa',
                'nome': maquina.number,
                'oee': 0.0,
                'disponibilidade': 0.0,
                'eficiencia': 0.0,
                'qualidade': 0.0,
            })
        
    context = {
        'maquinas_com_kpi': maquinas_com_kpi
    }
    
    return render(request, 'producao/gerenciamento_view.html', context)