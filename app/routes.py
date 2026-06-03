from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime, timezone, timedelta
from .database import get_db
from .models import Monitor, CheckResult, AlertChannel, AlertPolicy, StatusPage, StatusPageItem, Incident
from .schemas import (
    MonitorCreate, MonitorUpdate, MonitorResponse,
    CheckResultResponse, AlertChannelCreate, AlertChannelResponse,
    AlertPolicyCreate, AlertPolicyResponse,
    StatusPageCreate, StatusPageUpdate, StatusPageItemCreate, IncidentResponse
)
from .scheduler import schedule_monitor, unschedule_monitor, execute_check

router = APIRouter(prefix="/api")


# --- Monitors ---

@router.get("/monitors", response_model=list[MonitorResponse])
async def list_monitors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Monitor).order_by(Monitor.id))
    return result.scalars().all()


@router.post("/monitors", response_model=MonitorResponse)
async def create_monitor(data: MonitorCreate, db: AsyncSession = Depends(get_db)):
    monitor = Monitor(**data.model_dump())
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    if monitor.active:
        schedule_monitor(monitor.id, monitor.interval)
    return monitor


@router.get("/monitors/{monitor_id}", response_model=MonitorResponse)
async def get_monitor(monitor_id: int, db: AsyncSession = Depends(get_db)):
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor


@router.put("/monitors/{monitor_id}", response_model=MonitorResponse)
async def update_monitor(monitor_id: int, data: MonitorUpdate, db: AsyncSession = Depends(get_db)):
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(monitor, key, value)
    await db.commit()
    await db.refresh(monitor)
    if monitor.active:
        schedule_monitor(monitor.id, monitor.interval)
    else:
        unschedule_monitor(monitor.id)
    return monitor


@router.delete("/monitors/{monitor_id}")
async def delete_monitor(monitor_id: int, db: AsyncSession = Depends(get_db)):
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    unschedule_monitor(monitor_id)
    await db.delete(monitor)
    await db.commit()
    return {"detail": "Deleted"}


@router.post("/monitors/{monitor_id}/check")
async def trigger_check(monitor_id: int, db: AsyncSession = Depends(get_db)):
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    result = await execute_check(monitor_id)
    if result is None:
        raise HTTPException(status_code=500, detail="Check execution failed")
    return result


# --- Check Results ---

@router.get("/monitors/{monitor_id}/results", response_model=list[CheckResultResponse])
async def get_results(monitor_id: int, limit: int = 100, db: AsyncSession = Depends(get_db)):
    stmt = (select(CheckResult)
            .where(CheckResult.monitor_id == monitor_id)
            .order_by(desc(CheckResult.timestamp))
            .limit(limit))
    result = await db.execute(stmt)
    return result.scalars().all()


# --- Alert Channels ---

@router.get("/alert-channels", response_model=list[AlertChannelResponse])
async def list_channels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AlertChannel))
    return result.scalars().all()


