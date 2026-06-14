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
WRT_THEME=argon
#默认主机名
# WRT_NAME=Kxhubs
#默认地址
WRT_IP=192.168.1.2

WRT_DATE=$(TZ=UTC-8 date +"%y.%m.%d_%H.%M.%S")
WRT_MARK=Kxhubs
CFG_FILE="./package/base-files/files/bin/config_generate"

#修改默认主题
sed -i "s/luci-theme-bootstrap/luci-theme-$WRT_THEME/g" "$(find ./feeds/luci/collections/ -type f -name "Makefile")"

#修改immortalwrt.lan关联IP
sed -i "s/192\.168\.[0-9]*\.[0-9]*/$WRT_IP/g" "$(find ./feeds/luci/modules/luci-mod-system/ -type f -name "flash.js")"

#添加编译日期标识
sed -i "s/(\(luciversion || ''\))/(\1) + (' \/ $WRT_MARK-$WRT_DATE')/g" "$(find ./feeds/luci/modules/luci-mod-status/ -type f -name "10_system.js")"

#修改默认主机名
# sed -i "s/hostname='.*'/hostname='$WRT_NAME'/g" $CFG_FILE
 
 # 修复 smartdns 编译：声明 zlib 运行时依赖（smartdns 二进制链接了 libz.so.1 但 Makefile 未声明）
 sed -i 's/DEPENDS:=+i386:libatomic +libopenssl/DEPENDS:=+i386:libatomic +libopenssl +zlib/' feeds/kenzo/smartdns/Makefile
 
 # 修复 trojan-plus Boost 库命名不匹配（OpenWrt 用 layout=system 无编译器标签，CMake FindBoost 默认搜索带标签的库名）
 find feeds/small -name "Makefile" -path "*/trojan-plus/*" -exec sed -i '/-DBoost_NO_BOOST_CMAKE=ON/ s/$/ -DBoost_USE_TAGED_LAYOUT=OFF/' {} \;
