import os
import logging
import json
import secrets
import string
import threading
from datetime import datetime, timedelta

import pandas as pd
import ta
import pytz
import websocket
import requests

from repository import MongoDBRepository
from log_config import setup_logging

# === CONFIGURAÇÕES ENV ===
TOKEN = os.getenv('DERIV_TOKEN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
socket_url = "wss://ws.derivws.com/websockets/v3?app_id=72200"
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

granularity = int(os.getenv('GRANULARITY', '60'))
max_candles = int(os.getenv('MAX_CANDLES', '50'))
bollinger_band_threshold = float(os.getenv('BOLLINGER_THRESHOLD', '0.001'))
min_confidence_to_send = int(os.getenv('MIN_CONFIDENCE_TO_SEND', '20'))
# Tempo de cooldown após envio de sinal em segundos
signal_cooldown = int(os.getenv('SIGNAL_COOLDOWN', '120'))
validate_signal_cooldown = int(os.getenv('VALIDATE_SIGNAL_COOLDOWN', '120'))

# === CONFIGURAÇÃO DE LOG ===
setup_logging()
logger = logging.getLogger()               # root logger
signal_logger = logging.getLogger('signals')  # logger para sinais

logger.info(f"Configurações carregadas: MAX_CANDLES={max_candles}, GRANULARITY={granularity}")

# === VARIÁVEIS GLOBAIS ===
data_candles = []
last_open_time = None
last_signal_time = None  # Timestamp do último sinal enviado
pending_ids = []         # Lista de IDs de sinais aguardando validação

# === Geração de IDs ===
def generate_signal_id(length: int = 8) -> str:
    """Gera ID alfanumérico único."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# === Tempo e mensagem ===
def get_brazil_time(utc_dt: datetime) -> datetime:
    br_tz = pytz.timezone('America/Sao_Paulo')
    return utc_dt.replace(tzinfo=pytz.utc).astimezone(br_tz)


def calculate_entry_time(br_time: datetime) -> datetime:
    return br_time + timedelta(minutes=1)


def compose_telegram_message(signal_id: str, signal: str, price: float, confidence: int,
                             analyze_time: datetime, entry_time: datetime) -> str:
    return (
        f"🔖 ID: {signal_id}\n"
        f"🔔 Projeção de próximo candle!\n"
        f"🎯 Projeção: {signal}\n"
        f"🕒 Análise: {analyze_time.strftime('%Y-%m-%d %H:%M:%S')} (Brasília)\n"
        f"📈 Último preço: {price}\n"
        f"🎯 Confiança: {confidence}%\n"
        f"🕒 Entrada no candle: {entry_time.strftime('%Y-%m-%d %H:%M:%S')} (Brasília)"
    )

# === Envio e persistência ===
def send_to_telegram(message: str) -> tuple:
    
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    resp = requests.post(URL_TELEGRAM, data=payload)
    resp.raise_for_status()
    msg = resp.json()['result']
    message_id = msg['message_id']
    chat_id    = msg['chat']['id']
    return message_id, chat_id

# === Hull Moving Average ===
def hull_moving_average(series, period: int):
    """
    Calcula o Hull Moving Average (HMA) para uma série de dados.
    
    Args:
        series: Série pandas com os valores de preço
        period: Período para o cálculo do HMA
    
    Returns:
        Uma série pandas com os valores do HMA calculados
    """
    try:
        # Verificar se a série tem dados suficientes
        if len(series) < period:
            logger.warning(f"Série com tamanho insuficiente para calcular HMA com período {period}. Tamanho atual: {len(series)}")
            return pd.Series([float('nan')] * len(series), index=series.index)
        
        # 1. Calcula o WMA com metade do período
        half_period = max(1, int(period/2))  # Garantir que half_period seja pelo menos 1
        
        def weighted_mean(x):
            # Verificar se x tem dados suficientes
            if len(x) == 0:
                return float('nan')
            
            # Calcular os pesos
            weights = np.array([(i+1) for i in range(len(x))])
            
            # Verificar se a soma dos pesos é zero
            if weights.sum() == 0:
                return float('nan')
                
            # Calcular a média ponderada
            return np.sum(weights * x) / weights.sum()
        
        # Importar numpy para cálculos mais eficientes
        import numpy as np
        
        # Usar apply com tratamento de erros
        wma_half = series.rolling(window=half_period, min_periods=half_period).apply(
            weighted_mean, raw=True
        )
        
        # 2. Calcula o WMA com período completo
        wma_full = series.rolling(window=period, min_periods=period).apply(
            weighted_mean, raw=True
        )
        
        # 3. Calcula o Raw HMA = 2 * WMA(n/2) - WMA(n)
        raw_hma = 2 * wma_half - wma_full
        
        # 4. Aplica o WMA final com período = sqrt(n)
        sqrt_period = max(1, int(period ** 0.5))  # Garantir que sqrt_period seja pelo menos 1
        
        hma = raw_hma.rolling(window=sqrt_period, min_periods=sqrt_period).apply(
            weighted_mean, raw=True
        )
        
        # Substituir valores NaN por valores anteriores válidos
        hma = hma.fillna(method='ffill')
        
        return hma
    except Exception as e:
        logger.error(f"Erro ao calcular HMA: {e}")
        import traceback
        logger.error(f"Detalhes do erro no HMA: {traceback.format_exc()}")
        # Retornar uma série de NaN com o mesmo índice da série original
        return pd.Series([float('nan')] * len(series), index=series.index)

def reply_result(signal_id: str):
    repo = MongoDBRepository()
    doc = repo.find_one({'signal_id': signal_id})

    if not doc or 'message_id' not in doc:
        return

    chat_id    = int(doc['chat_id'])       # se você guardou o chat
    message_id = int(doc['message_id'])
    result = str(doc['result'])

    if result is None:
        return
    elif result == 'WIN':
        text = f"✅ Resultado para o sinal {signal_id}: *{result}*"
    else:
        text = f"❌ Resultado para o sinal {signal_id}: *{result}*"

    payload = {
      'chat_id': chat_id,
      'text': text,
      'reply_to_message_id': message_id,
      'parse_mode': 'Markdown'
    }
    requests.post(URL_TELEGRAM, data=payload)

def persist_signal(doc: dict) -> None:
    repo = MongoDBRepository()
    repo.insert_one(doc)


def log_signal(signal_id: str, signal: str, price: float, confidence: int, entry_time: datetime) -> None:
    logger.info(f"✅ Mensagem enviada ao Telegram (ID: {signal_id}).")
    signal_logger.info(
        f"[{signal_id}] Signal: {signal} | Price: {price} | Confidence: {confidence}% | Entry: {entry_time}"
    )

def handle_signal(signal: str, price: float, confidence: int, open_time: int) -> None:
    """Orquestra geração de ID, envio, log e persistência."""

    global last_signal_time, last_open_time
    # Não enviar sinal antes de receber o primeiro candle OHL (last_open_time definido)
    if last_open_time is None:
        logger.info("🔄 Ignorando sinal inicial antes de primeiro candle OHL.")
        return
    now = datetime.utcnow()
    # Verifica cooldown
    if last_signal_time and (now - last_signal_time).total_seconds() < signal_cooldown:
        wait = signal_cooldown - int((now - last_signal_time).total_seconds())
        logger.info(f"⏳ Em cooldown ({signal_cooldown}s). Próximo sinal em {wait}s.")
        return
    
    signal_id = generate_signal_id()
    analyze_time = get_brazil_time(now)
    entry_time = calculate_entry_time(analyze_time)
    message = compose_telegram_message(signal_id, signal, price, confidence, analyze_time, entry_time)

    try:
        # 3. Envio e log
        message_id, chat_id = send_to_telegram(message)
        log_signal(signal_id, signal, price, confidence, entry_time)

        # 4. Persistência e registro para validação
        doc = {
            'signal_id': signal_id,
            'signal': signal,
            'price': price,
            'confidence': confidence,
            'analyze_time': analyze_time,
            'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'open_candle_timestamp': open_time,
            'message_id': message_id,
            'chat_id': chat_id,
            'result': None  # Inicialmente None, será atualizado após validação
        }
        persist_signal(doc)
        pending_ids.append(signal_id)
        last_signal_time = now
    except Exception as e:
        logger.error(f"Erro ao processar sinal {signal_id}: {e}")

def validate_signals_for_candle(open_price: float, close_price: float) -> None:
    """
    Itera pelos IDs em pending_ids, busca cada sinal no MongoDB,
    avalia WIN/LOSS e atualiza o documento, removendo-o da lista.
    """
    logger.info(f"Iniciando metodo validate_signals_for_candle")
    repo = MongoDBRepository()
    to_remove = []
    for signal_id in pending_ids:
        doc = repo.find_one({'signal_id': signal_id})
        if not doc:
            to_remove.append(signal_id)
            continue
        signal = doc['signal']
        open_candle_timestamp = doc['open_candle_timestamp']
        candle_signal = next((candle for candle in data_candles if candle[0] == open_candle_timestamp), None)
        if candle_signal:
            open_price = candle_signal[1]
            close_price = candle_signal[4]
        else:
            logger.info(f"⚠️ Sinal {signal_id} não encontrado no candle atual.")
            continue
        # Avalia resultado
        win = (signal == 'RISE' and close_price > open_price) or \
              (signal == 'FALL' and close_price < open_price)
        result = 'WIN' if win else 'LOSS'
        repo.update_one({'signal_id': signal_id}, {'$set': {'result': result}})
        logger.info(f"Sinal {signal_id} validado como {result}")
        # Envia resultado para o Telegram
        reply_result(signal_id)
        to_remove.append(signal_id)
    # Limpa processed IDs
    for sid in to_remove:
        pending_ids.remove(sid)
    logger.info(f"Finalizando metodo validate_signals_for_candle")

def process_candles() -> None:
    """Processa candles, calcula indicadores e gera sinais."""
    global data_candles, last_open_time
    if len(data_candles) < max_candles:
        logger.info(f"Dados insuficientes para processar. Necessário: {max_candles}, Disponível: {len(data_candles)}")
        return
    try:
        # Verificar a estrutura dos dados antes de criar o DataFrame
        logger.info(f"Estrutura dos dados: {data_candles[0]}")
        
        # Criar o DataFrame a partir dos dados
        df = pd.DataFrame(data_candles[-max_candles:])
        
        # Renomear as colunas após criar o DataFrame
        if len(df.columns) >= 5:
            df.columns = ['epoch', 'open', 'high', 'low', 'close']
        else:
            logger.error(f"DataFrame com número incorreto de colunas: {len(df.columns)}. Esperado: 5")
            return
            
        # Converter para tipos numéricos
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # Verificar se há valores NaN após a conversão
        nan_counts = df.isna().sum()
        if nan_counts.sum() > 0:
            logger.warning(f"Valores NaN detectados no DataFrame após conversão: {nan_counts}")
            
        df['time'] = pd.to_datetime(df['epoch'], unit='s')

        # 5) Bollinger Bands (necessário para o filtro de volatilidade)
        try:
            from ta.volatility import BollingerBands
            bb = BollingerBands(df['close'], window=10, window_dev=1.5)
            upper = bb.bollinger_hband().iloc[-1]
            middle = bb.bollinger_mavg().iloc[-1]
            lower = bb.bollinger_lband().iloc[-1]
        except (ImportError, AttributeError):
            # Fallback caso a biblioteca ta não tenha o módulo volatility
            # Calcula média móvel simples
            sma = df['close'].rolling(window=10).mean()
            # Calcula o desvio padrão
            std = df['close'].rolling(window=10).std()
            upper = (sma + (std * 1.5)).iloc[-1]
            middle = sma.iloc[-1]
            lower = (sma - (std * 1.5)).iloc[-1]

        # 0) Filtro de volatilidade – largura mínima das bandas
        band_width = (upper - lower) / middle
        if band_width < bollinger_band_threshold:
            logger.info("⚠️ Bandas de Bollinger muito estreitas. Sem operação!")
            return

        # 1) Tendência via EMA9 e EMA21
        ema9 = df['close'].ewm(span=9, adjust=False).mean().iloc[-1]
        ema21 = df['close'].ewm(span=21, adjust=False).mean().iloc[-1]
        trend_ema = 'RISE' if ema9 > ema21 else 'FALL'
        
        # 1.1) Tendência via Hull Moving Average (HMA) com períodos 21 e 100
        # Calculamos apenas se temos dados suficientes
        logger.info(f"Verificando dados para HMA. Tamanho do DataFrame: {len(df)}")
        
        if len(df) >= 100:
            try:
                # Calcular HMA para os últimos 5 candles para determinar a direção
                logger.info("Calculando HMA21...")
                hma21_values = hull_moving_average(df['close'], 21).iloc[-5:].values
                
                logger.info("Calculando HMA100...")
                hma100_values = hull_moving_average(df['close'], 100).iloc[-5:].values
                
                # Verificar se os valores são válidos (não são NaN)
                import numpy as np
                if np.isnan(hma21_values).any() or np.isnan(hma100_values).any():
                    logger.warning("Valores NaN detectados no HMA. Usando EMA como fallback.")
                    trend = trend_ema
                    trend_confidence = 20  # Confiança padrão
                else:
                    # Verifica se as médias estão subindo ou descendo
                    hma21_direction = 'RISE' if hma21_values[-1] > hma21_values[0] else 'FALL'
                    hma100_direction = 'RISE' if hma100_values[-1] > hma100_values[0] else 'FALL'
                    
                    # Se ambas as médias estiverem na mesma direção, segue essa tendência
                    if hma21_direction == hma100_direction:
                        trend_hma = hma21_direction
                        trend_confidence = 30  # Maior confiança quando ambas concordam na direção
                    else:
                        # Se houver divergência, usa a direção do HMA21 (mais sensível a mudanças recentes)
                        trend_hma = hma21_direction
                        trend_confidence = 20  # Confiança padrão em caso de divergência
                    
                    # Define a tendência final com base no HMA
                    trend = trend_hma
                    
                    # Para log, guardamos os valores atuais
                    hma21 = hma21_values[-1]
                    hma100 = hma100_values[-1]
                    
                    logger.info(f"📊 HMA: HMA21={hma21:.2f} ({hma21_direction}), HMA100={hma100:.2f} ({hma100_direction}), trend_hma={trend_hma}")
            except Exception as e:
                logger.error(f"Erro ao processar HMA: {e}")
                import traceback
                logger.error(f"Detalhes do erro no processamento do HMA: {traceback.format_exc()}")
                # Fallback para EMA em caso de erro
                trend = trend_ema
                trend_confidence = 20  # Confiança padrão
        else:
            # Se não temos dados suficientes, continuamos usando apenas EMA
            trend = trend_ema
            trend_confidence = 20  # Confiança padrão
            logger.info(f"⚠️ Dados insuficientes para HMA, usando apenas EMA. Necessário: 100, Disponível: {len(df)}")

        # 2) RSI
        try:
            from ta.momentum import RSIIndicator
            rsi = RSIIndicator(df['close'], window=14).rsi().iloc[-1]
        except (ImportError, AttributeError):
            # Implementação manual de RSI
            delta = df['close'].diff()
            gain = delta.mask(delta < 0, 0)
            loss = -delta.mask(delta > 0, 0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]

        # 3) MACD
        try:
            from ta.trend import MACD
            macd_ind = MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
            macd = macd_ind.macd().iloc[-1]
            macd_signal = macd_ind.macd_signal().iloc[-1]
        except (ImportError, AttributeError):
            # Implementação manual de MACD
            ema12 = df['close'].ewm(span=12, adjust=False).mean()
            ema26 = df['close'].ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            macd_signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd = macd_line.iloc[-1]
            macd_signal = macd_signal_line.iloc[-1]

        # 4) ATR + corpo do candle
        try:
            from ta.volatility import AverageTrueRange
            atr = AverageTrueRange(
                df['high'], df['low'], df['close'], window=14
            ).average_true_range().iloc[-1]
        except (ImportError, AttributeError):
            # Implementação manual de ATR
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(window=14).mean().iloc[-1]
            
        last = df.iloc[-1]
        body = abs(last['close'] - last['open'])

        # Confiança inicial com tendência
        confidence = trend_confidence
        # Ajustes por indicadores
        if trend == 'RISE' and rsi >= 60:
            confidence += 20
        if trend == 'FALL' and rsi <= 40:
            confidence += 20
        if trend == 'RISE' and macd > macd_signal:
            confidence += 20
        if trend == 'FALL' and macd < macd_signal:
            confidence += 20
        if body >= 0.5 * atr:
            confidence += 20
        if (trend == 'RISE' and last['close'] > upper) or (trend == 'FALL' and last['close'] < lower):
            confidence += 20

        signal = trend if confidence >= min_confidence_to_send else None

        logger.info(
            f"📈 Análise: EMA9={ema9:.2f}, EMA21={ema21:.2f}, trend_ema={trend_ema}, " +
            (f"HMA21={hma21:.2f}, HMA100={hma100:.2f}, trend_hma={trend_hma}, " if 'hma21' in locals() else "") +
            f"trend_final={trend}, " +
            f"RSI={rsi:.2f}, MACD={macd:.2f}/{macd_signal:.2f}, ATR={atr:.2f}, " +
            f"body={body:.2f}, band_width={band_width:.3f}, confidence={confidence}"
        )

        if signal:
            logger.info(f"🚨 SINAL DETECTADO: {signal} | Confiança: {confidence}%")
            next_candle_time = df['time'].iloc[-1] + pd.Timedelta(seconds=granularity+58)
            next_candle_time_timestamp = int(next_candle_time.timestamp())
            handle_signal(signal, last['close'], confidence, next_candle_time_timestamp)
        else:
            logger.info("⚡ Sem sinal forte. Aguardando próximo candle.")

    except Exception as e:
        logger.error(f"⚠️ Erro no processamento dos candles: {e}")
        import traceback
        logger.error(f"Detalhes do erro: {traceback.format_exc()}")

# === WebSocket Callbacks ===
def handle_authorize(ws) -> None:
    logger.info(f"Token autorizado. Solicitando {max_candles} candles históricos...")
    
    # Solicitar mais candles do que o necessário para o HMA100 funcionar
    req = {
        "ticks_history": "R_25",
        "style": "candles",
        "granularity": granularity,
        "count": max_candles,
        "end": "latest",
        "subscribe": 1
    }
    logger.info(f"Enviando requisição: {req}")
    ws.send(json.dumps(req))
    logger.info(f"✅ Token autorizado às {datetime.utcnow()} UTC")


def handle_initial_candles(data: dict) -> None:
    global data_candles
    logger.info(f"Recebendo histórico inicial com {len(data['candles'])} candles")
    
    # Verificar estrutura do primeiro candle
    if data['candles'] and len(data['candles']) > 0:
        logger.info(f"Estrutura do primeiro candle: {data['candles'][0]}")
    
    for c in data['candles']:
        data_candles.append((
            c['epoch'], 
             float(c['open']), 
             float(c['high']),
             float(c['low']), 
             float(c['close'])
        ))
    data_candles = data_candles[-max_candles:]
    logger.info(f"📥 Histórico inicial recebido às {datetime.utcnow()} UTC. Total de candles: {len(data_candles)}")
    process_candles()


def handle_ohlc(data: dict) -> None:
    global data_candles, last_open_time
    candle = data['ohlc']
    current_open_time = int(candle['open_time'])
    open_price, close_price = float(candle['open']), float(candle['close'])

    data_candles.append((
            candle['epoch'], 
            float(candle['open']), 
            float(candle['high']),
            float(candle['low']), 
            float(candle['close'])
        ))

    if len(data_candles) > max_candles:
        data_candles = data_candles[-max_candles:]
    
    if last_open_time is None:
        last_open_time = current_open_time

    if current_open_time != last_open_time:
        logger.info(f"🔔 Novo candle em {datetime.utcfromtimestamp(candle['epoch'])} UTC")

        prev = data_candles[-1]
        prev_open, prev_close = prev[1], prev[4]
        
        if pending_ids is not None and len(pending_ids) > 0:
            # Se houver sinais pendentes, agenda a validação
            threading.Timer(
                validate_signal_cooldown,
                lambda: validate_signals_for_candle(prev_open, prev_close)
            ).start()
            logger.info(f"⏳ Agendada validação do candle {last_open_time} em {validate_signal_cooldown}s.")

        process_candles()

    last_open_time = current_open_time


def on_message(ws, message: str) -> None:
    try:
        data = json.loads(message)
        
        # Verificar se há erros na resposta da API
        if 'error' in data:
            logger.error(f"Erro na resposta da API: {data['error']}")
            return
            
        msg_type = data.get('msg_type')
        logger.debug(f"Mensagem recebida: {msg_type}")
        
        if msg_type == 'authorize':
            handle_authorize(ws)
        elif msg_type == 'candles':
            handle_initial_candles(data)
        elif msg_type == 'ohlc':
            handle_ohlc(data)
        else:
            logger.info(f"Tipo de mensagem não tratada: {msg_type}")
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}")
        logger.error(f"Mensagem recebida: {message[:200]}...")  # Limitar o tamanho do log
        import traceback
        logger.error(f"Detalhes do erro: {traceback.format_exc()}")


def on_error(ws, error: Exception) -> None:
    logger.error(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg) -> None:
    logger.warning(f"Conexão WebSocket fechada. Status: {close_status_code}, Mensagem: {close_msg}")


def on_open(ws) -> None:
    ws.send(json.dumps({"authorize": TOKEN}))

# === EXECUÇÃO PRINCIPAL ===
if __name__ == '__main__':
    logger.info("🔗 Conectando ao WebSocket...")
    ws = websocket.WebSocketApp(
        socket_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    threading.Thread(target=ws.run_forever).start()
    logger.info("🔗 Conexão WebSocket estabelecida. Aguardando dados...")
