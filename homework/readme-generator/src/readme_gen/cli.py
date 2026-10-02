"""CLI：scan / init / build / check 四個子命令 + 相容舊式旗標。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .generator import check_readme, generate
from .scanner import scan
from .templates import valid_templates

VERSION = "0.1.0"

# Windows 終端預設 cp950 會印不出 emoji，直接把 stdout 切成 UTF-8（失敗則忽略）
try:
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        ans = input(f"{prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return ans or default


def wizard(info: dict) -> dict:
    print("\n=== README 產生器 · 互動精靈 ===")
    print(f"偵測到專案：{info.get('name')} | 主語言：{info.get('primary_language') or '未知'}")
    fw = ", ".join(info.get("frameworks") or ["無"])
    print(f"框架：{fw}")
    print("直接按 Enter 可接受 [預設值]。\n")
    meta: dict = {}
    meta["name"] = ask("專案名稱", str(info.get("name", "")))
    meta["tagline"] = ask("一句話標語 (tagline)", str(info.get("description") or ""))
    meta["description"] = ask("專案簡介 (3-5 句)", "")
    meta["audience"] = ask("適用對象", "開發者")
    feats_raw = ask("功能特色 (用 ; 分隔多項，可空白)", "")
    meta["features"] = [f.strip() for f in feats_raw.split(";") if f.strip()]
    meta["license"] = ask("授權", str(info.get("license") or "MIT"))
    meta["contact"] = ask("聯絡方式", "")
    meta["url"] = ask("專案網址 (GitHub)", "")
    print("\n模板：library=開源函式庫 / portfolio=接案作品集 / course=課程專題 / saas=商業產品")
    meta["_template"] = ask("選擇模板", "library")
    if meta["_template"] not in valid_templates():
        print(f"未知模板，改用 library。")
        meta["_template"] = "library"
    print("語言：zh=中文 / en=英文 / bilingual=中英雙語")
    meta["_lang"] = ask("選擇語言", "zh")
    if meta["_lang"] not in ("zh", "en", "bilingual"):
        meta["_lang"] = "zh"
    return meta


def cmd_scan(args: argparse.Namespace) -> int:
    info = scan(args.path)
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(f"專案：{info['name']}")
        print(f"主語言：{info.get('primary_language') or '未知'}")
        print(f"語言分佈：{info['languages']}")
        print(f"框架：{info['frameworks'] or '無'}")
        print(f"授權：{info.get('license') or '未知'}")
        print(f"安裝：{info['install_commands'] or '—'}")
        print(f"啟動：{info['usage_commands'] or '—'}")
        print(f"測試：{info['test_commands'] or '—'}")
        print(f"Docker：{info['has_docker']}  CI：{info['has_ci']}  測試目錄：{info['has_tests']}")
        print(f"截圖：{info['screenshots'] or '無'}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    p = Path(args.file)
    if not p.is_file():
        print(f"找不到檔案: {p}", file=sys.stderr)
        return 1
    text = p.read_text(encoding="utf-8", errors="ignore")
    result = check_readme(text)
    print(f"README 評分: {result['score']}/100")
    for k, v in result["details"].items():
        print(f"  [{'OK' if v else 'MISS'}] {k}")
    if result["suggestions"]:
        print("\n改進建議：")
        for s in result["suggestions"]:
            print(f"  - {s}")
    else:
        print("\n很棒！README 結構完整。")
    return 0


def cmd_build(args: argparse.Namespace, meta: dict | None = None) -> int:
    info = scan(args.path)
    meta = meta or {}
    # 命令列參數覆蓋
    for key in ["name", "tagline", "description", "audience", "license", "contact", "url"]:
        val = getattr(args, key, None)
        if val:
            meta[key] = val
    if getattr(args, "features", None):
        meta["features"] = [f.strip() for f in str(args.features).split(";") if f.strip()]
    template = getattr(args, "template", None) or meta.pop("_template", "library")
    lang = getattr(args, "lang", None) or meta.pop("_lang", "zh")
    md = generate(info, meta, template=template, lang=lang)
    out = Path(getattr(args, "output", None) or "README.generated.md")
    # --force 覆寫 README.md 的保護
    if out.resolve().name.lower() == "readme.md" and out.exists() and not getattr(args, "force", False):
        print(f"拒絕直接覆寫 {out}（避免洗掉原檔）。請用 -o 另存，或加 --force。", file=sys.stderr)
        return 2
    out.write_text(md, encoding="utf-8")
    print(f"已產生：{out}（模板={template}，語言={lang}，{len(md)} 字元）")
    result = check_readme(md)
    print(f"品質評分：{result['score']}/100")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    info = scan(args.path)
    meta = wizard(info)
    # 把 wizard 的模板/語言搬到 args
    args.template = meta.get("_template", "library")
    args.lang = meta.get("_lang", "zh")
    args.output = args.output or "README.generated.md"
    return cmd_build(args, meta)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="readme-gen",
        description="專案 README 產生器：掃描專案 → 互動問答 → 產出高品質 README（含評分）。",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=False)

    p_scan = sub.add_parser("scan", help="只掃描專案，輸出分析報告")
    p_scan.add_argument("path", nargs="?", default=".", help="專案路徑")
    p_scan.add_argument("--json", action="store_true", help="輸出 JSON")

    p_init = sub.add_parser("init", help="互動式精靈（推薦新手）")
    p_init.add_argument("path", nargs="?", default=".", help="專案路徑")
    p_init.add_argument("-o", "--output", default="README.generated.md", help="輸出檔名")

    p_build = sub.add_parser("build", help="非互動一鍵產生（適合 CI）")
    p_build.add_argument("path", nargs="?", default=".", help="專案路徑")
    p_build.add_argument("-o", "--output", default="README.generated.md")
    p_build.add_argument("--template", default="library", choices=valid_templates())
    p_build.add_argument("--lang", default="zh", choices=["zh", "en", "bilingual"])
    p_build.add_argument("--name", default=None)
    p_build.add_argument("--tagline", default=None)
    p_build.add_argument("--description", default=None)
    p_build.add_argument("--audience", default=None)
    p_build.add_argument("--features", default=None, help="用 ; 分隔")
    p_build.add_argument("--license", default=None)
    p_build.add_argument("--contact", default=None)
    p_build.add_argument("--url", default=None)
    p_build.add_argument("--force", action="store_true", help="允許覆寫 README.md")

    p_check = sub.add_parser("check", help="為既有 README 打分")
    p_check.add_argument("--file", default="README.md")

    # 相容舊式：readme-gen --scan . / --init / --check
    ap.add_argument("--scan", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--init", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--check", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--path", default=".", help=argparse.SUPPRESS)
    ap.add_argument("-o", "--output", default="README.generated.md", help=argparse.SUPPRESS)
    ap.add_argument("--template", default="library", help=argparse.SUPPRESS)
    ap.add_argument("--lang", default="zh", help=argparse.SUPPRESS)
    ap.add_argument("--file", default="README.md", help=argparse.SUPPRESS)
    ap.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    # 舊式旗標轉子命令
    if args.cmd is None:
        if args.scan:
            args.cmd = "scan"
            args.path = args.path
            args.json = False
        elif args.init:
            args.cmd = "init"
        elif args.check:
            args.cmd = "check"
        else:
            ap.print_help()
            return 0
    if args.cmd == "scan":
        if not hasattr(args, "json"):
            args.json = False
        return cmd_scan(args)
    if args.cmd == "init":
        return cmd_init(args)
    if args.cmd == "build":
        return cmd_build(args)
    if args.cmd == "check":
        return cmd_check(args)
    ap.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
