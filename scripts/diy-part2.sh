#!/bin/bash
#
# https://github.com/P3TERX/Actions-OpenWrt
# File name: diy-part2.sh
# Description: OpenWrt DIY script part 2 (After Update feeds)
#
# Copyright (c) 2019-2024 P3TERX <https://p3terx.com>
#
# This is free software, licensed under the MIT License.
# See /LICENSE for more information.
#

set -euo pipefail

#默认主题
WRT_THEME=aurora
#默认主机名
# WRT_NAME=Kxhubs
#默认地址
WRT_IP=192.168.1.2

WRT_DATE=$(TZ=UTC-8 date +"%y.%m.%d_%H.%M.%S")
WRT_MARK=Kxhubs
CFG_FILE="./package/base-files/files/bin/config_generate"

# Add the standalone LuCI theme package before make defconfig.
AURORA_DIR="package/luci-theme-aurora"
if [ ! -d "$AURORA_DIR" ]; then
  git clone --depth 1 https://github.com/eamonxg/luci-theme-aurora.git "$AURORA_DIR"
fi

# Keep the upstream ImmortalWrt repository template and signing keys.
sed -i '/^CONFIG_VERSION_REPO=/d' .config

# Source-only feeds have no hosted APK index; keep them out of runtime repositories.
for SOURCE_ONLY_FEED in passwall_packages kenzo small bandix_core bandix_luci video; do
  sed -i "/^CONFIG_FEED_${SOURCE_ONLY_FEED}=/d; /^# CONFIG_FEED_${SOURCE_ONLY_FEED} is not set$/d" .config
  echo "# CONFIG_FEED_${SOURCE_ONLY_FEED} is not set" >> .config
done

#修改默认主题
sed -i "s/luci-theme-bootstrap/luci-theme-$WRT_THEME/g" ./feeds/luci/collections/luci/Makefile

# 设置实际 LAN 默认地址，同时更新刷机提示。
sed -i "s/192\.168\.1\.1/$WRT_IP/g" "$CFG_FILE"

#修改immortalwrt.lan关联IP
find ./feeds/luci/modules/luci-mod-system/ -type f -name flash.js -exec sed -i "s/192\.168\.[0-9]*\.[0-9]*/$WRT_IP/g" {} +

#添加编译日期标识
sed -i "s/(\(luciversion || ''\))/(\1) + (' \/ $WRT_MARK-$WRT_DATE')/g" ./feeds/luci/modules/luci-mod-status/htdocs/luci-static/resources/view/status/include/10_system.js

#修改默认主机名
# sed -i "s/hostname='.*'/hostname='$WRT_NAME'/g" $CFG_FILE
