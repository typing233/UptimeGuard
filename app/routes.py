from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db, Monitor, CheckResult
from app.schemas import MonitorCreate, MonitorUpdate, MonitorResponse, CheckResultResponse
from app.scheduler import schedule_monitor, unschedule_monitor
from app.checker import run_check

router = APIRouter(prefix="/api")


@router.get("/monitors", response_model=List[MonitorResponse])
def list_monitors(db: Session = Depends(get_db)):
    return db.query(Monitor).order_by(Monitor.id).all()


@router.get("/monitors/{monitor_id}", response_model=MonitorResponse)
def get_monitor(monitor_id: int, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor


@router.post("/monitors", response_model=MonitorResponse)
async def create_monitor(data: MonitorCreate, db: Session = Depends(get_db)):
    monitor = Monitor(**data.model_dump())
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    if monitor.active:
        await schedule_monitor(monitor.id, monitor.interval)
    return monitor


@router.put("/monitors/{monitor_id}", response_model=MonitorResponse)
async def update_monitor(monitor_id: int, data: MonitorUpdate, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(monitor, key, value)

    monitor.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(monitor)

    if monitor.active:
        await schedule_monitor(monitor.id, monitor.interval)
    else:
        await unschedule_monitor(monitor.id)

    return monitor


@router.delete("/monitors/{monitor_id}")
async def delete_monitor(monitor_id: int, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    await unschedule_monitor(monitor_id)
    db.query(CheckResult).filter(CheckResult.monitor_id == monitor_id).delete()
    db.delete(monitor)
    db.commit()
    return {"message": "Monitor deleted"}


@router.post("/monitors/{monitor_id}/check")
async def trigger_check(monitor_id: int, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    await run_check(monitor_id)
    return {"message": "Check triggered"}


@router.get("/monitors/{monitor_id}/results", response_model=List[CheckResultResponse])
def get_results(
    monitor_id: int,
    limit: int = Query(default=100, le=1000),
    hours: Optional[int] = Query(default=24),
    db: Session = Depends(get_db),
):
    query = db.query(CheckResult).filter(CheckResult.monitor_id == monitor_id)
    if hours:
        since = datetime.utcnow() - timedelta(hours=hours)
        query = query.filter(CheckResult.timestamp >= since)
    return query.order_by(desc(CheckResult.timestamp)).limit(limit).all()


@router.get("/status")
def get_status_summary(db: Session = Depends(get_db)):
    monitors = db.query(Monitor).all()
    summary = []
    for monitor in monitors:
        last_check = (
            db.query(CheckResult)
            .filter(CheckResult.monitor_id == monitor.id)
            .order_by(desc(CheckResult.timestamp))
            .first()
        )
        summary.append({
            "id": monitor.id,
            "name": monitor.name,
            "monitor_type": monitor.monitor_type,
            "target": monitor.target,
            "interval": monitor.interval,
            "active": monitor.active,
            "last_status": last_check.status if last_check else None,
            "last_latency": last_check.latency if last_check else None,
            "last_check_time": last_check.timestamp.isoformat() if last_check else None,
            "last_error": last_check.error if last_check else None,
        })
    return summary
