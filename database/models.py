# database/models.py
import sqlite3

from bot_config import PROFILE_DB_PATH


def initialize_database():
    """
    初始化数据库。如果表不存在，则创建它们。
    """
    # 连接到数据库文件，如果文件不存在，会自动创建
    conn = sqlite3.connect(PROFILE_DB_PATH)
    cursor = conn.cursor()

    # --- 创建用户档案表 (user_profiles) ---
    # 使用 IF NOT EXISTS 来防止重复创建表
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS user_profiles (
        user_id INTEGER PRIMARY KEY,      -- QQ号作为主键
        current_nickname TEXT,            -- 当前昵称
        historical_nicknames TEXT,        -- 存储为 JSON 字符串的列表
        aliases TEXT,                     -- 存储为 JSON 字符串的列表，如 ["懂哥", "小学生"]
        summary TEXT,                     -- LLM 生成的用户画像总结
        attitudes TEXT,                   -- 对其他群友的单向态度，JSON格式: {"target_user_id": "attitude_desc"}
        last_updated INTEGER              -- 最后更新时间的时间戳
    );
    """
    )

    # --- 创建对话主题总结表 (conversation_topics) ---
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS conversation_topics (
        topic_id INTEGER PRIMARY KEY AUTOINCREMENT, -- 自增ID
        group_id INTEGER NOT NULL,                  -- 发生对话的群组ID
        start_time INTEGER NOT NULL,                -- 对话段的开始时间戳
        end_time INTEGER NOT NULL,                  -- 对话段的结束时间戳
        avg_time INTEGER NOT NULL,                  -- 对话段的平均时间戳
        theme TEXT,                                 -- LLM总结的主题
        summary TEXT,                               -- LLM生成的话题概要
        participants_viewpoints TEXT                -- 参与者及其观点，JSON格式: {"user_id": "viewpoint"}
    );
    """
    )

    print("数据库初始化完成，user_profiles 和 conversation_topics 表已确认存在。")
    conn.commit()
    conn.close()


# 在程序启动时，我们需要调用一次这个函数。
# 后面我们会在 main.py 的 startup 事件中调用它。
