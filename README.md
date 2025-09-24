# TrollBot - 智能QQ机器人

一个基于 FastAPI 和 OneBot 协议的高级QQ机器人，具备AI对话能力、用户画像分析、记忆存储和主动交互功能。

## 🚀 项目特性

### 核心功能
- **智能对话**：基于大语言模型的自然对话能力
- **用户画像**：自动分析并记忆用户特征和行为模式
- **记忆系统**：使用向量数据库存储和检索历史对话内容
- **主动交互**：定时分析群聊活跃度，主动发起话题
- **快速响应**：支持快速轨道和深度分析两种回复模式

### 技术特性
- **多模型支持**：支持不同的LLM模型用于不同场景
- **异步架构**：基于 FastAPI 的高性能异步处理
- **模块化设计**：清晰的分层架构，易于扩展和维护
- **数据持久化**：SQLite + ChromaDB 混合存储方案

## 🏗️ 技术架构

```
TrollBot/
├── main.py                    # 应用程序入口
├── bot_config.py              # 机器人运行配置
├── api/
│   └── v1/
│       └── endpoints.py       # API端点定义
├── core/                      # 核心功能模块
│   ├── onebot_listener.py     # OneBot事件监听器
│   ├── onebot_actions.py      # OneBot动作执行器
│   ├── llm_service.py         # LLM服务封装
│   ├── scheduler.py           # 定时任务调度器
│   └── state.py              # 全局状态管理
├── database/                  # 数据库相关
│   ├── models.py             # 数据模型定义
│   ├── crud.py               # 数据库操作
│   └── utils.py              # 数据库工具函数
├── services/                  # 业务服务层
│   ├── graphrag_manager.py   # GraphRAG 管理器
│   ├── memory_service.py     # 记忆服务（GraphRAG 记忆）
│   ├── profile_service.py    # 用户画像服务（GraphRAG 支持）
│   └── topic_service.py      # 话题管理服务
├── trollbot_graphrag/        # 集成的 Youtu-GraphRAG 框架源码
├── prompts/                   # LLM提示词模板
└── data/                     # 数据存储目录
    ├── graphrag/             # GraphRAG 输出与缓存
    └── profiles.db           # SQLite用户数据库（兼容保留）
```

## 🔧 技术栈

- **后端框架**：FastAPI
- **QQ协议**：OneBot v11
- **AI服务**：OpenAI API（支持多提供商）
- **知识图谱检索**：Youtu-GraphRAG（FAISS + 图谱推理）
- **关系数据库**：SQLite
- **异步通信**：WebSocket + HTTP
- **依赖管理**：Python pip

## 📋 主要组件说明

### 消息处理流程
1. **OneBot监听器** 接收QQ群消息事件
2. **API端点** 处理消息并分发到对应处理器
3. **快速轨道** 处理即时回复需求
4. **慢速轨道** 进行深度分析和用户画像更新
5. **记忆服务** 存储重要对话内容到向量数据库

### 智能功能
- **意图识别**：快速判断消息是否需要回复
- **上下文理解**：结合历史消息和用户画像生成回复
- **社交分析**：分析用户间的互动关系和态度
- **主动交互**：在群聊沉默时主动发起话题

### 数据存储
- **用户档案**（SQLite）：用户基本信息、昵称历史、态度分析
- **对话主题**（SQLite）：话题总结、参与者观点
- **图谱记忆**（GraphRAG）：对话与画像的结构化知识图谱

## 🧠 GraphRAG 记忆与画像体系

- 所有记忆、画像与态度更新都会被封装为 `GraphDocument`，写入 `data/graphrag/corpus.json`。
- `services/graphrag_manager.py` 负责调用 Youtu-GraphRAG 的 `KTBuilder` 重新构建知识图谱，并通过 `KTRetriever` 进行检索。
- `services/memory_service.py` 使用 GraphRAG 构建的图谱来搜索黑历史，并将对话摘要转换为结构化记忆。
- `services/profile_service.py` 利用 GraphRAG 的检索结果生成用户画像，包含别名和社交态度等信息。
- `database/utils.reset_all_databases` 支持一键清空 GraphRAG 输出，便于测试和重新训练。

## ⚙️ 配置说明

主要配置项位于 `bot_config.py`：

- **OneBot配置**：WebSocket和HTTP连接地址
- **机器人配置**：目标群组、机器人QQ号等
- **AI服务配置**：API密钥、模型选择
- **功能参数**：回复频率、记忆搜索参数等

## 🎯 使用场景

- QQ群聊助手和话题引导
- 用户行为分析和社交洞察
- 智能客服和自动回复
- 群组活跃度管理
- 娱乐互动机器人

## 📝 注意事项

1. 需要搭配支持OneBot协议的QQ客户端（如 go-cqhttp）
2. 需要有效的OpenAI API密钥或兼容服务
3. 机器人具有主动发言功能，请合理配置使用
4. 建议在测试环境中充分测试后再部署到生产环境

## 📄 许可证

本项目仅供学习和研究使用，请遵守相关法律法规和平台服务条款。 