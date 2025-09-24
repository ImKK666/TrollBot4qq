# core/onebot_actions.py
import asyncio
import random
import re
from urllib.parse import urljoin

import httpx

# 直接从config中导入明确的HTTP API地址
from bot_config import ONEBOT_HTTP_URL


async def _send_single_message(group_id: int, message: str):
    """
    内部函数：负责单次调用HTTP API发送一条消息。
    """
    api_url = urljoin(ONEBOT_HTTP_URL, "/send_group_msg")
    payload = {"group_id": group_id, "message": message, "auto_escape": False}

    async with httpx.AsyncClient() as client:
        try:
            print(f"正在发送分段消息到群 {group_id}: {message}")
            response = await client.post(api_url, json=payload, timeout=10)
            response.raise_for_status()
            response_data = response.json()
            if response_data.get("status") == "ok":
                return True
            else:
                print(f"消息发送失败: {response_data.get('msg', '未知错误')}")
                return False
        except Exception as e:
            print(f"发送单条消息时发生错误: {e}")
            return False


async def send_segmented_message(group_id: int, user_id_to_at: int, full_message: str):
    """
    发送分段消息，模拟真人打字效果。
    只有第一条消息会@指定用户。
    """
    # 1. 使用正则表达式按标点符号分割句子，同时保留分隔符
    # 这个正则表达式会匹配句号、感叹号、问号和换行符
    sentences = re.split(r"([。！？\n])", full_message)
    # 将句子和其后的标点符号合并
    segments = ["".join(i) for i in zip(sentences[0::2], sentences[1::2])]
    # 如果有剩余的句子（没有结尾标点），也加上
    if len(sentences) % 2 == 1:
        segments.append(sentences[-1])

    # 过滤掉空的或只包含空白的段落
    segments = [s.strip() for s in segments if s and s.strip()]

    if not segments:
        print("警告：要发送的消息为空。")
        return

    # 2. 处理第一条消息，添加@
    first_segment = f"[CQ:at,qq={user_id_to_at}] {segments[0]}"

    # 3. 循环发送
    # 发送第一条
    if not await _send_single_message(group_id, first_segment):
        print("发送第一条分段消息失败，中止发送。")
        return

    # 依次发送剩余的
    for i in range(1, len(segments)):
        # 模拟打字延迟
        delay = random.uniform(1.5, 3.0)
        await asyncio.sleep(delay)

        if not await _send_single_message(group_id, segments[i]):
            print(f"发送第 {i+1} 条分段消息失败。")
            # 即使中间某条失败，也可以选择继续发送剩下的
            continue


async def send_group_message(group_id: int, message: str, at_sender: bool = True):
    """
    通过 OneBot v11 的 HTTP API 发送单条群消息。
    （保留此函数用于向后兼容或发送单条消息的场景）
    """
    await _send_single_message(group_id, message)
