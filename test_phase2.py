"""
Teste Phase 2 - Sistema Dinâmico Integrado
Valida a integração completa do sistema dinâmico no process_candles
"""

import sys
import os
import traceback

# Adicionar o diretório pai ao path para imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.indicator_system import IndicatorFactory, ConsensusAnalyzer
from app.config.indicators import get_enabled_indicators, get_consensus_config
import pandas as pd
import numpy as np
from datetime import datetime

def create_test_data():
    """Cria dados de teste realistas"""
    np.random.seed(42)
    
    # Criar 150 candles para testar HMA
    n_candles = 150
    base_price = 1.1000
    
    data = []
    current_price = base_price
    
    for i in range(n_candles):
        # Simular movimento de preço com tendência
        if i < 50:
            trend = 0.0001  # Tendência de alta inicial
        elif i < 100:
            trend = -0.0001  # Tendência de baixa
        else:
            trend = 0.0002  # Tendência de alta forte
            
        # Adicionar ruído
        noise = np.random.normal(0, 0.0001)
        price_change = trend + noise
        
        current_price += price_change
        
        # Gerar OHLC realístico
        open_price = current_price
        volatility = 0.0005
        high = open_price + abs(np.random.normal(0, volatility))
        low = open_price - abs(np.random.normal(0, volatility))
        close = open_price + np.random.normal(0, volatility/2)
        
        # Garantir que high >= max(open, close) e low <= min(open, close)
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        
        current_price = close
        
        data.append({
            'epoch': 1640995200 + i * 60,  # 2022-01-01 00:00:00 + i minutos
            'open_time': 1640995200 + i * 60,
            'open': round(open_price, 5),
            'high': round(high, 5),
            'low': round(low, 5),
            'close': round(close, 5)
        })
    
    return pd.DataFrame(data)

def test_indicator_factory():
    """Testa a factory de indicadores"""
    print("🧪 Testando IndicatorFactory...")
    
    try:
        factory = IndicatorFactory()
        factory.initialize()
        
        enabled = get_enabled_indicators()
        print(f"✅ Indicadores habilitados: {list(enabled.keys())}")
        
        processors = factory.get_all_processors()
        print(f"✅ Processadores carregados: {len(processors)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na factory: {e}")
        print(traceback.format_exc())
        return False

def test_adapters_calculation():
    """Testa o cálculo de indicadores via adaptadores"""
    print("\n🧪 Testando cálculo de indicadores...")
    
    try:
        df = create_test_data()
        print(f"✅ Dados de teste criados: {len(df)} candles")
        
        factory = IndicatorFactory()
        results = factory.calculate_all_indicators(df)
        
        print(f"✅ Indicadores calculados: {len(results)}")
        
        for result in results:
            status = "✅" if result.trend is not None else "⚠️"
            print(f"{status} {result.name}: {result.trend} "
                  f"(força: {result.strength:.3f}, confiança: {result.confidence:.3f})")
            
            if result.error:
                print(f"   ❌ Erro: {result.error}")
        
        return len(results) > 0
        
    except Exception as e:
        print(f"❌ Erro no cálculo: {e}")
        print(traceback.format_exc())
        return False

def test_consensus_analysis():
    """Testa a análise de consenso"""
    print("\n🧪 Testando análise de consenso...")
    
    try:
        df = create_test_data()
        factory = IndicatorFactory()
        consensus_analyzer = ConsensusAnalyzer()
        
        # Calcular indicadores
        indicator_results = factory.calculate_all_indicators(df)
        
        # Analisar consenso
        consensus_result = consensus_analyzer.analyze_consensus(indicator_results)
        
        print(f"✅ Consenso: {consensus_result.trend}")
        print(f"✅ Indicadores concordantes: {consensus_result.agreeing_count}/{consensus_result.total_count}")
        print(f"✅ Confiança: {consensus_result.confidence:.1f}%")
        print(f"✅ Votação: {consensus_result.vote_breakdown}")
        
        # Verificar se o consenso está funcionando
        has_consensus = consensus_result.trend is not None
        print(f"✅ Consenso alcançado: {has_consensus}")
        
        return has_consensus
        
    except Exception as e:
        print(f"❌ Erro no consenso: {e}")
        print(traceback.format_exc())
        return False

def test_configuration():
    """Testa a configuração do sistema"""
    print("\n🧪 Testando configuração...")
    
    try:
        enabled = get_enabled_indicators()
        consensus_config = get_consensus_config()
        
        print(f"✅ Indicadores configurados: {len(enabled)}")
        print(f"✅ Configuração de consenso: {consensus_config}")
        
        # Verificar se todos os indicadores têm configuração válida
        for name, config in enabled.items():
            required_fields = ['enabled', 'display_name', 'params']
            missing = [field for field in required_fields if field not in config]
            
            if missing:
                print(f"⚠️ {name}: campos faltando {missing}")
            else:
                print(f"✅ {name}: configuração válida")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na configuração: {e}")
        print(traceback.format_exc())
        return False

def test_edge_cases():
    """Testa casos extremos"""
    print("\n🧪 Testando casos extremos...")
    
    try:
        factory = IndicatorFactory()
        consensus_analyzer = ConsensusAnalyzer()
        
        # Teste com poucos dados
        small_df = create_test_data().head(10)
        results_small = factory.calculate_all_indicators(small_df)
        print(f"✅ Poucos dados: {len(results_small)} resultados")
        
        # Teste com dados NaN
        nan_df = create_test_data()
        nan_df.loc[50:60, 'close'] = float('nan')
        results_nan = factory.calculate_all_indicators(nan_df)
        print(f"✅ Dados com NaN: {len(results_nan)} resultados")
        
        # Teste consenso sem resultados
        empty_results = []
        consensus_empty = consensus_analyzer.analyze_consensus(empty_results)
        print(f"✅ Consenso vazio: {consensus_empty.trend}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro em casos extremos: {e}")
        print(traceback.format_exc())
        return False

def main():
    """Executa todos os testes da Phase 2"""
    print("🚀 TESTE PHASE 2 - SISTEMA DINÂMICO INTEGRADO")
    print("=" * 60)
    
    tests = [
        ("Configuração", test_configuration),
        ("IndicatorFactory", test_indicator_factory),
        ("Cálculo de Indicadores", test_adapters_calculation),
        ("Análise de Consenso", test_consensus_analysis),
        ("Casos Extremos", test_edge_cases)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n📋 Executando: {test_name}")
        print("-" * 40)
        results[test_name] = test_func()
    
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES")
    print("=" * 60)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Resultado Final: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 PHASE 2 CONCLUÍDA COM SUCESSO!")
        print("🔧 Sistema dinâmico está funcionando corretamente")
        print("📈 Pronto para uso em produção")
    else:
        print("⚠️ Alguns testes falharam. Revisar implementação.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
