# UptimeGuard - 服务可用性监控系统

全功能的服务可用性监控 Web 应用，支持 HTTP/HTTPS、TCP、ICMP Ping 三种监控类型，带告警通知和公开状态页。

## 快速启动

```bash
chmod +x run.sh
./run.sh
```

服务启动后访问 http://localhost:8000

## 功能概览

### 监控能力
- **HTTP/HTTPS**: 检查状态码、响应时间、关键字校验
- **TCP**: 端口连通性检测
- **ICMP Ping**: 主机可达性检测
- 可配置检测频率（30秒/1分钟/5分钟/10分钟）和超时阈值

### 告警通知
- **邮件**: SMTP 配置发送告警邮件
- **Webhook**: 自定义 JSON 请求体，支持动态变量 `$monitor_name`, `$target`, `$status`, `$failure_count`, `$down_time`, `$recovery_time`, `$error`, `$latency`
- **钉钉机器人**: Markdown 格式通知
- **飞书机器人**: 文本通知
- **企业微信机器人**: 文本通知

### 告警策略（每个监控项独立配置）
- 连续失败 N 次后触发告警
- 恢复后是否通知
- 选择通知渠道
- 静默时段（如 23:00-07:00 不告警）
- 重复提醒间隔

### 公开状态页
- 独立公开访问页面，可设置标题、Logo
- 服务分组展示
- 实时显示服务状态和 24 小时 uptime
- 近 7 天故障时间线
- 可通过 iframe 嵌入外部网站
- 分享链接: `/status-page/{slug}`

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/monitors` | 监控项列表/创建 |
| GET/PUT/DELETE | `/api/monitors/{id}` | 查看/编辑/删除监控项 |
| POST | `/api/monitors/{id}/check` | 手动触发检测 |
| GET | `/api/monitors/{id}/results` | 获取检测结果历史 |
| GET/POST | `/api/alert-channels` | 通知渠道列表/创建 |
| PUT/DELETE | `/api/alert-channels/{id}` | 编辑/删除渠道 |
| GET/POST | `/api/alert-policies` | 告警策略查看/创建 |
| DELETE | `/api/alert-policies/{monitor_id}` | 删除策略 |
| GET/POST | `/api/status-pages` | 状态页列表/创建 |
| PUT/DELETE | `/api/status-pages/{id}` | 编辑/删除状态页 |
| POST/DELETE | `/api/status-pages/{id}/items` | 添加/移除状态页服务 |
| GET | `/api/status/{slug}` | 公开状态页数据 |

## 运行测试

```bash
source venv/bin/activate
pytest tests/ -v
```

## 验收说明

1. **启动服务**: 执行 `./run.sh`，访问 http://localhost:8000
2. **创建监控**: 点击"新建监控"，填写名称、类型、目标地址、频率
3. **查看状态**: 仪表盘自动刷新，显示监控项状态和响应时间曲线
4. **配置告警**: 切换到"告警配置"页签，创建通知渠道和告警策略
5. **创建状态页**: 切换到"状态页"页签，创建公开状态页并添加服务
6. **访问状态页**: 点击状态页链接或访问 `/status-page/{slug}`
7. **嵌入测试**: 点击"复制嵌入代码"可获取 iframe 代码

## 技术栈

- **后端**: FastAPI + SQLAlchemy + APScheduler + aiosqlite
- **前端**: 原生 HTML/JS + Chart.js
- **数据库**: SQLite（自动创建）
- **检测**: httpx (HTTP) + asyncio (TCP) + 原生 ICMP/ping fallback
