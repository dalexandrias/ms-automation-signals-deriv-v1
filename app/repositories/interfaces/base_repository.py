from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TypeVar, Generic

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """
    Interface base para todos os repositórios.
    Define os métodos comuns que todos os repositórios devem implementar.
    """
    
    @abstractmethod
    def insert_one(self, entity: T) -> str:
        """
        Insere uma entidade no repositório.
        
        Args:
            entity: A entidade a ser inserida
            
        Returns:
            ID da entidade inserida
        """
        pass
    
    @abstractmethod
    def find_one(self, filter_dict: Dict[str, Any]) -> Optional[T]:
        """
        Busca uma entidade no repositório com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            
        Returns:
            A entidade encontrada ou None se não encontrar
        """
        pass
    
    @abstractmethod
    def update_one(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> int:
        """
        Atualiza uma entidade no repositório com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            update_dict: Dicionário com os campos a serem atualizados
            
        Returns:
            Número de documentos atualizados
        """
        pass
    
    @abstractmethod
    def delete_one(self, filter_dict: Dict[str, Any]) -> int:
        """
        Remove uma entidade do repositório com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            
        Returns:
            Número de documentos removidos
        """
        pass
    
    @abstractmethod
    def find_many(self, 
                 filter_dict: Optional[Dict[str, Any]] = None,
                 limit: Optional[int] = None,
                 sort: Optional[Dict[str, int]] = None) -> List[T]:
        """
        Busca múltiplas entidades no repositório com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            limit: Limite de resultados
            sort: Dicionário com os campos e direção de ordenação
            
        Returns:
            Lista de entidades encontradas
        """
        pass 