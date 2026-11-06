# 魅族 20(m2381)移植 Skyward — 移植笔记

> 上游:https://github.com/kirklin/skyward(GPL-3.0,v0.1.2)
> 维护 fork:**https://github.com/un6666cn/skyward**(origin,移植提交推这里)
> 远程布局:`origin` = un6666cn/skyward(推送),`upstream` = kirklin/skyward(跟进上游)
> 参照机型:小米 13 Ultra `ishtar`(同为 SM8550,已实测)
> 本文记录阶段 0(源码通读 + 配置起草)的结论与待办。

## 1. 可行性结论

**高可行。** 五条证据见会话评估,核心三条:

1. 同 SoC 实测参照(ishtar);2. 分区布局匹配(独立 recovery 分区 100MiB、A/B、VAB+压缩、super 动态分区 erofs、init_boot);3. TWRP 设备树证实解密链路(qseecomd + KeyMint QTI AIDL + Gatekeeper 1.0 HIDL)与 ishtar 同构——TWRP 在该机无设备级 sepolicy 补丁目录的情况下让这些服务以 `u:r:recovery:s0` 跑通,Skyward 的 fork+exec 拉起方式与之同域。

## 2. 阶段 0 摸清的机制(读码结论)

| 机制 | 位置 | 结论 |
|---|---|---|
| 打包 | `crates/skyward-pack/src/main.rs` | 完全设备无关:替换 ramdisk 内 `system/bin/recovery`、注入 config+字体、patch `prop.default`(删 ro.build.version.release / ro.build.version.security_patch / ro.vendor.build.security_patch,加 ro.secure=0 / ro.adb.secure=0 / ro.debuggable=1 / ro.ota.allow_downgrade=true)、补 task_profiles.json 与 MTP rc、追加未签名 AVB footer。**不碰内核/dtb/sepolicy** |
| stock 来源 | 同上 `Stock` 子命令 | 小米专用(OTA URL + 分区局部下载)。可绕过:`recovery` 子命令直接接受本地 `--stock` 镜像(须为含 AVB footer 的整分区) |
| 服务拉起 | `crates/skyward/src/services.rs` | fork+exec,继承 recovery 的 SELinux 域,**不经过 init、无需 sepolicy 改动**;凭证(user/groups/capabilities)在 exec 前切换;按书写顺序启动,就绪信号(property / AIDL 注册名 / HIDL 注册名)阻塞后续 |
| VINTF 描述 | `crates/skyward/src/secure.rs` | 从 `/vendor/etc/vintf/manifest`、`/odm/etc/vintf/manifest` 找到描述 `ready_service`+`registers` 的 fragment,改写为 framework 类型交给 servicemanager,再让注册过的服务重启 |
| TEE 版本门禁 | `main.rs` `adopt_installed_version` | recovery 启动时把三个版本属性改成已装系统的值,安全世界才不拒绝已装系统造的密钥 |
| VAB/super | `skyward-vab`、`skyward-lp` | 纯 AOSP 逻辑(liblp/snapshot),设备无关 |

## 3. m2381 关键事实(已钉死)

- 代号 `m2381`(20 / 20 Classic);20 Pro 为 `m2391`。SM8550(kalama),Android 13 / Flyme 10,API 33 / VNDK 33
- 分区:boot header v4,pagesize 4096;AB: boot/init_boot/vendor_boot/dtbo/vbmeta/vbmeta_system/odm/product/system/system_ext/system_dlkm/vendor/vendor_dlkm;super 8GB(全 erofs);recovery 100MiB;userdata f2fs(FBE v2 wrappedkey + metadata wrappedkey);**recovery 镜像不含内核**(内核在 vendor_boot)——对打包流程透明
- 解密服务(Flyme rc 原文凭证):qseecomd `root:root,drmrpc`;keymint `root:root,drmrpc`(AIDL);gatekeeper `root:root`(HIDL @1.0)
- KeyMint VINTF fragment:`IKeyMintDevice/default` + `ISecureClock/default` + `ISharedSecret/default` + `IRemotelyProvisionedComponent/default`
- stock vendor manifest **不声明 boot control HAL、不声明 weaver** → 魅族大概率无 weaver 依赖(TWRP 亦未带 weaver 而解密正常);boot HAL 缺失见 §5 待办
- 振动马达 AW8697(艾为),非高通 qcom-haptics;TWRP 下振动/电量均不可用
- WLAN:SM8550 预期 WCN7850 + qca_cld3_kiwi_v2 + cnss2(同 ishtar);TWRP manifest 未声明 supplicant HAL,待真机核实

