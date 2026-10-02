"""把掃描結果 + 使用者問答組裝成高品質 Markdown。"""
from __future__ import annotations

from .badges import build_badges
from .templates import STRINGS, get_sections

CHECK_ITEMS = [
    ("has_title", "標題 (首行 # ...)", "title"),
    ("has_badges", "徽章 (shields.io)", "badges"),
    ("has_install", "安裝說明", "install"),
    ("has_usage", "使用範例 / 快速開始", "usage"),
    ("has_features", "功能特色", "features"),
    ("has_structure", "專案結構", "structure"),
    ("has_license", "授權說明", "license"),
    ("has_demo", "展示截圖", "demo"),
]


def _t(lang: str) -> dict[str, str]:
    return STRINGS.get(lang, STRINGS["zh"])


def _code_block(lines: list[str]) -> str:
    if not lines:
        return ""
    # 每條 command 可能內含換行，逐行加 $ 前綴
    flat: list[str] = []
    for c in lines:
        flat.extend(c.splitlines() or [""])
    body = "\n".join(
        f"$ {line}" if line and not line.lstrip().startswith(("#", "$", "docker")) else line
        for line in flat
    )
    return f"```bash\n{body}\n```"


def _anchor_of(title: str) -> str:
    """GitHub 風格 anchor：去 '##' 與 emoji，只留中英數、空白、- _，空白轉 -。"""
    import re as _re
    text = title.lstrip("# ").strip().lower()
    # 移除 emoji / 符號，只留 \w、中日韓、空白、連字號
    text = _re.sub(r"[^\w\u4e00-\u9fff \-_]", "", text, flags=_re.UNICODE)
    text = _re.sub(r"\s+", "-", text.strip())
    return text


def build_toc(sections: list[str], s: dict[str, str]) -> str:
    title_map = {
        "features": s["features"], "demo": s["demo"], "install": s["install"],
        "usage": s["usage"], "api": s["api"], "config": s["config"],
        "tech_stack": s["tech_stack"], "project_structure": s["project_structure"],
        "test": s["test"], "contributing": s["contributing"],
        "license": s["license"], "acknowledgement": s["acknowledgement"],
        "highlights": s["highlights"], "contact": s["contact"],
        "members": s["members"], "reference": s["reference"],
        "deployment": s["deployment"], "pricing": s["pricing"],
    }
    lines = [s["toc"], ""]
    for sec in sections:
        if sec in ("header", "badges", "intro"):
            continue
        title = title_map.get(sec, sec)
        display = title.lstrip("# ").strip()
        lines.append(f"- [{display}](#{_anchor_of(title)})")
    return "\n".join(lines)


