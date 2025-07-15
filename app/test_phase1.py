"""
Script de teste para validar a estrutura base dos indicadores (Fase 1)
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from indicator_system import IndicatorFactory, ConsensusAnalyzer
from config.indicators import get_enabled_indicators, get_consensus_config
import logging

# Configurar logging para teste
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_phase_1():
    """
    Testa a estrutura base criada na Fase 1
    """
    logger.info("🧪 Iniciando teste da Fase 1 - Estrutura Base")
    
    try:
        # Teste 1: Configurações
        logger.info("\n📋 Teste 1: Configurações")
        enabled = get_enabled_indicators()
        logger.info(f"✅ Indicadores habilitados: {list(enabled.keys())}")
        
        consensus_config = get_consensus_config()
        logger.info(f"✅ Configuração de consenso: {consensus_config}")
        
        # Teste 2: Validação de configuração
        logger.info("\n🔍 Teste 2: Validação de configuração")
        errors = IndicatorFactory.validate_configuration()
        if errors:
            logger.warning(f"⚠️ Erros de configuração encontrados:")
            for error in errors:
                logger.warning(f"  - {error}")
        else:
            logger.info("✅ Configuração válida")
        
        # Teste 3: Inicialização da Factory
        logger.info("\n🏭 Teste 3: Inicialização da Factory")
        IndicatorFactory.initialize()
        
        status = IndicatorFactory.get_status()
        logger.info(f"✅ Factory inicializada: {status['total_loaded']} indicadores carregados")
        
        for name, info in status['indicators'].items():
            status_icon = "✅" if info['loaded'] else "❌"
            logger.info(f"  {status_icon} {name} ({info['display_name']}): loaded={info['loaded']}")
        
        # Teste 4: Processadores
        logger.info("\n⚙️ Teste 4: Processadores")
        processors = IndicatorFactory.get_enabled_processors()
        logger.info(f"✅ {len(processors)} processadores habilitados")
        
        for processor in processors:
            logger.info(f"  📊 {processor.name}: função carregada = {processor.function is not None}")
        
        # Teste 5: Consenso Analyzer
        logger.info("\n🤝 Teste 5: Consenso Analyzer")
        analyzer = ConsensusAnalyzer()
        logger.info(f"✅ ConsensusAnalyzer criado com config: {analyzer.config}")
        
        logger.info("\n🎉 Fase 1 - Estrutura Base: SUCESSO!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro no teste da Fase 1: {e}")
        import traceback
        logger.error(f"Detalhes: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = test_phase_1()
    sys.exit(0 if success else 1)
