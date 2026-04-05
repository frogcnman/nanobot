# nanobot-sync 多实例增量同步插件

## 功能

让你在一台 nanobot 上验证新功能/新技能后，一键增量同步到其他多台 nanobot 实例，保持全集群版本一致。

### 特性：
- ✅ 增量同步，只更改变更过的文件
- ✅ 不覆盖本地配置和记忆
- ✅ 自动安装新增依赖
- ✅ 支持SSH批量同步到多台服务器
- ✅ 生成升级日志，方便回滚

## 工作流

1. **开发机**：你在开发机尝鲜新功能、安装新技能，验证没问题
2. **开发机**：运行 `nanobot-sync prepare` → 自动把变更提交到Git仓库
3. **生产机**：运行 `nanobot-sync upgrade` → 自动拉取最新代码，增量升级，不碰本地配置
4. **批量模式**：开发机运行 `nanobot-sync sync-all` → 自动SSH到所有生产机执行升级

## 配置文件

创建 `~/.nanobot/sync-servers.json` 格式：

```json
{
  "servers": [
    {
      "name": "tokenport-prod-1",
      "host": "1.2.3.4",
      "port": 22,
      "user": "root",
      "keyPath": "~/.ssh/id_rsa",
      "nanobotPath": "/root/nanobot"
    },
    {
      "name": "mediation-bot",
      "host": "5.6.7.8",
      "port": 22,
      "user": "root",
      "password": "your-password",
      "nanobotPath": "/opt/nanobot"
    }
  ],
  "gitRemote": "origin",
  "gitBranch": "main",
  "excludePaths": [
    ".env",
    "*.json",
    "!*.json.example",
    "memory/",
    "*.log",
    "node_modules/",
    "__pycache__/",
    ".git/"
  ]
}
```

## 安装

```bash
# 从技能市场安装
nanobot install nanobot-sync
```

## 使用方法

### 在开发验证机上：

```bash
# 准备同步：检查变更，提交到Git
nanobot-sync prepare "升级了AgentReach v0.2，新增了exa搜索"
```

### 在每台生产机上手动升级：

```bash
# 一键增量升级
nanobot-sync upgrade
```

### 在开发机批量同步到所有生产机：

```bash
# 自动SSH连接所有服务器，执行升级
nanobot-sync sync-all
```

### 查看升级历史：

```bash
nanobot-sync log
```

### 回滚到上一个版本：

```bash
nanobot-sync rollback
```

## 安全

- SSH连接使用你的现有密钥，不保存密码
- 只同步Git仓库内的代码，不会碰你没提交的本地文件
- 升级前自动备份当前版本，出问题可以一键回滚

## 作者

nanobot
