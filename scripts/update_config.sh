#!/bin/sh

# 配置更新脚本 - 从GitHub下载配置文件，替换本地文件，重启服务
# 支持错误处理和回滚功能

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 恢复默认颜色

# 日志函数
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${BLUE}$1${NC}"
}

# 成功消息函数
log_success() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${GREEN}$1${NC}"
}

# 错误消息函数
log_error() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${RED}错误: $1${NC}"
}

# 警告消息函数
log_warning() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${YELLOW}$1${NC}"
}

# 错误处理函数 - 记录错误但不终止脚本
handle_error() {
    log_error "$1"
    failed_items+=("$2")
}

# 回退配置文件
rollback_config() {
    local_file=$(echo "$1" | cut -d'|' -f2)
    backup_file="${local_file}.bak"
    
    if [ -f "$backup_file" ]; then
        log_warning "回退 $local_file 配置文件"
        cp "$backup_file" "$local_file" || log_error "回退 $local_file 失败"
        rm -f "$backup_file"
    fi
}

# 配置信息
GITHUB_REPO="https://raw.githubusercontent.com/kxhubs/Actions-OpenWrt/main/other"
GHPROXY="https://gh-proxy.com/"

# 格式: "GitHub文件名|本地完整路径|服务名|进程名|是否检查进程(1=检查,0=不检查)"
FILES=(
    "smartdns|/etc/config/smartdns|smartdns|smartdns|1"
    "passwall|/etc/config/passwall|passwall|passwall|0"
    "AdGuardHome.yaml|/etc/AdGuardHome/AdGuardHome.yaml|AdGuardHome|AdGuardHome|0"
    "ddns-go|/etc/config/ddns-go|ddns-go|ddns-go|1"
    "ddns-go.yaml|/etc/ddns-go/config.yaml|ddns-go|ddns-go|1"
    "vlmcsd|/etc/config/vlmcsd|vlmcsd|vlmcsd|1"
)

# 创建临时目录
temp_dir=$(mktemp -d)
trap 'rm -rf "$temp_dir"' EXIT

# 初始化成功和失败数组
successful_items=()
failed_items=()
files_to_update=()

# 下载文件
log "开始下载配置文件..."
for file_info in "${FILES[@]}"; do
    github_file=$(echo "$file_info" | cut -d'|' -f1)
    local_file=$(echo "$file_info" | cut -d'|' -f2)
    service=$(echo "$file_info" | cut -d'|' -f3)
    
    original_url="${GITHUB_REPO}/${github_file}"
    proxy_url="${GHPROXY}${original_url#https://}"  # 修改代理链接生成方式
    temp_file="${temp_dir}/${github_file}"
    
    log "尝试使用ghproxy加速下载 $github_file"
    wget -q -T 30 -O "$temp_file" "$proxy_url"
    
    # 检查文件是否存在且不为空
    if [ -s "$temp_file" ]; then
        files_to_update+=("$file_info")
        successful_items+=("下载 $github_file")
        log_success "成功下载 $github_file (通过ghproxy加速)"
    else
        log_warning "ghproxy下载失败或超时，尝试使用原始链接下载"
        wget -q -T 30 -O "$temp_file" "$original_url"
        
        if [ -s "$temp_file" ]; then
            files_to_update+=("$file_info")
            successful_items+=("下载 $github_file")
            log_success "成功下载 $github_file (通过原始链接)"
        else
            handle_error "下载 $github_file 失败" "下载 $github_file"
            log_warning "跳过 $github_file 的处理"
        fi
    fi
done

# 备份并替换文件
log "开始备份并替换配置文件..."
for file_info in "${files_to_update[@]}"; do
    github_file=$(echo "$file_info" | cut -d'|' -f1)
    local_file=$(echo "$file_info" | cut -d'|' -f2)
    service=$(echo "$file_info" | cut -d'|' -f3)
    
    temp_file="${temp_dir}/${github_file}"
    
    # 确保目录存在
    mkdir -p "$(dirname "$local_file")"
    
    # 备份原文件
    backup_file="${local_file}.bak"
    if [ -f "$local_file" ]; then
        log "备份 $local_file 到 $backup_file"
        cp "$local_file" "$backup_file" || handle_error "备份 $local_file 失败" "备份 $local_file"
    else
        log_warning "$local_file 不存在，无需备份"
    fi
    
    # 替换文件
    log "替换 $local_file"
    cp "$temp_file" "$local_file" || handle_error "替换 $local_file 失败" "替换 $local_file"
done

# 重启所有服务
log "开始重启所有服务..."
for file_info in "${files_to_update[@]}"; do
    service=$(echo "$file_info" | cut -d'|' -f3)
    process_name=$(echo "$file_info" | cut -d'|' -f4)
    check_process=$(echo "$file_info" | cut -d'|' -f5)
    
    log "重启 $service 服务..."
    /etc/init.d/$service restart
    restart_status=$?
    
    # 检查服务状态
    if [ $restart_status -ne 0 ]; then
        handle_error "$service 服务重启失败" "重启 $service"
        rollback_config "$file_info"  # 回退配置文件
    else
        # 对于passwall不检查进程，直接标记成功
        if [ "$check_process" = "0" ]; then
            successful_items+=("重启 $service")
            log_success "$service 服务配置已更新"
        else
            log "检查 $service 服务进程..."
            sleep 2  # 等待服务启动
            
            # 使用pgrep检查进程是否存在
            if pgrep -f "$process_name" >/dev/null; then
                successful_items+=("重启 $service")
                log_success "$service 服务已成功启动"
            else
                handle_error "$service 服务未能正常运行" "验证 $service"
                rollback_config "$file_info"  # 回退配置文件
            fi
        fi
    fi
done

# 清理成功的备份文件
log "清理成功的备份文件..."
for file_info in "${files_to_update[@]}"; do
    local_file=$(echo "$file_info" | cut -d'|' -f2)
    backup_file="${local_file}.bak"
    service=$(echo "$file_info" | cut -d'|' -f3)
    
    if printf '%s\n' "${successful_items[@]}" | grep -q "重启 $service"; then
        if [ -f "$backup_file" ]; then
            rm -f "$backup_file"
            log_success "已删除 $local_file 的备份文件"
        fi
    fi
done

# 输出总结报告
echo ""
echo -e "${BLUE}========== 更新操作总结 ==========${NC}"
echo -e "${GREEN}成功项目:${NC}"
for item in "${successful_items[@]}"; do
    echo -e "✓ ${GREEN}$item${NC}"
done

echo ""
echo -e "${RED}失败项目:${NC}"
if [ ${#failed_items[@]} -eq 0 ]; then
    echo -e "✓ ${GREEN}无${NC}"
else
    for item in "${failed_items[@]}"; do
        echo -e "✗ ${RED}$item${NC}"
    done
fi
echo -e "${BLUE}=================================${NC}"

# 根据结果设置退出状态
if [ ${#failed_items[@]} -eq 0 ]; then
    log_success "所有配置更新完成，全部成功!"
    exit 0
else
    log_error "配置更新完成，但有 ${#failed_items[@]} 个项目失败"
    exit 1
fi
