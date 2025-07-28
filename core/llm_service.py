# core/llm_service.py
import asyncio
import base64
from typing import List, Dict, Any, Union
import httpx
import openai
import json
import time
import re

from config import (
    OPENAI_API_KEY, 
    OPENAI_API_URL, 
    LLM_MODEL_NAME, 
    FAST_LLM_MODEL_NAME
)
# 导入新的服务层函数
from services.topic_service import add_topic
from services.profile_service import update_attitudes
from services.memory_service import search_relevant_memories # 导入记忆搜索服务


# --- 定义我们的“工具”，即LLM可以调用的函数 ---
ANALYSIS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "save_conversation_analysis",
        "description": "保存对QQ群聊天记录的深入分析结果，包括话题总结和社交动态。",
        "parameters": {
            "type": "object",
            "properties": {
                "topic_analysis": {
                    "type": "object",
                    "description": "关于对话宏观主题的分析。",
                    "properties": {
                        "theme": {"type": "string", "description": "对话主题的一句话总结。"},
                        "summary": {"type": "string", "description": "对话内容的详细概要。"},
                        "participants_viewpoints": {
                            "type": "object",
                            "description": "一个JSON对象，key是用户ID(字符串形式)，value是该用户的核心观点。",
                            "additionalProperties": {"type": "string"}
                        }
                    },
                    "required": ["theme", "summary", "participants_viewpoints"]
                },
                "social_dynamics_analysis": {
                    "type": "array",
                    "description": "一个包含用户间社交互动分析的列表。",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_user_id": {"type": "integer", "description": "发起互动用户的QQ号。"},
                            "target_user_id": {"type": "integer", "description": "被互动用户的QQ号。"},
                            "attitude_description": {"type": "string", "description": "对source用户向target用户展现的行为和隐含态度的文字描述。"}
                        },
                        "required": ["source_user_id", "target_user_id", "attitude_description"]
                    }
                }
            },
            "required": ["topic_analysis", "social_dynamics_analysis"]
        }
    }
}


# --- 初始化 OpenAI 客户端 ---
if OPENAI_API_KEY:
    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_URL)
    print("LLM 服务已初始化 OpenAI 客户端。")
else:
    client = None
    print("警告: 未找到 OPENAI_API_KEY，LLM 服务将不可用。")

