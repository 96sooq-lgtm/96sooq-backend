"""
Supabase Database Client
Handles all database operations with Supabase PostgreSQL
"""
from supabase import create_client, Client
from config.settings import settings
from typing import Optional, List, Dict, Any

class SupabaseDB:
    """Supabase Database Manager"""
    
    _client: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client (singleton pattern)"""
        if cls._client is None:
            if not settings.supabase_url or not settings.supabase_key:
                raise ValueError("Supabase URL and Key must be set in environment variables")
            
            cls._client = create_client(
                supabase_url=settings.supabase_url,
                supabase_key=settings.supabase_key
            )
        
        return cls._client
    
    @classmethod
    def insert(cls, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a single record"""
        client = cls.get_client()
        response = client.table(table).insert(data).execute()
        return response.data[0] if response.data else None
    
    @classmethod
    def insert_many(cls, table: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert multiple records"""
        client = cls.get_client()
        response = client.table(table).insert(data).execute()
        return response.data
    
    @classmethod
    def select(cls, table: str, columns: str = "*", filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Select records from a table
        
        Example:
            SupabaseDB.select("users", columns="id,name,email")
            SupabaseDB.select("users", filters={"id": "eq.123"})
        """
        client = cls.get_client()
        query = client.table(table).select(columns)
        
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        
        response = query.execute()
        return response.data
    
    @classmethod
    def select_one(cls, table: str, id: str, columns: str = "*") -> Optional[Dict[str, Any]]:
        """Select a single record by ID"""
        client = cls.get_client()
        response = client.table(table).select(columns).eq("id", id).execute()
        return response.data[0] if response.data else None
    
    @classmethod
    def update(cls, table: str, id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a record"""
        client = cls.get_client()
        response = client.table(table).update(data).eq("id", id).execute()
        return response.data[0] if response.data else None
    
    @classmethod
    def delete(cls, table: str, id: str) -> bool:
        """Delete a record"""
        client = cls.get_client()
        response = client.table(table).delete().eq("id", id).execute()
        return len(response.data) > 0
    
    @classmethod
    def query(cls, table: str, query_func) -> Any:
        """
        Execute a custom query for complex operations
        
        Example:
            def custom_query(q):
                return q.select("*").gt("age", 18).limit(10)
            
            results = SupabaseDB.query("users", custom_query)
        """
        client = cls.get_client()
        return query_func(client.table(table)).execute()


# Singleton instance
db = SupabaseDB()
