# patches/ 说明

## 目录

```
patches/
 0001-droidspaces-gki-sysvipc-kabi.patch          # 构建时自动应用
 alternatives/
     0001-...-refreshed-android15-6.6.30.patch    # 备选（默认不应用）
```

workflow 只应用 `patches/*.patch`（顶层 glob，不含 `alternatives/`）。

## 0001-droidspaces-gki-sysvipc-kabi.patch（必打）

### 它做什么

来自 Droidspaces-OSS
`Documentation/resources/kernel-patches/GKI/below-6.12/001.GKI-below-6.12-fix_sysvipc_kabi_6_7_8.patch`，
**原样复制，未做任何修改**。它对 `include/linux/sched.h` 的
`struct task_struct` 做两处改动：

1. 把 `#ifdef CONFIG_SYSVIPC` 块里的 `sysvsem` / `sysvshm` 两个字段
   注释掉（开启 SYSVIPC 时它们不再追加到结构体原有位置）；
2. 在 ANDROID_KABI_RESERVE(3)~(8) 区块内插入：

```c
#ifdef CONFIG_SYSVIPC
        ANDROID_KABI_USE(6, struct sysv_sem sysvsem);
        _ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(7); ANDROID_KABI_RESERVE(8), struct sysv_shm sysvshm);
#else
        ANDROID_KABI_RESERVE(6);
        ANDROID_KABI_RESERVE(7);
        ANDROID_KABI_RESERVE(8);
#endif
```

### 为什么必须打（kABI / MODVERSIONS 原理）

- GKI 在结构体尾部预留了 kABI 填充槽（`u64` 数组）。直接开启
  `CONFIG_SYSVIPC` 会把 `sysvsem`/`sysvshm` 插到结构体原有位置，
  使后续所有字段**位移**厂商模块按旧偏移访问  崩溃/bootloop；
- 本补丁把这两个字段搬进预留槽 6/7/8：结构体**总大小和字段偏移**
  与原厂完全一致；
- 关键的第二层保险：`include/linux/android_kabi.h` 中
  `_ANDROID_KABI_REPLACE` 在 **`__GENKSYMS__`**（genksyms 计算
  `CONFIG_MODVERSIONS` 符号 CRC 时）模式下展开为原始的
  `_orig`（纯 reserve 声明）。也就是说：
  **genksyms 看到的 task_struct 与官方原厂完全相同  厂商模块的
  CRC 校验照常通过**。这正是 Android kABI 宏体系的设计目的。

### 在 android15-6.6 / 6.6.30 (94c1a24cabd5) 上的适配性验证

用从 94c1a24cabd5 提取的 `include/linux/sched.h` 逐 hunk 模拟
`git apply` 的上下文匹配，结论：

| Hunk | 结果 |
|---|---|
| @@ -1074,8（sysvsem/sysvshm 注释块） | 上下文**完全匹配**（实际位于 1072 行，偏移 -2，git apply 可接受） |
| @@ -1513,9（RESERVE(3..8) 区块） | 核心上下文（6 行 RESERVE）**完全匹配**（实际 1521 行）；仅**尾部 3 行**上下文过期：6.6.30 树上 RESERVE(8) 之后是空行 + `#ifdef CONFIG_RV`，而补丁写的是空行 + `/* New fields for task_struct ...` 注释 |

也就是说：`git apply` 会因 hunk 2 的尾部上下文整包拒绝，但
**GNU patch --fuzz=2 可以干净落位**（丢弃 2 行过期尾上下文，内核
RESERVE 六行精确匹配，其余插入照常完成）。补丁要求的
`ANDROID_KABI_RESERVE / ANDROID_KABI_USE / _ANDROID_KABI_REPLACE`
宏在 android15-6.6 的 `include/linux/android_kabi.h` 中**全部存在**，
且 `CONFIG_ANDROID_KABI_RESERVE` 默认（及本机官方 config）均为 y。

### workflow 的应用策略（自动）

```bash
for p in patches/*.patch; do
  if git -C kernel apply --check "$p"; then
    git -C kernel apply "$p"          # 优先：上下文完全匹配
  else
    patch -d kernel -p1 --fuzz=2 --no-backup-if-mismatch < "$p"   # 回退：fuzz
  fi
done
```

出现黄色 warning（"git apply 失败改用 GNU patch"）属预期；
出现 `.rej` 文件则直接 fail。

