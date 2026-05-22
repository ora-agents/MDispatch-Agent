from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime, timedelta
from math import radians, sin, cos, asin, sqrt
import json
import re
import ollama
from typing import Dict, List, Optional

app = FastAPI(title="MDispatch-Agent AI工业派单系统")

# WebSocket连接管理
active_connections: Dict[str, List[WebSocket]] = {}

async def broadcast_location(work_order_id: str, location_data: dict):
    """向关注某个工单的所有客户端广播位置信息"""
    connections = active_connections.get(work_order_id, [])
    for conn in connections:
        try:
            await conn.send_json(location_data)
        except:
            pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

from fastapi.responses import RedirectResponse

@app.get("/")
def root():
    return RedirectResponse(url="/static/user_app.html")

work_orders = {}
engineers_real = {}
user_profiles = {}
devices_registry = {}

DEFAULT_USER_PHONE = "13800138000"

class AlarmRequest(BaseModel):
    text: str
    device_id: str = ""
    user_name: str = ""
    user_phone: str = ""
    user_address: str = ""
    device_brand: str = ""
    device_model: str = ""
    device_type: str = "电梯"
    order_type: str = "报警"  # 工单类型：报警/报修
    fault_type: str = ""  # 故障类型：困人、机器失灵等

class EngineerRegisterRequest(BaseModel):
    engineer_id: str
    name: str
    phone: str
    password: str
    skill_brand: str
    skill_model: str
    status: str = "空闲"

class EngineerLocationRequest(BaseModel):
    engineer_id: str
    latitude: float
    longitude: float
    status: str = "空闲"

def extract_json(text):
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)
    return text

def ai_analyze_alarm(user_text):
    prompt = f"""
你是智慧电梯维修调度AI。

请分析用户报警内容，只返回JSON，不要解释。

格式：
{{
  "故障类型": "困人/异响/门故障/停运/其他",
  "紧急程度": "紧急/较急/普通",
  "是否派单": true,
  "设备品牌": "奥的斯",
  "设备型号": "GEN2",
  "给用户的话": "",
  "给维修工的话": ""
}}

用户报警：
{user_text}
"""

    try:
        response = ollama.chat(
            model="qwen3:4b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2}
        )
        content = extract_json(response["message"]["content"])
        return json.loads(content)
    except Exception:
        return {
            "故障类型": "困人",
            "紧急程度": "紧急",
            "是否派单": True,
            "设备品牌": "奥的斯",
            "设备型号": "GEN2",
            "给用户的话": "报警已收到，系统正在为您安排最近维修人员。",
            "给维修工的话": "收到紧急工单，请立即前往现场处理。"
        }

