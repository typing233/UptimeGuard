from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MonitorCreate(BaseModel):
    name: str
    monitor_type: str  # http, tcp, icmp
    target: str
    interval: int = 60
    timeout: int = 10
    keyword: Optional[str] = None
    expected_status_code: Optional[int] = 200
    port: Optional[int] = None
    active: bool = True


class MonitorUpdate(BaseModel):
    name: Optional[str] = None
    monitor_type: Optional[str] = None
    target: Optional[str] = None
    interval: Optional[int] = None
    timeout: Optional[int] = None
    keyword: Optional[str] = None
    expected_status_code: Optional[int] = None
    port: Optional[int] = None
    active: Optional[bool] = None


class MonitorResponse(BaseModel):
    id: int
    name: str
    monitor_type: str
    target: str
    interval: int
    timeout: int
    keyword: Optional[str]
    expected_status_code: Optional[int]
    port: Optional[int]
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CheckResultResponse(BaseModel):
    id: int
    monitor_id: int
    timestamp: datetime
    status: str
    latency: Optional[float]
    error: Optional[str]
    status_code: Optional[int]

    class Config:
        from_attributes = True
