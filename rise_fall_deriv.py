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

from app.enums.enum_gale_status import GaleEnum
from app.models.gale_item import GaleItem
from app.repositories.repository_factory import RepositoryFactory
from app.models.signal import Signal
from app.models.candle import Candle
from app.models.gale_item import GaleItem
from app.enums.enum_signal_direction import SignalDirection
from app.enums.enum_result_status import ResultStatusEnum
from app.log_config import setup_logging

# === SISTEMA DINÂMICO DE INDICADORES ===
from app.indicator_system import IndicatorFactory, ConsensusAnalyzer, IndicatorResult
from app.config.indicators import get_consensus_config

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
    FASE 3 - SISTEMA DINÂMICO EM PRODUÇÃO
    
    Processa candles usando exclusivamente o sistema dinâmico de indicadores.
    
    Fluxo Otimizado:
    1. Validação e preparação eficiente dos dados
    2. Análise usando sistema dinâmico de indicadores
    3. Verificação automática de consenso com validações de segurança
    4. Cálculo distribuído de confiança
    5. Geração e envio de sinal se critérios atendidos
    
    Performance Target: < 100ms para análise completa
    """
    global data_candles, last_open_time
    
    # Marcar início para medição de performance
    process_start_time = datetime.utcnow()
    
    # Validações iniciais rápidas
    if len(data_candles) < max_candles:
        logger.info(f"📊 Dados insuficientes: {len(data_candles)}/{max_candles} candles")
        return
    
    try:
        logger.info(f"� [FASE 3] Processando {len(data_candles)} candles com sistema dinâmico")
        
        # ==================== PREPARAÇÃO DOS DADOS ====================
        
        logger.debug(f"📊 Preparando dados de {len(data_candles)} candles para análise")
        
        # Usar apenas os últimos max_candles necessários para eficiência
        recent_candles = data_candles[-max_candles:]
        
        # Normalizar os dados para garantir consistência
        normalized_data = []
        for i, candle in enumerate(recent_candles):
            try:
                if len(candle) == 5:  # Formato antigo: (epoch, open, high, low, close)
                    normalized_data.append({
                        'epoch': candle[0],
                        'open_time': candle[0],  # Usar epoch como open_time se não estiver disponível
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4])
                    })
                elif len(candle) == 6:  # Formato novo: (epoch, open_time, open, high, low, close)
                    normalized_data.append({
                        'epoch': candle[0],
                        'open_time': candle[1],
                        'open': float(candle[2]),
                        'high': float(candle[3]),
                        'low': float(candle[4]),
                        'close': float(candle[5])
                    })
                else:
                    logger.warning(f"⚠️ Formato de candle inesperado no índice {i}: {candle}")
                    continue
            except (ValueError, TypeError, IndexError) as e:
                logger.warning(f"⚠️ Erro ao normalizar candle {i}: {e}")
                continue

        if len(normalized_data) < max_candles:
            logger.warning(f"⚠️ Dados normalizados insuficientes: {len(normalized_data)}/{max_candles}")
            return

        # Criar DataFrame otimizado
        df = pd.DataFrame(normalized_data)
        
        # Verificar se DataFrame foi criado corretamente
        if df.empty or len(df.columns) != 6:
            logger.error(f"❌ DataFrame inválido: vazio={df.empty}, colunas={len(df.columns) if not df.empty else 0}")
            return
            
        # Definir nomes das colunas
        df.columns = ['epoch', 'open_time', 'open', 'high', 'low', 'close']
        
        # Verificar tipos de dados e valores NaN
        numeric_cols = ['open', 'high', 'low', 'close']
        nan_counts = df[numeric_cols].isna().sum()
        if nan_counts.sum() > 0:
            logger.warning(f"⚠️ Valores NaN detectados: {nan_counts.to_dict()}")
            # Preencher NaN com valores válidos (forward fill)
            df[numeric_cols] = df[numeric_cols].fillna(method='ffill')
            
        # Adicionar coluna de tempo para referência
        df['time'] = pd.to_datetime(df['epoch'], unit='s')
        last = df.iloc[-1]
        
        logger.debug(f"✅ DataFrame preparado: {len(df)} registros, último candle: {last['time']}")

        # ==================== SISTEMA DINÂMICO DE INDICADORES ====================
        
        logger.info("🔄 Iniciando análise com sistema dinâmico de indicadores...")
        
        try:
            # Inicializar sistema dinâmico (apenas uma vez por execução)
            factory = IndicatorFactory()
            consensus_analyzer = ConsensusAnalyzer()
            
            # Medir tempo de processamento
            start_time = datetime.utcnow()
            
            # Calcular todos os indicadores usando o sistema dinâmico
            indicator_results = factory.calculate_all_indicators(df)
            
            # Verificar se obtivemos resultados
            if not indicator_results:
                logger.warning("⚠️ Sistema dinâmico não retornou resultados")
                return
            
            # Log dos resultados individuais
            valid_count = sum(1 for r in indicator_results if r.is_valid_for_consensus())
            logger.info(f"📊 Indicadores processados: {len(indicator_results)} total, {valid_count} válidos para consenso")
            
            for result in indicator_results:
                status_icon = "✅" if result.is_valid_for_consensus() else "⚠️"
                logger.info(f"   {status_icon} {result.name}: {result.trend} "
                           f"(força: {result.strength:.3f}, confiança: {result.confidence:.3f})")
            
            # Analisar consenso
            consensus_result = consensus_analyzer.analyze_consensus(indicator_results)
            
            # ==================== CÁLCULO DE CONFIANÇA PONDERADA ====================
            
            # Se há consenso, calcular confiança baseada em força e pesos dos indicadores
            final_confidence = consensus_result.confidence  # Valor padrão (porcentagem simples)
            
            if consensus_result.has_consensus and consensus_result.trend:
                try:
                    # Filtrar indicadores que concordam com o consenso
                    agreeing_indicators = [
                        r for r in indicator_results 
                        if r.trend == consensus_result.trend and r.is_valid_for_consensus()
                    ]
                    
                    if agreeing_indicators:
                        # Calcular confiança baseada na força média dos indicadores concordantes
                        total_strength = sum(r.strength for r in agreeing_indicators)
                        total_confidence = sum(r.confidence for r in agreeing_indicators)
                        total_weight = sum(r.weight for r in agreeing_indicators)
                        
                        # CONVERSÃO: confianças vêm como decimais (0.0-1.0), converter para percentual
                        confidence_percentages = [r.confidence * 100 for r in agreeing_indicators]
                        
                        # Confiança base: média ponderada das confianças individuais
                        if total_weight > 0:
                            weighted_confidence = sum(r.confidence * 100 * r.weight for r in agreeing_indicators) / total_weight
                        else:
                            weighted_confidence = sum(confidence_percentages) / len(agreeing_indicators)
                        
                        # Bônus por força: média das forças * 30 (força já está em 0.0-1.0)
                        strength_bonus = (total_strength / len(agreeing_indicators)) * 30
                        
                        # Bônus por consenso: +10% por cada indicador adicional além do mínimo
                        min_required = 2
                        consensus_bonus = max(0, (len(agreeing_indicators) - min_required) * 10)
                        
                        # Confiança final
                        final_confidence = min(100, weighted_confidence + strength_bonus + consensus_bonus)
                        
                        logger.info(f"🧮 Cálculo de Confiança Ponderada:")
                        logger.info(f"   📊 Indicadores concordantes: {len(agreeing_indicators)}")
                        logger.info(f"   🔍 Confianças originais: {[f'{r.confidence:.3f}' for r in agreeing_indicators]}")
                        logger.info(f"   📈 Confianças convertidas: {[f'{c:.1f}%' for c in confidence_percentages]}")
                        logger.info(f"   ⚖️ Confiança ponderada: {weighted_confidence:.1f}%")
                        logger.info(f"   💪 Bônus força: +{strength_bonus:.1f}%")
                        logger.info(f"   🤝 Bônus consenso: +{consensus_bonus:.1f}%")
                        logger.info(f"   🎯 Confiança final: {final_confidence:.1f}%")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Erro no cálculo de confiança ponderada: {e}")
                    final_confidence = consensus_result.confidence  # Fallback para valor simples
            
            # Medir tempo total de processamento
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(f"🤖 Sistema Dinâmico - Resultado em {processing_time:.1f}ms:")
            logger.info(f"   📈 Consenso: {consensus_result.trend}")
            logger.info(f"   🔢 Indicadores: {consensus_result.agreeing_count}/{consensus_result.total_count}")
            logger.info(f"   🎯 Confiança: {final_confidence:.1f}%")
            logger.info(f"   🗳️ Votação: {consensus_result.vote_breakdown}")
            
        except Exception as e:
            logger.error(f"❌ Erro no sistema dinâmico de indicadores: {e}")
            import traceback
            logger.error(f"Detalhes: {traceback.format_exc()}")
            return
        
        # ==================== VALIDAÇÃO E GERAÇÃO DE SINAL ====================
        
        # Verificar critérios para geração de sinal
        if consensus_result.trend is None:
            logger.info("⚠️ Sem consenso entre indicadores - sinal não gerado")
            return
            
        if final_confidence < min_confidence_to_send:
            logger.info(f"⚠️ Confiança insuficiente: {final_confidence:.1f}% < {min_confidence_to_send}% - sinal não gerado")
            return
        
        # Validações adicionais de segurança
        if consensus_result.agreeing_count < 2:
            logger.info(f"⚠️ Poucos indicadores concordantes: {consensus_result.agreeing_count} - sinal não gerado")
            return
        
        logger.info("🎯 Critérios atendidos - gerando sinal...")
        
        # Criar sinal com dados otimizados
        signal = Signal()
        signal.signal_id = generate_signal_id()
        signal.direction = SignalDirection.RISE if consensus_result.trend == 'RISE' else SignalDirection.FALL
        signal.confidence = int(final_confidence)
        signal.analyze_time = datetime.utcnow()
        
        # Época para o próximo candle (entrada)
        next_epoch = int(last['epoch']) + 60
        signal.open_candle_timestamp = next_epoch
        signal.entry_time = None  # Será definido no handle_signal
        
        # Inicializar campos de resposta
        signal.message_id = None
        signal.chat_id = None
        signal.result = None
        
        # Buscar ou criar candle
        candle_repo = RepositoryFactory.get_candle_repository()
        candle = candle_repo.find_by_epoch(next_epoch)
        
        if candle is None:
            candle = Candle()
            candle.epoch = next_epoch
            
        # Configurar candle com dados do último candle analisado
        candle.open_price = last['open']
        candle.high = last['high']
        candle.low = last['low']
        candle.close_price = last['close']
        candle.signal = signal
        candle.time = last['time']

        # Log detalhado da análise final
        indicator_summary = [f"{result.name}={result.trend}" for result in indicator_results]
        logger.info("=" * 60)
        logger.info("📈 ANÁLISE FINAL DO SISTEMA DINÂMICO:")
        logger.info(f"   🎯 Consenso: {consensus_result.trend}")
        logger.info(f"   🔢 Concordância: {consensus_result.agreeing_count}/{consensus_result.total_count} indicadores")
        logger.info(f"   💯 Confiança: {final_confidence:.1f}%")
        logger.info(f"   📊 Indicadores: {', '.join(indicator_summary)}")
        logger.info(f"   📅 Próximo candle: {datetime.fromtimestamp(next_epoch).strftime('%H:%M:%S')}")
        logger.info("=" * 60)

        logger.info(f"🚨 SINAL DETECTADO: {signal.direction} | ID: {signal.signal_id} | Confiança: {final_confidence:.1f}%")
        
        # Persistir e enviar sinal
        try:
            persist_candle(candle)
            handle_signal(candle)
            
            # Métricas finais de performance
            total_processing_time = (datetime.utcnow() - process_start_time).total_seconds() * 1000
            logger.info(f"✅ Sinal {signal.signal_id} processado em {total_processing_time:.1f}ms")
            
            # Validar target de performance (< 100ms)
            if total_processing_time > 100:
                logger.warning(f"⚠️ Performance abaixo do target: {total_processing_time:.1f}ms > 100ms")
            else:
                logger.info(f"🎯 Performance dentro do target: {total_processing_time:.1f}ms")
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar sinal {signal.signal_id}: {e}")
            raise

    except Exception as e:
        # Métricas de erro
        error_processing_time = (datetime.utcnow() - process_start_time).total_seconds() * 1000
        logger.error(f"⚠️ Erro no processamento após {error_processing_time:.1f}ms: {e}")
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
        logger.info("🤖 Sistema: DINÂMICO (Fase 3 - Produção)")
        
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
