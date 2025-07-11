import logging
import os
from pymongo import MongoClient, errors

logger = logging.getLogger(__name__)

mongo_uri = os.getenv('MONGO_URI')
mongo_database = os.getenv('MONGO_DATABASE')
mongo_collection = os.getenv('MONGO_COLLECTION')


class MongoDBRepository:
    def __init__(self):
        try:
            logger.info("Inicializando conexão com o MongoDB.")
            self.client = MongoClient(mongo_uri)
            self.db = self.client[mongo_database]
            self.collection = self.db[mongo_collection]
            logger.info("Conexão com o MongoDB estabelecida.")
        except errors.PyMongoError as e:
            logger.error("Erro ao conectar ao MongoDB: %s", e)
            raise

    def insert_one(self, document):
        try:
            logger.info("Inserindo documento: %s", document)
            result = self.collection.insert_one(document)
            logger.info("Documento inserido com ID: %s", result.inserted_id)
            return result.inserted_id
        except errors.PyMongoError as e:
            logger.error("Erro ao inserir documento: %s", e)
            raise

    def find_one(self, query):
        try:
            logger.info("Buscando documento com a query: %s", query)
            result = self.collection.find_one(query)
            logger.info("Documento encontrado: %s", result)
            return result
        except errors.PyMongoError as e:
            logger.error("Erro ao buscar documento: %s", e)
            raise

    def update_one(self, query, update):
        try:
            logger.info("Atualizando documento com a query: %s, update: %s", query, update)
            result = self.collection.update_one(query, update)
            logger.info("Número de documentos modificados: %d", result.modified_count)
            return result.modified_count
        except errors.PyMongoError as e:
            logger.error("Erro ao atualizar documento: %s", e)
            raise

    def delete_one(self, query):
        try:
            logger.info("Deletando documento com a query: %s", query)
            result = self.collection.delete_one(query)
            logger.info("Número de documentos deletados: %d", result.deleted_count)
            return result.deleted_count
        except errors.PyMongoError as e:
            logger.error("Erro ao deletar documento: %s", e)
            raise

    def find(self, query, projection=None):
        """
        Consulta múltiplos documentos na coleção com base em uma query.

        :param query: Dicionário contendo os critérios de busca.
        :param projection: Dicionário para especificar os campos a serem retornados (opcional).
        :return: Lista de documentos encontrados.
        """
        try:
            logger.info("Buscando documentos com a query: %s e projeção: %s", query, projection)
            cursor = self.collection.find(query, projection)
            results = list(cursor)
            logger.info("Número de documentos encontrados: %d", len(results))
            return results
        except errors.PyMongoError as e:
            logger.error("Erro ao buscar documentos: %s", e)
            raise