def render_section(name: str, info: dict, meta: dict, lang: str) -> str:
    s = _t(lang)
    badges_md = build_badges(info, meta.get("url", ""), lang)
    langs = info.get("languages", {})
    lang_line = ", ".join(f"{k} {v}%" for k, v in list(langs.items())[:5]) if langs else "—"

    if name == "header":
        tagline = meta.get("tagline") or info.get("description") or (
            "一句話介紹你的專案：解決什麼問題、為誰服務。" if lang == "zh"
            else "One-liner: what problem does this solve, and for whom?"
        )
        return f"# {meta.get('name') or info.get('name', 'My Project')}\n\n> {tagline}"
    if name == "badges":
        return badges_md
    if name == "intro":
        if lang == "zh":
            return (
                f"{meta.get('description') or '用 3–5 句話說明：背景痛點 → 解法 → 關鍵成果/數據。'}\n\n"
                f"- **主要語言**：{lang_line}\n"
                f"- **框架/函式庫**：{', '.join(info.get('frameworks') or ['—'])}\n"
                f"- **適用對象**：{meta.get('audience') or '開發者 / 業主 / 老師（請擇一補上）'}"
            )
        return (
            f"{meta.get('description') or 'In 3–5 sentences: pain point → solution → key results/metrics.'}\n\n"
            f"- **Main language**: {lang_line}\n"
            f"- **Frameworks**: {', '.join(info.get('frameworks') or ['—'])}\n"
            f"- **Audience**: {meta.get('audience') or 'developers / clients / instructors'}"
        )
    if name == "features":
        feats = meta.get("features") or []
        if feats:
            bullets = "\n".join(f"- ✅ {f}" for f in feats)
        else:
            # 依掃描結果給預設建議
            guesses: list[str] = []
            if info.get("has_docker"):
                guesses.append("✅ Docker 一鍵啟動（含 compose 範例）")
            if info.get("has_tests"):
                guesses.append("✅ 內建測試，保障重構品質")
            if "OpenGL" in (info.get("frameworks") or []):
                guesses.append("✅ 即時 3D 渲染（OpenGL）")
            if "Dear ImGui" in (info.get("frameworks") or []):
                guesses.append("✅ ImGui 即時除錯面板")
            guesses.append(s["todo_features"])
            bullets = "\n".join(f"- {g}" for g in guesses)
        return f"{s['features']}\n\n{bullets}"
    if name == "demo":
        shots = info.get("screenshots") or []
        if shots:
            imgs = "\n\n".join(f"![demo]({p})" for p in shots[:4])
            return f"{s['demo']}\n\n{imgs}"
        return f"{s['demo']}\n\n{s['no_demo']}"
    if name == "install":
        cmds = info.get("install_commands") or []
        body = _code_block(cmds) if cmds else ("```bash\n# 請補上安裝指令\n```" if lang == "zh" else "```bash\n# add install commands\n```")
        pre = "- Git\n- 對應語言工具鏈（見下方）" if lang == "zh" else "- Git\n- Language toolchain (see below)"
        return f"{s['install']}\n\n{s['prereq']}\n\n{pre}\n\n{s['steps']}\n\n{body}"
    if name == "usage":
        cmds = info.get("usage_commands") or []
        body = _code_block(cmds) if cmds else ("```bash\n# 請補上啟動指令\n```" if lang == "zh" else "```bash\n# add run commands\n```")
        extra = ""
        if meta.get("usage_note"):
            extra = f"\n\n{meta['usage_note']}"
        return f"{s['usage']}\n\n{body}{extra}"
    if name == "api":
        if lang == "zh":
            return f"{s['api']}\n\n| 函式 / 端點 | 說明 | 範例 |\n|---|---|---|\n| `example()` | 請補上 | `example()` |"
        return f"{s['api']}\n\n| Function / Endpoint | Description | Example |\n|---|---|---|\n| `example()` | TODO | `example()` |"
    if name == "config":
        if lang == "zh":
            return f"{s['config']}\n\n| 變數 / 檔案 | 說明 | 預設 |\n|---|---|---|\n| `scene.json` | 場景設定（本專案實測存在） | — |\n| `PORT` | 服務埠號 | `8000` |"
        return f"{s['config']}\n\n| Variable / File | Description | Default |\n|---|---|---|\n| `scene.json` | Scene config | — |\n| `PORT` | Service port | `8000` |"
    if name == "tech_stack":
        fw = ", ".join(info.get("frameworks") or ["—"])
        langs_top = ", ".join(list(langs.keys())[:5]) or "—"
        docker = "Docker ✅" if info.get("has_docker") else "Docker —"
        ci = "CI ✅" if info.get("has_ci") else "CI —"
        return f"{s['tech_stack']}\n\n- **語言**：{langs_top}\n- **框架**：{fw}\n- **DevOps**：{docker} / {ci}"
    if name == "project_structure":
        tree = info.get("file_tree") or []
        body = "\n".join(tree[:40]) if tree else "(空)"
        return f"{s['project_structure']}\n\n```text\n{body}\n```"
    if name == "test":
        cmds = info.get("test_commands") or []
        body = _code_block(cmds) if cmds else ("```bash\npytest\n```" if info.get("primary_language") == "Python" else "```bash\n# 請補上測試指令\n```")
        return f"{s['test']}\n\n{body}"
    if name == "contributing":
        if lang == "zh":
            return (f"{s['contributing']}\n\n1. Fork 本專案\n2. 建立分支 `git checkout -b feat/xxx`\n"
                    "3. 提交 `git commit -m 'feat: xxx'`\n4. 發 Pull Request")
        return (f"{s['contributing']}\n\n1. Fork the repo\n2. Create a branch `git checkout -b feat/xxx`\n"
                "3. Commit `git commit -m 'feat: xxx'`\n4. Open a Pull Request")
    if name == "license":
        lic = info.get("license") or meta.get("license") or ("MIT（建議，若無特殊需求）" if lang == "zh" else "MIT (recommended)")
        return f"{s['license']}\n\n{lic}"
    if name == "acknowledgement":
        return f"{s['acknowledgement']}\n\n- {meta.get('ack') or ('感謝所有開源專案與貢獻者。' if lang == 'zh' else 'Thanks to all open-source projects and contributors.')}"
    if name == "highlights":
        if lang == "zh":
            return (f"{s['highlights']}\n\n- 🏆 **為什麼選我**：{meta.get('why_me') or '交付準時、文件完整、可維護性高'}\n"
                    f"- 📈 **量化成果**：{meta.get('metrics') or '（請補：效能提升 x%、成本下降 y%…數字最能說服業主）'}\n"
                    f"- 🧾 **接案範圍**：{meta.get('scope') or '需求訪談 → 開發 → 文件 → 保固 n 個月'}")
        return (f"{s['highlights']}\n\n- 🏆 **Why me**: {meta.get('why_me') or 'on-time delivery, complete docs, maintainable'}\n"
                f"- 📈 **Metrics**: {meta.get('metrics') or '(add numbers: x% faster, y% cheaper…)'}\n"
                f"- 🧾 **Scope**: {meta.get('scope') or 'discovery → build → docs → n-month warranty'}")
    if name == "contact":
        c = meta.get("contact") or ("你的名字 / Email / 作品集連結" if lang == "zh" else "Your name / Email / Portfolio URL")
        return f"{s['contact']}\n\n- {c}"
    if name == "members":
        m = meta.get("members") or ("| 姓名 | 分工 | 貢獻 |\n|---|---|---|\n| A | 渲染引擎 | 60% |\n| B | 文件/測試 | 40% |" if lang == "zh"
                                        else "| Name | Role | Contribution |\n|---|---|---|\n| A | Engine | 60% |\n| B | Docs/Tests | 40% |")
        return f"{s['members']}\n\n{m}"
    if name == "reference":
        return f"{s['reference']}\n\n- {meta.get('refs') or '（請補上論文/教學/開源專案連結）'}"
    if name == "deployment":
        if lang == "zh":
            return (f"{s['deployment']}\n\n```bash\ndocker compose up --build -d\n```\n\n"
                    "或部署到 Render / Fly.io / Zeabur，記得設定環境變數。")
        return (f"{s['deployment']}\n\n```bash\ndocker compose up --build -d\n```\n\n"
                "Or deploy to Render / Fly.io / Zeabur with env vars set.")
    if name == "pricing":
        if lang == "zh":
            return (f"{s['pricing']}\n\n- **免費版**：本地 CLI 開源免費\n"
                    "- **Pro（$9/mo）**：AI 潤飾、多語系、徽章/架構圖、版本歷史\n"
                    "- **接案包（$49/次）**：幫你的作品集一次寫到好，含業主簡報頁")
        return (f"{s['pricing']}\n\n- **Free**: local CLI, open source\n"
                "- **Pro ($9/mo)**: AI polish, i18n, badges/diagrams, history\n"
                "- **Portfolio pack ($49)**: done-for-you README + one-page pitch")
    return ""


