#!/bin/bash
# Webchat Systemd Service Installer
# This script installs webchat as a systemd service that starts automatically

set -e

# Configuration
SERVICE_NAME="nanobot-webchat"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# webchat is in nanobot/webchat, so project root is two levels up
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_PATH="/usr/bin/python3"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "此脚本需要 root 权限运行"
        print_info "请使用: sudo $0"
        exit 1
    fi
}

# Detect Python path
detect_python() {
    # Try to find python3
    if command -v python3 &> /dev/null; then
        PYTHON_PATH=$(which python3)
    elif command -v python &> /dev/null; then
        PYTHON_PATH=$(which python)
    else
        print_error "未找到 Python，请先安装 Python 3"
        exit 1
    fi
    print_info "检测到 Python: $PYTHON_PATH"
}

# Create systemd service file
create_service_file() {
    print_info "创建 systemd 服务文件..."
    
    # Get the actual user (not root)
    ACTUAL_USER=${SUDO_USER:-$USER}
    ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Nanobot Webchat Service
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${ACTUAL_USER}
Group=${ACTUAL_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="PYTHONPATH=${PROJECT_DIR}"
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=${PYTHON_PATH} -m nanobot.webchat
Restart=always
RestartSec=5
StandardOutput=append:${ACTUAL_HOME}/.nanobot/webchat.log
StandardError=append:${ACTUAL_HOME}/.nanobot/webchat.log

# Note: PrivateTmp is disabled because project is in /tmp
# For production, move project to /opt/nanobot and enable PrivateTmp
PrivateTmp=false

[Install]
WantedBy=multi-user.target
EOF

    print_info "服务文件已创建: $SERVICE_FILE"
}

# Install the service
install_service() {
    print_info "安装服务..."
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable ${SERVICE_NAME}.service
    
    print_info "服务已安装并设置为开机自启"
}

# Start the service
start_service() {
    print_info "启动服务..."
    systemctl start ${SERVICE_NAME}.service
    
    sleep 2
    
    if systemctl is-active --quiet ${SERVICE_NAME}.service; then
        print_info "服务启动成功!"
        print_info "状态: $(systemctl status ${SERVICE_NAME}.service --no-pager | head -5)"
    else
        print_error "服务启动失败，请检查日志:"
        journalctl -u ${SERVICE_NAME}.service -n 20 --no-pager
        exit 1
    fi
}

# Show service info
show_info() {
    echo ""
    echo "=========================================="
    echo "  Nanobot Webchat 服务安装完成!"
    echo "=========================================="
    echo ""
    echo "服务名称: ${SERVICE_NAME}"
    echo "服务文件: ${SERVICE_FILE}"
    echo ""
    echo "常用命令:"
    echo "  启动服务:   sudo systemctl start ${SERVICE_NAME}"
    echo "  停止服务:   sudo systemctl stop ${SERVICE_NAME}"
    echo "  重启服务:   sudo systemctl restart ${SERVICE_NAME}"
    echo "  查看状态:   sudo systemctl status ${SERVICE_NAME}"
    echo "  查看日志:   journalctl -u ${SERVICE_NAME} -f"
    echo "  禁用自启:   sudo systemctl disable ${SERVICE_NAME}"
    echo ""
    echo "访问地址: http://localhost:8081"
    echo ""
}

# Uninstall the service
uninstall_service() {
    print_info "卸载服务..."
    
    systemctl stop ${SERVICE_NAME}.service 2>/dev/null || true
    systemctl disable ${SERVICE_NAME}.service 2>/dev/null || true
    
    if [[ -f "$SERVICE_FILE" ]]; then
        rm -f "$SERVICE_FILE"
        systemctl daemon-reload
        print_info "服务已卸载"
    else
        print_warn "服务文件不存在"
    fi
}

# Main
main() {
    echo ""
    echo "=========================================="
    echo "  Nanobot Webchat 服务安装器"
    echo "=========================================="
    echo ""
    
    case "${1:-install}" in
        install)
            check_root
            detect_python
            create_service_file
            install_service
            start_service
            show_info
            ;;
        uninstall|remove)
            check_root
            uninstall_service
            ;;
        status)
            systemctl status ${SERVICE_NAME}.service --no-pager
            ;;
        logs)
            journalctl -u ${SERVICE_NAME}.service -f
            ;;
        restart)
            check_root
            systemctl restart ${SERVICE_NAME}.service
            print_info "服务已重启"
            ;;
        *)
            echo "用法: $0 {install|uninstall|status|logs|restart}"
            echo ""
            echo "  install   - 安装并启动服务 (默认)"
            echo "  uninstall - 停止并卸载服务"
            echo "  status    - 查看服务状态"
            echo "  logs      - 查看服务日志"
            echo "  restart   - 重启服务"
            exit 1
            ;;
    esac
}

main "$@"
