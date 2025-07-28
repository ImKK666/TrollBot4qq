# services/topic_service.py
from typing import Dict

from database import crud

async def add_topic(
    group_id: int,
    start_time: int,
    end_time: int,
    theme: str,
    summary: str,
    participants_viewpoints: Dict[int, str]
):
    """
    (异步服务) 添加一个新的对话主题总结。
    """
    crud.add_conversation_topic(
        group_id=group_id,
        start_time=start_time,
        end_time=end_time,
        theme=theme,
        summary=summary,
        participants_viewpoints=participants_viewpoints
    ) 