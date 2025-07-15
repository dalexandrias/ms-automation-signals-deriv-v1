"""
Adaptadores para integrar indicadores existentes com o sistema dinâmico.
"""
from typing import Dict, Any, List
import pandas as pd
from .base import BaseIndicator, IndicatorResult

# Imports diretos das funções necessárias
from app.indicators import calculate_bollinger_bands, calculate_rsi, calculate_macd, calculate_atr, analyze_micro_trend
from app.trend_analysis import analyze_ema_trend
from app.bollinger_analysis import should_trade_bollinger


class BollingerBandsAdapter(BaseIndicator):
    """Adapter para as Bandas de Bollinger existentes."""
    
    def __init__(self, period: int = 20, std_dev: int = 2):
        super().__init__(name="bollinger_bands", display_name="Bollinger Bands")
        self.period = period
        self.std_dev = std_dev
        
    def calculate(self, df: pd.DataFrame, params: Dict[str, Any] = None) -> IndicatorResult:
        """Calcula as Bandas de Bollinger usando a função existente."""
        try:
            from app.indicators import calculate_bollinger_bands
            from app.bollinger_analysis import should_trade_bollinger
            
            # Usar parâmetros customizados se fornecidos
            window = params.get('window', self.period) if params else self.period
            window_dev = params.get('window_dev', self.std_dev) if params else self.std_dev
            
            # Chamar a função existente
            bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df, window, window_dev)
            
            # Analisar sinal usando a função existente
            should_trade, trend, strength = should_trade_bollinger(df, float(bb_upper), float(bb_middle), float(bb_lower))
            
            # Garantir valores válidos
            if trend is None:
                trend = 'SIDEWAYS'
            if strength is None:
                strength = 0.0
            if should_trade is None:
                should_trade = False
            
            # Mapear trend para o formato padrão
            signal_map = {
                'RISE': 'compra',
                'FALL': 'venda',
                None: 'neutro'
            }
            
            # Preparar dados brutos
            raw_data = {
                'upper': float(bb_upper),
                'lower': float(bb_lower), 
                'middle': float(bb_middle),
                'current_price': float(df.iloc[-1]['close']),
                'should_trade': should_trade
            }
            
            return IndicatorResult(
                name="Bollinger Bands",
                trend=trend,
                strength=strength,
                confidence=strength,  # Usar strength como confiança
                should_trade=should_trade,
                raw_data=raw_data
            )
            
        except Exception as e:
            return IndicatorResult(
                name="Bollinger Bands",
                trend=None,
                strength=0.0,
                confidence=0.0,
                should_trade=False,
                raw_data={},
                error=str(e)
            )


class EMAAdapter(BaseIndicator):
    """Adapter para análise de tendência EMA existente."""
    
    def __init__(self, fast_period: int = 9, slow_period: int = 21):
        super().__init__(name="ema", display_name="EMA Trend")
        self.fast_period = fast_period
        self.slow_period = slow_period
        
    def calculate(self, df: pd.DataFrame, params: Dict[str, Any] = None) -> IndicatorResult:
        """Calcula tendência EMA usando a função existente."""
        try:
            # Usar parâmetros customizados se fornecidos
            fast_period = params.get('fast_period', self.fast_period) if params else self.fast_period
            slow_period = params.get('slow_period', self.slow_period) if params else self.slow_period
            
            # Chamar a função existente
            trend, ema_fast, ema_slow = analyze_ema_trend(df, fast_period, slow_period)
            
            # Garantir valores válidos
            if not trend:
                trend = 'lateral'
            if not ema_fast:
                ema_fast = 0.0
            if not ema_slow:
                ema_slow = 0.0
            
            # Mapear resultado para formato padrão
            trend_map = {
                'alta': 'RISE',
                'baixa': 'FALL', 
                'lateral': 'SIDEWAYS'
            }
            mapped_trend = trend_map.get(trend, 'SIDEWAYS')
            
            # Calcular confiança baseada na distância entre EMAs
            if ema_fast and ema_slow:
                distance = abs(ema_fast - ema_slow) / ema_slow
                confidence = min(0.9, max(0.3, distance * 10))
                strength = confidence  # Usar confiança como força
            else:
                confidence = 0.3
                strength = 0.3
            
            raw_data = {
                'trend': trend,
                'ema_fast': float(ema_fast) if ema_fast else 0.0,
                'ema_slow': float(ema_slow) if ema_slow else 0.0
            }
            
            return IndicatorResult(
                name="EMA Trend",
                trend=mapped_trend,
                strength=strength,
                confidence=confidence,
                should_trade=mapped_trend != 'SIDEWAYS',
                raw_data=raw_data
            )
            
        except Exception as e:
            return IndicatorResult(
                name="EMA Trend",
                trend=None,
                strength=0.0,
                confidence=0.0,
                should_trade=False,
                raw_data={},
                error=str(e)
            )


