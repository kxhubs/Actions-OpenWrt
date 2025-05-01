#!/bin/bash
#
# https://github.com/P3TERX/Actions-OpenWrt
# File name: diy-part1.sh
# Description: OpenWrt DIY script part 1 (Before Update feeds)
#
# Copyright (c) 2019-2024 P3TERX <https://p3terx.com>
#
# This is free software, licensed under the MIT License.
# See /LICENSE for more information.
#

# Uncomment a feed source
#sed -i 's/^#\(.*helloworld\)/\1/' feeds.conf.default

# Add a feed source
#echo 'src-git helloworld https://github.com/fw876/helloworld' >>feeds.conf.default
#echo 'src-git passwall https://github.com/xiaorouji/openwrt-passwall' >>feeds.conf.default

# 额外编译的插件
package="luci-app-adguardhome luci-app-alpha-config luci-app-nikki luci-theme-alpha luci-theme-design luci-theme-ifit luci-theme-kucat"

git clone https://github.com/kenzok8/small-package.git -b main --single-branch --depth=1 --filter=blob:none --sparse small-package-temp
cd small-package-temp
git sparse-checkout init --cone
git sparse-checkout set $package
cd ..
rm -f small-package-temp/LICENSE  small-package-temp/README.md
cp -r small-package-temp/* package/
rm -rf small-package-temp


