from typing import Optional, Union
from datetime import datetime
from app.enums.enum_gale_status import GaleEnum
from app.enums.enum_result_status import ResultStatusEnum


class GaleItem:
    """
    Representa um item de gale com os dados do candle e o tipo de gale.
    """
    
    def __init__(self,
                 gale_type: Optional[GaleEnum] = None,
                 epoch: Optional[int] = None,
                 open_price: Optional[float] = None,
                 high: Optional[float] = None,
                 low: Optional[float] = None,
                 close_price: Optional[float] = None,
                 time: Optional[datetime] = None,
                 result: Optional[ResultStatusEnum] = None):
        """
        Inicializa um item de gale.
        
        Args:
            gale_type: Tipo do gale (GALE_1, GALE_2, etc.)
            epoch: Timestamp Unix do candle
            open_price: Preço de abertura
            high: Preço máximo
            low: Preço mínimo
            close_price: Preço de fechamento
            time: Data/hora do candle
            result: Resultado do gale (WIN, LOSS ou None)
        """
        self.gale_type = gale_type
        self.epoch = epoch
        self.open_price = open_price
        self.high = high
        self.low = low
        self.close_price = close_price
        self.time = time
        self.result = result
    
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
    
    def to_dict(self) -> dict:
        """
        Converte o item de gale para um dicionário.
        
        Returns:
            Dicionário com os dados do item de gale
        """
        return {
            'gale_type': self.gale_type.value if self.gale_type is not None else None,
            'epoch': self.epoch,
            'open_price': self.open_price,
            'high': self.high,
            'low': self.low,
            'close_price': self.close_price,
            'time': self.time,
            'result': self.result.value if hasattr(self.result, 'value') else self.result
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GaleItem':
        """
        Cria uma instância de GaleItem a partir de um dicionário.
        
        Args:
            data: Dicionário com os dados do item de gale
            
        Returns:
            Nova instância de GaleItem
        """
        gale_type = GaleEnum(data['gale_type']) if isinstance(data['gale_type'], str) else data['gale_type']
        
        return cls(
            gale_type=gale_type,
            epoch=data.get('epoch'),
            open_price=data.get('open_price'),
            high=data.get('high'),
            low=data.get('low'),
            close_price=data.get('close_price'),
            time=data.get('time'),
            result=data.get('result')
        )
    
    def __str__(self) -> str:
        """Representação em string do item de gale."""
        direction = "BULLISH" if self.is_bullish else "BEARISH" if self.is_bearish else "DOJI"
        return (f"GaleItem({self.gale_type}, {self.time}, {direction}, "
                f"O:{self.open_price:.2f}, H:{self.high:.2f}, L:{self.low:.2f}, C:{self.close_price:.2f}, "
                f"Result:{self.result or 'Pending'})")
