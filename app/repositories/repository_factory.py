import os
from typing import Dict, Type, TypeVar, Optional, cast

from .interfaces.base_repository import BaseRepository
from .interfaces.signal_repository import SignalRepository
from .interfaces.candle_repository import CandleRepository
from .implementations.mongodb_signal_repository import MongoDBSignalRepository
from .implementations.mongodb_candle_repository import MongoDBCandleRepository

T = TypeVar('T', bound=BaseRepository)


class RepositoryFactory:
    """
    Fábrica para criar instâncias de repositórios.
    Implementa o padrão Factory para abstrair a criação de repositórios.
    """
    
    _repositories: Dict[Type[BaseRepository], Type[BaseRepository]] = {
        SignalRepository: MongoDBSignalRepository,
        CandleRepository: MongoDBCandleRepository
    }
    
    _instances: Dict[Type[BaseRepository], BaseRepository] = {}
    
    @classmethod
    def get_repository(cls, repository_type: Type[T]) -> T:
        """
        Obtém uma instância de repositório.
        
        Args:
            repository_type: Tipo de repositório
            
        Returns:
            Instância do repositório
        """
        if repository_type not in cls._instances:
            implementation = cls._repositories.get(repository_type)
            if not implementation:
                raise ValueError(f"Não há implementação para {repository_type.__name__}")
            
            cls._instances[repository_type] = implementation()
        
        return cast(T, cls._instances[repository_type])
    
    @classmethod
    def get_signal_repository(cls) -> SignalRepository:
        """
        Obtém uma instância do repositório de sinais.
        
        Returns:
            Instância do repositório de sinais
        """
        return cls.get_repository(SignalRepository)
    
    @classmethod
    def get_candle_repository(cls) -> CandleRepository:
        """
        Obtém uma instância do repositório de candles.
        
        Returns:
            Instância do repositório de candles
        """
        return cls.get_repository(CandleRepository) 