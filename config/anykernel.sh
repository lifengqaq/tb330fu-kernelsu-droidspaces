### AnyKernel3 Ramdisk Mod Script
## osm0sis @ xda-developers
## TB330FU (barley) kernel-only packaging  maintained by kbuild repo

### AnyKernel setup
# global properties
properties() { '
kernel.string=TB330FU 6.6.30 (Droidspaces+KernelSU)
do.devicecheck=0
do.modules=0
do.systemless=1
do.cleanup=1
do.cleanuponabort=0
device.name1=barley
device.name2=TB330FU
device.name3=tb8786p1_64_k66
device.name4=
device.name5=
supported.versions=
supported.patchlevels=
supported.vendorpatchlevels=
'; } # end properties


### AnyKernel install
## boot shell variables
BLOCK=auto;
IS_SLOT_DEVICE=1;
RAMDISK_COMPRESSION=auto;
PATCH_VBMETA_FLAG=auto;

# import functions/variables and setup patching - see for reference (DO NOT REMOVE)
. tools/ak3-core.sh;

# boot install
# TB330FU 的 boot.img 为 Android boot v4：仅含 gzip 内核、无 ramdisk
# （ramdisk 在 init_boot/vendor_boot 分区），因此走标准内核替换流程。
# 新内核以 Image.gz 之名放在 zip 根目录，ak3-core.sh 会自动识别。
dump_boot;
write_boot;
## end boot install
