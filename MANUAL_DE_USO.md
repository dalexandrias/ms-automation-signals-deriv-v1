# 📖 MANUAL DE USO - SISTEMA DINÂMICO DE INDICADORES

## 🎯 INTRODUÇÃO

Este manual explica como usar o **Sistema Dinâmico de Indicadores Técnicos** para trading automatizado na plataforma Deriv. O sistema analisa múltiplos indicadores em tempo real e gera sinais de compra (RISE) ou venda (FALL) quando há consenso entre os indicadores.

---

## 🚀 INSTALAÇÃO E CONFIGURAÇÃO INICIAL

### 1. **Pré-requisitos**
- Python 3.9 ou superior
- MongoDB (opcional, para persistência)
- Token da API Deriv
- Bot do Telegram configurado

### 2. **Instalação das Dependências**
```bash
cd "c:\Users\dalex\Documents\Linguagem Python\workspace_python\script_deriv"
pip install -r requirements.txt
```

### 3. **Configuração de Variáveis de Ambiente**
Crie um arquivo `.env` na raiz do projeto com:

```env
# === API DERIV ===
DERIV_TOKEN=seu_token_aqui

# === TELEGRAM ===
TELEGRAM_BOT_TOKEN=seu_bot_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui

# === CONFIGURAÇÕES DE TRADING ===
GRANULARITY=60                    # Timeframe em segundos (60 = 1 minuto)
MAX_CANDLES=200                   # Quantidade de candles para análise
MIN_CONFIDENCE_TO_SEND=70         # Confiança mínima para enviar sinal (%)
SIGNAL_COOLDOWN=300               # Tempo entre sinais em segundos
VALIDATE_SIGNAL_COOLDOWN=10       # Tempo para validação em segundos

# === INDICADORES ===
BOLLINGER_THRESHOLD=0.001         # Sensibilidade das Bandas de Bollinger

# === MONGODB (OPCIONAL) ===
MONGODB_CONNECTION_STRING=mongodb://localhost:27018/trading_signals
```

---

## ⚙️ CONFIGURAÇÕES DETALHADAS

### 🎯 **CONFIGURAÇÕES PRINCIPAIS**

#### **GRANULARITY** (Timeframe)
- **Descrição**: Intervalo de tempo de cada candle em segundos
- **Valores aceitos**: 60, 120, 180, 300, 600, 900, 1800, 3600, 14400, 86400
- **Exemplo**: `GRANULARITY=60` (candles de 1 minuto)

| Valor | Timeframe | Uso Recomendado |
|-------|-----------|-----------------|
| 60    | 1 minuto  | Scalping, alta frequência |
| 300   | 5 minutos | Day trading |
| 900   | 15 minutos| Swing trading |
| 3600  | 1 hora    | Posições de médio prazo |

#### **MAX_CANDLES** (Histórico de Análise)
- **Descrição**: Quantidade de candles usados para calcular indicadores
- **Mínimo**: 100 (para HMA funcionar)
- **Recomendado**: 200-500
- **Máximo**: 1000 (pode impactar performance)

#### **MIN_CONFIDENCE_TO_SEND** (Filtro de Qualidade)
- **Descrição**: Confiança mínima necessária para enviar um sinal
- **Faixa**: 10-100%
- **Cálculo**: Baseado no consenso entre indicadores válidos

#### **SIGNAL_COOLDOWN** (Controle de Frequência)
- **Descrição**: Tempo mínimo entre sinais consecutivos
- **Propósito**: Evitar spam de sinais
- **Recomendado**: 120-600 segundos

#### **BOLLINGER_THRESHOLD** (Sensibilidade)
- **Descrição**: Limiar para considerar rompimento das Bandas de Bollinger
- **Menor valor**: Mais sinais (mais sensível)
- **Maior valor**: Menos sinais (mais conservador)

---

## 🎚️ CONFIGURAÇÕES POR PERFIL DE RISCO

### 🔴 **PERFIL ALTO RISCO - ALTA FREQUÊNCIA**
*Para traders experientes que buscam muitas oportunidades*

