from datetime import datetime
from typing import Optional, Tuple, Any, List, TYPE_CHECKING, Union
from .signal import Signal

if TYPE_CHECKING:
    from .gale_item import GaleItem
    from app.enums.enum_gale_status import GaleEnum

class Candle:
    """
    Representa um candle OHLC (Open, High, Low, Close).
    """
    def __init__(self, 
                 epoch: Optional[int] = None,
                 open_price: Optional[float] = None,
                 high: Optional[float] = None,
                 low: Optional[float] = None,
                 close_price: Optional[float] = None,    
                 signal: Optional[Signal] = None,
                 time: Optional[datetime] = None,
                 gale_items: Optional[List['GaleItem']] = None):
        """
        Inicializa um novo candle.
        
        Args:
            epoch: Timestamp Unix do candle
            open_price: Preço de abertura
            high: Preço máximo
            low: Preço mínimo
            close_price: Preço de fechamento
            signal: Sinal gerado pelo candle
            time: Data/hora do candle (opcional, calculado a partir do epoch se não fornecido)
            gale_items: Lista de itens de gale associados ao candle
        """
        self.epoch = epoch
        self.open_price = open_price
        self.high = high
        self.low = low
        self.close_price = close_price
        self.time = time
        self.signal = signal
        self.gale_items = gale_items or []

    @property
    def body(self) -> float:
        """Tamanho do corpo do candle."""
        if self.close_price is None or self.open_price is None:
            return 0
        return abs(self.close_price - self.open_price)
    
    @property
    def is_bullish(self) -> bool:
        """Verifica se o candle é de alta."""
        if self.close_price is None or self.open_price is None:
            return False
        return self.close_price > self.open_price
    
    @property
    def is_bearish(self) -> bool:
        """Verifica se o candle é de baixa."""
        if self.close_price is None or self.open_price is None:
            return False
        return self.close_price < self.open_price
    
    @property
    def is_doji(self) -> bool:
        """Verifica se o candle é um doji (sem corpo)."""
        if self.close_price is None or self.open_price is None:
            return False
        return self.close_price == self.open_price
    
    @classmethod
    def from_tuple(cls, data: Tuple[Any, ...]) -> 'Candle':
        """
        Cria uma instância de Candle a partir de uma tupla.
        
        Args:
            data: Tupla com os dados do candle. Pode ter diferentes formatos:
                 - (epoch, open, high, low, close)
                 - (epoch, open, high, low, close)
                 - (epoch, open, high, low, close, signal)
            
        Returns:
            Uma nova instância de Candle
        """
        # Verificar o tamanho da tupla e extrair os valores conforme disponibilidade
        epoch = data[0]
        open_price = data[1]
        high = data[2]
        low = data[3]
        close_price = data[4]
        
        signal = None
        
        
        if len(data) > 6:
            # Se o sinal for um dicionário, converter para objeto Signal
            if isinstance(data[6], dict):
                from .signal import Signal
                signal = Signal.from_dict(data[6])
            else:
                signal = data[6]
        
        return cls(
            epoch=epoch,
            open_price=open_price,
            high=high,
            low=low,
            close_price=close_price,
            signal=signal
        )
    
    def to_tuple(self) -> tuple:
        """
        Converte o candle para uma tupla.
        
        Returns:
            Tupla com os dados do candle (epoch, open, high, low, close, signal)
        """
        return (
            self.epoch,
            self.open_price,
            self.high,
            self.low,
            self.close_price,
            self.signal.to_dict() if self.signal else None
        )
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Candle':
        """
        Cria uma instância de Candle a partir de um dicionário.
        """
        # Extrair o sinal se estiver presente no dicionário
        signal_data = data.pop('signal', None)
        data.pop('_id', None)
        signal = None
        if signal_data:
            from .signal import Signal
            signal = Signal.from_dict(signal_data)
        
        # Extrair os itens de gale se estiverem presentes
        gale_items_data = data.pop('gale_items', None)
        gale_items = []
        if gale_items_data:
            from .gale_item import GaleItem
            gale_items = [GaleItem.from_dict(item) for item in gale_items_data]
            
        # Renomear chaves se necessário para compatibilidade com o construtor
        if 'open' in data and 'open_price' not in data:
            data['open_price'] = data.pop('open')
        if 'close' in data and 'close_price' not in data:
            data['close_price'] = data.pop('close')
            
        # Adicionar o sinal e gale_items de volta
        data['signal'] = signal
        data['gale_items'] = gale_items
        
        return cls(**data)
    
    def to_dict(self) -> dict:
        """
        Converte o candle para um dicionário.
        
        Returns:
            Dicionário com os dados do candle
        """
        return {
            'epoch': self.epoch,
            'open': self.open_price,
            'high': self.high,
            'low': self.low,
            'close': self.close_price,
            'time': self.time,
            'signal': self.signal.to_dict() if self.signal else None,
            'gale_items': [item.to_dict() for item in self.gale_items] if self.gale_items else []
        }
    
    def __str__(self) -> str:
        """Representação em string do candle."""
        direction = "BULLISH" if self.is_bullish else "BEARISH" if self.is_bearish else "DOJI"
        gale_info = f", Gales:{len(self.gale_items)}" if self.gale_items else ""
        return (f"Candle({self.time}, {direction}, "
                f"O:{self.open_price:.2f}, H:{self.high:.2f}, L:{self.low:.2f}, C:{self.close_price:.2f}{gale_info})")
    
    def update_gale_item(self, gale_item: 'GaleItem') -> None:
        """
        Atualiza um item de gale existente no candle.
        
        Args:
            gale_item: Item de gale a ser atualizado
        """
        for item in self.gale_items:
            if item.epoch == gale_item.epoch:
                item.open_price = gale_item.open_price
                item.high = gale_item.high
                item.low = gale_item.low
                item.close_price = gale_item.close_price
                item.time = gale_item.time
                item.result = gale_item.result
                break
        

    def add_gale_item(self, gale_item: 'GaleItem') -> None:
        """
        Adiciona um item de gale ao candle.
        
        Args:
            gale_item: Item de gale a ser adicionado
        """
        self.gale_items.append(gale_item)
    
    def get_gale_items_by_type(self, gale_type: 'GaleEnum') -> List['GaleItem']:
        """
        Retorna todos os itens de gale de um tipo específico.
        
        Args:
            gale_type: Tipo de gale a ser filtrado
            
        Returns:
            Lista de itens de gale do tipo especificado
        """
        return [item for item in self.gale_items if item.gale_type == gale_type]
    
    def has_gale_items(self) -> bool:
        """
        Verifica se o candle possui itens de gale.
        
        Returns:
            True se possui itens de gale, False caso contrário
        """
        return len(self.gale_items) > 0
    
    def get_latest_gale_item(self) -> Optional['GaleItem']:
        """
        Retorna o último item de gale adicionado.
        
        Returns:
            Último item de gale ou None se não houver itens
        """
        return self.gale_items[-1] if self.gale_items else None