def calc_distance_km(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371 * c

def select_nearest_engineer(device_brand, device_model, device_lat, device_lon, exclude_ids=None):
    candidates = []
    exclude_ids = exclude_ids or []

    for engineer_id, engineer in engineers_real.items():
        if engineer_id in exclude_ids:
            continue

        if engineer["工作状态"] != "空闲":
            continue

        if engineer["latitude"] is None or engineer["longitude"] is None:
            continue

        if device_brand not in engineer["技能品牌"]:
            continue

        if device_model not in engineer["技能型号"]:
            continue

        distance = calc_distance_km(
            device_lat,
            device_lon,
            engineer["latitude"],
            engineer["longitude"]
        )

        candidates.append({
            "engineer_id": engineer_id,
            "engineer": engineer,
            "distance_km": distance
        })

    if not candidates:
        return None

    candidates.sort(key=lambda x: x["distance_km"])
    return candidates[0]

def sync_user_legacy_fields(user_table):
    """兼容旧版扁平字段"""
    info = user_table.get("用户信息") or {}
    device = user_table.get("设备信息") or {}
    engineer = user_table.get("维修人员信息") or {}
    status = user_table.get("工单状态", "待接单")

    user_table["当前状态"] = status
    user_table["用户姓名"] = info.get("用户姓名")
    user_table["用户电话"] = info.get("联系电话")
    user_table["用户地址"] = info.get("地址")
    user_table["维修工姓名"] = engineer.get("维修工姓名")
    user_table["维修工电话"] = engineer.get("维修工电话")
    user_table["预计到达时间"] = engineer.get("预计到达时间")
    user_table["距离"] = engineer.get("距离")
    user_table["设备ID"] = device.get("设备ID")
    user_table["设备品牌"] = device.get("设备品牌")
    user_table["设备型号"] = device.get("设备型号")

def build_user_order_table(
    work_order_id,
    user_name,
    user_phone,
    user_address,
    device_id,
    device_brand,
    device_model,
    device_type,
    fault_type,
    order_status,
    engineer_name,
    engineer_phone,
    distance_text,
    eta_text,
    user_notice,
    complete_time=None,
    create_time=None,
    last_operation_time=None,
    order_type="报警",
):
    user_table = {
        "工单ID": work_order_id,
        "工单类型": order_type,
        "用户信息": {
            "用户姓名": user_name,
            "联系电话": user_phone,
            "地址": user_address,
        },
        "设备信息": {
            "设备ID": device_id,
            "设备品牌": device_brand,
            "设备型号": device_model,
            "设备类型": device_type,
        },
        "故障类型": fault_type,
        "工单状态": order_status,
        "维修人员信息": {
            "维修工姓名": engineer_name,
            "维修工电话": engineer_phone,
            "预计到达时间": eta_text,
            "距离": distance_text,
        },
        "完成时间": complete_time,
        "用户通知": user_notice,
        "下单时间": create_time,
        "最后操作时间": last_operation_time,
    }
    sync_user_legacy_fields(user_table)
    return user_table

def engineer_mgmt_view(engineer):
    lat = engineer.get("latitude")
    lon = engineer.get("longitude")
    if lat is not None and lon is not None:
        location = f"{lat:.5f}, {lon:.5f}"
    else:
        location = "未上传定位"

    return {
        "维修工ID": engineer.get("维修工ID"),
        "维修工姓名": engineer.get("维修工姓名"),
        "联系电话": engineer.get("联系电话"),
        "工作状态": engineer.get("工作状态"),
        "技能品牌": engineer.get("技能品牌"),
        "技能型号": engineer.get("技能型号"),
        "地理位置": location,
        "更新时间": engineer.get("update_time"),
    }

def build_full_address(province, city, address_detail):
    parts = [p for p in (province or "", city or "", address_detail or "") if p]
    return "".join(parts)

def upsert_user_profile(name, phone, address, province="", city="", address_detail=""):
    if province and city:
        full = build_full_address(province, city, address_detail or "")
    else:
        full = address or ""
        if not address_detail and full:
            address_detail = full

    user_profiles[phone] = {
        "用户姓名": name,
        "联系电话": phone,
        "地址": full,
        "省份": province or "",
        "城市": city or "",
        "详细地址": address_detail or "",
    }
    save_user_to_db(user_profiles[phone])

def upsert_device(device_id, brand, model, device_type, user_name, address, phone, status, install_time=None):
    if not install_time:
        install_time = "2024-06-01"
    devices_registry[device_id] = {
        "设备ID": device_id,
        "设备品牌": brand,
        "设备型号": model,
        "设备类型": device_type,
        "设备状态": status,
        "所属用户姓名": user_name,
        "绑定地址": address,
        "联系电话": phone,
        "安装时间": install_time,
    }

def list_user_orders(user_phone):
    result = []
    for order in work_orders.values():
        internal = order.get("内部维修工单表", {})
        if internal.get("联系电话") == user_phone:
            user_table = order["用户端维修工单表"]
            sync_user_legacy_fields(user_table)
            result.append(user_table)
    result.sort(key=lambda x: x["工单ID"], reverse=True)
    return result

def user_order_stats(user_phone):
    orders = list_user_orders(user_phone)
    stats = {"待接单": 0, "已接单": 0, "已完成": 0, "总计": len(orders)}
    for o in orders:
        status = o.get("工单状态", "待接单")
        if status in ["待接单", "待人工派单", "正在转派", "待处理"]:
            stats["待接单"] += 1
        elif status in ["已接单", "处理中"]:
            stats["已接单"] += 1
        elif status == "已完成":
            stats["已完成"] += 1
    return stats

def list_engineer_orders(engineer_id):
    result = []
    for order in work_orders.values():
        task = order.get("维修工窗口", {})
        if task.get("维修工ID") == engineer_id:
            result.append(task)
    result.sort(key=lambda x: x["工单ID"], reverse=True)
    return result

def engineer_order_stats(engineer_id):
    orders = list_engineer_orders(engineer_id)
    stats = {"待处理": 0, "已接单": 0, "已完成": 0, "总计": len(orders)}
    for task in orders:
        status = task.get("任务状态", "待处理")
        if status == "待处理" or status == "已派单":
            stats["待处理"] += 1
        elif status == "已接单":
            stats["已接单"] += 1
        elif status == "已完成":
            stats["已完成"] += 1
    return stats

@app.post("/api/engineer/register")
def register_engineer(req: EngineerRegisterRequest):
    engineers_real[req.engineer_id] = {
        "维修工ID": req.engineer_id,
        "维修工姓名": req.name,
        "联系电话": req.phone,
        "密码": req.password,
        "技能品牌": req.skill_brand,
        "技能型号": req.skill_model,
        "工作状态": req.status,
        "latitude": None,
        "longitude": None,
        "update_time": None
    }

    save_engineer_to_db(engineers_real[req.engineer_id])

    return {
        "status": "success",
        "message": "维修工信息已保存",
        "data": engineers_real[req.engineer_id]
    }

@app.post("/api/engineer/login")
def engineer_login(req: dict):
    """维修工登录接口"""
    phone = req.get("phone", "").strip()
    password = req.get("password", "").strip()
    
    if not phone or not password:
        return {"status": "error", "message": "请输入账号和密码"}
    
    # 查找维修工
    for engineer_id, engineer in engineers_real.items():
        engineer_phone = engineer.get("联系电话", "")
        engineer_password = engineer.get("密码", "")
        
        if engineer_phone == phone and engineer_password == password:
            return {
                "status": "success",
                "message": "登录成功",
                "data": {
                    "engineer_id": engineer_id,
                    "name": engineer.get("维修工姓名", ""),
                    "phone": engineer_phone,
                    "skill_brand": engineer.get("技能品牌", ""),
                    "skill_model": engineer.get("技能型号", ""),
                    "status": engineer.get("工作状态", "空闲")
                }
            }
    
    return {"status": "error", "message": "账号或密码错误"}

class UserRegisterRequest(BaseModel):
    """用户注册请求模型"""
    phone: str
    name: str
    password: str
    address: str = ""

@app.post("/api/user/register")
def user_register(req: UserRegisterRequest):
    """用户注册接口"""
    phone = req.phone.strip()
    name = req.name.strip()
    password = req.password.strip()
    address = req.address.strip()
    
    if not phone or not name or not password:
        return {"status": "error", "message": "手机号、姓名和密码不能为空"}
    
    if phone in user_profiles:
        return {"status": "error", "message": "该手机号已注册"}
    
    user_profiles[phone] = {
        "用户姓名": name,
        "联系电话": phone,
        "密码": password,
        "地址": address,
        "省份": "",
        "城市": "",
        "详细地址": "",
    }
    save_user_to_db(user_profiles[phone])
    
    return {
        "status": "success",
        "message": "注册成功",
        "data": {
            "phone": phone,
            "name": name,
            "address": address
        }
    }

@app.post("/api/user/login")
def user_login(req: dict):
    """用户登录接口"""
    phone = req.get("phone", "").strip()
    password = req.get("password", "").strip()
    
    if not phone or not password:
        return {"status": "error", "message": "请输入账号和密码"}
    
    user = user_profiles.get(phone)
    
    if not user:
        return {"status": "error", "message": "该手机号未注册"}
    
    if user.get("密码", "") != password:
        return {"status": "error", "message": "密码错误"}
    
    return {
        "status": "success",
        "message": "登录成功",
        "data": {
            "phone": phone,
            "name": user.get("用户姓名", ""),
            "address": user.get("地址", "")
        }
    }

@app.get("/api/engineer/real/list")
def list_real_engineers():
    return {
        "status": "success",
        "data": engineers_real
    }

@app.post("/api/engineer/location/update")
def update_engineer_location(req: EngineerLocationRequest):
    engineer = engineers_real.get(req.engineer_id)

    if not engineer:
        return {
            "status": "error",
            "message": "维修工不存在，请先在手机端保存/登录维修工信息"
        }

    engineer["latitude"] = req.latitude
    engineer["longitude"] = req.longitude
    engineer["工作状态"] = req.status
    engineer["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    update_engineer_location_db(engineer)

    return {
        "status": "success",
        "message": "GPS位置更新成功",
        "data": engineer
    }

@app.get("/api/engineer/location/{engineer_id}")
def get_engineer_location(engineer_id: str):
    engineer = engineers_real.get(engineer_id)

    if not engineer:
        return {
            "status": "error",
            "message": "维修工不存在"
        }

    return {
        "status": "success",
        "data": engineer
    }

@app.post("/api/alarm")
def alarm(req: AlarmRequest):
    ai_result = ai_analyze_alarm(req.text)

    device_lat = 31.9485
    device_lon = 118.7854

    device_brand = req.device_brand or ai_result.get("设备品牌", "奥的斯")
    device_model = req.device_model or ai_result.get("设备型号", "GEN2")
    user_name = req.user_name
    user_phone = req.user_phone
    user_address = req.user_address
    
    # 使用请求中的工单类型，默认为"报警"
    order_type = req.order_type if req.order_type in ["报警", "报修"] else "报警"
    # 使用请求中的故障类型，如果没有则使用AI分析结果
    fault_type = req.fault_type if req.fault_type else ai_result.get("故障类型", "未知")

    upsert_user_profile(user_name, user_phone, user_address)
    upsert_device(
        req.device_id,
        device_brand,
        device_model,
        req.device_type,
        user_name,
        user_address,
        user_phone,
        "报警中" if order_type == "报警" else "待维护",
    )

    nearest = select_nearest_engineer(
        device_brand,
        device_model,
        device_lat,
        device_lon
    )

    work_order_id = "WO" + datetime.now().strftime("%Y%m%d%H%M%S")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if nearest:
        engineer_id = nearest["engineer_id"]
        engineer = nearest["engineer"]
        distance_text = f"{nearest['distance_km']:.2f}公里"
        eta_text = f"预计{max(3, int(nearest['distance_km'] * 3))}分钟到达"
        dispatch_status = "AI已自动派单"
        engineer["工作状态"] = "忙碌"
        engineer_name = engineer["维修工姓名"]
        engineer_phone = engineer["联系电话"]
        internal_status = "待处理"
        user_order_status = "待接单"
        task_status = "待处理"
        user_notice = ai_result.get("给用户的话", "您的工单已受理，维修人员将尽快到达。")
        engineer_notice = ai_result.get("给维修工的话", "请前往现场处理。")
    else:
        engineer_id = "未分配"
        engineer_name = "暂未分配"
        engineer_phone = "暂未分配"
        distance_text = "暂无"
        eta_text = "客服确认后通知"
        dispatch_status = "等待客服人工派单"
        internal_status = "待人工派单"
        user_order_status = "待接单"
        task_status = "未派单"
        user_notice = "当前暂无可自动派单维修人员，客服中心已介入处理，请保持冷静。"
        engineer_notice = "当前工单暂未派出，等待后台人工调度。"

    user_table = build_user_order_table(
        work_order_id,
        user_name,
        user_phone,
        user_address,
        req.device_id,
        device_brand,
        device_model,
        req.device_type,
        fault_type,
        user_order_status,
        engineer_name,
        engineer_phone,
        distance_text,
        eta_text,
        user_notice,
        None,  # complete_time
        now_str,  # create_time
        now_str,  # last_operation_time
        order_type,  # 工单类型
    )

    # 根据工单类型确定紧急程度：报警=紧急，报修=普通
    urgency = "紧急" if order_type == "报警" else "普通"
    
    order = {
        "内部维修工单表": {
            "工单ID": work_order_id,
            "报修/报警时间": now_str,
            "下单时间": now_str,
            "最后操作时间": now_str,
            "工单类型": order_type,
            "用户姓名": user_name,
            "联系电话": user_phone,
            "地址": user_address,
            "设备ID": req.device_id,
            "设备品牌": device_brand,
            "设备型号": device_model,
            "故障类型": fault_type,
            "紧急程度": urgency,
            "工单状态": internal_status,
            "备注": dispatch_status,
        },
        "用户端维修工单表": user_table,
        "维修工窗口": {
            "工单ID": work_order_id,
            "维修工ID": engineer_id,
            "维修工姓名": engineer_name,
            "联系电话": engineer_phone,
            "任务状态": task_status,
            "工单类型": order_type,
            "故障类型": fault_type,
            "紧急程度": urgency,
            "设备ID": req.device_id,
            "设备品牌": device_brand,
            "设备型号": device_model,
            "设备地址": user_address,
            "用户电话": user_phone,
            "距离": distance_text,
            "预计到达时间": eta_text,
            "维修工通知": engineer_notice,
            "下单时间": now_str,
            "最后操作时间": now_str,
        },
        "设备管理表": devices_registry.get(req.device_id, {}),
        "AI 派单结果": {
            "AI 识别": ai_result,
            "派单状态": dispatch_status,
            "推荐维修工 ID": engineer_id,
            "距离": distance_text,
            "预计到达": eta_text,
            "device_lat": device_lat,  # 保存设备经纬度用于实时追踪
            "device_lon": device_lon,
        },
    }

    work_orders[work_order_id] = order
    save_work_order_to_db(order)

    return {
        "status": "success",
        "reply_text": user_notice,
        "ai_result": ai_result,
        "data": order,
    }

# ===============================
# AI 控制面板专用派单接口
# ===============================

class AIDispatchRequest(BaseModel):
    """AI控制面板派单请求模型"""
    fault_type: str = ""           # 故障类型：困人、机器失灵、异响、门故障、停运等（必需）
    fault_description: str = ""    # 故障描述（必需）
    order_type: str = "报警"       # 工单类型：报警/报修（默认：报警）
    device_id: str = ""            # 设备ID（必需，系统将根据设备ID自动获取设备信息）

@app.post("/api/ai/control/dispatch")
def ai_control_dispatch(req: AIDispatchRequest):
    """
    AI控制面板专用派单接口
    
    接收AI控制面板发送的派单指令，自动创建工单并派发给合适的维修工。
    
    请求参数（只需提供以下参数，设备其他信息将自动获取）：
    - fault_type: 故障类型（必需）：困人、机器失灵、异响、门故障、停运、定期保养、其他
    - fault_description: 故障描述（必需）
    - order_type: 工单类型（可选）：报警/报修（默认：报警）
    - device_id: 设备ID（必需）：系统将根据设备ID自动查询设备品牌、型号、类型及绑定的用户信息
    
    响应：
    - status: 成功/失败
    - message: 提示信息
    - work_order_id: 工单ID
    - order_type: 工单类型
    - fault_type: 故障类型
    - device_info: 设备信息（从设备注册表获取）
    - dispatch_status: 派单状态（AI已自动派单/等待客服人工派单）
    - assigned_engineer: 分配的维修工信息（无人可派时为null）
    - user_info: 绑定用户信息
    """
    
    # 验证必要参数
    if not req.fault_type:
        return {"status": "error", "message": "请提供故障类型"}
    if not req.fault_description:
        return {"status": "error", "message": "请提供故障描述"}
    if not req.device_id:
        return {"status": "error", "message": "请提供设备ID"}
    
    # 根据设备ID获取设备信息
    device_info = devices_registry.get(req.device_id, {})
    
    # 使用设备注册表中的信息，如果请求中没有提供的话
    device_type = req.device_id.split("-")[0] if "-" in req.device_id else device_info.get("设备类型", "电梯")
    device_brand = device_info.get("设备品牌", "奥的斯")
    device_model = device_info.get("设备型号", "GEN2")
    user_name = device_info.get("所属用户姓名", "系统用户")
    user_phone = device_info.get("联系电话", DEFAULT_USER_PHONE)
    user_address = device_info.get("绑定地址", "系统地址")
    
    # 调用报警接口创建真实工单
    alarm_req = AlarmRequest(
        text=req.fault_description,
        device_id=req.device_id,
        user_name=user_name,
        user_phone=user_phone,
        user_address=user_address,
        device_brand=device_brand,
        device_model=device_model,
        device_type=device_type,
        order_type=req.order_type if req.order_type in ["报警", "报修"] else "报警",
        fault_type=req.fault_type,
    )
    
    result = alarm(alarm_req)
    
    if result["status"] == "success":
        order = result["data"]
        internal = order["内部维修工单表"]
        engineer_task = order["维修工窗口"]
        device_table = order["设备管理表"]
        
        return {
            "status": "success",
            "message": "工单创建成功",
            "work_order_id": internal["工单ID"],
            "order_type": internal["工单类型"],
            "fault_type": internal["故障类型"],
            "urgency": internal["紧急程度"],
            "device_info": {
                "device_id": internal["设备ID"],
                "device_type": device_table.get("设备类型", device_type),
                "device_brand": device_table.get("设备品牌", device_brand),
                "device_model": device_table.get("设备型号", device_model),
                "device_status": device_table.get("设备状态", "运行中"),
                "install_time": device_table.get("安装时间", ""),
            },
            "user_info": {
                "user_name": internal["用户姓名"],
                "user_phone": internal["联系电话"],
                "user_address": internal["地址"],
            },
            "dispatch_status": internal["备注"],
            "assigned_engineer": {
                "engineer_id": engineer_task["维修工ID"],
                "engineer_name": engineer_task["维修工姓名"],
                "engineer_phone": engineer_task["联系电话"],
                "distance": engineer_task["距离"],
                "eta": engineer_task["预计到达时间"],
            } if engineer_task["维修工ID"] != "未分配" else None,
            "create_time": internal["下单时间"],
            "order_data": order,
        }
    else:
        return {
            "status": "error",
            "message": result.get("reply_text", "工单创建失败"),
        }

@app.get("/api/ai/control/order/{work_order_id}")
def ai_control_order_status(work_order_id: str):
    """
    AI控制面板工单状态查询接口
    
    根据工单ID查询工单当前状态，包括：
    - 工单类型（报警/报修）
    - 工单状态（待接单/已接单/处理中/已完成/已取消/待人工派单/待预约等）
    - 紧急程度
    - 故障类型
    - 维修人员信息
    - 创建时间
    - 最后操作时间
    
    请求路径：
    - work_order_id: 工单ID（必需）
    
    响应：
    - status: 成功/失败
    - message: 提示信息
    - data: 工单完整状态信息
    """
    order = work_orders.get(work_order_id)
    
    if not order:
        return {"status": "error", "message": "工单不存在"}
    
    internal = order["内部维修工单表"]
    user_table = order["用户端维修工单表"]
    engineer_task = order["维修工窗口"]
    device_table = order.get("设备管理表", {})
    
    return {
        "status": "success",
        "message": "查询成功",
        "data": {
            "work_order_id": internal["工单ID"],
            "order_type": internal.get("工单类型", "报修"),
            "order_status": internal["工单状态"],
            "urgency": internal.get("紧急程度", "普通"),
            "fault_type": internal.get("故障类型", ""),
            "device_info": {
                "device_id": internal.get("设备ID", ""),
                "device_brand": internal.get("设备品牌", ""),
                "device_model": internal.get("设备型号", ""),
                "device_address": internal.get("地址", ""),
            },
            "user_info": {
                "user_name": internal.get("用户姓名", ""),
                "user_phone": internal.get("联系电话", ""),
            },
            "engineer_info": {
                "engineer_id": engineer_task.get("维修工ID", ""),
                "engineer_name": engineer_task.get("维修工姓名", ""),
                "engineer_phone": engineer_task.get("联系电话", ""),
                "engineer_status": engineer_task.get("任务状态", ""),
                "distance": engineer_task.get("距离", ""),
                "eta": engineer_task.get("预计到达时间", ""),
            } if engineer_task.get("维修工ID") != "未分配" and engineer_task.get("维修工ID") != "" else None,
            "create_time": internal.get("下单时间", ""),
            "last_operation_time": internal.get("最后操作时间", ""),
            "remark": internal.get("备注", ""),
            "booking_time": internal.get("预约时间", ""),
        }
    }

@app.get("/api/ai/control/orders")
def ai_control_orders(
    phone: Optional[str] = None,
    status: Optional[str] = None,
    start_time: Optional[str] = None
):
    """
    AI控制面板工单状态查询接口
    
    查询指定手机号用户从指定时间到当前时间为止的所有工单状态。
    
    查询参数：
    - phone: 用户手机号（必需）：只查询该用户的工单
    - status: 工单状态（可选）：待接单/已接单/处理中/已完成/已取消/待人工派单/待预约等
    - start_time: 开始时间（可选）：格式"YYYY-MM-DD HH:MM:SS"，查询此时间到当前时间的所有工单
    
    响应：
    - status: 成功/失败
    - message: 提示信息
    - data: 工单列表（包含每个工单的完整状态信息）
    - count: 工单总数
    """
    if not phone:
        return {"status": "error", "message": "请提供用户手机号"}
    
    orders_list = []
    
    for order_id, order in work_orders.items():
        internal = order["内部维修工单表"]
        engineer_task = order["维修工窗口"]
        
        order_phone = internal.get("联系电话", "")
        
        if order_phone != phone:
            continue
        
        order_status = internal["工单状态"]
        
        if status and order_status != status:
            continue
        
        order_time = internal.get("下单时间", "")
        if start_time:
            if not order_time or order_time < start_time:
                continue
        
        orders_list.append({
            "work_order_id": internal["工单ID"],
            "order_type": internal.get("工单类型", "报修"),
            "order_status": order_status,
            "urgency": internal.get("紧急程度", "普通"),
            "fault_type": internal.get("故障类型", ""),
            "device_id": internal.get("设备ID", ""),
            "device_brand": internal.get("设备品牌", ""),
            "device_model": internal.get("设备型号", ""),
            "device_address": internal.get("地址", ""),
            "user_name": internal.get("用户姓名", ""),
            "user_phone": order_phone,
            "engineer_id": engineer_task.get("维修工ID", ""),
            "engineer_name": engineer_task.get("维修工姓名", "未分配"),
            "engineer_phone": engineer_task.get("联系电话", ""),
            "engineer_status": engineer_task.get("任务状态", ""),
            "distance": engineer_task.get("距离", ""),
            "eta": engineer_task.get("预计到达时间", ""),
            "create_time": internal.get("下单时间", ""),
            "last_operation_time": internal.get("最后操作时间", ""),
            "remark": internal.get("备注", ""),
            "booking_time": internal.get("预约时间", ""),
        })
    
    orders_list.sort(key=lambda x: x["create_time"], reverse=True)
    
    return {
        "status": "success",
        "message": "查询成功",
        "data": orders_list,
        "count": len(orders_list),
    }

@app.get("/api/admin/orders")
def admin_orders():
    return {
        "status": "success",
        "data": work_orders
    }

@app.post("/api/admin/assign-order")
def assign_order(req: dict):
    """人工派单接口"""
    order_id = req.get("order_id")
    engineer_id = req.get("engineer_id")
    remark = req.get("remark", "")
    
    if not order_id or not engineer_id:
        return {"status": "error", "message": "缺少工单ID或维修工ID"}
    
    if order_id not in work_orders:
        return {"status": "error", "message": "工单不存在"}
    
    if engineer_id not in engineers_real:
        return {"status": "error", "message": "维修工不存在"}
    
    order = work_orders[order_id]
    engineer = engineers_real[engineer_id]
    
    # 更新工单状态为待处理
    if "内部维修工单表" in order:
        order["内部维修工单表"]["工单状态"] = "待处理"
        order["内部维修工单表"]["维修工ID"] = engineer_id
        order["内部维修工单表"]["维修工姓名"] = engineer.get("name") or engineer.get("维修工姓名") or ""
        if remark:
            order["内部维修工单表"]["派单备注"] = remark
    
    # 更新用户端工单表
    if "用户端维修工单表" in order:
        order["用户端维修工单表"]["维修工姓名"] = engineer.get("name") or engineer.get("维修工姓名") or ""
    
    # 更新维修工窗口
    if "维修工窗口" in order:
        order["维修工窗口"]["维修工ID"] = engineer_id
        order["维修工窗口"]["维修工姓名"] = engineer.get("name") or engineer.get("维修工姓名") or ""
        order["维修工窗口"]["任务状态"] = "待处理"
    
    return {
        "status": "success",
        "message": "派单成功",
        "data": {
            "order_id": order_id,
            "engineer_id": engineer_id,
            "engineer_name": engineer.get("name") or engineer.get("维修工姓名") or "",
            "status": "待处理"
        }
    }

@app.delete("/api/order/{work_order_id}")
def delete_order(work_order_id: str):
    """删除工单"""
    if work_order_id not in work_orders:
        return {"status": "error", "message": "工单不存在"}
    
    del work_orders[work_order_id]
    return {"status": "success", "message": "工单已删除"}

@app.delete("/api/engineer/{engineer_id}")
def delete_engineer(engineer_id: str):
    """删除维修工"""
    if engineer_id not in engineers_real:
        return {"status": "error", "message": "维修工不存在"}
    
    del engineers_real[engineer_id]
    return {"status": "success", "message": "维修工已删除"}

@app.get("/api/engineer/info/{engineer_id}")
def get_engineer(engineer_id: str):
    """获取单个维修工信息"""
    engineer = engineers_real.get(engineer_id)
    if not engineer:
        return {"status": "error", "message": "维修工不存在"}
    
    return {
        "status": "success",
        "data": {
            "engineer_id": engineer.get("engineer_id") or engineer.get("维修工ID") or engineer_id,
            "name": engineer.get("name") or engineer.get("维修工姓名") or "未知",
            "phone": engineer.get("phone") or engineer.get("联系电话") or "",
            "skills_brand": engineer.get("skill_brand") or engineer.get("技能品牌") or "",
            "skills_model": engineer.get("skill_model") or engineer.get("技能型号") or "",
            "completed_tasks": engineer.get("completed_tasks") or 0,
            "status": engineer.get("status") or engineer.get("工作状态") or "离线"
        }
    }

@app.put("/api/engineer/{engineer_id}")
def update_engineer(engineer_id: str, req: dict):
    """更新维修工信息"""
    if engineer_id not in engineers_real:
        return {"status": "error", "message": "维修工不存在"}
    
    engineer = engineers_real[engineer_id]
    
    if "name" in req:
        engineer["维修工姓名"] = req["name"]
        engineer["name"] = req["name"]
    if "phone" in req:
        engineer["联系电话"] = req["phone"]
        engineer["phone"] = req["phone"]
    if "skills_brand" in req:
        engineer["技能品牌"] = req["skills_brand"]
        engineer["skill_brand"] = req["skills_brand"]
    if "skills_model" in req:
        engineer["技能型号"] = req["skills_model"]
        engineer["skill_model"] = req["skills_model"]
    
    save_engineer_to_db(engineer)
    
    return {"status": "success", "message": "维修工信息已更新", "data": engineer}

@app.get("/api/device/{device_id}")
def get_device(device_id: str):
    """获取单个设备信息"""
    device = devices_registry.get(device_id)
    if not device:
        return {"status": "error", "message": "设备不存在"}
    
    return {
        "status": "success",
        "data": {
            "device_id": device_id,
            "device_name": device.get("device_name") or device.get("设备名称") or "",
            "brand": device.get("brand") or device.get("品牌") or "",
            "model": device.get("model") or device.get("型号") or "",
            "device_type": device.get("device_type") or device.get("设备类型") or "",
            "installation_address": device.get("installation_address") or device.get("安装地址") or "",
            "user_id": device.get("user_id") or device.get("用户ID") or ""
        }
    }

@app.delete("/api/device/{device_id}")
def delete_device(device_id: str):
    """删除设备"""
    if device_id not in devices_registry:
        return {"status": "error", "message": "设备不存在"}
    
    del devices_registry[device_id]
    return {"status": "success", "message": "设备已删除"}

@app.put("/api/device/{device_id}")
def update_device(device_id: str, req: dict):
    """更新设备信息"""
    if device_id not in devices_registry:
        return {"status": "error", "message": "设备不存在"}
    
    device = devices_registry[device_id]
    
    if "device_name" in req:
        device["设备名称"] = req["device_name"]
        device["device_name"] = req["device_name"]
    if "brand" in req:
        device["品牌"] = req["brand"]
        device["brand"] = req["brand"]
    if "model" in req:
        device["型号"] = req["model"]
        device["model"] = req["model"]
    if "device_type" in req:
        device["设备类型"] = req["device_type"]
        device["device_type"] = req["device_type"]
    if "installation_address" in req:
        device["安装地址"] = req["installation_address"]
        device["installation_address"] = req["installation_address"]
    if "user_id" in req:
        device["用户ID"] = req["user_id"]
        device["user_id"] = req["user_id"]
    
    return {"status": "success", "message": "设备信息已更新", "data": device}

@app.get("/api/engineers")
def get_engineers():
    """获取所有维修工列表"""
    result = {}
    for engineer_id, engineer in engineers_real.items():
        result[engineer_id] = {
            "engineer_id": engineer.get("engineer_id") or engineer.get("维修工ID") or engineer_id,
            "name": engineer.get("name") or engineer.get("维修工姓名") or "未知",
            "phone": engineer.get("phone") or engineer.get("联系电话") or "",
            "skill_brand": engineer.get("skill_brand") or engineer.get("技能品牌") or "",
            "skill_model": engineer.get("skill_model") or engineer.get("技能型号") or "",
            "status": engineer.get("status") or engineer.get("工作状态") or "空闲",
            "completed_tasks": engineer.get("completed_tasks") or 0,
        }
    return {
        "status": "success",
        "data": result
    }

@app.get("/api/devices")
def get_devices():
    """获取所有设备列表"""
    return {
        "status": "success",
        "data": devices_registry
    }

@app.get("/api/users")
def get_users():
    """获取所有用户列表"""
    result = {}
    for phone, profile in user_profiles.items():
        result[phone] = {
            "user_id": phone,
            "name": profile.get("name") or profile.get("用户姓名") or "未知",
            "phone": phone
        }
    return {"status": "success", "data": result}

@app.get("/api/user/{work_order_id}")
def user_order(work_order_id: str):
    order = work_orders.get(work_order_id)
    if not order:
        return {"status": "error", "message": "工单不存在"}
    user_table = order["用户端维修工单表"]
    sync_user_legacy_fields(user_table)
    return {"status": "success", "data": user_table}

class UserCancelRequest(BaseModel):
    work_order_id: str
    reason: str = ""

@app.post("/api/user/order/cancel")
def cancel_order(req: UserCancelRequest):
    order = work_orders.get(req.work_order_id)
    
    if not order:
        return {"status": "error", "message": "工单不存在"}
    
    internal_status = order["内部维修工单表"]["工单状态"]
    
    if internal_status == "已完成":
        return {"status": "error", "message": "已完成的工单无法取消"}
    
    if internal_status == "已取消":
        return {"status": "error", "message": "工单已取消"}
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    order["内部维修工单表"]["工单状态"] = "已取消"
    order["内部维修工单表"]["备注"] = f"用户取消原因: {req.reason}"
    order["内部维修工单表"]["最后操作时间"] = now_str
    
    user_table = order["用户端维修工单表"]
    user_table["工单状态"] = "已取消"
    user_table["最后操作时间"] = now_str
    sync_user_legacy_fields(user_table)
    
    engineer_task = order["维修工窗口"]
    engineer_task["任务状态"] = "已取消"
    engineer_task["最后操作时间"] = now_str
    
    engineer_id = engineer_task.get("维修工ID")
    if engineer_id and engineer_id != "未分配" and engineer_id in engineers_real:
        engineers_real[engineer_id]["工作状态"] = "空闲"
        update_engineer_location_db(engineers_real[engineer_id])
    
    save_work_order_to_db(order)
    
    return {
        "status": "success",
        "message": "工单已取消",
        "data": order["用户端维修工单表"],
    }

class UserProfileUpdateRequest(BaseModel):
    phone: str
    user_name: str
    new_phone: str = ""
    province: str = ""
    city: str = ""
    address_detail: str = ""

@app.put("/api/app/user/profile")
def update_user_profile(req: UserProfileUpdateRequest):
    if not req.phone or not req.user_name:
        return {"status": "error", "message": "姓名与联系电话不能为空"}

    if not req.province or not req.city:
        return {"status": "error", "message": "请选择省份和城市"}

    if not req.address_detail.strip():
        return {"status": "error", "message": "请填写详细地址"}

    new_phone = (req.new_phone or req.phone).strip()
    full_address = build_full_address(req.province, req.city, req.address_detail.strip())

    if req.phone != new_phone and req.phone in user_profiles:
        del user_profiles[req.phone]
        delete_user_from_db(req.phone)

    upsert_user_profile(
        req.user_name.strip(),
        new_phone,
        full_address,
        req.province.strip(),
        req.city.strip(),
        req.address_detail.strip(),
    )

    for device in devices_registry.values():
        if device.get("联系电话") == req.phone:
            device["联系电话"] = new_phone
            device["所属用户姓名"] = req.user_name.strip()
            device["绑定地址"] = full_address

    return {
        "status": "success",
        "message": "资料已保存",
        "data": user_profiles[new_phone],
    }

@app.get("/api/app/user/profile")
def app_user_profile(phone: str = DEFAULT_USER_PHONE):
    profile = user_profiles.get(phone)
    if not profile:
        profile = get_user_from_db(phone)
        if profile:
            user_profiles[phone] = profile
    
    if not profile:
        return {
            "status": "error",
            "message": "用户不存在",
            "data": {}
        }

    devices = [
        d for d in devices_registry.values()
        if d.get("联系电话") == phone or d.get("user_phone") == phone
    ]
    
    # 如果内存中没有，从数据库加载
    if not devices:
        devices = load_devices_from_db(phone)
        # 将加载的设备添加到注册表
        for dev in devices:
            device_id = dev.get("device_id") or dev.get("设备ID", "")
            if device_id:
                devices_registry[device_id] = dev
    
    # 转换设备数据格式
    formatted_devices = []
    for dev in devices:
        formatted_devices.append({
            "设备ID": dev.get("device_id") or dev.get("设备ID", ""),
            "设备名称": dev.get("device_name") or dev.get("设备名称", ""),
            "品牌": dev.get("brand") or dev.get("设备品牌") or dev.get("品牌", ""),
            "型号": dev.get("model") or dev.get("设备型号") or dev.get("型号", ""),
            "设备类型": dev.get("device_type") or dev.get("设备类型", ""),
            "设备状态": dev.get("status") or dev.get("设备状态", ""),
            "所属用户姓名": profile["用户姓名"],
            "绑定地址": profile["地址"],
            "联系电话": phone,
            "安装时间": dev.get("install_time") or dev.get("安装时间", ""),
        })

    return {
        "status": "success",
        "data": {
            "基础信息": profile,
            "设备列表": formatted_devices,
            "工单统计": user_order_stats(phone),
        },
    }

@app.get("/api/app/user/orders")
def app_user_orders(phone: str = DEFAULT_USER_PHONE):
    return {
        "status": "success",
        "data": list_user_orders(phone),
        "stats": user_order_stats(phone),
    }

@app.get("/api/app/user/order/{work_order_id}")
def app_user_order_detail(work_order_id: str):
    order = work_orders.get(work_order_id)
    if not order:
        return {"status": "error", "message": "工单不存在"}
    user_table = order["用户端维修工单表"]
    sync_user_legacy_fields(user_table)
    return {
        "status": "success",
        "data": {
            "用户端维修工单表": user_table,
            "设备管理表": order.get("设备管理表", {}),
        },
    }

@app.get("/api/engineer/{work_order_id}")
def engineer_order(work_order_id: str):
    order = work_orders.get(work_order_id)
    if not order:
        return {"status": "error", "message": "工单不存在"}
    return {"status": "success", "data": order["维修工窗口"]}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": "qwen3:4b",
        "engineers_count": len(engineers_real),
        "orders_count": len(work_orders)
    }
# ===============================
# 维修工接单 / 完成工单接口
# ===============================

class EngineerActionRequest(BaseModel):
    engineer_id: str
    work_order_id: str

@app.post("/api/engineer/order/accept")
def accept_order(req: EngineerActionRequest):

    order = work_orders.get(req.work_order_id)

    if not order:
        return {
            "status":"error",
            "message":"工单不存在"
        }

    engineer = engineers_real.get(req.engineer_id)

    if not engineer:
        return {
            "status":"error",
            "message":"维修工不存在"
        }

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    order["维修工窗口"]["任务状态"] = "已接单"
    order["维修工窗口"]["最后操作时间"] = now_str
    order["内部维修工单表"]["工单状态"] = "已接单"
    order["内部维修工单表"]["最后操作时间"] = now_str

    user_table = order["用户端维修工单表"]
    user_table["工单状态"] = "已接单"
    user_table["最后操作时间"] = now_str
    sync_user_legacy_fields(user_table)

    engineer["工作状态"] = "忙碌"

    save_work_order_to_db(order)
    update_engineer_location_db(engineer)

    return {
        "status": "success",
        "message": "工单已接单",
        "data": order["维修工窗口"],
    }

@app.post("/api/engineer/order/start")
def start_order(req: EngineerActionRequest):
    """维修工开始处理工单（到达现场）"""
    
    order = work_orders.get(req.work_order_id)
    if not order:
        return {"status": "error", "message": "工单不存在"}
    
    engineer = engineers_real.get(req.engineer_id)
    if not engineer:
        return {"status": "error", "message": "维修工不存在"}
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 更新状态为"处理中"
    order["维修工窗口"]["任务状态"] = "处理中"
    order["维修工窗口"]["最后操作时间"] = now_str
    order["内部维修工单表"]["工单状态"] = "处理中"
    order["内部维修工单表"]["最后操作时间"] = now_str
    
    user_table = order["用户端维修工单表"]
    user_table["工单状态"] = "处理中"
    user_table["最后操作时间"] = now_str
    sync_user_legacy_fields(user_table)
    
    save_work_order_to_db(order)
    
    return {
        "status": "success",
        "message": "已开始处理工单",
        "data": order["维修工窗口"],
    }

class EngineerRejectRequest(BaseModel):
    work_order_id: str
    engineer_id: str
    reason: str = ""

@app.post("/api/engineer/order/reject")
def reject_order(req: EngineerRejectRequest):
    order = work_orders.get(req.work_order_id)

    if not order:
        return {
            "status": "error",
            "message": "工单不存在"
        }

    engineer = engineers_real.get(req.engineer_id)

    if not engineer:
        return {
            "status": "error",
            "message": "维修工不存在"
        }

    current_engineer_id = order["维修工窗口"].get("维修工ID")
    if current_engineer_id != req.engineer_id:
        return {
            "status": "error",
            "message": "您不是该工单的派单维修工，无法拒绝"
        }

    order["内部维修工单表"]["工单状态"] = "正在转派"
    order["内部维修工单表"]["备注"] = f"维修工{engineer['维修工姓名']}拒绝接单，原因: {req.reason}"

    user_table = order["用户端维修工单表"]
    user_table["工单状态"] = "正在转派"
    sync_user_legacy_fields(user_table)

    engineer_task = order["维修工窗口"]
    engineer_task["任务状态"] = "已拒绝"
    engineer["工作状态"] = "空闲"
    update_engineer_location_db(engineer)

    device_brand = order["内部维修工单表"]["设备品牌"]
    device_model = order["内部维修工单表"]["设备型号"]
    address = order["内部维修工单表"]["地址"]

    nearest = select_nearest_engineer(
        device_brand,
        device_model,
        0,
        0,
        exclude_ids=[req.engineer_id]
    )

    if nearest:
        new_engineer_id = nearest["engineer_id"]
        new_engineer = nearest["engineer"]
        distance_text = f"{nearest['distance_km']:.2f}公里"
        eta_text = f"预计{max(3, int(nearest['distance_km'] * 3))}分钟到达"
        
        new_engineer["工作状态"] = "忙碌"
        update_engineer_location_db(new_engineer)

        order["内部维修工单表"]["工单状态"] = "待处理"
        order["内部维修工单表"]["备注"] = f"原维修工{engineer['维修工姓名']}拒绝，已转派给{new_engineer['维修工姓名']}"
        
        user_table["工单状态"] = "待接单"
        user_table["维修人员信息"] = {
            "维修工姓名": new_engineer["维修工姓名"],
            "维修工电话": new_engineer["联系电话"],
            "预计到达时间": eta_text,
            "距离": distance_text,
        }
        sync_user_legacy_fields(user_table)

        engineer_task.update({
            "维修工ID": new_engineer_id,
            "维修工姓名": new_engineer["维修工姓名"],
            "联系电话": new_engineer["联系电话"],
            "任务状态": "待处理",
            "距离": distance_text,
            "预计到达时间": eta_text,
            "维修工通知": f"原维修工{engineer['维修工姓名']}拒绝接单，该工单已转派给您，请尽快处理。",
        })

        save_work_order_to_db(order)

        return {
            "status": "success",
            "message": "工单已拒绝，已转派给其他维修工",
            "data": {
                "order": order["维修工窗口"],
                "new_engineer": new_engineer["维修工姓名"],
            },
        }
    else:
        order["内部维修工单表"]["工单状态"] = "待人工派单"
        order["内部维修工单表"]["备注"] = f"维修工{engineer['维修工姓名']}拒绝接单，暂无其他可派单维修工，等待人工派单"
        
        user_table["工单状态"] = "待接单"
        user_table["维修人员信息"] = {
            "维修工姓名": "暂未分配",
            "维修工电话": "暂未分配",
            "预计到达时间": "客服确认后通知",
            "距离": "暂无",
        }
        sync_user_legacy_fields(user_table)

        engineer_task.update({
            "维修工ID": "未分配",
            "维修工姓名": "暂未分配",
            "联系电话": "暂未分配",
            "任务状态": "未派单",
            "维修工通知": "当前工单暂未派出，等待后台人工调度。",
        })

        save_work_order_to_db(order)

        return {
            "status": "success",
            "message": "工单已拒绝，暂无其他可派单维修工，已转为人工派单",
            "data": order["维修工窗口"],
        }

@app.post("/api/engineer/order/complete")
def complete_order(req: EngineerActionRequest):

    order = work_orders.get(req.work_order_id)

    if not order:
        return {
            "status":"error",
            "message":"工单不存在"
        }

    engineer = engineers_real.get(req.engineer_id)

    if not engineer:
        return {
            "status":"error",
            "message":"维修工不存在"
        }

    complete_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    order["维修工窗口"]["任务状态"] = "已完成"
    order["维修工窗口"]["最后操作时间"] = complete_time
    order["内部维修工单表"]["工单状态"] = "已完成"
    order["内部维修工单表"]["最后操作时间"] = complete_time

    user_table = order["用户端维修工单表"]
    user_table["工单状态"] = "已完成"
    user_table["完成时间"] = complete_time
    user_table["最后操作时间"] = complete_time
    sync_user_legacy_fields(user_table)

    device_id = order["内部维修工单表"].get("设备ID")
    if device_id and device_id in devices_registry:
        devices_registry[device_id]["设备状态"] = "在线"

    engineer["工作状态"] = "空闲"

    save_work_order_to_db(order)
    update_engineer_location_db(engineer)

    return {
        "status": "success",
        "message": "工单已完成",
        "data": order["维修工窗口"],
    }

# ===============================
# 维修工自动接收派单任务
# ===============================

@app.get("/api/engineer/pending/{engineer_id}")
def get_engineer_pending_orders(engineer_id: str):
    result = []

    for order_id, order in work_orders.items():
        task = order.get("维修工窗口", {})

        if task.get("维修工ID") == engineer_id and task.get("任务状态") in ["待处理", "已派单"]:
            result.append(task)

    return {
        "status": "success",
        "engineer_id": engineer_id,
        "data": result,
    }

@app.get("/api/app/engineer/profile/{engineer_id}")
def app_engineer_profile(engineer_id: str):
    engineer = engineers_real.get(engineer_id)
    if not engineer:
        return {"status": "error", "message": "维修工不存在，请先在「我的」中登记信息"}

    return {
        "status": "success",
        "data": {
            "维修人员管理表": engineer_mgmt_view(engineer),
            "工单统计": engineer_order_stats(engineer_id),
        },
    }

@app.get("/api/app/engineer/orders")
def app_engineer_orders(engineer_id: str):
    engineer = engineers_real.get(engineer_id)
    if not engineer:
        return {"status": "error", "message": "维修工不存在"}

    return {
        "status": "success",
        "data": list_engineer_orders(engineer_id),
        "stats": engineer_order_stats(engineer_id),
    }

# ===============================
# PostgreSQL 数据库工具函数
# ===============================

import psycopg2
import psycopg2.extras
from contextlib import contextmanager

# PostgreSQL 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "mdispatch",
    "user": "postgres",
    "password": "ml030827"
}

