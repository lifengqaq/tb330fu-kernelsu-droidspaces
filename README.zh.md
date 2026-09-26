# TB330FU 自定义内核构建仓库（kbuild）

为 **联想 Tab M11（TB330FU，MTK MT8786，代号 barley）** 构建
**Linux 6.6.30 / android15-6.6** 自定义内核的 GitHub Actions 仓库。

集 **Droidspaces**（安卓上的 Linux 容器）与 **KernelSU**（root）于一体。
构建产物为可直接刷写的 `boot.img`（Android boot v4）、AnyKernel3 刷机包
以及原始 `Image.gz`。

> **不用 SusFS。** Droidspaces 官方明确声明不支持 SusFS（见其
> Documentation），本仓库遵循官方方案，未集成任何 SusFS 补丁。

---

## 1. 目标设备与基线

| 项 | 值 |
|---|---|
| 设备 | 联想 Tab M11（TB330FU，barley，tb8786p1_64，MT8786） |
| 固件 | Android 15（alps k66），内核 Linux 6.6.30 |
| 内核源码基线 | AOSP `kernel/common` commit **94c1a24cabd5**（与官方固件同源） |
| 官方版本串 | `6.6.30-android15-8-g94c1a24cabd5-ab12293704-4k` |
| 基础 config | 从当前槽位 boot.img 内核 IKCONFIG 段提取的官方出厂 config |
| boot 镜像形态 | Android boot image **v4**：仅 gzip 内核、无 ramdisk、页 4096、无 AVB 强制校验 |

> 注意：Google GKI 仓库中**并不存在** `android15-6.6.30` 这个 tag
> （tag 形如 `android15-6.6.46_r00` / `android15-6.6-2024-07_r1`，最低
> sublevel 为 46）。因此本仓库不用 tag，而是**按精确 commit SHA 拉取**
> `94c1a24cabd5`（已验证存在于 android.googlesource.com，Makefile 为
> 6.6.30，与设备固件内核源一致）。

## 2. 仓库结构

```
kbuild/
 .github/workflows/build.yml   # GitHub Actions 构建流程（手动触发）
 config/
    barley_defconfig          # 官方 config + 2 处记录在案的修改
    droidspaces.fragment      # Droidspaces GKI 专属配置（16 项，kABI 安全）
    kernelsu.fragment         # KernelSU 依赖（含关键项 FTRACE_SYSCALLS=y）
    anykernel.sh              # AnyKernel3 打包配置（内核替换模式）
 patches/
    0001-droidspaces-gki-sysvipc-kabi.patch   # Droidspaces SYSVIPC kABI 补丁（原样）
    alternatives/             # 备选/替代补丁（workflow 默认不应用）
    README.zh.md              # 补丁说明与适配性分析
 tools/
    mkboot_v4.py              # 纯 Python 构造 Android boot v4 镜像
 .gitignore
 README.zh.md                  # 本文件
```

## 3. 构建策略要点

1. **源码**：`git init` + `git fetch --depth 1 origin 94c1a24cabd5`
   （全量 clone 太大；失败时自动回退 gitiles 归档 tar）。该树 **没有**
   `localversion*` / `.scmversion` 文件（已核实），版本串完全由
   `Makefile`（6.6.30）+ `CONFIG_LOCALVERSION` 决定。
2. **config**：`barley_defconfig` = 官方出厂 config 逐字拷贝，只改
   `CONFIG_LOCALVERSION`（拼出完整官方版本串）和
   `CONFIG_LOCALVERSION_AUTO`（yn，见 5）。构建时再叠加
   `droidspaces.fragment` + `kernelsu.fragment`（merge_config.sh）。
