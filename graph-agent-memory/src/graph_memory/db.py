"""
FalkorDB database client, connection management, query execution, and schema initialization.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from falkordb import FalkorDB, Graph
import redis.exceptions

from graph_memory.config import settings

logger = logging.getLogger(__name__)


class FalkorDBClient:
    """Manages connection and query execution to FalkorDB."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        graph_name: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.host = host or settings.falkordb_host
        self.port = port or settings.falkordb_port
        self.graph_name = graph_name or settings.falkordb_graph_name
        self.username = username or settings.falkordb_username
        self.password = password or settings.falkordb_password
        self._client: Optional[FalkorDB] = None
        self._graph: Optional[Graph] = None

    @property
    def client(self) -> FalkorDB:
        if self._client is None:
            connect_kwargs: Dict[str, Any] = {
                "host": self.host,
                "port": self.port,
            }
            if self.username and self.username.strip():
                connect_kwargs["username"] = self.username.strip()
            if self.password and self.password.strip():
                connect_kwargs["password"] = self.password.strip()
            self._client = FalkorDB(**connect_kwargs)
        return self._client

    @property
    def graph(self) -> Graph:
        if self._graph is None:
            self._graph = self.client.select_graph(self.graph_name)
        return self._graph

    def check_health(self) -> Dict[str, Any]:
        """Pings FalkorDB and executes a heartbeat query."""
        try:
            # Check Redis-level ping
            self.client.connection.ping()
            # Check Graph-level query
            res = self.graph.query("RETURN 1 AS ping")
            return {
                "status": "healthy",
                "host": self.host,
                "port": self.port,
                "graph_name": self.graph_name,
                "ping_result": res.result_set[0][0] if res.result_set else None,
            }
        except Exception as e:
            logger.error("FalkorDB healthcheck failed: %s", e)
            return {
                "status": "unhealthy",
                "host": self.host,
                "port": self.port,
                "graph_name": self.graph_name,
                "error": str(e),
            }

    def query(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
        read_only: bool = False,
    ) -> Any:
        """
        Executes a parameterized Cypher query on the selected graph.
        """
        query_params = params or {}
        try:
            if read_only:
                return self.graph.ro_query(cypher, query_params)
            return self.graph.query(cypher, query_params)
        except Exception as e:
            logger.error(
                "Cypher execution failed: query=%s, params=%s, error=%s",
                cypher,
                query_params,
                e,
            )
            raise

    def init_schema(self, schema_file_path: Optional[str] = None) -> List[str]:
        """
        Reads schema statements from a .cypher file and creates indexes idempotently.
        """
        if schema_file_path:
            schema_path = Path(schema_file_path)
        else:
            # Default to config/graph-schema.cypher relative to repo root
            schema_path = Path(__file__).resolve().parent.parent.parent / "config" / "graph-schema.cypher"

        if not schema_path.exists():
            logger.warning("Schema file not found at %s. Applying fallback schema.", schema_path)
            statements = [
                "CREATE INDEX FOR (w:Workspace) ON (w.id)",
                "CREATE INDEX FOR (d:Developer) ON (d.id)",
                "CREATE INDEX FOR (a:Agent) ON (a.id)",
                "CREATE INDEX FOR (s:Session) ON (s.id)",
                "CREATE INDEX FOR (s:Session) ON (s.workspace_id)",
                "CREATE INDEX FOR (m:Memory) ON (m.id)",
                "CREATE INDEX FOR (m:Memory) ON (m.workspace_id)",
                "CREATE INDEX FOR (m:Memory) ON (m.status)",
                "CREATE INDEX FOR (m:Memory) ON (m.memory_type)",
                "CREATE INDEX FOR (dec:Decision) ON (dec.id)",
                "CREATE INDEX FOR (dec:Decision) ON (dec.workspace_id)",
                "CREATE INDEX FOR (dec:Decision) ON (dec.status)",
                "CREATE INDEX FOR (e:Entity) ON (e.id)",
                "CREATE INDEX FOR (e:Entity) ON (e.workspace_id)",
                "CREATE INDEX FOR (e:Entity) ON (e.name)",
                "CREATE INDEX FOR (t:Task) ON (t.id)",
                "CREATE INDEX FOR (t:Task) ON (t.workspace_id)",
                "CREATE INDEX FOR (ev:Evidence) ON (ev.id)",
            ]
        else:
            content = schema_path.read_text(encoding="utf-8")
            # Parse statements split by semicolon or newlines, ignoring comments
            statements = []
            for line in content.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("//") and not stripped.startswith("#"):
                    stmt = stripped.rstrip(";")
                    statements.append(stmt)

        results = []
        for stmt in statements:
            try:
                self.graph.query(stmt)
                results.append(f"SUCCESS: {stmt}")
                logger.info("Executed schema statement: %s", stmt)
            except redis.exceptions.ResponseError as err:
                msg = str(err).lower()
                if "already indexed" in msg or "already exists" in msg:
                    results.append(f"SKIPPED (already exists): {stmt}")
                    logger.debug("Index already exists: %s", stmt)
                else:
                    logger.error("Schema execution error on '%s': %s", stmt, err)
                    raise
            except Exception as e:
                logger.error("Unexpected schema execution error on '%s': %s", stmt, e)
                raise

        return results

    def close(self) -> None:
        """Closes connection client if open."""
        if self._client is not None:
            try:
                self._client.connection.close()
            except Exception:
                pass
            self._client = None
            self._graph = None


# Module-level default client
_default_client: Optional[FalkorDBClient] = None


def get_db() -> FalkorDBClient:
    """Returns the singleton FalkorDBClient instance."""
    global _default_client
    if _default_client is None:
        _default_client = FalkorDBClient()
    return _default_client


def cli_init_schema() -> None:
    """CLI utility function to initialize the schema."""
    client = get_db()
    health = client.check_health()
    if health.get("status") != "healthy":
        print(f"Error: FalkorDB is not healthy: {health}")
        exit(1)
    results = client.init_schema()
    for res in results:
        print(res)
    print("Schema initialization complete.")


if __name__ == "__main__":
    cli_init_schema()
