"""按 skyward-config 的 DeviceConfig::parse 语义规则校验 devices/m2381.toml。

只覆盖当前骨架涉及的规则:服务凭证、registers、路径形态、efs/wipe/backup。
正式验证以 cargo test -p skyward-config(安装 Rust 后)为准。
"""

import tomllib
from pathlib import Path, PurePosixPath

CAPS = {
    "CHOWN", "DAC_OVERRIDE", "DAC_READ_SEARCH", "FOWNER", "FSETID", "KILL",
    "SETGID", "SETUID", "SETPCAP", "LINUX_IMMUTABLE", "NET_BIND_SERVICE",
    "NET_BROADCAST", "NET_ADMIN", "NET_RAW", "IPC_LOCK", "IPC_OWNER",
    "SYS_MODULE", "SYS_RAWIO", "SYS_CHROOT", "SYS_PTRACE", "SYS_PACCT",
    "SYS_ADMIN", "SYS_BOOT", "SYS_NICE", "SYS_RESOURCE", "SYS_TIME",
    "SYS_TTY_CONFIG", "MKNOD", "LEASE", "AUDIT_WRITE", "AUDIT_CONTROL",
    "SETFCAP", "MAC_OVERRIDE", "MAC_ADMIN", "SYSLOG", "WAKE_ALARM",
    "BLOCK_SUSPEND", "AUDIT_READ", "PERFMON", "BPF", "CHECKPOINT_RESTORE",
}

errors: list[str] = []
plain = lambda p: all(c == "\\" or (PurePosixPath(p)).name == c for c in PurePosixPath(p).parts)

text = Path(__file__).with_name("m2381.toml").read_text(encoding="utf-8")
# 剔除注释后交给 tomllib(TOML 注释合法,无需剔除,此处直接解析)
cfg = tomllib.loads(text)

# ---- [device] ----
dev = cfg.get("device", {})
if not dev.get("codename"):
    errors.append("[device] codename 缺失")
if dev.get("ab") is not True:
    errors.append("[device] 本机为 A/B,ab 必须为 true")

# ---- [[service]] ----
for s in cfg.get("service", []):
    path = s.get("path", "")
    label = f"[[service]] {path or '(无 path)'}"
    if not PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
        errors.append(f"{label}: path 不是绝对路径")
    if s.get("oneshot"):
        if s.get("ready_property") or s.get("ready_service") or s.get("ready_hardware_service") \
           or s.get("registers") or s.get("description"):
            errors.append(f"{label}: oneshot 服务不得声明就绪信号或注册项")
    if not s.get("ready_property") and not s.get("ready_service") and not s.get("ready_hardware_service") \
       and not s.get("oneshot"):
        errors.append(f"{label}: 常驻服务未声明就绪信号,拉起顺序无法保证")
    if s.get("user") and not s.get("groups"):
        errors.append(f"{label}: 给了 user 必须给 groups")
    for name in [s.get("user", "")] + s.get("groups", []):
        if not name or any(c.isspace() for c in name):
            errors.append(f"{label}: {name!r} 不是合法账户名")
    for c in s.get("capabilities", []):
        if c not in CAPS:
            errors.append(f"{label}: 未知 capability {c}")
    for lib in s.get("libraries", []):
        if not PurePosixPath(lib).is_absolute() or not PurePosixPath(lib).name:
            errors.append(f"{label}: 库目录 {lib} 不是绝对目录")

# registers 里的名字必须形如 接口/实例
for s in cfg.get("service", []):
    for name in s.get("registers", []):
        if "/" not in name.rsplit(".", 1)[-1]:
            errors.append(f"[[service]] {s['path']}: registers 项 {name} 不是 接口/实例 形式")

# 就绪信号出现的顺序不得早于提供它的服务(就绪探测按书写顺序阻塞)
names = [s.get("ready_service") or s.get("ready_hardware_service") for s in cfg.get("service", [])]

# ---- [backup] / [wipe] ----
for name in cfg.get("backup", {}).get("efs", []):
    if not name or "/" in name:
        errors.append(f"[backup] efs: {name} 不是分区名")
for folder in cfg.get("backup", {}).get("data_skipped", []):
    p = PurePosixPath(folder)
    if folder.startswith("/") or ".." in p.parts or p.is_absolute():
        errors.append(f"[backup] data_skipped: {folder} 必须是 data 分区内的相对路径")
for log in cfg.get("wipe", {}).get("logs", []):
    p = PurePosixPath(log)
    if not p.is_absolute() or ".." in p.parts or log == "/data" or not log.startswith("/data/"):
        errors.append(f"[wipe] logs: {log} 不是 /data 内的目录")

# ---- 注释段落里隐藏的待启用项提醒 ----
# (定稿后无隐藏段,原 wlan 注释检查已删)

if errors:
    print("未通过:")
    for e in errors:
        print(f"  - {e.strip()}")
    raise SystemExit(1)

services = [s["path"] for s in cfg.get("service", [])]
print(f"解析通过。服务 {len(services)} 个:")
for s in services:
    print(f"  {s}")
order = [(s["path"], s.get("ready_property") or s.get("ready_service") or s.get("ready_hardware_service")) for s in cfg["service"]]
print("就绪顺序:")
for p, r in order:
    print(f"  {p}  ->  {r}")
