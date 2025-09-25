#!/bin/bash

# 配置变量：需要添加的插件文件夹名称
PLUGINS="luci-app-adguardhome nikki luci-app-nikki luci-app-store luci-app-lucky luci-app-quickstart quickstart"

# 基础目录
CUSTOM_FEED_DIR="package/custom"
FEEDS_CONF="feeds.conf.default"

# 创建自定义feed目录
mkdir -p "$CUSTOM_FEED_DIR"

# 克隆kenzok8/small-package仓库（仅获取指定插件）
echo "正在获取插件源代码..."
git clone https://github.com/kenzok8/small-package.git -b main --single-branch --depth=1 --filter=blob:none --sparse temp-repo
cd temp-repo || exit

# 设置稀疏检出（只获取指定插件文件夹）
git sparse-checkout init --cone
git sparse-checkout set $PLUGINS

# 复制插件到custom目录
echo "正在复制插件到 $CUSTOM_FEED_DIR..."
ADDED_PLUGINS=""  # 存储实际添加的插件名称
for plugin in $PLUGINS; do
    if [ -d "$plugin" ]; then
        cp -r "$plugin" ../"$CUSTOM_FEED_DIR"
        if [ $? -eq 0 ]; then
            ADDED_PLUGINS="$ADDED_PLUGINS $plugin"
            echo "✓ 已复制: $plugin"
        else
            echo "✗ 复制失败: $plugin"
        fi
    else
        echo "✗ 未找到插件: $plugin"
    fi
done

cd ..
rm -rf temp-repo

# 更新feeds配置
echo "正在更新feeds配置..."
if [ ! -f "$FEEDS_CONF" ]; then
    touch "$FEEDS_CONF"
    echo "# 自定义feeds配置" > "$FEEDS_CONF"
fi

# 添加或更新custom feed源
if ! grep -q "src-link custom" "$FEEDS_CONF"; then
    echo "src-link custom $CUSTOM_FEED_DIR" >> "$FEEDS_CONF"
else
    sed -i "s|^src-link custom.*|src-link custom $CUSTOM_FEED_DIR|" "$FEEDS_CONF"
fi

echo "✓ 已更新 feeds.conf"


# 显示添加的插件列表
echo "============================"
echo "以下插件已成功添加:"
echo "$ADDED_PLUGINS" | tr ' ' '\n' | grep -v '^$' | sed 's/^/ - /'
echo "============================"
