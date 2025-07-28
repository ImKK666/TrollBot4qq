# core/scheduler.py
import asyncio
import time
import random
from datetime import datetime

from config import (
    PROACTIVE_ATTACK_INTERVAL_SECONDS,
    PROACTIVE_ATTACK_INACTIVITY_HOURS,
    PROACTIVE_ATTACK_ACTIVE_TIME_RANGE,
    TARGET_GROUP_IDS,
    CRITICAL_TARGET_LIST
)
# 从新的状态模块导入共享的时间戳字典
from core.state import last_speech_timestamps
from services.memory_service import search_relevant_memories
from core.llm_service import generate_proactive_attack_message
from core.onebot_actions import send_group_message


async def proactive_attack_task():
    """
    定时任务，用于检查并发起主动攻击。
    """
    while True:
        await asyncio.sleep(PROACTIVE_ATTACK_INTERVAL_SECONDS)
        
        # 1. 检查当前是否在活跃时间内
        now = datetime.now()
        start_hour, end_hour = PROACTIVE_ATTACK_ACTIVE_TIME_RANGE
        if not (start_hour <= now.hour < end_hour):
            print(f"【定时任务】: 当前时间 ({now.hour}点) 不在活跃时间段内，跳过本次检查。")
            continue
            
        print("【定时任务】: 开始检查可主动攻击的目标...")

        # 2. 遍历所有需要被“关怀”的目标
        for user_id in CRITICAL_TARGET_LIST:
            last_speech = last_speech_timestamps.get(user_id, 0)
            inactivity_seconds = time.time() - last_speech
            
            # 3. 检查沉默时间是否足够长
            if inactivity_seconds > PROACTIVE_ATTACK_INACTIVITY_HOURS * 3600:
                print(f"【定时任务】: 发现目标 {user_id} 已沉默超过 {PROACTIVE_ATTACK_INACTIVITY_HOURS} 小时。")

                # 4. 随机抽取一条该用户的黑历史
                # 我们通过一个宽泛的查询（比如他自己的昵称或ID）来随机捞取记忆
                memories = await search_relevant_memories(str(user_id), user_id=user_id)
                if not memories:
                    print(f"【定时任务】: 未找到用户 {user_id} 的任何黑历史，无法攻击。")
                    continue
                
                # 随机选一条记忆作为“弹药”
                chosen_memory = random.choice(memories)

                # 5. 生成攻击性发言
                attack_message = await generate_proactive_attack_message(chosen_memory)

                # 6. 发动攻击 (随机选择一个目标群组)
                if attack_message:
                    target_group_id = random.choice(TARGET_GROUP_IDS)
                    print(f"【定时任务】: 决定在群 {target_group_id} 对用户 {user_id} 发动攻击！")
                    await send_group_message(target_group_id, attack_message)
                    
                    # 攻击后，更新其“最后发言时间”为当前，防止短时间内连续攻击
                    last_speech_timestamps[user_id] = time.time()
                    
                    # 每次只攻击一个人，避免刷屏
                    break 
        
        print("【定时任务】: 本轮检查结束。") 