## 4. 已产出

- `skyward/devices/m2381.toml` — 适配骨架。已填:device/display/modules sources/qseecomd/keymint/hwservicemanager/gatekeeper/backup/wipe;TODO(真机) 标注:触摸模块、firmware=modem 确认、hwservicemanager 路径、boot control、WLAN(整段注释)、haptics、os_version_prop
- `skyward/devices/validate_m2381.py` — schema 语义校验脚本(Python 等效实现),当前通过
- 本笔记

## 5. 待办清单

### 阶段 1(真机,解锁 BL 后)—— 已于 2026-11-06 完成,结果见 §8
- [x] `dd` 导出 recovery(用户直接提供 `recovery.img`,见 §7)+ EFS 分区备份仍待做(modemst1/2、fsg、fsc、persist)
- [x] 确认属性:`ro.sf.lcd_density=450`、版本属性 `ro.build.display.id`、`ro.vndk.version=33`
- [x] 清点 vendor 服务:boot@1.2 存在、hwservicemanager 在 system_ext、supplicant fragment 在
- [x] 模块名:触摸 `goodix_ts.ko`、WLAN `qca_cld3_kiwi_v2.ko`(均 vendor_dlkm)
- [x] fstab.qcom:modem、persist 条目存在,userdata 为标准 `metadata_encryption=aes-256-xts:wrappedkey_v0`
- [x] 更新 `m2381.toml` 收窄 TODO(仅余 corner_radius 真机测量)
- [ ] `cargo test -p skyward-config`(需装 Rust)

### 环境准备(本机)—— 已于 2026-11-06 完成
- [x] Rust stable:Windows 侧 `stable-x86_64-pc-windows-gnu`(MSVC Build Tools 缺失,弃用 msvc 工具链);WSL Ubuntu 侧 rustc 1.99.1(unix 语义测试用)
- [x] `aarch64-linux-android` target(两侧)
- [x] NDK r29:`E:/android-sdk/ndk/29.0.14206865`(sdkmanager)
- [x] cargo-ndk 4.1.2(`cargo install --locked`)
- [x] 全 workspace 测试(WSL):全绿(含 data.rs wrappedkey 回退测试)
- [x] `parses_m2381` 测试已按作者 per-device 模式加入 skyward-config 并通过

**分工约定**(因 Windows host 的 unix 语义缺失):WSL 跑 `cargo test --workspace`(`CARGO_TARGET_DIR=~/skyward-target` 避开 /mnt 慢盘)与 `skyward-pack` 打包(配置解析的绝对路径校验依赖 unix 语义);Windows 侧只做 `cargo ndk -t arm64-v8a --platform 30 build --release -p skyward` 的 Android 构建并把产物喂给 WSL 的 pack。

### 阶段 2(第一版镜像)—— 已于 2026-11-06 完成
- [x] 打包:`work/skyward-m2381-v0.1.2.img`(刷机版 SHA-256 `ac6220fd341ba58a792e1a65fcc9fcad2d6d0209498825dfe19b3dd7c3f095df`)
- [x] 刷入 `recovery_a`(槽位 a)并验收:**屏幕/背光/触摸/adb root/MTP/TEE 五服务/data 解密(用户 CE 全开)全部通过**,UI 无重启循环
- [x] 首刷黑屏已修复:`normal_max()` 只认 MIUI 面板属性,魅族面板节点(`qcom,mdss_dsi_meizu_amoled_boe_cmd`)没有 → `skyward/src/ui.rs` 补丁:无正常最大属性时回退全量亮度范围(详见图层一节 §9)
- [ ] 待验收:WLAN(UI 内开关)、`adb sideload`、fastbootd、备份/恢复
- [ ] 观察项:UI 内操作时的 avc 拒绝日志(permissive 下仅记录,不影响功能)

