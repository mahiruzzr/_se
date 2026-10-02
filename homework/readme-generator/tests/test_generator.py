"""核心測試：掃描 + 產生 + 評分。零第三方依賴，用 pytest 或 python 直接跑皆可。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from readme_gen.generator import check_readme, generate
from readme_gen.scanner import scan


def make_fake_project() -> Path:
    d = Path(tempfile.mkdtemp(prefix="demo-proj-"))
    (d / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (d / "requirements.txt").write_text("fastapi\npytest\n", encoding="utf-8")
    (d / "tests").mkdir(exist_ok=True)
    (d / "tests" / "test_x.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (d / "images").mkdir(exist_ok=True)
    (d / "images" / "demo.png").write_bytes(b"\x89PNG fake")
    return d


def test_scan_detects_python_and_fastapi():
    info = scan(make_fake_project())
    assert info["primary_language"] == "Python", info
    assert "FastAPI" in info["frameworks"], info
    assert info["has_tests"] is True
    assert info["screenshots"] == ["images/demo.png"]
    assert any("pip install" in c for c in info["install_commands"])


def test_generate_library_zh_contains_sections():
    info = scan(make_fake_project())
    md = generate(info, {"name": "demo", "description": "測試專案", "features": ["A 功能;B 功能"] if False else ["A 功能", "B 功能"]},
                  template="library", lang="zh")
    for needle in ["# demo", "功能特色", "安裝", "快速開始", "專案結構", "授權"]:
        assert needle in md, f"缺少 {needle}"


def test_generate_all_templates_and_langs():
    info = scan(make_fake_project())
    for tpl in ["library", "portfolio", "course", "saas"]:
        for lang in ["zh", "en", "bilingual"]:
            md = generate(info, {"name": "demo"}, template=tpl, lang=lang)
            assert len(md) > 500, (tpl, lang)


def test_check_scores_good_readme_high():
    info = scan(make_fake_project())
    md = generate(info, {"name": "demo", "description": "完整專案"}, template="library", lang="zh")
    result = check_readme(md)
    assert result["score"] >= 80, result


def test_check_scores_empty_readme_low():
    result = check_readme("# hi\n")
    assert result["score"] < 40
    assert len(result["suggestions"]) > 0
