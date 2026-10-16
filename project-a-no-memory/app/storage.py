"""
Transactional SQLite storage layer with WAL mode for EventRoute.
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.models import DeliveryStatus, WebhookDeliveryLog, RoutingSubscription


class SQLiteStorage:
    """Thread-safe SQLite storage with WAL mode enabled."""

    def __init__(self, db_path: str = "eventroute.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for high-concurrency non-blocking reads/writes
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        with conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_logs (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                destination_url TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_http_status INTEGER,
                response_body TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events (id)
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY,
                topic_pattern TEXT NOT NULL,
                destination_url TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_idemp ON events(idempotency_key);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_delivery_status ON delivery_logs(status);")

    def save_event(self, event_id: str, source_id: str, topic: str, payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> bool:
        """Saves an incoming event. Returns False if duplicate idempotency key exists."""
        conn = self._get_connection()
        payload_json = json.dumps(payload)
        now = datetime.now(timezone.utc).isoformat()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO events (id, source_id, topic, payload, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (event_id, source_id, topic, payload_json, idempotency_key, now)
                )
            return True
        except sqlite3.IntegrityError:
            # Duplicate idempotency key
            return False

    def get_event_by_idempotency_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM events WHERE idempotency_key = ?", (idempotency_key,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "source_id": row["source_id"],
            "topic": row["topic"],
            "payload": json.loads(row["payload"]),
            "idempotency_key": row["idempotency_key"],
            "created_at": row["created_at"],
        }

    def save_delivery_log(self, log: WebhookDeliveryLog) -> None:
        conn = self._get_connection()
        with conn:
            conn.execute("""
            INSERT INTO delivery_logs (
                id, event_id, source_id, topic, destination_url, status, attempts, last_http_status, response_body, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                attempts = excluded.attempts,
                last_http_status = excluded.last_http_status,
                response_body = excluded.response_body,
                updated_at = excluded.updated_at
            """, (
                log.id, log.event_id, log.source_id, log.topic, log.destination_url,
                log.status.value, log.attempts, log.last_http_status, log.response_body,
                log.created_at, log.updated_at
            ))

    def get_delivery_logs(self, limit: int = 50) -> List[WebhookDeliveryLog]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM delivery_logs ORDER BY created_at DESC LIMIT ?", (limit,))
        logs = []
        for r in cur.fetchall():
            logs.append(WebhookDeliveryLog(
                id=r["id"],
                event_id=r["event_id"],
                source_id=r["source_id"],
                topic=r["topic"],
                destination_url=r["destination_url"],
                status=DeliveryStatus(r["status"]),
                attempts=r["attempts"],
                last_http_status=r["last_http_status"],
                response_body=r["response_body"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            ))
        return logs

    def get_delivery_log_by_id(self, log_id: str) -> Optional[WebhookDeliveryLog]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM delivery_logs WHERE id = ?", (log_id,))
        r = cur.fetchone()
        if not r:
            return None
        return WebhookDeliveryLog(
            id=r["id"],
            event_id=r["event_id"],
            source_id=r["source_id"],
            topic=r["topic"],
            destination_url=r["destination_url"],
            status=DeliveryStatus(r["status"]),
            attempts=r["attempts"],
            last_http_status=r["last_http_status"],
            response_body=r["response_body"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def add_subscription(self, sub: RoutingSubscription) -> None:
        conn = self._get_connection()
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO subscriptions (id, topic_pattern, destination_url, enabled) VALUES (?, ?, ?, ?)",
                (sub.id, sub.topic_pattern, sub.destination_url, 1 if sub.enabled else 0)
            )

    def get_matching_subscriptions(self, topic: str) -> List[RoutingSubscription]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM subscriptions WHERE enabled = 1")
        matched = []
        for r in cur.fetchall():
            pattern = r["topic_pattern"]
            if pattern == "*" or pattern == topic or (pattern.endswith(".*") and topic.startswith(pattern[:-2])):
                matched.append(RoutingSubscription(
                    id=r["id"],
                    topic_pattern=pattern,
                    destination_url=r["destination_url"],
                    enabled=bool(r["enabled"]),
                ))
        return matched
