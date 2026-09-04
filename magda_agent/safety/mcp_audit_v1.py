import json
import logging
import sqlite3
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

class MCPAuditTrailV1:
    """
    Records and queries MCP specific tool invocations to track tool usage frequency and execution results.
    Includes in-memory buffering and optional SQLite persistence.
    """

    def __init__(self, max_capacity: int = 1000, db_path: Optional[str] = "mcp_audit_trail_v1.db") -> None:
        """
        Initializes the MCPAuditTrailV1 with a fixed capacity and an SQLite database for persistence.

        Args:
            max_capacity: Maximum number of entries to keep in the in-memory trail.
            db_path: Path to the SQLite database file. If None, only in-memory logging is used.
        """
        self.max_capacity = max_capacity
        self.trail: Deque[Dict[str, Any]] = deque(maxlen=max_capacity)
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initializes the SQLite database schema if a path is provided."""
        if not self.db_path:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    CREATE TABLE IF NOT EXISTS mcp_audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        server_name TEXT NOT NULL,
                        tool_name TEXT NOT NULL,
                        arguments TEXT NOT NULL,
                        result TEXT NOT NULL,
                        duration REAL NOT NULL,
                        status TEXT NOT NULL
                    )
                    '''
                )
                conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Failed to initialize SQLite mcp audit database at {self.db_path}: {e}")

    async def log_mcp_invocation(self, server_name: str, tool_name: str, arguments: Dict[str, Any], result: Any, duration: float, status: str = "success") -> None:
        """
        Logs an MCP tool invocation.

        Args:
            server_name: The name of the MCP server.
            tool_name: The name of the executed tool.
            arguments: The arguments passed to the tool.
            result: The outcome of the execution.
            duration: Time taken in seconds.
            status: The status of the invocation (e.g. "success", "error").
        """
        timestamp = time.time()

        # Simple sanitization or just deepcopying could be done here similar to standard audit.
        # Assuming arguments and results are JSON serializable.

        entry = {
            "timestamp": timestamp,
            "server_name": server_name,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "duration": duration,
            "status": status
        }

        self.trail.append(entry)

        if self.db_path:
            import asyncio
            def _log():
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            '''
                            INSERT INTO mcp_audit_logs (timestamp, server_name, tool_name, arguments, result, duration, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''',
                            (
                                timestamp,
                                server_name,
                                tool_name,
                                json.dumps(arguments),
                                json.dumps(result) if not isinstance(result, str) else result,
                                duration,
                                status
                            )
                        )
                        conn.commit()
                except sqlite3.Error as e:
                    logging.error(f"Failed to log to SQLite mcp audit database at {self.db_path}: {e}")
            await asyncio.to_thread(_log)

    def get_mcp_logs(self, server_name: Optional[str] = None, tool_name: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Queries the audit logs from the SQLite database.

        Args:
            server_name: Filter by MCP server name.
            tool_name: Filter by tool name.
            status: Filter by execution status.

        Returns:
            A list of matching audit log entries.
        """
        if not self.db_path:
            results = list(self.trail)
            if server_name:
                results = [r for r in results if r["server_name"] == server_name]
            if tool_name:
                results = [r for r in results if r["tool_name"] == tool_name]
            if status:
                results = [r for r in results if r["status"] == status]
            return results

        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                query = "SELECT timestamp, server_name, tool_name, arguments, result, duration, status FROM mcp_audit_logs WHERE 1=1"
                params = []

                if server_name:
                    query += " AND server_name = ?"
                    params.append(server_name)
                if tool_name:
                    query += " AND tool_name = ?"
                    params.append(tool_name)
                if status:
                    query += " AND status = ?"
                    params.append(status)

                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()

                for row in rows:
                    try:
                        args_dict = json.loads(row[3])
                    except json.JSONDecodeError:
                        args_dict = row[3]

                    try:
                        res_obj = json.loads(row[4])
                    except (json.JSONDecodeError, TypeError):
                        res_obj = row[4]

                    results.append({
                        "timestamp": row[0],
                        "server_name": row[1],
                        "tool_name": row[2],
                        "arguments": args_dict,
                        "result": res_obj,
                        "duration": row[5],
                        "status": row[6]
                    })
        except sqlite3.Error as e:
            logging.error(f"Failed to query SQLite mcp audit database at {self.db_path}: {e}")

        return results

    def clear(self) -> None:
        """Clears all entries from the in-memory trail and the SQLite database."""
        self.trail.clear()

        if self.db_path:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM mcp_audit_logs")
                    conn.commit()
            except sqlite3.Error as e:
                logging.error(f"Failed to clear SQLite mcp audit database at {self.db_path}: {e}")
