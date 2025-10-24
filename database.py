from pymongo import MongoClient
from config import Config
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        
    def connect(self):
        try:
            # Close existing connection if any
            if self.client is not None:
                self.client.close()
            
            self.client = MongoClient(Config.MONGODB_URI)
            self.db = self.client[Config.DATABASE_NAME]
            logger.info("Connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def get_collection(self, collection_name):
        if self.db is None or self.client is None:
            self.connect()
        try:
            # Test the connection
            self.client.admin.command('ping')
        except:
            # Reconnect if connection is stale
            self.connect()
        return self.db[collection_name]
    
    def close(self):
        if self.client is not None:
            self.client.close()
            self.client = None
            self.db = None

# Global database instance
db = Database()