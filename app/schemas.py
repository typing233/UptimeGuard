from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class MonitorCreate(BaseModel):
    name: str
    monitor_type: str  # http, tcp, icmp
    target: str
    interval: int = 60
    timeout: int = 10
    expected_status: int = 200
    keyword: Optional[str] = None
    http_method: str = "GET"
    port: Optional[int] = None
    active: bool = True


class MonitorUpdate(BaseModel):
    name: Optional[str] = None
    target: Optional[str] = None
    interval: Optional[int] = None
    timeout: Optional[int] = None
    expected_status: Optional[int] = None
    keyword: Optional[str] = None
    http_method: Optional[str] = None
    port: Optional[int] = None
    active: Optional[bool] = None


class MonitorResponse(BaseModel):
    id: int
    name: str
    monitor_type: str
    target: str
    interval: int
    timeout: int
    expected_status: Optional[int]
    keyword: Optional[str]
    http_method: Optional[str]
    port: Optional[int]
    active: bool
    status: str
    last_check: Optional[datetime]

    class Config:
        from_attributes = True


class CheckResultResponse(BaseModel):
    id: int
    monitor_id: int
    timestamp: datetime
    status: str
    latency: Optional[float]
    error: Optional[str]

    class Config:
        from_attributes = True


class AlertChannelCreate(BaseModel):
    name: str
    channel_type: str  # email, webhook, dingtalk, feishu, wecom
    config: dict
    enabled: bool = True


class AlertChannelResponse(BaseModel):
    id: int
    name: str
    channel_type: str
    config: dict
    enabled: bool

    class Config:
        from_attributes = True


class AlertPolicyCreate(BaseModel):
    monitor_id: int
    failure_threshold: int = 3
    recovery_notify: bool = True
    channel_ids: list[int] = []
    silence_start: Optional[str] = None
    silence_end: Optional[str] = None
    repeat_interval: int = 0


class AlertPolicyResponse(BaseModel):
    id: int
    monitor_id: int
    failure_threshold: int
    recovery_notify: bool
    channel_ids: list
    silence_start: Optional[str]
    silence_end: Optional[str]
    repeat_interval: int
    consecutive_failures: int
    alerted: bool

    class Config:
        from_attributes = True


class StatusPageCreate(BaseModel):
    title: str = "Service Status"
    slug: str
    logo_url: Optional[str] = None
    custom_css: Optional[str] = None
    is_public: bool = True


class StatusPageUpdate(BaseModel):
    title: Optional[str] = None
    logo_url: Optional[str] = None
    custom_css: Optional[str] = None
    is_public: Optional[bool] = None


class StatusPageItemCreate(BaseModel):
    monitor_id: int
    group_name: str = "Default"
    sort_order: int = 0


class IncidentResponse(BaseModel):
    id: int
    monitor_id: int
    started_at: datetime
    resolved_at: Optional[datetime]
    error: Optional[str]

    class Config:
        from_attributes = True
