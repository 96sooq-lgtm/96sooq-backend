"""
Supabase Database Client
Handles all database operations with Supabase PostgreSQL
Production-ready with HTTP/2 disabled, retry logic, and broadcast support.
"""

import time
import threading
from typing import Any, Dict, List, Optional

import httpx
from httpx import RemoteProtocolError as HttpxRemoteProtocolError
from supabase import Client, ClientOptions, create_client

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Retryable error signals ───────────────────────────────────────────────────

_RETRYABLE_ERRORS = (
    "Server disconnected",
    "RemoteProtocolError",
    "ReadTimeout",
    "ConnectionTerminated",
    "ConnectTimeout",
    "ConnectionResetError",
    "BrokenPipeError",
)


class SupabaseDB:
    """
    Supabase Database Manager (Singleton, thread-safe)

    Features:
    - HTTP/2 disabled to prevent RemoteProtocolError / ConnectionTerminated
    - Exponential back-off retry on transient connection errors
    - Thread-safe singleton client with double-checked locking
    - Realtime broadcast via REST API (short-lived httpx client)
    """

    _client: Optional[Client] = None
    _lock = threading.Lock()

    # ── Client initialisation ─────────────────────────────────────────────────

    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client (singleton, thread-safe, HTTP/2 disabled)."""
        if cls._client is None:
            with cls._lock:
                if cls._client is None:
                    if not settings.supabase_url or not settings.supabase_service_role_key:
                        raise ValueError(
                            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment."
                        )

                    # HTTP/2 disabled — prevents RemoteProtocolError / ConnectionTerminated
                    transport = httpx.HTTPTransport(http2=False, retries=2)
                    httpx_client = httpx.Client(
                        transport=transport,
                        timeout=httpx.Timeout(20.0, connect=10.0),
                    )

                    cls._client = create_client(
                        supabase_url=settings.supabase_url,
                        supabase_key=settings.supabase_service_role_key,
                        options=ClientOptions(
                            postgrest_client_timeout=20,
                            storage_client_timeout=20,
                            httpx_client_args={
                                "http2": False,
                                "timeout": httpx.Timeout(20.0, connect=10.0),
                            },
                        ),
                    )
                    logger.info("Supabase client initialised (HTTP/2 disabled).")
        return cls._client

    @classmethod
    def reset_client(cls) -> None:
        """Force re-initialisation of the Supabase client on next use."""
        with cls._lock:
            cls._client = None
        logger.warning("Supabase client reset — will reinitialise on next request.")

    # ── CRUD helpers ──────────────────────────────────────────────────────────

    @classmethod
    def insert(cls, table: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insert a single record and return it."""
        response = cls._safe_execute(
            lambda: cls.get_client().table(table).insert(data).execute()
        )
        return response.data[0] if response and response.data else None

    @classmethod
    def insert_many(
        cls, table: str, data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Insert multiple records and return them."""
        if not data:
            return []
        response = cls._safe_execute(
            lambda: cls.get_client().table(table).insert(data).execute()
        )
        return response.data if response and response.data else []

    @classmethod
    def select(
        cls,
        table: str,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        ascending: bool = True,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Select records with optional filters, ordering, and limit."""

        def run():
            query = cls.get_client().table(table).select(columns)
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            if order_by:
                query = query.order(order_by, desc=not ascending)
            if limit:
                query = query.limit(limit)
            return query.execute()

        response = cls._safe_execute(run)
        return response.data if response and response.data else []

    @classmethod
    def select_one(
        cls, table: str, id: str, columns: str = "*"
    ) -> Optional[Dict[str, Any]]:
        """Select a single record by ID."""
        response = cls._safe_execute(
            lambda: cls.get_client()
            .table(table)
            .select(columns)
            .eq("id", id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response and response.data else None

    @classmethod
    def select_in(
        cls,
        table: str,
        column: str,
        values: list,
        columns: str = "*",
    ) -> List[Dict[str, Any]]:
        """Select records where column value is IN a list."""
        if not values:
            return []
        response = cls._safe_execute(
            lambda: cls.get_client()
            .table(table)
            .select(columns)
            .in_(column, values)
            .execute()
        )
        return response.data if response and response.data else []

    @classmethod
    def update(
        cls, table: str, id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a record by ID and return the updated row."""
        response = cls._safe_execute(
            lambda: cls.get_client().table(table).update(data).eq("id", id).execute()
        )
        return response.data[0] if response and response.data else None

    @classmethod
    def update_where(
        cls, table: str, filters: Dict[str, Any], data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Update records matching all filters and return updated rows."""

        def run():
            query = cls.get_client().table(table).update(data)
            for key, value in filters.items():
                query = query.eq(key, value)
            return query.execute()

        response = cls._safe_execute(run)
        return response.data if response and response.data else []

    @classmethod
    def delete(cls, table: str, id: str) -> bool:
        """Delete a record by ID."""
        response = cls._safe_execute(
            lambda: cls.get_client().table(table).delete().eq("id", id).execute()
        )
        return bool(response and response.data)

    @classmethod
    def delete_where(cls, table: str, filters: Dict[str, Any]) -> bool:
        """Delete records matching all filters."""

        def run():
            query = cls.get_client().table(table).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            return query.execute()

        response = cls._safe_execute(run)
        return bool(response and response.data)

    @classmethod
    def query(cls, table: str, query_func) -> Any:
        """Execute a custom query function with retry support.

        Usage:
            db.query("messages", lambda q: q.select("*").eq("chat_id", cid).order("created_at"))
        """
        return cls._safe_execute(
            lambda: query_func(cls.get_client().table(table)).execute()
        )

    @classmethod
    def rpc(cls, function_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Call a Supabase RPC (stored procedure)."""
        response = cls._safe_execute(
            lambda: cls.get_client().rpc(function_name, params or {}).execute()
        )
        return response.data if response else None

    # ── Retry engine ──────────────────────────────────────────────────────────

    @classmethod
    def _safe_execute(cls, func, max_retries: int = 3) -> Any:
        """
        Execute a Supabase query with retry logic for transient connection errors.

        - Detects: RemoteProtocolError, ConnectionTerminated, ReadTimeout, etc.
        - Exponential back-off: 0.5s → 1.0s → 1.5s
        - Forces client re-initialisation on each retry attempt
        """
        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                return func()

            except Exception as e:
                last_exception = e
                e_str = str(e)
                type_name = type(e).__name__

                is_retryable = (
                    any(sig in e_str for sig in _RETRYABLE_ERRORS)
                    or any(sig in type_name for sig in _RETRYABLE_ERRORS)
                    or isinstance(e, HttpxRemoteProtocolError)
                )

                if not is_retryable:
                    # Non-retryable error — raise immediately
                    raise

                if attempt == max_retries:
                    logger.error(
                        f"Supabase query failed after {max_retries} attempts. "
                        f"Last error: [{type_name}] {e_str}"
                    )
                    raise

                delay = 0.5 * attempt
                logger.warning(
                    f"Supabase transient error [{type_name}] on attempt {attempt}/{max_retries}. "
                    f"Retrying in {delay}s... Details: {e_str}"
                )
                time.sleep(delay)

                # Force fresh client on next attempt
                cls._client = None

        # Should never reach here, but safety net
        if last_exception:
            raise last_exception

    # ── Realtime broadcast ────────────────────────────────────────────────────

    @classmethod
    def broadcast(
        cls,
        channel: str,
        event: str,
        payload: Dict[str, Any],
        timeout: float = 5.0,
    ) -> bool:
        """
        Broadcast a Realtime message via the Supabase REST broadcast API.
        Uses a fresh short-lived httpx client (HTTP/1.1) to avoid stale connections.

        Args:
            channel: Supabase channel name e.g. "conversation:uuid"
            event:   Event name e.g. "new_message"
            payload: Dict payload to send to Flutter clients
            timeout: Request timeout in seconds (default 5s)

        Returns:
            True if broadcast succeeded, False otherwise
        """
        url = f"{settings.supabase_url.rstrip('/')}/realtime/v1/api/broadcast"
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }
        body = {
            "messages": [
                {
                    "topic":   channel,
                    "event":   event,
                    "payload": payload,
                }
            ]
        }

        for attempt in range(1, 3):  # 2 attempts for broadcast
            try:
                # Fresh client per call — avoids stale HTTP/2 connection issues
                with httpx.Client(
                    http2=False,
                    timeout=httpx.Timeout(timeout),
                ) as client:
                    response = client.post(url, headers=headers, json=body)

                if response.status_code in (200, 202):
                    logger.debug(
                        f"Broadcast sent → channel='{channel}' event='{event}'"
                    )
                    return True

                logger.warning(
                    f"Broadcast HTTP {response.status_code} on attempt {attempt}: {response.text}"
                )

            except Exception as e:
                logger.error(
                    f"Broadcast exception on attempt {attempt} "
                    f"[{type(e).__name__}]: {e}"
                )

            if attempt < 2:
                time.sleep(0.3)

        return False

    # ── Health check ──────────────────────────────────────────────────────────

    @classmethod
    def ping(cls) -> bool:
        """
        Lightweight health check — verifies Supabase connectivity.
        Returns True if connection is healthy, False otherwise.
        """
        try:
            cls.get_client().table("conversations").select("id").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Supabase health check failed: {e}")
            cls._client = None  # Reset so next real request gets a fresh client
            return False


# ── Singleton instance ────────────────────────────────────────────────────────

db = SupabaseDB()