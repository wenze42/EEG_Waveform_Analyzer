#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手机文件夹清理与分类工具（Windows / macOS 通用，只用 Python 标准库）

用途：
  1. 通过 adb 直接从手机导出文件（推荐，比 Windows 的 MTP 稳定）；
  2. 扫描一份已导出的副本，按中文分类输出报告；
  3. 可选把文件按分类复制（或移动）到「整理结果」目录；
  4. 可选把无用文件移到「待删除」目录，由你自己确认后再清空。

两种用法：
  A. 手机开启「USB 调试」并连上电脑，让脚本直接读手机（不用手动复制）：
       python phone_cleaner.py --adb
  B. 手机文件夹已经在电脑硬盘上（例如 D:\\phone），直接扫描：
       python phone_cleaner.py --src "D:\\phone"

常用命令：
  python phone_cleaner.py --adb                                   # 导出手机常用目录并扫描
  python phone_cleaner.py --adb --adb目录 "DCIM,Download"         # 只导出指定目录
  python phone_cleaner.py --adb --apply --skip-junk               # 导出 + 按分类归档
  python phone_cleaner.py --src "手机导出" --delete --yes          # 清理无用文件到「待删除」
  python phone_cleaner.py --src "D:\\phone" --apply --move        # 扫描 + 移动归档