@contextmanager
def get_db():
    """上下文管理器：自动处理数据库连接的获取和释放"""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def save_engineer_to_db(engineer):
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO engineers (
            engineer_id,
            name,
            phone,
            password,
            skill_brand,
            skill_model,
            work_status,
            latitude,
            longitude,
            update_time
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
            engineer["维修工ID"],
            engineer["维修工姓名"],
            engineer["联系电话"],
            engineer["密码"],
            engineer["技能品牌"],
            engineer["技能型号"],
            engineer["工作状态"],
            engineer["latitude"],
            engineer["longitude"],
            engineer["update_time"]
        ))

# ===============================
# 更新维修工GPS到PostgreSQL
# ===============================

def update_engineer_location_db(engineer):
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE engineers
        SET
            work_status = %s,
            latitude = %s,
            longitude = %s,
            update_time = %s
        WHERE engineer_id = %s
        """, (
            engineer["工作状态"],
            engineer["latitude"],
            engineer["longitude"],
            engineer["update_time"],
            engineer["维修工ID"]
        ))


# ===============================
# 保存工单到 PostgreSQL
# ===============================

def save_work_order_to_db(order):
    internal = order["内部维修工单表"]
    user = order["用户端维修工单表"]
    engineer_task = order["维修工窗口"]
    engineer_info = user.get("维修人员信息") or {}
    order_type = internal.get("工单类型", "报修")  # 获取工单类型

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO work_orders (
            work_order_id,
            alarm_time,
            user_name,
            user_phone,
            address,
            device_id,
            device_brand,
            device_model,
            fault_type,
            emergency_level,
            order_type,
            order_status,
            engineer_id,
            engineer_name,
            engineer_phone,
            distance,
            eta,
            user_notice,
            engineer_notice,
            remark,
            create_time,
            last_operation_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (work_order_id) DO UPDATE SET
            alarm_time = EXCLUDED.alarm_time,
            user_name = EXCLUDED.user_name,
            user_phone = EXCLUDED.user_phone,
            address = EXCLUDED.address,
            device_id = EXCLUDED.device_id,
            device_brand = EXCLUDED.device_brand,
            device_model = EXCLUDED.device_model,
            fault_type = EXCLUDED.fault_type,
            emergency_level = EXCLUDED.emergency_level,
            order_type = EXCLUDED.order_type,
            order_status = EXCLUDED.order_status,
            engineer_id = EXCLUDED.engineer_id,
            engineer_name = EXCLUDED.engineer_name,
            engineer_phone = EXCLUDED.engineer_phone,
            distance = EXCLUDED.distance,
            eta = EXCLUDED.eta,
            user_notice = EXCLUDED.user_notice,
            engineer_notice = EXCLUDED.engineer_notice,
            remark = EXCLUDED.remark,
            create_time = EXCLUDED.create_time,
            last_operation_time = EXCLUDED.last_operation_time
        """, (
            internal["工单ID"],
            internal["报修/报警时间"],
            internal["用户姓名"],
            internal["联系电话"],
            internal["地址"],
            internal["设备ID"],
            internal["设备品牌"],
            internal["设备型号"],
            internal["故障类型"],
            internal["紧急程度"],
            order_type,
            internal["工单状态"],
            engineer_task["维修工ID"],
            engineer_task["维修工姓名"],
            engineer_task["联系电话"],
            engineer_info.get("距离") or engineer_task.get("距离"),
            engineer_info.get("预计到达时间") or engineer_task.get("预计到达时间"),
            user.get("用户通知", ""),
            engineer_task["维修工通知"],
            internal["备注"],
            internal.get("下单时间", ""),
            internal.get("最后操作时间", "")
        ))


