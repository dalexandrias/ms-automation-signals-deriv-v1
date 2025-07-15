"""
Processador base para indicadores de tendência
"""
import importlib
import pandas as pd
from typing import Any, Dict, Optional, Callable
import logging
from .base import IndicatorResult, IndicatorError, ConfigurationError

logger = logging.getLogger(__name__)

class IndicatorProcessor:
    """
    Processador base para indicadores de tendência
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Inicializa o processador do indicador
        
        Args:
            name: Nome do indicador
            config: Configuração do indicador
        """
        self.name = name
        self.config = config
        self.function = None
        self._load_function()
    
    def _load_function(self):
        """
        Carrega a função do indicador dinamicamente
        """
        try:
            module_name = self.config['module']
            function_name = self.config['function_name']
            
            # Importar o módulo dinamicamente
            module = importlib.import_module(module_name)
            
            # Obter a função
            self.function = getattr(module, function_name)
            
            logger.debug(f"✅ Função {function_name} carregada do módulo {module_name}")
            
        except ImportError as e:
            raise ConfigurationError(f"Módulo {module_name} não encontrado: {e}")
        except AttributeError as e:
            raise ConfigurationError(f"Função {function_name} não encontrada no módulo {module_name}: {e}")
    
    def has_sufficient_data(self, df: pd.DataFrame) -> bool:
        """
        Verifica se há dados suficientes para processar o indicador
        
        Args:
            df: DataFrame com dados dos candles
            
        Returns:
            bool: True se há dados suficientes
        """
        min_data = self.config.get('min_data_points', 0)
        return len(df) >= min_data
    
    def process(self, df: pd.DataFrame, **kwargs) -> IndicatorResult:
        """
        Processa o indicador com os dados fornecidos
        
        Args:
            df: DataFrame com dados dos candles
            **kwargs: Argumentos adicionais
            
        Returns:
            IndicatorResult: Resultado do processamento
        """
        result = IndicatorResult(name=self.name)
        
        try:
            # Verificar se há dados suficientes
            if not self.has_sufficient_data(df):
                result.error = f"Dados insuficientes ({len(df)}/{self.config['min_data_points']})"
                return result
            
            # Preparar parâmetros da função
            params = self.config.get('params', {}).copy()
            params.update(kwargs)
            
            # Chamar a função do indicador
            if self.name == 'BB':
                # BB precisa dos valores de BB calculados
                upper = kwargs.get('upper')
                middle = kwargs.get('middle') 
                lower = kwargs.get('lower')
                if None in [upper, middle, lower]:
                    result.error = "Valores de Bollinger Bands não fornecidos"
                    return result
                raw_result = self.function(df, upper, middle, lower)
            else:
                raw_result = self.function(df, **params)
            
            # Processar o resultado baseado na configuração
            self._parse_result(raw_result, result)
            
            # Calcular peso se resultado é válido
            if result.error is None:
                result.weight = self.calculate_weight(result)
            
            logger.debug(f"✅ {self.name} processado: trend={result.trend}, weight={result.weight:.2f}")
            
        except Exception as e:
            result.error = f"Erro no processamento: {str(e)}"
            logger.error(f"❌ Erro ao processar {self.name}: {e}")
            import traceback
            logger.debug(f"Detalhes do erro: {traceback.format_exc()}")
        
        return result
    
    def _parse_result(self, raw_result: Any, result: IndicatorResult):
        """
        Converte o resultado bruto da função para IndicatorResult
        
        Args:
            raw_result: Resultado bruto da função
            result: Objeto IndicatorResult para preencher
        """
        try:
            mapping = self.config['result_mapping']
            
            if self.config['returns_tuple']:
                # Resultado é uma tupla
                if isinstance(raw_result, (list, tuple)):
                    for key, index in mapping.items():
                        if isinstance(index, int) and index < len(raw_result):
                            setattr(result, key, raw_result[index])
                        result.raw_data[key] = raw_result[index] if index < len(raw_result) else None
                else:
                    result.error = f"Esperava tupla/lista, recebeu {type(raw_result)}"
                    return
            else:
                # Resultado é um valor direto ou dict
                if mapping.get('trend') == 'direct':
                    # Valor direto (como HMA)
                    result.trend = raw_result
                    result.raw_data['trend'] = raw_result
                elif isinstance(raw_result, dict):
                    # Resultado é um dicionário (como Micro)
                    for key, dict_key in mapping.items():
                        if dict_key in raw_result:
                            setattr(result, key, raw_result[dict_key])
                        result.raw_data[key] = raw_result.get(dict_key)
                else:
                    result.error = f"Formato de resultado não suportado: {type(raw_result)}"
                    return
            
            # Validações específicas
            if hasattr(result, 'should_trade') and self.name == 'BB':
                # Para BB, should_trade vem do resultado
                pass
            else:
                # Para outros indicadores, assumir should_trade = True se trend válido
                result.should_trade = result.trend not in [None, 'SIDEWAYS']
                
        except Exception as e:
            result.error = f"Erro ao processar resultado: {str(e)}"
    
    def calculate_weight(self, result: IndicatorResult) -> float:
        """
        Calcula o peso do indicador baseado na fórmula configurada
        
        Args:
            result: Resultado do indicador
            
        Returns:
            float: Peso calculado
        """
        try:
            formula = self.config['weight_formula']
            max_weight = self.config.get('weight_max', 100)
            
            # Preparar variáveis para avaliação da fórmula
            variables = {
                'strength': getattr(result, 'strength', 0.0),
                'confidence': getattr(result, 'confidence', 0.0),
                'should_trade': getattr(result, 'should_trade', True)
            }
            
            # Avaliar fórmula
            if formula.replace('.', '').replace(' ', '').isdigit():
                # Peso fixo
                weight = float(formula)
            else:
                # Fórmula dinâmica
                weight = eval(formula, {"__builtins__": {}}, variables)
            
            # Aplicar limite máximo
            weight = min(weight, max_weight)
            
            return float(weight)
            
        except Exception as e:
            logger.warning(f"Erro ao calcular peso para {self.name}: {e}. Usando peso padrão 1.0")
            return 1.0
    
    def is_valid_for_consensus(self, result: IndicatorResult) -> bool:
        """
        Verifica se o resultado é válido para participar do consenso
        
        Args:
            result: Resultado do indicador
            
        Returns:
            bool: True se válido para consenso
        """
        try:
            validation_rule = self.config.get('validation_rule', 'True')
            
            # Preparar variáveis para avaliação
            variables = {
                'trend': result.trend,
                'strength': result.strength,
                'confidence': result.confidence,
                'should_trade': result.should_trade,
                'error': result.error
            }
            
            # Avaliar regra de validação
            is_valid = eval(validation_rule, {"__builtins__": {}}, variables)
            
            return bool(is_valid) and result.error is None
            
        except Exception as e:
            logger.warning(f"Erro ao validar {self.name}: {e}. Considerando inválido.")
            return False
    
    def format_log(self, result: IndicatorResult) -> str:
        """
        Formata resultado para log baseado na configuração
        
        Args:
            result: Resultado do indicador
            
        Returns:
            str: String formatada para log
        """
        try:
            if result.error:
                return f"ERROR: {result.error}"
            
            log_format = self.config.get('log_format', 'trend={trend}')
            
            # Preparar variáveis para formatação
            variables = result.to_dict()
            variables.update(result.raw_data)
            
            return log_format.format(**variables)
            
        except Exception as e:
            return f"LOG_ERROR: {e}"
