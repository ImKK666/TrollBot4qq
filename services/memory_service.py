# services/memory_service.py

import chromadb
from chromadb.config import Settings
import openai
from typing import List, Dict, Any, Union
import uuid

from config import (
    MEMORY_DB_PATH, 
    OPENAI_API_KEY, 
    EMBEDDING_API_KEY, 
    EMBEDDING_API_URL,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_API_TIMEOUT,
    MEMORY_SEARCH_TOP_K,
    MEMORY_SEARCH_MAX_DISTANCE,
    MEMORY_SEARCH_FINAL_MAX_COUNT
)

# --- 初始化 OpenAI 客户端 ---
# 主要OpenAI客户端（用于Chat/Completion等）
if OPENAI_API_KEY:
	openai.api_key = OPENAI_API_KEY
else:
	print("警告: 未找到 OPENAI_API_KEY，Chat/Completion 功能将不可用。")

# --- 初始化嵌入向量专用OpenAI客户端 ---
# 创建一个独立的客户端实例用于嵌入向量服务
embedding_client = None
if EMBEDDING_API_KEY:
	embedding_client = openai.OpenAI(
		api_key=EMBEDDING_API_KEY,
		base_url=EMBEDDING_API_URL
	)
	print(f"嵌入向量客户端已初始化，使用URL: {EMBEDDING_API_URL}")
else:
	print("警告: 未找到 EMBEDDING_API_KEY，向量生成功能将不可用。")

# --- ChromaDB 客户端重构：延迟初始化 ---

# 将客户端和集合实例变量变为私有的，并初始化为None
_client: chromadb.Client = None
_memory_collection: chromadb.Collection = None

def get_client() -> chromadb.Client:
    """获取ChromaDB客户端的单例。在第一次调用时初始化。"""
    global _client
    if _client is None:
        print("首次调用，正在初始化ChromaDB持久化客户端...")
        # 允许通过API重置数据库，这对于测试非常重要
        settings = Settings(allow_reset=True)
        _client = chromadb.PersistentClient(path=MEMORY_DB_PATH, settings=settings)
    return _client

def get_memory_collection() -> chromadb.Collection:
    """获取记忆集合的单例。如果客户端被重置，能自动重新创建集合。"""
    global _memory_collection
    client = get_client()
    
    # 检查集合是否已被创建或是否需要重新获取
    # client.get_or_create_collection 是幂等的，所以重复调用是安全的
    _memory_collection = client.get_or_create_collection(name="troll_memories")
    return _memory_collection


def get_embedding_from_text(text: str) -> List[float]:
	"""
	使用外部API（这里是独立的嵌入向量API）为文本生成向量。
	你可以轻易地将这里替换成任何其他 embedding 服务。
	"""
	if not embedding_client:
		raise ValueError("嵌入向量 API 客户端未初始化")
	
	# 我们选择一个性价比高的模型
	response = embedding_client.embeddings.create(
		input=text,
		model=EMBEDDING_MODEL_NAME, # 使用配置文件中的模型名称
        timeout=EMBEDDING_API_TIMEOUT # 使用配置的超时时间
	)
	return response.data[0].embedding

async def add_memory(
    user_id: int, 
    message_id: int, 
    original_text: str, 
    summary_text: str, 
    troll_potential: int, 
    timestamp: int
):
    """
    将一条关键记忆添加到向量数据库中。
    summary_text 是用来生成向量的文本。
    """
    try:
        print(f"正在为记忆生成向量: '{summary_text}'")
        # 1. 为“槽点总结”生成向量
        embedding = get_embedding_from_text(summary_text)
        
        # 2. 准备要存储的文档和元数据
        document_to_store = original_text  # 我们存储原始发言，方便日后引用
        
        metadata_to_store = {
            "user_id": user_id,
            "message_id": message_id,
            "summary": summary_text,
            "troll_potential": troll_potential,
            "timestamp": timestamp
        }
        
        # 3. 使用一个唯一的ID来标识这条记忆
        # 我们可以用 message_id，但为了防止重复，转为字符串
        memory_id = str(message_id)
        
        # 4. 获取最新的集合实例并添加数据
        collection = get_memory_collection()
        collection.add(
            embeddings=[embedding],
            documents=[document_to_store],
            metadatas=[metadata_to_store],
            ids=[memory_id]
        )
        print(f"成功添加记忆 (ID: {memory_id}) 到ChromaDB。")
        return True
    except Exception as e:
        print(f"添加记忆失败: {e}")
        return False

async def search_relevant_memories(query_text: str, user_id: int = None) -> Union[List[Dict[str, Any]], None]:
    """
    根据查询文本，搜索最相关的黑历史。
    现在包含二次筛选逻辑，并在失败时返回None。
    1. 初步从ChromaDB获取 top_k 条。
    2. 在代码中过滤掉距离大于阈值的。
    3. 最后返回不超过最大数量的结果。
    """
    try:
        print(f"正在为查询生成向量: '{query_text}'")
        # 1. 为查询文本生成向量
        query_embedding = get_embedding_from_text(query_text)
        
        # 2. 构建元数据过滤器 (where-filter)
        where_filter = {}
        if user_id:
            where_filter["user_id"] = user_id
            print(f"应用过滤器: 只搜索用户 {user_id} 的记忆。")

        # 3. 在集合中进行初步查询
        collection = get_memory_collection()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=MEMORY_SEARCH_TOP_K, # 使用配置的初步获取数量
            where=where_filter if where_filter else None
        )
        
        # 4. 二次筛选
        retrieved_memories = []
        if results and results['ids'][0]:
            for i, memory_id in enumerate(results['ids'][0]):
                distance = results['distances'][0][i]
                
                # 只有距离小于阈值的才算“足够相关”
                if distance < MEMORY_SEARCH_MAX_DISTANCE:
                    memory = {
                        "id": memory_id,
                        "original_text": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "distance": distance # 距离越小，越相关
                    }
                    retrieved_memories.append(memory)
        
        print(f"初步找到 {len(results['ids'][0])} 条记忆，经过距离阈值 (<{MEMORY_SEARCH_MAX_DISTANCE}) 筛选后剩下 {len(retrieved_memories)} 条。")

        # 5. 返回最终结果（不超过最大数量）
        final_memories = retrieved_memories[:MEMORY_SEARCH_FINAL_MAX_COUNT]
        print(f"最终返回 {len(final_memories)} 条记忆给LLM。")
        
        return final_memories
    
    except openai.APIConnectionError as e:
        print(f"【错误】[Memory Search]: 无法连接到嵌入服务 ({EMBEDDING_API_URL})。请检查网络连接和API地址。错误: {e.__cause__}")
        return None
    except openai.APITimeoutError:
        print(f"【错误】[Memory Search]: 请求嵌入服务超时 (超过 {EMBEDDING_API_TIMEOUT} 秒)。请检查服务状态或增加超时时间。")
        return None
    except openai.APIStatusError as e:
        print(f"【错误】[Memory Search]: 嵌入服务返回了非200的状态码 {e.status_code}。响应: {e.response}")
        return None
    except Exception as e:
        print(f"【错误】[Memory Search]: 搜索记忆时发生未知错误: {e}")
        return None