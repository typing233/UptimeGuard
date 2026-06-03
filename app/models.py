from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .database import Base


class Monitor(Base):
    __tablename__ = "monitors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    monitor_type = Column(String(10), nullable=False)  # http, tcp, icmp
    target = Column(String(500), nullable=False)
    interval = Column(Integer, nullable=False, default=60)  # seconds
    timeout = Column(Integer, nullable=False, default=10)  # seconds
    # HTTP specific
    expected_status = Column(Integer, default=200)
    keyword = Column(String(500), default=None)
    http_method = Column(String(10), default="GET")
    # TCP specific
    port = Column(Integer, default=None)
    # State
    active = Column(Boolean, default=True)
    status = Column(String(10), default="pending")  # up, down, pending
    last_check = Column(DateTime, default=None)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    results = relationship("CheckResult", back_populates="monitor", cascade="all, delete-orphan")
    alert_policy = relationship("AlertPolicy", back_populates="monitor", uselist=False, cascade="all, delete-orphan")
    status_page_items = relationship("StatusPageItem", back_populates="monitor", cascade="all, delete-orphan")


class CheckResult(Base):
    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = Column(String(10), nullable=False)  # up, down
    latency = Column(Float, default=None)  # milliseconds
    error = Column(Text, default=None)

    monitor = relationship("Monitor", back_populates="results")


class AlertChannel(Base):
    __tablename__ = "alert_channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    channel_type = Column(String(20), nullable=False)  # email, webhook, dingtalk, feishu, wecom
    config = Column(JSON, nullable=False)  # type-specific config
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AlertPolicy(Base):
    __tablename__ = "alert_policies"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=False, unique=True)
    failure_threshold = Column(Integer, default=3)
    recovery_notify = Column(Boolean, default=True)
    channel_ids = Column(JSON, default=list)  # list of alert channel IDs
    silence_start = Column(String(5), default=None)  # HH:MM
    silence_end = Column(String(5), default=None)  # HH:MM
    repeat_interval = Column(Integer, default=0)  # minutes, 0 = no repeat
    # Runtime state
    consecutive_failures = Column(Integer, default=0)
    last_alert_time = Column(DateTime, default=None)
    alerted = Column(Boolean, default=False)

    monitor = relationship("Monitor", back_populates="alert_policy")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, default=None)
    error = Column(Text, default=None)


class StatusPage(Base):
    __tablename__ = "status_pages"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, default="Service Status")
    slug = Column(String(100), nullable=False, unique=True)
    logo_url = Column(String(500), default=None)
    custom_css = Column(Text, default=None)
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    items = relationship("StatusPageItem", back_populates="status_page", cascade="all, delete-orphan")


class StatusPageItem(Base):
    __tablename__ = "status_page_items"

    id = Column(Integer, primary_key=True, index=True)
    status_page_id = Column(Integer, ForeignKey("status_pages.id"), nullable=False)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=False)
    group_name = Column(String(200), default="Default")
    sort_order = Column(Integer, default=0)

    status_page = relationship("StatusPage", back_populates="items")
    monitor = relationship("Monitor", back_populates="status_page_items")
