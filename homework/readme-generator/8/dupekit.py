#!/usr/bin/env python3
"""dupekit - 安全、快速的重複檔案尋找與清理工具（純標準庫）。

流程（逐階段縮小候選，避免不必要的讀取）：
    1. 依檔案大小分組            （只需 stat，不讀內容）
    2. 依部分雜湊（頭/中/尾）分組  （每檔只讀約 192KB）
    3. 依完整雜湊分組             （只對仍有疑義的檔案做完整讀取）
    4. 執行動作前再做逐位元組比對   （最後一道保險）

預設只「報告」；要真的刪除 / 硬連結 / 移動，必須加上 --apply。
"""
from __future__ import annotations

import argparse
import filecmp
import fnmatch
import hashlib
import json
import os
import shutil
import stat
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from typing import Callable, Iterable, Optional

CHUNK = 1 << 20          # 完整雜湊每次讀 1MB
SAMPLE = 64 * 1024       # 部分雜湊每段取樣 64KB
DEFAULT_EXCLUDES = (".git", ".svn", ".hg", "node_modules", "__pycache__")
KEEP_POLICIES = ("first", "oldest", "newest", "shortest")
ACTIONS = ("report", "delete", "hardlink", "move")


# --------------------------------------------------------------------------
# 資料結構
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FileInfo:
    path: str
    size: int
    mtime: float
    dev: int
    ino: int
    root_index: int


@dataclass
class DupGroup:
    size: int
    digest: str
    files: list  # list[FileInfo]

    @property
    def reclaimable(self) -> int:
        return self.size * (len(self.files) - 1)


@dataclass
class Action:
    kind: str
    path: str
    keeper: str
    size: int
    digest: str
    status: str = "planned"   # planned / done / skipped / error
    detail: str = ""


# --------------------------------------------------------------------------
# 工具函式
# --------------------------------------------------------------------------
def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{int(n)} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def parse_size(text: str) -> int:
    """'512' / '10K' / '1.5MB' / '2g' → bytes"""
    s = text.strip().upper()
    if s.endswith("B"):
        s = s[:-1]
    mult = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}
    if s and s[-1] in mult:
        return int(float(s[:-1]) * mult[s[-1]])
    return int(float(s))


def _is_excluded(name: str, path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(path, p) for p in patterns)


# --------------------------------------------------------------------------
# 掃描
# --------------------------------------------------------------------------
def scan(roots, min_size: int = 1, excludes=DEFAULT_EXCLUDES):
    """遞迴掃描，回傳 (files, stats)。

    - 略過符號連結與非一般檔案
    - 同一個 inode（硬連結）只計一次：它們不佔額外空間，不算「重複」
    """
    files: list[FileInfo] = []
    seen_inodes: set = set()
    stats = {"visited": 0, "hardlink_skipped": 0, "too_small": 0, "unreadable": 0}

    for ri, root in enumerate(roots):
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = sorted(
                d for d in dirnames
                if not _is_excluded(d, os.path.join(dirpath, d), excludes)
            )
            for name in sorted(filenames):
                path = os.path.join(dirpath, name)
                if _is_excluded(name, path, excludes):
                    continue
                try:
                    st = os.lstat(path)
                except OSError:
                    stats["unreadable"] += 1
                    continue
                if not stat.S_ISREG(st.st_mode):
                    continue
                stats["visited"] += 1
                if st.st_size < min_size:
                    stats["too_small"] += 1
                    continue
                if st.st_ino:
                    ident = (st.st_dev, st.st_ino)
                    if ident in seen_inodes:
                        stats["hardlink_skipped"] += 1
                        continue
                    seen_inodes.add(ident)
                files.append(FileInfo(path, st.st_size, st.st_mtime,
                                      st.st_dev, st.st_ino, ri))
    return files, stats


