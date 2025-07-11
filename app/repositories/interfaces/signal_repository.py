from abc import abstractmethod
from datetime import datetime
from typing import List, Optional

from repositories.interfaces.base_repository import BaseRepository
from models.signal import Signal


class SignalRepository(BaseRepository[Signal]):
    """
    Interface para o repositório de sinais.
    Define métodos específicos para operações com sinais.
    """
    
    @abstractmethod
    def find_pending_signals(self) -> List[Signal]:
        """
        Busca sinais pendentes de validação.
        
        Returns:
            Lista de sinais pendentes
        """
        pass
    
    @abstractmethod
    def mark_as_validated(self, signal_id: str, result: str) -> int:
        """
        Marca um sinal como validado com resultado.
        
        Args:
            signal_id: ID do sinal
            result: Resultado do sinal (WIN ou LOSS)
            
        Returns:
            Número de documentos atualizados
        """
        pass
    
    @abstractmethod
    def get_signals_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Signal]:
        """
        Obtém sinais em um intervalo de datas.
        
        Args:
            start_date: Data inicial
            end_date: Data final
            
        Returns:
            Lista de sinais no intervalo
        """
        pass
    
    @abstractmethod
    def get_signal_by_id(self, signal_id: str) -> Optional[Signal]:
        """
        Busca um sinal pelo ID.
        
        Args:
            signal_id: ID do sinal
            
        Returns:
            O sinal encontrado ou None se não encontrar
        """
        pass
    
    @abstractmethod
    def get_signals_by_result(self, result: str) -> List[Signal]:
        """
        Busca sinais por resultado.
        
        Args:
            result: Resultado do sinal (WIN, LOSS ou None)
            
        Returns:
            Lista de sinais com o resultado especificado
        """
        pass 