def save_user_to_db(profile):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO users (
            phone, name, password, province, city, address_detail, full_address
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (phone) DO UPDATE SET
            name = EXCLUDED.name,
            password = EXCLUDED.password,
            province = EXCLUDED.province,
            city = EXCLUDED.city,
            address_detail = EXCLUDED.address_detail,
            full_address = EXCLUDED.full_address
        """, (
            profile["联系电话"],
            profile["用户姓名"],
            profile.get("密码", ""),
            profile.get("省份", ""),
            profile.get("城市", ""),
            profile.get("详细地址", ""),
            profile["地址"],
        ))


def get_user_from_db(phone):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM users WHERE phone = %s", (phone,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "用户姓名": row["name"],
            "联系电话": row["phone"],
            "密码": row.get("password", ""),
            "省份": row["province"] or "",
            "城市": row["city"] or "",
            "详细地址": row["address_detail"] or "",
            "地址": row["full_address"] or "",
        }


def delete_user_from_db(phone):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE phone = %s", (phone,))


def load_devices_from_db(user_phone):
    """从数据库加载指定用户的设备"""
    devices = []
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT * FROM devices WHERE user_phone = %s", (user_phone,))
            rows = cursor.fetchall()
            for row in rows:
                devices.append({
                    "device_id": row["device_id"],
                    "brand": row["brand"] or "",
                    "model": row["model"] or "",
                    "device_type": row["device_type"] or "",
                    "user_name": row["user_name"] or "",
                    "user_phone": row["user_phone"] or "",
                    "address": row["address"] or "",
                    "status": row["status"] or "正常",
                    "install_time": row["install_time"] or "",
                })
    except Exception as e:
        print(f"Error loading devices from DB: {e}")
    return devices


def load_users_from_db():
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
            for row in rows:
                user_profiles[row["phone"]] = {
                    "用户姓名": row["name"],
                    "联系电话": row["phone"],
                    "密码": row.get("password", ""),
                    "省份": row["province"] or "",
                    "城市": row["city"] or "",
                    "详细地址": row["address_detail"] or "",
                    "地址": row["full_address"] or "",
                }
    except psycopg2.Error:
        pass


def load_engineers_from_db():
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT * FROM engineers")
            rows = cursor.fetchall()
            for row in rows:
                engineers_real[row["engineer_id"]] = {
                    "维修工ID": row["engineer_id"],
                    "维修工姓名": row["name"],
                    "联系电话": row["phone"],
                    "密码": row["password"],
                    "技能品牌": row["skill_brand"],
                    "技能型号": row["skill_model"],
                    "工作状态": row["work_status"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "update_time": row["update_time"],
                }
    except psycopg2.Error:
        pass


def load_devices_from_db():
    """从工单表中提取设备信息"""
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            # 从工单表中提取所有唯一的设备
            cursor.execute("""
                SELECT DISTINCT 
                    device_id, device_brand, device_model,
                    user_name, address, user_phone
                FROM work_orders
                WHERE device_id IS NOT NULL
            """)
            rows = cursor.fetchall()
            for row in rows:
                device_id = row["device_id"]
                # 如果设备已经存在，跳过
                if device_id in devices_registry:
                    continue
                devices_registry[device_id] = {
                    "设备ID": device_id,
                    "设备名称": f"{row['device_brand'] or ''} {row['device_model'] or ''}".strip() or device_id,
                    "品牌": row["device_brand"] or "",
                    "型号": row["device_model"] or "",
                    "设备类型": "电梯",  # 默认值
                    "设备状态": "正常",
                    "所属用户姓名": row["user_name"] or "",
                    "绑定地址": row["address"] or "",
                    "安装地址": row["address"] or "",  # 兼容前端字段
                    "联系电话": row["user_phone"] or "",
                    "安装时间": "",
                    "latitude": None,
                    "longitude": None,
                }
    except psycopg2.Error as e:
        print("Error loading devices:", e)
        pass


def load_work_orders_from_db():
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT * FROM work_orders")
            rows = cursor.fetchall()
            for row in rows:
                work_order_id = row["work_order_id"]
                order = {
                    "内部维修工单表": {
                        "工单ID": row["work_order_id"],
                        "报修/报警时间": row["alarm_time"],
                        "用户姓名": row["user_name"],
                        "联系电话": row["user_phone"],
                        "地址": row["address"],
                        "设备ID": row["device_id"],
                        "设备品牌": row["device_brand"],
                        "设备型号": row["device_model"],
                        "故障类型": row["fault_type"],
                        "紧急程度": row["emergency_level"],
                        "工单类型": row.get("order_type", "报修"),
                        "工单状态": row["order_status"],
                        "备注": row["remark"],
                        "下单时间": row.get("create_time", ""),
                        "最后操作时间": row.get("last_operation_time", ""),
                    },
                    "用户端维修工单表": {
                        "工单ID": row["work_order_id"],
                        "工单类型": row.get("order_type", "报修"),
                        "用户信息": {
                            "用户姓名": row["user_name"],
                            "联系电话": row["user_phone"],
                            "地址": row["address"],
                        },
                        "设备信息": {
                            "设备ID": row["device_id"],
                            "设备品牌": row["device_brand"],
                            "设备型号": row["device_model"],
                            "设备类型": "电梯",
                        },
                        "故障类型": row["fault_type"],
                        "工单状态": row["order_status"],
                        "维修人员信息": {
                            "维修工姓名": row["engineer_name"],
                            "维修工电话": row["engineer_phone"],
                            "预计到达时间": row["eta"],
                            "距离": row["distance"],
                        },
                        "用户通知": row["user_notice"],
                        "下单时间": row.get("create_time", ""),
                        "最后操作时间": row.get("last_operation_time", ""),
                    },
                    "维修工窗口": {
                        "工单ID": row["work_order_id"],
                        "维修工ID": row["engineer_id"],
                        "维修工姓名": row["engineer_name"],
                        "联系电话": row["engineer_phone"],
                        "任务状态": row["order_status"],
                        "工单类型": row.get("order_type", "报修"),
                        "故障类型": row["fault_type"],
                        "紧急程度": row["emergency_level"],
                        "设备ID": row["device_id"],
                        "设备品牌": row["device_brand"],
                        "设备型号": row["device_model"],
                        "设备地址": row["address"],
                        "距离": row["distance"],
                        "预计到达时间": row["eta"],
                        "维修工通知": row["engineer_notice"],
                        "下单时间": row.get("create_time", ""),
                        "最后操作时间": row.get("last_operation_time", ""),
                    },
                    "设备管理表": {},
                    "AI派单结果": {},
                }
                work_orders[work_order_id] = order
    except psycopg2.Error:
        pass


@app.on_event("startup")
def startup_load_data():
    load_users_from_db()
    load_engineers_from_db()
    load_devices_from_db()
    load_work_orders_from_db()

# ===============================
# WebSocket 实时位置追踪
# ===============================

@app.websocket("/ws/track/{work_order_id}")
async def websocket_track(websocket: WebSocket, work_order_id: str):
    """WebSocket 端点：用于实时追踪维修工位置"""
    await websocket.accept()
    
    if work_order_id not in active_connections:
        active_connections[work_order_id] = []
    active_connections[work_order_id].append(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            # 接收维修工位置更新并广播给所有关注该工单的客户端
            if data.get("type") == "location_update":
                # 动态计算距离和预计到达时间
                order = work_orders.get(work_order_id)
                distance_km = None
                eta_minutes = None
                
                if order:
                    # 获取用户地址的经纬度（从设备地址）
                    device = order.get("设备管理表", {})
                    device_lat = device.get("latitude")
                    device_lon = device.get("longitude")
                    
                    # 如果设备没有经纬度，使用工单创建时的经纬度
                    if device_lat is None or device_lon is None:
                        # 从 AI 派单结果中获取（工单创建时保存的）
                        ai_result = order.get("AI 派单结果", {})
                        device_lat = ai_result.get("device_lat")
                        device_lon = ai_result.get("device_lon")
                    
                    # 计算维修工与用户之间的距离
                    if device_lat and device_lon:
                        engineer_lat = data.get("latitude")
                        engineer_lon = data.get("longitude")
                        if engineer_lat and engineer_lon:
                            distance_km = calc_distance_km(
                                device_lat, device_lon,
                                engineer_lat, engineer_lon
                            )
                            eta_minutes = max(3, int(distance_km * 3))
                
                await broadcast_location(work_order_id, {
                    "type": "location_update",
                    "work_order_id": work_order_id,
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "engineer_id": data.get("engineer_id"),
                    "engineer_name": data.get("engineer_name"),
                    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "distance_km": distance_km,
                    "eta_minutes": eta_minutes,
                })
    except WebSocketDisconnect:
        active_connections[work_order_id].remove(websocket)
        if not active_connections[work_order_id]:
            del active_connections[work_order_id]

# ===============================
# 预约维修功能
# ===============================

class BookRequest(BaseModel):
    user_phone: str
    device_id: str
    fault_type: str
    remark: str = ""
    booking_time: str  # 预约时间，格式：YYYY-MM-DD HH:mm

@app.post("/api/user/order/book")
def book_order(req: BookRequest):
    """创建预约工单"""
    now = datetime.now()
    booking_dt = datetime.strptime(req.booking_time, "%Y-%m-%d %H:%M")
    
    if booking_dt < now:
        return {"status": "error", "message": "预约时间不能早于当前时间"}
    
    # 检查是否有重复预约（同一设备在同一时间段）
    for order_id, order in work_orders.items():
        if order["内部维修工单表"]["设备ID"] == req.device_id:
            order_time = order["内部维修工单表"].get("下单时间", "")
            if order_time:
                try:
                    existing_dt = datetime.strptime(order_time, "%Y-%m-%d %H:%M:%S")
                    # 如果存在30分钟内的预约，拒绝新预约
                    if abs((existing_dt - booking_dt).total_seconds()) < 1800:
                        return {"status": "error", "message": "该设备在该时间段已有预约"}
                except:
                    pass
    
    # 生成预约工单ID
    work_order_id = f"BK{booking_dt.strftime('%Y%m%d%H%M')}{req.device_id[-4:]}"
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # 创建预约工单（状态为待预约）
    order = {
        "内部维修工单表": {
            "工单ID": work_order_id,
            "报修/报警时间": now_str,
            "下单时间": now_str,
            "最后操作时间": now_str,
            "用户姓名": user_profiles.get(req.user_phone, {}).get("用户姓名", ""),
            "联系电话": req.user_phone,
            "地址": user_profiles.get(req.user_phone, {}).get("地址", ""),
            "设备ID": req.device_id,
            "设备品牌": devices_registry.get(req.device_id, {}).get("设备品牌", ""),
            "设备型号": devices_registry.get(req.device_id, {}).get("设备型号", ""),
            "故障类型": req.fault_type,
            "紧急程度": "普通",
            "工单类型": "报修",
            "工单状态": "待预约",
            "备注": f"预约维修 - {req.booking_time} - {req.remark}",
            "预约时间": req.booking_time,
        },
        "用户端维修工单表": {
            "工单ID": work_order_id,
            "工单类型": "报修",
            "工单状态": "待预约",
            "下单时间": now_str,
            "最后操作时间": now_str,
            "故障类型": req.fault_type,
            "预约时间": req.booking_time,
            "用户信息": user_profiles.get(req.user_phone, {}),
            "设备信息": devices_registry.get(req.device_id, {}),
            "维修人员信息": {},
            "用户通知": f"预约成功！您的工单将在 {req.booking_time} 进行维修",
        },
        "维修工窗口": {
            "工单ID": work_order_id,
            "维修工ID": "未分配",
            "维修工姓名": "未分配",
            "联系电话": "",
            "任务状态": "待预约",
            "工单类型": "报修",
            "故障类型": req.fault_type,
            "紧急程度": "普通",
            "设备ID": req.device_id,
            "设备品牌": devices_registry.get(req.device_id, {}).get("设备品牌", ""),
            "设备型号": devices_registry.get(req.device_id, {}).get("设备型号", ""),
            "设备地址": user_profiles.get(req.user_phone, {}).get("地址", ""),
            "距离": "",
            "预计到达时间": "",
            "维修工通知": "",
            "下单时间": now_str,
            "最后操作时间": now_str,
        },
        "设备管理表": devices_registry.get(req.device_id, {}),
        "AI派单结果": {},
    }
    
    work_orders[work_order_id] = order
    save_work_order_to_db(order)
    
    return {
        "status": "success",
        "message": "预约成功",
        "data": {
            "工单ID": work_order_id,
            "预约时间": req.booking_time,
        },
    }

@app.get("/api/user/booking/time-slots")
def get_booking_time_slots(device_id: Optional[str] = None):
    """获取可用的预约时间段"""
    now = datetime.now()
    slots = []
    
    # 生成未来7天的可用时间段（每30分钟一个时段）
    for day_offset in range(7):
        target_date = now + timedelta(days=day_offset)
        # 工作时间：9:00 - 18:00
        for hour in range(9, 18):
            for minute in [0, 30]:
                slot_time = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if slot_time > now:
                    # 检查该时段是否已有预约
                    is_available = True
                    if device_id:
                        for order_id, order in work_orders.items():
                            if order["内部维修工单表"].get("设备ID") == device_id:
                                booking_time = order["内部维修工单表"].get("预约时间", "")
                                if booking_time:
                                    try:
                                        existing_dt = datetime.strptime(booking_time, "%Y-%m-%d %H:%M")
                                        if abs((existing_dt - slot_time).total_seconds()) < 1800:
                                            is_available = False
                                            break
                                    except:
                                        pass
                    
                    if is_available:
                        slots.append({
                            "time": slot_time.strftime("%Y-%m-%d %H:%M"),
                            "label": slot_time.strftime("%m月%d日 %H:%M"),
                            "available": is_available,
                        })
    
    return {
        "status": "success",
        "data": slots,
    }

