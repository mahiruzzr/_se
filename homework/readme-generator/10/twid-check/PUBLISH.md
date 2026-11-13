# 發佈步驟 (Publish checklist)

## 0. 發佈前先改這些
- `Your Name` / `you@example.com` → 你自己的（pyproject.toml、package.json、Cargo.toml、LICENSE）
- `YOUR_GITHUB_NAME` → 你的 GitHub 帳號（建議先把整個專案推上 GitHub）
- 套件名稱 `twid-check`：2026-11-13 查詢時三個平台都尚未被使用，但隨時可能被佔走；想改名就三個地方一起改
- 版本號發佈後**不能覆蓋**，要更新只能升版號（0.1.1、0.2.0 …）

## 1. Python → PyPI
```bash
cd python
pip install build twine
python -m build                      # 產生 dist/*.whl 與 dist/*.tar.gz
twine upload --repository testpypi dist/*   # 建議先上 TestPyPI 試跑 (test.pypi.org 另外註冊)
twine upload dist/*                  # username: __token__ ; password: pypi-xxxx (API token)
```
註冊 https://pypi.org → 開啟 2FA → Account settings → Add API token。

## 2. Node.js → npm
```bash
cd node
npm test
npm pack --dry-run                   # 確認打包內容只有 5 個檔案
npm login
npm publish
```
註冊 https://www.npmjs.com → 開啟 2FA。

## 3. Rust → crates.io
```bash
cd rust
cargo test
cargo publish --dry-run
cargo login                          # 貼上 https://crates.io/settings/tokens 產生的 token
cargo publish
```
用 GitHub 帳號登入 crates.io，並在 Account Settings 驗證 email（沒驗證不能發佈）。