def generate(info: dict, meta: dict, template: str = "library", lang: str = "zh") -> str:
    """主入口。lang: zh / en / bilingual。"""
    sections = get_sections(template)
    if lang == "bilingual":
        zh = generate(info, meta, template, "zh")
        en = generate(info, meta, template, "en")
        # 雙語：中文為主，英文附錄（避免無限遞迴：直接串接）
        return zh.rstrip() + "\n\n---\n\n# English Version\n\n" + en
    chunks: list[str] = []
    # header + badges + intro 緊連
    for sec in sections:
        md = render_section(sec, info, meta, lang)
        if md:
            chunks.append(md)
        # 在 intro 後插入目錄
        if sec == "intro":
            chunks.append(build_toc(sections, _t(lang)))
    chunks.append(_t(lang)["generated_footer"])
    return "\n\n".join(chunks) + "\n"


def check_readme(text: str) -> dict:
    """README 品質評分 0–100 + 改進建議。"""
    score = 0
    suggestions: list[str] = []
    details: dict[str, bool] = {}
    lines = text.splitlines()
    details["has_title"] = any(l.startswith("# ") for l in lines)
    details["has_badges"] = "img.shields.io" in text or "![" in text and "badge" in text.lower()
    details["has_install"] = any(k in text.lower() for k in ["安裝", "installation", "pip install", "npm install", "make", "cmake"])
    details["has_usage"] = any(k in text.lower() for k in ["快速開始", "quick start", "usage", "cargo run", "python ", "./main"])
    details["has_features"] = any(k in text for k in ["功能特色", "Features", "✨"])
    details["has_structure"] = any(k in text for k in ["專案結構", "Project Structure", "📁"])
    details["has_license"] = any(k in text for k in ["授權", "License", "📄", "MIT", "Apache"])
    details["has_demo"] = any(k in text for k in ["展示", "Demo", "🖼"]) and (".png" in text or ".jpg" in text or ".gif" in text or "images/" in text)

    weights = {"has_title": 10, "has_badges": 10, "has_install": 20,
               "has_usage": 20, "has_features": 15, "has_structure": 10,
               "has_license": 10, "has_demo": 5}
    for key, w in weights.items():
        if details.get(key):
            score += w
        else:
            label = next((lbl for k, lbl, _ in CHECK_ITEMS if k == key), key)
            suggestions.append(f"缺少「{label}」：執行 `readme-gen --init` 可自動補上。")
    if len(text) < 800:
        suggestions.append(f"內容偏短（{len(text)} 字元）：建議補到 800+ 字元，含安裝/範例/結構。")
        score = max(0, score - 5)
    if "TODO" in text:
        suggestions.append("仍有 TODO 未填：把 TODO 換成真實功能描述，分數會更高。")
    return {"score": min(100, score), "details": details, "suggestions": suggestions}
