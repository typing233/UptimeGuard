import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db, engine, Base


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_monitor(client):
    resp = await client.post("/api/monitors", json={
        "name": "Test HTTP",
        "monitor_type": "http",
        "target": "https://httpbin.org/get",
        "interval": 60,
        "timeout": 10,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test HTTP"
    assert data["monitor_type"] == "http"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_list_monitors(client):
    await client.post("/api/monitors", json={"name": "M1", "monitor_type": "http", "target": "https://a.com", "interval": 60, "timeout": 5})
    await client.post("/api/monitors", json={"name": "M2", "monitor_type": "tcp", "target": "b.com", "port": 443, "interval": 30, "timeout": 5})
    resp = await client.get("/api/monitors")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_monitor(client):
    create_resp = await client.post("/api/monitors", json={"name": "Old", "monitor_type": "http", "target": "https://x.com", "interval": 60, "timeout": 5})
    mid = create_resp.json()["id"]
    resp = await client.put(f"/api/monitors/{mid}", json={"name": "New", "interval": 30})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"
    assert resp.json()["interval"] == 30


@pytest.mark.asyncio
async def test_delete_monitor(client):
    create_resp = await client.post("/api/monitors", json={"name": "Del", "monitor_type": "icmp", "target": "8.8.8.8", "interval": 60, "timeout": 5})
    mid = create_resp.json()["id"]
    resp = await client.delete(f"/api/monitors/{mid}")
    assert resp.status_code == 200
    list_resp = await client.get("/api/monitors")
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_create_alert_channel(client):
    resp = await client.post("/api/alert-channels", json={
        "name": "Test Webhook",
        "channel_type": "webhook",
        "config": {"url": "https://hooks.example.com/test"},
    })
    assert resp.status_code == 200
    assert resp.json()["channel_type"] == "webhook"


@pytest.mark.asyncio
async def test_create_alert_policy(client):
    m_resp = await client.post("/api/monitors", json={"name": "P", "monitor_type": "http", "target": "https://p.com", "interval": 60, "timeout": 5})
    mid = m_resp.json()["id"]
    resp = await client.post("/api/alert-policies", json={
        "monitor_id": mid, "failure_threshold": 5, "recovery_notify": True, "channel_ids": [], "repeat_interval": 10,
    })
    assert resp.status_code == 200
    assert resp.json()["failure_threshold"] == 5


@pytest.mark.asyncio
async def test_status_page_lifecycle(client):
    m_resp = await client.post("/api/monitors", json={"name": "SP Monitor", "monitor_type": "http", "target": "https://sp.com", "interval": 60, "timeout": 5})
    mid = m_resp.json()["id"]

    sp_resp = await client.post("/api/status-pages", json={"title": "Test Status", "slug": "test-sp"})
    assert sp_resp.status_code == 200
    sp_id = sp_resp.json()["id"]

    item_resp = await client.post(f"/api/status-pages/{sp_id}/items", json={"monitor_id": mid, "group_name": "Core"})
    assert item_resp.status_code == 200

    public_resp = await client.get("/api/status/test-sp")
    assert public_resp.status_code == 200
    data = public_resp.json()
    assert data["title"] == "Test Status"
    assert len(data["services"]) == 1
    assert data["services"][0]["group"] == "Core"


@pytest.mark.asyncio
async def test_status_page_not_found(client):
    resp = await client.get("/api/status/nonexistent")
    assert resp.status_code == 404
