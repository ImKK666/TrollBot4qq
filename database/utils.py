# database/utils.py
import os
import shutil

from bot_config import PROFILE_DB_PATH
from services.graphrag_manager import reset_graphrag

from .models import initialize_database


def reset_all_databases():
    """
    危险操作：清空并重置所有数据库（关系型和向量型）。
    """
    print("--- 正在重置所有数据库 ---")

    # 1. 重置关系型数据库 (SQLite)
    if os.path.exists(PROFILE_DB_PATH):
        try:
            os.remove(PROFILE_DB_PATH)
            print(f"已删除旧的关系型数据库文件: {PROFILE_DB_PATH}")
        except OSError as e:
            print(f"删除SQLite数据库文件失败: {e}")

    # 2. 重置 GraphRAG 记忆库
    print("正在重置 GraphRAG 记忆库...")
    reset_graphrag()
    print("GraphRAG 记忆库已清空。")

    # 3. 重新初始化数据库表结构
    print("正在重新初始化数据库表结构...")
    initialize_database()
    print("--- 数据库重置完成 ---")
