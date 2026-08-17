# 新电脑 Git 环境配置指南

> 适用于 HF-Micro-ERP（jshERP 二次开发）项目，从零配置到可以正常 clone / pull / push。

***

## 一、仓库信息

| 项目 | 值 |
| --- | --- |
| 远程仓库 | `https://github.com/AlphaDogLab/HF-Micro-ERP.git` |
| 默认分支 | `dev` |
| 主要分支 | `dev`（开发主线，含全部定制改动）、`master`（原版基线）、`feat/batch-list`（历史特性分支） |
| 认证方式 | HTTPS + Personal Access Token（推荐）/ SSH Key |

> 提示：本仓库已包含完整历史（约 3800+ 提交）和 v1.0 ~ v3.6 标签。

***

## 二、安装 Git

### Windows

方式一（推荐，官网安装包）：

1. 打开 https://git-scm.com/download/win 下载安装包
2. 一路下一步，建议勾选「Add a Git Bash Profile to Windows Terminal」
3. 安装完成打开 **Git Bash** 执行后续命令

方式二（命令行，需已装 winget 或 choco）：

```bash
winget install --id Git.Git -e --source winget
```

### macOS

```bash
# 未装 Homebrew 先装：https://brew.sh
brew install git
```

或安装 Xcode Command Line Tools：

```bash
xcode-select --install
```

### Linux（Ubuntu/Debian）

```bash
sudo apt update && sudo apt install -y git
```

### 验证安装

```bash
git --version
# 期望输出形如：git version 2.4x.x
```

***

## 三、初始化全局配置

> 注意：当前旧机器的提交身份是自动生成的 `root@Cgy.localdomain`，新电脑请务必配置成你自己的身份。

```bash
git config --global user.name "你的GitHub用户名"
git config --global user.email "你的GitHub邮箱"
```

推荐再补充两项：

```bash
# 新仓库默认分支统一为 dev
git config --global init.defaultBranch dev

# 换行符：Windows 上拉取自动转 CRLF、提交转回 LF，避免全文件误判为改动
git config --global core.autocrlf input   # macOS/Linux
# git config --global core.autocrlf true  # Windows
```

查看当前配置：

```bash
git config --global --list
```

***

## 四、配置 GitHub 认证（三选一）

### 方式 A：HTTPS + Personal Access Token（推荐，最快）

#### 1. 生成 Token

1. 打开 GitHub → 右上角头像 → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
2. **Repository access** 选 `Only select repositories`，选中 `AlphaDogLab/HF-Micro-ERP`
3. **Permissions → Repository permissions → Contents** 设为 **Read and write**
4. 设置有效期（建议 7~90 天）→ 生成并复制 token（形如 `github_pat_...`）

> 关键：Contents 必须是 **Read and write**，否则只能拉不能推（会报 `403 Permission denied`）。

#### 2. 配置凭据缓存

让 git 记住 token，避免每次都要输。

Windows（Git Credential Manager，安装 Git 时自带）：

```bash
git config --global credential.helper manager
```

macOS（钥匙串）：

```bash
git config --global credential.helper osxkeychain
```

Linux（明文存储，注意文件权限）：

```bash
git config --global credential.helper store
printf 'https://你的GitHub用户名:你的token@github.com\n' > ~/.git-credentials
chmod 600 ~/.git-credentials
```

#### 3. 首次触发认证

第一次 clone 或 push 时输入一次 token 作为密码，之后会被记住。

### 方式 B：SSH Key（更安全，一次配置长期免密）

```bash
# 1. 生成密钥（一路回车即可，建议加 -C 备注邮箱）
ssh-keygen -t ed25519 -C "你的GitHub邮箱"

# 2. 复制公钥
cat ~/.ssh/id_ed25519.pub
```

3. 打开 GitHub → Settings → **SSH and GPG keys** → **New SSH key**，粘贴公钥
4. 用 SSH 协议克隆：

```bash
git clone git@github.com:AlphaDogLab/HF-Micro-ERP.git
```

### 方式 C：GitHub CLI（最省心，交互式登录）

```bash
# 安装 gh（详见 https://cli.github.com）
gh auth login
# 按提示选择 GitHub.com → HTTPS → Login with a web browser，浏览器授权即可
```

登录后 git 会自动复用 `gh` 的凭据，无需手配 token。

***

## 五、克隆并切换到 dev 分支

```bash
git clone https://github.com/AlphaDogLab/HF-Micro-ERP.git
cd HF-Micro-ERP
```

clone 完成后默认就在 `dev` 分支（仓库默认分支）。如需要可显式确认：

```bash
git checkout dev
git pull
```

***

## 六、验证配置

依次执行以下命令，确认环境正常：

```bash
# 1. 远程地址
git remote -v
# 期望：origin  https://github.com/AlphaDogLab/HF-Micro-ERP.git

# 2. 当前分支及跟踪关系
git branch -vv
# 期望：* dev  xxxxx [origin/dev] ...

# 3. 最近提交
git log --oneline -5
```

能正常看到提交记录即说明认证 + 克隆都成功。

***

## 七、日常工作流

```bash
# 拉取最新代码
git pull

# 查看状态
git status

# 提交改动
git add <文件或目录>
git commit -m "说明"

# 推送到远程
git push
```

建议提交信息遵循项目现有风格（`feat:` / `fix:` / `docs:` + 中文简述），例如：

```
feat: 新增xxx功能
fix: 修复xxx问题
docs: 更新xxx文档
```

***

## 八、常见问题

### 1. push 报 `403 Permission denied`

**原因**：token 的 `Contents` 权限是只读，或 Repository access 没选到该仓库。

**解决**：回到 GitHub Fine-grained tokens → 编辑该 token → 把 Contents 改为 `Read and write`，Repository access 选 `AlphaDogLab/HF-Micro-ERP`。

### 2. push 报 `did not receive expected object` / `unpack failed`

**原因**：本地是浅克隆（`--depth` 拉取），历史不完整。

**解决**：补全完整历史后再推：

```bash
git fetch --unshallow origin
git push
```

### 3. 提示 `fatal: Authentication failed`

**原因**：token 过期或被吊销，或密码栏填了 GitHub 登录密码（GitHub 已禁用密码）。

**解决**：重新生成 token，并用 token 作为密码（不是 GitHub 账号密码）。

### 4. Windows 下 `git diff` 显示整个文件都被改动

**原因**：换行符 CRLF/LF 不一致。

**解决**：

```bash
git config --global core.autocrlf true
```

### 5. 需要走代理才能访问 GitHub

```bash
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 取消代理
git config --global --unset http.proxy
git config --global --unset https.proxy
```
