from datetime import datetime
from typing import Optional, Union
from enums.enum_signal_direction import SignalDirection 
from enums.enum_result_status import ResultStatusEnum

class Signal:
    """
    Representa um sinal de trading gerado pelo sistema.
    """
    
    def __init__(self, 
                 signal_id: Optional[str] = None,
                 direction: Optional[SignalDirection] = None,   
                 confidence: Optional[int] = None,
                 analyze_time: Optional[datetime] = None,
                 entry_time: Optional[datetime] = None,
                 open_candle_timestamp: Optional[int] = None,
                 message_id: Optional[int] = None,
                 chat_id: Optional[int] = None,
                 result: Optional[ResultStatusEnum] = None):
        """
        Inicializa um novo sinal de trading.
        
        Args:
            signal_id: ID único do sinal
            direction: Direção do sinal (RISE ou FALL)
            confidence: Nível de confiança do sinal (0-100)
            analyze_time: Momento em que a análise foi feita
            entry_time: Momento sugerido para entrada
            open_candle_timestamp: Timestamp do candle de abertura para validação
            message_id: ID da mensagem no Telegram (opcional)
            chat_id: ID do chat no Telegram (opcional)
            result: Resultado do sinal (WIN, LOSS ou None)
        """
        self.signal_id = signal_id
        self.direction = direction
        self.confidence = confidence
        self.analyze_time = analyze_time
        
        self.entry_time = entry_time
            
        self.open_candle_timestamp = open_candle_timestamp
        self.message_id = message_id
        self.chat_id = chat_id
        self.result = result
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Signal':
        """
        Cria uma instância de Signal a partir de um dicionário.
        
        Args:
            data: Dicionário com os dados do sinal
            
        Returns:
            Uma nova instância de Signal
        """
        # Converter string de volta para enum
        direction = None
        if data.get('signal'):
            direction = SignalDirection(data.get('signal'))
        
        result = None
        if data.get('result'):
            result = ResultStatusEnum(data.get('result'))
        
        return cls(
            signal_id=data.get('signal_id'),
            direction=direction,
            confidence=data.get('confidence'),
            analyze_time=data.get('analyze_time'),
            entry_time=data.get('entry_time'),
            open_candle_timestamp=data.get('open_candle_timestamp'),
            message_id=data.get('message_id'),
            chat_id=data.get('chat_id'),
            result=result
        )
    
    def to_dict(self) -> dict:
        """
        Converte o sinal para um dicionário.
        
        Returns:
            Dicionário com os dados do sinal
        """
        return {
            'signal_id': self.signal_id,
            'signal': self.direction.value if self.direction else None,
            'confidence': self.confidence,
            'analyze_time': self.analyze_time,
            'entry_time': self.entry_time,
            'open_candle_timestamp': self.open_candle_timestamp,
            'message_id': self.message_id,
            'chat_id': self.chat_id,
            'result': self.result.value if self.result else None
        }
    
    def __str__(self) -> str:
        """Representação em string do sinal."""
        return (f"Signal(id={self.signal_id}, direction={self.direction}, "
                f"confidence={self.confidence}%, result={self.result or 'Pendente'})") 