from pydantic import BaseModel, Field
from typing import Optional

#VALIDATE DATA FOR SCAN REQUESTS
class ScanRequest(BaseModel):
    data_type: str = Field(..., example="username")
    search_data: str = Field(..., example="jack")
    custom_regex: Optional[str] = None

class ScanResponse(BaseModel):
    scan_id: int
    message: str = "Scan started successfully."
