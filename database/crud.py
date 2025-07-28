# database/crud.py
import sqlite3
import json
import time
from typing import Optional, Dict, Any, List

from config import PROFILE_DB_PATH

def get_db_connection():
    """获取数据库连接的辅助函数"""
    conn = sqlite3.connect(PROFILE_DB_PATH)
    conn.row_factory = sqlite3.Row  # 让查询结果可以像字典一样访问列
    return conn

# --- User Profile 的 CRUD 操作 ---

def get_or_create_user_profile(user_id: int, nickname: str) -> Dict[str, Any]:
    """
    获取用户档案，如果不存在则创建一个新的。
    这是最常用的函数之一。
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if user:
        # 用户存在，检查昵称是否需要更新
        user_dict = dict(user) # 将 Row 对象转换为字典
        if user_dict['current_nickname'] != nickname:
            user_dict['current_nickname'] = nickname
            # 将旧昵称添加到历史记录中
            historical = json.loads(user_dict.get('historical_nicknames') or '[]')
            if nickname not in historical:
                historical.append(user_dict['current_nickname']) # 应该是添加旧的
                update_user_profile(user_id, {
                    "current_nickname": nickname, 
                    "historical_nicknames": json.dumps(historical)
                })
        conn.close()
        # 解析 JSON 字段
        user_dict['aliases'] = json.loads(user_dict.get('aliases') or '[]')
        user_dict['historical_nicknames'] = json.loads(user_dict.get('historical_nicknames') or '[]')
        user_dict['attitudes'] = json.loads(user_dict.get('attitudes') or '{}') # 新增：解析attitudes
        return user_dict
    else:
        # 用户不存在，创建新记录
        new_user = {
            "user_id": user_id,
            "current_nickname": nickname,
            "historical_nicknames": json.dumps([]),
            "aliases": json.dumps([]),
            "summary": "新用户，暂无画像。",
            "attitudes": json.dumps({}), # 新增：初始化attitudes
            "last_updated": int(time.time())
        }
        cursor.execute('''
            INSERT INTO user_profiles (user_id, current_nickname, historical_nicknames, aliases, summary, attitudes, last_updated)
            VALUES (:user_id, :current_nickname, :historical_nicknames, :aliases, :summary, :attitudes, :last_updated)
        ''', new_user)
        conn.commit()
        conn.close()
        # 返回刚创建的用户信息（已解析JSON）
        new_user['aliases'] = []
        new_user['historical_nicknames'] = []
        new_user['attitudes'] = {} # 新增：返回解析后的attitudes
        return new_user

def update_user_profile(user_id: int, updates: Dict[str, Any]):
    """
    通用更新函数，可以更新一个或多个字段。
    `updates` 是一个包含要更新的列名和新值的字典。
    """
    if not updates:
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 动态构建 SQL UPDATE 语句
    update_fields = ", ".join([f"{key} = ?" for key in updates.keys()])
    sql = f"UPDATE user_profiles SET {update_fields}, last_updated = ? WHERE user_id = ?"
    
    # 准备参数
    values = list(updates.values())
    values.append(int(time.time()))
    values.append(user_id)
    
    cursor.execute(sql, tuple(values))
    conn.commit()
    conn.close()
    print(f"已更新用户 {user_id} 的档案: {updates}")


def add_alias_to_user(user_id: int, alias: str):
    """
    为一个用户添加一个新的外号，并确保不重复。
    """
    # 先获取当前的外号列表
    profile = get_or_create_user_profile(user_id, "") # 此时昵称不重要
    current_aliases = profile['aliases'] # 已经解析为 list
    
    if alias not in current_aliases:
        current_aliases.append(alias)
        # 将更新后的 list 转换回 JSON 字符串存入数据库
        update_user_profile(user_id, {"aliases": json.dumps(current_aliases)})
        print(f"成功为用户 {user_id} 添加外号: {alias}")

# --- Conversation Topic 的 CRUD 操作 ---

def add_conversation_topic(
    group_id: int,
    start_time: int,
    end_time: int,
    theme: str,
    summary: str,
    participants_viewpoints: Dict[int, str]
):
    """将一个分析后的话题保存到数据库中"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    avg_time = (start_time + end_time) // 2
    
    cursor.execute('''
        INSERT INTO conversation_topics 
        (group_id, start_time, end_time, avg_time, theme, summary, participants_viewpoints)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (group_id, start_time, end_time, avg_time, theme, summary, json.dumps(participants_viewpoints)))
    
    conn.commit()
    conn.close()
    print(f"成功添加新的对话主题: {theme}")


def update_user_attitudes(user_id: int, target_user_id: int, attitude_desc: str):
    """
    更新或添加一个用户对另一个用户的态度。
    这是一个原子操作，只更新特定目标用户的态度。
    """
    # 1. 获取当前用户的完整档案，包括已有的态度
    # 注意：这里需要一个有效的昵称，但在这个场景下它不重要，所以传个空字符串
    profile = get_or_create_user_profile(user_id, "")
    current_attitudes = profile.get('attitudes', {}) # 确保 attitudes 是一个字典

    # 2. 更新对特定目标的态度
    current_attitudes[str(target_user_id)] = attitude_desc # JSON的key必须是字符串

    # 3. 将更新后的整个 attitudes 对象写回数据库
    update_user_profile(user_id, {"attitudes": json.dumps(current_attitudes)})
    print(f"已更新用户 {user_id} 对 {target_user_id} 的态度: {attitude_desc}")