"""Base connector interface for all external data source connectors"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC,datetime
from typing import Any

import structlog

log=structlog.get_logger()

@dataclass
class SyncResult:
    source_type: str
    records_fetched: int = 0
    records_created: int = 0
    records_updated: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    success: bool = True

    def finish(self) -> None:
        self.completed_at = datetime.now(UTC)

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class BaseConnector(ABC):
    """Abstract base class for all data source connectors."""
    source_type: str = "base"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config=config
        self.log=structlog.get_logger().bind(connector=self.source_type)

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test that the connector credentials and connectivity are valid"""
        ...
    
    @abstractmethod
    async def sync(self, workspace_id: str, since: datetime | None = None) -> SyncResult:
        """Ingest data from the external source.
        
        Args:
            workspace_id: The workspace to associate data with.
            since: If set, only fetch records updated after this timestamp (incremental).

        Returns:
            SyncResult with counts and errors.
        """
        ...

    @abstractmethod
    async def fetch_raw(self, since: datetime | None=None)-> list[dict[str, Any]]:
        """Fetch raw records from the source (no D8 writes)."""
        ...
    
    def _get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)
    