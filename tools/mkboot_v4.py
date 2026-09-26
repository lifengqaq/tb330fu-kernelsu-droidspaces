#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mkboot_v4.py  构造/解析 Android boot image v4（TB330FU barley 专用形态）.

目标设备的 boot 分区镜像（当前槽位实测）：
  - Android boot image header v4（header_size=1584，头固定占 4096 字节，页大小固定 4096）
  - 仅含 gzip 压缩内核，ramdisk_size=0（ramdisk 位于 init_boot / vendor_boot 分区）
  - 无 boot signature、无 AVB footer（设备引导不校验签名，无签名镜像可正常启动）
  - 官方样例：kernel_size=14276711，kernel 从偏移 4096 开始，随后按 4096 对齐补零

布局（AOSP system/tools/mkbootimg include/bootimg/bootimg.h）：
  boot_img_hdr_v4 = magic[8] kernel_size u32 ramdisk_size u32 os_version u32
                    header_size u32 reserved[4] u32 header_version u32
                    cmdline[1536] signature_size u32   （共 1584 字节，补零到 4096）
  之后：kernel（m 页，m = ceil(kernel_size/4096)），再补零到页对齐。

纯 Python 实现，无第三方依赖。用法：
  python3 mkboot_v4.py build Image.gz boot.img [--cmdline "..."] [--partition-size N]
  python3 mkboot_v4.py info  boot.img
"""
import argparse
import struct
import sys
from pathlib import Path

MAGIC = b'ANDROID!'
HDR_VERSION = 4
HDR_SIZE = 1584          # v4 头实际字节数（= v3 的 1580 + signature_size 4）
HEADER_PAGES = 4096      # v4 规定头占满 4096 字节（页大小固定 4096）
PAGE = 4096
GZIP_MAGIC = b'\x1f\x8b'


def build_boot_v4(kernel: bytes, cmdline: bytes = b'', os_version: int = 0) -> bytes:
    if len(cmdline) > 1536 - 1:
        raise ValueError('cmdline 过长（>1535 字节）')
    hdr = bytearray(HEADER_PAGES)
    hdr[0:8] = MAGIC
    struct.pack_into('<I', hdr, 8, len(kernel))    # kernel_size
    struct.pack_into('<I', hdr, 12, 0)             # ramdisk_size（barley：无 ramdisk）
    struct.pack_into('<I', hdr, 16, os_version)    # os_version（官方镜像为 0）
    struct.pack_into('<I', hdr, 20, HDR_SIZE)      # header_size = 1584
    struct.pack_into('<4I', hdr, 24, 0, 0, 0, 0)   # reserved[4] = 0
    struct.pack_into('<I', hdr, 40, HDR_VERSION)   # header_version = 4
    hdr[44:44 + len(cmdline)] = cmdline            # cmdline[512] + extra_cmdline[1024]
    # signature_size（偏移 1580）保持 0：不写 boot signature / AVB footer
    out = bytearray(hdr)
    out += kernel
    out += bytes((-len(kernel)) % PAGE)            # 内核段补零到 4096 对齐
    return bytes(out)


def parse_boot_v4(data: bytes) -> dict:
    if len(data) < HEADER_PAGES:
        raise ValueError('文件过小，不是有效的 boot image')
    if data[0:8] != MAGIC:
        raise ValueError(f'bad magic: {data[0:8]!r}')
    k_size, r_size, os_ver, h_size = struct.unpack_from('<IIII', data, 8)
    reserved = struct.unpack_from('<4I', data, 24)
    hver = struct.unpack_from('<I', data, 40)[0]
    cmdline = data[44:44 + 1536].split(b'\x00')[0]
    sig_size = struct.unpack_from('<I', data, 1580)[0]
    k_start = HEADER_PAGES
    kernel = data[k_start:k_start + k_size]
    padded_end = k_start + ((k_size + PAGE - 1) // PAGE) * PAGE
    return {
        'kernel_size': k_size, 'ramdisk_size': r_size, 'os_version': os_ver,
        'header_size': h_size, 'reserved': reserved, 'header_version': hver,
        'cmdline': cmdline.decode('ascii', errors='replace'),
        'signature_size': sig_size,
        'kernel_offset': k_start, 'kernel': kernel,
        'padded_kernel_end': padded_end,
        'file_size': len(data),
        'kernel_is_gzip': kernel[:2] == GZIP_MAGIC,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)

    b = sub.add_parser('build', help='用 gzip 内核构造 boot v4 镜像')
    b.add_argument('kernel', help='gzip 压缩的内核文件（如 out/arch/arm64/boot/Image.gz）')
    b.add_argument('out', help='输出 boot.img 路径')
    b.add_argument('--cmdline', default='', help='boot cmdline（默认空，与官方镜像一致）')
    b.add_argument('--os-version', type=lambda x: int(x, 0), default=0,
                   help='os_version 字段（默认 0，与官方镜像一致）')
    b.add_argument('--partition-size', type=lambda x: int(x, 0), default=0,
                   help='可选：把输出补零到该字节数（如 33554432 = 32MB 分区）')

    i = sub.add_parser('info', help='解析并打印 boot v4 镜像信息')
    i.add_argument('image', help='boot.img 路径')

    args = ap.parse_args()

    if args.cmd == 'build':
        kernel = Path(args.kernel).read_bytes()
        if kernel[:2] != GZIP_MAGIC:
            print(f'warning: {args.kernel} 前两字节不是 gzip magic（仍按原样打包）', file=sys.stderr)
        blob = build_boot_v4(kernel, args.cmdline.encode(), args.os_version)
        if args.partition_size:
            if args.partition_size < len(blob):
                raise ValueError(f'输出 {len(blob)} 字节超过分区大小 {args.partition_size}')
            blob += bytes(args.partition_size - len(blob))
        Path(args.out).write_bytes(blob)
        info = parse_boot_v4(blob)
        print(f'wrote {args.out} ({len(blob)} bytes)')
        print(f"  kernel_size = {info['kernel_size']}  gzip = {info['kernel_is_gzip']}")
        print(f"  header_version = {info['header_version']}  header_size = {info['header_size']}")
        print(f"  ramdisk_size = {info['ramdisk_size']}  signature_size = {info['signature_size']}")
        print(f"  kernel_offset = {info['kernel_offset']}  cmdline = {info['cmdline']!r}")
        # 自检：重解析后内核段必须与输入一致
        assert info['kernel'] == kernel, 'self-check failed: kernel roundtrip mismatch'
        print('  self-check: OK (内核段与输入逐字节一致)')
    elif args.cmd == 'info':
        data = Path(args.image).read_bytes()
        info = parse_boot_v4(data)
        for k, v in info.items():
            if k == 'kernel':
                continue
            print(f'{k:20} = {v}')
        if not info['kernel_is_gzip']:
            print('note: kernel 段前两字节不是 gzip magic')
        tail = data[info['padded_kernel_end']:]
        if tail.strip(b'\x00'):
            print(f"note: 内核对齐区之后还有 {len(tail)} 字节非零数据"
                  f"（官方镜像为 AVB vbmeta/footer，本工具构建的镜像不含）")


if __name__ == '__main__':
    main()
