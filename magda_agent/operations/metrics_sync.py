import asyncio
import logging
import json
import sqlite3
from typing import Optional, List, Dict, Any

from magda_agent.telemetry.quality_metrics import LongitudinalQualityMetricsTracker
from magda_agent.channels.hub import ChannelHub

logger = logging.getLogger(__name__)

class MetricsSyncService:
    """
    Sync service that flushes quality tracking SQLite metrics to an external endpoint
    via the Channel Hub periodically. Inspired by Hermes Agent.
    """
    def __init__(self, tracker: LongitudinalQualityMetricsTracker, hub: ChannelHub, channel_id: str = "metrics_endpoint", endpoint_user_id: str = "external_system", sync_interval: float = 60.0):
        self.tracker = tracker
        self.hub = hub
        self.channel_id = channel_id
        self.endpoint_user_id = endpoint_user_id
        self.sync_interval = sync_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Starts the periodic sync loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._sync_loop())

    async def stop(self) -> None:
        """Stops the periodic sync loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _sync_loop(self) -> None:
        """The main loop that flushes metrics periodically."""
        while self._running:
            try:
                await self.flush_metrics()
            except Exception as e:
                logger.error(f"Error during metrics sync: {e}")

            if self.sync_interval <= 0:
                await asyncio.sleep(0)
            else:
                await asyncio.sleep(self.sync_interval)

    def _get_all_metrics(self) -> List[Dict[str, Any]]:
        """Fetch all metrics directly from the tracker's database."""
        conn = self.tracker._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Fetch recent 100 metrics across all names for sync to avoid huge payload
            cursor.execute(
                '''
                SELECT id, metric_name, metric_value, metadata, timestamp
                FROM metrics
                ORDER BY timestamp DESC
                LIMIT 100
                '''
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
                    "id": row['id'],
                    "metric_name": row['metric_name'],
                    "metric_value": row['metric_value'],
                    "metadata": metadata_dict,
                    "timestamp": row['timestamp']
                })
            return results
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch metrics for sync: {e}")
            return []
        finally:
            # Need to carefully close if not in-memory
            if self.tracker._mem_conn is None:
                conn.close()

    async def flush_metrics(self) -> None:
        """
        Reads metrics from the tracker, formats them securely, and sends them
        via the Channel Hub.
        """
        metrics = self._get_all_metrics()
        if not metrics:
            logger.debug("No metrics to sync.")
            return

        payload = {
            "type": "quality_metrics_sync",
            "count": len(metrics),
            "metrics": metrics
        }

        payload_str = json.dumps(payload)

        await self.hub.send_to_channel(
            channel_id=self.channel_id,
            recipient_id=self.endpoint_user_id,
            text=payload_str,
            metadata={"source": "MetricsSyncService"}
        )
        logger.info(f"Successfully synced {len(metrics)} metrics.")
