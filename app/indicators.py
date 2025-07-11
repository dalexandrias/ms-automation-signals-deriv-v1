import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def calculate_bollinger_bands(df, window=10, window_dev=1.5):
    """
    Calcula as Bandas de Bollinger para uma série de dados.
    
    Args:
        df: DataFrame com coluna 'close'
        window: Período para o cálculo da média móvel
        window_dev: Número de desvios padrão
        
    Returns:
        tuple: (upper_band, middle_band, lower_band)
    """
    try:
        try:
            from ta.volatility import BollingerBands
            bb = BollingerBands(df['close'], window=window, window_dev=int(window_dev))
            upper = bb.bollinger_hband().iloc[-1]
            middle = bb.bollinger_mavg().iloc[-1]
            lower = bb.bollinger_lband().iloc[-1]
        except (ImportError, AttributeError):
            # Implementação manual de Bollinger Bands
            sma = df['close'].rolling(window=window).mean()
            std = df['close'].rolling(window=window).std()
            upper = sma.iloc[-1] + (std.iloc[-1] * window_dev)
            middle = sma.iloc[-1]
            lower = sma.iloc[-1] - (std.iloc[-1] * window_dev)
            
        return upper, middle, lower
    except Exception as e:
        logger.error(f"Erro ao calcular Bollinger Bands: {e}")
        return None, None, None

def calculate_ema(df, span):
    """
    Calcula a Média Móvel Exponencial (EMA) para uma série de dados.
    
    Args:
        df: DataFrame com coluna 'close'
        span: Período para o cálculo da EMA
        
    Returns:
        float: Valor da EMA
    """
    try:
        return df['close'].ewm(span=span, adjust=False).mean().iloc[-1]
    except Exception as e:
        logger.error(f"Erro ao calcular EMA: {e}")
        return None

def hull_moving_average(series, period):
    """
    Calcula o Hull Moving Average (HMA) para uma série de dados.
    
    Args:
        series: Série pandas com os valores de preço
        period: Período para o cálculo do HMA
    
    Returns:
        Uma série pandas com os valores do HMA calculados
    """
    try:
        # Verificar se a série tem dados suficientes
        if len(series) < period:
            logger.warning(f"Série com tamanho insuficiente para calcular HMA com período {period}. Tamanho atual: {len(series)}")
            return pd.Series([float('nan')] * len(series), index=series.index)
        
        # 1. Calcula o WMA com metade do período
        half_period = max(1, int(period/2))  # Garantir que half_period seja pelo menos 1
        
        def weighted_mean(x):
            # Verificar se x tem dados suficientes
            if len(x) == 0:
                return float('nan')
            
            # Calcular os pesos
            weights = np.array([(i+1) for i in range(len(x))])
            
            # Verificar se a soma dos pesos é zero
            if weights.sum() == 0:
                return float('nan')
                
            # Calcular a média ponderada
            return np.sum(weights * x) / weights.sum()
        
        # Usar apply com tratamento de erros
        wma_half = series.rolling(window=half_period, min_periods=half_period).apply(
            weighted_mean, raw=True
        )
        
        # 2. Calcula o WMA com período completo
        wma_full = series.rolling(window=period, min_periods=period).apply(
            weighted_mean, raw=True
        )
        
        # 3. Calcula o Raw HMA = 2 * WMA(n/2) - WMA(n)
        raw_hma = 2 * wma_half - wma_full
        
        # 4. Aplica o WMA final com período = sqrt(n)
        sqrt_period = max(1, int(period ** 0.5))  # Garantir que sqrt_period seja pelo menos 1
        
        hma = raw_hma.rolling(window=sqrt_period, min_periods=sqrt_period).apply(
            weighted_mean, raw=True
        )
        
        # Substituir valores NaN por valores anteriores válidos
        hma = hma.ffill()
        
        return hma
    except Exception as e:
        logger.error(f"Erro ao calcular HMA: {e}")
        import traceback
        logger.error(f"Detalhes do erro no HMA: {traceback.format_exc()}")
        # Retornar uma série de NaN com o mesmo índice da série original
        return pd.Series([float('nan')] * len(series), index=series.index)

def calculate_rsi(df, window=14):
    """
    Calcula o Relative Strength Index (RSI) para uma série de dados.
    
    Args:
        df: DataFrame com coluna 'close'
        window: Período para o cálculo do RSI
        
    Returns:
        float: Valor do RSI
    """
    try:
        try:
            from ta.momentum import RSIIndicator
            rsi = RSIIndicator(df['close'], window=window).rsi().iloc[-1]
        except (ImportError, AttributeError):
            # Implementação manual de RSI
            delta = df['close'].diff()
            gain = delta.mask(delta < 0, 0)
            loss = -delta.mask(delta > 0, 0)
            avg_gain = gain.rolling(window=window).mean()
            avg_loss = loss.rolling(window=window).mean()
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
        return rsi
    except Exception as e:
        logger.error(f"Erro ao calcular RSI: {e}")
        return None

