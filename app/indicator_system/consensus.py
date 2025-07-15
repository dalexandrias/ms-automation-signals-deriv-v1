"""
Sistema de análise de consenso entre indicadores
"""
from typing import List, Dict
import logging
from .base import IndicatorResult, ConsensusResult, ConfidenceResult
from app.config.indicators import get_consensus_config

logger = logging.getLogger(__name__)

class ConsensusAnalyzer:
    """
    Analisador de consenso entre indicadores de tendência
    """
    
    def __init__(self, config: Dict = None):
        """
        Inicializa o analisador de consenso
        
        Args:
            config: Configurações personalizadas (opcional)
        """
        self.config = config or get_consensus_config()
    
    def analyze_consensus(self, results: List[IndicatorResult]) -> ConsensusResult:
        """
        Analisa consenso entre os resultados dos indicadores
        
        Args:
            results: Lista de resultados dos indicadores
            
        Returns:
            ConsensusResult: Resultado da análise de consenso
        """
        consensus = ConsensusResult()
        consensus.total_indicators = len(results)
        
        try:
            # Filtrar apenas resultados válidos para consenso
            valid_results = []
            for result in results:
                is_valid = result.is_valid_for_consensus()
                logger.info(f"📊 {result.name}: {result.trend} - Válido para consenso: {is_valid} "
                           f"(erro: {result.error}, should_trade: {result.should_trade})")
                if is_valid:
                    valid_results.append(result)
            
            consensus.valid_indicators = len(valid_results)
            
            # Verificar se há indicadores suficientes
            min_indicators = self.config.get('min_indicators', 3)
            logger.info(f"🔍 Consenso: {consensus.valid_indicators}/{consensus.total_indicators} válidos, mínimo: {min_indicators}")
            if consensus.valid_indicators < min_indicators:
                consensus.reason = f"Indicadores válidos insuficientes: {consensus.valid_indicators}/{min_indicators}"
                return consensus
            
            # Contar votos por tendência
            trend_votes = {}
            participating = {}
            
            for result in valid_results:
                trend = result.trend
                if trend in ['RISE', 'FALL']:  # Ignorar SIDEWAYS e None
                    trend_votes[trend] = trend_votes.get(trend, 0) + 1
                    participating[result.name] = trend
            
            consensus.participating_indicators = participating
            
            if not trend_votes:
                consensus.reason = "Nenhum indicador com tendência válida (RISE/FALL)"
                return consensus
            
            # Encontrar tendência majoritária
            max_votes = max(trend_votes.values())
            majority_trends = [trend for trend, votes in trend_votes.items() if votes == max_votes]
            
            # Verificar se há empate
            if len(majority_trends) > 1:
                consensus.reason = f"Empate entre tendências: {majority_trends}"
                return consensus
            
            majority_trend = majority_trends[0]
            consensus.consensus_count = max_votes
            consensus.consensus_percentage = (max_votes / consensus.valid_indicators) * 100
            
            # Verificar se atende ao threshold de consenso
            threshold = self.config.get('consensus_threshold', 0.75)
            required_percentage = threshold * 100
            
            if consensus.consensus_percentage >= required_percentage:
                consensus.has_consensus = True
                consensus.consensus_trend = majority_trend
                consensus.reason = f"Consenso alcançado: {majority_trend}"
            else:
                consensus.reason = f"Consenso insuficiente: {consensus.consensus_percentage:.1f}% < {required_percentage:.1f}%"
            
            logger.info(f"🗳️ Análise de consenso: {trend_votes}, consenso: {consensus.has_consensus}")
            
        except Exception as e:
            consensus.reason = f"Erro na análise de consenso: {str(e)}"
            logger.error(f"❌ Erro no consenso: {e}")
        
        return consensus
    
    def calculate_proportional_confidence(self, 
                                        results: List[IndicatorResult],
                                        consensus_trend: str,
                                        base_confidence: int) -> ConfidenceResult:
        """
        Calcula confiança final usando sistema proporcional
        
        Args:
            results: Lista de resultados dos indicadores
            consensus_trend: Tendência de consenso
            base_confidence: Confiança base calculada
            
        Returns:
            ConfidenceResult: Resultado do cálculo de confiança
        """
        confidence_result = ConfidenceResult(
            final_confidence=base_confidence,
            base_confidence=base_confidence,
            bonus_confidence=0
        )
        
        try:
            # Filtrar indicadores que concordam com o consenso
            consensus_results = [r for r in results if r.trend == consensus_trend and r.error is None]
            
            if not consensus_results:
                confidence_result.breakdown = f"base: {base_confidence}"
                return confidence_result
            
            # Calcular pesos totais
            total_weight = 0
            weights = {}
            
            for result in consensus_results:
                weight = result.weight
                weights[result.name] = weight
                total_weight += weight
            
            confidence_result.weights = weights
            
            # Distribuir bônus proporcionalmente
            max_bonus = self.config.get('max_bonus_percentage', 40)
            bonuses = {}
            total_bonus = 0
            
            if total_weight > 0:
                for result in consensus_results:
                    weight = result.weight
                    proportional_bonus = int((weight / total_weight) * max_bonus)
                    bonuses[result.name] = proportional_bonus
                    total_bonus += proportional_bonus
            
            confidence_result.bonuses = bonuses
            confidence_result.bonus_confidence = total_bonus
            confidence_result.final_confidence = min(100, base_confidence + total_bonus)
            
            # Montar breakdown para log
            bonus_parts = [f"{name}: +{bonus}" for name, bonus in bonuses.items()]
            confidence_result.breakdown = f"base: {base_confidence} + bônus: {total_bonus} [{', '.join(bonus_parts)}]"
            
            logger.info(f"📊 Confiança proporcional calculada: {confidence_result.final_confidence}%")
            
        except Exception as e:
            logger.error(f"❌ Erro no cálculo de confiança: {e}")
            confidence_result.breakdown = f"base: {base_confidence} (erro no cálculo de bônus)"
        
        return confidence_result
    
    def _get_processor_for_result(self, result: IndicatorResult):
        """
        Obtém o processador correspondente a um resultado
        
        Args:
            result: Resultado do indicador
            
        Returns:
            IndicatorProcessor: Processador correspondente ou None
        """
        try:
            from .factory import IndicatorFactory
            return IndicatorFactory.get_processor(result.name)
        except:
            return None
    
    def get_consensus_summary(self, results: List[IndicatorResult]) -> Dict:
        """
        Retorna resumo detalhado do consenso para debug
        
        Args:
            results: Lista de resultados dos indicadores
            
        Returns:
            Dict: Resumo detalhado
        """
        summary = {
            'total_indicators': len(results),
            'by_status': {
                'valid': 0,
                'invalid': 0,
                'error': 0
            },
            'by_trend': {
                'RISE': 0,
                'FALL': 0,
                'SIDEWAYS': 0,
                'None': 0
            },
            'details': []
        }
        
        for result in results:
            # Status
            if result.error:
                summary['by_status']['error'] += 1
                status = 'ERROR'
            elif result.is_valid_for_consensus():
                summary['by_status']['valid'] += 1
                status = 'VALID'
            else:
                summary['by_status']['invalid'] += 1
                status = 'INVALID'
            
            # Tendência
            trend = result.trend or 'None'
            summary['by_trend'][trend] = summary['by_trend'].get(trend, 0) + 1
            
            # Detalhes
            summary['details'].append({
                'name': result.name,
                'trend': result.trend,
                'status': status,
                'weight': result.weight,
                'error': result.error,
                'should_trade': result.should_trade
            })
        
        return summary