```env
# Configuração Alto Risco
GRANULARITY=60                    # 1 minuto - muitas oportunidades
MAX_CANDLES=150                   # Análise mais rápida
MIN_CONFIDENCE_TO_SEND=50         # Aceita sinais com menor consenso
SIGNAL_COOLDOWN=120               # 2 minutos entre sinais
BOLLINGER_THRESHOLD=0.0005        # Muito sensível a movimentos
VALIDATE_SIGNAL_COOLDOWN=5        # Validação rápida
```

**Características:**
- ✅ **Vantagens**: Muitos sinais, oportunidades frequentes
- ⚠️ **Riscos**: Mais falsos positivos, requer acompanhamento constante
- 📊 **Sinais esperados**: 10-20 por dia
- 💰 **Gestão**: Use apenas 1-2% do capital por operação

---

### 🟡 **PERFIL MÉDIO RISCO - EQUILIBRADO**
*Para traders com experiência moderada*

```env
# Configuração Médio Risco (RECOMENDADA)
GRANULARITY=300                   # 5 minutos - equilíbrio
MAX_CANDLES=200                   # Análise balanceada
MIN_CONFIDENCE_TO_SEND=70         # Boa qualidade de sinais
SIGNAL_COOLDOWN=300               # 5 minutos entre sinais
BOLLINGER_THRESHOLD=0.001         # Sensibilidade padrão
VALIDATE_SIGNAL_COOLDOWN=10       # Validação padrão
```

**Características:**
- ✅ **Vantagens**: Equilíbrio entre frequência e qualidade
- ⚠️ **Riscos**: Moderado, boa relação risco/retorno
- 📊 **Sinais esperados**: 5-10 por dia
- 💰 **Gestão**: Use 2-3% do capital por operação

---

### 🟢 **PERFIL BAIXO RISCO - CONSERVADOR**
*Para iniciantes ou trading com capital significativo*

```env
# Configuração Baixo Risco
GRANULARITY=900                   # 15 minutos - movimentos sólidos
MAX_CANDLES=300                   # Análise mais robusta
MIN_CONFIDENCE_TO_SEND=85         # Apenas sinais de alta qualidade
SIGNAL_COOLDOWN=600               # 10 minutos entre sinais
BOLLINGER_THRESHOLD=0.002         # Menos sensível, mais conservador
VALIDATE_SIGNAL_COOLDOWN=15       # Validação mais cuidadosa
```

**Características:**
- ✅ **Vantagens**: Alta precisão, poucos falsos positivos
- ⚠️ **Limitações**: Menos oportunidades, movimentos maiores necessários
- 📊 **Sinais esperados**: 2-5 por dia
- 💰 **Gestão**: Use 3-5% do capital por operação

---

## 🔧 CONFIGURAÇÕES AVANÇADAS DOS INDICADORES

### 📊 **Personalização em `app/config/indicators.py`**

```python
INDICATOR_CONFIG = {
    'BB': {  # Bandas de Bollinger
        'enabled': True,                    # Ativar/desativar indicador
        'period': 20,                       # Período para cálculo (padrão: 20)
        'std_dev': 2,                       # Desvios padrão (padrão: 2)
        'min_confidence': 0.6,              # Confiança mínima (60%)
        'weight_formula': 'strength * confidence',  # Fórmula de peso
        'validation_rules': {
            'min_data_points': 20,          # Mínimo de dados necessários
            'volatility_threshold': 0.1     # Limite de volatilidade
        }
    },
    
    'EMA': {  # Exponential Moving Average
        'enabled': True,
        'short_period': 12,                 # EMA curta (padrão: 12)
        'long_period': 26,                  # EMA longa (padrão: 26)
        'min_confidence': 0.5,
        'weight_formula': 'strength * 0.8'  # Peso menor que BB
    },
    
    'HMA': {  # Hull Moving Average
        'enabled': True,
        'period': 100,                      # Período HMA (padrão: 100)
        'min_confidence': 0.6,
        'weight_formula': 'strength * confidence * 1.1'  # Peso maior
    },
    
    'MICRO': {  # Micro Trend
        'enabled': True,
        'lookback_period': 10,              # Período de análise
        'min_confidence': 0.4,
        'weight_formula': 'strength * 0.7'
    }
}

# Configurações de Consenso
CONSENSUS_CONFIG = {
    'min_indicators': 2,                    # Mínimo de indicadores concordantes
    'consensus_threshold': 0.6,             # Limiar para consenso (60%)
    'unanimous_bonus': 0.2,                 # Bônus para unanimidade
    'partial_consensus_penalty': 0.1       # Penalidade para consenso parcial
}
```

