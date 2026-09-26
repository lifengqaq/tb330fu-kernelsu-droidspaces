#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kleaf integration for TB330FU: KernelSU + defconfig options.

Replicates the proven June-2026 WSL flow (yizhi/scripts/patch-wsl-kernel-common.py):
- symlink common/drivers/kernelsu -> ../KernelSU/kernel
- drivers/Makefile += obj-$(CONFIG_KSU) += kernelsu/
- drivers/Kconfig += source "drivers/kernelsu/Kconfig"
- gki_defconfig: enable the Droidspaces core + KSU option set (line flip/append)

Usage: kleaf_integrate.py --common /path/to/common --defconfig /path/to/barley_defconfig
"""
import argparse
from pathlib import Path

ENABLE = [
    "CONFIG_KSU",
    "CONFIG_SYSVIPC",
    "CONFIG_POSIX_MQUEUE",
    "CONFIG_IPC_NS",
    "CONFIG_PID_NS",
    "CONFIG_DEVTMPFS",
    "CONFIG_NETFILTER_XT_MATCH_ADDRTYPE",
    "CONFIG_NETFILTER_XT_TARGET_LOG",
    "CONFIG_NETFILTER_XT_MATCH_RECENT",
    "CONFIG_IP_SET",
    "CONFIG_IP_SET_HASH_IP",
    "CONFIG_IP_SET_HASH_NET",
    "CONFIG_NETFILTER_XT_SET",
    "CONFIG_TMPFS_POSIX_ACL",
    "CONFIG_TMPFS_XATTR",
    # KernelSU v3.3.x syscall tracepoint dispatcher hard requirement;
    # v3.2.5 does not need it but having it on is harmless.
    "CONFIG_FTRACE_SYSCALLS",
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--common", required=True)
    ap.add_argument("--defconfig", required=True)
    args = ap.parse_args()
    root = Path(args.common)

    # KernelSU wiring (KernelSU repo cloned at common/KernelSU beforehand)
    ksu_link = root / "drivers" / "kernelsu"
    if ksu_link.is_symlink():
        ksu_link.unlink()
    if not ksu_link.exists():
        ksu_link.symlink_to("../KernelSU/kernel")
    assert (root / "KernelSU" / "kernel" / "Kconfig").exists(), "KernelSU/kernel missing"

    makefile = root / "drivers" / "Makefile"
    text = makefile.read_text()
    line = "obj-$(CONFIG_KSU) += kernelsu/"
    if line not in text:
        makefile.write_text(text.rstrip() + "\n\n" + line + "\n")

    kconfig = root / "drivers" / "Kconfig"
    text = kconfig.read_text()
    source = 'source "drivers/kernelsu/Kconfig"'
    if source not in text:
        kconfig.write_text(text.replace("endmenu", source + "\n\nendmenu"))

    # base defconfig = our barley_defconfig (stock device config)
    dest = root / "arch" / "arm64" / "configs" / "gki_defconfig"
    dest.write_text(Path(args.defconfig).read_text())

    # option flip/append (their proven approach; kconfig drops unknown symbols)
    lines = dest.read_text().splitlines()
    for opt in ENABLE:
        enabled = f"{opt}=y"
        disabled = f"# {opt} is not set"
        for i, lt in enumerate(lines):
            if lt == enabled:
                break
            if lt == disabled or lt.startswith(opt + "="):
                lines[i] = enabled
                break
        else:
            lines.append(enabled)
    dest.write_text("\n".join(lines) + "\n")
    print("integrated; gki_defconfig options:")
    for opt in ENABLE:
        print(" ", opt, "OK")

if __name__ == "__main__":
    main()
