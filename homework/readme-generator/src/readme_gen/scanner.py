"""專案掃描器：零依賴，只用標準函式庫。

掃描一個資料夾，回傳 ProjectInfo dict，包含：
- name, description (盡力推斷)
- languages: {Python: 60.5, C++: 30.0, ...} 百分比
- frameworks: ["FastAPI", "React", ...]
- package_managers / build_tools
- entry_points: 安裝/啟動指令
- has_docker, has_ci, has_tests, license, screenshots
- file_tree (精簡版，最多 2 層)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

EXT_TO_LANG = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++",
    ".c": "C",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".less": "Less",
    ".sql": "SQL",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".lua": "Lua",
    ".r": "R",
    ".jl": "Julia",
    ".dart": "Dart",
    ".hs": "Haskell",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".pl": "Perl",
    ".pm": "Perl",
    ".vim": "Vim script",
    ".cmake": "CMake",
    ".glsl": "GLSL",
    ".vert": "GLSL",
    ".frag": "GLSL",
}

IGNORE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__",
    ".pytest_cache", ".venv", "venv", ".idea", ".vscode",
    "dist", "build", "target", ".next", ".nuxt", "coverage",
    "glad_output", "__MACOSX",
}

# 常見框架 / 函式庫關鍵字 -> 顯示名稱
DEP_KEYWORDS = {
    # Python
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask",
    "torch": "PyTorch", "tensorflow": "TensorFlow", "numpy": "NumPy",
    "pandas": "pandas", "pytest": "pytest", "click": "Click",
    "typer": "Typer", "sqlalchemy": "SQLAlchemy", "celery": "Celery",
    "opencv-python": "OpenCV", "cv2": "OpenCV", "pillow": "Pillow",
    "pygame": "Pygame", "pyqt": "PyQt", "tkinter": "tkinter",
    # JS/TS
    "react": "React", "vue": "Vue", "next": "Next.js", "nuxt": "Nuxt",
    "express": "Express", "nest": "@nestjs/core", "typescript": "TypeScript",
    "vite": "Vite", "webpack": "webpack", "tailwindcss": "Tailwind CSS",
    "electron": "Electron",
    # 其他
    "glfw": "GLFW", "glad": "GLAD", "imgui": "Dear ImGui",
    "opengl": "OpenGL", "glm": "GLM",
    "gin-gonic": "Gin", "spring-boot": "Spring Boot",
    "flutter": "Flutter", "react-native": "React Native",
}

LICENSE_FILES = ["LICENSE", "LICENSE.txt", "LICENSE.md", "LICENCE", "COPYING"]


def _read_text(path: Path, limit: int = 200_000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return text[:limit]
    except (OSError, UnicodeError):
        return ""


def detect_languages(root: Path) -> dict[str, float]:
    counts: dict[str, int] = {}
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # 修剪忽略目錄 (就地修改)
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for fn in filenames:
            ext = Path(fn).suffix.lower()
            lang = EXT_TO_LANG.get(ext)
            if lang:
                try:
                    size = (Path(dirpath) / fn).stat().st_size
                except OSError:
                    size = 1
                # 用檔案大小加權，比單純計數更準；上限定 200KB 避免單一大檔壟斷
                counts[lang] = counts.get(lang, 0) + min(size, 200_000) + 500
                total += min(size, 200_000) + 500
    if total == 0:
        return {}
    pct = {k: round(v / total * 100, 1) for k, v in counts.items()}
    return dict(sorted(pct.items(), key=lambda kv: kv[1], reverse=True))


def detect_frameworks(root: Path) -> list[str]:
    found: list[str] = []
    dep_blobs: list[str] = []
    native_blobs: list[str] = []
    # 收集依賴檔內容 (只在這裡找 JS/Python 等框架，避免 main.cpp 變數名誤判)
    for name in ["requirements.txt", "pyproject.toml", "package.json",
                 "Pipfile", "environment.yml", "Cargo.toml", "go.mod",
                 "pom.xml", "build.gradle", "Gemfile", "composer.json",
                 "pubspec.yaml", "CMakeLists.txt", "Makefile", "conanfile.txt"]:
        p = root / name
        if p.is_file():
            dep_blobs.append(_read_text(p).lower())
    # C/C++ 原生庫：看目錄 / 原始碼 include
    for vendor in ["glad", "glfw", "imgui", "glm", "KHR"]:
        if (root / vendor).exists():
            native_blobs.append(vendor)
    main_cpp = root / "main.cpp"
    if main_cpp.is_file():
        native_blobs.append(_read_text(main_cpp, 50_000).lower())
    dep_blob = "\n".join(dep_blobs)
    native_blob = "\n".join(native_blobs)
    combined = dep_blob + "\n" + native_blob
    # 原生庫允許從原始碼/目錄判斷；其他框架只看依賴檔
    NATIVE_OK = {"glfw", "glad", "imgui", "opengl", "glm"}
    for keyword, display in DEP_KEYWORDS.items():
        hay = combined if keyword.lower() in NATIVE_OK else dep_blob
        # 避免子字串誤判 ("next" 匹配 "next_frame" 等)：用非 [a-z0-9_-] 包夾判斷
        pattern = r"(?<![a-z0-9_\-])" + re.escape(keyword.lower()) + r"(?![a-z0-9_\-])"
        if re.search(pattern, hay) and display not in found:
            found.append(display)
    return sorted(found)


def detect_license(root: Path) -> str | None:
    for name in LICENSE_FILES:
        p = root / name
        if p.is_file():
            text = _read_text(p, 8_000).lower()
            if "mit license" in text or text.startswith("mit "):
                return "MIT"
            if "apache license" in text:
                return "Apache-2.0"
            if "gnu general public license" in text:
                if "version 3" in text:
                    return "GPL-3.0"
                if "version 2" in text:
                    return "GPL-2.0"
                return "GPL"
            if "bsd" in text and "license" in text:
                return "BSD"
            if "mozilla public license" in text:
                return "MPL-2.0"
            return "Custom (see LICENSE file)"
    # package.json / pyproject 裡的 license 欄位
    for fname in ["package.json", "pyproject.toml"]:
        p = root / fname
        if p.is_file():
            text = _read_text(p, 20_000)
            m = re.search(r'"license"\s*:\s*"([^"]+)"', text)
            if m:
                return m.group(1)
            m = re.search(r'license\s*=\s*["\']([^"\']+)["\']', text)
            if m:
                return m.group(1)
    return None


def detect_entry_points(root: Path) -> dict[str, list[str]]:
    """回傳 {install: [...], usage: [...], test: [...]} 建議指令。"""
    install: list[str] = []
    usage: list[str] = []
    test: list[str] = []

    if (root / "package.json").is_file():
        try:
            pkg = json.loads(_read_text(root / "package.json", 50_000) or "{}")
            scripts = pkg.get("scripts", {})
        except json.JSONDecodeError:
            scripts = {}
        install.append("npm install")
        if "dev" in scripts:
            usage.append("npm run dev")
        elif "start" in scripts:
            usage.append("npm start")
        else:
            usage.append("npm start")
        if "test" in scripts:
            test.append("npm test")

    if (root / "requirements.txt").is_file():
        install.append("pip install -r requirements.txt")
    if (root / "pyproject.toml").is_file():
        install.append("pip install -e .")
    if (root / "Pipfile").is_file():
        install.append("pipenv install")
    if (root / "environment.yml").is_file():
        install.append("conda env create -f environment.yml")
    if (root / "Cargo.toml").is_file():
        install.append("cargo build")
        usage.append("cargo run")
        test.append("cargo test")
    if (root / "go.mod").is_file():
        install.append("go mod download")
        usage.append("go run ./...")
        test.append("go test ./...")
    if (root / "pom.xml").is_file():
        install.append("mvn package")
        usage.append("mvn exec:java  # 或 java -jar target/*.jar")
        test.append("mvn test")
    if (root / "build.gradle").is_file():
        install.append("./gradlew build")
        test.append("./gradlew test")
    if (root / "CMakeLists.txt").is_file() or (root / "Makefile").is_file():
        if (root / "CMakeLists.txt").is_file():
            install.append("cmake -B build && cmake --build build")
            usage.append("./build/<executable>")
        if (root / "Makefile").is_file():
            install.append("make")
            # 常見 C++ OpenGL 專案
            if (root / "main.cpp").is_file() or (root / "main.exe").is_file():
                usage.append("./main.exe  # Windows")
                usage.append("./main  # Linux/macOS")
    if (root / "Dockerfile").is_file() or (root / "docker-compose.yml").is_file():
        usage.append("docker compose up --build")

    # Python 入口啟發式
    for candidate in ["main.py", "app.py", "manage.py", "cli.py", "bot.py"]:
        if (root / candidate).is_file():
            usage.append(f"python {candidate}")
            break
    # 去重保序
    def dedup(xs: list[str]) -> list[str]:
        seen, out = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out
    return {"install": dedup(install), "usage": dedup(usage), "test": dedup(test)}


def detect_misc(root: Path) -> dict:
    has_docker = (root / "Dockerfile").is_file() or (root / "docker-compose.yml").is_file()
    ci = any((root / d).is_dir() for d in [".github", ".gitlab-ci.yml", ".circleci"]) or \
        (root / ".github" / "workflows").is_dir() or (root / ".gitlab-ci.yml").is_file()
    has_tests = any((root / d).is_dir() for d in ["tests", "test", "__tests__"]) or \
        any((root / f).is_file() for f in ["pytest.ini", "tox.ini", "jest.config.js"])
    screenshots: list[str] = []
    for img_dir in ["images", "screenshots", "docs/images", "assets", "res"]:
        p = root / img_dir
        if p.is_dir():
            try:
                for f in sorted(p.iterdir()):
                    if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                        screenshots.append(f"{img_dir}/{f.name}")
                        if len(screenshots) >= 6:
                            break
            except OSError:
                pass
    # 精簡檔案樹：頂層 + 一層子目錄
    tree: list[str] = []
    try:
        top = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for p in top[:40]:
            if p.name in IGNORE_DIRS or p.name.startswith(".git"):
                continue
            if p.is_dir():
                tree.append(f"{p.name}/")
                try:
                    for sub in sorted(p.iterdir(), key=lambda x: x.name.lower())[:8]:
                        tree.append(f"  {sub.name}{'/' if sub.is_dir() else ''}")
                except OSError:
                    pass
            else:
                if len(tree) < 60:
                    tree.append(p.name)
    except OSError:
        pass
    return {
        "has_docker": has_docker,
        "has_ci": bool(ci),
        "has_tests": has_tests,
        "screenshots": screenshots,
        "file_tree": tree,
    }


def guess_name_description(root: Path) -> tuple[str, str]:
    name = root.resolve().name.replace("_", "-").replace(" ", "-")
    description = ""
    # package.json
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(_read_text(pkg, 50_000) or "{}")
            if data.get("name"):
                name = str(data["name"])
            if data.get("description"):
                description = str(data["description"])
        except json.JSONDecodeError:
            pass
    # pyproject.toml
    py = root / "pyproject.toml"
    if py.is_file() and not description:
        text = _read_text(py, 30_000)
        m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', text)
        if m:
            name = m.group(1)
        m = re.search(r'description\s*=\s*["\']([^"\']+)["\']', text)
        if m:
            description = m.group(1)
    # 既有 README 第一行
    for rd in ["README.md", "README.MD", "readme.md"]:
        p = root / rd
        if p.is_file():
            for line in _read_text(p, 5_000).splitlines():
                line = line.strip()
                if line.startswith("# "):
                    if not description:
                        pass
                    break
            break
    return name, description


def scan(root: str | Path) -> dict:
    """掃描專案，回傳可 JSON 序列化的 ProjectInfo。"""
    r = Path(root).resolve()
    if not r.is_dir():
        raise FileNotFoundError(f"找不到目錄: {r}")
    name, description = guess_name_description(r)
    languages = detect_languages(r)
    frameworks = detect_frameworks(r)
    license_name = detect_license(r)
    entry = detect_entry_points(r)
    misc = detect_misc(r)
    primary = next(iter(languages), "")
    return {
        "path": str(r),
        "name": name,
        "description": description,
        "primary_language": primary,
        "languages": languages,
        "frameworks": frameworks,
        "license": license_name,
        "install_commands": entry["install"],
        "usage_commands": entry["usage"],
        "test_commands": entry["test"],
        **misc,
    }


if __name__ == "__main__":  # pragma: no cover
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(scan(target), ensure_ascii=False, indent=2))
