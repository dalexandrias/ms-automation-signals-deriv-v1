import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from pymongo.collection import Collection

from repositories.interfaces.signal_repository import SignalRepository
from repositories.implementations.mongodb_connection import MongoDBConnection
from models.signal import Signal

logger = logging.getLogger(__name__)


class MongoDBSignalRepository(SignalRepository):
    """
    Implementação MongoDB do repositório de sinais.
    """
    
    def __init__(self, collection_name: Optional[str] = None):
        """
        Inicializa o repositório de sinais.
        
        Args:
            collection_name: Nome da coleção no MongoDB
        """
        self.collection_name = collection_name or os.getenv('MONGO_COLLECTION', 'sinais')
        self.connection = MongoDBConnection()
        self.collection: Collection = self.connection.get_collection(self.collection_name)
    
    def insert_one(self, entity: Signal) -> str:
        """
        Insere um sinal no MongoDB.
        
        Args:
            entity: O sinal a ser inserido
            
        Returns:
            ID do documento inserido
        """
        try:
            logger.info("Inserindo sinal: %s", entity)
            result = self.collection.insert_one(entity.to_dict())
            logger.info("Sinal inserido com ID: %s", result.inserted_id)
            return str(result.inserted_id)
        except Exception as e:
            logger.error("Erro ao inserir sinal: %s", e)
            raise
    
    def find_one(self, filter_dict: Dict[str, Any]) -> Optional[Signal]:
        """
        Busca um sinal no MongoDB com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            
        Returns:
            O sinal encontrado ou None se não encontrar
        """
        try:
            logger.info("Buscando sinal com filtro: %s", filter_dict)
            result = self.collection.find_one(filter_dict)
            if result:
                logger.info("Sinal encontrado: %s", result)
                return Signal.from_dict(result)
            logger.info("Sinal não encontrado")
            return None
        except Exception as e:
            logger.error("Erro ao buscar sinal: %s", e)
            raise
    
    def update_one(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> int:
        """
        Atualiza um sinal no MongoDB com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            update_dict: Dicionário com os campos a serem atualizados
            
        Returns:
            Número de documentos atualizados
        """
        try:
            logger.info("Atualizando sinal com filtro: %s, update: %s", filter_dict, update_dict)
            result = self.collection.update_one(filter_dict, update_dict)
            logger.info("Número de sinais atualizados: %d", result.modified_count)
            return result.modified_count
        except Exception as e:
            logger.error("Erro ao atualizar sinal: %s", e)
            raise
    
    def delete_one(self, filter_dict: Dict[str, Any]) -> int:
        """
        Remove um sinal do MongoDB com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            
        Returns:
            Número de documentos removidos
        """
        try:
            logger.info("Removendo sinal com filtro: %s", filter_dict)
            result = self.collection.delete_one(filter_dict)
            logger.info("Número de sinais removidos: %d", result.deleted_count)
            return result.deleted_count
        except Exception as e:
            logger.error("Erro ao remover sinal: %s", e)
            raise
    
    def find_many(self, 
                 filter_dict: Optional[Dict[str, Any]] = None,
                 limit: Optional[int] = None,
                 sort: Optional[Dict[str, int]] = None) -> List[Signal]:
        """
        Busca múltiplos sinais no MongoDB com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            limit: Limite de resultados
            sort: Dicionário com os campos e direção de ordenação
            
        Returns:
            Lista de sinais encontrados
        """
        try:
            filter_dict = filter_dict or {}
            logger.info("Buscando sinais com filtro: %s, limit: %s, sort: %s", filter_dict, limit, sort)
            
            cursor = self.collection.find(filter_dict)
            
            if sort:
                cursor = cursor.sort(list(sort.items()))
            
            if limit:
                cursor = cursor.limit(limit)
            
            results = list(cursor)
            logger.info("Número de sinais encontrados: %d", len(results))
            
            return [Signal.from_dict(doc) for doc in results]
        except Exception as e:
            logger.error("Erro ao buscar sinais: %s", e)
            raise
    
    def find_pending_signals(self) -> List[Signal]:
        """
        Busca sinais pendentes de validação.
        
        Returns:
            Lista de sinais pendentes
        """
        return self.find_many({'result': None})
    
    def mark_as_validated(self, signal_id: str, result: str) -> int:
        """
        Marca um sinal como validado com resultado.
        
        Args:
            signal_id: ID do sinal
            result: Resultado do sinal (WIN ou LOSS)
            
        Returns:
            Número de documentos atualizados
        """
        return self.update_one({'signal_id': signal_id}, {'$set': {'result': result}})
    
    def get_signals_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Signal]:
        """
        Obtém sinais em um intervalo de datas.
        
        Args:
            start_date: Data inicial
            end_date: Data final
            
        Returns:
            Lista de sinais no intervalo
        """
        return self.find_many({
            'analyze_time': {
                '$gte': start_date,
                '$lte': end_date
            }
        })
    
    def get_signal_by_id(self, signal_id: str) -> Optional[Signal]:
        """
        Busca um sinal pelo ID.
        
        Args:
            signal_id: ID do sinal
            
        Returns:
            O sinal encontrado ou None se não encontrar
        """
        return self.find_one({'signal_id': signal_id})
    
    def get_signals_by_result(self, result: str) -> List[Signal]:
        """
        Busca sinais por resultado.
        
        Args:
            result: Resultado do sinal (WIN, LOSS ou None)
            
        Returns:
            Lista de sinais com o resultado especificado
        """
        return self.find_many({'result': result}) 