### alternatives/（备选，默认不应用）

`alternatives/0001-droidspaces-gki-sysvipc-kabi-refreshed-android15-6.6.30.patch`
是**同一改动**针对 94c1a24cabd5 重新生成的版本：hunk 2 的尾部上下文
已按 6.6.30 实际内容（空行 + `#ifdef CONFIG_RV`）刷新，`git apply`
可零 fuzz 通过。

仅当某天 GNU patch 回退也失败（例如基线换成了别的 commit、RESERVE
区块被上游改动）时，手工使用：

```bash
cd kernel
git apply ../patches/alternatives/0001-droidspaces-gki-sysvipc-kabi-refreshed-android15-6.6.30.patch
```

### 手工打补丁失败的 .rej 处理

若在本地手工 `patch -p1` 出现 `.rej`：

1. 打开 `include/linux/sched.h.rej`，确认失败的是哪个 hunk；
2. hunk 1（sysvsem/sysvshm 注释）：直接按 rej 内容手工注释那两行；
3. hunk 2：定位 `ANDROID_KABI_RESERVE(5);`，把 rej 中的
   `#ifdef CONFIG_SYSVIPC ... #endif` 块插到 RESERVE(5) 与
   RESERVE(6) 之间（`#endif` 放在 RESERVE(8) 之后）；
4. 用 `grep -n "ANDROID_KABI_USE(6" include/linux/sched.h` 确认插入成功。

## 为什么没有 0002-kernelsu-hooks-6.6.patch

早期方案计划手写 KernelSU 的 fs/exec.c、fs/open.c、fs/read_write.c、
fs/stat.c 手动 hook 补丁。**实际抓取 tiann/KernelSU v3.3.0
（官方最新 release）源码核实后确认：该方案已不适用**，v3.3.0 根本
没有可供 fs/*.c 调用的旧式 `ksu_handle_execveat(int *dirfd, ...)`
接口。证据：

- `kernel/feature/sucompat.h` 中现存的处理器签名全部是
  pt_regs 型（如 `long ksu_handle_execveat_sucompat(const char
  __user **filename_user, int orig_nr, struct pt_regs *regs)`），
  由 `hook/syscall_hook_manager.c` 统一注册，**不是**给 fs/*.c
  调用的；
- `hook/syscall_hook_manager.c` 的 `ksu_syscall_hook_manager_init()`
  通过 `register_trace_prio_sys_enter()` 挂 sys_enter tracepoint，
  把受管进程的 `execve/execveat/faccessat/newfstatat/setresuid`
  重定向到自装的 dispatcher；
- `hook/arm64/syscall_hook.c` 用 kallsyms 解析 `sys_call_table` 与
  `__arm64_sys_ni_syscall`，直接把 dispatcher 挂进一个空闲的
  ni_syscall 槽位（fixmap + stop_machine 改写）；
- supercall 接口经 `runtime/ksud_integration.c` / `supercall/supercall.c`
  的 **kprobe** 挂钩安装（Kconfig 依赖 `KPROBES && EXT4_FS`）。

因此 v3.3.0 的集成只需要：官方 `setup.sh`（或等效 clone+symlink+
Makefile/Kconfig 挂载）+ 正确的内核配置，**无需任何内核源码补丁**。
给 6.6.30 强行写 fs hook 调用反而会引用不存在的符号，直接编译失败。

KernelSU v3.3.0 对内核配置的真实要求（已核对官方 config）：

| 符号 | 要求 | 官方 config |
|---|---|---|
| CONFIG_KPROBES | y | y  |
| CONFIG_KRETPROBES | y | y  |
| CONFIG_KALLSYMS / KALLSYMS_ALL | y | y  |
| CONFIG_EXT4_FS | y（Kconfig 依赖） | y  |
| **CONFIG_FTRACE_SYSCALLS** | **y（trace_syscalls.o 定义 sys_enter tracepoint，缺了链接失败）** | **not set   由 kernelsu.fragment 补开** |
| CONFIG_TRACEPOINTS / FTRACE | y | y  |
| CONFIG_HAVE_SYSCALL_TRACEPOINTS | y（arm64 恒 y） | y  |

以上已全部写入 `config/kernelsu.fragment`，并在 workflow 的
"Verify required kernel config options" 步骤强制校验。
