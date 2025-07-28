# services/profile_service.py
from typing import Dict, Any, List

# 从 crud 模块导入底层的数据库操作函数
from database import crud

async def get_user_profile(user_id: int, nickname: str) -> Dict[str, Any]:
    """
    获取指定用户的完整档案。
    这是上层应用（如endpoints）应该调用的函数。
    """
    # crud 函数是同步的，但在 FastAPI 的异步函数中直接调用它们是可以的
    # FastAPI 会在线程池中运行它们，不会阻塞事件循环
    profile = crud.get_or_create_user_profile(user_id, nickname)
    return profile

async def update_user_summary(user_id: int, summary: str):
    """
    更新用户的画像总结。
    """
    crud.update_user_profile(user_id, {"summary": summary})

async def add_new_alias(user_id: int, alias: str):
    """
    为用户添加一个新外号。
    """
    # 这是一个很好的封装例子，隐藏了数据库实现的细节
    crud.add_alias_to_user(user_id, alias)

async def update_attitudes(user_id: int, target_user_id: int, attitude_desc: str):
    """
    (异步服务) 更新用户对另一个用户的态度。
    """
    crud.update_user_attitudes(user_id, target_user_id, attitude_desc)