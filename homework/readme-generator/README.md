# readme-generator · 專案 README 產生器

> 掃描專案結構 → 3 分鐘互動問答 → 產出接案級高品質 README（含 0–100 品質評分）。
> 零第三方依賴，Python 3.9+ 離線可用。

![language: Python](https://img.shields.io/badge/language-Python-3776AB) ![license: MIT](https://img.shields.io/badge/license-MIT-green) ![readme: auto-generated](https://img.shields.io/badge/readme-auto-generated-8A2BE2)

本專案就是用自己產生的 README（見 `examples/`）。為什麼值得做，見 [`BUSINESS_MODEL.md`](BUSINESS_MODEL.md)。

## 🖼 效果（一鍵產出）

以本機 OpenGL 專案實測（C++ 59%、ImGui/GLFW/GLM），一鍵產出作品集模板，評分 **100/100**：

- 自動偵測語言分佈、框架、安裝/啟動指令、截圖（`images/`）
- 自動徽章（shields.io）、目錄、專案結構樹
- 作品集模板自帶「專案亮點（給業主看）」：為什麼選我 / 量化成果 / 接案範圍

完整範例：[`examples/README.opengl-demo.md`](examples/README.opengl-demo.md)

## ✨ 功能特色

- ✅ **自動掃描**：語言佔比、框架（Python/JS/C++/Go/Rust…）、Docker/CI/測試、授權、截圖、精簡檔案樹
- ✅ **4 種模板**：`library` 開源函式庫 / `portfolio` 接案作品集 / `course` 課程專題 / `saas` 商業產品
- ✅ **3 種語言**：`zh` 中文 / `en` 英文 / `bilingual` 中英雙語
- ✅ **品質評分 `check`**：8 項檢查 + 改進建議，不再猜 README 缺什麼
- ✅ **兩種用法**：`init` 互動精靈（新手） / `build` 非互動（CI/老手）
- ✅ **安全設計**：預設不覆寫 `README.md`（需 `--force`），先輸出 `README.generated.md` 確認

## 📦 安裝

### 前置需求

- Git
- Python 3.9+

### 安裝步驟

```bash
git clone <your-repo-url>
cd readme-generator
pip install -e .
# 或免安裝：PYTHONPATH=src python -m readme_gen ...
```

## 🚀 快速開始

```bash
# 1. 只掃描（看看能偵測到什麼）
$ PYTHONPATH=src python -m readme_gen scan /path/to/your-project --json

# 2. 互動式產生（推薦第一次用）
$ PYTHONPATH=src python -m readme_gen init /path/to/your-project -o README.generated.md

# 3. 一鍵非互動產生（適合 CI / 已想好參數）
$ PYTHONPATH=src python -m readme_gen build /path/to/your-project -o README.generated.md --template portfolio --lang zh --name "我的專案" --features "功能A;功能B"

# 4. 為既有 README 打分
$ PYTHONPATH=src python -m readme_gen check --file README.md
```

安裝後（`pip install -e .`）可直接用短指令 `readme-gen` 取代 `PYTHONPATH=src python -m readme_gen`。

## 🛠 技術棧

- **語言**：Python（標準函式庫 only，零依賴）
- **框架**：無（argparse + pathlib + json + re）
- **DevOps**：Docker — / CI —

## 📁 專案結構

```text
src/readme_gen/
  __init__.py
  __main__.py
  scanner.py       # 掃描語言/框架/指令/授權/截圖
  badges.py        # shields.io 徽章
  templates.py     # 4 模板 × 2 語系文案
  generator.py     # 組裝 Markdown + check 評分
  cli.py           # scan/init/build/check
tests/
  test_generator.py
examples/
  README.opengl-demo.md   # 真實 OpenGL 專案產出範例
```

## ✅ 測試

```bash
$ python -m pytest readme-generator/tests -v
```

5 項測試：掃描準確度、多模板×多語系、評分高低分邊界。

## 💡 專案亮點（給業主看）

- 🏆 **為什麼選我**：文件完整度直接影響成交率；本工具把「寫文件」從 2 小時壓到 3 分鐘，且輸出結構固定、可審查
- 📈 **量化成果**：實測 OpenGL 專案（~10 種語言混合、無 README）→ 100/100 分 README，2300+ 字元，含截圖與啟動指令
- 🧾 **接案範圍**：需求訪談 → 開發 → 文件 → 保固 n 個月；文件部分可用本工具標準化交付

## 📬 聯絡 / 接案資訊

- Your Name / your@email.com / 作品集連結

## 📄 授權

MIT

---
*本 README 由 [readme-generator](https://example.com) 自動產生，可再手動潤飾。*
