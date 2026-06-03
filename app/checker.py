import asyncio
import time
import socket
import subprocess
import httpx
from datetime import datetime
from app.database import SessionLocal, Monitor, CheckResult


async def check_http(monitor: Monitor) -> dict:
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=monitor.timeout, follow_redirects=True) as client:
            response = await client.get(monitor.target)
            latency = (time.time() - start) * 1000

            if monitor.expected_status_code and response.status_code != monitor.expected_status_code:
                return {
                    "status": "down",
                    "latency": latency,
                    "error": f"Expected status {monitor.expected_status_code}, got {response.status_code}",
                    "status_code": response.status_code,
                }

            if monitor.keyword:
                text = response.text
                if monitor.keyword not in text:
                    return {
                        "status": "down",
                        "latency": latency,
                        "error": f"Keyword '{monitor.keyword}' not found in response",
                        "status_code": response.status_code,
                    }

            return {
                "status": "up",
                "latency": latency,
                "error": None,
                "status_code": response.status_code,
            }
    except httpx.TimeoutException:
        latency = (time.time() - start) * 1000
        return {"status": "down", "latency": latency, "error": "Request timed out", "status_code": None}
    except Exception as e:
        latency = (time.time() - start) * 1000
        return {"status": "down", "latency": latency, "error": str(e), "status_code": None}


async def check_tcp(monitor: Monitor) -> dict:
    start = time.time()
    port = monitor.port
    if not port:
        return {"status": "down", "latency": 0, "error": "No port specified", "status_code": None}

    host = monitor.target.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]

    try:
        loop = asyncio.get_event_loop()
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=monitor.timeout)
        latency = (time.time() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return {"status": "up", "latency": latency, "error": None, "status_code": None}
    except asyncio.TimeoutError:
        latency = (time.time() - start) * 1000
        return {"status": "down", "latency": latency, "error": "Connection timed out", "status_code": None}
    except Exception as e:
        latency = (time.time() - start) * 1000
        return {"status": "down", "latency": latency, "error": str(e), "status_code": None}


async def check_icmp(monitor: Monitor) -> dict:
    host = monitor.target.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
    start = time.time()

    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", str(monitor.timeout), host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=monitor.timeout + 2)
        latency = (time.time() - start) * 1000

        if proc.returncode == 0:
            output = stdout.decode()
            for line in output.split("\n"):
                if "time=" in line:
                    time_part = line.split("time=")[1].split(" ")[0]
                    try:
                        latency = float(time_part)
                    except ValueError:
                        pass
                    break
            return {"status": "up", "latency": latency, "error": None, "status_code": None}
        else:
            return {"status": "down", "latency": latency, "error": "Host unreachable", "status_code": None}
    except asyncio.TimeoutError:
        latency = (time.time() - start) * 1000
        return {"status": "down", "latency": latency, "error": "Ping timed out", "status_code": None}
    except Exception as e:
        latency = (time.time() - start) * 1000
        return {"status": "down", "latency": latency, "error": str(e), "status_code": None}


async def run_check(monitor_id: int):
    db = SessionLocal()
    try:
        monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
        if not monitor or not monitor.active:
            return

        if monitor.monitor_type == "http":
            result = await check_http(monitor)
        elif monitor.monitor_type == "tcp":
            result = await check_tcp(monitor)
        elif monitor.monitor_type == "icmp":
            result = await check_icmp(monitor)
        else:
            result = {"status": "down", "latency": 0, "error": f"Unknown type: {monitor.monitor_type}", "status_code": None}

        check_result = CheckResult(
            monitor_id=monitor.id,
            timestamp=datetime.utcnow(),
            status=result["status"],
            latency=result["latency"],
            error=result["error"],
            status_code=result.get("status_code"),
        )
        db.add(check_result)
        db.commit()
    finally:
        db.close()


def run_check_sync(monitor_id: int):
    asyncio.run(run_check(monitor_id))
