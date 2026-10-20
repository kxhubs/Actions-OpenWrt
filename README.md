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
- `config/build-sources.json` 集中声明上游、全部 feeds、Go 和主题的仓库及分支。
  构建开始时用 `git ls-remote` 解析一次提交，生成 `Source_lock` 产物；两个架构
  均按其中的 SHA 获取源码。`Build_inputs_*` 记录版本清单、最终配置及规则文件校验值，
  发布时附带 `build-inputs.tar.gz`。规则文件仍取下载时的最新版，尚非离线可复现构建。
- 编译并行度依据 CPU 和可用内存选择；失败后用单线程详细输出诊断。
  通知使用 HTTPS、验证 API 返回值，缺少通知凭据时跳过，通知失败不影响固件构建。
- 编译线程数同时考虑 cgroup CPU/内存限额；预留 3 GiB 给系统及 runner，每个编译任务
  按 3 GiB 预算，下载使用独立并行度。云端保留已有 swap，不足 2 GiB 时增加 4 GiB
  临时 swap；本地 `act` 不修改宿主 swap。编译期间每分钟记录内存、swap、磁盘及
  cgroup 内存事件，保存为 `Build_resources_*` 诊断产物。
- 仅当 GitHub 明确标注 hosted runner 失联，且没有其他失败原因时，恢复工作流才会
  自动重跑失败任务一次。编译错误不触发此类重试；重新上传的同名产物会替换旧版本，
  避免重跑时出现 artifact 名称冲突。

### 构建加速与工作流

- `Repository checks` 在 push 和 PR 时运行脚本语法、隔离回归测试及 actionlint；
  固件工作流也先执行相同检查，通过后才启动耗时构建。
- 手动运行 `ImmortalWrt Builder` 时，`target` 可选 `both`、`R4S`、`x86_64`。
  单架构构建只发布该架构；默认仍编译并发布两个架构。`upload_bin` 默认关闭，
  需要全部软件包及原始 bin 输出时再开启。刷机镜像和构建记录始终保留。
- 同一分支、同一目标的构建排队执行，不中断正在运行的任务；GitHub concurrency
  只保留一个等待任务，新请求会替换旧的等待任务。重复请求不会同时占用编译资源。
- C/C++ 使用 OpenWrt 自带的 ccache，Go 使用独立构建缓存，Rust 使用 sccache。
  编译缓存按架构、最终配置、工具链目录、宿主 GCC、Go 和 Rust 配方隔离，
  不缓存 `build_dir` 或 `staging_dir`。首次构建需填充缓存，后续收益取决于命中率。
- 每个架构持久化上限：ccache 768 MiB、Go 256 MiB、sccache 128 MiB、下载目录
  1024 MiB。编译结束后按最近访问时间裁剪；Go 模块下载目录作为整体淘汰，避免半份模块。
  上限约束保存的缓存，不限制编译过程的峰值磁盘占用。GitHub 按仓库配额自动淘汰旧缓存。
- 缓存恢复后仍由 OpenWrt 校验下载文件。固件使用失败时的单线程诊断重试，摘要记录
  重试、编译秒数、缓存统计和磁盘余量，便于对比优化前后耗时。
- 镜像通常已经压缩，artifact 不再重复压缩；固件和可选 bin 产物保留 7 天，
  Release 产物不受此期限影响。当前先保留完整磁盘清理，收集磁盘余量后再决定缩减范围。
- `Update Checker` 每天北京时间 **11:17** 检查上游、feeds、Go 和主题；GitHub 定时任务
  可能延迟。输入版本或本仓库提交有变化时触发构建，并传递同一份版本清单。
  仅在触发 API 成功后记录该输入已派发；构建失败可手动重新运行固件工作流。
  此检查不监控 GeoIP/Geosite 的单独更新，需要规则更新时可手动构建。

构建工具版本及 SHA-256 固定在 `scripts/ci-tools.sh`。默认保留所有现有插件、
1 GiB 根分区，不添加自动扩容；轻量固件配置和减少磁盘清理可在测量后另行调整。

### 本地 act 兼容

GitHub 工作流使用 Node.js 24 的 `upload-artifact@v6` / `download-artifact@v7`。
需要旧版 artifact Action 的本地 `act` 请生成兼容副本，避免修改云端工作流后重新出现
Node.js 20 弃用警告：

```sh
python3 scripts/prepare_act.py
act workflow_dispatch -W .act/workflows/immortalwrt.yml --input target=R4S --env LOCAL_ACT=true
```

副本位于被忽略的 `.act/workflows`，其中上传/下载 Action 使用 v5/v6。
每次更新工作流后重新生成；继续使用本机已验证的容器镜像、架构及 artifact server 参数。
此生成步骤与副本语法已验证，完整 `act` 固件编译仍取决于本机环境。

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
也可使用与 CI 相同的完整检查入口：

```sh
bash scripts/ci-tools.sh lint
PATH="${RUNNER_TEMP:-/tmp}/openwrt-ci-tools:$PATH" bash scripts/check.sh
```

隔离测试覆盖下载、校验、备份和重启失败，以及主题定制。
新增测试覆盖版本清单校验、精确提交检出、配置保留、缓存隔离和淘汰。
完整固件编译及刷机验证仍需在 GitHub Actions 和实际设备上执行。
