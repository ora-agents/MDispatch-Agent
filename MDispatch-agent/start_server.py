# start_server.py - 派单系统启动脚本
# 版本: v1.0

import uvicorn
import sys

if __name__ == "__main__":
    print("=== 启动MDispatch-Agent AI工业派单系统 ===")
    print("服务地址: http://localhost:8000")
    print("静态页面: http://localhost:8000/static/user_app.html")
    print("API文档: http://localhost:8000/docs")
    print("=" * 50)
    
    # 启动FastAPI应用
    uvicorn.run(
        "app_dispatch:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # 开发模式，自动重载
    )