### 阶段 3
- [ ] WLAN(MTP 已证明 UI 内外设路径正常;kiwi_v2 + cnss2 + wpa_supplicant 配置就绪)
- [ ] 解密页带锁屏口令的解锁(gatekeeper verify 路径,无口令场景已通)

### 阶段 3
- [ ] 触摸(补 `load` 与可能的 `touch`/`owners`)→ 解密(→ `data` 子命令验证)→ WLAN → haptics

## 6. 风险登记

| 风险 | 等级 | 缓解 |
|---|---|---|
| BL 解锁需第三方渠道(meizubl.com / EDL 工具) | 前提 | 已解锁则无碍;未解锁先解决 |
| Flyme recovery sepolicy 对 fork+exec 拉起服务的许可范围 | 中 | TWRP 在 recovery 域跑通 TEE 是强旁证;真机 kmsg 验证 |
| haptics:AW8697 无 FF 输入设备(仅 LED 类 aw_vibrator) | 已定论 | Skyward 力反馈机制驱动不了,不配置;TWRP 同样不可用。若日后要振动需驱动级工作 |
| supplicant fragment 位置未定 → WLAN 注册被拒 | 已解除 | `/vendor/etc/vintf/manifest/android.hardware.wifi.supplicant.xml` 存在 |
| boot HAL 缺失 → 槽位切换不可用 | 已解除 | `android.hardware.boot@1.2-service` 在 vendor 中,TWRP 设备树自建服务系误判(其 manifest.xml 是不完整旧版) |
| Flyme 版本碎片(仅 12.6.0.0A + slot a 实测) | 低 | 本机恰为 pmOS 验证基线;每个 Flyme 版本重跑阶段 1 清单 |
| Flyme fstab 无 `metadata_encryption` extra | 已解除(变防御) | 真 fstab.qcom 是标准写法,recovery.fstab 的 `ice,wrappedkey` 只是 recovery 简写;data.rs 回退补丁保留作他机健壮性 |

## 7. stock recovery.img 解包结论(Flyme 12.6.0.0A,`work/stock/`)

`work/stock/recovery.img` = 整分区含 AVB footer(104857600 字节),header v4、kernel 0 字节、ramdisk 16.7MB(lz4_legacy)、OS 13.0.0 / patch 2023-10。可直接作 `skyward-pack recovery --stock` 输入。已用 magiskboot 解包至 `work/stock/rootfs/`。

### prop.default(29KB,235 条)
- `ro.build.display.id=Flyme 12.6.0.0A` → **`os_version_prop = "ro.build.display.id"` 实证正确**,与 pmOS 验证基线同版本
- 三个待剥离属性齐全:`ro.build.version.release=13`、`ro.build.version.security_patch=2023-10-01`、`ro.vendor.build.security_patch=2023-10-01`(skyward-pack 会剥)
- `ro.secure=1 / ro.adb.secure=1 / ro.debuggable=0` → pack 的追加行覆盖方案有效;`ro.vndk.version=33`

### init.rc(system/etc/init/hw/init.rc)
服务:console、ueventd、charger、**recovery(seclabel u:r:recovery:s0)**、adbd(--root_seclabel=u:r:su:s0)、fastbootd。**没有 logd** → `[logd]` 确认不需要。另有 `servicemanager.recovery.rc`(disabled,由 Skyward 经 ctl.restart 重启加载 VINTF 描述)与 health HAL(qti_recovery,自跑)。