---

## 🎮 COMO USAR O SISTEMA

### 1. **Inicialização**
```bash
# Execute sempre do diretório raiz:
cd "c:\Users\dalex\Documents\Linguagem Python\workspace_python\script_deriv"
python -m app.rise_fall_deriv
```

### 2. **Monitoramento dos Logs**
O sistema gera logs detalhados mostrando:
- ✅ Conexão com Deriv API
- 📊 Análise de cada indicador
- 🤖 Resultado do consenso
- 🎯 Geração de sinais
- ✉️ Envio para Telegram

### 3. **Interpretação dos Sinais**
```
🚨 SINAL DETECTADO: FALL | ID: ABC123XY | Confiança: 85.0%
📈 Consenso: FALL
🔢 Indicadores: 3/4
💯 Confiança: 85.0%
📊 Indicadores: Bollinger Bands=FALL, Hull MA=FALL, EMA=FALL
```

### 4. **Notificações no Telegram**
```
🔖 ID: ABC123XY
🔔 Projeção de próximo candle!
🎯 Projeção: FALL
🕒 Análise: 2025-07-11 18:30:00 (Brasília)
📈 Último preço: 2794.50
🎯 Confiança: 85%
🕒 Entrada no candle: 18:31:00 (Brasília)
```

---

## 📊 INTERPRETAÇÃO DOS INDICADORES

### 🎯 **Status dos Indicadores**

| Status | Significado | Ação |
|--------|-------------|------|
| ✅ **RISE** | Tendência de alta detectada | Considerar compra |
| ❌ **FALL** | Tendência de baixa detectada | Considerar venda |
| ⚠️ **SIDEWAYS** | Lateral/indeciso | Aguardar definição |

### 🔢 **Níveis de Confiança**

| Confiança | Qualidade | Recomendação |
|-----------|-----------|--------------|
| 90-100% | Excelente | Sinal muito forte, baixo risco |
| 80-89% | Muito Boa | Sinal confiável, risco baixo |
| 70-79% | Boa | Sinal válido, risco moderado |
| 60-69% | Regular | Sinal aceitável, risco elevado |
| < 60% | Baixa | Evitar, aguardar melhor oportunidade |

### ⚖️ **Consenso Entre Indicadores**

| Concordância | Força do Sinal | Ação Recomendada |
|--------------|----------------|-------------------|
| 4/4 indicadores | 🔥 Muito Forte | Entrada com confiança |
| 3/4 indicadores | 💪 Forte | Entrada recomendada |
| 2/4 indicadores | ⚡ Moderado | Entrada com cautela |
| 1/4 indicadores | ⚠️ Fraco | Aguardar confirmação |

---

## 🛡️ GESTÃO DE RISCO

### 💰 **Recomendações de Capital**

#### **Por Perfil de Risco:**
- **Alto Risco**: 1-2% do capital por operação
- **Médio Risco**: 2-3% do capital por operação  
- **Baixo Risco**: 3-5% do capital por operação

#### **Por Nível de Confiança:**
- **90-100%**: Até o máximo do seu perfil
- **80-89%**: 75% do máximo do seu perfil
- **70-79%**: 50% do máximo do seu perfil
- **60-69%**: 25% do máximo do seu perfil

### 🎯 **Estratégia de Gale (Martingale)**
O sistema suporta automaticamente estratégia de gale:
- **G1**: Se perder, dobra o valor na próxima
- **G2**: Se G1 perder, dobra novamente
- **Stop**: Após G2, para e aguarda novo sinal

### ⏰ **Horários Recomendados**
- **Melhor liquidez**: 08:00 - 18:00 (horário de Londres)
- **Evitar**: Finais de semana e feriados
- **Cuidado**: Horários de notícias econômicas importantes

---

## 📈 OTIMIZAÇÃO E AJUSTES

