from pydantic import BaseModel, Field
from typing import Optional

#VALIDATE DATA FOR SCAN REQUESTS
class ScanRequest(BaseModel):
    data_type: str = Field(..., example="email")
    search_data: str = Field(..., example="user@example.com")
    custom_regex: Optional[str] = Field(None, example=r"\b\d{12}\b")  # For IC, etc.

class ScanResponse(BaseModel):
    scan_id: int
    message: str = "Scan started successfully."
