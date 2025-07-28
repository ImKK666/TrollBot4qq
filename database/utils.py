# database/utils.py
import os
import shutil
from config import PROFILE_DB_PATH, MEMORY_DB_PATH
from services.memory_service import get_client as get_chroma_client
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
    
    # 2. 重置向量数据库 (ChromaDB)
    # 延迟加载确保客户端在使用时才初始化
    print("正在重置向量数据库...")
    try:
        chroma_client = get_chroma_client()
        chroma_client.reset() 
        print("向量数据库已重置。")
    except Exception as e:
        # 如果数据库目录不存在或首次运行，可能会出错，可以安全地忽略
        print(f"重置向量数据库时出错（可能是首次运行，可以忽略）: {e}")

    # 3. 重新初始化数据库表结构
    print("正在重新初始化数据库表结构...")
    initialize_database()
    print("--- 数据库重置完成 ---") 