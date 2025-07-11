import pandas as pd
import numpy as np
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def calculate_dynamic_threshold(df: pd.DataFrame, lookback_period: int = 20) -> float:
    """
    Calcula um threshold dinâmico baseado na volatilidade histórica das bandas.
    
    Args:
        df: DataFrame com dados históricos
        lookback_period: Período para calcular a volatilidade histórica
        
    Returns:
        float: Threshold dinâmico para a largura das bandas
    """
    try:
        # Calcula a volatilidade histórica usando desvio padrão
        historical_volatility = df['close'].rolling(window=lookback_period).std()
        avg_volatility = historical_volatility.mean()
        
        # Normaliza a volatilidade para um range adequado (0.001 - 0.005)
        min_threshold = 0.001
        max_threshold = 0.005
        normalized_threshold = min_threshold + (avg_volatility / historical_volatility.max()) * (max_threshold - min_threshold)
        
        return normalized_threshold
        
    except Exception as e:
        logger.error(f"Erro ao calcular threshold dinâmico: {e}")
        return 0.001  # valor padrão conservador

def analyze_bollinger_trend(df: pd.DataFrame, 
                          upper: float, 
                          middle: float, 
                          lower: float,
                          window: int = 10) -> Tuple[str, float]:
    """
    Analisa a tendência das Bandas de Bollinger considerando múltiplos fatores.
    
    Args:
        df: DataFrame com dados históricos
        upper: Banda superior atual
        middle: Banda média atual
        lower: Banda inferior atual
        window: Janela para análise da tendência
        
    Returns:
        Tuple[str, float]: (direção da tendência, força do sinal)
    """
    try:
        last_price = df['close'].iloc[-1]
        
        # 1. Calcular largura relativa das bandas
        band_width = (upper - lower) / middle
        
        # 2. Calcular threshold dinâmico
        dynamic_threshold = calculate_dynamic_threshold(df)
        
        # 3. Analisar direção das bandas
        middle_direction = middle - df['close'].rolling(window=window).mean().iloc[-2]
        
        # 4. Calcular distância do preço às bandas
        upper_distance = (upper - last_price) / last_price
        lower_distance = (last_price - lower) / last_price
        
        # 5. Calcular força do sinal (0-1)
        signal_strength = 0.0
        
        # Condições para ALTA
        if last_price > middle:
            signal_strength += 0.3  # Preço acima da média
            if middle_direction > 0:
                signal_strength += 0.2  # Bandas em tendência de alta
            if band_width > dynamic_threshold:
                signal_strength += 0.3  # Volatilidade adequada
            if upper_distance < 0.002:  # Próximo à banda superior
                signal_strength += 0.2
                
        # Condições para BAIXA
        elif last_price < middle:
            signal_strength += 0.3  # Preço abaixo da média
            if middle_direction < 0:
                signal_strength += 0.2  # Bandas em tendência de baixa
            if band_width > dynamic_threshold:
                signal_strength += 0.3  # Volatilidade adequada
            if lower_distance < 0.002:  # Próximo à banda inferior
                signal_strength += 0.2
        
        # Determinar direção com base na análise completa
        if signal_strength >= 0.5:  # Requer pelo menos 70% de força para gerar sinal
            if last_price > middle:
                trend = "RISE"
            else:
                trend = "FALL"
        else:
            trend = None
            
        return trend, signal_strength
        
    except Exception as e:
        logger.error(f"Erro ao analisar tendência das Bandas de Bollinger: {e}")
        return None, 0.0

def should_trade_bollinger(df: pd.DataFrame, 
                         upper: float, 
                         middle: float, 
                         lower: float) -> Tuple[bool, str, float]:
    """
    Determina se deve operar baseado na análise completa das Bandas de Bollinger.
    
    Args:
        df: DataFrame com dados históricos
        upper: Banda superior atual
        middle: Banda média atual
        lower: Banda inferior atual
        
    Returns:
        Tuple[bool, str, float]: (deve operar, direção, força do sinal)
    """
    try:
        # Análise da tendência e força do sinal
        trend, strength = analyze_bollinger_trend(df, upper, middle, lower)
        
        # Verificações adicionais de segurança
        last_price = df['close'].iloc[-1]
        
        # 1. Verificar se não estamos em um movimento muito estendido
        if trend == "RISE" and last_price > upper * 1.005:
            logger.info("⚠️ Preço muito estendido acima da banda superior")
            return False, None, 0.0
            
        if trend == "FALL" and last_price < lower * 0.995:
            logger.info("⚠️ Preço muito estendido abaixo da banda inferior")
            return False, None, 0.0
            
        # 2. Verificar consistência do movimento
        price_std = df['close'].rolling(window=5).std().iloc[-1]
        if price_std > (upper - lower) * 0.3:
            logger.info("⚠️ Volatilidade muito alta no curto prazo")
            return False, None, 0.0
            
        # Decisão final
        should_trade = trend is not None and strength >= 0.7
        
        return should_trade, trend, strength
        
    except Exception as e:
        logger.error(f"Erro ao avaliar condições de trade Bollinger: {e}")
        return False, None, 0.0 