### 🔍 **Análise de Performance**
Monitore regularmente:
- **Taxa de acertos**: Meta > 65%
- **Frequência de sinais**: Ajuste conforme necessário
- **Drawdown máximo**: Não deve exceder 20% do capital
- **Profit factor**: Meta > 1.3

### ⚙️ **Ajustes Finos**

#### **Se muitos sinais falsos:**
- ⬆️ Aumentar `MIN_CONFIDENCE_TO_SEND`
- ⬆️ Aumentar `BOLLINGER_THRESHOLD`
- ⬆️ Aumentar `GRANULARITY`

#### **Se poucos sinais:**
- ⬇️ Diminuir `MIN_CONFIDENCE_TO_SEND`
- ⬇️ Diminuir `BOLLINGER_THRESHOLD`
- ⬇️ Diminuir `GRANULARITY`

#### **Para melhor estabilidade:**
- ⬆️ Aumentar `MAX_CANDLES`
- ⬆️ Aumentar `SIGNAL_COOLDOWN`
- 🔧 Ativar mais indicadores

---

## 🔧 SOLUÇÃO DE PROBLEMAS

### ❌ **Problemas Comuns**

#### **Sistema não gera sinais:**
- ✅ Verifique conexão com internet
- ✅ Confirme token Deriv válido
- ✅ Reduza `MIN_CONFIDENCE_TO_SEND`
- ✅ Verifique se indicadores estão habilitados

#### **Muitos sinais falsos:**
- ✅ Aumente confiança mínima
- ✅ Use timeframe maior
- ✅ Aumente cooldown entre sinais

#### **Erro de conexão MongoDB:**
- ✅ Verifique se MongoDB está rodando
- ✅ Confirme string de conexão
- ✅ Sistema funciona sem MongoDB (apenas logs)

#### **Não recebe notificações Telegram:**
- ✅ Verifique token do bot
- ✅ Confirme chat_id correto
- ✅ Bot deve estar ativo no chat

### 📞 **Logs para Debug**
Monitore os arquivos de log:
- `logs/app.log`: Logs gerais do sistema
- `logs/signals.log`: Logs específicos de sinais

---

## 🎯 EXEMPLOS PRÁTICOS

### 🟢 **Configuração Conservadora - Iniciante**
```env
GRANULARITY=900
MAX_CANDLES=300
MIN_CONFIDENCE_TO_SEND=90
SIGNAL_COOLDOWN=1800
BOLLINGER_THRESHOLD=0.003
```

### 🟡 **Configuração Balanceada - Intermediário**
```env
GRANULARITY=300
MAX_CANDLES=200
MIN_CONFIDENCE_TO_SEND=75
SIGNAL_COOLDOWN=600
BOLLINGER_THRESHOLD=0.0015
```

### 🔴 **Configuração Agressiva - Avançado**
```env
GRANULARITY=60
MAX_CANDLES=150
MIN_CONFIDENCE_TO_SEND=55
SIGNAL_COOLDOWN=180
BOLLINGER_THRESHOLD=0.0008
```

---

## 📚 RECURSOS ADICIONAIS

### 🔗 **Links Úteis**
- [Documentação API Deriv](https://developers.deriv.com/)
- [Guia Bandas de Bollinger](https://www.investopedia.com/bollinger-bands/)
- [Estratégias de Moving Average](https://www.investopedia.com/moving-averages/)

### 📖 **Documentação Técnica**
- `DOCUMENTACAO_INDICADORES_DINAMICOS.md`: Documentação completa do sistema
- `test_phase2.py` e `test_phase3.py`: Exemplos de testes
- `app/config/indicators.py`: Configurações detalhadas

---

## ⚠️ DISCLAIMER

**AVISO IMPORTANTE**: Este sistema é uma ferramenta de auxílio para análise técnica. Não garante lucros e todo trading envolve risco de perda. Sempre:

- 📚 Estude e entenda o mercado
- 💰 Use apenas capital que pode perder
- 🧪 Teste em conta demo primeiro
- 📊 Monitore e ajuste constantemente
- 🛡️ Mantenha gestão de risco rigorosa

**O sistema é fornecido "como está" sem garantias. O usuário é totalmente responsável por suas decisões de trading.**

---

**🎉 BOA SORTE E BOM TRADING! 🎉**
