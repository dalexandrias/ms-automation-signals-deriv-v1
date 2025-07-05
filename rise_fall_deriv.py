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
from indicators import calculate_bollinger_bands, calculate_rsi, calculate_macd, calculate_atr
from trend_analysis import analyze_ema_trend, analyze_hma_trend, calculate_signal_confidence

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

logger.info(f"Configurações carregadas: MAX_CANDLES={max_candles}, GRANULARITY={granularity}, BOLLINGER_THRESHOLD={bollinger_band_threshold}, MIN_CONFIDENCE_TO_SEND={min_confidence_to_send}, SIGNAL_COOLDOWN={signal_cooldown}, VALIDATE_SIGNAL_COOLDOWN={validate_signal_cooldown}")

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

        # Calcular Bollinger Bands
        upper, middle, lower = calculate_bollinger_bands(df, window=10, window_dev=1.5)
        if upper is None or middle is None or lower is None:
            logger.error("Falha ao calcular Bollinger Bands")
            return

        # Filtro de volatilidade – largura mínima das bandas
        band_width = (upper - lower) / middle
        if band_width < bollinger_band_threshold:
            logger.info("⚠️ Bandas de Bollinger muito estreitas. Sem operação!")
            return

        # Calcular RSI
        rsi = calculate_rsi(df, window=14)
        if rsi is None:
            logger.error("Falha ao calcular RSI")
            return

        # Calcular MACD
        macd, macd_signal = calculate_macd(df)
        if macd is None or macd_signal is None:
            logger.error("Falha ao calcular MACD")
            return

        # Calcular ATR e corpo do candle
        atr = calculate_atr(df, window=14)
        if atr is None:
            logger.error("Falha ao calcular ATR")
            return
            
        last = df.iloc[-1]
        body = abs(last['close'] - last['open'])

        # Análise de tendência via EMA
        trend_ema, ema9, ema21 = analyze_ema_trend(df, fast_period=9, slow_period=21)

        # Calcular confiança do sinal com base na tendência EMA
        confidence = calculate_signal_confidence(
            trend_ema, rsi, macd, macd_signal, body, atr, last['close'], upper, lower
        )

        signal = None
        
        # Verificar se temos dados suficientes para HMA e se a confiança é alta o suficiente
        if len(df) >= 100 and confidence >= min_confidence_to_send:
            # Usar HMA para confirmar ou reverter a tendência
            trend_hma = analyze_hma_trend(df)
            
            if trend_hma == trend_ema:
                signal = trend_hma
                logger.info(f"✅ Tendências HMA21 e HMA100 concordam: {trend_hma} | EMA: {trend_ema}")
            else:
                logger.info("⚠️ Tendencia HMA21 e HMA100 não encontrada")
        else:
            logger.info(f"⚠️ Sem dados suficientes para HMA. Dados HMA: {len(df)>=100}, Confiança: {confidence}")

        logger.info(
            f"📈 Análise: EMA9={ema9:.2f}, EMA21={ema21:.2f}, trend_ema={trend_ema}, " +
            f"trend_final={signal if signal is not None else 'Tendencia nao definida'}, " +
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
