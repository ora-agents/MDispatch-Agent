"""初始化默认数据到数据库"""
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "mdispatch",
    "user": "postgres",
    "password": "ml030827"
}

def init_default_user():
    """初始化默认用户张三"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO users (phone, name, password, province, city, address_detail, full_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (phone) DO UPDATE SET
                name = EXCLUDED.name,
                password = EXCLUDED.password,
                province = EXCLUDED.province,
                city = EXCLUDED.city,
                address_detail = EXCLUDED.address_detail,
                full_address = EXCLUDED.full_address
        """, (
            "13800138000",
            "张三",
            "123456",  # 默认密码
            "江苏省",
            "南京市",
            "江宁区XX小区1栋101",
            "江苏省南京市江宁区XX小区1栋101"
        ))
        
        print("默认用户 张三 (13800138000) 已创建/更新")
        cursor.close()
        conn.close()
    except psycopg2.Error as e:
        print("创建默认用户失败: " + str(e))

def init_default_device():
    """初始化默认设备"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                brand TEXT,
                model TEXT,
                device_type TEXT,
                user_name TEXT,
                user_phone TEXT,
                address TEXT,
                status TEXT DEFAULT '正常',
                install_time TEXT
            )
        """)
        
        cursor.execute("""
            INSERT INTO devices (device_id, brand, model, device_type, user_name, user_phone, address, status, install_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (device_id) DO UPDATE SET
                brand = EXCLUDED.brand,
                model = EXCLUDED.model,
                device_type = EXCLUDED.device_type,
                user_name = EXCLUDED.user_name,
                user_phone = EXCLUDED.user_phone,
                address = EXCLUDED.address,
                status = EXCLUDED.status,
                install_time = EXCLUDED.install_time
        """, (
            "DEV2025001",
            "奥的斯",
            "GEN2",
            "电梯",
            "张三",
            "13800138000",
            "江苏省南京市江宁区XX小区1栋101",
            "正常",
            "2024-06-01"
        ))
        
        print("默认设备 DEV2025001 已创建/更新")
        cursor.close()
        conn.close()
    except psycopg2.Error as e:
        print("创建默认设备失败: " + str(e))

def init_default_engineers():
    """初始化默认维修工"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()
        
        engineers = [
            {
                "engineer_id": "ENG001",
                "name": "李四",
                "phone": "13900139001",
                "password": "123456",
                "skill_brand": "奥的斯",
                "skill_model": "GEN2",
                "work_status": "空闲",
                "latitude": 32.0603,
                "longitude": 118.7969,
                "update_time": "2024-01-01 00:00:00"
            },
            {
                "engineer_id": "ENG002",
                "name": "王五",
                "phone": "13900139002",
                "password": "123456",
                "skill_brand": "三菱",
                "skill_model": "LEHY",
                "work_status": "空闲",
                "latitude": 32.0503,
                "longitude": 118.8069,
                "update_time": "2024-01-01 00:00:00"
            }
        ]
        
        for eng in engineers:
            cursor.execute("""
                INSERT INTO engineers (
                    engineer_id, name, phone, password, skill_brand, skill_model,
                    work_status, latitude, longitude, update_time
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (engineer_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    phone = EXCLUDED.phone,
                    password = EXCLUDED.password,
                    skill_brand = EXCLUDED.skill_brand,
                    skill_model = EXCLUDED.skill_model,
                    work_status = EXCLUDED.work_status,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    update_time = EXCLUDED.update_time
            """, (
                eng["engineer_id"],
                eng["name"],
                eng["phone"],
                eng["password"],
                eng["skill_brand"],
                eng["skill_model"],
                eng["work_status"],
                eng["latitude"],
                eng["longitude"],
                eng["update_time"]
            ))
        
        print("默认维修工 李四(ENG001)、王五(ENG002) 已创建/更新")
        cursor.close()
        conn.close()
    except psycopg2.Error as e:
        print("创建默认维修工失败: " + str(e))

if __name__ == "__main__":
    print("=== Initializing Default Data ===")
    init_default_user()
    init_default_device()
    init_default_engineers()
    print("=== Default Data Initialized ===")
