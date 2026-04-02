# 对话历史与项目记录

## 2026-04-01 智能调解系统功能设计
- 用户请求设计智能调解系统功能清单
- 输出完整功能清单包含：
  1. 核心业务流程（申请入口、调解邀请、流程启动）
  2. 用户角色与权限（申请人、被申请人、AI调解员、人类调解员、管理员、运营）
  3. AI核心能力（NLU、法律匹配、方案生成、沟通引导）
  4. 调解过程功能（在线调解室、证据管理、进度管理、人工介入）
  5. 知识与法规支持（法规库、案例库、计算工具）
  6. 协议与法律效力（自动生成、电子签名、司法对接、履行跟进）
  7. 数据分析与运营（统计看板、案件管理、训练数据）
  8. 系统管理与安全（权限、安全合规、内容审核、日志）
  9. 移动端适配（H5、拍照优化、推送）
  10. 增值功能扩展（仲裁对接、诉讼辅导、调解员入驻、企业批量调解、智能咨询）
- 给出MVP分阶段优先级：第一阶段MVP（申请+调解室+AI归纳+方案+签名），第二阶段（法规+人工+数据），第三阶段（司法+企业+诉讼）
- 核心设计思想：AI为主人工兜底、自愿中立、从简单争议切入、保证法律效力

## 2026-04-02 Claude Code 源码泄露事件分析
### 事件澄清
- 用户听到的"Open Claw源码泄露"为误传，实际是 **Anthropic Claude Code CLI** 在2026-03-31发布npm包时意外打包source map，导致约51.2万行源码泄露
- **OpenClaw** 本身就是开源AI Agent项目（GitHub: https://github.com/openclaw-ai/OpenClaw），已有超过215,000 stars，不需要"泄露"

### nanobot vs OpenClaw 对比
| 维度 | OpenClaw | nanobot |
|------|----------|---------|
| 定位 | 全功能生产级产品 | 轻量学习研究原型 |
| 代码量 | ~30万+行 | ~3千行（核心Agent） |
| 架构 | 大而全，插件生态完善 | 极简微内核，模块化 |
| 优势 | 开箱即用，生态成熟 | 容易理解，适合二次开发 |

### Claude Code 泄露源码设计亮点整理
1. **双内存架构**：Session Memory（会话内12K token上限，每5K tokens/3工具调用自动整理） + Auto Memory（跨会话持久化，按主题文件，24h+5会话+锁触发consolidation）
2. **YOLO两阶段Prompt注入检测**：Stage1（64 token快速过滤，可疑就拦）→ Stage2（4096 token精细分析）
3. **Coordinator分叉子代理10条铁律**：强制最佳实践，避免反模式，缓存复用，防止递归爆炸
4. **功能gates（200+）**：灰度发布，快速回滚，A/B测试
5. **ULTRAPLAN分工协作**：重型规划离线给大模型，本地轮询等待，不卡住交互
6. **Anti-Distillation反蒸馏**：每个API请求注入fake_tools毒化偷训练数据集
7. **Dream System后台记忆consolidation**：Orient→Gather→Consolidate→Prune，自动后台整理
8. **BUDDY虚拟宠物系统**：Tamagotchi风格，18物种5稀有度，增加产品粘性
9. **Token细节优化**：JSON工具格式优化省~4.5% token，红act思考块节省token，按任务分配token预算
10. **Undercover Mode保密机制**：内部开发信息死代码消除，对外发布不可见

### 专业工程开发可借鉴优点
1. **功能Gate灰度发布体系**：新功能可先合并，灰度放量，一键回滚
2. **Undercover Mode保密机制**：工程化处理保密，不靠人自觉
3. **Token预算治理**：按任务配置token预算，成本可控
4. **YOLO两阶段安全检测**：平衡安全与速度
5. **双层记忆分离**：符合认知，自动整理
6. **子代理强制规则**：避免反模式，系统稳定
7. **大小模型分工**：重型规划离线，不卡交互
8. **细节优化降本**：每个请求省一点，量级上去很可观

### nanobot保持轻量前提下可升级点（分优先级）
**P0高优先级（改了收益大，代码少）**
1. 工具调用JSON格式压缩 → 省~4.5% token，改几行
2. Token预算配置化 → 不同任务不同预算，成本可控
3. 功能Gate基础支持 → 几十行代码，给未来开发保障

