# Git 流程示範：分支、合併、Fork 與 Pull Request

本文件記錄如何在命令列與 GitHub 上完成四種常見操作：

1. 分支 (Branch)
2. 合併 (Merge)
3. Fork
4. Pull Request

這是 **Git Flow / Forking Workflow** 的混合做法：在母專案內用分支開發（Git Flow 的 develop 分支概念），外部協作者則透過 Fork + Pull Request 貢獻程式碼（Forking Workflow）。

---

## 專案連結

* 母專案：https://github.com/se-test-examples/git-examples/commits/main/
    * 分支：https://github.com/se-test-examples/git-examples/commits/developGitBranch
* 子專案 (Fork)：https://github.com/ccckmit/git-examples/commits/main/

---

## 1. 分支 (Branch)

在母專案本地建立並切換到新分支：

```bash
git remote -v                       # 確認遠端倉庫位置
git checkout -b developGitBranch    # 建立並切換到 developGitBranch 分支
git branch                          # 確認目前所在分支
```

## 2. 合併 (Merge)

在新分支上提交修改，推上 GitHub 後，再合併回 main：

```bash
git add *.md                        # 加入修改的檔案
git commit -m "add gitBranch.md"    # 提交到 developGitBranch
git push origin developGitBranch    # 推送分支到 GitHub

git checkout main                   # 切回 main
git merge developGitBranch          # 把 developGitBranch 合併進 main
git push origin main                # 推送合併後的 main
```

## 3. Fork

Fork 是在 **GitHub 網頁上** 的動作（無法用 git 指令完成）：

1. 打開母專案 https://github.com/se-test-examples/git-examples
2. 點右上角 **Fork** 按鈕
3. 選擇自己的帳號，GitHub 會複製一份到你的帳號下（即 `ccckmit/git-examples`）

接著把自己的 fork clone 下來開發：

```bash
git clone git@github.com:ccckmit/git-examples.git   # clone 自己的 fork
cd git-examples
git add .                                           # 加入修改
git commit -m "add ccckmitFork.md"                  # 提交
git push                                            # 推送到自己的 fork
```

## 4. Pull Request

Pull Request 也是在 **GitHub 網頁上** 的動作：

1. 推送到自己的 fork 後，打開 https://github.com/ccckmit/git-examples
2. GitHub 會出現 **Compare & pull request** 按鈕（或到 Pull requests 頁籤點 New pull request）
3. 設定 base repository 為母專案 `se-test-examples/git-examples` 的 `main`，head repository 為自己的 fork
4. 填寫標題與說明，點 **Create pull request**
5. 母專案擁有者審核後點 **Merge pull request**，即完成貢獻

---

## 這是哪個 Git 流程？

* **母專案內部**：採用 [Git Flow](https://www.ruanyifeng.com/blog/2015/12/git-workflow.html) 的概念 —— `main` 為穩定主幹，功能開發在 `developGitBranch` 等分支進行，完成後合併回 `main`。
* **外部協作**：採用 **Forking Workflow** —— 協作者 Fork 母專案、在自己的副本上開發、再透過 Pull Request 請求合併回母專案。

## 參考

1. [Git 工作流程 (阮一峰)](https://www.ruanyifeng.com/blog/2015/12/git-workflow.html)
2. [How does Git work? (ByteByteGo)](https://bytebytego.com/guides/how-does-git-work/)
