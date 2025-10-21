from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Dict, Any, List

# This defines the structure for a single tool's result
class ToolResult(BaseModel):
    type: str
    data: Any
    confidence: float | None = None
    severity: str
    source: str | None = None

# This is the main response model for a single scan job in the history
class ScanHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_id: int
    scan_source: str  # The crucial field we are adding
    data_type: str
    search_data: str
    timestamp: datetime
    status: str
    results: Dict[str, ToolResult]