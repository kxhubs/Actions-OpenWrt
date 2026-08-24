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

#默认主题
 WRT_THEME=glass
#默认主机名
# WRT_NAME=Kxhubs
#默认地址
WRT_IP=192.168.1.2

WRT_DATE=$(TZ=UTC-8 date +"%y.%m.%d_%H.%M.%S")
WRT_MARK=Kxhubs
CFG_FILE="./package/base-files/files/bin/config_generate"

case "$REPO_BRANCH" in
  openwrt-[0-9]*.[0-9]*|immortalwrt-[0-9]*.[0-9]*)
    OPENWRT_OFFICIAL_REPO="https://downloads.openwrt.org/releases/${REPO_BRANCH#*-}"
    ;;
  *)
    OPENWRT_OFFICIAL_REPO="https://downloads.openwrt.org/snapshots"
    ;;
esac

# Force generated APK/OPKG package feeds to use the official OpenWrt server.
sed -i '/^CONFIG_VERSION_REPO=/d' .config
echo "CONFIG_VERSION_REPO=\"$OPENWRT_OFFICIAL_REPO\"" >> .config

# Source-only feeds have no hosted APK index; keep them out of runtime repositories.
for SOURCE_ONLY_FEED in kenzo small bandix_core bandix_luci video; do
  sed -i "/^CONFIG_FEED_${SOURCE_ONLY_FEED}=/d; /^# CONFIG_FEED_${SOURCE_ONLY_FEED} is not set$/d" .config
  echo "# CONFIG_FEED_${SOURCE_ONLY_FEED} is not set" >> .config
done

#修改默认主题
sed -i "s/luci-theme-bootstrap/luci-theme-$WRT_THEME/g" "$(find ./feeds/luci/collections/ -type f -name "Makefile")"

#修改immortalwrt.lan关联IP
sed -i "s/192\.168\.[0-9]*\.[0-9]*/$WRT_IP/g" "$(find ./feeds/luci/modules/luci-mod-system/ -type f -name "flash.js")"

#添加编译日期标识
sed -i "s/(\(luciversion || ''\))/(\1) + (' \/ $WRT_MARK-$WRT_DATE')/g" "$(find ./feeds/luci/modules/luci-mod-status/ -type f -name "10_system.js")"

#修改默认主机名
# sed -i "s/hostname='.*'/hostname='$WRT_NAME'/g" $CFG_FILE