3. **补丁**：Droidspaces 的 SYSVIPC kABI 补丁（`patches/0001`，原样保留）。
4. **KernelSU**：官方 `kernel/setup.sh` 集成 tiann/KernelSU v3.3.0
   （clone 到 `kernel/KernelSU`，符号链接 `drivers/kernelsu`，自动挂
   Makefile/Kconfig 条目）。**v3.3.0 无需任何 fs/*.c 手动 hook 补丁**，
   详见 `patches/README.zh.md`。
5. **产物**：`make Image.gz`（clang/lld，LLVM=1） 校验 banner 
   `tools/mkboot_v4.py` 打成 boot.img  AnyKernel3 zip。

## 4. 推送到 GitHub

本仓库将被推送到 **lifengqaq** 账号下的新仓库（由 Lead 执行）。
如需自行操作：

```bash
cd kbuild
git init -b main
git add -A
git commit -m "TB330FU kernel build scaffolding (android15-6.6.30 + Droidspaces + KernelSU)"
# 在 GitHub 网页上新建空仓库（不要勾选初始化 README），然后：
git remote add origin git@github.com:lifengqaq/<仓库名>.git
git push -u origin main
```

- 也可用 `gh repo create` / GitHub Desktop 等任何你熟悉的方式。
- 仓库应为 **Private**（避免他人误刷你的定制内核）。
- 提交前确认没有大文件：本仓库全部为文本文件，`.gitignore` 已排除
  `*.img`、`*.zip`、`kernel/` 等。

## 5. 为什么版本串必须逐字符一致（vermagic）

设备内核开启 **`CONFIG_MODVERSIONS=y`**：vendor 分区里的厂商模块
（GPU、触控、WiFi 等以 .ko 形式存在的驱动）在加载时会校验
**vermagic**，其中包含完整 `UTS_RELEASE`。版本串差一个字符，所有
厂商模块都拒绝加载  WiFi/触屏/显示等全部失效，甚至无法开机。

官方串的构成（kleaf 构建系统注入，普通 make 无法自动复现）：

```
6.6.30 - android15-8 - g94c1a24cabd5 - ab12293704 - -4k
                                                 
                                                  CONFIG_LOCALVERSION（官方原值）
                                         kleaf 构建 id（ab...)
                          git describe 的 -g<sha>
             分支名 android15-8
  Makefile VERSION.PATCHLEVEL.SUBLEVEL
```

本仓库的复现方式（三件事，缺一不可）：

1. `barley_defconfig` 中 `CONFIG_LOCALVERSION` 直接写成完整后缀
   `-android15-8-g94c1a24cabd5-ab12293704-4k`；
2. `CONFIG_LOCALVERSION_AUTO` 改为 **n**（官方值是 y，但在我们这种
   git 拉取的源码树上会追加不可控的 `-g<sha>` / `-dirty` 后缀）；
3. 构建时设置环境变量 **`LOCALVERSION=""`**（build.yml 已处理）：
   6.6 的 `scripts/setlocalversion` 在 `AUTO=n` 且 `LOCALVERSION`
   未设置时仍会调用 `scm_version --short`，对无 tag 的树输出 **`+`**，
   这会直接毁掉版本串；显式设空串可完全关掉 scm 增量。

构建完成后 workflow 会从 `out/include/generated/utsrelease.h` 和
解压后的 `Image` 里提取 banner，与官方串**逐字符比对**，不一致直接
fail（见 build.yml "Verify kernel banner" 步骤）。

## 6. 为什么 config 必须逐字对齐（WiFi 的教训）

此前曾用 AOSP 源码 + `gki_defconfig` 构建并刷入过：除 WiFi 外一切
正常。根因就是 config 不对官方 config 与 gki_defconfig 的关键差异：

| 符号 | 官方 config | gki_defconfig | 影响 |
|---|---|---|---|
| `CONFIG_CFG80211` | **未设** | 未设 | 同 |
| `CONFIG_RFKILL` | **m** | 未设 | WiFi 模块加载链断裂 |
| `CONFIG_WLAN` | **y** | 未设 | MTK 全栈 WiFi 驱动无法进内核 |
| `CONFIG_KALLSYMS_ALL` | y | y |  |

MTK 平台的 WiFi 是全栈模块驱动，对这些符号的组合非常敏感。因此本仓库
的 config 策略是：**以官方提取值为唯一基准，只叠加 Droidspaces /
KernelSU 所需的最小增量**（两个 fragment + kABI 补丁），不做任何
"顺手优化"。

## 7. 运行构建（GitHub Actions）

1. 打开仓库页面  **Actions** 标签页（首次会要求点击 "I understand my
   workflows, go ahead and enable them"）。
2. 左侧选择 **"Build TB330FU kernel (android15-6.6.30)"**。
3. 点击右侧 **Run workflow** 下拉按钮，可选参数：
   - `kernel_sha`：内核源码 commit，默认 `94c1a24cabd5`（官方基线，
     **不要改**，除非你知道自己在做什么改了它 banner 校验会放宽，
     且 defconfig 里的版本串也要手动同步）；
   - `ksu_tag`：KernelSU 版本，默认 `v3.3.0`（官方最新 release）。
4. 点击绿色 **Run workflow** 按钮。整个流程约 4090 分钟
   （含拉源码、编译 BTF/DWARF5 调试信息）。
5. 构建过程出现黄色 `::warning::`（如 0001 补丁走 GNU patch fuzz 回退）
   是预期内的；红色 `::error::` 才是失败。

## 8. 下载产物

构建成功后，进入该次 run 的页面  底部 **Artifacts** 区域，下载：

| Artifact | 内容 | 用途 |
|---|---|---|
| `boot-img-<sha>-ksu-<tag>` | `boot.img`、`anykernel.zip` | 刷机用 |
| `kernel-build-<sha>-ksu-<tag>` | `Image`、`Image.gz`、`out/.config`、`utsrelease.h`、`banner-check.txt`、`boot-img-info.txt` | 排查/存档 |

注意：
- Artifact 默认保留 **14 天**，请及时转存；
- 下载需要登录 GitHub 账号；
- `boot-img-info.txt` 里核对 `kernel_size` / `gzip = True`；
  `banner-check.txt` 里核对版本串与官方一致。

## 9. 刷入方式

> **刷机有风险。** 任何一步都可能变砖。务必先完整备份当前槽位的
> `boot`（以及 `init_boot`、`vendor_boot`、`dtbo` 等）分区镜像，
> 保留 Fastboot/BROM 救砖通道，再开始操作。

### 方式 A：GeekFlashTool（BROM 直刷 boot.img）推荐

1. 手机关机，按住音量键（MTK BROM 模式）连接电脑；
2. GeekFlashTool 选择 `boot` 分区（注意当前槽位 a/b），刷入
   下载的 `boot.img`；
3. 重启。首次启动较慢（SELinux 重建等）属正常。

此前用无签名的 AOSP 自编译镜像刷入可正常启动，说明本机引导流程
不强制 AVB 校验本工具产出的 `boot.img` 不含 signature/footer。

### 方式 B：AnyKernel3（已 root / 自定义 recovery 下刷）

1. 把 `anykernel.zip` 传到手机；
2. 在 KernelSU 管理器或自定义 recovery 中刷入该 zip
   （AK3 会自动 dump 当前 boot、替换内核、回写）。

### 方式 C：fastboot（若 bootloader 已解锁）

```
fastboot flash boot boot.img
fastboot reboot
```

### 回滚

用备份的原厂镜像按同样方式刷回即可（或 `fastboot flash boot
boot_backup.img`）。

## 10. KernelSU 管理器

- 从 <https://github.com/tiann/KernelSU/releases> 下载 **与构建相同
  版本** 的管理器 APK（默认构建用 **v3.3.0**，就下 v3.3.0 release 的
  manager APK），安装后打开。
- 管理器显示"正在工作"即内核侧集成成功。
- 之后在管理器里给需要的 App 授权 root。

## 11. Droidspaces

1. 从 <https://github.com/ravindu644/Droidspaces-OSS/releases> 下载
   App 并安装；
2. 打开 Droidspaces  设置（齿轮） **Requirements  Check
   Requirements**，检查内核能力清单；
3. 或在终端执行：

   ```bash
   su -c droidspaces check
   ```

   全绿（PID/MNT/UTS/IPC 命名空间、devtmpfs、cgroups、seccomp 等）
   即本内核的 Droidspaces 增量全部生效。

### UFW / REJECT 规则的限制

Droidspaces 文档的 GKI 推荐配置包含 `CONFIG_NETFILTER_XT_TARGET_REJECT`，但该目标在
android15-6.6 GKI 源码树（94c1a24cabd5）中已被 Google 整体移除（无 `xt_REJECT.c`、
无对应 Kconfig 符号），官方 stock 配置也未启用 nftables（`NF_TABLES` 未开）。因此：

- UFW 的 REJECT 类规则在本内核上不可用（Droidspaces 官方将此项标注为"可选"）
- UFW 的 DROP / ACCEPT / LOG 等其余规则正常；Fail2ban 所需的 IP_SET 全套已启用
- 若未来确需 REJECT，可在 fragment 中引入 `NF_TABLES=y` + `NFT_REJECT=y` + `NFT_COMPAT=y`
  （config 面扩大，需自行评估与厂商模块的兼容性后再上机）

## 12. 为什么不用 SusFS

- Droidspaces 官方（Documentation / Kernel-Configuration.md）明确
  **不支持 SusFS**，其容器隔离方案与 SusFS 的隐藏逻辑无关；
- SusFS 与 GKI kABI 管理冲突面大，且与 KernelSU 主线无官方集成；
- 本仓库目标是"官方基线 + 最小增量"，多一个非必要补丁就多一分
  vermagic/ABI 风险。

如未来需要隐藏 root 痕迹，建议研究 KernelSU 自身的隐藏策略，而不是
引入 SusFS。

## 13. 风险与警告（务必阅读）

- **变砖风险**：boot 镜像错误会导致无法开机。MTK 设备有 BROM 救砖
  通道（GeekFlashTool / SP Flash Tool），但请提前演练/确认线缆与驱动。
- **备份数据**：刷机失败可能需要 wipe。先备份重要数据。
- **保留原厂镜像**：构建前请确认你手里有当前槽位完整分区备份
  （boot/init_boot/vendor_boot/dtbo 等）。
- **保修**：解锁/刷自定义内核通常影响保修。
- **版本漂移**：任何对 `barley_defconfig` 的多余改动都可能破坏
  vermagic  厂商模块失效。修改前请重读 5/6。

## 14. 常见问题

- **Q: 构建中 0001 补丁出现 warning "git apply 失败，改用 GNU patch"？**
  预期内。该补丁第二个 hunk 的尾部上下文在 6.6.30 源上已漂移
  （RESERVE 区块后面跟着 `#ifdef CONFIG_RV` 而非原注释），GNU patch
  以 fuzz=2 顺利落位，效果与原补丁完全一致。详见 `patches/README.zh.md`。
- **Q: 为什么没有 0002-kernelsu-hooks 补丁？**
  KernelSU v3.3.0 架构已改为 syscall 表拦截（sys_enter tracepoint
  dispatcher + 直接 patch syscall 表），不再需要旧版 fs/exec.c、
  fs/open.c、fs/read_write.c、fs/stat.c 的手动 hook 调用点，写了反而
  会引用不存在的符号导致编译失败。证据与分析见 `patches/README.zh.md`。
- **Q: 能不能换更新的内核（比如分支 HEAD 6.6.142）？**
  不行。必须锁定 94c1a24cabd5（6.6.30）才能复现官方版本串；更高的
  sublevel 会让 vermagic 漂移，厂商模块全部失效。
- **Q: KSU 想换版本怎么办？**
  Run workflow 时改 `ksu_tag`（如 `main` 或其他 release tag）。注意
  管理器 APK 要用同版本。
- **Q: 构建要多久 / 会不会超时？**
  约 4090 分钟（4 核 runner、BTF+DWARF5+zstd）。timeout 设了
  300 分钟。
- **Q: boot.img 比分区小（约 14MB vs 32MB）能刷吗？**
  可以。工具只写 header + 内核对齐段；未用区域保持原样或补零均可。

## 15. 致谢与许可

- **AOSP kernel/common**（GPL-2.0）：内核源码基线。
- **Droidspaces / ravindu644**（GPL-3.0）：kABI 补丁与 GKI 配置文档。
- **KernelSU / tiann**（GPL-3.0）：root 方案与 setup.sh 集成脚本。
- **AnyKernel3 / osm0sis**（GPL-3.0）：刷机打包框架。
- 感谢本项目前期对设备分区与官方 config 的提取分析工作。
