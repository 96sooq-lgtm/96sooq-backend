"""
Supabase Database Client
Handles all database operations with Supabase PostgreSQL
"""
from supabase import create_client, Client, ClientOptions
from config.settings import settings
from typing import Optional, List, Dict, Any

class SupabaseDB:
    """Supabase Database Manager"""
    
    _client: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client (singleton pattern)"""
        if cls._client is None:
            if not settings.supabase_url or not settings.supabase_service_role_key:
                raise ValueError("Supabase URL and Service Role Key must be set")

            cls._client = create_client(
                supabase_url=settings.supabase_url,
                supabase_key=settings.supabase_service_role_key,
                options=ClientOptions(
                    postgrest_client_timeout=20,
                    storage_client_timeout=20
                )
            )
        
        return cls._client
    
    @classmethod
    def insert(cls, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a single record"""
        def run():
            client = cls.get_client()
            return client.table(table).insert(data).execute()
            
        response = cls._safe_execute(run)
        return response.data[0] if response.data else None
    
    @classmethod
    def insert_many(cls, table: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert multiple records"""
        def run():
            client = cls.get_client()
            return client.table(table).insert(data).execute()
            
        response = cls._safe_execute(run)
        return response.data
    
    @classmethod
    def select(cls, table: str, columns: str = "*", filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Select records from a table"""
        def run():
            client = cls.get_client()
            query = client.table(table).select(columns)
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            return query.execute()
        
        response = cls._safe_execute(run)
        return response.data

    @classmethod
    def select_one(cls, table: str, id: str, columns: str = "*") -> Optional[Dict[str, Any]]:
        """Select a single record by ID"""
        def run():
            client = cls.get_client()
            return client.table(table).select(columns).eq("id", id).execute()
            
        response = cls._safe_execute(run)
        return response.data[0] if response.data else None

    @classmethod
    def select_in(cls, table: str, column: str, values: list, columns: str = "*") -> List[Dict[str, Any]]:
        """Select records where column value is IN a list of values."""
        if not values:
            return []
            
        def run():
            client = cls.get_client()
            return client.table(table).select(columns).in_(column, values).execute()
            
        response = cls._safe_execute(run)
        return response.data if response.data else []
    
    @classmethod
    def update(cls, table: str, id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a record"""
        def run():
            client = cls.get_client()
            return client.table(table).update(data).eq("id", id).execute()
            
        response = cls._safe_execute(run)
        return response.data[0] if response.data else None
    
    @classmethod
    def delete(cls, table: str, id: str) -> bool:
        """Delete a record"""
        def run():
            client = cls.get_client()
            return client.table(table).delete().eq("id", id).execute()
            
        response = cls._safe_execute(run)
        return len(response.data) > 0
    
    @classmethod
    def query(cls, table: str, query_func) -> Any:
        """Execute a custom query with retry on connection error."""
        def run():
            client = cls.get_client()
            return query_func(client.table(table)).execute()

        return cls._safe_execute(run)

    @classmethod
    def _safe_execute(cls, func, max_retries: int = 3) -> Any:
        """
        Wraps database execution with retry logic for common connection errors.
        Specifically handles 'RemoteProtocolError: Server disconnected' which
        can happen when a pooled connection is closed by the server.
        """
        import time
        from utils.logger import get_logger
        logger = get_logger(__name__)

        attempt = 0
        while attempt < max_retries:
            try:
                return func()
            except Exception as e:
                e_str = str(e)
                # Detect connection loss / protocol errors
                if "Server disconnected" in e_str or "RemoteProtocolError" in e_str or "ReadTimeout" in type(e).__name__:
                    attempt += 1
                    if attempt >= max_retries:
                        logger.error(f"Supabase connection retry failed after {max_retries} attempts: {e}")
                        raise e
                        
                    logger.warning(
                        f"Supabase connection issue ({type(e).__name__}). "
                        f"Attempt {attempt}/{max_retries}. Retrying in {0.5 * attempt}s..."
                    )
                    
                    time.sleep(0.5 * attempt)
                    # Force client re-initialization
                    cls._client = None
                else:
                    # Re-raise if it's not a connection issue we can fix by retrying
                    raise e

    @classmethod
    def broadcast(cls, channel: str, event: str, payload: Dict[str, Any]) -> bool:
        """
        Broadcast a Realtime message directly (ephemeral).
        Using the Supabase Realtime REST API.
        """
        import httpx
        from utils.logger import get_logger
        logger = get_logger(__name__)
        try:
            # Correct endpoint is /realtime/v1/api/broadcast
            url = f"{settings.supabase_url.rstrip('/')}/realtime/v1/api/broadcast"
            
            headers = {
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "application/json"
            }
            
            # The Realtime v2 REST protocol expects a message object
            body = {
                "topic": channel,
                "event": event,
                "payload": payload,
                "type": "broadcast"
            }
            
            # Using a short-lived client for broadcast to avoid stale connection issues
            with httpx.Client(timeout=5.0) as client:
                response = client.post(url, headers=headers, json=body)
                if response.status_code != 200:
                    logger.warning(f"Realtime broadcast HTTP error: {response.status_code} - {response.text}")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Realtime broadcast exception: {e}")
            return False


# Singleton instance
db = SupabaseDB()
