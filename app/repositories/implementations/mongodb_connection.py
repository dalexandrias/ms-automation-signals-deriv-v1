import os
import logging
from typing import Optional
from pymongo import MongoClient, errors
from pymongo.database import Database
from pymongo.collection import Collection

logger = logging.getLogger(__name__)


class MongoDBConnection:
    """
    Gerencia a conexão com o MongoDB.
    Implementa o padrão Singleton para garantir uma única instância de conexão.
    """
    _instance: Optional['MongoDBConnection'] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MongoDBConnection, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, uri: Optional[str] = None, database: Optional[str] = None):
        if self._initialized:
            return
            
        self.uri = uri or os.getenv('MONGO_URI')
        self.database_name = database or os.getenv('MONGO_DATABASE')
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        
        if not self.uri or not self.database_name:
            raise ValueError("MongoDB URI e nome do banco de dados são obrigatórios")
        
        self._connect()
        self._initialized = True
    
    def _connect(self) -> None:
        """
        Estabelece a conexão com o MongoDB.
        """
        try:
            logger.info("Inicializando conexão com o MongoDB.")
            self.client = MongoClient(self.uri)
            self.db = self.client[self.database_name]
            logger.info("Conexão com o MongoDB estabelecida.")
        except errors.PyMongoError as e:
            logger.error("Erro ao conectar ao MongoDB: %s", e)
            raise
    
    def get_collection(self, collection_name: str) -> Collection:
        """
        Obtém uma coleção do MongoDB.
        
        Args:
            collection_name: Nome da coleção
            
        Returns:
            Coleção do MongoDB
        """
        if self.db is None:
            self._connect()
        return self.db[collection_name]
    
    def close(self) -> None:
        """
        Fecha a conexão com o MongoDB.
        """
        if self.client is not None:
            self.client.close()
            logger.info("Conexão com o MongoDB fechada.")
            self.client = None
            self.db = None 