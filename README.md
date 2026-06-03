# UptimeGuard - 服务可用性监控系统

## 功能

- **HTTP/HTTPS 监控** — 检查状态码、响应时间、关键字校验
- **TCP 端口监控** — 检测目标端口连通性
- **ICMP Ping 监控** — 检测主机可达性
- 支持 30秒 / 1分钟 / 5分钟 检测频率
- 可配置超时阈值
- 检测结果持久化 (SQLite)，含时间戳、状态、延迟、错误信息
- Web 仪表盘：监控列表、实时状态、响应时间曲线
- 页面上创建、编辑、删除监控项

## 快速启动

```bash
# 确保已安装 Python 3.9+
chmod +x run.sh
./run.sh
```

或手动启动:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动后访问 http://localhost:8000

## 项目结构

```
├── app/
│   ├── main.py         # FastAPI 应用入口
│   ├── database.py     # 数据库模型 (SQLite + SQLAlchemy)
│   ├── schemas.py      # Pydantic 数据模型
│   ├── routes.py       # REST API 接口
│   ├── checker.py      # HTTP/TCP/ICMP 检测实现
│   └── scheduler.py    # APScheduler 定时任务
├── static/
│   └── index.html      # 前端仪表盘 (Tailwind + Chart.js)
├── requirements.txt
├── run.sh
└── README.md
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/monitors | 获取所有监控项 |
| POST | /api/monitors | 创建监控项 |
| PUT | /api/monitors/:id | 更新监控项 |
| DELETE | /api/monitors/:id | 删除监控项 |
| POST | /api/monitors/:id/check | 手动触发检测 |
| GET | /api/monitors/:id/results | 查询检测历史 |
| GET | /api/status | 状态概览 (含最近一次检测结果) |

## 技术栈

- **后端**: FastAPI + SQLAlchemy + APScheduler
- **数据库**: SQLite (零配置)
- **前端**: Tailwind CSS + Chart.js (CDN)
- **HTTP 检测**: httpx (异步)
- **ICMP**: 系统 ping 命令