def calculate_macd(df, window_fast=12, window_slow=26, window_sign=9):
    """
    Calcula o Moving Average Convergence Divergence (MACD) para uma série de dados.
    
    Args:
        df: DataFrame com coluna 'close'
        window_fast: Período para o cálculo da EMA rápida
        window_slow: Período para o cálculo da EMA lenta
        window_sign: Período para o cálculo da linha de sinal
        
    Returns:
        tuple: (macd_line, signal_line)
    """
    try:
        try:
            from ta.trend import MACD
            macd_ind = MACD(df['close'], window_slow=window_slow, window_fast=window_fast, window_sign=window_sign)
            macd = macd_ind.macd().iloc[-1]
            macd_signal = macd_ind.macd_signal().iloc[-1]
        except (ImportError, AttributeError):
            # Implementação manual de MACD
            ema12 = df['close'].ewm(span=window_fast, adjust=False).mean()
            ema26 = df['close'].ewm(span=window_slow, adjust=False).mean()
            macd_line = ema12 - ema26
            macd_signal_line = macd_line.ewm(span=window_sign, adjust=False).mean()
            macd = macd_line.iloc[-1]
            macd_signal = macd_signal_line.iloc[-1]
            
        return macd, macd_signal
    except Exception as e:
        logger.error(f"Erro ao calcular MACD: {e}")
        return None, None

def calculate_atr(df, window=14):
    """
    Calcula o Average True Range (ATR) para uma série de dados.
    
    Args:
        df: DataFrame com colunas 'high', 'low', 'close'
        window: Período para o cálculo do ATR
        
    Returns:
        float: Valor do ATR
    """
    try:
        try:
            from ta.volatility import AverageTrueRange
            atr = AverageTrueRange(
                df['high'], df['low'], df['close'], window=window
            ).average_true_range().iloc[-1]
        except (ImportError, AttributeError):
            # Implementação manual de ATR
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(window=window).mean().iloc[-1]
            
        return atr
    except Exception as e:
        logger.error(f"Erro ao calcular ATR: {e}")
        return None

def analyze_micro_trend(df, period=5, trend_strength_threshold=0.1):
    """
    Analisa a micro tendência dos candles baseada nos últimos períodos.
    
    Args:
        df: DataFrame com colunas 'open', 'high', 'low', 'close'
        period: Número de candles para analisar (padrão: 5)
        trend_strength_threshold: Limite para considerar tendência forte (0.0 a 1.0)
        
    Returns:
        dict: {
            'trend': 'RISE'|'FALL'|'SIDEWAYS',
            'strength': float (0.0 a 1.0),
            'confidence': float (0.0 a 1.0),
            'pattern': str,
            'momentum': float
        }
    """
    try:
        if len(df) < period:
            logger.warning(f"DataFrame insuficiente para analisar micro tendência. Tamanho: {len(df)}, Período: {period}")
            return {
                'trend': 'SIDEWAYS',
                'strength': 0.0,
                'confidence': 0.0,
                'pattern': 'insufficient_data',
                'momentum': 0.0
            }
        
        # Pegar os últimos 'period' candles
        recent_data = df.tail(period).copy()
        
        # Análise de fechamentos
        closes = recent_data['close'].values
        opens = recent_data['open'].values
        highs = recent_data['high'].values
        lows = recent_data['low'].values
        
        # 1. Análise de direção geral
        price_changes = np.diff(closes)
        positive_moves = np.sum(price_changes > 0)
        negative_moves = np.sum(price_changes < 0)
        total_moves = len(price_changes)
        
        # 2. Análise de momentum
        total_change = closes[-1] - closes[0]
        max_range = np.max(highs) - np.min(lows)
        momentum = total_change / max_range if max_range > 0 else 0
        
        # 3. Análise de força dos candles
        bullish_candles = np.sum(closes > opens)
        bearish_candles = np.sum(closes < opens)
        doji_candles = period - bullish_candles - bearish_candles
        
        # 4. Análise de tamanho dos corpos
        body_sizes = np.abs(closes - opens)
        avg_body_size = np.mean(body_sizes)
        body_strength = avg_body_size / np.mean(highs - lows) if np.mean(highs - lows) > 0 else 0
        
        # 5. Determinar tendência
        bullish_score = (positive_moves / total_moves) if total_moves > 0 else 0
        bearish_score = (negative_moves / total_moves) if total_moves > 0 else 0
        candle_score = (bullish_candles / period) if period > 0 else 0
        
        # Calcular força combinada
        combined_bullish_strength = (bullish_score + candle_score + max(0, momentum)) / 3
        combined_bearish_strength = (bearish_score + (bearish_candles / period) + max(0, -momentum)) / 3
        
        # 6. Análise de padrões
        pattern = _identify_micro_pattern(recent_data)
        
        # 7. Determinar tendência final
        if combined_bullish_strength > trend_strength_threshold:
            trend = 'RISE'
            strength = combined_bullish_strength
        elif combined_bearish_strength > trend_strength_threshold:
            trend = 'FALL'
            strength = combined_bearish_strength
        else:
            trend = 'SIDEWAYS'
            strength = max(combined_bullish_strength, combined_bearish_strength)
        
        # 8. Calcular confiança
        volatility = np.std(price_changes) / np.mean(np.abs(price_changes)) if np.mean(np.abs(price_changes)) > 0 else 1
        confidence = min(1.0, (body_strength * (1 - min(volatility, 1))) + (strength * 0.5))
        
        return {
            'trend': trend,
            'strength': round(strength, 3),
            'confidence': round(confidence, 3),
            'pattern': pattern,
            'momentum': round(momentum, 3)
        }
        
    except Exception as e:
        logger.error(f"Erro ao analisar micro tendência: {e}")
        import traceback
        logger.error(f"Detalhes do erro: {traceback.format_exc()}")
        return {
            'trend': 'SIDEWAYS',
            'strength': 0.0,
            'confidence': 0.0,
            'pattern': 'error',
            'momentum': 0.0
        }

