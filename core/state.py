# core/state.py
from collections import deque
from typing import Deque, Dict, List

# --- 共享状态 ---

# 1. 按群组隔离的慢速通道（认知轨道）的临时缓冲区
slow_track_buffers_by_group: Dict[int, List[dict]] = {}

# 2. 按群组隔离的全局滚动上下文缓冲区，用于为快速通道提供稳定的近期对话历史
recent_contexts_by_group: Dict[int, Deque[dict]] = {}

# 3. 用于快速通道和定时任务的发言时间戳，实现冷却和主动攻击
last_speech_timestamps: Dict[int, float] = {}