### recovery.fstab(★ 三个关键差异)
1. **无 modem(/vendor/firmware_mnt)与 persist 条目**——Flyme stock recovery 不挂它们,说明其 recovery 不做 data 解密。Skyward 读的是**已装系统**的 `/vendor/etc/fstab.qcom`(或 `/odm/etc/fstab.qcom`,见 `skyward-block/src/fstab.rs:8`),能否挂 modem/persist 取决于那个文件,本镜像看不到 → 待真机 `cat /vendor/etc/fstab.qcom` 确认后再启用 `[firmware]` 与 `[partitions] mounted`
2. **userdata 行:`fileencryption=ice,wrappedkey`,无 `metadata_encryption=...` extra**——`skyward-crypto/src/data.rs:56` 的 `Encryption::of` 只认显式 extra → **解密必失败,需补丁**:`metadata_encryption` 缺席且有 `wrappedkey` 标志时按 AOSP 语义回退 `aes-256-xts:wrappedkey_v0`(等价于 ishtar 的显式写法;`fileencryption=ice` 是高通内核的简写,不解成同一硬件包裹密钥路径,不影响 Skyward)
3. metadata 分区行带 `wrappedkey`(f2fs),与小米一致

### 其余
- `system/bin/recovery` 1.78MB(将被替换)、fastbootd/init/servicemanager/toybox 齐备
- `odm/` 在 ramdisk 里为空挂载点树,触摸固件与 vendor 内容不可见,仍需真机/完整包
- `init.recovery.qcom.rc` 只做背光(2784)与 USB controller 配置,不起 vendor 服务
- TWRP 设备树里的 qseecomd/keymint/gatekeeper rc 系 TWRP 作者自写(非 Flyme 自带),其凭证(root:root,drmrpc 等)与 `seclabel u:r:recovery:s0` 仍是可抄的合理起点

### 真机取数清单(解 BL + 官方 root 或临时 root shell)
```sh
adb shell su -c 'cat /vendor/etc/fstab.qcom; cat /odm/etc/fstab.qcom'   # ① modem/persist 条目与加密写法
adb shell su -c 'ls /vendor/bin/hw/'                                    # ② boot HAL / gatekeeper / keymint 实名
adb shell su -c 'ls /vendor/lib/modules/ /odm/lib/modules/ 2>/dev/null' # ③ 触摸与 WLAN 模块名
adb shell getprop ro.sf.lcd_density ro.vndk.version ro.build.version.incremental  # ④ density 与版本属性复核
adb shell su -c 'ls /sys/class/leds /sys/class/*haptics* 2>/dev/null'   # ⑤ AW8697 的 sysfs 形态
```

## 8. 真机取数结果(2026-11-06,Flyme 12.6.0.0A,slot a,KernelSU root)

设备:`MEIZU_20`(meizu20,product meizu_20_CN),BL 已解锁(`ro.meizu.bl_unlock=1`),官方支持 root(KernelSU)。