class HMAAdapter(BaseIndicator):
    """Adapter para Hull Moving Average existente."""
    
    def __init__(self, period: int = 14):
        super().__init__(name="hma", display_name="Hull Moving Average")
        self.period = period
        
    def calculate(self, df: pd.DataFrame, params: Dict[str, Any] = None) -> IndicatorResult:
        """Calcula HMA usando a função existente."""
        try:
            from app.indicators import hull_moving_average
            
            period = params.get('period', self.period) if params else self.period
            
            # Calcular HMA
            hma = hull_moving_average(df['close'], period)
            current_hma = hma.iloc[-1]
            prev_hma = hma.iloc[-2] if len(hma) > 1 else current_hma
            current_price = df.iloc[-1]['close']
            
            # Determinar sinal baseado na direção do HMA e posição do preço
            if current_hma > prev_hma and current_price > current_hma:
                trend = "RISE"
                confidence = 0.8
                strength = 0.8
            elif current_hma < prev_hma and current_price < current_hma:
                trend = "FALL"
                confidence = 0.8
                strength = 0.8
            else:
                trend = "SIDEWAYS"
                confidence = 0.4
                strength = 0.4
                
            raw_data = {
                'hma': float(current_hma),
                'hma_direction': 'up' if current_hma > prev_hma else 'down',
                'price_position': 'above' if current_price > current_hma else 'below'
            }
            
            return IndicatorResult(
                name="Hull Moving Average",
                trend=trend,
                strength=strength,
                confidence=confidence,
                should_trade=trend != 'SIDEWAYS',
                raw_data=raw_data
            )
            
        except Exception as e:
            return IndicatorResult(
                name="Hull Moving Average",
                trend=None,
                strength=0.0,
                confidence=0.0,
                should_trade=False,
                raw_data={},
                error=str(e)
            )


class MicroTrendAdapter(BaseIndicator):
    """Adapter para análise de micro tendência existente."""
    
    def __init__(self, window: int = 5):
        super().__init__(name="micro_trend", display_name="Micro Trend")
        self.window = window
        
    def calculate(self, df: pd.DataFrame, params: Dict[str, Any] = None) -> IndicatorResult:
        """Calcula micro tendência usando a função existente."""
        try:
            window = params.get('window', self.window) if params else self.window
            
            # Chamar a função existente
            trend_result = analyze_micro_trend(df, window)
            
            # Garantir valores válidos
            if not trend_result:
                trend_result = {'trend': 'lateral', 'strength': 0.0, 'confidence': 0.0}
            
            # trend_result pode ser um dicionário ou string
            if isinstance(trend_result, dict):
                trend = trend_result.get('trend', 'SIDEWAYS')
                strength = trend_result.get('strength', 0.5)
                confidence = trend_result.get('confidence', 0.5)
            else:
                trend = trend_result
                strength = 0.5
                confidence = 0.5
            
            # Mapear resultado para formato padrão
            trend_map = {
                'alta': 'RISE',
                'subida': 'RISE',
                'up': 'RISE',
                'baixa': 'FALL',
                'descida': 'FALL', 
                'down': 'FALL',
                'lateral': 'SIDEWAYS',
                'stable': 'SIDEWAYS'
            }
            mapped_trend = trend_map.get(trend.lower() if trend else '', 'SIDEWAYS')
            
            raw_data = {
                'trend': trend,
                'strength': strength,
                'window': window
            }
            
            return IndicatorResult(
                name="Micro Trend",
                trend=mapped_trend,
                strength=strength,
                confidence=confidence,
                should_trade=mapped_trend != 'SIDEWAYS',
                raw_data=raw_data
            )
            
        except Exception as e:
            return IndicatorResult(
                name="Micro Trend",
                trend=None,
                strength=0.0,
                confidence=0.0,
                should_trade=False,
                raw_data={},
                error=str(e)
            )