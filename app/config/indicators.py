"""
Configurações dos indicadores de tendência
Arquivo centralizado para gerenciar todos os indicadores disponíveis

GUIA DE CONFIGURAÇÃO:
====================

Este arquivo controla como cada indicador técnico funciona no sistema.
Cada indicador pode ser personalizado através dos parâmetros abaixo.

PERFIS DE RISCO RECOMENDADOS:
=============================

🔴 ALTO RISCO (Agressivo):
- enabled: True para todos
- weight_formula: valores menores (mais sinais)
- validation_rule: menos restritiva

🟡 MÉDIO RISCO (Equilibrado):
- enabled: True para BB, EMA, HMA 
- weight_formula: valores padrão
- validation_rule: padrão

🟢 BAIXO RISCO (Conservador):
- enabled: True apenas para BB e HMA
- weight_formula: valores maiores (menos sinais)
- validation_rule: mais restritiva

PARÂMETROS EXPLICADOS:
=====================

enabled: True/False - Liga/desliga o indicador
function_name: Nome da função original no código
module: Módulo onde está a função
adapter_class: Classe que adapta a função ao sistema dinâmico
params: Parâmetros passados para o cálculo do indicador
weight_formula: Como calcular o peso do indicador no consenso
min_data_points: Mínimo de candles necessários
validation_rule: Regra para considerar o indicador válido
display_name: Nome amigável para logs
returns_tuple: Se a função retorna tupla ou valor único
result_mapping: Como mapear os valores retornados
"""

# ====================================================================
# CONFIGURAÇÃO DOS INDICADORES
# ====================================================================

INDICATOR_CONFIG = {
    # ================================================================
    # BANDAS DE BOLLINGER - Indicador Principal
    # ================================================================
    # Detecta volatilidade e pontos de reversão
    # Mais confiável em mercados laterais
    'BB': {
        'enabled': True,                    # ✅ Sempre ativo (principal indicador)
        'function_name': 'should_trade_bollinger',
        'module': 'app.bollinger_analysis',
        'adapter_class': 'BollingerBandsAdapter',
        
        # Parâmetros do cálculo das Bandas de Bollinger
        'params': {
            'window': 10,               # Período para média móvel (padrão: 10)
            'window_dev': 1.5          # Multiplicador desvio padrão (padrão: 1.5)
        },
        
        # Sistema de peso e validação
        'weight_formula': 'strength * 25',     # Alto peso por ser indicador principal
        'weight_max': 25,                      # Peso máximo possível
        'min_data_points': 10,                 # Mínimo de candles para funcionar
        'validation_rule': 'should_trade and trend not in [None, "SIDEWAYS"]',
        
        # Interface e logs
        'display_name': 'Bollinger Bands',
        'log_format': 'trend={trend}, strength={strength:.3f}, should_trade={should_trade}',
        'returns_tuple': True,                 # Retorna: (should_trade, trend, strength)
        'result_mapping': {
            'should_trade': 0,  # Índice 0 da tupla
            'trend': 1,         # Índice 1 da tupla  
            'strength': 2       # Índice 2 da tupla
        }
    },
    
    # ================================================================
    # EMA TREND - Análise de Tendência por Médias Exponenciais
    # ================================================================
    # Detecta direção da tendência através do cruzamento de EMAs
    # Mais eficaz em tendências claras
    'EMA': {
        'enabled': True,                    # ✅ Ativo (complementar)
        'function_name': 'analyze_ema_trend',
        'module': 'app.trend_analysis',
        'adapter_class': 'EMAAdapter',
        
        # Parâmetros das médias exponenciais
        'params': {
            'fast_period': 9,           # EMA rápida (padrão: 9)
            'slow_period': 21          # EMA lenta (padrão: 21)
        },
        
        # Sistema de peso - menor que BB
        'weight_formula': '10',             # Peso fixo menor que BB
        'weight_max': 10,
        'min_data_points': 21,              # Precisa da EMA21 completa
        'validation_rule': 'trend not in [None, "SIDEWAYS"]',  # Só RISE/FALL
        
        # Interface
        'display_name': 'EMA Trend',
        'log_format': 'trend={trend}, EMA9={ema9:.5f}, EMA21={ema21:.5f}',
        'returns_tuple': True,              # Retorna: (trend, ema9, ema21)
        'result_mapping': {
            'trend': 0,
            'ema9': 1,
            'ema21': 2
        }
    },
    
    # ================================================================
    # HULL MOVING AVERAGE (HMA) - Média Móvel Responsiva
    # ================================================================
    # Média móvel que reduz lag e aumenta suavidade
    # Excelente para confirmar tendências estabelecidas
    'HMA': {
        'enabled': True,                    # ✅ Ativo (confirmação de tendência)
        'function_name': 'analyze_hma_trend',
        'module': 'app.trend_analysis',
        'adapter_class': 'HMAAdapter',
        
        # Parâmetros do Hull Moving Average
        'params': {
            'short_period': 21,         # HMA curto (padrão: 21)
            'long_period': 100         # HMA longo (padrão: 100) - requer 100+ candles
        },
        
        # Sistema de peso - moderado
        'weight_formula': '15',             # Peso fixo moderado
        'weight_max': 15,
        'min_data_points': 100,             # Precisa de 100 candles (HMA100)
        'validation_rule': 'trend not in [None, "SIDEWAYS"]',  # Só RISE/FALL
        
        # Interface
        'display_name': 'Hull Moving Average',
        'log_format': 'trend={trend}',
        'returns_tuple': False,             # Retorna apenas: trend
        'result_mapping': {
            'trend': 'direct'               # Valor direto (não é tupla)
        }
    },
    
    # ================================================================
    # MICRO TREND - Análise de Padrões de Curto Prazo
    # ================================================================
    # Detecta micro-tendências e padrões em pequenos períodos
    # Útil para timing de entrada mais preciso
    'Micro': {
        'enabled': True,                    # ✅ Ativo (timing de entrada)
        'function_name': 'analyze_micro_trend',
        'module': 'app.indicators',         # Arquivo indicators.py original
        'adapter_class': 'MicroTrendAdapter',
        
        # Parâmetros do micro trend
        'params': {
            'period': 10,                    # Período de análise (5 candles)
            'trend_strength_threshold': 0.6  # Força mínima para considerar válido
        },
        
        # Sistema de peso - dinâmico baseado em força e confiança
        'weight_formula': 'strength * confidence * 20',  # Peso calculado dinamicamente
        'weight_max': 20,
        'min_data_points': 5,               # Mínimo de 5 candles
        'validation_rule': 'trend not in [None, "SIDEWAYS"]',  # Só RISE/FALL
        
        # Interface
        'display_name': 'Micro Trend',
        'log_format': 'trend={trend}, strength={strength:.3f}, confidence={confidence:.3f}, pattern={pattern}',
        'returns_tuple': False,             # Retorna dict completo
        'result_mapping': {
            'trend': 'trend',               # Chave 'trend' do dict
            'strength': 'strength',         # Chave 'strength' do dict
            'confidence': 'confidence',     # Chave 'confidence' do dict
            'pattern': 'pattern',           # Chave 'pattern' do dict
            'momentum': 'momentum'          # Chave 'momentum' do dict
        }
    }
}

