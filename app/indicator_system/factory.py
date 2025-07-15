"""
Factory para criação e gerenciamento de indicadores
"""
from typing import List, Dict, Optional
import logging
import pandas as pd
from .processor import IndicatorProcessor
from .base import ConfigurationError, IndicatorResult
from .adapters import BollingerBandsAdapter, EMAAdapter, HMAAdapter, MicroTrendAdapter
from app.config.indicators import get_enabled_indicators, get_indicator_config

logger = logging.getLogger(__name__)

class IndicatorFactory:
    """
    Factory responsável por criar e gerenciar processadores de indicadores
    """
    
    _processors: Dict[str, IndicatorProcessor] = {}
    _initialized = False
    
    @classmethod
    def initialize(cls) -> None:
        """
        Inicializa a factory carregando todos os indicadores habilitados
        """
        if cls._initialized:
            return
            
        try:
            enabled_indicators = get_enabled_indicators()
            logger.info(f"🔧 Inicializando factory com {len(enabled_indicators)} indicadores habilitados")
            
            for name, config in enabled_indicators.items():
                try:
                    processor = IndicatorProcessor(name, config)
                    cls._processors[name] = processor
                    logger.info(f"✅ Indicador {name} ({config['display_name']}) carregado")
                except Exception as e:
                    logger.error(f"❌ Falha ao carregar indicador {name}: {e}")
                    
            cls._initialized = True
            logger.info(f"🚀 Factory inicializada com {len(cls._processors)} indicadores")
            
        except Exception as e:
            logger.error(f"❌ Falha crítica na inicialização da factory: {e}")
            raise ConfigurationError(f"Não foi possível inicializar a factory: {e}")
    
    @classmethod
    def get_processor(cls, name: str) -> Optional[IndicatorProcessor]:
        """
        Retorna um processador específico
        
        Args:
            name: Nome do indicador
            
        Returns:
            IndicatorProcessor: Processador do indicador ou None se não encontrado
        """
        if not cls._initialized:
            cls.initialize()
            
        return cls._processors.get(name)
    
    @classmethod
    def get_all_processors(cls) -> Dict[str, IndicatorProcessor]:
        """
        Retorna todos os processadores carregados
        
        Returns:
            Dict[str, IndicatorProcessor]: Dicionário com todos os processadores
        """
        if not cls._initialized:
            cls.initialize()
            
        return cls._processors.copy()
    
    @classmethod
    def get_enabled_processors(cls) -> List[IndicatorProcessor]:
        """
        Retorna lista de processadores habilitados
        
        Returns:
            List[IndicatorProcessor]: Lista de processadores habilitados
        """
        if not cls._initialized:
            cls.initialize()
            
        enabled_names = list(get_enabled_indicators().keys())
        return [cls._processors[name] for name in enabled_names if name in cls._processors]
    
    @classmethod
    def reload_indicator(cls, name: str) -> bool:
        """
        Recarrega um indicador específico
        
        Args:
            name: Nome do indicador
            
        Returns:
            bool: True se recarregado com sucesso
        """
        try:
            config = get_indicator_config(name)
            if config and config.get('enabled', False):
                processor = IndicatorProcessor(name, config)
                cls._processors[name] = processor
                logger.info(f"🔄 Indicador {name} recarregado")
                return True
            else:
                # Remover se desabilitado
                if name in cls._processors:
                    del cls._processors[name]
                    logger.info(f"🗑️ Indicador {name} removido (desabilitado)")
                return True
                
        except Exception as e:
            logger.error(f"❌ Falha ao recarregar indicador {name}: {e}")
            return False
    
    @classmethod
    def reload_all(cls) -> None:
        """
        Recarrega todos os indicadores
        """
        logger.info("🔄 Recarregando todos os indicadores...")
        cls._processors.clear()
        cls._initialized = False
        cls.initialize()
    
    @classmethod
    def get_status(cls) -> Dict[str, Dict]:
        """
        Retorna status de todos os indicadores
        
        Returns:
            Dict: Status dos indicadores
        """
        if not cls._initialized:
            cls.initialize()
            
        status = {
            'initialized': cls._initialized,
            'total_loaded': len(cls._processors),
            'indicators': {}
        }
        
        enabled_indicators = get_enabled_indicators()
        
        for name, config in enabled_indicators.items():
            indicator_status = {
                'enabled': config.get('enabled', False),
                'loaded': name in cls._processors,
                'display_name': config.get('display_name', name),
                'module': config.get('module', 'unknown'),
                'function': config.get('function_name', 'unknown'),
                'min_data_points': config.get('min_data_points', 0)
            }
            
            if name in cls._processors:
                processor = cls._processors[name]
                indicator_status['processor'] = {
                    'function_loaded': processor.function is not None,
                    'config_keys': list(processor.config.keys())
                }
            
            status['indicators'][name] = indicator_status
        
        return status
    
    @classmethod
    def validate_configuration(cls) -> List[str]:
        """
        Valida a configuração de todos os indicadores
        
        Returns:
            List[str]: Lista de erros encontrados
        """
        errors = []
        enabled_indicators = get_enabled_indicators()
        
        required_fields = ['function_name', 'module', 'result_mapping', 'display_name']
        
        for name, config in enabled_indicators.items():
            # Verificar campos obrigatórios
            for field in required_fields:
                if field not in config:
                    errors.append(f"Indicador {name}: campo obrigatório '{field}' ausente")
            
            # Verificar se mapping está correto
            if 'result_mapping' in config:
                mapping = config['result_mapping']
                if not isinstance(mapping, dict):
                    errors.append(f"Indicador {name}: result_mapping deve ser um dicionário")
                elif 'trend' not in mapping:
                    errors.append(f"Indicador {name}: result_mapping deve conter 'trend'")
            
            # Verificar se fórmula de peso é válida
            weight_formula = config.get('weight_formula', '1')
            if not weight_formula:
                errors.append(f"Indicador {name}: weight_formula não pode ser vazio")
        
        return errors
    
    @classmethod
    def calculate_all_indicators(cls, df: pd.DataFrame) -> List[IndicatorResult]:
        """
        Calcula todos os indicadores habilitados usando adaptadores
        
        Args:
            df: DataFrame com dados OHLC
            
        Returns:
            List[IndicatorResult]: Lista de resultados dos indicadores
        """
        from .adapters import (
            BollingerBandsAdapter, 
            EMAAdapter, 
            HMAAdapter, 
            MicroTrendAdapter
        )
        
        results = []
        
        # Mapeamento direto de adaptadores para indicadores
        adapters = {
            'BB': BollingerBandsAdapter(),
            'EMA': EMAAdapter(),
            'HMA': HMAAdapter(),
            'Micro': MicroTrendAdapter()
        }
        
        enabled_indicators = get_enabled_indicators()
        
        for name, config in enabled_indicators.items():
            try:
                if name in adapters:
                    # Usar adaptador para indicadores
                    adapter = adapters[name]
                    result = adapter.calculate(df, config.get('params', {}))
                    results.append(result)
                    
                    logger.info(f"📊 {result.name}: {result.trend} "
                              f"(força: {result.strength:.3f}, confiança: {result.confidence:.3f})")
                else:
                    logger.warning(f"⚠️ Adaptador não encontrado para {name}")
                        
            except Exception as e:
                logger.error(f"❌ Erro ao calcular indicador {name}: {e}")
                # Criar resultado de erro
                error_result = IndicatorResult(
                    name=name,
                    trend=None,
                    strength=0.0,
                    confidence=0.0,
                    should_trade=False,
                    raw_data={},
                    error=str(e)
                )
                results.append(error_result)
        
        logger.info(f"🔧 Calculados {len(results)} indicadores")
        return results
