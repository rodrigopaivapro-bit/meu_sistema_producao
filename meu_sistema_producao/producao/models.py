from django.db import models
from django.conf import settings

class Pn(models.Model):
    """
    Modelo para o cadastro de Part Numbers (PNs).
    """
    cliente = models.CharField(max_length=100)
    pn_code = models.CharField(max_length=50, unique=True, verbose_name="PN")
    description = models.CharField(max_length=200, verbose_name="Descrição")
    type_piece = models.CharField(max_length=50, verbose_name="Tipo")
    property = models.CharField(max_length=50, verbose_name="Propriedade")
    capacity_liters = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Capacidade (Litros)")
    min_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Peso Mín (Kg)")
    max_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Peso Máx (Kg)")
    sold_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Peso Vendido (Kg)")
    cycle_time_seconds = models.IntegerField(verbose_name="Tempo de Ciclo (segundos)")
    cavity = models.IntegerField(verbose_name="Cavidade")
    dim_c = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Dimensão C")
    dim_a = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Dimensão A")
    dim_l = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Dimensão L")

    def __str__(self):
        return self.pn_code

    class Meta:
        permissions = [
            ('can_view_planejamento', 'Pode visualizar a página de planejamento'),
            ("can_view_producao", "Pode visualizar a tela de produção"),
        ]
        verbose_name = 'PN'
        verbose_name_plural = 'Part Numbers'

class Maquina(models.Model):
    """
    Modelo para o cadastro de Máquinas.
    """
    number = models.CharField(max_length=50, unique=True, verbose_name="Número da Máquina")
    capacity_liters = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Capacidade (Litros)")
    mold_dim_c = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Dimensão C (Molde)")
    mold_dim_a = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Dimensão A (Molde)")
    mold_dim_l = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Dimensão L (Molde)")
    
    def __str__(self):
        return self.number
    
    class Meta: # Garanta que esta seja a única classe Meta
        verbose_name = 'Máquina'
        verbose_name_plural = 'Máquinas'

class OrdemProducao(models.Model):
    """
    Modelo para o cadastro de Ordens de Produção (OPs).
    """
    pn = models.ForeignKey(Pn, on_delete=models.CASCADE, verbose_name="PN")
    quantity = models.IntegerField(verbose_name="Quantidade")
    delivery_date = models.DateField(verbose_name="Data de Entrega")
    STATUS_CHOICES = [
        ('Disponível', 'Disponível'),
        ('Planejada', 'Planejada'),
        ('Em Produção', 'Em Produção'),
        ('Concluída', 'Concluída'),
    ]

    pn = models.ForeignKey(Pn, on_delete=models.CASCADE, verbose_name="PN")
    quantity = models.IntegerField(verbose_name="Quantidade")
    delivery_date = models.DateField(verbose_name="Data de Entrega")
    quantidade_produzida = models.IntegerField(default=0, verbose_name="Quantidade Produzida")
    
    # =======================================================================
    # NOVO CAMPO ADICIONADO AQUI
    # =======================================================================
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Disponível', # Garante que toda nova OP comece como "Disponível"
        verbose_name="Status"
    )
    def get_duracao_horas(self):
        tempo_ciclo_segundos = self.pn.cycle_time_seconds
        quantidade_a_produzir = self.quantity
        if not tempo_ciclo_segundos or tempo_ciclo_segundos <= 0:
            return 1.0

        # 1. Calcula o tempo total de produção em segundos
        total_segundos = tempo_ciclo_segundos * quantidade_a_produzir
        
        # 2. Converte o total de segundos para horas, mantendo a precisão
        total_horas = total_segundos / 3600.0

        # 3. Retorna o valor exato, sem nenhum arredondamento
        return total_horas

    def __str__(self):
        return f"OP de {self.pn.pn_code} - Qtd: {self.quantity}"
    
    class Meta:
        verbose_name = 'Ordem de Produção'
        verbose_name_plural = 'Ordens de Produção'

class Agendamento(models.Model):
    """
    Modelo para armazenar o planejamento de uma Ordem de Produção em uma Máquina.
    """
    ordem_producao = models.ForeignKey(OrdemProducao, on_delete=models.CASCADE, verbose_name="Ordem de Produção")
    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE, verbose_name="Máquina")
    start_datetime = models.DateTimeField(verbose_name="Início do Agendamento")
    end_datetime = models.DateTimeField(verbose_name="Fim do Agendamento")
    LADO_CHOICES = (
        ('L', 'Esquerdo'),
        ('R', 'Direito'),
    )
    lado = models.CharField(
        max_length=1, 
        choices=LADO_CHOICES, 
        null=True, 
        blank=True
    )
    def __str__(self):
        return f"{self.ordem_producao} na {self.maquina} em {self.start_datetime.strftime('%d/%m/%Y %H:%M')}"
    class Meta:
        verbose_name = 'Agendamento'
        verbose_name_plural = 'Agendamentos'
        # Garante que uma mesma OP não possa ser agendada duas vezes.
        unique_together = ('ordem_producao',)

# NOVO MODELO: Para registrar cada apontamento de produção
class ApontamentoProducao(models.Model):
    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE, related_name="apontamentos")
    quantidade = models.IntegerField(verbose_name="Quantidade Apontada")
    data_apontamento = models.DateTimeField(auto_now_add=True, verbose_name="Data do Apontamento")
    operador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.quantidade} un. na OP {self.agendamento.ordem_producao.id} em {self.data_apontamento}"

class TipoParada(models.Model):
    codigo = models.CharField(max_length=20, unique=True, verbose_name="Código da Parada")
    descricao = models.CharField(max_length=255, verbose_name="Descrição")

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"

    class Meta:
        verbose_name = "Tipo de Parada"
        verbose_name_plural = "Tipos de Parada"

class Parada(models.Model):
    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE, related_name="paradas")
    tipo_parada = models.ForeignKey(TipoParada, on_delete=models.PROTECT, verbose_name="Tipo de Parada", null=True)
    inicio_parada = models.DateTimeField(verbose_name="Início da Parada")
    fim_parada = models.DateTimeField(verbose_name="Fim da Parada")
    operador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        if self.tipo_parada:
            return f"Parada na OP {self.agendamento.ordem_producao.id}: {self.tipo_parada.descricao}"
        return f"Parada na OP {self.agendamento.ordem_producao.id}: (Tipo não definido)"

class TipoRefugo(models.Model):
    codigo = models.CharField(max_length=20, unique=True, verbose_name="Código do Refugo")
    descricao = models.CharField(max_length=255, verbose_name="Descrição")

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"

    class Meta:
        verbose_name = "Tipo de Refugo"
        verbose_name_plural = "Tipos de Refugo"

class Refugo(models.Model):
    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE, related_name="refugos")
    tipo_refugo = models.ForeignKey(TipoRefugo, on_delete=models.PROTECT, verbose_name="Tipo de Refugo") # PROTECT evita excluir um tipo se ele já foi usado
    quantidade = models.IntegerField(verbose_name="Quantidade Refugada")
    data_apontamento = models.DateTimeField(auto_now_add=True, verbose_name="Data do Apontamento")
    operador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.quantidade} un. refugo ({self.tipo_refugo.codigo}) na OP {self.agendamento.ordem_producao.id}"

    class Meta:
        verbose_name = "Apontamento de Refugo"
        verbose_name_plural = "Apontamentos de Refugo"