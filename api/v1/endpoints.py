# api/v1/endpoints.py
import asyncio
import time
from collections import deque
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, Request

from bot_config import (BOT_NICKNAME, BOT_QQ_ID, CRITICAL_TARGET_LIST,
                        DIGESTION_BUFFER_SIZE, QUICK_REPLY_COOLDOWN_SECONDS,
                        RECENT_MESSAGES_BUFFER_SIZE, TARGET_GROUP_IDS)
from core.llm_service import (digest_messages_in_background,
                              generate_fast_track_reply)
from core.onebot_actions import send_segmented_message
# 导入新的共享状态模块
from core.state import (last_speech_timestamps, recent_contexts_by_group,
                        slow_track_buffers_by_group)

router = APIRouter()

# --- 缓冲逻辑和状态管理现在从 core.state 导入 ---


async def process_fast_track_message(target_message: dict, recent_history: List[dict]):
    """
    真实处理快速通道的函数。
    它调用LLM服务生成回复，然后调用动作服务发送消息。
    """
    print(f"【快速轨道】: 开始处理用户 {target_message['user_id']} 的消息...")

    # 1. 调用 LLM 服务生成回复
    reply_text = await generate_fast_track_reply(target_message, recent_history)

    # 2. 如果 LLM 决定回复，则发送消息并记录自己的发言
    if reply_text:
        group_id = target_message.get("group_id")
        user_id_to_at = target_message.get("user_id")

        await send_segmented_message(group_id, user_id_to_at, reply_text)

        # --- 新增：“回声”机制 ---
        # 在发送成功后，手动构造一条消息来代表我们自己的发言
        # 并将其添加到全局上下文中，以便未来的对话能够理解
        bot_message = {
            "time": int(time.time()),
            "self_id": BOT_QQ_ID,
            "post_type": "message",
            "message_type": "group",
            "sub_type": "normal",
            "message_id": -1,  # 使用一个特殊值表示是内部记录
            "group_id": group_id,
            "user_id": BOT_QQ_ID,
            "sender": {
                "user_id": BOT_QQ_ID,
                "nickname": BOT_NICKNAME,
                "role": "member",
            },
            "message": [{"type": "text", "data": {"text": reply_text}}],
            "raw_message": reply_text,
        }
        # 将这个“伪造的”机器人发言消息，添加到全局上下文中
        if group_id in recent_contexts_by_group:
            recent_contexts_by_group[group_id].append(bot_message)
        print(f"【回声】: 已将机器人自己的发言记录到群 {group_id} 的上下文中。")

    print("【快速轨道】: 任务完成。")


@router.post("/messages")
async def handle_message(request: Request, background_tasks: BackgroundTasks):
    """
    接收所有群消息的入口点。
    实现“分发器”逻辑。
    """
    message_data = await request.json()

    # 首先，只处理目标群组的消息
    if message_data.get("group_id") not in TARGET_GROUP_IDS:
        return {"status": "ignored", "reason": "not target group"}

    user_id = message_data.get("user_id")
    group_id = message_data.get("group_id")  # 获取group_id

    # 统一将消息添加到对应群组的滚动上下文中
    if group_id not in recent_contexts_by_group:
        recent_contexts_by_group[group_id] = deque(maxlen=RECENT_MESSAGES_BUFFER_SIZE)
    recent_contexts_by_group[group_id].append(message_data)

    # --- 双轨分发逻辑 ---
    if user_id in CRITICAL_TARGET_LIST:
        current_time = time.time()
        last_speech_time = last_speech_timestamps.get(user_id, 0)

        # 检查冷却时间
        if current_time - last_speech_time < QUICK_REPLY_COOLDOWN_SECONDS:
            print(f"【冷却中】: 用户 {user_id} 发言过于频繁，本次不触发快速回复。")
            # 即使不回复，也要更新发言时间戳
            last_speech_timestamps[user_id] = current_time
            return {"status": "ok", "track": "fast_cooldown"}

        # 更新时间戳并触发回复
        last_speech_timestamps[user_id] = current_time

        # 快速轨道：立即将处理任务放入后台，并快速响应
        print(f"检测到关键目标 {user_id}，启动快速反应轨道。")
        # 将目标消息和当前的上下文历史一起传递给后台任务
        background_tasks.add_task(
            process_fast_track_message,
            message_data,
            list(recent_contexts_by_group[group_id]),  # 传递deque的当前快照
        )
        return {"status": "ok", "track": "fast"}
    else:
        # 认知轨道：将消息存入对应群组的慢速通道缓冲区
        if group_id not in slow_track_buffers_by_group:
            slow_track_buffers_by_group[group_id] = []

        slow_buffer = slow_track_buffers_by_group[group_id]
        slow_buffer.append(message_data)

        # 即使是普通用户，也更新他们的最后发言时间
        last_speech_timestamps[user_id] = time.time()

        # 检查缓冲区是否需要“消化”
        if len(slow_buffer) >= DIGESTION_BUFFER_SIZE:
            print("缓冲区已满，启动后台消化任务。")
            # 把当前缓冲区的所有内容交给后台任务，然后清空
            background_tasks.add_task(digest_messages_in_background, list(slow_buffer))
            slow_buffer.clear()

        return {"status": "ok", "track": "slow"}
