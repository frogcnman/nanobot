#!/usr/bin/env python3
"""
nanobot-sync: 多实例增量同步升级插件
增量同步新功能/新技能到多台nanobot，不覆盖本地配置和记忆
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Optional

DEFAULT_CONFIG_PATH = Path.home() / ".nanobot" / "sync-servers.json"
DEFAULT_EXCLUDE = [
    ".env",
    "*.env",
    "*.json",
    "!*.json.example",
    "memory/",
    "*.log",
    "node_modules/",
    "__pycache__/",
    ".git/",
    "*.pyc",
]

class NanobotSync:
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config = self.load_config()
        
    def load_config(self) -> Dict:
        if not self.config_path.exists():
            default_config = {
                "servers": [],
                "gitRemote": "origin",
                "gitBranch": "main",
                "excludePaths": DEFAULT_EXCLUDE
            }
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
            print(f"⚠️  配置文件不存在，已创建默认配置: {self.config_path}")
            print("请编辑配置文件添加你的服务器信息")
            return default_config
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def run_git(self, args: List[str], cwd: Optional[Path] = None) -> int:
        """运行git命令"""
        result = subprocess.run(['git'] + args, cwd=cwd)
        return result.returncode
    
    def prepare(self, message: str) -> int:
        """准备同步：检查变更，提交到Git"""
        print("🔍 检查Git状态...")
        status = self.run_git(['status', '--porcelain'])
        if status != 0:
            print("❌ 不是一个Git仓库，请在nanobot根目录运行")
            return 1
        
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if not result.stdout.strip():
            print("✅ 没有变更需要提交")
            return 0
        
        print("📝 当前变更:")
        print(result.stdout)
        
        print("🚀 提交变更到Git...")
        self.run_git(['add', '.'])
        self.run_git(['commit', '-m', message])
        print(f"✅ 已提交: {message}")
        print(f"👉 下一步运行: git push {self.config['gitRemote']} {self.config['gitBranch']}")
        return 0
    
    def upgrade(self, nanobot_path: str = ".") -> int:
        """在生产机执行增量升级"""
        cwd = Path(nanobot_path).resolve()
        print(f"⬇️  开始增量升级，工作目录: {cwd}")
        
        # 1. 检查Git状态， stash 本地未提交变更
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True, cwd=cwd)
        if result.stdout.strip():
            print("💾 保存本地未提交变更...")
            self.run_git(['stash'], cwd=cwd)
        
        # 2. 拉取最新代码
        remote = self.config['gitRemote']
        branch = self.config['gitBranch']
        print(f"⬇️  拉取最新代码: {remote}/{branch}")
        if self.run_git(['pull', remote, branch], cwd=cwd) != 0:
            print("❌ git pull 失败，请检查网络/权限")
            return 1
        
        # 3. 恢复本地stash（不覆盖配置）
        if result.stdout.strip():
            print("♻️  恢复本地变更...")
            self.run_git(['stash', 'pop'], cwd=cwd)
        
        # 4. 升级依赖
        print("📦 升级依赖...")
        if (cwd / 'pyproject.toml').exists():
            subprocess.run(['uv', 'pip', 'install', '-e', '.'], cwd=cwd)
        elif (cwd / 'requirements.txt').exists():
            subprocess.run(['pip', 'install', '-r', 'requirements.txt'], cwd=cwd)
        
        print("✅ 升级完成！请重启nanobot生效")
        return 0
    
    def sync_server(self, server: Dict) -> bool:
        """SSH同步单个服务器"""
        name = server['name']
        host = server['host']
        port = server.get('port', 22)
        user = server.get('user', 'root')
        nanobot_path = server['nanobotPath']
        
        print(f"\n🚀 开始同步服务器: {name} ({user}@{host}:{port})")
        
        # 构建SSH命令
        upgrade_cmd = f"cd {nanobot_path} && python3 -m nanobot_sync upgrade"
        ssh_cmd = [
            'ssh',
            '-p', str(port),
            f"{user}@{host}",
            upgrade_cmd
        ]
        
        print(f"🔗 连接执行: {' '.join(ssh_cmd)}")
        result = subprocess.run(ssh_cmd)
        
        if result.returncode == 0:
            print(f"✅ 服务器 {name} 同步成功")
            return True
        else:
            print(f"❌ 服务器 {name} 同步失败")
            return False
    
    def sync_all(self) -> int:
        """批量同步所有服务器"""
        if not self.config['servers']:
            print("⚠️  没有配置服务器，请编辑: {self.config_path}")
            return 1
        
        print(f"📋 准备同步 {len(self.config['servers'])} 台服务器...")
        success = 0
        failed = 0
        
        for server in self.config['servers']:
            if self.sync_server(server):
                success += 1
            else:
                failed += 1
        
        print(f"\n📊 同步完成: 成功 {success}, 失败 {failed}")
        return 0 if failed == 0 else 1
    
    def log(self) -> int:
        """查看升级历史"""
        self.run_git(['log', '--oneline', '-20'])
        return 0
    
    def rollback(self, commit: str = None) -> int:
        """回滚到上一个版本"""
        if commit is None:
            print("⏪ 回滚到上一个提交...")
            self.run_git(['reset', '--hard', 'HEAD~1'])
        else:
            print(f"⏪ 回滚到提交: {commit}")
            self.run_git(['reset', '--hard', commit])
        print("✅ 回滚完成")
        return 0

def main():
    parser = argparse.ArgumentParser(description='nanobot-sync: 多实例增量同步升级')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # prepare
    prepare_parser = subparsers.add_parser('prepare', help='准备同步，提交变更到Git')
    prepare_parser.add_argument('message', help='提交信息')
    
    # upgrade
    upgrade_parser = subparsers.add_parser('upgrade', help='执行增量升级')
    upgrade_parser.add_argument('--path', default='.', help='nanobot根目录路径')
    
    # sync-all
    sync_all_parser = subparsers.add_parser('sync-all', help='批量同步所有服务器')
    
    # log
    log_parser = subparsers.add_parser('log', help='查看升级历史')
    
    # rollback
    rollback_parser = subparsers.add_parser('rollback', help='回滚到上一个版本')
    rollback_parser.add_argument('commit', nargs='?', help='回滚到指定commit')
    
    args = parser.parse_args()
    sync = NanobotSync()
    
    if args.command == 'prepare':
        sys.exit(sync.prepare(args.message))
    elif args.command == 'upgrade':
        sys.exit(sync.upgrade(args.path))
    elif args.command == 'sync-all':
        sys.exit(sync.sync_all())
    elif args.command == 'log':
        sys.exit(sync.log())
    elif args.command == 'rollback':
        sys.exit(sync.rollback(args.commit))
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
