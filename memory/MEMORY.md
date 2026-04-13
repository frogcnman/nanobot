# 项目记忆

---

## TokenPort - AI Token 出海中转服务

**项目定位**: 中国开发者优质AI tokens出海中转服务，OpenAI兼容接口  
**域名**: https://tokenport.top  
**服务器IP**: 43.155.246.81  
**部署**: Docker + OneAPI + Nginx + Let's Encrypt SSL  
**容器ID**: `49e842db7a91`  
**数据路径**: `/root/oneapi/data/one-api.db` (SQLite)

### 核心配置
- **新用户福利**: 注册送 **700积分** (≈$10.00)
- **邀请返利**: 邀请者 20%，被邀请者额外 +100积分
- **推广码**: `LAUNCH100` (100积分)

### 最终定价表（全部对齐全网最低价）

| Model | Input ($/M) | Output ($/M) | Notes |
|-------|-------------|--------------|-------|
| GLM-5.1 | **$0.060** | **$0.220** | 智谱旗舰，全网最低 |
| MiniMax M2.5 | $0.064 | $0.900 | -46% |
| DeepSeek V3.2 / V3.1 | $0.070 | $0.280 | -73% |
| Doubao Seed 2.0 Lite | $0.090 | $0.530 | 全网最低 |
| Qwen3.5-397B | $0.100 | $0.400 | 全网最低 |
| Qwen3-235B | $0.110 | $0.600 | -76% |
| Kimi K2.5 | $0.150 | $1.720 | -61% |
| GLM-4.5 | $0.150 | $1.099 | -75% |
| GLM-4.5-Air | $0.150 | $0.950 | -25% |
| Doubao Seed 2.0 Pro | $0.250 | $2.000 | -47% |
| Doubao Seed 2.0 Code | $0.250 | $2.000 | -63% |
| Doubao Seed Code / Ark Code | $0.064 | $0.280 | 新增超低价 |
| GLM-4.6 | $0.300 | $1.749 | -50% |
| GLM-4.7 | $0.300 | $1.749 | 全网最低 |
| GLM-5 | $0.400 | $2.300 | 开源旗舰，全网最低 |
| GLM-5-Turbo | $0.600 | $2.550 | -38% |

### 渠道配置
| ID | Name | Models |
|----|------|--------|
| 1 | volcengine | ark-code-latest, kimi-k2.5, deepseek-v3.2, glm-4.7, doubao |
| 2 | tianyi | GLM-5, GLM-5-Turbo, GLM-5.1, GLM-4.5/4.5-Air/4.6/4.7 |
| 3 | 天翼3 | GLM-5, GLM-5-Turbo, GLM-5.1, GLM-4.7/4.6/4.5-Air/4.5 |
| 4 | lty | MiniMax-M2.5, glm-5, kimi-k2.5, Qwen3.5-397B, Qwen3-235B, DeepSeek-V3.1 |

### 关键修复记录
- **2026-04-07**: 发现 OneAPI 缺失 `CompletionRatio` 配置，导致输入输出无法独立定价 → 手动数据库修复解决
- **2026-04-07**: 首页HTML标签不匹配导致源码泄露 → 生成 `tokenport-homepage-fixed.html` 修复（46/46 div 完全匹配）
- **2026-04-07**: 容器假死导致无法访问 → `docker restart one-api` 恢复

### 首页HTML文件
- 修复版: `/root/tokenport-homepage-fixed.html` (15101 bytes)

---

## 每日科技简报定时任务

**任务配置**: 每天09:00定时触发，获取GitHub热门AI开源项目热榜，生成AI开源项目日报，推送到QQ WEBCHAT渠道（Chat ID: 7BD233AED449A5C292FA5DC792A5ED83）
**简报存储路径**: `/tmp/nanobot_project/data/ai_projects_daily_YYYYMMDD.md`
**WEBCHAT会话保存**: `daily_briefing_YYYYMMDD`

### 运行记录
- **2026-03-18**: 首次运行，生成每日科技简报包含Hacker News Top 10
- **2026-03-19**: 切换为AI开源项目日报格式
- **2026-03-22**: GitHub API DNS解析失败，Brave Search API未配置，获取失败
- **2026-03-23**: 网络不稳定，ping 8.8.8.8 50%丢包，生成说明简报推送
- **2026-03-24**: 网络恢复，手动获取GitHub热榜成功，推送完成
- **2026-03-25** ~ **2026-04-04**: 每日正常运行

### GitHub热榜趋势
- **榜首项目**: `openclaw/openclaw` 持续霸榜，从323,016 stars (2026-03-19) 增长到 347,249 stars (2026-04-04)，日均增长约 1,200+ stars
- **项目描述**: Your own personal AI assistant. Any OS. Any Platform. The lobster way. 🦞 （开源个人AI助手，全平台支持）
- **技术语言分布**: Python 和 TypeScript 占据主导，基本平分4/10席位，AI Agent/工作流框架持续热门
- **知名项目排名**:
  1. openclaw/openclaw
  2. tensorflow/tensorflow
  3. Significant-Gravitas/AutoGPT
  4. n8n-io/n8n
  5. ollama/ollama
  6. AUTOMATIC1111/stable-diffusion-webui
  7. huggingface/transformers
  8. f/prompts.chat (Awesome ChatGPT Prompts)

---

## 历史项目

### 2026-04-01 智能调解系统功能设计
完成完整功能清单设计，MVP分三阶段开发，核心思想：AI为主人工兜底、自愿中立、从简单争议切入、保证法律效力。

### 2026-04-02 Claude Code 源码泄露事件分析
- 澄清误传：OpenClaw 本来就是开源项目，泄露的是 Anthropic Claude Code CLI 源码（51.2万行）
- nanobot 完成双层记忆架构重构吸收优秀设计实践

### 2026-04-04 AgentReach 技能安装
- 8/16 渠道可用，需要Cookie认证扩展剩余8个渠道

---

## 环境信息

- **服务器**: Ubuntu Linux x86_64
- **Python**: 3.12.3
- **nanobot 服务**: `systemctl status nanobot.service`
- **TokenPort Docker**: `docker ps | grep one-api`
- **Nginx**: `/etc/nginx/sites-available/tokenport.top.conf`