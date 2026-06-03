import pytest
from app.checker import check_http, check_tcp, check_icmp, run_check


@pytest.mark.asyncio
async def test_check_http_success():
    result = await check_http("https://httpbin.org/get", timeout=10, expected_status=200)
    assert result.status == "up"
    assert result.latency is not None
    assert result.latency > 0


@pytest.mark.asyncio
async def test_check_http_wrong_status():
    result = await check_http("https://httpbin.org/status/404", timeout=10, expected_status=200)
    assert result.status == "down"
    assert "404" in result.error


@pytest.mark.asyncio
async def test_check_http_keyword_found():
    result = await check_http("https://httpbin.org/html", timeout=10, expected_status=200, keyword="Herman")
    assert result.status == "up"


@pytest.mark.asyncio
async def test_check_http_keyword_missing():
    result = await check_http("https://httpbin.org/html", timeout=10, expected_status=200, keyword="ZZZZZ_NOT_HERE")
    assert result.status == "down"
    assert "Keyword" in result.error


@pytest.mark.asyncio
async def test_check_http_timeout():
    result = await check_http("https://httpbin.org/delay/5", timeout=2, expected_status=200)
    assert result.status == "down"
    assert "timed out" in result.error.lower() or "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_check_tcp_success():
    result = await check_tcp("httpbin.org", 443, timeout=10)
    assert result.status == "up"
    assert result.latency > 0


@pytest.mark.asyncio
async def test_check_tcp_failure():
    result = await check_tcp("127.0.0.1", 19999, timeout=3)
    assert result.status == "down"


@pytest.mark.asyncio
async def test_run_check_dispatch():
    result = await run_check("http", "https://httpbin.org/get", timeout=10)
    assert result.status == "up"

    result = await run_check("tcp", "httpbin.org", port=80, timeout=10)
    assert result.status == "up"
