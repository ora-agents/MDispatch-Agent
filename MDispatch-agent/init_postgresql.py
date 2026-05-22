"""PostgreSQL 数据库初始化脚本"""
import psycopg2

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "postgres",
    "user": "postgres",
    "password": "ml030827"
}

def create_database():
    """创建 mdispatch 数据库"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE mdispatch")
        print("Database mdispatch created successfully")
        cursor.close()
        conn.close()
    except psycopg2.Error as e:
        if "already exists" in str(e):
            print("Database mdispatch already exists")
        else:
            print("Failed to create database: " + str(e))

def create_tables():
    """创建数据库表"""
    db_config = DB_CONFIG.copy()
    db_config["database"] = "mdispatch"
    
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                phone TEXT PRIMARY KEY,
                name TEXT,
                password TEXT DEFAULT '',
                province TEXT,
                city TEXT,
                address_detail TEXT,
                full_address TEXT
            )
        """)
        print("users table created")
        
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
        print("engineers table created")
        
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
                order_type TEXT DEFAULT '报修',
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
        print("work_orders table created")
        
        cursor.close()
        conn.close()
    except psycopg2.Error as e:
        print("Failed to create tables: " + str(e))

if __name__ == "__main__":
    print("=== PostgreSQL Database Initialization ===")
    create_database()
    create_tables()
    print("=== Initialization Complete ===")
