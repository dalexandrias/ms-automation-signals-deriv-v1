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