import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from pymongo.collection import Collection

from ..interfaces.candle_repository import CandleRepository
from .mongodb_connection import MongoDBConnection
from app.models.candle import Candle
from app.models.signal import Signal

logger = logging.getLogger(__name__)


class MongoDBCandleRepository(CandleRepository):
    """
    Implementação MongoDB do repositório de candles.
    """
    
    def __init__(self, collection_name: Optional[str] = None):
        """
        Inicializa o repositório de candles.
        
        Args:
            collection_name: Nome da coleção no MongoDB
        """
        self.collection_name = collection_name or os.getenv('MONGO_CANDLE_COLLECTION', 'candles')
        self.connection = MongoDBConnection()
        self.collection: Collection = self.connection.get_collection(self.collection_name)
    
    def find_by_signal_id(self, signal_id: str) -> Optional[Candle]:
        """
        Busca um candle no MongoDB pelo ID do sinal associado.
        
        Args:
            signal_id: ID do sinal
            
        Returns:
            O candle encontrado ou None se não encontrar
        """
        try:
            logger.info(f"Buscando candle com signal_id: {signal_id}")
            # Usa o campo aninhado para a busca
            result = self.collection.find_one({'signal.signal_id': signal_id})
            
            if result:
                logger.info(f"Candle encontrado para o signal_id: {signal_id}")
                return self._create_candle_from_dict(result)
                
            logger.info(f"Candle não encontrado para o signal_id: {signal_id}")
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar candle pelo signal_id {signal_id}: {e}")
            raise

    def insert_one(self, entity: Candle) -> str:
        """
        Insere um candle no MongoDB.
        
        Args:
            entity: O candle a ser inserido
            
        Returns:
            ID do documento inserido
        """
        try:
            logger.info("Inserindo candle: %s", entity)
            candle_dict = self._prepare_candle_dict(entity)
            result = self.collection.insert_one(candle_dict)
            logger.info("Candle inserido com ID: %s", result.inserted_id)
            return str(result.inserted_id)
        except Exception as e:
            logger.error("Erro ao inserir candle: %s", e)
            raise
    
    def find_one(self, filter_dict: Dict[str, Any]) -> Optional[Candle]:
        """
        Busca um candle no MongoDB com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            
        Returns:
            O candle encontrado ou None se não encontrar
        """
        try:
            logger.info("Buscando candle com filtro: %s", filter_dict)
            result = self.collection.find_one(filter_dict)
            if result:
                logger.info("Candle encontrado: %s", result)
                return self._create_candle_from_dict(result)
            logger.info("Candle não encontrado")
            return None
        except Exception as e:
            logger.error("Erro ao buscar candle: %s", e)
            raise
    
    def update_one(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> int:
        """
        Atualiza um candle no MongoDB com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            update_dict: Dicionário com os campos a serem atualizados
            
        Returns:
            Número de documentos atualizados
        """
        try:
            logger.info("Atualizando candle com filtro: %s, update: %s", filter_dict, update_dict)
            result = self.collection.update_one(filter_dict, update_dict)
            logger.info("Número de candles atualizados: %d", result.modified_count)
            return result.modified_count
        except Exception as e:
            logger.error("Erro ao atualizar candle: %s", e)
            raise
    
    def delete_one(self, filter_dict: Dict[str, Any]) -> int:
        """
        Remove um candle do MongoDB com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            
        Returns:
            Número de documentos removidos
        """
        try:
            logger.info("Removendo candle com filtro: %s", filter_dict)
            result = self.collection.delete_one(filter_dict)
            logger.info("Número de candles removidos: %d", result.deleted_count)
            return result.deleted_count
        except Exception as e:
            logger.error("Erro ao remover candle: %s", e)
            raise
    
    def find_many(self, 
                 filter_dict: Optional[Dict[str, Any]] = None,
                 limit: Optional[int] = None,
                 sort: Optional[Dict[str, int]] = None) -> List[Candle]:
        """
        Busca múltiplos candles no MongoDB com base em um filtro.
        
        Args:
            filter_dict: Dicionário com os critérios de busca
            limit: Limite de resultados
            sort: Dicionário com os campos e direção de ordenação
            
        Returns:
            Lista de candles encontrados
        """
        try:
            filter_dict = filter_dict or {}
            logger.info("Buscando candles com filtro: %s, limit: %s, sort: %s", filter_dict, limit, sort)
            
            cursor = self.collection.find(filter_dict)
            
            if sort:
                cursor = cursor.sort(list(sort.items()))
            
            if limit:
                cursor = cursor.limit(limit)
            
            results = list(cursor)
            logger.info("Número de candles encontrados: %d", len(results))
            
            return [self._create_candle_from_dict(doc) for doc in results]
        except Exception as e:
            logger.error("Erro ao buscar candles: %s", e)
            raise
    
    def find_by_epoch(self, epoch: int) -> Optional[Candle]:
        """
        Busca um candle pelo timestamp epoch.
        
        Args:
            epoch: Timestamp do candle
            
        Returns:
            O candle encontrado ou None se não encontrar
        """
        return self.find_one({'epoch': epoch})
    
    def find_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Candle]:
        """
        Busca candles em um intervalo de datas.
        
        Args:
            start_date: Data inicial
            end_date: Data final
            
        Returns:
            Lista de candles no intervalo
        """
        start_epoch = int(start_date.timestamp())
        end_epoch = int(end_date.timestamp())
        return self.find_many({
            'epoch': {
                '$gte': start_epoch,
                '$lte': end_epoch
            }
        }, sort={'epoch': 1})
    
    def find_latest(self, limit: int = 1) -> List[Candle]:
        """
        Busca os candles mais recentes.
        
        Args:
            limit: Número máximo de candles a retornar
            
        Returns:
            Lista de candles mais recentes
        """
        return self.find_many({}, limit=limit, sort={'epoch': -1})
    
    def find_with_signal(self) -> List[Candle]:
        """
        Busca candles que possuem sinais associados.
        
        Returns:
            Lista de candles com sinais
        """
        return self.find_many({'signal': {'$ne': None}})
    
    def update_signal(self, signal: Signal) -> int:
        """
        Atualiza o sinal associado a um candle.
        
        Args:
            epoch: Timestamp do candle
            signal_id: ID do sinal
            
        Returns:
            Número de documentos atualizados
        """
        return self.update_one({'signal.signal_id': signal.signal_id}, {'$set': {'signal': signal.to_dict()}})
    
    def _prepare_candle_dict(self, candle: Candle) -> Dict[str, Any]:
        """
        Prepara um dicionário para inserção no MongoDB a partir de um objeto Candle.
        
        Args:
            candle: Objeto Candle
            
        Returns:
            Dicionário pronto para inserção
        """
        return candle.to_dict()
    
    def _create_candle_from_dict(self, doc: Dict[str, Any]) -> Candle:
        """
        Cria um objeto Candle a partir de um dicionário do MongoDB.
        
        Args:
            doc: Dicionário do MongoDB
            
        Returns:
            Objeto Candle
        """
        return Candle.from_dict(doc)