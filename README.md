# 🤖 Sistema Dinâmico de Indicadores Técnicos

Sistema avançado de trading automatizado que analisa múltiplos indicadores técnicos em tempo real e gera sinais de alta precisão para a plataforma Deriv.

## 🎯 Características Principais

- **🔄 Análise Dinâmica**: 4 indicadores técnicos processados automaticamente
- **🧠 Consenso Inteligente**: Sistema de votação entre indicadores
- **⚡ Alta Performance**: Análise completa em < 20ms
- **📱 Notificações Telegram**: Sinais enviados automaticamente
- **🛡️ Gestão de Risco**: Configurações por perfil de risco
- **📊 Logs Detalhados**: Monitoramento completo do sistema

## 📈 Indicadores Suportados

| Indicador | Descrição | Status |
|-----------|-----------|--------|
| **Bandas de Bollinger** | Volatilidade e sobrecompra/sobrevenda | ✅ Ativo |
| **EMA Trend** | Tendência baseada em médias exponenciais | ✅ Ativo |
| **Hull Moving Average** | Média móvel de alta responsividade | ✅ Ativo |
| **Micro Trend** | Análise de tendências de curto prazo | ✅ Ativo |

## 🚀 Instalação Rápida

### 1. Pré-requisitos
- Python 3.9+
- Token API Deriv
- Bot Telegram

### 2. Instalação
```bash
# Clonar repositório
git clone https://github.com/dalexandrias/ms-automation-signals-deriv-v1.git
cd ms-automation-signals-deriv-v1

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp config_exemplos.env .env
# Editar .env com suas configurações
```

### 3. Execução
```bash
python -m app.rise_fall_deriv
```

## ⚙️ Configuração por Perfil de Risco

### 🔴 Alto Risco (Agressivo)
```env
GRANULARITY=60                    # 1 minuto
MIN_CONFIDENCE_TO_SEND=50         # 50% confiança mínima
SIGNAL_COOLDOWN=120               # 2 min entre sinais
```
- **Sinais**: 10-20 por dia
- **Capital**: 1-2% por operação

### 🟡 Médio Risco (Equilibrado) ⭐ RECOMENDADO
```env
GRANULARITY=300                   # 5 minutos
MIN_CONFIDENCE_TO_SEND=70         # 70% confiança mínima
SIGNAL_COOLDOWN=300               # 5 min entre sinais
```
- **Sinais**: 5-10 por dia
- **Capital**: 2-3% por operação

### 🟢 Baixo Risco (Conservador)
```env
GRANULARITY=900                   # 15 minutos
MIN_CONFIDENCE_TO_SEND=85         # 85% confiança mínima
SIGNAL_COOLDOWN=600               # 10 min entre sinais
```
- **Sinais**: 2-5 por dia
- **Capital**: 3-5% por operação

## 📊 Exemplo de Sinal

```
🔖 ID: ABC123XY
🔔 Projeção de próximo candle!
🎯 Projeção: FALL
🕒 Análise: 2025-07-11 18:30:00 (Brasília)
📈 Último preço: 2794.50
🎯 Confiança: 85%
🕒 Entrada no candle: 18:31:00 (Brasília)
```

## 🔧 Configurações Principais

| Parâmetro | Descrição | Exemplo |
|-----------|-----------|---------|
| `GRANULARITY` | Timeframe dos candles (segundos) | `300` (5 min) |
| `MAX_CANDLES` | Histórico para análise | `200` |
| `MIN_CONFIDENCE_TO_SEND` | Confiança mínima (%) | `70` |
| `SIGNAL_COOLDOWN` | Tempo entre sinais (segundos) | `300` |
| `BOLLINGER_THRESHOLD` | Sensibilidade BB | `0.001` |

## 📈 Performance

### Métricas Validadas
- **⚡ Velocidade**: 19.2ms por análise (target: <100ms)
- **🛡️ Estabilidade**: 100% sucessos em testes de carga
- **🎯 Precisão**: 100% detecção de tendências válidas
- **📊 Consenso**: Sistema de votação inteligente

### Indicadores de Qualidade
- **Taxa de acertos esperada**: >65%
- **Profit factor target**: >1.3
- **Drawdown máximo**: <20%

## 📚 Documentação

- **[Manual de Uso](MANUAL_DE_USO.md)**: Guia completo de configuração e uso
- **[Documentação Técnica](DOCUMENTACAO_INDICADORES_DINAMICOS.md)**: Detalhes da implementação
- **[Configurações de Exemplo](config_exemplos.env)**: Templates por perfil de risco

## 🔍 Monitoramento

### Logs Disponíveis
- `logs/app.log`: Logs gerais do sistema
- `logs/signals.log`: Histórico detalhado de sinais

### Métricas em Tempo Real
- Status de cada indicador
- Tempo de processamento
- Qualidade do consenso
- Performance do sistema

## 🛡️ Gestão de Risco

### Recomendações
- **Sempre** teste em conta demo primeiro
- Use apenas capital que pode perder
- Monitore regularmente a performance
- Ajuste configurações conforme mercado
- Mantenha disciplina na gestão de capital

### Sistema de Gale Automático
- **G1**: Automaticamente ativado em caso de perda
- **G2**: Segunda tentativa se G1 falhar
- **Stop**: Para após G2 e aguarda novo sinal

## 🔧 Solução de Problemas

### Problemas Comuns
- **Sem sinais**: Verifique conexão e reduza `MIN_CONFIDENCE_TO_SEND`
- **Muitos falsos positivos**: Aumente confiança mínima e timeframe
- **Erro MongoDB**: Sistema funciona sem DB, apenas com logs

## 📞 Suporte

### Estrutura do Projeto
```
app/
├── indicator_system/     # Sistema dinâmico de indicadores
├── models/              # Modelos de dados
├── repositories/        # Persistência de dados
├── config/             # Configurações
└── rise_fall_deriv.py  # Sistema principal
```

### Requisitos do Sistema
- **OS**: Windows/Linux/macOS
- **Python**: 3.9+
- **RAM**: 512MB mínimo
- **Conexão**: Internet estável
- **MongoDB**: Opcional (para persistência)

## ⚠️ Disclaimer

Este sistema é uma ferramenta de auxílio para análise técnica. Não garante lucros e todo trading envolve risco. Use sempre gestão adequada de risco e teste em conta demo primeiro.

## 📄 Licença

Este projeto está licenciado sob a MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

**Desenvolvido por:** Alex  
**Versão:** 3.0.0 - Sistema Dinâmico Completo  
**Status:** ✅ Produção  

**🎉 BOA SORTE E BOM TRADING! 🎉**
