# Sistema dinâmico de indicadores
from .base import BaseIndicator, IndicatorResult, ConsensusResult, ConfidenceResult, IndicatorError, ConfigurationError
from .processor import IndicatorProcessor
from .factory import IndicatorFactory
from .consensus import ConsensusAnalyzer

__all__ = [
    'BaseIndicator',
    'IndicatorResult',
    'ConsensusResult', 
    'ConfidenceResult',
    'IndicatorError',
    'ConfigurationError',
    'IndicatorProcessor',
    'IndicatorFactory',
    'ConsensusAnalyzer'
]
