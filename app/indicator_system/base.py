"""
Classes base para o sistema dinâmico de indicadores
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union
import logging
from abc import ABC, abstractmethod
import pandas as pd

logger = logging.getLogger(__name__)

@dataclass
class IndicatorResult:
    """
    Classe que representa o resultado de um indicador de tendência
    """
    name: str
    trend: Optional[str] = None  # 'RISE', 'FALL', 'SIDEWAYS', None
    strength: float = 0.0
    confidence: float = 0.0
    should_trade: bool = True
    raw_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    weight: float = 0.0
    
    def is_valid_for_consensus(self) -> bool:
        """
        Verifica se o resultado é válido para participar do consenso
        
        Returns:
            bool: True se válido para consenso
        """
        return (
            self.error is None and 
            self.trend is not None and 
            self.trend not in ['SIDEWAYS'] and
            self.should_trade
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte resultado para dicionário
        
        Returns:
            dict: Representação em dicionário
        """
        return {
            'name': self.name,
            'trend': self.trend,
            'strength': self.strength,
            'confidence': self.confidence,
            'should_trade': self.should_trade,
            'raw_data': self.raw_data,
            'error': self.error,
            'weight': self.weight
        }

@dataclass 
class ConsensusResult:
    """
    Classe que representa o resultado da análise de consenso
    """
    has_consensus: bool = False
    consensus_trend: Optional[str] = None
    participating_indicators: Dict[str, str] = field(default_factory=dict)
    total_indicators: int = 0
    valid_indicators: int = 0
    consensus_count: int = 0
    consensus_percentage: float = 0.0
    reason: str = ""
    
    @property
    def trend(self) -> Optional[str]:
        """
        Propriedade de compatibilidade que retorna consensus_trend
        
        Returns:
            str: Trend do consenso
        """
        return self.consensus_trend
    
    @property
    def agreeing_count(self) -> int:
        """
        Propriedade de compatibilidade que retorna consensus_count
        
        Returns:
            int: Número de indicadores concordantes
        """
        return self.consensus_count
    
    @property
    def total_count(self) -> int:
        """
        Propriedade de compatibilidade que retorna total_indicators
        
        Returns:
            int: Total de indicadores
        """
        return self.total_indicators
    
    @property
    def confidence(self) -> float:
        """
        Propriedade de compatibilidade que retorna consensus_percentage
        
        Returns:
            float: Percentual de confiança
        """
        return self.consensus_percentage
    
    @property
    def vote_breakdown(self) -> Dict[str, str]:
        """
        Propriedade de compatibilidade que retorna participating_indicators
        
        Returns:
            Dict[str, str]: Breakdown da votação
        """
        return self.participating_indicators
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte resultado para dicionário
        
        Returns:
            dict: Representação em dicionário
        """
        return {
            'has_consensus': self.has_consensus,
            'consensus_trend': self.consensus_trend,
            'participating_indicators': self.participating_indicators,
            'total_indicators': self.total_indicators,
            'valid_indicators': self.valid_indicators,
            'consensus_count': self.consensus_count,
            'consensus_percentage': self.consensus_percentage,
            'reason': self.reason
        }

@dataclass
class ConfidenceResult:
    """
    Classe que representa o resultado do cálculo de confiança
    """
    final_confidence: int
    base_confidence: int
    bonus_confidence: int
    weights: Dict[str, float] = field(default_factory=dict)
    bonuses: Dict[str, int] = field(default_factory=dict)
    breakdown: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte resultado para dicionário
        
        Returns:
            dict: Representação em dicionário
        """
        return {
            'final_confidence': self.final_confidence,
            'base_confidence': self.base_confidence,
            'bonus_confidence': self.bonus_confidence,
            'weights': self.weights,
            'bonuses': self.bonuses,
            'breakdown': self.breakdown
        }

class IndicatorError(Exception):
    """
    Exceção customizada para erros de indicadores
    """
    def __init__(self, indicator_name: str, message: str, original_error: Exception = None):
        self.indicator_name = indicator_name
        self.original_error = original_error
        super().__init__(f"Erro no indicador {indicator_name}: {message}")

class ConfigurationError(Exception):
    """
    Exceção para erros de configuração
    """
    pass

class BaseIndicator(ABC):
    """
    Classe base abstrata para todos os indicadores
    """
    
    def __init__(self, name: str, display_name: str = None):
        self.name = name
        self.display_name = display_name or name
    
    @abstractmethod
    def calculate(self, df: pd.DataFrame, params: dict) -> 'IndicatorResult':
        """
        Calcula o indicador com base nos dados fornecidos
        
        Args:
            df: DataFrame com dados OHLC
            params: Parâmetros de configuração do indicador
            
        Returns:
            IndicatorResult: Resultado do cálculo
        """
        pass
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Valida se os dados são adequados para o cálculo
        
        Args:
            df: DataFrame a ser validado
            
        Returns:
            bool: True se os dados são válidos
        """
        required_columns = ['open', 'high', 'low', 'close']
        return all(col in df.columns for col in required_columns) and len(df) > 0