| 项 | 结果 | 对配置的影响 |
|---|---|---|
| fstab.qcom | persist(ext4→/mnt/vendor/persist)与 modem(vfat→/vendor/firmware_mnt)条目齐全;userdata 行 `metadata_encryption=aes-256-xts:wrappedkey_v0` | `[firmware] modem` 与 `[partitions] mounted=persist` 启用;data.rs 回退补丁转为防御性 |
| 运行服务 | qseecomd(root)、keymint-service-qti(system)、gatekeeper@1.0(system)、boot@1.2(root)全部在跑 | TOML 凭证照 Flyme rc:keymint/gatekeeper 用 **system**(TWRP rc 的 root 写法错误);qseecomd root 与 rc 一致 |
| boot HAL | `android.hardware.boot@1.2-service` 在 vendor,fragment `android.hardware.boot@1.2.xml` 在;TWRP 自建服务系误判 | 服务条目启用,与 ishtar 同款(`@1.2::IBootControl/default`) |
| weaver / SPU | 仅 `-spu-qti` 变体(gatekeeper/keymint/weaver),本机无 spu 属性、未运行,无 plain weaver 二进制 | 不配 weaver,与 TWRP 免 weaver 解密一致 |
| 触摸 | `goodix_ts.ko`;输入设备 `main_touch`(goodix_ts/input0);固件 `/vendor/firmware/goodix_firmware.bin` + `goodix_cfg_group.bin`;recovery ueventd 固件目录含 `/vendor/firmware/` | `load = ["goodix_ts"]`,无需 touch 写入与 owners |
| WLAN | `qca_cld3_kiwi_v2.ko` + cnss2 套件;cfg `/vendor/etc/wifi/kiwi_v2/WCNSS_qcom_cfg.ini`;supplicant fragment 在;`/vendor/firmware/wlan/qca_cld/kiwi_v2/wlan_mac.bin` → `/mnt/vendor/persist/kiwi_v2/` **悬空** | `[wlan]` 启用;mac 条目不写(阶段 3 实测后定) |
| system_dlkm | 分区内无模块(只有 etc/),rfkill 内建 | `sources` 不含 system_dlkm |
| 振动 | AW8697 仅 LED 类 `/sys/class/leds/aw_vibrator`,无 FF 输入设备 | `[haptics]` 不配置(定论) |
| 属性 | `ro.sf.lcd_density=450`、VNDK 33、slot _a | display.density=450 |
| /data 日志目录 | vendor 下 log/imslogs/pddump/qti-logkit/ramdump/ssrdump/tombstones | `[wipe] logs` 已填 |
| 其他 | `/vendor/etc/vintf/manifest/` 里 boot@1.2、supplicant、keymint fragment 齐全;hwservicemanager 在 `/system_ext/bin/`(且有 /system/bin 符号链接) | `publish_descriptions` 能找到全部三个 fragment;hwservicemanager 路径确认 |

**遗留 TODO**:corner_radius(真机测量)、WLAN MAC 来源、Flyme 联网探测地址。EFS 备份用户已明确不做。

## 9. 已打补丁(skyward fork 相对上游的全部改动)

| 文件 | 改动 | 原因 |
|---|---|---|
| `devices/m2381.toml` | 新增设备配置(含 `parses_m2381` 测试) | 移植主体 |
| `crates/skyward-config/src/lib.rs` | 新增 `parses_m2381` 测试 | 按作者 per-device 测试模式守护配置 |
| `crates/skyward-crypto/src/data.rs` | `Encryption::of`:无 `metadata_encryption` extra 且有裸 `wrappedkey` 标志时回退 `aes-256-xts:wrappedkey_v0`,附测试 | 防御性(m2381 的 fstab.qcom 实为标准写法);对其他无此 extra 的机型兜底 |
| `crates/skyward/src/ui.rs` | `normal_max()`:面板节点无 MIUI 亮度属性时回退全量范围(top = max_brightness) | **首刷黑屏根因**:MIUI 用 `mi,*` 属性预留 HBM 区间,魅族面板节点没有,原实现直接报错导致 UI 循环崩溃 |
| `crates/skyward-pack/src/main.rs` | `prop.default` 追加行增加 `sys.usb.config_disable=0` | **MTP 起不来根因**:Flyme stock recovery 无任何地方设置该属性(unset ≠ "0"),`skyward-mtp.rc` 里带此条件的 `start adbd` 规则永不触发;mtp,adb 流程经 "none" 后 adbd 停止且 `ffs.ready` 清零,adbd 无法重启则绑定规则永不满足。已在真机手动置齐条件验证规则点火 |
| `devices/m2381.toml` 的 ADSP oneshot | `[[service]]` oneshot `/vendor/bin/sh`,按固件名(`adsp.mdt`)定位 remoteproc 写 `start`;循环以 `true` 结尾 | **电池读不到根因**:魅族 DT 不自动启动任何 remoteproc,电池固件跑在 ADSP 上——`qti_battery_charger` 开机已加载但 ADSP 不起就不注册 battery psy(TWRP 同样读不到)。oneshot 首版循环以不匹配项收尾导致退出码 1、`devices not brought up` 连累 TEE 服务,已修正 |