**P1中优先级（保持轻量，可以做）**
4. 两阶段安全检测框架 → 生产环境需要，做成可选模块
5. 子代理分叉规则校验 → 减少使用错误
6. 结构化日志 → 方便问题排查

**P2低优先级（后期再说）**
7. Auto Memory后台自动整理 → 当前手动整理可用
8. 完整操作审计 → 个人用不需要，企业部署才需要

## 2026-04-02 GitHub CLI 安装
- 用户询问nanobot是否有GitHub PR技能，已安装`github-cli`技能但缺少`gh` CLI依赖
- 用户要求安装，通过apt成功安装 **gh version 2.4.0+dfsg1**
- 当前状态：github-cli技能完整可用，支持创建PR、查看PR、合并PR、管理Issues

## 2026-04-02 基于Claude Code最佳实践 nanobot优化升级PR
### 优化目标
- 根据之前的分析，对nanobot实现P0+P1优先级改进，推送到https://github.com/HKUDS/nanobot创建PR
- 保持nanobot轻量特性，不增加依赖，保持向后兼容

### 已完成的优化（总计+416行 -14行，零新增依赖）
1. **新增 Feature Gate（特性开关）** `nanobot/config/feature_gate.py` (67行)
   - 轻量实现，支持灰度发布、一键回滚
   - 用法：`get_feature_gate().is_enabled("feature_name")`

2. **新增 Token 预算配置化** `config/schema.py`
   - 按任务类型配置不同max_tokens预算：default/simple_chat/planning/code_review/document_analysis/subagent
   - AgentRunSpec增加`max_tokens_task_type`参数自动查找预算
   - 平衡成本与输出质量，符合Claude Code的token预算治理经验

3. **新增 YOLO两阶段 Prompt 注入检测** `security/prompt_injection.py` (234行)
   - Stage1：64-token快速启发式关键词过滤，可疑就拦截
   - Stage2：LLM深度分析仅对可疑内容，平衡安全速度成本
   - 可配置拒绝阈值，集成到配置系统

4. **改进 子代理分叉规则强化** `agent/subagent.py`
   - 添加Claude Code风格10条不可协商子代理规则，防止反模式和递归爆炸
   - 核心规则：禁止递归分叉、保持专注、失败快速、提交后报告等

5. **相关配置和导入更新**
   - 更新`config/schema.py`添加`FeatureGatesConfig`, `TokenBudgetConfig`, `SecurityConfig`
   - 更新`config/__init__.py`导出新类型
   - 更新`agent/runner.py`支持token预算查找
   - 更新`security/__init__.py`导出检测器

### 当前状态
- ✅ 代码开发完成，通过Python导入测试，语法正确
- ✅ 已在本地创建Git commit：`feature/claude-code-engineering-improvements`
- ⚠️ GitHub推送认证失败：用户提供的密码认证不被GitHub支持（需要Personal Access Token），尝试gh auth login也因凭证错误失败
- 代码已准备就绪，提供有效PAT后即可推送并创建PR

## Nanobot项目当前状态（截至2026-04-02）
### 基本信息
- **名称**: Nanobot - Python-based AI Agent框架
- **支持渠道**: CLI/Webchat/QQ(官方API)/微信(已内置未启用)/其他平台已配置未启用
- **技术栈**: Python Flask，当前模型 minimax/MiniMax-M2.5（v0.1.4.post6存在兼容性问题，已降级回v0.1.4.post5）
- **时区**: Asia/Shanghai (UTC+8)
- **代码仓库**: https://gitee.com/frogcn/nanobot_frogcn (含nanobot-dev-skills子模块)

### 当前定时任务
1. 每日日志分析（凌晨00:00）：使用miniMax分析前一日日志，自动修复问题，更新README→ ✅ 2026-04-02正常执行
2. 每日科技简报（早上09:00）：获取HN新闻和GitHub热门项目，生成中文简报→ ✅ 正常执行

### 技能统计
- 总计17个技能，可用13个（内置5，第三方8）
- 已安装github-cli技能，gh CLI已安装完成，PR功能可用

### 已知问题
- v0.1.4.post6存在MiniMax兼容性问题，已降级
- 若干非关键问题：favicon 404等
- GitHub推送需要有效PAT才能完成PR创建