# --------------------------------------------------------------------------
# 雜湊
# --------------------------------------------------------------------------
def partial_hash(path: str, size: int) -> str:
    """取樣檔頭、檔中、檔尾各 64KB。"""
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        h.update(f.read(SAMPLE))
        if size > 2 * SAMPLE:
            f.seek(size // 2 - SAMPLE // 2)
            h.update(f.read(SAMPLE))
        if size > SAMPLE:
            f.seek(max(size - SAMPLE, SAMPLE))
            h.update(f.read(SAMPLE))
    return h.hexdigest()


def full_hash(path: str) -> str:
    h = hashlib.blake2b(digest_size=32)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _group_by(files, keyfn, workers: int, errors: list):
    """平行計算 key，回傳「仍有 2 個以上成員」的分組 [(key, files)]。"""
    buckets = defaultdict(list)

    def work(f):
        try:
            return f, keyfn(f), None
        except OSError as e:
            return f, None, e

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for f, key, err in ex.map(work, files):
            if err is not None:
                errors.append((f.path, str(err)))
            else:
                buckets[key].append(f)
    return [(k, g) for k, g in buckets.items() if len(g) > 1]


# --------------------------------------------------------------------------
# 尋找重複
# --------------------------------------------------------------------------
def find_duplicates(files, workers: int = 4,
                    log: Callable[[str], None] = lambda _m: None):
    errors: list = []

    by_size = defaultdict(list)
    for f in files:
        by_size[f.size].append(f)
    cands = [f for g in by_size.values() if len(g) > 1 for f in g]
    log(f"階段 1/3 依大小：{len(files)} 個檔案 → {len(cands)} 個候選")

    groups = _group_by(cands, lambda f: (f.size, partial_hash(f.path, f.size)),
                       workers, errors)
    cands = [f for _k, g in groups for f in g]
    log(f"階段 2/3 部分雜湊：{len(cands)} 個候選")

    groups = _group_by(cands, lambda f: full_hash(f.path), workers, errors)
    log(f"階段 3/3 完整雜湊：找到 {len(groups)} 組重複")

    final = [
        DupGroup(size=g[0].size, digest=digest,
                 files=sorted(g, key=lambda f: (f.root_index, f.path)))
        for digest, g in groups
    ]
    final.sort(key=lambda g: g.reclaimable, reverse=True)
    return final, errors


# --------------------------------------------------------------------------
# 保留策略與動作
# --------------------------------------------------------------------------
def pick_keeper(files, policy: str) -> FileInfo:
    keys = {
        "first":    lambda f: (f.root_index, f.path),
        "oldest":   lambda f: (f.mtime, f.root_index, f.path),
        "newest":   lambda f: (-f.mtime, f.root_index, f.path),
        "shortest": lambda f: (len(f.path), f.root_index, f.path),
    }
    return min(files, key=keys[policy])


def plan_actions(groups, policy: str, kind: str) -> list:
    actions = []
    for g in groups:
        keeper = pick_keeper(g.files, policy)
        for f in g.files:
            if f is not keeper:
                actions.append(Action(kind, f.path, keeper.path, f.size, g.digest))
    return actions


def _unique_dest(directory: str, name: str) -> str:
    dest = os.path.join(directory, name)
    n = 1
    while os.path.exists(dest):
        dest = os.path.join(directory, f"{n}_{name}")
        n += 1
    return dest


def run_action(a: Action, move_to: Optional[str] = None) -> None:
    """執行單一動作；失敗時丟出例外。動作前一律重新驗證內容完全相同。"""
    if not os.path.isfile(a.keeper):
        raise RuntimeError("保留檔已不存在，為安全起見略過")
    if not os.path.isfile(a.path):
        raise RuntimeError("目標檔已不存在")
    if os.path.samefile(a.path, a.keeper):
        raise RuntimeError("與保留檔是同一個檔案，略過")
    if not filecmp.cmp(a.path, a.keeper, shallow=False):
        raise RuntimeError("逐位元組比對不一致，略過")

    if a.kind == "delete":
        os.remove(a.path)
    elif a.kind == "hardlink":
        tmp = f"{a.path}.dupekit-{os.getpid()}.tmp"
        os.link(a.keeper, tmp)          # 跨磁碟會在此丟出 OSError
        try:
            os.replace(tmp, a.path)     # 原子替換
        except OSError:
            os.unlink(tmp)
            raise
    elif a.kind == "move":
        if not move_to:
            raise RuntimeError("move 需要 --move-to")
        os.makedirs(move_to, exist_ok=True)
        dest = _unique_dest(move_to, f"{a.digest[:8]}_{os.path.basename(a.path)}")
        shutil.move(a.path, dest)
        a.detail = f"→ {dest}"
    else:
        raise RuntimeError(f"未知動作 {a.kind}")


def execute(actions, apply: bool, move_to: Optional[str] = None) -> None:
    for a in actions:
        if not apply:
            continue  # 預覽模式：維持 planned
        try:
            run_action(a, move_to)
            a.status = "done"
        except (OSError, RuntimeError) as e:
            a.status = "error"
            a.detail = str(e)


# --------------------------------------------------------------------------
# 報告
# --------------------------------------------------------------------------
def format_report(groups, actions, scan_stats, errors, kind, apply) -> str:
    keeper_of = {a.path: a.keeper for a in actions}
    lines = []
    for i, g in enumerate(groups, 1):
        lines.append(f"[{i}] {len(g.files)} 個檔案 × {human(g.size)}"
                     f"（可回收 {human(g.reclaimable)}） #{g.digest[:12]}")
        keeper = None
        if actions:
            keeper = next((f.path for f in g.files if f.path not in keeper_of), None)
        for f in g.files:
            tag = "保留" if (keeper == f.path) else "重複"
            lines.append(f"    {tag}  {f.path}")
        lines.append("")
    total = sum(g.reclaimable for g in groups)
    lines.append("=" * 60)
    lines.append(f"掃描檔案：{scan_stats['visited']}　重複組數：{len(groups)}　"
                 f"重複檔案：{sum(len(g.files) - 1 for g in groups)}")
    lines.append(f"可回收空間：{human(total)}")
    if scan_stats["hardlink_skipped"]:
        lines.append(f"（已排除 {scan_stats['hardlink_skipped']} 個硬連結，它們不佔額外空間）")
    if kind != "report":
        done = sum(a.status == "done" for a in actions)
        err = sum(a.status == "error" for a in actions)
        if apply:
            freed = sum(a.size for a in actions if a.status == "done")
            lines.append(f"動作 {kind}：成功 {done}、失敗 {err}，實際釋放 {human(freed)}")
            for a in actions:
                if a.status == "error":
                    lines.append(f"  ! {a.path}: {a.detail}")
        else:
            lines.append(f"動作 {kind}：預覽模式，共 {len(actions)} 項，尚未變更任何檔案"
                         f"（加上 --apply 才會執行）")
    for path, msg in errors:
        lines.append(f"  ! 無法讀取 {path}: {msg}")
    return "\n".join(lines)


def to_json(groups, actions, scan_stats, errors) -> dict:
    return {
        "summary": {
            "groups": len(groups),
            "reclaimable_bytes": sum(g.reclaimable for g in groups),
            **scan_stats,
        },
        "groups": [{"size": g.size, "digest": g.digest,
                    "files": [f.path for f in g.files]} for g in groups],
        "actions": [asdict(a) for a in actions],
        "errors": [{"path": p, "error": m} for p, m in errors],
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dupekit",
        description="尋找並（可選地）清理重複檔案。預設只預覽，不會變更任何檔案。")
    p.add_argument("paths", nargs="+", help="要掃描的目錄（可多個）")
    p.add_argument("--min-size", default="1", help="忽略小於此大小的檔案，如 4K、1MB（預設 1）")
    p.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                   help="排除符合的檔名/路徑（可重複）")
    p.add_argument("--no-default-excludes", action="store_true",
                   help=f"不要自動排除 {', '.join(DEFAULT_EXCLUDES)}")
    p.add_argument("--keep", choices=KEEP_POLICIES, default="first",
                   help="每組保留哪一個：first=最前面的目錄優先、oldest、newest、shortest（路徑最短）")
    p.add_argument("--action", choices=ACTIONS, default="report",
                   help="report=只報告；delete=刪除重複；hardlink=換成硬連結；move=搬到 --move-to")
    p.add_argument("--move-to", metavar="DIR", help="action=move 時的目的目錄")
    p.add_argument("--apply", action="store_true", help="真的執行動作（否則只預覽）")
    p.add_argument("--json", metavar="FILE", help="另外輸出 JSON 報告到檔案（- 表示 stdout）")
    p.add_argument("--workers", type=int, default=min(8, (os.cpu_count() or 2) * 2),
                   help="平行雜湊的執行緒數")
    p.add_argument("-q", "--quiet", action="store_true", help="不顯示進度")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    for p in args.paths:
        if not os.path.isdir(p):
            print(f"錯誤：{p} 不是目錄", file=sys.stderr)
            return 2
    if args.action == "move":
        if not args.move_to:
            print("錯誤：--action move 需要 --move-to", file=sys.stderr)
            return 2
        dest = os.path.realpath(args.move_to)
        for p in args.paths:
            root = os.path.realpath(p)
            if os.path.commonpath([dest, root]) == root:
                print("錯誤：--move-to 不可位於被掃描的目錄內", file=sys.stderr)
                return 2
    try:
        min_size = max(1, parse_size(args.min_size))
    except ValueError:
        print(f"錯誤：無法解析 --min-size {args.min_size!r}", file=sys.stderr)
        return 2

    log = (lambda m: None) if args.quiet else (lambda m: print(m, file=sys.stderr))
    excludes = tuple(args.exclude) + (() if args.no_default_excludes else DEFAULT_EXCLUDES)

    files, scan_stats = scan(args.paths, min_size, excludes)
    groups, errors = find_duplicates(files, args.workers, log)

    actions = []
    if args.action != "report":
        actions = plan_actions(groups, args.keep, args.action)
        execute(actions, args.apply, args.move_to)
    elif groups:
        # report 模式也標出會保留哪一個
        actions = plan_actions(groups, args.keep, "report")

    print(format_report(groups, actions, scan_stats, errors, args.action, args.apply))

    if args.json:
        data = json.dumps(to_json(groups, actions, scan_stats, errors),
                          ensure_ascii=False, indent=2)
        if args.json == "-":
            print(data)
        else:
            with open(args.json, "w", encoding="utf-8") as fh:
                fh.write(data)

    return 1 if any(a.status == "error" for a in actions) else 0


if __name__ == "__main__":
    sys.exit(main())
