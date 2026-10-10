**English** | [中文](https://p3terx.com/archives/build-openwrt-with-github-actions.html)

# Actions-OpenWrt

[![LICENSE](https://img.shields.io/github/license/mashape/apistatus.svg?style=flat-square&label=LICENSE)](https://github.com/P3TERX/Actions-OpenWrt/blob/master/LICENSE)
![GitHub Stars](https://img.shields.io/github/stars/P3TERX/Actions-OpenWrt.svg?style=flat-square&label=Stars&logo=github)
![GitHub Forks](https://img.shields.io/github/forks/P3TERX/Actions-OpenWrt.svg?style=flat-square&label=Forks&logo=github)

A template for building OpenWrt with GitHub Actions

## Usage

- Click the [Use this template](https://github.com/P3TERX/Actions-OpenWrt/generate) button to create a new repository.
- Generate `.config` files using [Lean's OpenWrt](https://github.com/coolsnowwolf/lede) source code. ( You can change it through environment variables in the workflow file. )
- Push `.config` file to the GitHub repository.
- Select `Build OpenWrt` on the Actions page.
- Click the `Run workflow` button.
- When the build is complete, click the `Artifacts` button in the upper right corner of the Actions page to download the binaries.

## Tips

- It may take a long time to create a `.config` file and build the OpenWrt firmware. Thus, before create repository to build your own firmware, you may check out if others have already built it which meet your needs by simply [search `Actions-Openwrt` in GitHub](https://github.com/search?q=Actions-openwrt).
- Add some meta info of your built firmware (such as firmware architecture and installed packages) to your repository introduction, this will save others' time.

## Credits

- [Microsoft Azure](https://azure.microsoft.com)
- [GitHub Actions](https://github.com/features/actions)
- [OpenWrt](https://github.com/openwrt/openwrt)
- [coolsnowwolf/lede](https://github.com/coolsnowwolf/lede)
- [Mikubill/transfer](https://github.com/Mikubill/transfer)
- [softprops/action-gh-release](https://github.com/softprops/action-gh-release)
- [Mattraks/delete-workflow-runs](https://github.com/Mattraks/delete-workflow-runs)
- [dev-drprasad/delete-older-releases](https://github.com/dev-drprasad/delete-older-releases)
- [peter-evans/repository-dispatch](https://github.com/peter-evans/repository-dispatch)

## License

[MIT](https://github.com/P3TERX/Actions-OpenWrt/blob/main/LICENSE) © [**P3TERX**](https://p3terx.com)

## 本仓库的构建与维护说明

- R4S 与 x86_64 的初始根分区均为 **1024 MiB**。保留全部现有插件选择。
- 固件不包含自动扩容脚本，首次启动不会自动修改磁盘分区。
- 保留 ImmortalWrt 自带软件源及签名校验。源码专用 feeds 不写入运行时软件源。
  自编译固件安装额外包时仍需确认版本、架构及内核 ABI 匹配。
- 同一次构建的两个架构使用同一个上游提交。`Build_inputs_*` 产物记录最终配置、
  上游/feeds/Go/主题提交及规则文件校验值，发布时附带 `build-inputs.tar.gz`。
  第三方 feeds 仍跟随分支更新；这些记录用于追踪差异，不代表已经完成离线可复现构建。
- 编译并行度依据 CPU 和可用内存选择；失败后用单线程详细输出诊断。
  通知使用 HTTPS、验证 API 返回值，缺少通知凭据时跳过，通知失败不影响固件构建。

### 路由器配置更新

在路由器上以 root 执行 `sh scripts/update_config.sh`。需要 `curl`、`uci`、
`jsonfilter`、`ubus`；仅更新已安装的服务。直接从 GitHub HTTPS 下载，
可用 `CONFIG_BASE_URL` 指定受信任的 HTTPS 配置目录。

UCI 配置先验证再写入；YAML 配置需要 Ruby 的 Psych 解析器，缺少解析器时
跳过相关服务并返回失败，不会覆盖原配置。YAML 验证仅验证语法及顶层映射，
实际服务兼容性通过重启和状态检查验证。使用共享模板会替换设备上的自定义配置，
请先确认仓库配置符合当前设备，尤其是网络、防火墙及账号设置。

同一服务的文件全部下载、校验及备份后才替换，ddns-go 两个文件一起更新并仅重启一次。
失败时回滚已替换的文件并重启原服务；若文件恢复失败，备份保留在输出提示的
`/tmp/update-config-recovery.*` 目录，需及时复制到持久存储。
不存在的 Passwall 配置不再列入更新清单；以后添加 Passwall2 配置时需同时添加对应服务项。

### 本地检查

```sh
python3 -m unittest discover -s tests -v
sh -n scripts/update_config.sh
bash -n scripts/diy-part1.sh
bash -n scripts/diy-part2.sh
```

安装 actionlint 后运行 `actionlint -shellcheck= -pyflakes=` 校验工作流。
隔离测试覆盖下载、校验、备份和重启失败，以及主题定制。
完整固件编译及刷机验证仍需在 GitHub Actions 和实际设备上执行。
