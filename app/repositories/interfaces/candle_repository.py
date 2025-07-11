from abc import abstractmethod
from datetime import datetime
from typing import List, Optional

from models.signal import Signal
from repositories.interfaces.base_repository import BaseRepository
from models.candle import Candle


class CandleRepository(BaseRepository[Candle]):
    """
    Interface para o repositório de candles.
    Define métodos específicos para operações com candles.
    """
    
    @abstractmethod
    def find_by_epoch(self, epoch: int) -> Optional[Candle]:
        """
        Busca um candle pelo timestamp epoch.
        
        Args:
            epoch: Timestamp do candle
            
        Returns:
            O candle encontrado ou None se não encontrar
        """
        pass
    
    @abstractmethod
    def find_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Candle]:
        """
        Busca candles em um intervalo de datas.
        
        Args:
            start_date: Data inicial
            end_date: Data final
            
        Returns:
            Lista de candles no intervalo
        """
        pass
    
    @abstractmethod
    def find_latest(self, limit: int = 1) -> List[Candle]:
        """
        Busca os candles mais recentes.
        
        Args:
            limit: Número máximo de candles a retornar
            
        Returns:
            Lista de candles mais recentes
        """
        pass
    
    @abstractmethod
    def find_with_signal(self) -> List[Candle]:
        """
        Busca candles que possuem sinais associados.
        
        Returns:
            Lista de candles com sinais
        """
        pass
    
    @abstractmethod
    def update_signal(self, signal: Signal) -> int:
        """
        Atualiza o sinal associado a um candle.
        
        Args:
            signal: Instância de Signal com os dados atualizados
            
        Returns:
            Número de documentos atualizados
        """
        pass 

    @abstractmethod
    def find_by_signal_id(self, signal_id: str) -> Optional[Candle]:
        """
        Busca um candle pelo ID do sinal associado.
        
        Args:
            signal_id: ID do sinal
            
        Returns:
            O candle encontrado ou None se não encontrar
        """
        pass