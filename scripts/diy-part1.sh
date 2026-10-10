#!/bin/bash
set -euo pipefail

# 将三方插件库插入顶部；重复运行时先移除同名项。
sed -i -E '/^src-git(-full)? (passwall_packages|kenzo|small|bandix_core|bandix_luci) /d' feeds.conf.default

sed -i '1i src-git passwall_packages https://github.com/Openwrt-Passwall/openwrt-passwall-packages.git;main' feeds.conf.default
sed -i '2i src-git kenzo https://github.com/kenzok8/openwrt-packages' feeds.conf.default
sed -i '3i src-git small https://github.com/kenzok8/small' feeds.conf.default
sed -i '4i src-git bandix_core https://github.com/timsaya/openwrt-bandix;main' feeds.conf.default
sed -i '5i src-git bandix_luci https://github.com/timsaya/luci-app-bandix;main' feeds.conf.default
./scripts/feeds update -a
rm -rf feeds/luci/applications/luci-app-mosdns
rm -rf feeds/packages/net/{alist,adguardhome,mosdns,xray*,v2ray*,sing*,smartdns}
rm -rf feeds/packages/utils/v2dat
rm -rf feeds/packages/lang/golang

# 更新Golang版本
git clone https://github.com/sbwml/packages_lang_golang -b 27.x feeds/packages/lang/golang

./scripts/feeds install -a
# clashoo also PROVIDES mihomo and triggers a recursive Kconfig dependency.
# These configurations use mihomo directly; leave its alternate provider uninstalled.
./scripts/feeds uninstall clashoo
./scripts/feeds install -p passwall_packages -f xray-core v2ray-geoip v2ray-geosite