@router.post("/alert-channels", response_model=AlertChannelResponse)
async def create_channel(data: AlertChannelCreate, db: AsyncSession = Depends(get_db)):
    channel = AlertChannel(**data.model_dump())
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.put("/alert-channels/{channel_id}", response_model=AlertChannelResponse)
async def update_channel(channel_id: int, data: AlertChannelCreate, db: AsyncSession = Depends(get_db)):
    channel = await db.get(AlertChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    for key, value in data.model_dump().items():
        setattr(channel, key, value)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.delete("/alert-channels/{channel_id}")
async def delete_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
    channel = await db.get(AlertChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.delete(channel)
    await db.commit()
    return {"detail": "Deleted"}


# --- Alert Policies ---

@router.get("/alert-policies/{monitor_id}", response_model=AlertPolicyResponse)
async def get_policy(monitor_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(AlertPolicy).where(AlertPolicy.monitor_id == monitor_id)
    result = await db.execute(stmt)
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.post("/alert-policies", response_model=AlertPolicyResponse)
async def create_policy(data: AlertPolicyCreate, db: AsyncSession = Depends(get_db)):
    stmt = select(AlertPolicy).where(AlertPolicy.monitor_id == data.monitor_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        for key, value in data.model_dump().items():
            setattr(existing, key, value)
        await db.commit()
        await db.refresh(existing)
        return existing
    policy = AlertPolicy(**data.model_dump())
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.delete("/alert-policies/{monitor_id}")
async def delete_policy(monitor_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(AlertPolicy).where(AlertPolicy.monitor_id == monitor_id)
    result = await db.execute(stmt)
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    await db.delete(policy)
    await db.commit()
    return {"detail": "Deleted"}


# --- Status Pages ---

@router.get("/status-pages")
async def list_status_pages(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StatusPage))
    pages = result.scalars().all()
    response = []
    for page in pages:
        stmt = select(StatusPageItem).where(StatusPageItem.status_page_id == page.id).order_by(StatusPageItem.sort_order)
        items_result = await db.execute(stmt)
        items = items_result.scalars().all()
        response.append({
            "id": page.id,
            "title": page.title,
            "slug": page.slug,
            "logo_url": page.logo_url,
            "is_public": page.is_public,
            "items": [{"id": it.id, "monitor_id": it.monitor_id, "group_name": it.group_name, "sort_order": it.sort_order} for it in items],
        })
    return response


@router.post("/status-pages")
async def create_status_page(data: StatusPageCreate, db: AsyncSession = Depends(get_db)):
    page = StatusPage(**data.model_dump())
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


@router.put("/status-pages/{page_id}")
async def update_status_page(page_id: int, data: StatusPageUpdate, db: AsyncSession = Depends(get_db)):
    page = await db.get(StatusPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Status page not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(page, key, value)
    await db.commit()
    await db.refresh(page)
    return page


@router.delete("/status-pages/{page_id}")
async def delete_status_page(page_id: int, db: AsyncSession = Depends(get_db)):
    page = await db.get(StatusPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Status page not found")
    await db.delete(page)
    await db.commit()
    return {"detail": "Deleted"}


@router.post("/status-pages/{page_id}/items")
async def add_status_page_item(page_id: int, data: StatusPageItemCreate, db: AsyncSession = Depends(get_db)):
    page = await db.get(StatusPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Status page not found")
    item = StatusPageItem(status_page_id=page_id, **data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/status-pages/{page_id}/items/{item_id}")
async def remove_status_page_item(page_id: int, item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(StatusPageItem, item_id)
    if not item or item.status_page_id != page_id:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()
    return {"detail": "Deleted"}


@router.put("/status-pages/{page_id}/items")
async def replace_status_page_items(page_id: int, items: list[StatusPageItemCreate], db: AsyncSession = Depends(get_db)):
    page = await db.get(StatusPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Status page not found")
    stmt = select(StatusPageItem).where(StatusPageItem.status_page_id == page_id)
    existing = await db.execute(stmt)
    for old_item in existing.scalars().all():
        await db.delete(old_item)
    for i, item_data in enumerate(items):
        new_item = StatusPageItem(
            status_page_id=page_id,
            monitor_id=item_data.monitor_id,
            group_name=item_data.group_name,
            sort_order=item_data.sort_order if item_data.sort_order else i,
        )
        db.add(new_item)
    await db.commit()
    return {"detail": "Items updated"}


# --- Public Status Page Data ---

@router.get("/status/{slug}")
async def public_status_page(slug: str, db: AsyncSession = Depends(get_db)):
    stmt = select(StatusPage).where(StatusPage.slug == slug, StatusPage.is_public == True)
    result = await db.execute(stmt)
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Status page not found")

    stmt = (select(StatusPageItem)
            .where(StatusPageItem.status_page_id == page.id)
            .order_by(StatusPageItem.sort_order))
    items_result = await db.execute(stmt)
    items = items_result.scalars().all()

    services = []
    for item in items:
        monitor = await db.get(Monitor, item.monitor_id)
        if not monitor:
            continue

        # Get 24h uptime
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = (select(CheckResult)
                .where(CheckResult.monitor_id == monitor.id, CheckResult.timestamp >= since))
        results = await db.execute(stmt)
        checks = results.scalars().all()
        total = len(checks)
        up_count = sum(1 for c in checks if c.status == "up")
        uptime_24h = (up_count / total * 100) if total > 0 else 100.0

        services.append({
            "name": monitor.name,
            "group": item.group_name,
            "status": monitor.status,
            "uptime_24h": round(uptime_24h, 2),
            "last_check": monitor.last_check.isoformat() if monitor.last_check else None,
        })

    # Get incidents for all monitors on this page
    monitor_ids = [item.monitor_id for item in items]
    incidents = []
    if monitor_ids:
        since_7d = datetime.now(timezone.utc) - timedelta(days=7)
        stmt = (select(Incident)
                .where(Incident.monitor_id.in_(monitor_ids), Incident.started_at >= since_7d)
                .order_by(desc(Incident.started_at)))
        inc_result = await db.execute(stmt)
        for inc in inc_result.scalars().all():
            monitor = await db.get(Monitor, inc.monitor_id)
            duration_seconds = None
            if inc.resolved_at:
                duration_seconds = int((inc.resolved_at - inc.started_at).total_seconds())
            incidents.append({
                "monitor_name": monitor.name if monitor else "Unknown",
                "started_at": inc.started_at.isoformat(),
                "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
                "duration_seconds": duration_seconds,
                "error": inc.error,
            })

    return {
        "title": page.title,
        "logo_url": page.logo_url,
        "services": services,
        "incidents": incidents,
    }