"""

import argparse
import csv
import hashlib
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

# ---------------------------------------------------------------- 分类规则

CATEGORIES = [
    ("01_照片", {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif",
                 ".dng", ".raw", ".arw", ".cr2", ".nef", ".tif", ".tiff", ".svg"}),
    ("02_视频", {".mp4", ".mov", ".avi", ".mkv", ".flv", ".3gp", ".3g2", ".ts",
                 ".m4v", ".webm", ".wmv", ".mpg", ".mpeg", ".rmvb", ".rm"}),
    ("03_音频", {".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".opus", ".amr",
                 ".wma", ".ape", ".mid", ".midi"}),
    ("04_文档", {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt",
                 ".md", ".csv", ".epub", ".rtf", ".odt", ".ods", ".odp"}),
    ("05_安装包", {".apk", ".apks", ".xapk", ".apkm"}),
    ("06_压缩包", {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}),
]

EXT_TO_CATEGORY = {}
for _cat, _exts in CATEGORIES:
    for _e in _exts:
        EXT_TO_CATEGORY[_e] = _cat
CAT_其他 = "08_其他"

# 聊天/社交软件产生的文件，单独一栏，方便你判断是否保留
CHAT_DIRS = {
    "tencent", "micromsg", "weixin", "wechat", "qq", "qzone", "qqpimsecure",
    "com.tencent.mm", "com.tencent.mobileqq", "telegram", "whatsapp",
    "dingtalk", "feishu", "lark", "wecom",
}

# 手机根目录下的系统/应用目录：不扫描、不建议动
SYSTEM_ROOT_DIRS = {
    "android", ".vivo", "vivo", "lost.dir", "$recycle.bin",
    "system volume information", ".trashes", ".trash", "bugtrap", "mtklog",
}

# 缓存/临时/缩略图目录：里面的文件列为可删候选（不会自动删）
JUNK_DIR_NAMES = {
    "cache", "cache2", ".cache", "temp", "tmp", ".tmp",
    ".thumbnails", "thumbnails", "log", "logs", "crash", "crashlog",
}

# 可删候选的后缀（系统产生的临时/日志/备份文件）
JUNK_EXTS = {".log", ".tmp", ".temp", ".bak", ".dmp", ".crdownload", ".part"}

OTHER_CATS = {"01_照片", "02_视频"}  # 这两类按年份分子目录


# ---------------------------------------------------------------- 小工具

def 人类可读(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    v = float(n)
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    return f"{v:.0f}B" if i == 0 else f"{v:.1f}{units[i]}"


def 修改时间(ts):
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return "未知"


def 年份(ts):
    try:
        y = datetime.fromtimestamp(ts).year
    except (OSError, OverflowError, ValueError):
        return "未知年份"
    return str(y) if 1990 <= y <= 2100 else "未知年份"


def 快速指纹(path, size):
    """按 文件大小 + 首尾各 128KB 生成指纹，用于找重复文件（够快，误判极低）。"""
    h = hashlib.md5()
    h.update(str(size).encode())
    try:
        with open(path, "rb") as f:
            h.update(f.read(131072))
            if size > 262144:
                f.seek(size - 131072)
                h.update(f.read(131072))
    except OSError:
        return None
    return h.hexdigest()


def 安全名字(name):
    bad = '<>:"/\\|?*'
    cleaned = "".join("_" if c in bad else c for c in name).strip(" .")
    return cleaned or "未命名"


# ---------------------------------------------------------------- 扫描

class 扫描结果:
    def __init__(self):
        self.files = []          # 每个元素：dict
        self.system_dirs = []    # 系统目录（未扫描）
        self.empty_dirs = []     # 空文件夹
        self.junk = []           # 可删候选：dict
        self.dups = []           # 重复文件组
        self.errors = []         # 权限等错误


def 扫描(src, include_apk=False):
    res = 扫描结果()
    file_count = defaultdict(int)     # 目录 -> 直属文件数
    children = defaultdict(list)      # 目录 -> 子目录

    for root, dirnames, filenames in os.walk(src, onerror=lambda e: res.errors.append(str(e))):
        rel_root = os.path.relpath(root, src)
        parts = [] if rel_root == "." else rel_root.split(os.sep)

        # 根目录下的系统目录：记录后跳过，不深入
        if len(parts) == 1 and parts[0].lower() in SYSTEM_ROOT_DIRS:
            dirnames[:] = []
            res.system_dirs.append((rel_root, 0, 0))
            continue

        if rel_root != ".":
            children[os.path.dirname(root)].append(root)

        for fn in filenames:
            full = os.path.join(root, fn)
            try:
                st = os.stat(full)
            except OSError as e:
                res.errors.append(f"{full}: {e}")
                continue

            rel = os.path.join(rel_root, fn) if rel_root != "." else fn
            ext = os.path.splitext(fn)[1].lower()
            lower_parts = [p.lower() for p in parts]

            if any(p in CHAT_DIRS for p in lower_parts):
                cat = "07_聊天与社交"
            else:
                cat = EXT_TO_CATEGORY.get(ext, CAT_其他)

            条目 = {
                "分类": cat,
                "相对路径": rel,
                "绝对路径": full,
                "文件名": fn,
                "后缀": ext,
                "大小": st.st_size,
                "修改时间": 修改时间(st.st_mtime),
                "时间戳": st.st_mtime,
                "目录部分": lower_parts,
            }
            res.files.append(条目)
            file_count[os.path.dirname(full)] += 1

    # 空文件夹：从深到浅累计文件数
    所有目录 = set(file_count) | set(children)
    for _v in children.values():
        所有目录.update(_v)
    total = {d: file_count.get(d, 0) for d in 所有目录}
    for d in sorted(children.keys(), key=lambda p: p.count(os.sep), reverse=True):
        s = total.get(d, 0)
        for c in children.get(d, []):
            s += total.get(c, 0)
        total[d] = s
    for d, n in total.items():
        if n == 0 and d != src:
            res.empty_dirs.append(d)

    # 可删候选
    for f in res.files:
        if 任何(f["目录部分"], JUNK_DIR_NAMES):
            原因 = "缓存/临时/缩略图目录"
        elif f["大小"] == 0:
            原因 = "空文件（0 字节）"
        elif f["后缀"] in JUNK_EXTS:
            原因 = "临时文件/日志/备份"
        elif f["后缀"] in {".apk", ".apks", ".xapk", ".apkm"} and include_apk:
            原因 = "已安装的安装包（按需清理）"
        else:
            continue
        d = dict(f)
        d["原因"] = 原因
        res.junk.append(d)

    # 重复文件：先按大小分组，再按指纹分组
    by_size = defaultdict(list)
    for f in res.files:
        if f["大小"] >= 1024 * 1024 and f["分类"] != "05_安装包":
            by_size[f["大小"]].append(f)
    for size, group in by_size.items():
        if len(group) < 2:
            continue
        by_hash = defaultdict(list)
        for f in group:
            h = 快速指纹(f["绝对路径"], size)
            if h:
                by_hash[h].append(f)
        for h, same in by_hash.items():
            if len(same) > 1:
                same.sort(key=lambda x: (x["相对路径"].count(os.sep), len(x["相对路径"]), x["修改时间"], x["相对路径"]))
                res.dups.append(same)

    return res


def 任何(seq, targets):
    return any(x in targets for x in seq)


# ---------------------------------------------------------------- 报告

def 写报告(res, src, 报告目录):
    os.makedirs(报告目录, exist_ok=True)
    总大小 = sum(f["大小"] for f in res.files)
    分类统计 = defaultdict(lambda: [0, 0])
    for f in res.files:
        分类统计[f["分类"]][0] += 1
        分类统计[f["分类"]][1] += f["大小"]

    去重可省 = sum(g[0]["大小"] * (len(g) - 1) for g in res.dups)
    垃圾大小 = sum(j["大小"] for j in res.junk)
    空目录 = len(res.empty_dirs)

    lines = []
    lines.append("# 手机文件夹扫描报告\n")
    lines.append(f"- 扫描目录：`{src}`")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 文件总数：{len(res.files)}")
    lines.append(f"- 总大小：{人类可读(总大小)}")
    lines.append(f"- 可删候选：{len(res.junk)} 个，约 {人类可读(垃圾大小)}")
    lines.append(f"- 重复文件：{len(res.dups)} 组，可省约 {人类可读(去重可省)}")
    lines.append(f"- 空文件夹：{空目录} 个")
    if res.system_dirs:
        lines.append(f"- 系统/应用目录（未扫描、不建议动）：{len(res.system_dirs)} 个")
        lines.append("- 说明：上述系统目录未计入上方文件数与大小。")
    lines.append("")

    lines.append("## 一、按分类统计\n")
    lines.append("| 分类 | 文件数 | 大小 |")
    lines.append("| --- | ---: | ---: |")
    for cat, (n, s) in sorted(分类统计.items()):
        lines.append(f"| {cat} | {n} | {人类可读(s)} |")
    lines.append("")

    if res.system_dirs:
        lines.append("## 二、系统与应用目录（不建议动）\n")
        for d, _, _ in sorted(res.system_dirs):
            lines.append(f"- `{d}`")
        lines.append("")

    lines.append("## 三、可删除候选\n")
    if res.junk:
        按原因 = defaultdict(lambda: [0, 0])
        for j in res.junk:
            按原因[j["原因"]][0] += 1
            按原因[j["原因"]][1] += j["大小"]
        lines.append("| 原因 | 数量 | 大小 |")
        lines.append("| --- | ---: | ---: |")
        for r, (n, s) in sorted(按原因.items(), key=lambda x: -x[1][1]):
            lines.append(f"| {r} | {n} | {人类可读(s)} |")
        lines.append("")
        lines.append("最大的 20 个：\n")
        lines.append("| 大小 | 文件 |")
        lines.append("| ---: | --- |")
        for j in sorted(res.junk, key=lambda x: -x["大小"])[:20]:
            lines.append(f"| {人类可读(j['大小'])} | `{j['相对路径']}` |")
    else:
        lines.append("没有发现可删候选。")
    lines.append("")

    if res.empty_dirs:
        lines.append("## 四、空文件夹\n")
        for d in sorted(res.empty_dirs, key=lambda p: len(p))[:100]:
            lines.append(f"- `{os.path.relpath(d, src)}`")
        if len(res.empty_dirs) > 100:
            lines.append(f"- …… 另有 {len(res.empty_dirs) - 100} 个")
        lines.append("")

    if res.dups:
        lines.append("## 五、重复文件（每组保留第一个，其余可删）\n")
        for i, group in enumerate(sorted(res.dups, key=lambda g: -g[0]["大小"])[:30], 1):
            lines.append(f"**第 {i} 组** · {人类可读(group[0]['大小'])} × {len(group)}")
            for idx, f in enumerate(group):
                mark = "保留" if idx == 0 else "可删"
                lines.append(f"- [{mark}] `{f['相对路径']}`")
            lines.append("")
        if len(res.dups) > 30:
            lines.append(f"（仅显示最大的 30 组，共 {len(res.dups)} 组）\n")

    lines.append("## 六、最大的 20 个文件\n")
    lines.append("| 大小 | 文件 | 分类 |")
    lines.append("| ---: | --- | --- |")
    for f in sorted(res.files, key=lambda x: -x["大小"])[:20]:
        lines.append(f"| {人类可读(f['大小'])} | `{f['相对路径']}` | {f['分类']} |")
    lines.append("")

    if res.errors:
        lines.append("## 七、读取失败的项目\n")
        for e in res.errors[:50]:
            lines.append(f"- {e}")
        lines.append("")

    报告路径 = os.path.join(报告目录, "扫描报告.md")
    with open(报告路径, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # 文件清单
    清单路径 = os.path.join(报告目录, "文件清单.csv")
    with open(清单路径, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["分类", "相对路径", "大小(字节)", "大小", "修改时间"])
        for x in sorted(res.files, key=lambda y: (y["分类"], y["相对路径"])):
            w.writerow([x["分类"], x["相对路径"], x["大小"], 人类可读(x["大小"]), x["修改时间"]])

    # 可删除清单
    可删路径 = os.path.join(报告目录, "可删除清单.csv")
    with open(可删路径, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["序号", "原因", "相对路径", "大小(字节)", "大小"])
        i = 0
        for x in sorted(res.junk, key=lambda y: -y["大小"]):
            i += 1
            w.writerow([i, x["原因"], x["相对路径"], x["大小"], 人类可读(x["大小"])])
        for group in res.dups:
            for x in group[1:]:
                i += 1
                w.writerow([i, "重复文件（同组保留一份）", x["相对路径"], x["大小"], 人类可读(x["大小"])])

    return 报告路径, 清单路径, 可删路径, 总大小


# ---------------------------------------------------------------- 执行整理

def 执行整理(res, src, out, 模式, 跳过=None):
    跳过 = 跳过 or set()
    os.makedirs(out, exist_ok=True)
    日志 = []
    已用 = set()
    操作 = "移动" if 模式 == "move" else "复制"
    for f in res.files:
        if f["绝对路径"] in 跳过:
            continue
        cat = f["分类"]
        目标目录 = os.path.join(out, cat)
        if cat in OTHER_CATS:
            目标目录 = os.path.join(目标目录, 年份(f["时间戳"]))
        os.makedirs(目标目录, exist_ok=True)

        名字 = 安全名字(f["文件名"])
        目标 = os.path.join(目标目录, 名字)
        基名, 后缀 = os.path.splitext(名字)
        n = 1
        while 目标.lower() in 已用 or os.path.exists(目标):
            目标 = os.path.join(目标目录, f"{基名}_{n}{后缀}")
            n += 1
        已用.add(目标.lower())

        try:
            if 模式 == "move":
                shutil.move(f["绝对路径"], 目标)
            else:
                shutil.copy2(f["绝对路径"], 目标)
            结果 = "成功"
        except (OSError, shutil.Error) as e:
            结果 = f"失败：{e}"
            目标 = ""
        日志.append([操作, f["相对路径"], 目标, 人类可读(f["大小"]), 结果])

    return 日志


def 移到待删除(res, src, 待删目录):
    """把可删候选和多余重复文件移动到「待删除」目录，保留相对结构，便于你复核后手工清空。"""
    日志 = []
    待处理 = list(res.junk)
    for group in res.dups:
        待处理.extend(group[1:])

    已做 = set()
    for x in 待处理:
        key = x["绝对路径"]
        if key in 已做:
            continue
        已做.add(key)
        目标 = os.path.join(待删目录, x["相对路径"])
        try:
            os.makedirs(os.path.dirname(目标), exist_ok=True)
            shutil.move(key, 目标)
            日志.append(["移入待删除", x["相对路径"], 目标, 人类可读(x["大小"]), "成功"])
        except (OSError, shutil.Error) as e:
            日志.append(["移入待删除", x["相对路径"], "", 人类可读(x["大小"]), f"失败：{e}"])

    for d in res.empty_dirs:
        try:
            os.rmdir(d)
            日志.append(["删除空文件夹", os.path.relpath(d, src), "", "-", "成功"])
        except OSError as e:
            日志.append(["删除空文件夹", os.path.relpath(d, src), "", "-", f"失败：{e}"])

    return 日志


def 写日志(日志, 报告目录):
    path = os.path.join(报告目录, "操作日志.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["操作", "源", "目标", "大小", "结果"])
        w.writerows(日志)
    return path


# ---------------------------------------------------------------- adb 导出

# 手机内部存储里默认要导出的目录（存在哪个就导哪个）
默认导出目录 = [
    "DCIM", "Pictures", "Download", "Documents", "Movies", "Music",
    "Recordings", "录音", "Ringtones", "tencent",
]

adb_安装提示 = """
[错误] 没有找到 adb 命令。