# --- 加载 System Prompt ---
try:
    with open("prompts/digest_prompt.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
    print("消化任务的 System Prompt 已加载。")
    with open("prompts/fast_track_intent_prompt.txt", "r", encoding="utf-8") as f:
        INTENT_PROMPT_TEMPLATE = f.read()
    print("快速通道意图分析Prompt已加载。")
    with open("prompts/fast_track_reply_prompt.txt", "r", encoding="utf-8") as f:
        REPLY_PROMPT_TEMPLATE = f.read()
    print("快速通道回复生成Prompt已加载。")
    with open("prompts/proactive_attack_prompt.txt", "r", encoding="utf-8") as f:
        ATTACK_PROMPT_TEMPLATE = f.read()
    print("主动攻击Prompt已加载。")
except FileNotFoundError as e:
    print(f"【错误】: 缺少必要的Prompt文件: {e}")
    SYSTEM_PROMPT = ""
    INTENT_PROMPT_TEMPLATE = ""
    REPLY_PROMPT_TEMPLATE = ""
    ATTACK_PROMPT_TEMPLATE = ""


# --- QQ 表情ID到文本的映射 ---
# 这只是一个示例，您需要根据 go-cqhttp 的文档或实际接收到的数据来完善这个映射
# https://docs.go-cqhttp.org/cqcode/#%E8%A1%A8%E6%83%85
CQ_FACE_MAP = {
    "14": "[微笑]", "1": "[撇嘴]", "2": "[色]", "3": "[发呆]", "4": "[得意]",
    "5": "[流泪]", "6": "[害羞]", "7": "[闭嘴]", "8": "[睡]", "9": "[大哭]",
    "10": "[尴尬]", "11": "[发怒]", "12": "[调皮]", "13": "[呲牙]", 
    # ... 在这里继续添加更多表情 ...
}

async def _download_image_as_base64(url: str) -> Union[str, None]:
    """异步下载图片并返回 base64 编码的字符串"""
    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.get(url, timeout=10)
            response.raise_for_status()  # 如果下载失败则抛出异常
            content_type = response.headers.get('content-type', 'image/jpeg')
            base64_data = base64.b64encode(response.content).decode('utf-8')
            return f"data:{content_type};base64,{base64_data}"
        except httpx.HTTPStatusError as e:
            print(f"下载图片失败: {e}")
            return None

async def _prepare_llm_message_content(message_segments: List[Dict]) -> List[Dict]:
    """
    将 OneBot 的消息段(segments)转换为 OpenAI API 能理解的内容格式。
    """
    llm_content = []
    text_parts = []

    for segment in message_segments:
        seg_type = segment.get("type")
        data = segment.get("data", {})

        if seg_type == "text":
            text_parts.append(data.get("text", ""))
        
        elif seg_type == "face":
            face_id = data.get("id")
            # 将表情ID转换为文本描述，如果找不到就用一个通用描述
            face_text = CQ_FACE_MAP.get(face_id, f"[QQ表情ID:{face_id}]")
            text_parts.append(face_text)

        elif seg_type == "image":
            # 如果之前有文字，先把它们组合成一个文本块
            if text_parts:
                llm_content.append({"type": "text", "text": "".join(text_parts)})
                text_parts = []
            
            image_url = data.get("url")
            if image_url:
                base64_image = await _download_image_as_base64(image_url)
                if base64_image:
                    llm_content.append({
                        "type": "image_url",
                        "image_url": {"url": base64_image}
                    })

    # 处理循环结束后剩余的文本部分
    if text_parts:
        llm_content.append({"type": "text", "text": "".join(text_parts)})
    
    return llm_content

def _format_message_for_prompt(message: Dict) -> str:
    """将单条OneBot消息格式化为人类可读的字符串。"""
    sender = message.get("sender", {})
    nickname = sender.get("nickname", "未知用户")
    user_id = sender.get("user_id", "N/A")
    
    parts = []
    for segment in message.get("message", []):
        if segment["type"] == "text":
            parts.append(segment["data"]["text"])
        elif segment["type"] == "face":
            face_id = segment["data"]["id"]
            parts.append(CQ_FACE_MAP.get(face_id, f"[表情:{face_id}]"))
        elif segment["type"] == "image":
            parts.append("[图片]") # 在纯文本Prompt中，我们只做标记

    return f"{nickname}({user_id}): {''.join(parts)}"


async def generate_fast_track_reply(target_message: Dict, context_messages: List[Dict]) -> Union[str, None]:
    """
    快速通道回复生成逻辑
    1. 使用快速LLM评估消息是否值得回复。
    2. 如果值得，搜索相关记忆。
    3. 使用高级LLM结合上下文和记忆生成回复。
    """
    if not client or not INTENT_PROMPT_TEMPLATE or not REPLY_PROMPT_TEMPLATE:
        print("【快速通道】: 服务未初始化或缺少Prompt，跳过。")
        return None

    target_user_id = target_message["user_id"]
    
    # 1. 使用快速LLM进行意图分析和趣味性评估
    try:
        print("【快速通道】: 正在进行趣味性评估...")
        intent_system_prompt = INTENT_PROMPT_TEMPLATE
        intent_user_prompt = f"用户消息: \"{_format_message_for_prompt(target_message)}\""
        
        # 调试日志
        # print(f"--- Intent System Prompt ---\n{intent_system_prompt}")
        # print(f"--- Intent User Prompt ---\n{intent_user_prompt}")

        response = await client.chat.completions.create(
            model=FAST_LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": intent_system_prompt},
                {"role": "user", "content": intent_user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        intent_response_raw = response.choices[0].message.content
        
        # 从Markdown代码块中提取纯JSON
        json_match = re.search(r'```json\n(.*)\n```', intent_response_raw, re.DOTALL)
        if json_match:
            intent_response_raw = json_match.group(1)

        try:
            intent_data = json.loads(intent_response_raw)
            is_interesting = intent_data.get("is_interesting", False)
            search_query = intent_data.get("search_query", "")
            print(f"【快速通道】: 趣味性评估结果: {is_interesting}, 搜索词: '{search_query}'")
        except json.JSONDecodeError:
            print(f"【快速通道】【错误】: 解析趣味性评估JSON失败。响应: {intent_response_raw}")
            return None # JSON解析失败，终止流程

        # 如果快速模型认为消息无聊，则直接终止
        if not is_interesting:
            print("【快速通道】: 快速模型判定消息无聊，跳过处理。")
            return None
            
    except Exception as e:
        print(f"【快速通道】【错误】: 趣味性评估API调用失败: {e}")
        return None

    # --- 只有在消息有趣时，才继续执行以下步骤 ---

    # 2. 根据意图搜索相关记忆
    relevant_memories = []
    if search_query: # 仅当有搜索词时才执行搜索
        try:
            print(f"正在为查询生成向量: '{search_query}'")
            query_embedding = await get_embedding_from_text(search_query)
            if query_embedding:
                # 注意：search_relevant_memories现在返回的是字典列表
                memories_found = await search_relevant_memories(
                    group_id=target_message.get('group_id'),
                    query_embedding=query_embedding
                )
                if memories_found:
                    relevant_memories = memories_found
                    print(f"找到 {len(relevant_memories)} 条相关黑历史。")
                else:
                    print("未找到相关黑历史。")
        except Exception as e:
            # 即使记忆搜索失败，也应该继续，而不是终止
            print(f"搜索记忆失败: {e}。将仅基于当前上下文生成回复。")

    # 3. 准备最终回复的上下文
    formatted_context = "\n".join([_format_message_for_prompt(msg) for msg in context_messages])
    formatted_memories = "\n".join([
        f"- [发言时间: {mem['timestamp']}] [发言主题: {mem.get('topic', '未知')}] [发言内容: {mem['content']}]"
        for mem in relevant_memories
    ]) if relevant_memories else "无"

    # 4. 调用高级LLM生成最终回复
    try:
        print("【快速通道】: 正在生成最终回复...")
        # 分离 system 指令和 user 数据
        reply_system_prompt = REPLY_PROMPT_TEMPLATE
        reply_user_prompt = f"最近聊天记录:\n{formatted_context}\n\n目标的当前发言:\n{_format_message_for_prompt(target_message)}\n\n相关黑历史 (如果找到):\n{formatted_memories}"
        
        # --- 新增：详细调试日志 ---
        print("\n--- [Debug] Sending to Reply Generation LLM ---")
        print(f"System Prompt: {reply_system_prompt}")
        print(f"User Prompt:\n{reply_user_prompt}")
        print("---------------------------------------------\n")

        response = await client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": reply_system_prompt},
                {"role": "user", "content": reply_user_prompt}
            ],
            temperature=1, # 增加一点创造性
            max_tokens=15000 # 增加输出长度限制
        )
        
        # --- 新增：更详细的响应验证和诊断日志 ---
        if not response.choices:
            print("【快速通道】【错误】: LLM API返回了空的choices列表，无法获取回复。")
            return None

        choice = response.choices[0]
        finish_reason = choice.finish_reason
        message = choice.message
        
        print(f"【快速通道】【调试】: 响应完成原因: {finish_reason}")

        final_reply_raw = message.content.strip() if message.content else ""
        
        # 根据完成原因，为空回复提供更详细的诊断
        if not final_reply_raw:
            if finish_reason == 'content_filter':
                print("【快速通道】【警告】: LLM生成了空回复，原因是内容可能被服务商的安全策略过滤。")
            elif finish_reason == 'length':
                print("【快速通道】【警告】: LLM生成了空回复，原因是输出的内容达到了max_tokens的限制。")
            else:
                print(f"【快速通道】【警告】: LLM生成了空回复，但未提供明确原因 (finish_reason: {finish_reason})。")

        # 5. 处理回复（增强版）
        # 解析嘲讽潜力评分
        tp_score = 0
        score_match = re.search(r'<TP-Score:\s*(\d+)>', final_reply_raw)
        if score_match:
            tp_score = int(score_match.group(1))
            # 从回复中移除标记
            final_reply = re.sub(r'<TP-Score:\s*\d+>', '', final_reply_raw).strip()
        else:
            final_reply = final_reply_raw

        # 如果返回的是 NO_REPLY，或者是一个空/空白字符串，都视为不回复
        if final_reply == "NO_REPLY" or not final_reply:
            print("【快速通道】: LLM决定不回复。")
            return None
        
        print(f"【快速通道】: 生成回复 (TP-Score: {tp_score}): {final_reply}")
        return final_reply

    except Exception as e:
        print(f"【快速通道】: 回复生成失败: {e}")
        return None

async def generate_proactive_attack_message(memory: Dict) -> Union[str, None]:
    """
    根据一条黑历史，生成主动攻击的发言。
    """
    if not client or not ATTACK_PROMPT_TEMPLATE:
        print("【主动攻击】: 服务未初始化或缺少Prompt，跳过。")
        return None

    try:
        memory_text = f"“{memory['original_text']}” (发生在: {time.strftime('%Y-%m-%d', time.localtime(memory['metadata']['timestamp']))})"
        
        # 分离 system 指令和 user 数据
        attack_system_prompt = ATTACK_PROMPT_TEMPLATE
        attack_user_prompt = f"目标的黑历史:\n{memory_text}"
        
        print(f"【主动攻击】: 正在为黑历史 '{memory_text}' 生成攻击性发言...")
        
        response = await client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": attack_system_prompt},
                {"role": "user", "content": attack_user_prompt}
            ],
            temperature=0.8, # 增加创造性以产生更有趣的攻击
            max_tokens=400 # 增加输出长度限制
        )
        
        # --- 新增：更详细的响应验证和诊断日志 ---
        if not response.choices:
            print("【主动攻击】【错误】: LLM API返回了空的choices列表，无法获取回复。")
            return None

        choice = response.choices[0]
        finish_reason = choice.finish_reason
        message = choice.message
        
        print(f"【主动攻击】【调试】: 响应完成原因: {finish_reason}")

        attack_message = message.content.strip() if message.content else ""

        if not attack_message:
            if finish_reason == 'content_filter':
                print("【主动攻击】【警告】: LLM生成了空回复，原因是内容可能被服务商的安全策略过滤。")
            else:
                print(f"【主动攻击】【警告】: LLM生成了空回复 (finish_reason: {finish_reason})。")
            return None

        print(f"【主动攻击】: 生成攻击发言: {attack_message}")
        return attack_message

    except Exception as e:
        print(f"【主动攻击】: 生成攻击发言失败: {e}")
        return None


