import json
import httpx
import aiosmtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone
from string import Template


TEMPLATE_VARS = {
    "monitor_name", "target", "status", "failure_count",
    "down_time", "recovery_time", "error", "latency"
}


def _render_template(template_str: str, context: dict) -> str:
    tpl = Template(template_str)
    return tpl.safe_substitute(context)


def _render_json_body(body_template: dict | str, context: dict) -> str:
    if isinstance(body_template, str):
        return _render_template(body_template, context)
    raw = json.dumps(body_template, ensure_ascii=False)
    rendered = _render_template(raw, context)
    return rendered


def build_context(monitor_name: str, target: str, status: str,
                  failure_count: int = 0, error: str = "",
                  latency: float = 0, down_time: str = "", recovery_time: str = "") -> dict:
    return {
        "monitor_name": monitor_name,
        "target": target,
        "status": status,
        "failure_count": str(failure_count),
        "down_time": down_time or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "recovery_time": recovery_time or "",
        "error": error or "",
        "latency": f"{latency:.1f}" if latency else "N/A",
    }


async def send_email(config: dict, subject: str, body: str):
    msg = MIMEText(body, "html", "utf-8")
    msg["From"] = config["from_addr"]
    msg["To"] = ", ".join(config["to_addrs"])
    msg["Subject"] = subject

    await aiosmtplib.send(
        msg,
        hostname=config["smtp_host"],
        port=config.get("smtp_port", 587),
        username=config.get("smtp_user"),
        password=config.get("smtp_pass"),
        use_tls=config.get("use_tls", True),
    )


async def send_webhook(config: dict, context: dict):
    url = config["url"]
    headers = config.get("headers", {"Content-Type": "application/json"})
    body_template = config.get("body_template")

    if body_template:
        body = _render_json_body(body_template, context)
    else:
        body = json.dumps({
            "monitor": context["monitor_name"],
            "target": context["target"],
            "status": context["status"],
            "failure_count": context["failure_count"],
            "error": context["error"],
            "time": context["down_time"],
        }, ensure_ascii=False)

    async with httpx.AsyncClient() as client:
        await client.post(url, content=body, headers=headers, timeout=10)


async def send_dingtalk(config: dict, context: dict):
    url = config["webhook_url"]
    status_text = "🔴 故障" if context["status"] == "down" else "🟢 恢复"
    content = (
        f"### {status_text}: {context['monitor_name']}\n\n"
        f"- 目标: {context['target']}\n"
        f"- 状态: {context['status']}\n"
        f"- 连续失败: {context['failure_count']} 次\n"
        f"- 错误: {context['error']}\n"
        f"- 时间: {context['down_time']}\n"
    )
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": f"UptimeGuard - {context['monitor_name']}", "text": content}
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, timeout=10)


async def send_feishu(config: dict, context: dict):
    url = config["webhook_url"]
    status_text = "故障" if context["status"] == "down" else "恢复"
    content = (
        f"监控告警 - {status_text}\n"
        f"名称: {context['monitor_name']}\n"
        f"目标: {context['target']}\n"
        f"状态: {context['status']}\n"
        f"失败次数: {context['failure_count']}\n"
        f"错误: {context['error']}\n"
        f"时间: {context['down_time']}"
    )
    payload = {"msg_type": "text", "content": {"text": content}}
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, timeout=10)


async def send_wecom(config: dict, context: dict):
    url = config["webhook_url"]
    status_text = "故障" if context["status"] == "down" else "恢复"
    content = (
        f"监控告警 - {status_text}\n"
        f"名称: {context['monitor_name']}\n"
        f"目标: {context['target']}\n"
        f"状态: {context['status']}\n"
        f"失败次数: {context['failure_count']}\n"
        f"错误: {context['error']}\n"
        f"时间: {context['down_time']}"
    )
    payload = {"msgtype": "text", "text": {"content": content}}
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, timeout=10)


async def send_alert(channel_type: str, config: dict, context: dict):
    subject = f"[UptimeGuard] {context['monitor_name']} - {context['status']}"
    if channel_type == "email":
        body = (
            f"<h3>{subject}</h3>"
            f"<p>目标: {context['target']}</p>"
            f"<p>状态: {context['status']}</p>"
            f"<p>连续失败: {context['failure_count']} 次</p>"
            f"<p>错误: {context['error']}</p>"
            f"<p>时间: {context['down_time']}</p>"
        )
        await send_email(config, subject, body)
    elif channel_type == "webhook":
        await send_webhook(config, context)
    elif channel_type == "dingtalk":
        await send_dingtalk(config, context)
    elif channel_type == "feishu":
        await send_feishu(config, context)
    elif channel_type == "wecom":
        await send_wecom(config, context)