# ====================================================================
# CONFIGURAÇÕES DO SISTEMA DE CONSENSO
# ====================================================================
# Controla como os indicadores "votam" para gerar o sinal final

CONSENSUS_CONFIG = {
    # Quantos indicadores precisam concordar
    'min_indicators': 2,                    # 🎯 AJUSTÁVEL: 2=mais sinais, 3+=menos sinais

    # Porcentagem de concordância necessária
    'consensus_threshold': 0.6,             # 🎯 AJUSTÁVEL: 60% de concordância
    
    # Bônus de confiança
    'max_bonus_percentage': 40,             # Máximo 40% de bônus na confiança final
    
    # Regras especiais
    'require_bb_consensus': False,          # 🎯 AJUSTÁVEL: Se BB deve sempre estar no consenso
    'allow_sideways': False                 # Não permite tendência SIDEWAYS no consenso final
}

# ====================================================================
# CONFIGURAÇÕES POR PERFIL DE RISCO
# ====================================================================

# 🔴 PARA ALTO RISCO - Descomente e ajuste:
# CONSENSUS_CONFIG['min_indicators'] = 2
# CONSENSUS_CONFIG['consensus_threshold'] = 0.5
# CONSENSUS_CONFIG['require_bb_consensus'] = False

# 🟡 PARA MÉDIO RISCO - Configuração atual (padrão)
# CONSENSUS_CONFIG['min_indicators'] = 2
# CONSENSUS_CONFIG['consensus_threshold'] = 0.6
# CONSENSUS_CONFIG['require_bb_consensus'] = False

# 🟢 PARA BAIXO RISCO - Descomente e ajuste:
# CONSENSUS_CONFIG['min_indicators'] = 3
# CONSENSUS_CONFIG['consensus_threshold'] = 0.75
# CONSENSUS_CONFIG['require_bb_consensus'] = True
# INDICATOR_CONFIG['EMA']['enabled'] = False  # Desabilitar EMA para ser mais conservador
# INDICATOR_CONFIG['Micro']['enabled'] = False  # Desabilitar Micro para ser mais conservador

# ====================================================================
# CONFIGURAÇÕES DE LOGGING
# ====================================================================

LOGGING_CONFIG = {
    'log_calculations': True,               # Log detalhado de cálculos dos indicadores
    'log_weights': True,                   # Log de pesos calculados para cada indicador
    'log_validation': True,                # Log de validações (por que indicador foi aceito/rejeitado)
    'log_errors': True                     # Log de erros durante processamento
}

def get_enabled_indicators():
    """
    Retorna apenas os indicadores habilitados
    
    Returns:
        dict: Dicionário com indicadores habilitados
    """
    return {name: config for name, config in INDICATOR_CONFIG.items() 
            if config.get('enabled', False)}

def get_indicator_config(name: str):
    """
    Retorna configuração de um indicador específico
    
    Args:
        name: Nome do indicador
        
    Returns:
        dict: Configuração do indicador ou None se não existir
    """
    return INDICATOR_CONFIG.get(name)

def update_indicator_status(name: str, enabled: bool):
    """
    Atualiza status de um indicador
    
    Args:
        name: Nome do indicador
        enabled: Se deve estar habilitado ou não
    """
    if name in INDICATOR_CONFIG:
        INDICATOR_CONFIG[name]['enabled'] = enabled
        return True
    return False

def get_consensus_config():
    """
    Retorna configurações de consenso
    
    Returns:
        dict: Configurações de consenso
    """
    return CONSENSUS_CONFIG.copy()
