# config.py
import os

# --- OneBot 配置 ---
ONEBOT_WS_URL = "ws://127.0.0.1:3001"
ONEBOT_HTTP_URL = "http://127.0.0.1:3000"
ONEBOT_ACCESS_TOKEN = ""  # 如果你的OneBot配置需要访问令牌，在这里填入

# --- 机器人核心配置 ---
# 请修改以下示例值为你的实际配置
TARGET_GROUP_IDS = [123456789, 987654321]  # 替换为你的目标群组ID
CRITICAL_TARGET_LIST = [111111111]  # 替换为你的关键目标用户ID
BOT_QQ_ID = 1234567890  # 替换为你的机器人QQ号
BOT_NICKNAME = "MyBot"  # 替换为你的机器人昵称

# --- 认知轨道配置 ---
DIGESTION_BUFFER_SIZE = 50  # 积攒50条消息后进行一次消化
DIGESTION_INTERVAL_SECONDS = 900  # 或者每15分钟消化一次

# --- 数据库路径 ---
PROFILE_DB_PATH = "data/profiles.db"
MEMORY_DB_PATH = "data/memory_db"

# --- API Keys ---
# 请将以下示例API密钥替换为你的真实密钥
OPENAI_API_KEY = "sk-your-actual-openai-api-key-here"  # 替换为你的实际OpenAI API密钥
OPENAI_API_URL = "https://api.openai.com/v1"  # 如果使用第三方API服务，请修改此URL

# 嵌入向量专用API（可以使用不同的服务商或账号）
EMBEDDING_API_KEY = "sk-your-embedding-api-key-here"  # 替换为你的嵌入向量API密钥
EMBEDDING_API_URL = "https://api.openai.com/v1"  # 嵌入向量API URL
EMBEDDING_MODEL_NAME = "text-embedding-3-small"  # 嵌入向量模型
EMBEDDING_API_TIMEOUT = 30  # 嵌入API的请求超时时间（秒）

# --- LLM 模型配置 ---
LLM_MODEL_NAME = "gpt-4"  # 用于生成回复和进行分析的主力模型
FAST_LLM_MODEL_NAME = "gpt-3.5-turbo"  # 用于快速意图分析的模型，可以选用更快的

# --- 核心逻辑配置 ---
RECENT_MESSAGES_BUFFER_SIZE = 20  # 快速反应通道将参考的最近消息数量
QUICK_REPLY_COOLDOWN_SECONDS = 10  # 针对同一用户的快速回复冷却时间（秒）

# --- 主动攻击配置 ---
PROACTIVE_ATTACK_INTERVAL_SECONDS = 300  # 每隔5分钟检查一次是否需要主动攻击
PROACTIVE_ATTACK_INACTIVITY_HOURS = 2  # 目标沉默超过2小时则可能触发攻击
PROACTIVE_ATTACK_ACTIVE_TIME_RANGE = (9, 23)  # 只在早上9点到晚上11点之间发动攻击

# --- 记忆搜索配置 ---
MEMORY_SEARCH_TOP_K = 10  # 从向量数据库中初步获取的最相似的记忆条数
MEMORY_SEARCH_MAX_DISTANCE = 1.2  # 定义"足够相关"的距离阈值（L2距离，越小越相关）
MEMORY_SEARCH_FINAL_MAX_COUNT = 3  # 经过距离筛选后，最终提供给LLM的最大记忆条数