def _identify_micro_pattern(df):
    """
    Identifica padrões específicos nos últimos candles.
    
    Args:
        df: DataFrame com os últimos candles
        
    Returns:
        str: Nome do padrão identificado
    """
    try:
        if len(df) < 3:
            return 'insufficient_data'
        
        closes = df['close'].values
        opens = df['open'].values
        highs = df['high'].values
        lows = df['low'].values
        
        # Analisar últimos 3 candles
        last_3_closes = closes[-3:]
        last_3_opens = opens[-3:]
        
        # Padrão de 3 candles ascendentes
        if (last_3_closes[1] > last_3_closes[0] and 
            last_3_closes[2] > last_3_closes[1] and
            all(c > o for c, o in zip(last_3_closes, last_3_opens))):
            return 'three_ascending_bullish'
        
        # Padrão de 3 candles descendentes
        if (last_3_closes[1] < last_3_closes[0] and 
            last_3_closes[2] < last_3_closes[1] and
            all(c < o for c, o in zip(last_3_closes, last_3_opens))):
            return 'three_descending_bearish'
        
        # Padrão de engolfo bullish
        if (len(df) >= 2 and
            closes[-2] < opens[-2] and  # Candle anterior bearish
            closes[-1] > opens[-1] and  # Candle atual bullish
            opens[-1] < closes[-2] and  # Abre abaixo do fechamento anterior
            closes[-1] > opens[-2]):    # Fecha acima da abertura anterior
            return 'bullish_engulfing'
        
        # Padrão de engolfo bearish
        if (len(df) >= 2 and
            closes[-2] > opens[-2] and  # Candle anterior bullish
            closes[-1] < opens[-1] and  # Candle atual bearish
            opens[-1] > closes[-2] and  # Abre acima do fechamento anterior
            closes[-1] < opens[-2]):    # Fecha abaixo da abertura anterior
            return 'bearish_engulfing'
        
        # Doji
        if abs(closes[-1] - opens[-1]) < (highs[-1] - lows[-1]) * 0.1:
            return 'doji'
        
        # Hammer/Shooting star
        body_size = abs(closes[-1] - opens[-1])
        total_range = highs[-1] - lows[-1]
        lower_shadow = min(closes[-1], opens[-1]) - lows[-1]
        upper_shadow = highs[-1] - max(closes[-1], opens[-1])
        
        if (lower_shadow > body_size * 2 and upper_shadow < body_size and 
            total_range > 0):
            return 'hammer'
        
        if (upper_shadow > body_size * 2 and lower_shadow < body_size and 
            total_range > 0):
            return 'shooting_star'
        
        # Padrão lateral
        price_range = max(closes) - min(closes)
        avg_body = np.mean(np.abs(closes - opens))
        if price_range < avg_body * 2:
            return 'sideways_consolidation'
        
        return 'no_clear_pattern'
        
    except Exception as e:
        logger.error(f"Erro ao identificar padrão micro: {e}")
        return 'pattern_error'