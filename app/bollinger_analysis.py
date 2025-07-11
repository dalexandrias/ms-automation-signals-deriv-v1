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
        
        # 2. Calcular threshold dinâmico (mais flexível)
        dynamic_threshold = calculate_dynamic_threshold(df) * 0.5  # Reduzir threshold
        
        # 3. Analisar direção das bandas
        if len(df) >= window + 1:
            middle_direction = middle - df['close'].rolling(window=window).mean().iloc[-2]
        else:
            middle_direction = 0
        
        # 4. Calcular distância do preço às bandas
        upper_distance = (upper - last_price) / last_price
        lower_distance = (last_price - lower) / last_price
        
        # 5. Calcular força do sinal (0-1) - AJUSTADO
        signal_strength = 0.0
        
        # Condições para ALTA
        if last_price >= middle:  # Mudado de > para >=
            signal_strength += 0.3  # Preço acima ou igual à média
            if middle_direction > 0:
                signal_strength += 0.2  # Bandas em tendência de alta
            if band_width > dynamic_threshold:
                signal_strength += 0.2  # Volatilidade adequada (reduzido de 0.3)
            if upper_distance < 0.005:  # Mais flexível (era 0.002)
                signal_strength += 0.3  # Aumentado bônus
                
        # Condições para BAIXA
        elif last_price < middle:
            signal_strength += 0.3  # Preço abaixo da média
            if middle_direction < 0:
                signal_strength += 0.2  # Bandas em tendência de baixa
            if band_width > dynamic_threshold:
                signal_strength += 0.2  # Volatilidade adequada (reduzido de 0.3)
            if lower_distance < 0.005:  # Mais flexível (era 0.002)
                signal_strength += 0.3  # Aumentado bônus
        
        # Determinar direção com base na análise completa (AJUSTADO)
        if signal_strength >= 0.4:  # Reduzido de 0.5 para 0.4
            if last_price >= middle:
                trend = "RISE"
            else:
                trend = "FALL"
        else:
            trend = None
            
        # Log detalhado para debug
        logger.debug(f"🔍 BB Trend Analysis: price={last_price:.5f}, middle={middle:.5f}, "
                    f"band_width={band_width:.6f}, strength={signal_strength:.3f}, trend={trend}")
            
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
        
        # 1. Verificar se não estamos em um movimento muito estendido (mais flexível)
        if trend == "RISE" and last_price > upper * 1.01:  # Reduzido de 1.005 para 1.01
            logger.info("⚠️ Preço muito estendido acima da banda superior")
            return False, None, 0.0
            
        if trend == "FALL" and last_price < lower * 0.99:  # Ajustado de 0.995 para 0.99
            logger.info("⚠️ Preço muito estendido abaixo da banda inferior")
            return False, None, 0.0
            
        # 2. Verificar consistência do movimento (AJUSTADO - mais flexível)
        price_std = df['close'].rolling(window=5).std().iloc[-1]
        volatility_threshold = (upper - lower) * 0.5  # Aumentado de 0.3 para 0.5
        
        if price_std > volatility_threshold:
            logger.info(f"⚠️ Volatilidade alta: {price_std:.6f} > {volatility_threshold:.6f}")
            # Em vez de bloquear completamente, vamos reduzir a força do sinal
            strength = strength * 0.7  # Reduz força em 30%
            logger.info(f"🔄 Força do sinal reduzida para {strength:.3f} devido à volatilidade")
            
        # 3. Adicionar análise de momentum das bandas
        band_momentum = middle - df['close'].rolling(window=10).mean().iloc[-10]
        if abs(band_momentum) < 0.0001:  # Bandas muito estagnadas
            logger.info("⚠️ Bandas de Bollinger em consolidação lateral")
            strength = strength * 0.8  # Reduz força em 20%
            
        # Decisão final (reduzido threshold de 0.7 para 0.5)
        should_trade = trend is not None and strength >= 0.5
        
        # Log detalhado para debug
        logger.info(f"📊 BB Analysis: trend={trend}, strength={strength:.3f}, price_std={price_std:.6f}, threshold={volatility_threshold:.6f}")
        
        return should_trade, trend, strength
        
    except Exception as e:
        logger.error(f"Erro ao avaliar condições de trade Bollinger: {e}")
        return False, None, 0.0