import os
import logging
from logging.handlers import TimedRotatingFileHandler
import json
import secrets
import string
import pytz
import threading
from datetime import datetime, timedelta

import pandas as pd
import ta
import websocket
import requests
from repository import MongoDBRepository
from log_config import setup_logging

# === CONFIGURAÇÕES ENV ===
TOKEN = os.getenv('DERIV_TOKEN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
socket_url = "wss://ws.derivws.com/websockets/v3?app_id=72200"

granularity = int(os.getenv('GRANULARITY', '60'))
max_candles = int(os.getenv('MAX_CANDLES', '50'))
bollinger_band_threshold = float(os.getenv('BOLLINGER_THRESHOLD', '0.001'))
min_confidence_to_send = int(os.getenv('MIN_CONFIDENCE_TO_SEND', '50'))

# === CONFIGURAÇÃO DE LOG ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Logger principal
setup_logging()
logger = logging.getLogger() # root logger
signal_logger = logging.getLogger('signals')  # logger específico para sinais

# === VARIÁVEIS GLOBAIS ===
data_candles = []
last_open_time = None

# === FUNÇÕES ===
# === Geração de IDs simples e únicos ===
def generate_signal_id(length: int = 8) -> str:
    """
    Gera um ID aleatório de `length` caracteres alfanuméricos
    usando o módulo secrets para garantir unicidade razoável.
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def send_telegram_message(signal, last_close, confidence):
    # Gera um ID único para este sinal
    signal_id = generate_signal_id()

    utc_now = datetime.utcnow()
    br_tz = pytz.timezone('America/Sao_Paulo')
    br_time = utc_now.replace(tzinfo=pytz.utc).astimezone(br_tz)
    next_candle_time = br_time + timedelta(minutes=1)

    message = (
        f"🔖 ID: {signal_id}\n"
        f"🔔 Projeção de próximo candle!\n"
        f"🎯 Projeção: {signal}\n"
        f"🕒 Análise: {br_time.strftime('%Y-%m-%d %H:%M:%S')} (Brasília)\n"
        f"📈 Último preço: {last_close}\n"
        f"🎯 Confiança: {confidence}%\n"
        f"🕒 Entrada no candle: {next_candle_time.strftime('%Y-%m-%d %H:%M:%S')} (Brasília)"
    )

    doc = {
        "signal_id": signal_id,
        "signal": signal,
        "price": last_close,
        "confidence": confidence,
        "analyze_time": br_time.strftime('%Y-%m-%d %H:%M:%S'),
        "entry_time": next_candle_time.strftime('%Y-%m-%d %H:%M:%S')
    }

    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}

    try:
        requests.post(url, data=payload)
        logger.info("✅ Mensagem enviada ao Telegram com sucesso.")
        signal_logger.info(
            f"Signal: {signal} | Price: {last_close} | Confidence: {confidence}% | Entry: {next_candle_time}"
        )
        # Salvar no MongoDB
        mongo_repo = MongoDBRepository()
        mongo_repo.insert_one(doc)
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem Telegram (ID: {signal_id}): {e}")

def analyze_signal(rsi, macd, macdsignal, macdhist, prev_macdhist, close, middleband, lowerband):
    signal = None
    confidence = 0

    # Regras de queda
    if rsi < 50 and macd < 0 and macdhist < 0:
        signal, confidence = 'FALL', confidence + 20
    if macd < macdsignal and macdhist < 0:
        signal, confidence = 'FALL', confidence + 20
    if macdhist < 0 and (macdhist - prev_macdhist) > 0:
        signal, confidence = 'RISE', confidence + 20
    if close < lowerband:
        signal, confidence = 'RISE', confidence + 30

    # Regras de alta
    if rsi > 50 and macd > 0 and macdhist > 0:
        signal, confidence = 'RISE', confidence + 20
    if macd > macdsignal and macdhist > 0:
        signal, confidence = 'RISE', confidence + 20
    if macdhist > 0 and (macdhist - prev_macdhist) < 0:
        signal, confidence = 'FALL', confidence + 20

    return signal, confidence

def process_candles():
    try:
        if len(data_candles) < 35:
            return

        df = pd.DataFrame(data_candles[-35:], columns=['epoch', 'open', 'high', 'low', 'close'])
        df['time'] = pd.to_datetime(df['epoch'], unit='s')

        rsi = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
        macd_ind = ta.trend.MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
        macd = macd_ind.macd()
        macd_signal = macd_ind.macd_signal()
        macd_hist = macd_ind.macd_diff()
        bb = ta.volatility.BollingerBands(close=df['close'], window=10, window_dev=1.5)

        last_close = df['close'].iloc[-1]
        last_rsi = rsi.iloc[-1]
        last_macd = macd.iloc[-1]
        last_macdsignal = macd_signal.iloc[-1]
        last_macdhist = macd_hist.iloc[-1]
        prev_macdhist = macd_hist.iloc[-2]
        upper = bb.bollinger_hband().iloc[-1]
        middle = bb.bollinger_mavg().iloc[-1]
        lower = bb.bollinger_lband().iloc[-1]

        band_width = (upper - lower) / middle
        if band_width < bollinger_band_threshold:
            logger.info("⚠️ Bandas de Bollinger muito estreitas. Sem operação!")
            return

        logger.info(f"📈 Análise em: {datetime.utcnow()} UTC | Close: {last_close:.2f} | RSI: {last_rsi:.2f} | MACD: {last_macd:.2f}/{last_macdsignal:.2f} | Hist: {last_macdhist:.2f}")
        signal, confidence = analyze_signal(last_rsi, last_macd, last_macdsignal, last_macdhist, prev_macdhist, last_close, middle, lower)

        if signal:
            logger.info(f"🚨 SINAL DETECTADO: {signal} | Confiança: {confidence}%")
            if confidence >= min_confidence_to_send:
                send_telegram_message(signal, last_close, confidence)
        else:
            logger.info("⚡ Nenhum sinal forte detectado. Melhor esperar!")
    except Exception as e:
        logger.error(f"⚠️ Erro no processamento dos candles: {e}")

# === CALLBACKS WEBSOCKET ===
def on_message(ws, message):
    global data_candles, last_open_time
    data = json.loads(message)

    if data.get('msg_type') == 'authorize':
        req = {
            "ticks_history": "R_25",
            "style": "candles",
            "granularity": granularity,
            "count": 50,
            "end": "latest",
            "subscribe": 1
        }
        ws.send(json.dumps(req))
        logger.info(f"✅ Token autorizado com sucesso às {datetime.utcnow()} UTC")

    elif data.get('msg_type') == 'candles':
        for c in data['candles']:
            data_candles.append([c['epoch'], float(c['open']), float(c['high']), float(c['low']), float(c['close'])])
        if len(data_candles) > max_candles:
            data_candles = data_candles[-max_candles:]
        logger.info(f"📥 Histórico inicial recebido às {datetime.utcnow()} UTC")
        process_candles()

    elif data.get('msg_type') == 'ohlc':
        candle = data['ohlc']
        current_open_time = int(candle['open_time'])
        if last_open_time is None:
            last_open_time = current_open_time
        if current_open_time != last_open_time:
            logger.info(f"🔔 Novo candle fechado às {datetime.utcfromtimestamp(candle['epoch'])} UTC")
            data_candles.append([candle['epoch'], float(candle['open']), float(candle['high']), float(candle['low']), float(candle['close'])])
            if len(data_candles) > max_candles:
                data_candles = data_candles[-max_candles:]
            process_candles()
        last_open_time = current_open_time

def on_error(ws, error):
    logger.error(f"Erro no WebSocket: {error}")

def on_close(ws):
    logger.warning("Conexão WebSocket fechada")

def on_open(ws):
    ws.send(json.dumps({"authorize": TOKEN}))

# === EXECUÇÃO PRINCIPAL ===
if __name__ == "__main__":
    logger.info("🔗 Conectando ao WebSocket...")
    ws = websocket.WebSocketApp(
        socket_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    t = threading.Thread(target=ws.run_forever)
    t.start()
    logger.info("🔗 Conexão WebSocket estabelecida. Aguardando mensagens...")
