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


@pytest.mark.asyncio
async def test_trigger_check_returns_result(client):
    resp = await client.post("/api/monitors", json={
        "name": "Trigger Test",
        "monitor_type": "tcp",
        "target": "127.0.0.1",
        "port": 1,
        "interval": 60,
        "timeout": 2,
    })
    mid = resp.json()["id"]
    check_resp = await client.post(f"/api/monitors/{mid}/check")
    assert check_resp.status_code == 200
    data = check_resp.json()
    assert "status" in data
    assert "latency" in data
    assert "timestamp" in data
    assert data["monitor_id"] == mid


@pytest.mark.asyncio
async def test_check_with_alert_policy_does_not_crash(client):
    m_resp = await client.post("/api/monitors", json={
        "name": "Alert Test",
        "monitor_type": "tcp",
        "target": "127.0.0.1",
        "port": 1,
        "interval": 60,
        "timeout": 2,
    })
    mid = m_resp.json()["id"]
    # Create alert policy with non-existent channel IDs — should not crash
    await client.post("/api/alert-policies", json={
        "monitor_id": mid, "failure_threshold": 1, "recovery_notify": True,
        "channel_ids": [9999], "repeat_interval": 0,
    })
    check_resp = await client.post(f"/api/monitors/{mid}/check")
    assert check_resp.status_code == 200
    assert check_resp.json()["status"] == "down"

    # Verify result was persisted
    results_resp = await client.get(f"/api/monitors/{mid}/results")
    assert results_resp.status_code == 200
    assert len(results_resp.json()) == 1


@pytest.mark.asyncio
async def test_status_page_edit(client):
    m_resp = await client.post("/api/monitors", json={"name": "Edit SP", "monitor_type": "http", "target": "https://a.com", "interval": 60, "timeout": 5})
    mid = m_resp.json()["id"]
    m2_resp = await client.post("/api/monitors", json={"name": "Edit SP2", "monitor_type": "http", "target": "https://b.com", "interval": 60, "timeout": 5})
    mid2 = m2_resp.json()["id"]

    sp_resp = await client.post("/api/status-pages", json={"title": "Original", "slug": "edit-test"})
    sp_id = sp_resp.json()["id"]

    # Add initial item
    await client.post(f"/api/status-pages/{sp_id}/items", json={"monitor_id": mid, "group_name": "G1"})

    # Edit: change title and replace items
    await client.put(f"/api/status-pages/{sp_id}", json={"title": "Updated Title"})
    await client.put(f"/api/status-pages/{sp_id}/items", json=[
        {"monitor_id": mid, "group_name": "NewGroup", "sort_order": 0},
        {"monitor_id": mid2, "group_name": "NewGroup", "sort_order": 1},
    ])

    public_resp = await client.get("/api/status/edit-test")
    data = public_resp.json()
    assert data["title"] == "Updated Title"
    assert len(data["services"]) == 2
    assert data["services"][0]["group"] == "NewGroup"


@pytest.mark.asyncio
async def test_incidents_have_timestamps(client):
    m_resp = await client.post("/api/monitors", json={
        "name": "Incident Test",
        "monitor_type": "tcp",
        "target": "127.0.0.1",
        "port": 1,
        "interval": 60,
        "timeout": 2,
    })
    mid = m_resp.json()["id"]

    # Trigger a down check to create an incident
    await client.post(f"/api/monitors/{mid}/check")

    sp_resp = await client.post("/api/status-pages", json={"title": "Inc Page", "slug": "inc-test"})
    sp_id = sp_resp.json()["id"]
    await client.post(f"/api/status-pages/{sp_id}/items", json={"monitor_id": mid, "group_name": "Test"})

    public_resp = await client.get("/api/status/inc-test")
    data = public_resp.json()
    assert len(data["incidents"]) == 1
    inc = data["incidents"][0]
    assert inc["started_at"] is not None
    assert inc["resolved_at"] is None
    assert inc["duration_seconds"] is None
