from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import enum

DATABASE_URL = "sqlite:///./uptimeguard.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class MonitorType(str, enum.Enum):
    HTTP = "http"
    TCP = "tcp"
    ICMP = "icmp"


class CheckInterval(int, enum.Enum):
    THIRTY_SECONDS = 30
    ONE_MINUTE = 60
    FIVE_MINUTES = 300


class Monitor(Base):
    __tablename__ = "monitors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    monitor_type = Column(String, nullable=False)
    target = Column(String, nullable=False)
    interval = Column(Integer, nullable=False, default=60)
    timeout = Column(Integer, nullable=False, default=10)
    keyword = Column(String, nullable=True)
    expected_status_code = Column(Integer, nullable=True, default=200)
    port = Column(Integer, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CheckResult(Base):
    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String, nullable=False)  # "up" or "down"
    latency = Column(Float, nullable=True)  # milliseconds
    error = Column(String, nullable=True)
    status_code = Column(Integer, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
