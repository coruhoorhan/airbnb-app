import sqlite3
import datetime
from typing import Dict, Any, List, Optional

class LongitudinalMetricsTracker:
    """
    Tracks and persists code quality metrics and skill performance metrics over time.
    """
    def __init__(self, db_path: str = "./longitudinal_metrics_db.sqlite3"):
        self.db_path = db_path
        # If it's an in-memory DB, we must keep the connection open to retain data
        self._memory_conn = sqlite3.connect(':memory:') if self.db_path == ':memory:' else None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._memory_conn:
            return self._memory_conn
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        """Initializes the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS code_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skill_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_name TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    def record_metric(self, metric_name: str, value: float) -> None:
        """
        Records a single metric value.

        Args:
            metric_name (str): The name of the metric (e.g., 'test_coverage', 'complexity').
            value (float): The value of the metric.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO code_metrics (metric_name, value, timestamp) VALUES (?, ?, ?)",
                (metric_name, value, timestamp)
            )
            conn.commit()

    def get_metrics_history(self, metric_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieves the history of a specific metric.

        Args:
            metric_name (str): The name of the metric.
            limit (int): The maximum number of historical records to fetch.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing metric history.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value, timestamp FROM code_metrics WHERE metric_name = ? ORDER BY timestamp DESC LIMIT ?",
                (metric_name, limit)
            )
            rows = cursor.fetchall()

        return [{"value": row[0], "timestamp": row[1]} for row in rows]

    def record_skill_result(self, skill_name: str, success: bool) -> None:
        """
        Records a success/failure event for a specific skill.

        Args:
            skill_name (str): The name of the skill.
            success (bool): True if the skill succeeded, False otherwise.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO skill_events (skill_name, success, timestamp) VALUES (?, ?, ?)",
                (skill_name, 1 if success else 0, timestamp)
            )
            conn.commit()

    def get_skill_success_rate(self, skill_name: str) -> Optional[float]:
        """
        Calculates and returns the historical success rate for a specific skill.

        Args:
            skill_name (str): The name of the skill.

        Returns:
            Optional[float]: The success rate (between 0.0 and 1.0), or None if no entries exist.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT AVG(success) FROM skill_events WHERE skill_name = ?",
                (skill_name,)
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                return float(row[0])
        return None

    def get_all_skills_success_rates(self) -> Dict[str, float]:
        """
        Aggregates and retrieves historical success rates for all recorded skills.

        Returns:
            Dict[str, float]: A dictionary mapping skill names to their success rate (0.0 to 1.0).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT skill_name, AVG(success) FROM skill_events GROUP BY skill_name"
            )
            rows = cursor.fetchall()
        return {row[0]: float(row[1]) for row in rows}
