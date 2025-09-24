# core/onebot_listener.py
import asyncio
import json

import httpx  # 使用 httpx 库来发送异步 HTTP 请求
import websockets

from bot_config import ONEBOT_WS_URL

API_SERVER_URL = "http://127.0.0.1:8000/api/v1/messages"  # 我们自己服务器的地址


async def listen_for_events():
    """连接到 OneBot 并将事件转发到我们的 API 服务器。"""
    print(f"开始监听 OneBot 事件于 {ONEBOT_WS_URL}...")
    async with websockets.connect(ONEBOT_WS_URL) as websocket:
        print("OneBot 连接成功！")
        async for message in websocket:
            try:
                data = json.loads(message)
                print(f"收到事件: {data}")

                # 我们只关心群消息，其他事件直接忽略
                if (
                    data.get("post_type") == "message"
                    and data.get("message_type") == "group"
                ):

                    # 将消息发送到我们自己的后端进行处理
                    # 使用 httpx 异步发送，不会阻塞监听
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            API_SERVER_URL, json=data, timeout=10
                        )
                        # 只是为了调试，看看我们的服务器是否正确响应
                        if response.status_code != 200:
                            print(f"发送到API服务器失败: {response.text}")

            except Exception as e:
                print(f"处理事件时发生错误: {e}")


# 这个文件不再需要 if __name__ == "__main__":，因为它将由 main.py 启动
