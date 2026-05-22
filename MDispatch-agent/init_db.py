import sqlite3

DB_PATH = "mdispatch.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 维修工表
cursor.execute("""
CREATE TABLE IF NOT EXISTS engineers (
    engineer_id TEXT PRIMARY KEY,
    name TEXT,
    phone TEXT,
    password TEXT,
    skill_brand TEXT,
    skill_model TEXT,
    work_status TEXT,
    latitude REAL,
    longitude REAL,
    update_time TEXT
)
""")

# 工单表
cursor.execute("""
CREATE TABLE IF NOT EXISTS work_orders (
    work_order_id TEXT PRIMARY KEY,
    alarm_time TEXT,
    user_name TEXT,
    user_phone TEXT,
    address TEXT,
    device_id TEXT,
    device_brand TEXT,
    device_model TEXT,
    fault_type TEXT,
    emergency_level TEXT,
    order_status TEXT,
    engineer_id TEXT,
    engineer_name TEXT,
    engineer_phone TEXT,
    distance TEXT,
    eta TEXT,
    user_notice TEXT,
    engineer_notice TEXT,
    remark TEXT,
    create_time TEXT,
    last_operation_time TEXT
)
""")

# 用户资料表
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    phone TEXT PRIMARY KEY,
    name TEXT,
    province TEXT,
    city TEXT,
    address_detail TEXT,
    full_address TEXT
)
""")

conn.commit()
conn.close()

print("SQLite数据库初始化完成：mdispatch.db")
