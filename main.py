# main.py
import asyncio
import sys # 导入sys模块来读取命令行参数
from fastapi import FastAPI
import uvicorn

from api.v1 import endpoints as api_v1
from core.onebot_listener import listen_for_events
from core.scheduler import proactive_attack_task # 导入新的定时任务
from database.models import initialize_database
from database.utils import reset_all_databases # 导入重置函数

# 创建 FastAPI 应用实例
app = FastAPI(title="TrollBot Server")

# 注册我们的 API 路由
app.include_router(api_v1.router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """在服务器启动时执行"""
    print("服务器启动...")
    # 在应用启动时初始化数据库
    initialize_database()
    # 创建一个后台任务来运行 onebot 监听器
    asyncio.create_task(listen_for_events())
    # 创建另一个后台任务来运行主动攻击调度器
    asyncio.create_task(proactive_attack_task())

@app.get("/")
async def root():
    return {"message": "TrollBot is alive!"}

if __name__ == "__main__":
    # 检查命令行参数中是否包含 --reset-db 标志
    if "--reset-db" in sys.argv:
        reset_all_databases()

    # 使用 uvicorn 来运行 FastAPI 应用
    # reload=True 可以在你修改代码后自动重启服务器，非常适合开发
    # 注意：uvicorn的热重载本身就是一个包装器，它会重新启动一个新的进程。
    # 我们把重置逻辑放在uvicorn.run之前，可以确保重置只在手动启动时执行一次，
    # 而不会在每次代码变更导致热重载时都重复执行。
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)