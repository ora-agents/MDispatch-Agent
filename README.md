# MDispatch - 智能设备维修调度系统

> 基于 FastAPI 的智能设备维修调度系统，支持工单管理、AI派单、设备管理和用户隔离。

## 📋 项目简介

MDispatch 是一个面向设备维修服务的智能调度系统，主要功能包括：

- **工单管理**：支持报警报修、预约维修等多种工单类型
- **AI派单**：基于设备类型和维修工技能智能分配工单
- **用户隔离**：不同用户账户的工单完全隔离
- **实时监控**：维修工位置追踪和工单状态实时更新

## 🛠️ 技术栈

| 分类 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI | ^0.104.1 |
| 数据库 | PostgreSQL | ^16.0 |
| 前端 | HTML/CSS/JavaScript | - |
| 地图服务 | Leaflet | ^1.9.4 |
| API文档 | Swagger UI | 内置 |

## 📁 项目结构

```
MDispatch-agent/
├── app_dispatch.py          # 主应用服务
├── mcp_server.py            # MCP服务（AI控制面板调用）
├── init_postgresql.py       # 数据库初始化脚本
├── init_default_data.py     # 默认数据初始化
├── migrate_data.py          # 数据迁移脚本
├── start_server.py          # 服务启动脚本
└── static/
    ├── user_app.html        # 用户端页面
    ├── admin.html           # 管理员后台
    ├── dashboard_v2/        # 数据监控中心
    └── engineer_map.html    # 维修工实时调度地图
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- PostgreSQL 16.0+
- pip 包管理器

### 安装依赖

```bash
pip install fastapi uvicorn psycopg2-binary requests python-multipart
```

### 数据库配置

修改数据库连接参数（`app_dispatch.py` 和初始化脚本中）：

```python
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "mdispatch",
    "user": "postgres",
    "password": "your_password"
}
```

### 初始化数据库

```bash
# 创建数据库表结构
python init_postgresql.py

# 添加默认数据（可选）
python init_default_data.py
```

### 启动服务

```bash
# 方式1：直接运行
python app_dispatch.py

# 方式2：使用 uvicorn
uvicorn app_dispatch:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后访问：
- 用户端页面：http://localhost:8000/static/user_app.html
- 管理员后台：http://localhost:8000/static/admin.html
- API文档：http://localhost:8000/docs

## 🔐 用户账户系统

### 用户注册/登录

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/user/register` | POST | 用户注册 |
| `/api/user/login` | POST | 用户登录 |

### 默认测试用户

| 用户名 | 手机号 | 密码 |
|--------|--------|------|
| 张三 | 13800138000 | 123456 |

### 用户隔离机制

系统通过 `user_phone` 字段实现用户数据隔离：
- 用户登录后只能查看自己的工单和设备
- 工单创建时自动关联当前用户
- 设备绑定到指定用户后仅该用户可见

## 📡 API 接口

### 工单管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/app/user/orders` | GET | 获取用户工单列表 |
| `/api/app/user/order/{id}` | GET | 获取工单详情 |
| `/api/user/order/cancel` | POST | 取消工单 |
| `/api/user/order/book` | POST | 创建预约工单 |

### 设备管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/device/add` | POST | 添加设备 |
| `/api/device/{id}` | GET | 获取设备详情 |
| `/api/device/{id}` | PUT | 更新设备信息 |
| `/api/device/{id}` | DELETE | 删除设备 |

### 用户管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/users` | GET | 获取所有用户列表 |
| `/api/app/user/profile` | GET | 获取用户信息 |
| `/api/app/user/profile` | PUT | 更新用户信息 |

### AI 派单接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/ai/control/dispatch` | POST | AI智能派单 |
| `/api/ai/control/orders` | GET | 获取工单状态列表 |

## 🔄 MCP 服务（Model Context Protocol）

用于 AI 控制面板调用的标准化接口封装：

```bash
# 启动 MCP 服务
python mcp_server.py

# 服务地址
http://localhost:8001/mcp/
```

### MCP 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/mcp/dispatch` | POST | 创建工单并派单 |
| `/mcp/order/{id}` | GET | 获取工单详情 |
| `/mcp/orders` | GET | 获取工单列表 |

## 🗄️ 数据库表结构

### users（用户表）

| 字段 | 类型 | 说明 |
|------|------|------|
| phone | TEXT | 手机号（主键） |
| name | TEXT | 用户姓名 |
| password | TEXT | 密码 |
| province | TEXT | 省份 |
| city | TEXT | 城市 |
| address_detail | TEXT | 详细地址 |
| full_address | TEXT | 完整地址 |

### devices（设备表）

| 字段 | 类型 | 说明 |
|------|------|------|
| device_id | TEXT | 设备ID（主键） |
| brand | TEXT | 设备品牌 |
| model | TEXT | 设备型号 |
| device_type | TEXT | 设备类型 |
| user_name | TEXT | 所属用户姓名 |
| user_phone | TEXT | 所属用户手机号 |
| address | TEXT | 安装地址 |
| status | TEXT | 设备状态 |
| install_time | TEXT | 安装时间 |

### work_orders（工单表）

| 字段 | 类型 | 说明 |
|------|------|------|
| work_order_id | TEXT | 工单ID（主键） |
| alarm_time | TEXT | 报警/报修时间 |
| user_name | TEXT | 用户姓名 |
| user_phone | TEXT | 用户电话 |
| device_id | TEXT | 设备ID |
| fault_type | TEXT | 故障类型 |
| order_status | TEXT | 工单状态 |
| engineer_id | TEXT | 维修工ID |
| create_time | TEXT | 创建时间 |
| last_operation_time | TEXT | 最后操作时间 |

### engineers（维修工表）

| 字段 | 类型 | 说明 |
|------|------|------|
| engineer_id | TEXT | 维修工ID（主键） |
| name | TEXT | 姓名 |
| phone | TEXT | 联系电话 |
| skill_brand | TEXT | 技能品牌 |
| skill_model | TEXT | 技能型号 |
| work_status | TEXT | 工作状态 |
| latitude | FLOAT | 纬度 |
| longitude | FLOAT | 经度 |

## 📊 功能特性

- ✅ 用户账户注册与登录
- ✅ 用户数据隔离机制
- ✅ 工单创建与管理
- ✅ AI智能派单
- ✅ 设备绑定与管理
- ✅ 预约维修功能
- ✅ 工单状态实时更新
- ✅ 维修工位置追踪
- ✅ 数据监控中心
- ✅ MCP接口封装

## 📝 License

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

*项目维护中，持续更新功能...*
