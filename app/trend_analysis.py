import pandas as pd
import numpy as np
import logging
from indicators import hull_moving_average, calculate_ema

logger = logging.getLogger(__name__)

def analyze_ema_trend(df, fast_period=9, slow_period=21):
    """
    Analisa a tendência usando EMAs de diferentes períodos.
    
    Args:
        df: DataFrame com coluna 'close'
        fast_period: Período para a EMA rápida
        slow_period: Período para a EMA lenta
        
    Returns:
        tuple: (trend, ema_fast, ema_slow)
    """
    try:
        ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean().iloc[-1]
        ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean().iloc[-1]
        trend = 'RISE' if ema_fast > ema_slow else 'FALL'
        return trend, ema_fast, ema_slow
    except Exception as e:
        logger.error(f"Erro ao analisar tendência EMA: {e}")
        return None, None, None

def analyze_hma_trend(df, short_period=21, long_period=100):
    """
    Analisa a direção da tendência usando Hull Moving Average (HMA).
    Simplificada para retornar apenas a direção da tendência.
    
    Args:
        df: DataFrame com coluna 'close'
        short_period: Período para o HMA curto
        long_period: Período para o HMA longo
        
    Returns:
        str: 'RISE' para tendência de alta, 'FALL' para tendência de baixa, ou None se não for possível calcular
    """
    try:
        if len(df) < long_period:
            logger.warning(f"Dados insuficientes para HMA, necessário: {long_period}, disponível: {len(df)}")
            return None
            
        # Calcular as séries HMA completas
        hma_short_series = hull_moving_average(df['close'], short_period)
        hma_long_series = hull_moving_average(df['close'], long_period)

        # Verificar se os valores são válidos (não são NaN)
        if hma_short_series.isna().all() or hma_long_series.isna().all():
            logger.warning("Valores NaN detectados no HMA.")
            return None

        # Determinar direção da tendência
        hma_short_direction = 'RISE' if hma_short_series.iloc[-1] > hma_short_series.iloc[0] else 'FALL'
        hma_long_direction = 'RISE' if hma_long_series.iloc[-1] > hma_long_series.iloc[0] else 'FALL'

        # Determinar a direção da tendência final
        if hma_short_direction == hma_long_direction:
            trend = hma_long_direction
        else:
            trend = None

        logger.info(f"Tendência HMA: {trend} (HMA{short_period}={hma_short_series.iloc[-1]:.2f}, HMA{long_period}={hma_long_series.iloc[-1]:.2f})")
        return trend
        
    except Exception as e:
        logger.error(f"Erro ao analisar tendência HMA: {e}")
        import traceback
        logger.error(f"Detalhes do erro no processamento do HMA: {traceback.format_exc()}")
        return None

def calculate_signal_confidence(trend, rsi, macd, macd_signal, body, atr, close_price, upper_band, lower_band):
    """
    Calcula a confiança base do sinal com base nos indicadores auxiliares.
    Versão conservadora que retorna até 60% para deixar espaço para bônus de consenso.
    
    Args:
        trend: Direção da tendência ('RISE' ou 'FALL')
        rsi: Valor do RSI
        macd: Valor da linha MACD
        macd_signal: Valor da linha de sinal MACD
        body: Tamanho do corpo do candle
        atr: Valor do ATR
        close_price: Preço de fechamento atual
        upper_band: Banda superior de Bollinger
        lower_band: Banda inferior de Bollinger
        
    Returns:
        int: Valor da confiança base (20-60)
    """
    try:
        # Confiança inicial conservadora
        confidence = 20
        
        # Ajustes por indicadores auxiliares (máximo 40 pontos adicionais)
        # RSI - até 10 pontos
        if trend == 'RISE' and 55 <= rsi <= 75:
            confidence += 10
        elif trend == 'FALL' and 30 <= rsi <= 50:
            confidence += 10
        elif trend == 'RISE' and 50 <= rsi < 55:
            confidence += 5  # RSI neutro favorável
        elif trend == 'FALL' and 50 < rsi <= 55:
            confidence += 5  # RSI neutro favorável
            
        # MACD - até 10 pontos
        if trend == 'RISE' and macd > macd_signal:
            # Força do cruzamento
            macd_strength = min(10, int(abs(macd - macd_signal) * 100))
            confidence += max(5, macd_strength)
        elif trend == 'FALL' and macd < macd_signal:
            # Força do cruzamento
            macd_strength = min(10, int(abs(macd - macd_signal) * 100))
            confidence += max(5, macd_strength)
            
        # Corpo do candle - até 10 pontos
        if body >= 0.8 * atr:
            confidence += 10  # Corpo muito forte
        elif body >= 0.5 * atr:
            confidence += 7   # Corpo forte
        elif body >= 0.3 * atr:
            confidence += 4   # Corpo moderado
            
        # Posição nas Bandas de Bollinger - até 10 pontos
        if trend == 'RISE' and close_price > upper_band:
            confidence += 10  # Breakout de alta
        elif trend == 'FALL' and close_price < lower_band:
            confidence += 10  # Breakout de baixa
        elif trend == 'RISE' and close_price > (upper_band + lower_band) / 2:
            confidence += 5   # Acima da média
        elif trend == 'FALL' and close_price < (upper_band + lower_band) / 2:
            confidence += 5   # Abaixo da média
            
        # Garantir que não ultrapasse 60 (deixar espaço para bônus de consenso)
        confidence = min(60, confidence)
        
        return confidence
    except Exception as e:
        logger.error(f"Erro ao calcular confiança do sinal: {e}")
        return 20  # Confiança mínima em caso de erro 