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

from enums.enum_gale_status import GaleEnum
from models.gale_item import GaleItem
from repositories.repository_factory import RepositoryFactory
from models.signal import Signal
from models.candle import Candle
from models.gale_item import GaleItem
from enums.enum_signal_direction import SignalDirection
from enums.enum_result_status import ResultStatusEnum
from log_config import setup_logging
from indicators import calculate_bollinger_bands, calculate_rsi, calculate_macd, calculate_atr, analyze_micro_trend
from trend_analysis import analyze_ema_trend, analyze_hma_trend, calculate_signal_confidence
from bollinger_analysis import should_trade_bollinger

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
queue_validate_signal = []         # Lista de IDs de sinais aguardando validação
current_candle_state = None  # Estado do candle atual sendo atualizado

# === FUNÇÕES AUXILIARES ===
def generate_signal_id(length: int = 8) -> str:
    """Gera ID alfanumérico único."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def is_new_candle(current_open_time: int, last_open_time: int) -> bool:
    """
    Verifica se um evento OHLC representa um novo candle.
    
    Args:
        current_open_time: Timestamp de abertura do candle atual
        last_open_time: Timestamp de abertura do último candle registrado
        
    Returns:
        bool: True se for um novo candle, False caso contrário
    """
    return current_open_time != last_open_time

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
        f"🕒 Entrada no candle: {entry_time} (Brasília)"
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

def reply_result(candle: Candle):
    """
    Envia uma mensagem de resposta ao Telegram com o resultado do sinal.
    
    Args:
        signal: O sinal com o resultado a ser enviado
    """
    signal = candle.signal

    if not signal or signal.message_id is None or signal.chat_id is None or signal.result is None:
        return
    
    # Preparar texto da mensagem com base no tipo de sinal (gale ou normal) e resultado
    if candle.has_gale_items():
        latest_gale_item = candle.get_latest_gale_item()
        # Sinal de gale com ícone específico baseado no resultado
        if latest_gale_item.result == ResultStatusEnum.WIN:
            text = f"✅ Gale {latest_gale_item.gale_type.name} para o sinal {signal.signal_id}: *{latest_gale_item.result}*"
        else:   
            if latest_gale_item.gale_type == GaleEnum.G2 and latest_gale_item.result is None:
                text = f"🚨 Gale {latest_gale_item.gale_type.name} para o sinal {signal.signal_id}\n"
                text += f"💰 Preço de entrada: {latest_gale_item.open_price}\n"
                text += f"🕒 Entrada no candle: {(datetime.fromtimestamp(latest_gale_item.epoch)).strftime('%Y-%m-%d %H:%M:%S')}"
            elif latest_gale_item.gale_type == GaleEnum.G2 and latest_gale_item.result is not None:
                text = f"❌ Gale {latest_gale_item.gale_type.name} para o sinal {signal.signal_id}: *{latest_gale_item.result}*"
            elif latest_gale_item.gale_type == GaleEnum.G1:
                text = f"🚨 Gale {latest_gale_item.gale_type.name} para o sinal {signal.signal_id}\n"
                text += f"💰 Preço de entrada: {latest_gale_item.open_price}\n"
                text += f"🕒 Entrada no candle: {(datetime.fromtimestamp(latest_gale_item.epoch)).strftime('%Y-%m-%d %H:%M:%S')}"

            
    else:
        # Sinal normal
        if signal.result == ResultStatusEnum.WIN:
            text = f"✅ Resultado para o sinal {signal.signal_id}: *{signal.result}*"
        else:
            text = f"❌ Resultado para o sinal {signal.signal_id}: *{signal.result}*"

    # Enviar mensagem como resposta ao sinal original
    payload = {
        'chat_id': signal.chat_id,
        'text': text,
        'reply_to_message_id': signal.message_id,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(URL_TELEGRAM, data=payload)
        response.raise_for_status()
        logger.info(f"✅ Resposta de resultado enviada para o sinal {signal.signal_id}")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar resposta de resultado para o sinal {signal.signal_id}: {e}")
    
def persist_candle(candle: Candle) -> None:
    """
    Persiste um candle no repositório.
    
    Args:
        candle: O candle a ser persistido
    """
    repo = RepositoryFactory.get_candle_repository()
    repo.insert_one(candle)

def log_signal(signal_id: str, signal: str, price: float, confidence: int, entry_time: datetime) -> None:
    logger.info(f"✅ Mensagem enviada ao Telegram (ID: {signal_id}).")
    signal_logger.info(
        f"[{signal_id}] Signal: {signal} | Price: {price} | Confidence: {confidence}% | Entry: {entry_time}"
    )

def handle_signal(candle: Candle) -> None:
    """Orquestra geração de ID, envio, log e persistência."""
    global last_signal_time

    # Não enviar sinal antes de receber o primeiro candle OHL (last_open_time definido)
    if candle.epoch is None:
        logger.info("🔄 Ignorando sinal inicial antes de primeiro candle OHL.")
        return
    
    signal = candle.signal

    signal.entry_time = datetime.fromtimestamp(candle.epoch)

    signal.analyze_time = datetime.fromtimestamp(candle.epoch - 60)
    signal.direction = signal.direction if signal.direction else SignalDirection.INDEFINIDO

    close_price = candle.close_price if candle.close_price is not None else 0.0

    message = compose_telegram_message(
            signal.signal_id, 
            signal.direction, 
            close_price, 
            signal.confidence or 0, 
            signal.analyze_time, 
            signal.entry_time
        )

    try:
        message_id, chat_id = send_to_telegram(message)

        signal.message_id = message_id
        signal.chat_id = chat_id

        repo = RepositoryFactory.get_candle_repository()
        repo.update_signal(signal)

        queue_validate_signal.append(signal.signal_id)
        
        # Atualiza o tempo do último sinal enviado
        last_signal_time = datetime.utcnow()

        log_signal(signal.signal_id, signal.direction, close_price, signal.confidence or 0, signal.entry_time)
    except Exception as e:
        logger.error(f"Erro ao processar sinal {candle.signal.signal_id}: {e}")

# Crie uma funcao para que recebe um Candle e valide se o sinal foi win ou loss
def validate_signal(candle: Candle):
    """
    Valida o sinal de um candle e retorna o resultado (WIN ou LOSS).
    
    Args:
        candle: O candle a ser validado
    
    Returns:
        ResultStatusEnum: Resultado da validação do sinal
    """
    if not candle.signal:
        logger.warning(f"⚠️ Sinal não encontrado no candle {candle.epoch}")
        return
    
    logger.info(f"Funcao validate_signal iniciada para o signal {candle.signal.signal_id}")

    signal = candle.signal

    # Sinal com gale
    if candle.has_gale_items():
        latest_gale_item = candle.get_latest_gale_item()
        logger.info(f"Validando sinal {signal.signal_id} para gale item {latest_gale_item.gale_type.name}")

        if latest_gale_item is None or latest_gale_item.open_price is None or latest_gale_item.close_price is None:
            logger.warning(f"⚠️ latest_gale_item, open_price ou close_price é None para o candle {candle.epoch}")
            result = ResultStatusEnum.LOSS
        else:
            if signal.direction == SignalDirection.RISE:
                result = ResultStatusEnum.WIN if latest_gale_item.close_price > latest_gale_item.open_price else ResultStatusEnum.LOSS
            else:
                result = ResultStatusEnum.WIN if latest_gale_item.close_price < latest_gale_item.open_price else ResultStatusEnum.LOSS
        
        latest_gale_item.result = result
        candle.update_gale_item(latest_gale_item)
        logger.info(f"Resultado do gale item {latest_gale_item.gale_type.name} para o sinal {signal.signal_id}: {result}")
        return
    
    open_price = candle.open_price if candle.open_price is not None else 0.0
    close_price = candle.close_price if candle.close_price is not None else 0.0
    
    # Sinal normal
    if signal.direction == SignalDirection.RISE:
        result = ResultStatusEnum.WIN if close_price > open_price else ResultStatusEnum.LOSS
    else:
        result = ResultStatusEnum.WIN if close_price < open_price else ResultStatusEnum.LOSS

    signal.result = result
    candle.signal = signal

    logger.info(f"Funcao validate_signal finalizada para o signal {candle.signal.signal_id}")

def validate_signals_for_candle() -> None:
    """
    Itera pelos IDs em queue_validate_signal, busca cada sinal no MongoDB,
    avalia WIN/LOSS e atualiza o documento, removendo-o da lista.
    
    Args:
        open_price: Preço de abertura do candle
        close_price: Preço de fechamento do candle
    """
    logger.info(f"Iniciando validação de sinais pendentes. Total: {len(queue_validate_signal)}")

    if not queue_validate_signal:
        logger.info("Sem sinais pendentes para validação")
        return

    repo = RepositoryFactory.get_candle_repository()
    current_candle = data_candles[-1]

    for signal_id in queue_validate_signal:
        try:
            logger.info(f"Funcao validate_signals_for_candle iniciada para o sinal {signal_id}")
            # Busca o candle pelo signal_id
            candle_db = repo.find_by_signal_id(signal_id)
            
            if not candle_db or not candle_db.signal:
                logger.warning(f"⚠️ Sinal {signal_id} não encontrado no repositório")
                if queue_validate_signal:
                    queue_validate_signal.pop(0)
                continue
            
            validate_signal(candle_db)
            
            if candle_db.has_gale_items():
                logger.info(f"Validando sinal {signal_id} com gale items")

                latest_gale_item = candle_db.get_latest_gale_item()
                if latest_gale_item.result == ResultStatusEnum.LOSS:
                    logger.info(f"Gale {latest_gale_item.gale_type.name} para o sinal {signal_id} resultou em LOSS")

                    if latest_gale_item.gale_type == GaleEnum.G1:
                        gale_item = GaleItem(
                            gale_type=GaleEnum.G2,
                            epoch=current_candle[0],
                            open_price=current_candle[2],
                            high=current_candle[3],
                            low=current_candle[4],
                            close_price=current_candle[5],
                            time=datetime.now(),
                        )
                    
                        candle_db.add_gale_item(gale_item)
                        queue_validate_signal.append(signal_id)
                        logger.info(f"Sinal {signal_id} adicionado à fila para G2")

            else:
                logger.info(f"Validando sinal {signal_id} sem gale items")

                # Lógica de progressão de gale em caso de LOSS
                if candle_db.signal.result == ResultStatusEnum.LOSS:
                    logger.info(f"Sinal {signal_id} resultou em LOSS, iniciando gale G1")
                    gale_item = GaleItem(
                            gale_type=GaleEnum.G1,
                            epoch=current_candle[0],
                            open_price=current_candle[2],
                            high=current_candle[3],
                            low=current_candle[4],
                            close_price=current_candle[5],
                            time=datetime.now(),
                        )
                    
                    candle_db.add_gale_item(gale_item)
                    queue_validate_signal.append(signal_id)
                    logger.info(f"Sinal {signal_id} adicionado à fila (queue_validate_signal) para validacao de gale G1")
                
                candle_db.signal.result = candle_db.signal.result


            # Atualiza o candle no repositório
            if candle_db.has_gale_items():
                repo.update_one({'epoch': candle_db.epoch}, {'$set':candle_db.to_dict()})
                logger.info(f"Candle completo com gales atualizado para {signal_id}")
            else:
                repo.update_signal(candle_db.signal)
                logger.info(f"Sinal atualizado no repositório para {signal_id}")

            # Envia resultado para o Telegram
            reply_result(candle_db)

            if queue_validate_signal:
                queue_validate_signal.pop(0)

            logger.info(f"Funcao validate_signals_for_candle finalizada com sucesso para o sinal {signal_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao validar sinal {signal_id}: {e}")
            import traceback
            logger.error(f"Detalhes do erro: {traceback.format_exc()}")
    
    logger.info(f"Validação concluída. Sinais pendentes restantes: {len(queue_validate_signal)}")

def process_candles() -> None:
    """
    Processa candles, calcula indicadores e gera sinais.
    Esta função é chamada quando um novo candle é recebido e não há cooldown ativo.
    """
    global data_candles, last_open_time
    
    # Verifica se há dados suficientes para análise
    if len(data_candles) < max_candles:
        logger.info(f"📊 Dados insuficientes para processar. Necessário: {max_candles}, Disponível: {len(data_candles)}")
        return
    
    try:
        logger.info(f"📊 Iniciando processamento de {len(data_candles)} candles")
        
        # Normalizar os dados para garantir consistência
        normalized_data = []
        for candle in data_candles[-max_candles:]:
            if len(candle) == 5:  # Formato antigo: (epoch, open, high, low, close)
                normalized_data.append({
                    'epoch': candle[0],
                    'open_time': candle[0],  # Usar epoch como open_time se não estiver disponível
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4]
                })
            elif len(candle) == 6:  # Formato novo: (epoch, open_time, open, high, low, close)
                normalized_data.append({
                    'epoch': candle[0],
                    'open_time': candle[1],
                    'open': candle[2],
                    'high': candle[3],
                    'low': candle[4],
                    'close': candle[5]
                })
            else:
                logger.warning(f"⚠️ Formato de candle inesperado ignorado: {candle}")
                continue

        # Criar o DataFrame a partir dos dados
        df = pd.DataFrame(normalized_data)
        
        # Renomear as colunas após criar o DataFrame
        if len(df.columns) == 6:
            df.columns = ['epoch', 'open_time', 'open', 'high', 'low', 'close']
        else:
            logger.error(f"❌ DataFrame com número incorreto de colunas: {len(df.columns)}. Esperado: 5")
            return
            
        # Converter para tipos numéricos
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # Verificar se há valores NaN após a conversão
        # Verificar porque os valores NaN estão aparecendo
        nan_counts = df.isna().sum()
        if nan_counts.sum() > 0:
            logger.warning(f"⚠️ Valores NaN detectados no DataFrame após conversão: {nan_counts}")
            
        df['time'] = pd.to_datetime(df['epoch'], unit='s')

        # Calcular Bollinger Bands
        upper, middle, lower = calculate_bollinger_bands(df, window=10, window_dev=1.5)
        if upper is None or middle is None or lower is None:
            logger.error("Falha ao calcular Bollinger Bands")
            return

        # Nova análise de Bollinger Bands
        should_trade, bb_trend, bb_strength = should_trade_bollinger(df, upper, middle, lower)
        if not should_trade:
            logger.info("⚠️ Condições das Bandas de Bollinger não favoráveis para operação.")
            return

        # Apenas para teste
        # bb_trend, bb_strength = None, None

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

        # Análise de micro tendência dos candles
        micro_trend_analysis = analyze_micro_trend(df, period=5, trend_strength_threshold=0.6)
        micro_trend = micro_trend_analysis['trend']
        micro_strength = micro_trend_analysis['strength']
        micro_confidence = micro_trend_analysis['confidence']
        micro_pattern = micro_trend_analysis['pattern']
        micro_momentum = micro_trend_analysis['momentum']

        # Análise de tendência via EMA
        trend_ema, ema9, ema21 = analyze_ema_trend(df, fast_period=9, slow_period=21)

        # Calcular confiança do sinal com base na tendência EMA e força do BB
        confidence = calculate_signal_confidence(
            trend_ema, rsi, macd, macd_signal, body, atr, last['close'], upper, lower
        )

        signal = Signal()

        candle_repo = RepositoryFactory.get_candle_repository()
        candle = candle_repo.find_by_epoch(int(last['epoch']))

        if candle is None:
            candle = Candle()
        
        # Adicionar bônus de confiança se BB concordar com EMA
        # Apenas para teste
        if bb_trend == trend_ema:
            confidence += int(bb_strength * 20)  # Adiciona até 20 pontos extras baseado na força do BB

        # Aplicar bônus adicional se micro tendência concordar com EMA
        if micro_trend == trend_ema:
            micro_bonus = int(micro_strength * micro_confidence * 15)  # Até 15 pontos extras
            confidence += micro_bonus
            logger.info(f"🎯 Micro tendência concorda com EMA. Bônus aplicado: +{micro_bonus} pontos")

        # Verificar se temos dados suficientes para HMA e se a confiança é alta o suficiente
        if len(df) >= 100 and confidence >= min_confidence_to_send:
            # Usar HMA para confirmar ou reverter a tendência
            trend_hma = analyze_hma_trend(df)
            
            # Agora requeremos concordância entre BB, EMA, HMA e Micro Tendência
            micro_trend_ema_match = micro_trend == trend_ema
            # all_trends_agree = (trend_hma == trend_ema == bb_trend and micro_trend_ema_match)
            all_trends_agree = (True)
            
            if all_trends_agree:
                epoch = int(last['epoch']) + 60
                # Atribuir valores ao sinal
                signal.direction = SignalDirection.RISE if trend_hma == 'RISE' else SignalDirection.FALL
                signal.confidence = confidence
                signal.analyze_time = datetime.utcnow()
                signal.open_candle_timestamp = epoch
                signal.message_id = None
                signal.chat_id = None
                signal.result = None
                signal.signal_id = generate_signal_id()
                signal.entry_time = None
                

                # Atribuir valores ao candle
                candle.epoch = epoch
                candle.open_price = last['open']
                candle.high = last['high']
                candle.low = last['low']
                candle.close_price = last['close']
                candle.signal = signal
                candle.time = last['time']

                logger.info(f"✅ Todas as tendências concordam: HMA={trend_hma}, EMA={trend_ema}, BB={bb_trend}, Micro={micro_trend}")
            else:
                logger.info(f"⚠️ Divergência entre indicadores - HMA:{trend_hma}, EMA:{trend_ema}, BB:{bb_trend}, Micro:{micro_trend}")
        else:
            logger.info(f"⚠️ Sem dados suficientes para HMA ou confiança baixa. Dados HMA: {len(df)>=100}, Confiança: {confidence}")

        
        
        logger.info(
            f"📈 Análise: EMA9={ema9:.2f}, EMA21={ema21:.2f}, trend_ema={trend_ema}, " +
            f"micro_trend={micro_trend}(força:{micro_strength:.2f}, conf:{micro_confidence:.2f}, padrão:{micro_pattern}), " +
            f"trend_final={signal.direction if signal is not None else 'Tendencia nao definida'}, " +
            f"RSI={rsi:.2f}, MACD={macd:.2f}/{macd_signal:.2f}, ATR={atr:.2f}, " +
            f"body={body:.2f}, confidence={confidence}"
        )

        if signal.direction:
            logger.info(f"🚨 SINAL DETECTADO: {signal.direction} | Confiança: {confidence}%")
            
            # Persistir o candle sem o sinal associado
            persist_candle(candle)
            
            # Enviar o sinal
            handle_signal(candle)
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
    logger.info(f"📥 Histórico inicial recebido às {datetime.utcnow()} UTC. Total de candles: {len(data_candles)}")
    # process_candles()


def handle_ohlc(data: dict) -> None:
    global data_candles, last_open_time, last_signal_time
    candle = data['ohlc']
    current_open_time = int(candle['open_time'])
    open_price, close_price = float(candle['open']), float(candle['close'])

    # Adiciona novo candle aos dados
    data_candles.append((
            candle['epoch'], 
            candle['open_time'],
            float(candle['open']), 
            float(candle['high']),
            float(candle['low']), 
            float(candle['close'])
        ))

    # Mantém apenas os últimos max_candles
    if len(data_candles) > max_candles:
        data_candles = data_candles[-max_candles:]

    # Inicializa last_open_time se for o primeiro candle
    if last_open_time is None:
        last_open_time = current_open_time
        logger.info(f"🔔 Primeiro candle recebido em {datetime.utcfromtimestamp(candle['epoch'])} UTC")
    

    if is_new_candle(current_open_time, last_open_time):
        logger.info(f"🔔 Novo candle detectado em {datetime.utcfromtimestamp(candle['epoch'])} UTC")

        if queue_validate_signal:
            repo = RepositoryFactory.get_candle_repository()
            candle_db = repo.find_by_signal_id(queue_validate_signal[0])
            if candle_db:

                if candle_db.signal is not None:
                    entry_time = candle_db.signal.entry_time
                    if entry_time is not None:
                        current_open_time_dt = datetime.utcfromtimestamp(current_open_time)
                        if entry_time.replace(second=0, microsecond=0) >= datetime.now().replace(second=0, microsecond=0):
                            logger.info(f"🔔 Candle {candle['epoch']} é menor ou igual ao entry_time {entry_time}")
                            last_open_time = current_open_time
                            return
                        else:
                            logger.info(f"🔔 Candle {candle['epoch']} é maior que o entry_time {entry_time}")
                            save_previous_candle_on_transition(candle_db)
                            validate_signals_for_candle()
                    else:
                        logger.info(f"🔔 Candle {candle['epoch']} não tem entry_time")
                else:
                    logger.info(f"🔔 Candle {candle['epoch']} não tem signal")

            else:
                logger.warning(f"⚠️ Não foi possível encontrar o candle com signal_id={queue_validate_signal[0]}")
        else:
            # Verifica se está em período de cooldown para novos sinais
            now = datetime.utcnow()
            in_cooldown = last_signal_time and (now - last_signal_time).total_seconds() < signal_cooldown
            
            if in_cooldown and last_signal_time is not None:
                wait = signal_cooldown - int((now - last_signal_time).total_seconds())
                logger.info(f"⏳ Em cooldown ({signal_cooldown}s). Próximo sinal em {wait}s.")
            else:
                process_candles()   
    
    # Atualiza o timestamp do último candle processado
    last_open_time = current_open_time

def schedule_signal_validation(prev_open, prev_close):
    """
    Agenda a validação de sinais pendentes após um tempo determinado.
    
    Args:
        prev_open: Preço de abertura do candle anterior
        prev_close: Preço de fechamento do candle anterior
    """
    # Verifica se há sinais pendentes para validação
    if queue_validate_signal and len(queue_validate_signal) > 0:
        # Cria um timer para validar os sinais após o cooldown
        timer = threading.Timer(
            validate_signal_cooldown,
            lambda: validate_signals_for_candle(prev_open, prev_close)
        )
        
        # Inicia o timer como daemon para não bloquear o encerramento do programa
        timer.daemon = True
        timer.start()
        
        timestamp = datetime.utcnow() + timedelta(seconds=validate_signal_cooldown)
        formatted_time = timestamp.strftime('%H:%M:%S')
        logger.info(f"⏳ Validação de {len(queue_validate_signal)} sinais agendada para {formatted_time} UTC (em {validate_signal_cooldown}s)")
    else:
        logger.info("📝 Sem sinais pendentes para agendar validação")

def save_previous_candle_on_transition(candle_db: Candle) -> bool:
    """
    Verifica se houve uma transição de candle e, se sim, salva o candle anterior no banco de dados.
    
    Args:
        current_open_time: Timestamp de abertura do candle atual
        last_open_time: Timestamp de abertura do candle anterior
        
    Returns:
        bool: True se um candle foi salvo, False caso contrário
    """
    global data_candles
    
    logger.info(f"Funcao save_previous_candle_on_transition iniciada.")

    try:
        if not candle_db:
            logger.warning(f"⚠️ Não foi possível encontrar o candle com signal_id={queue_validate_signal[0]}")
            return False

        last_open_time = candle_db.epoch
        if candle_db.has_gale_items():
            latest_gale_item = candle_db.get_latest_gale_item()
            last_open_time = latest_gale_item.epoch
        else:
            last_open_time = candle_db.epoch + 60
              

        # Encontra o candle anterior baseado no last_open_time
        previous_candles = [c for c in data_candles if c[1] == last_open_time]
        
        if not previous_candles:
            logger.warning(f"⚠️ Não foi possível encontrar o candle anterior com open_time={last_open_time}")
            return False
            
        # Pega o último estado do candle anterior (último na lista com mesmo timestamp)
        prev_candle_data = previous_candles[-1]

        logger.info(f"🔄 Candle {last_open_time} já existe no banco, atualizando...")
        
        # Se tiver gale_items, atualiza o último
        if candle_db.has_gale_items():
            latest_gale_item = candle_db.get_latest_gale_item()
            if latest_gale_item:
                # Atualiza o último gale item
                logger.info(f"🔄 Atualizando último gale item do candle {last_open_time}")
                latest_gale_item.open_price = float(prev_candle_data[2])
                latest_gale_item.high = float(prev_candle_data[3])
                latest_gale_item.low = float(prev_candle_data[4])
                latest_gale_item.close_price = float(prev_candle_data[5])
                candle_db.update_gale_item(latest_gale_item)
        else:
            logger.info(f"🔄 Candle {last_open_time} não tem gale_items")
            # Atualiza os valores do candle
            candle_db.open_price = float(prev_candle_data[2])
            candle_db.high = float(prev_candle_data[3])
            candle_db.low = float(prev_candle_data[4])
            candle_db.close_price = float(prev_candle_data[5])
        
        # Atualiza o candle no banco de dados usando o to_dict()
        repo = RepositoryFactory.get_candle_repository()
        repo.update_one({'epoch': candle_db.epoch}, {'$set': candle_db.to_dict()})
        logger.info(f"✅ Candle {candle_db.epoch} atualizado com sucesso")
    
        logger.info(f"Funcao save_previous_candle_on_transition concluída com sucesso.")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar candle anterior: {e}")
        import traceback
        logger.error(f"Detalhes do erro: {traceback.format_exc()}")
        return False

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
    try:
        logger.info("🚀 Iniciando aplicação Deriv Signal...")
        logger.info(f"🔧 Configurações: MAX_CANDLES={max_candles}, GRANULARITY={granularity}s")
        logger.info(f"⏱️ Cooldowns: SIGNAL={signal_cooldown}s, VALIDATE={validate_signal_cooldown}s")
        logger.info(f"🎯 Confiança mínima: {min_confidence_to_send}%")
        
        # Inicializa a conexão WebSocket
        logger.info("🔗 Conectando ao WebSocket Deriv...")
        ws = websocket.WebSocketApp(
            socket_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        # Cria e inicia a thread do WebSocket como daemon
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        logger.info("✅ Aplicação iniciada com sucesso! Pressione Ctrl+C para encerrar.")
        
        # Mantém o programa rodando até que seja interrompido
        while True:
            ws_thread.join(1)  # Espera 1 segundo e verifica se a thread ainda está ativa
            if not ws_thread.is_alive():
                logger.error("❌ Conexão WebSocket perdida. Tentando reconectar...")
                ws_thread = threading.Thread(target=ws.run_forever)
                ws_thread.daemon = True
                ws_thread.start()
            
    except KeyboardInterrupt:
        logger.info("👋 Encerrando aplicação por solicitação do usuário.")
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}")
        import traceback
        logger.error(f"Detalhes do erro: {traceback.format_exc()}")
    finally:
        logger.info("🔚 Aplicação encerrada.")

def check_candle_data_consistency() -> bool:
    """
    Verifica a consistência dos dados de candles armazenados.
    
    Returns:
        bool: True se os dados são consistentes, False caso contrário
    """
    if not data_candles or len(data_candles) < 2:
        logger.warning("⚠️ Dados insuficientes para verificar consistência")
        return False
    
    # Verifica a estrutura dos candles
    for idx, candle in enumerate(data_candles):
        if len(candle) != 5:
            logger.error(f"❌ Candle {idx} com estrutura inválida: {candle}")
            return False
    
    # Verifica se os timestamps estão em ordem crescente
    prev_time = data_candles[0][0]
    for idx, candle in enumerate(data_candles[1:], 1):
        curr_time = candle[0]
        if curr_time < prev_time:
            logger.error(f"❌ Timestamp fora de ordem: candle {idx-1}:{prev_time} > candle {idx}:{curr_time}")
            return False
        prev_time = curr_time
    
    # Verifica se há valores nulos ou inválidos
    for idx, candle in enumerate(data_candles):
        for i, val in enumerate(candle):
            if val is None or (isinstance(val, (int, float)) and (val == 0 or pd.isna(val))):
                field = ["timestamp", "open", "high", "low", "close"][i]
                logger.error(f"❌ Valor inválido no candle {idx}, campo {field}: {val}")
                return False
    
    # Verifica se os high/low são consistentes com open/close
    for idx, candle in enumerate(data_candles):
        open_price, high, low, close = candle[1], candle[2], candle[3], candle[4]
        if high < open_price or high < close:
            logger.error(f"❌ High inválido no candle {idx}: high={high}, open={open_price}, close={close}")
            return False
        if low > open_price or low > close:
            logger.error(f"❌ Low inválido no candle {idx}: low={low}, open={open_price}, close={close}")
            return False
    
    logger.info("✅ Dados de candles verificados e consistentes")
    return True

# === FUNÇÕES DE GERENCIAMENTO DE CANDLES ===
def save_current_candle_update(ohlc_data: dict) -> None:
    """
    Salva as atualizações do candle atual (mesmo open_time).
    
    Args:
        ohlc_data: Dados OHLC recebidos da API da Deriv
    """
    global current_candle_state
    
    try:
        # Extrai os dados do evento OHLC
        epoch = ohlc_data['epoch']
        open_time = int(ohlc_data['open_time'])
        open_price = float(ohlc_data['open'])
        high = float(ohlc_data['high'])
        low = float(ohlc_data['low'])
        close = float(ohlc_data['close'])
        
        # Atualiza o estado do candle atual
        current_candle_state = {
            'epoch': epoch,
            'open_time': open_time,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'time': datetime.utcfromtimestamp(epoch)
        }
        
        logger.debug(f"📊 Candle atual atualizado: open_time={open_time}, "
                    f"OHLC=({open_price:.3f}, {high:.3f}, {low:.3f}, {close:.3f})")
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar atualização do candle atual: {e}")

def detect_and_create_new_candle(ohlc_data: dict, previous_open_time: int) -> Candle:
    """
    Detecta um novo candle e cria uma instância da classe Candle com os dados.
    
    Args:
        ohlc_data: Dados OHLC recebidos da API da Deriv
        previous_open_time: Timestamp do open_time anterior
        
    Returns:
        Candle: Nova instância da classe Candle ou None se não for um novo candle
    """
    try:
        # Extrai os dados do evento OHLC
        epoch = ohlc_data['epoch']
        current_open_time = int(ohlc_data['open_time'])
        open_price = float(ohlc_data['open'])
        high = float(ohlc_data['high'])
        low = float(ohlc_data['low'])
        close = float(ohlc_data['close'])
        
        # Verifica se é realmente um novo candle
        if current_open_time == previous_open_time:
            return None
            
        # Cria uma nova instância da classe Candle
        new_candle = Candle(
            epoch=epoch,
            open_price=open_price,
            high=high,
            low=low,
            close_price=close,
            time=datetime.utcfromtimestamp(epoch)
        )
        
        logger.info(f"🆕 Novo candle criado: open_time={current_open_time}, "
                   f"OHLC=({open_price:.3f}, {high:.3f}, {low:.3f}, {close:.3f})")
        
        # Valida a consistência do novo candle
        if validate_new_candle_data(new_candle, current_candle_state):
            return new_candle
        else:
            logger.warning(f"⚠️ Novo candle com dados inconsistentes, ignorando")
            return None
            
    except Exception as e:
        logger.error(f"❌ Erro ao detectar/criar novo candle: {e}")
        return None

def validate_new_candle_data(new_candle: Candle, previous_state: dict) -> bool:
    """
    Valida a consistência dos dados do novo candle.
    
    Args:
        new_candle: Nova instância do candle
        previous_state: Estado do candle anterior
        
    Returns:
        bool: True se os dados são válidos, False caso contrário
    """
    try:
        # Verifica se os valores OHLC são válidos
        if (new_candle.open_price <= 0 or new_candle.high <= 0 or 
            new_candle.low <= 0 or new_candle.close_price <= 0):
            logger.error(f"❌ Candle com preços inválidos: {new_candle}")
            return False
        
        # Verifica se high >= max(open, close) e low <= min(open, close)
        max_oc = max(new_candle.open_price, new_candle.close_price)
        min_oc = min(new_candle.open_price, new_candle.close_price)
        
        if new_candle.high < max_oc:
            logger.error(f"❌ High ({new_candle.high}) menor que max(open, close) ({max_oc})")
            return False
            
        if new_candle.low > min_oc:
            logger.error(f"❌ Low ({new_candle.low}) maior que min(open, close) ({min_oc})")
            return False
        
        # Verifica continuidade com o candle anterior (se existir)
        if previous_state and 'close' in previous_state:
            # O open do novo candle deve ser próximo ao close do anterior
            price_diff = abs(new_candle.open_price - previous_state['close'])
            max_gap = previous_state['close'] * 0.01  # 1% de tolerância
            
            if price_diff > max_gap:
                logger.warning(f"⚠️ Gap significativo entre candles: "
                             f"close anterior={previous_state['close']:.3f}, "
                             f"open atual={new_candle.open_price:.3f}, "
                             f"diferença={price_diff:.3f}")
        
        logger.debug(f"✅ Candle validado com sucesso: {new_candle}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na validação do candle: {e}")
        return False

def get_finalized_candle_from_state() -> tuple:
    """
    Retorna o candle finalizado baseado no estado atual salvo.
    
    Returns:
        tuple: Tupla no formato (epoch, open, high, low, close) ou None
    """
    global current_candle_state
    
    if not current_candle_state:
        return None
    
    try:
        return (
            current_candle_state['epoch'],
            current_candle_state['open'],
            current_candle_state['high'],
            current_candle_state['low'],
            current_candle_state['close']
        )
    except Exception as e:
        logger.error(f"❌ Erro ao obter candle finalizado: {e}")
        return None

def analyze_deriv_api_pattern(ohlc_data: dict, last_open_time: int = None) -> dict:
    """
    Analisa o padrão dos dados recebidos da API da Deriv para identificar o tipo de evento.
    
    Args:
        ohlc_data: Dados OHLC recebidos da API
        last_open_time: Último open_time registrado
        
    Returns:
        dict: Análise do evento contendo:
            - event_type: 'new_candle' ou 'candle_update'
            - is_valid: Se os dados são válidos
            - transition_info: Informações sobre a transição (se novo candle)
    """
    try:
        current_open_time = int(ohlc_data['open_time'])
        current_epoch = ohlc_data['epoch']
        
        # Determina o tipo de evento
        if last_open_time is None:
            event_type = 'first_candle'
        elif current_open_time != last_open_time:
            event_type = 'new_candle'
        else:
            event_type = 'candle_update'
        
        # Análise de validade dos dados
        open_price = float(ohlc_data['open'])
        high = float(ohlc_data['high'])
        low = float(ohlc_data['low'])
        close = float(ohlc_data['close'])
        
        # Verifica a validade básica dos dados OHLC
        is_valid = (
            open_price > 0 and high > 0 and low > 0 and close > 0 and
            high >= max(open_price, close) and
            low <= min(open_price, close) and
            high >= low
        )
        
        # Informações sobre transição (para novos candles)
        transition_info = {}
        if event_type == 'new_candle' and current_candle_state:
            transition_info = {
                'previous_close': current_candle_state.get('close'),
                'current_open': open_price,
                'gap': abs(open_price - current_candle_state.get('close', 0)),
                'gap_percentage': abs(open_price - current_candle_state.get('close', 0)) / current_candle_state.get('close', 1) * 100
            }
        
        analysis = {
            'event_type': event_type,
            'is_valid': is_valid,
            'open_time': current_open_time,
            'epoch': current_epoch,
            'ohlc': {
                'open': open_price,
                'high': high,
                'low': low,
                'close': close
            },
            'transition_info': transition_info,
            'timestamp_human': datetime.utcfromtimestamp(current_epoch).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        logger.debug(f"📊 Análise da API: {event_type} - "
                    f"open_time={current_open_time}, "
                    f"valid={is_valid}, "
                    f"OHLC=({open_price:.3f}, {high:.3f}, {low:.3f}, {close:.3f})")
        
        return analysis
        
    except Exception as e:
        logger.error(f"❌ Erro na análise do padrão da API: {e}")
        return {
            'event_type': 'error',
            'is_valid': False,
            'error': str(e)
        }
