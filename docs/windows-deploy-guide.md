# 新电脑（Windows）Docker 一键部署指南

> 在全新 Windows 电脑上跑起 HF-Micro-ERP（jshERP 二次开发版），并恢复现有业务数据。

***

## 一、整体流程

```
安装 Docker Desktop  →  安装 Git  →  克隆项目  →  一键启动  →  恢复数据库  →  浏览器访问
```

> 本指南所有命令建议在 **Git Bash**（安装 Git 时自带）里执行，避免 PowerShell 的重定向差异问题。

***

## 二、安装 Docker Desktop

1. 下载安装包：https://www.docker.com/products/docker-desktop/
2. 运行安装，默认选项即可（会自动启用 **WSL2** 后端）
3. 安装完重启电脑，启动 Docker Desktop
4. 等任务栏鲸鱼图标变绿（表示引擎已就绪）

验证安装：

```bash
docker --version
docker compose version
# 快速自检（首次会拉一个测试镜像）
docker run --rm hello-world
```

> 提示：Docker Desktop 免费即可，个人使用无需付费订阅。

***

## 三、安装 Git for Windows

1. 下载：https://git-scm.com/download/win
2. 安装时注意关键一步 —— **Configuring the line ending conversions** 选择：

   ```
   Checkout as-is, commit Unix-style line endings
   ```

   这会让 `core.autocrlf=input`，与仓库（Linux 下开发、LF 换行）保持一致，避免 git 把整个文件都标成已修改。

3. 其余选项保持默认，一路下一步

验证：

```bash
git --version
```

***

## 四、克隆项目并配置 Git

先配置身份（换成你自己的 GitHub 用户名/邮箱）：

```bash
git config --global user.name "你的GitHub用户名"
git config --global user.email "你的GitHub邮箱"
git config --global init.defaultBranch dev
git config --global core.autocrlf input
```

克隆项目：

```bash
git clone https://github.com/AlphaDogLab/HF-Micro-ERP.git
cd HF-Micro-ERP
git checkout dev
```

> GitHub 认证（token 需 `Contents: Read and write` 权限）配置详见 [git-env-setup.md](git-env-setup.md)。

***

## 五、启动系统（首次会构建镜像）

```bash
cd HF-Micro-ERP
docker compose up -d --build
```

说明：

- 首次启动会拉取基础镜像 + 用 Maven/npm 编译后端和前端，**耗时较长（视网络约 10~30 分钟）**，属正常现象
- 构建完成后自动启动 4 个容器：`jsh-mysql`、`jsh-redis`、`jsh-backend`、`jsh-frontend`
- MySQL 首次启动会执行 `jshERP-boot/docs/jsh_erp.sql` 初始化脚本，需再等约 30 秒

查看启动状态：

```bash
docker compose ps
# 期望 4 个容器都是 Up/healthy
```

查看后端日志（确认启动完成）：

```bash
docker compose logs -f backend
# 看到 "Started ... Application" 或端口监听即成功，Ctrl+C 退出日志
```

***

## 六、恢复数据库（把现有业务数据导回来）

> 首次启动的数据库是「原始初始化数据」，需要再导入我们在旧机器上备份的数据，才有你的商品/库存/单据。

1. 先把备份文件复制到新电脑，放到 `HF-Micro-ERP` 目录下（任意方式：scp / WinSCP / 网盘等）。旧机器上备份文件位置：

   ```
   /opt/backup/jsh_erp_20260817_191432.sql
   ```

   scp 示例（在 Git Bash 执行，替换成服务器 IP）：

   ```bash
   scp root@<服务器IP>:/opt/backup/jsh_erp_20260817_191432.sql .
   ```

2. 等 MySQL 健康后，在 `HF-Micro-ERP` 目录执行恢复：

   ```bash
   docker exec -i jsh-mysql mysql -uroot -p123456 jsh_erp < jsh_erp_20260817_191432.sql
   ```

   > 命令里的 `-p123456` 是 MySQL 密码，会在命令行显示一条「password on the command line」警告，可忽略。
   > 若提示 `ERROR 1045`，说明容器还没初始化完成，等一会儿再执行。

***

## 七、访问系统

| 入口 | 地址 |
| --- | --- |
| 前端页面 | http://localhost:3000 |
| 后端接口文档 | http://localhost:9999/jshERP-boot/doc.html |

系统默认登录账号：`jsh` / `123456`

***

## 八、日常命令

```bash
cd HF-Micro-ERP

# 停止
docker compose down

# 启动（镜像已存在时，无需再 --build）
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f backend
docker compose logs -f frontend

# 重启单个服务
docker compose restart backend
```

***

## 九、常见问题

### 1. 端口被占用

系统占用 4 个端口：`3000`、`9999`、`3307`、`6380`。启动报错 `port is already allocated` 时检查：

```bash
netstat -ano | findstr :3000
netstat -ano | findstr :9999
netstat -ano | findstr :3307
netstat -ano | findstr :6380
```

找到占用进程的 PID 后，到任务管理器结束该进程，或改 `docker-compose.yml` 里的外部端口。

### 2. Docker Desktop 引擎未启动

报错 `Cannot connect to the Docker daemon`：先打开 Docker Desktop，等图标变绿再执行命令。

### 3. 首次构建失败/超时

多为网络问题。确认能正常访问外网；若在国内网络慢，可重试几次。镜像源已内置阿里云 Maven 镜像和 npmmirror 源，无需额外配置。

### 4. git 把所有文件都标成已修改

换行符没配对。执行：

```bash
git config --global core.autocrlf input
```

然后重新 clone 一次即可。

### 5. 恢复数据库后前端仍显示旧数据

后端有 Redis 缓存，恢复数据库后重启一下后端即可：

```bash
docker compose restart backend
```
