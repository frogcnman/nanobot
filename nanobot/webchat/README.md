# nanobot Web Chat

一个基于 Web 的聊天界面，可以通过浏览器访问 nanobot AI 助手。

## 功能特性

- 🌐 **Web 界面** - 通过浏览器访问，支持局域网访问
- 💬 **流式输出** - 实时显示 AI 回复
- 📝 **对话持久化** - 自动保存聊天记录，刷新页面不丢失
- 📋 **多会话管理** - 支持创建、切换、重命名、删除多个对话
- 🎨 **现代界面** - 深色主题，响应式设计，支持移动端
- ⚙️ **自动配置** - 自动读取 nanobot 配置文件

## 快速开始

### 方式一：作为模块运行

```bash
cd /path/to/nanobot
python3 -m nanobot.webchat
```

### 方式二：使用启动脚本

```bash
./scripts/start-webchat.sh
```

### 方式三：直接运行

```bash
python3 nanobot/webchat/app.py
```

## 访问地址

启动后，通过以下地址访问：

- **本地访问**: http://localhost:8081
- **局域网访问**: http://YOUR_IP:8081

## 配置

Web Chat 自动读取 `~/.nanobot/config.json` 中的配置，包括：

- API Key（从 providers 配置中自动选择）
- 模型名称
- API Base URL

也可以通过环境变量覆盖：

```bash
export API_KEY="your-api-key"
export MODEL="gpt-4o-mini"
export API_BASE_URL="https://api.openai.com/v1"
python3 -m nanobot.webchat
```

## 数据存储

聊天记录保存在 `~/.nanobot/webchat-data/sessions/` 目录下，每个会话一个 JSON 文件。

## 支持的 API 提供商

- 智谱AI (zhipu)
- OpenAI
- DeepSeek
- Anthropic
- Moonshot
- Groq
- OpenRouter
- SiliconFlow
- 自定义 API

## 技术栈

- **后端**: Python Flask
- **前端**: 原生 JavaScript + CSS
- **特性**: Server-Sent Events (SSE) 流式传输

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 发送消息（支持流式） |
| `/api/sessions` | GET | 获取会话列表 |
| `/api/sessions` | POST | 创建新会话 |
| `/api/sessions/<id>` | DELETE | 删除会话 |
| `/api/sessions/<id>/rename` | POST | 重命名会话 |
| `/api/history` | GET | 获取会话历史 |
| `/api/clear` | POST | 清除当前会话 |
| `/api/config` | GET | 获取配置信息 |
| `/health` | GET | 健康检查 |

## 许可证

MIT License
