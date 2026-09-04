import sqlite3
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LongitudinalQualityMetricsTracker:
    """
    A class for tracking longitudinal quality metrics in an SQLite database.
    This allows continuous improvement by storing metrics over time.
    """

    def __init__(self, db_path: str = "quality_metrics.db"):
        """
        Initialize the LongitudinalQualityMetricsTracker.

        Args:
            db_path (str): The path to the SQLite database file.
        """
        self.db_path = db_path

        # When using :memory:, the connection is closed immediately in _initialize_db,
        # which destroys the in-memory database. We must keep the connection open for :memory:.
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            self._mem_conn = None

        self._initialize_db()

    def _get_connection(self):
        """Get an active SQLite connection."""
        if self._mem_conn is not None:
            return self._mem_conn
        return sqlite3.connect(self.db_path)

    def _initialize_db(self) -> None:
        """
        Initialize the database schema if it doesn't exist.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metadata TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize SQLite database at {self.db_path}: {e}")
            raise
        finally:
            if self._mem_conn is None:
                conn.close()

    def record_metric(self, metric_name: str, metric_value: float, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a quality metric.

        Args:
            metric_name (str): The name of the metric to record (e.g., 'success_rate').
            metric_value (float): The numeric value of the metric.
            metadata (Optional[Dict[str, Any]]): Additional metadata to store with the metric as JSON.
        """
        metadata_str = json.dumps(metadata) if metadata else None

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO metrics (metric_name, metric_value, metadata)
                VALUES (?, ?, ?)
                ''',
                (metric_name, metric_value, metadata_str)
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to record metric '{metric_name}': {e}")
            raise
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_metrics_history(self, metric_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve the history of a specific metric.

        Args:
            metric_name (str): The name of the metric to retrieve.
            limit (int): The maximum number of recent records to retrieve.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing metric data.
        """
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT metric_name, metric_value, metadata, timestamp
                FROM metrics
                WHERE metric_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
                ''',
                (metric_name, limit)
            )
            rows = cursor.fetchall()

            results = []
            for row in rows:
                metadata_dict = None
                if row['metadata']:
                    try:
                        metadata_dict = json.loads(row['metadata'])
                    except json.JSONDecodeError:
                        metadata_dict = {}

                results.append({
                    "metric_name": row['metric_name'],
                    "metric_value": row['metric_value'],
                    "metadata": metadata_dict,
                    "timestamp": row['timestamp']
                })
            return results
        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve metric history for '{metric_name}': {e}")
            return []
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_average_metric(self, metric_name: str) -> Optional[float]:
        """
        Calculate the average value of a specific metric over its entire history.

        Args:
            metric_name (str): The name of the metric to average.

        Returns:
            Optional[float]: The average value, or None if no records exist.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT AVG(metric_value)
                FROM metrics
                WHERE metric_name = ?
                ''',
                (metric_name,)
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else None
        except sqlite3.Error as e:
            logger.error(f"Failed to calculate average for metric '{metric_name}': {e}")
            return None
        finally:
            if self._mem_conn is None:
                conn.close()
