from fastmcp import FastMCP
from app_dispatch import (
    work_orders,
    devices_registry,
    engineers_real,
    AIDispatchRequest,
    ai_control_dispatch,
    ai_control_order_status,
    ai_control_orders,
    AlarmRequest,
    alarm,
    select_nearest_engineer,
    build_user_order_table,
)

mcp = FastMCP("AI派单系统MCP服务")

@mcp.tool
def create_order(fault_type: str, fault_description: str, device_id: str, order_type: str = "报警") -> dict:
    """
    创建维修派单工单，当检测到设备故障时使用
    
    参数:
        fault_type: 故障类型：困人、机器失灵、异响、门故障、停运、定期保养、其他
        fault_description: 故障详细描述
        device_id: 设备ID
        order_type: 工单类型：报警/报修（默认：报警）
    """
    try:
        req = AIDispatchRequest(
            fault_type=fault_type,
            fault_description=fault_description,
            device_id=device_id,
            order_type=order_type
        )
        return ai_control_dispatch(req)
    except Exception as e:
        return {"status": "error", "message": f"MCP调用失败: {str(e)}"}

@mcp.tool
def get_order(work_order_id: str) -> dict:
    """
    查询单个工单的详细状态
    
    参数:
        work_order_id: 工单ID
    """
    try:
        return ai_control_order_status(work_order_id)
    except Exception as e:
        return {"status": "error", "message": f"MCP调用失败: {str(e)}"}

@mcp.tool
def list_orders(phone: str, status: str = None, start_time: str = None) -> dict:
    """
    查询工单列表，可以按手机号、状态、时间筛选
    
    参数:
        phone: 用户手机号（必需）
        status: 工单状态（可选）
        start_time: 开始时间，格式: YYYY-MM-DD HH:MM:SS（可选）
    """
    try:
        return ai_control_orders(phone=phone, status=status, start_time=start_time)
    except Exception as e:
        return {"status": "error", "message": f"MCP调用失败: {str(e)}"}

@mcp.tool
def list_all_orders() -> dict:
    """
    获取所有工单列表（管理员权限）
    
    返回:
        所有工单的完整信息
    """
    try:
        return {
            "status": "success",
            "message": "查询成功",
            "data": list(work_orders.values()),
            "count": len(work_orders)
        }
    except Exception as e:
        return {"status": "error", "message": f"MCP调用失败: {str(e)}"}

@mcp.tool
def list_engineers() -> dict:
    """
    获取所有维修工列表
    
    返回:
        所有维修工的信息，包括ID、姓名、联系电话、技能、工作状态等
    """
    try:
        result = {}
        for engineer_id, engineer in engineers_real.items():
            result[engineer_id] = {
                "engineer_id": engineer.get("engineer_id") or engineer.get("维修工ID") or engineer_id,
                "name": engineer.get("name") or engineer.get("维修工姓名") or "未知",
                "phone": engineer.get("phone") or engineer.get("联系电话") or "",
                "skill_brand": engineer.get("skill_brand") or engineer.get("技能品牌") or "",
                "skill_model": engineer.get("skill_model") or engineer.get("技能型号") or "",
                "status": engineer.get("status") or engineer.get("工作状态") or "空闲",
                "latitude": engineer.get("latitude"),
                "longitude": engineer.get("longitude"),
            }
        return {
            "status": "success",
            "message": "查询成功",
            "data": result,
            "count": len(result)
        }
    except Exception as e:
        return {"status": "error", "message": f"MCP调用失败: {str(e)}"}

@mcp.tool
def list_devices() -> dict:
    """
    获取所有设备列表
    
    返回:
        所有设备的信息，包括设备ID、品牌、型号、类型、状态等
    """
    try:
        return {
            "status": "success",
            "message": "查询成功",
            "data": list(devices_registry.values()),
            "count": len(devices_registry)
        }
    except Exception as e:
        return {"status": "error", "message": f"MCP调用失败: {str(e)}"}

@mcp.tool
def get_device_info(device_id: str) -> dict:
    """
    获取单个设备的详细信息
    
    参数:
        device_id: 设备ID
    
    返回:
        设备的完整信息，包括品牌、型号、类型、绑定用户等
    """
    try:
        device = devices_registry.get(device_id)
        if not device:
            return {"status": "error", "message": "设备不存在"}
        
        return {
            "status": "success",
            "message": "查询成功",
            "data": {
                "device_id": device.get("设备ID", device_id),
                "device_type": device.get("设备类型", ""),
                "device_brand": device.get("设备品牌", ""),
                "device_model": device.get("设备型号", ""),
                "device_status": device.get("设备状态", ""),
                "install_time": device.get("安装时间", ""),
                "user_name": device.get("所属用户姓名", ""),
                "user_phone": device.get("联系电话", ""),
                "address": device.get("绑定地址", ""),
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"MCP调用失败: {str(e)}"}

if __name__ == "__main__":
    print("=== 启动AI派单MCP服务 ===")
    print("服务地址: http://0.0.0.0:8001/mcp")
    print("绑定地址: 0.0.0.0 (允许外部访问)")
    print("使用 HTTP 传输启动...")
    print("=" * 50)
    
    mcp.run(transport="http", host="0.0.0.0", port=8001)