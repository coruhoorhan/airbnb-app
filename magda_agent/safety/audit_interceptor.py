import time
import inspect
import json
import sqlite3
import copy
import re
import threading
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

F = TypeVar('F', bound=Callable[..., Any])

class PreemptiveAuditInterceptor:
    """
    An advanced preemptive interception layer inspired by Falco Prempti.
    Intercepts every action tool execution right before it hits the operating system/code execution engine,
    writing the exact parameters and timestamps into an immutable local audit log (SQLite-backed
    and in-memory append-only).
    """

    SENSITIVE_KEYS = {
        "password", "secret", "key", "token", "auth", "credential",
        "env", "api_key", "access_key", "private", "private_key"
    }

    def __init__(self, db_path: Optional[str] = "preemptive_audit_trail.db") -> None:
        """
        Initializes the PreemptiveAuditInterceptor with a database path.
        """
        self.db_path = db_path
        self.trail: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
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
                    CREATE TABLE IF NOT EXISTS preemptive_audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        tool_name TEXT NOT NULL,
                        kwargs TEXT NOT NULL,
                        why TEXT NOT NULL,
                        status TEXT NOT NULL,
                        result TEXT,
                        duration REAL
                    )
                    '''
                )
                conn.commit()
        except sqlite3.Error as e:
            import logging
            logging.error(f"Failed to initialize SQLite preemptive audit database at {self.db_path}: {e}")

    def _sanitize(self, data: Any, memo: Optional[Dict[int, Any]] = None) -> Any:
        """
        Recursively sanitizes sensitive data from dictionaries and lists.
        Redacts values for keys that match sensitive patterns.
        Handles circular references via a memo dictionary.
        """
        if memo is None:
            memo = {}

        if id(data) in memo:
            return "<circular reference>"

        if inspect.isawaitable(data):
            return "<awaitable>"

        if isinstance(data, dict):
            memo[id(data)] = True
            sanitized = {}
            for k, v in data.items():
                k_lower = k.lower()

                # Check for exact matches or word boundaries to avoid over-redacting
                is_sensitive = False
                for s in self.SENSITIVE_KEYS:
                    if re.search(rf"(^|[^a-zA-Z]){re.escape(s)}s?([^a-zA-Z]|$)", k_lower):
                        is_sensitive = True
                        break

                if is_sensitive:
                    if isinstance(v, dict):
                        sanitized[k] = self._sanitize(v, memo)
                    elif isinstance(v, list):
                        sanitized[k] = ["***" if not isinstance(item, (dict, list)) else self._sanitize(item, memo) for item in v]
                    else:
                        sanitized[k] = "***"
                else:
                    sanitized[k] = self._sanitize(v, memo)
            return sanitized

        elif isinstance(data, list):
            memo[id(data)] = True
            return [self._sanitize(item, memo) for item in data]

        try:
            return copy.deepcopy(data)
        except Exception:
            return repr(data)

    def _extract_args(self, func: Callable[..., Any], args: Any, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts and normalizes arguments passed to a function based on its signature.
        """
        try:
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            return dict(bound.arguments)
        except Exception:
            # Fallback if signature parsing fails
            return {"args": list(args), "kwargs": kwargs}

    def _write_log(
        self,
        tool_name: str,
        kwargs: Dict[str, Any],
        why: str,
        status: str,
        result: Optional[Any] = None,
        duration: Optional[float] = None
    ) -> float:
        """
        Internal thread-safe method to append a log entry. Returns the timestamp.
        """
        timestamp = time.time()
        sanitized_kwargs = self._sanitize(kwargs)
        sanitized_result = self._sanitize(result) if result is not None else None

        entry = {
            "timestamp": timestamp,
            "tool_name": tool_name,
            "kwargs": sanitized_kwargs,
            "why": why,
            "status": status,
            "result": sanitized_result,
            "duration": duration
        }

        with self._lock:
            self.trail.append(entry)

            if self.db_path:
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            '''
                            INSERT INTO preemptive_audit_logs (timestamp, tool_name, kwargs, why, status, result, duration)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''',
                            (
                                timestamp,
                                tool_name,
                                json.dumps(sanitized_kwargs),
                                why,
                                status,
                                json.dumps(sanitized_result) if sanitized_result is not None else None,
                                duration
                            )
                        )
                        conn.commit()
                except sqlite3.Error as e:
                    import logging
                    logging.error(f"Failed to log to SQLite preemptive database at {self.db_path}: {e}")

        return timestamp

    def log_preemptive(self, tool_name: str, kwargs: Dict[str, Any], why: str) -> float:
        """
        Preemptively logs a tool execution *before* hitting the operating system.
        """
        return self._write_log(
            tool_name=tool_name,
            kwargs=kwargs,
            why=why,
            status="preemptive_start"
        )

    def log_completion(self, tool_name: str, kwargs: Dict[str, Any], why: str, result: Any, duration: float) -> float:
        """
        Logs a successful tool execution.
        """
        return self._write_log(
            tool_name=tool_name,
            kwargs=kwargs,
            why=why,
            status="success",
            result=result,
            duration=duration
        )

    def log_failure(self, tool_name: str, kwargs: Dict[str, Any], why: str, error: Exception, duration: float) -> float:
        """
        Logs a failed tool execution.
        """
        return self._write_log(
            tool_name=tool_name,
            kwargs=kwargs,
            why=why,
            status="failed",
            result=str(error),
            duration=duration
        )

    def intercept(self, tool_name: Optional[str] = None, why: str = "intercepted call") -> Callable[[F], F]:
        """
        A decorator that intercepts a tool call preemptively (before execution)
        and logs its lifecycle.
        """
        def decorator(func: F) -> F:
            name_to_use = tool_name if tool_name else func.__name__

            if inspect.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    all_args = self._extract_args(func, args, kwargs)
                    self.log_preemptive(name_to_use, all_args, why)
                    start_time = time.time()
                    try:
                        result = await func(*args, **kwargs)
                        duration = time.time() - start_time
                        self.log_completion(name_to_use, all_args, why, result, duration)
                        return result
                    except Exception as e:
                        duration = time.time() - start_time
                        self.log_failure(name_to_use, all_args, why, e, duration)
                        raise
                return cast(F, async_wrapper)
            else:
                @wraps(func)
                def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    all_args = self._extract_args(func, args, kwargs)
                    self.log_preemptive(name_to_use, all_args, why)
                    start_time = time.time()
                    try:
                        result = func(*args, **kwargs)
                        duration = time.time() - start_time
                        self.log_completion(name_to_use, all_args, why, result, duration)
                        return result
                    except Exception as e:
                        duration = time.time() - start_time
                        self.log_failure(name_to_use, all_args, why, e, duration)
                        raise
                return cast(F, sync_wrapper)

        return decorator

    def execute_sync(self, func: Callable[..., Any], tool_name: str, why: str, *args: Any, **kwargs: Any) -> Any:
        """
        Explicitly executes and intercepts a sync function without decorators.
        """
        all_args = self._extract_args(func, args, kwargs)
        self.log_preemptive(tool_name, all_args, why)
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            self.log_completion(tool_name, all_args, why, result, duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            self.log_failure(tool_name, all_args, why, e, duration)
            raise

    async def execute_async(self, func: Callable[..., Any], tool_name: str, why: str, *args: Any, **kwargs: Any) -> Any:
        """
        Explicitly executes and intercepts an async function without decorators.
        """
        all_args = self._extract_args(func, args, kwargs)
        self.log_preemptive(tool_name, all_args, why)
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            self.log_completion(tool_name, all_args, why, result, duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            self.log_failure(tool_name, all_args, why, e, duration)
            raise

    def query(
        self,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Queries the in-memory audit trail.
        Note: The class does not expose deletion or update methods, ensuring immutability of the log.
        """
        with self._lock:
            results = list(self.trail)

        if tool_name:
            results = [e for e in results if e["tool_name"] == tool_name]
        if status:
            results = [e for e in results if e["status"] == status]
        if start_time is not None:
            results = [e for e in results if e["timestamp"] >= start_time]
        if end_time is not None:
            results = [e for e in results if e["timestamp"] <= end_time]
        return results

    def query_db(
        self,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Queries the SQLite database audit trail.
        """
        if not self.db_path:
            return []

        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                query = "SELECT timestamp, tool_name, kwargs, why, status, result, duration FROM preemptive_audit_logs WHERE 1=1"
                params = []

                if tool_name:
                    query += " AND tool_name = ?"
                    params.append(tool_name)
                if status:
                    query += " AND status = ?"
                    params.append(status)
                if start_time is not None:
                    query += " AND timestamp >= ?"
                    params.append(start_time)
                if end_time is not None:
                    query += " AND timestamp <= ?"
                    params.append(end_time)

                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()

                for row in rows:
                    try:
                        kwargs_dict = json.loads(row[2])
                    except json.JSONDecodeError:
                        kwargs_dict = row[2]

                    try:
                        result_obj = json.loads(row[5]) if row[5] is not None else None
                    except (json.JSONDecodeError, TypeError):
                        result_obj = row[5]

                    results.append({
                        "timestamp": row[0],
                        "tool_name": row[1],
                        "kwargs": kwargs_dict,
                        "why": row[3],
                        "status": row[4],
                        "result": result_obj,
                        "duration": row[6]
                    })
        except sqlite3.Error as e:
            import logging
            logging.error(f"Failed to query SQLite preemptive database at {self.db_path}: {e}")

        return results

    def get_all(self) -> List[Dict[str, Any]]:
        """Returns all entries in the in-memory audit trail."""
        with self._lock:
            return list(self.trail)
