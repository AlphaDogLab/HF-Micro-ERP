# 管伊佳ERP (jshERP) 部署运维手册

> 适用于深圳晶科芯/华富微电子元器件贸易场景的 Docker 化部署

***

## 一、系统架构

```
┌──────────────────────────────────────────────────────┐
│  Docker Compose                                      │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐ │
│  │ jsh-mysql│  │jsh-redis │  │jsh-backend│  │jsh-frontend│ │
│  │ MySQL 8  │  │Redis 6.2 │  │SpringBoot│  │ Vue+Nginx│
│  │ :3307    │  │   :6380  │  │  :9999   │  │  :3000  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────┘ │
└──────────────────────────────────────────────────────┘
```

***

## 二、端口与密码

| 服务     | 内部端口 | 外部端口     | 账号/密码         |
| ------ | ---- | -------- | ------------- |
| MySQL  | 3306 | **3307** | root / 123456 |
| Redis  | 6379 | **6380** | 密码: 1234abcd  |
| 后端 API | 9999 | **9999** | —             |
| 前端页面   | 3000 | **3000** | —             |

系统默认登录: `jsh` / `123456`

超管账号：admin / 123456

***

## 三、目录结构

```
/opt/jshERP/
├── docker-compose.yml          # 服务编排
├── Dockerfile.backend          # 后端 Docker 镜像 (Maven编译 + JRE运行)
├── Dockerfile.frontend         # 前端 Docker 镜像 (Node编译 + Nginx)
├── default.conf                # 前端 Nginx 配置
├── application-docker.yml      # 后端生产环境配置 (Docker网络)
├── mysql_data/                 # MySQL 数据持久化 (Volume)
├── upload/                     # 文件上传目录 (Volume)
├── export/                     # 文件导出目录 (Volume)
├── docs/                       # 项目文档
│   ├── deployment-guide.md     # 本文件
│   ├── dev-changelog.md        # 二次开发记录
│   └── field-mapping.md        # 字段对照表
├── docker-config/              # Docker 构建配置
│   └── settings.xml            # Maven 阿里云镜像加速
├── jshERP-boot/                # 后端源码
│   ├── pom.xml
│   ├── src/
│   └── docs/jsh_erp.sql        # 初始化数据库脚本
└── jshERP-web/                 # 前端源码
    ├── package.json
    └── src/
```

***

## 四、常用命令

### 启动服务

```bash
cd /opt/jshERP
docker compose up -d
```

### 停止服务

```bash
cd /opt/jshERP
docker compose down
```

### 查看运行状态

```bash
cd /opt/jshERP
docker compose ps
```

### 查看日志

```bash
# 所有服务
docker compose logs -f

# 只看后端
docker compose logs -f backend

# 只看前端
docker compose logs -f frontend
```

### 重启某个服务

```bash
docker compose restart backend
docker compose restart frontend
```

***

## 五、修改代码后重建镜像

### 只改前端

```bash
cd /opt/jshERP
DOCKER_BUILDKIT=0 docker build -f Dockerfile.frontend -t jsherp-frontend .
docker compose up -d frontend
```

### 只改后端 (Java源码)

```bash
cd /opt/jshERP
DOCKER_BUILDKIT=0 docker build -f Dockerfile.backend -t jsherp-backend .
docker compose up -d backend
```

### 前后端都改

```bash
cd /opt/jshERP
# 并行构建
DOCKER_BUILDKIT=0 docker build -f Dockerfile.frontend -t jsherp-frontend . &
DOCKER_BUILDKIT=0 docker build -f Dockerfile.backend -t jsherp-backend . &
wait
docker compose up -d
```

**注意**: `DOCKER_BUILDKIT=0` 必须加，因为当前环境 buildx 不可用。

***

## 六、数据库备份与恢复

### 备份

```bash
docker exec jsh-mysql mysqldump -uroot -p123456 jsh_erp > jsh_erp_backup_$(date +%Y%m%d).sql
```

### 恢复

```bash
docker exec -i jsh-mysql mysql -uroot -p123456 jsh_erp < jsh_erp_backup_20260101.sql
```

***

## 七、常见问题

### 1. 登录页报"未知异常"

**原因**: Alpine 容器缺少 AWT 字体库，验证码图片生成失败

**状态**: 已在 Dockerfile.backend 中修复，通过 `apk add fontconfig ttf-dejavu` + `-Djava.awt.headless=true`

### 2. MySQL 连接报 Public Key Retrieval

**原因**: MySQL 8 默认安全策略

**状态**: 已在 application-docker.yml 中配置 `allowPublicKeyRetrieval=true`

### 3. 后端构建太慢

**原因**: Maven 默认从中央仓库下载依赖

**解决**: 已在 Dockerfile.backend 中使用阿里云 Maven 镜像 (`docker-config/settings.xml`)

### 4. Nginx 502 Bad Gateway

**原因**: 后端未就绪或连接不上

**排查**:

```bash
docker compose logs backend --tail=50
curl http://localhost:9999/jshERP-boot/user/randomImage
```

### 5. 首次启动数据库初始化慢

MySQL 首次启动需要执行 `docs/jsh_erp.sql` 初始化脚本（约200+张表），需等待约30秒。

***

## 八、备份清单

| 项目   | 位置                                               | 备份建议     |
| ---- | ------------------------------------------------ | -------- |
| 数据库  | `jsh-mysql` 容器                                   | 每周全量备份   |
| 源码修改 | `/opt/jshERP/jshERP-boot/src/`、`jshERP-web/src/` | 推送到 Git  |
| 上传文件 | `/opt/jshERP/upload/`                            | 与数据库同步备份 |
| 配置文件 | `docker-compose.yml`, `application-docker.yml`   | 纳入版本管理   |

