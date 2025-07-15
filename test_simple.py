"""
Teste simples do sistema dinâmico
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

try:
    # Testar imports básicos
    print("🧪 Testando imports básicos...")
    
    # Testar base
    from app.indicator_system.base import IndicatorResult, ConsensusResult
    print("✅ Base imports funcionando")
    
    # Testar configuração
    from app.config.indicators import get_enabled_indicators
    enabled = get_enabled_indicators()
    print(f"✅ Configuração carregada: {len(enabled)} indicadores")
    
    # Testar factory (sem adaptadores)
    from app.indicator_system.factory import IndicatorFactory
    print("✅ Factory import funcionando")
    
    # Testar consensus
    from app.indicator_system.consensus import ConsensusAnalyzer
    print("✅ Consensus import funcionando")
    
    print("\n🎉 SISTEMA DINÂMICO FUNCIONANDO!")
    print("📋 Próximo passo: implementar process_candles dinâmico")
    
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