async def digest_messages_in_background(messages: List[Dict[str, Any]]):
    """
    认知轨道（慢速通道）的核心功能。
    接收消息缓冲区，调用LLM进行分析、总结，并更新记忆和用户画像。
    """
    if not client:
        print("LLM 客户端未初始化，跳过消化任务。")
        return

    if not messages:
        print("【认知轨道】: 消息缓冲区为空，跳过处理。")
        return
        
    # --- 提取上下文信息 ---
    group_id = messages[0].get("group_id")
    start_time = messages[0].get("time")
    end_time = messages[-1].get("time")

    # 1. 构建一个大的对话历史记录，用于LLM分析
    conversation_history = []
    for msg in messages:
        user_id = msg.get("user_id")
        nickname = msg.get("sender", {}).get("nickname", "未知用户")
        
        # 将原始消息段转换为LLM能理解的格式
        llm_message_content = await _prepare_llm_message_content(msg.get("message", []))

        # 【已修复】在这里，我们将发言者信息作为第一个文本块，
        # 然后直接拼接由_prepare_llm_message_content生成的、保留了正确顺序的图文内容列表。
        # 这确保了多模态内容的完整性和顺序。
        user_intro = {"type": "text", "text": f"用户 {nickname} (ID: {user_id}) 说:\n"}
        
        # 将格式化的消息内容添加到历史记录
        conversation_history.append({
            "role": "user",
            "content": [user_intro] + llm_message_content
        })

    # --- 真正调用 LLM ---
    try:
        print("【认知轨道】: 对话历史已构建，正在发送给 LLM 进行分析...")
        
        # 构建发送给API的消息列表
        api_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *conversation_history
        ]

        response = await client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=api_messages,
            # --- 兼容性调整：从函数调用模式降级回JSON模式 ---
            # tools=[ANALYSIS_TOOL_SCHEMA], 
            # tool_choice={"type": "function", "function": {"name": "save_conversation_analysis"}},
            response_format={"type": "json_object"}, # 重新启用JSON模式
            temperature=0.5,
        )
        
        response_content = response.choices[0].message.content
        print("【认知轨道】: LLM 分析完成。")
        
        # --- 解析并处理LLM的返回结果 (JSON模式) ---
        try:
            # 【关键修复】 清洗LLM可能返回的Markdown代码块标记
            cleaned_response = response_content
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:] # 移除 "```json\n"
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3] # 移除 "```"
            
            analysis_result = json.loads(cleaned_response.strip())
            
            print("--- LLM返回的分析结果 ---")
            print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
            print("--------------------------")

            # 1. 处理话题分析结果
            topic_analysis = analysis_result.get("topic_analysis")
            if topic_analysis:
                # 将 participants_viewpoints 的 key 从字符串转为整数
                participants_viewpoints = {
                    int(k): v for k, v in topic_analysis.get("participants_viewpoints", {}).items()
                }
                
                await add_topic(
                    group_id=group_id,
                    start_time=start_time,
                    end_time=end_time,
                    theme=topic_analysis.get("theme"),
                    summary=topic_analysis.get("summary"),
                    participants_viewpoints=participants_viewpoints
                )
            
            # 2. 处理社交动态分析结果
            social_analysis = analysis_result.get("social_dynamics_analysis", [])
            for attitude in social_analysis:
                await update_attitudes(
                    user_id=attitude.get("source_user_id"),
                    target_user_id=attitude.get("target_user_id"),
                    attitude_desc=attitude.get("attitude_description")
                )

        except json.JSONDecodeError:
            print(f"【错误】: LLM返回的不是有效的JSON格式。原始返回: {response_content}")
            
    except Exception as e:
        print(f"【错误】: 调用LLM API或处理时发生错误: {e}")