adb 是 Android 官方调试工具，比 Windows 自带的 MTP 传输稳定得多。
安装方法（Windows）：
  1. 下载 platform-tools：
     https://dl.google.com/android/repository/platform-tools-latest-windows.zip
  2. 解压到任意目录，例如 D:\\platform-tools
  3. 把这行加到系统环境变量 Path，或直接在本脚本同目录下放一个 platform-tools 文件夹
  4. 重新打开 PowerShell，运行 adb version 确认可用

手机端设置（vivo X200S）：
  1. 设置 → 更多设置 → 关于手机 → 连续点「软件版本号」7 次，开启开发者选项
  2. 设置 → 更多设置 → 开发者选项 → 打开「USB 调试」
  3. 数据线连电脑，手机弹窗选「允许 USB 调试」（可勾选「一律允许」）
  4. 手机下拉通知栏，把 USB 用途切换为「传输文件」
"""


def 找adb():
    """优先用 PATH 里的 adb，其次用脚本同目录下 platform-tools 里的。"""
    for name in ("adb", "adb.exe"):
        p = shutil.which(name)
        if p:
            return p
    这里 = os.path.dirname(os.path.abspath(__file__))
    for cand in (
        os.path.join(这里, "platform-tools", "adb.exe"),
        os.path.join(这里, "platform-tools", "adb"),
        os.path.join(这里, "adb.exe"),
        os.path.join(这里, "adb"),
    ):
        if os.path.exists(cand):
            return cand
    return None


def adb运行(adb, 参数):
    try:
        return subprocess.run(
            [adb] + 参数, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError as e:
        print(f"[错误] 运行 adb 失败：{e}")
        return None


def 获取设备(adb):
    adb运行(adb, ["start-server"])
    r = adb运行(adb, ["devices"])
    if not r:
        return None
    行 = [x.split() for x in r.stdout.splitlines()[1:] if x.strip()]
    ready = [x for x in 行 if len(x) >= 2 and x[1] == "device"]
    if ready:
        return ready[0][0]
    状态 = {x[1] for x in 行 if len(x) >= 2}
    if "unauthorized" in 状态:
        print("[错误] 手机还没授权调试。请在手机屏幕上点「允许 USB 调试」，然后重试。")
    elif "offline" in 状态:
        print("[错误] 设备处于 offline 状态。请拔插数据线，或运行 adb kill-server 后重试。")
    else:
        print("[错误] 没有检测到已连接的设备。请检查：")
        print("  · 数据线是否支持传输（不是只能充电的线）")
        print("  · USB 用途是否选为「传输文件」")
        print("  · 开发者选项里的「USB 调试」是否已打开")
    return None


def 手机有该目录(adb, serial, 路径):
    r = adb运行(adb, ["-s", serial, "shell", "ls", "-d", 路径])
    return bool(r) and r.returncode == 0 and "No such file" not in (r.stdout + r.stderr)


def 从手机导出(导出目录, 目录参数=""):
    adb = 找adb()
    if not adb:
        print(adb_安装提示)
        return False

    serial = 获取设备(adb)
    if not serial:
        return False

    要导出 = [x.strip().strip("/") for x in 目录参数.split(",") if x.strip()] if 目录参数 else 默认导出目录

    print(f"已连接设备：{serial}")
    print(f"导出到：{os.path.abspath(导出目录)}\n")

    成功数 = 0
    失败 = []
    for 名 in 要导出:
        远端 = f"/sdcard/{名}"
        if not 手机有该目录(adb, serial, 远端):
            print(f"[跳过] 手机里没有 {名}")
            continue
        本地 = os.path.join(导出目录, 名)
        print(f"[导出] {远端} → {本地}")
        r = subprocess.run([adb, "-s", serial, "pull", 远端, 本地])
        if r.returncode == 0:
            成功数 += 1
        else:
            失败.append(名)
            print(f"[失败] {名} 导出中断。可重新运行脚本继续，已导出的文件会被覆盖但不会丢失")

    print()
    if 成功数 == 0:
        print("[错误] 一个目录都没导出成功。可先用 --adb目录 \"DCIM\" 测试单个目录。")
        return False
    if 失败:
        print(f"[提示] 有 {len(失败)} 个目录导出失败：{', '.join(失败)}")
    print(f"共导出 {成功数} 个目录。")
    return True


# ---------------------------------------------------------------- 入口

def main():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            pass

    p = argparse.ArgumentParser(description="手机文件夹清理与分类工具")
    p.add_argument("--src", help="已导出到电脑的手机文件夹路径，例如 D:\\phone（配合 --adb 时可省略）")
    p.add_argument("--out", default="整理结果", help="整理后文件的输出目录（默认：整理结果）")
    p.add_argument("--报告目录", "--report", dest="报告目录", default="清理报告", help="报告输出目录")
    p.add_argument("--apply", action="store_true", help="执行复制（不改动源文件）")
    p.add_argument("--move", action="store_true", help="执行移动（会清空源位置）")
    p.add_argument("--delete", action="store_true", help="把可删候选移到「待删除」目录")
    p.add_argument("--yes", action="store_true", help="配合 --delete 使用，表示已确认")
    p.add_argument("--include-apk", action="store_true", help="把安装包也列为可删候选")
    p.add_argument("--skip-junk", action="store_true", help="归档时跳过可删候选和多余的重复文件")
    p.add_argument("--adb", action="store_true", help="用 adb 直接从手机导出文件（需开启 USB 调试）")
    p.add_argument("--adb目录", default="", help="要导出的手机目录，逗号分隔，如 DCIM,Download")
    p.add_argument("--导出目录", default="手机导出", help="adb 导出到本地的目录（默认：手机导出）")
    args = p.parse_args()

    if args.adb:
        if not 从手机导出(args.导出目录, args.adb目录):
            sys.exit(1)
        args.src = args.导出目录

    if not args.src:
        print("[错误] 请用 --adb 直接读手机，或者用 --src 指定已导出的目录。")
        print("例如：python phone_cleaner.py --adb")
        print("      python phone_cleaner.py --src \"D:\\phone\"")
        sys.exit(1)

    src = os.path.abspath(os.path.expanduser(args.src))
    if not os.path.isdir(src):
        print(f"[错误] 找不到目录：{src}")
        print("提示：如果是手动复制的手机文件，请确认路径正确；")
        print("      或者用 --adb 让脚本直接从手机导出。")
        sys.exit(1)
    if os.path.abspath(args.out) == src:
        print("[错误] 输出目录不能和源目录相同。")
        sys.exit(1)

    print(f"正在扫描：{src}")
    res = 扫描(src, include_apk=args.include_apk)
    报告路径, 清单路径, 可删路径, 总大小 = 写报告(res, src, args.报告目录)

    去重可省 = sum(g[0]["大小"] * (len(g) - 1) for g in res.dups)
    垃圾大小 = sum(j["大小"] for j in res.junk)

    print("\n===== 扫描完成 =====")
    print(f"文件总数：{len(res.files)}    总大小：{人类可读(总大小)}")
    print(f"可删候选：{len(res.junk)} 个（约 {人类可读(垃圾大小)}）")
    print(f"重复文件：{len(res.dups)} 组（可省约 {人类可读(去重可省)}）")
    print(f"空文件夹：{len(res.empty_dirs)} 个")
    print(f"系统目录（不动）：{len(res.system_dirs)} 个")

    分类数 = defaultdict(int)
    for f in res.files:
        分类数[f["分类"]] += 1
    print("\n按分类：")
    for cat, n in sorted(分类数.items()):
        print(f"  {cat}：{n} 个")

    print(f"\n报告已生成：{报告路径}")
    print(f"文件清单：{清单路径}")
    print(f"可删除清单：{可删路径}")

    日志 = []
    if args.apply or args.move:
        模式 = "move" if args.move else "copy"
        if 模式 == "move":
            print("\n正在按分类移动文件（源位置会被清空）……")
        else:
            print("\n正在按分类复制文件（源文件保持不动）……")
        跳过 = set()
        if args.skip_junk:
            跳过.update(j["绝对路径"] for j in res.junk)
            for g in res.dups:
                跳过.update(x["绝对路径"] for x in g[1:])
        日志 += 执行整理(res, src, os.path.abspath(args.out), 模式, 跳过)
        成功 = sum(1 for x in 日志 if x[4] == "成功")
        print(f"整理完成：成功 {成功} / {len(日志)}，输出目录：{os.path.abspath(args.out)}")

    if args.delete:
        if not args.yes:
            print("\n[提示] --delete 会把文件移入「待删除」目录而非直接删除。")
            print("       确认无误后加 --yes 再运行一次即可执行。")
        else:
            print("\n正在把可删候选移入「待删除」目录……")
            日志 += 移到待删除(res, src, os.path.join(os.path.abspath(args.报告目录), "待删除"))
            成功 = sum(1 for x in 日志 if x[4] == "成功")
            print(f"已处理 {成功} 项，可在「{args.报告目录}\\待删除」中复核后手工清空。")

    if 日志:
        print(f"操作日志：{写日志(日志, args.报告目录)}")
    else:
        print("\n本次仅扫描，没有改动任何文件。加 --apply 可复制归档，加 --delete --yes 可清理无用文件。")


if __name__ == "__main__":
    main()
