import asyncio
import time
import httpx
import socket
import struct
import os
from dataclasses import dataclass


@dataclass
class CheckResponse:
    status: str  # "up" or "down"
    latency: float | None = None  # ms
    error: str | None = None


async def check_http(target: str, timeout: int = 10, expected_status: int = 200,
                     keyword: str | None = None, method: str = "GET") -> CheckResponse:
    start = time.time()
    try:
        async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
            resp = await client.request(method, target, timeout=timeout)
            latency = (time.time() - start) * 1000

            if resp.status_code != expected_status:
                return CheckResponse(
                    status="down", latency=latency,
                    error=f"Expected status {expected_status}, got {resp.status_code}"
                )

            if keyword:
                body = resp.text
                if keyword not in body:
                    return CheckResponse(
                        status="down", latency=latency,
                        error=f"Keyword '{keyword}' not found in response"
                    )

            return CheckResponse(status="up", latency=latency)
    except httpx.TimeoutException:
        latency = (time.time() - start) * 1000
        return CheckResponse(status="down", latency=latency, error="Request timed out")
    except Exception as e:
        latency = (time.time() - start) * 1000
        return CheckResponse(status="down", latency=latency, error=str(e))


async def check_tcp(target: str, port: int, timeout: int = 10) -> CheckResponse:
    start = time.time()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(target, port), timeout=timeout
        )
        latency = (time.time() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return CheckResponse(status="up", latency=latency)
    except asyncio.TimeoutError:
        latency = (time.time() - start) * 1000
        return CheckResponse(status="down", latency=latency, error="Connection timed out")
    except Exception as e:
        latency = (time.time() - start) * 1000
        return CheckResponse(status="down", latency=latency, error=str(e))


def _icmp_checksum(data: bytes) -> int:
    s = 0
    n = len(data) % 2
    for i in range(0, len(data) - n, 2):
        s += (data[i]) + ((data[i + 1]) << 8)
    if n:
        s += data[-1]
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return ~s & 0xFFFF


async def check_icmp(target: str, timeout: int = 10) -> CheckResponse:
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _ping_sync, target, timeout),
            timeout=timeout + 1
        )
        return result
    except asyncio.TimeoutError:
        return CheckResponse(status="down", error="Ping timed out")


def _ping_sync(target: str, timeout: int) -> CheckResponse:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError:
        return _ping_fallback(target, timeout)

    sock.settimeout(timeout)
    packet_id = os.getpid() & 0xFFFF
    header = struct.pack("!BBHHH", 8, 0, 0, packet_id, 1)
    payload = b"uptimeguard" * 4
    chk = _icmp_checksum(header + payload)
    header = struct.pack("!BBHHH", 8, 0, chk, packet_id, 1)
    packet = header + payload

    try:
        dest = socket.gethostbyname(target)
    except socket.gaierror as e:
        sock.close()
        return CheckResponse(status="down", error=f"DNS resolution failed: {e}")

    start = time.time()
    try:
        sock.sendto(packet, (dest, 0))
        sock.recv(1024)
        latency = (time.time() - start) * 1000
        sock.close()
        return CheckResponse(status="up", latency=latency)
    except socket.timeout:
        sock.close()
        return CheckResponse(status="down", error="Ping timed out")
    except Exception as e:
        sock.close()
        return CheckResponse(status="down", error=str(e))


def _ping_fallback(target: str, timeout: int) -> CheckResponse:
    import subprocess
    start = time.time()
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), target],
            capture_output=True, text=True, timeout=timeout + 2
        )
        latency = (time.time() - start) * 1000
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "time=" in line:
                    t = line.split("time=")[1].split()[0]
                    latency = float(t)
                    break
            return CheckResponse(status="up", latency=latency)
        return CheckResponse(status="down", error="Ping failed")
    except subprocess.TimeoutExpired:
        return CheckResponse(status="down", error="Ping timed out")
    except Exception as e:
        return CheckResponse(status="down", error=str(e))


async def run_check(monitor_type: str, target: str, port: int | None = None,
                    timeout: int = 10, expected_status: int = 200,
                    keyword: str | None = None, method: str = "GET") -> CheckResponse:
    if monitor_type == "http":
        return await check_http(target, timeout, expected_status, keyword, method)
    elif monitor_type == "tcp":
        return await check_tcp(target, port or 80, timeout)
    elif monitor_type == "icmp":
        return await check_icmp(target, timeout)
    else:
        return CheckResponse(status="down", error=f"Unknown monitor type: {monitor_type}")
