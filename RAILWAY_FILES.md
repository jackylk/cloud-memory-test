# Railway 部署文件清单

## 已创建的文件

本次为 Railway 部署创建/修改了以下文件：

### 配置文件

1. **railway.toml** (项目根目录)
   - Railway 主配置文件
   - 定义构建和部署参数
   - 指定 Dockerfile 路径和健康检查

2. **railway.json** (项目根目录)
   - Railway JSON 格式配置（可选）
   - 与 railway.toml 功能相同

3. **web/railway.toml** (web 目录)
   - web 服务专用配置（可选）

### 文档

4. **web/RAILWAY_DEPLOY.md**
   - 完整的 Railway 部署指南
   - 包含三种部署方式
   - 详细的配置说明和故障排查

5. **web/RAILWAY_QUICKSTART.md**
   - 快速开始指南
   - 3 步完成部署
   - 常用命令和验证方法

6. **web/COMPARISON.md**
   - Railway vs Zeabur 详细对比
   - 帮助你了解两个平台的区别
   - 迁移建议和成本预估

7. **README.md** (项目根目录)
   - 更新了部署选项说明
   - 包含 Railway 和 Zeabur 的快速入口

### 脚本

8. **web/deploy_railway.sh**
   - 一键部署脚本
   - 自动检查环境和登录状态
   - 引导式部署流程

9. **web/test_railway_deploy.sh**
   - 部署前测试脚本
   - 检查所有必需文件
   - 验证 Docker 构建

### CI/CD

10. **.github/workflows/railway-deploy.yml**
    - GitHub Actions 自动部署配置
    - 监听 web 目录变更
    - 自动部署到 Railway

### 已修改的文件

11. **web/Procfile**
    - 更新了 gunicorn 启动命令
    - 添加了 workers 和 timeout 参数

## 文件结构

```
cloud-memory-test/
├── railway.toml              # Railway 主配置（推荐）
├── railway.json              # Railway JSON 配置（可选）
├── README.md                 # 项目说明（已更新）
├── .github/
│   └── workflows/
│       └── railway-deploy.yml  # 自动部署配置
└── web/
    ├── railway.toml          # Web 服务配置（可选）
    ├── Dockerfile            # 容器配置（已存在，无需修改）
    ├── Procfile              # 启动命令（已修改）
    ├── requirements.txt      # Python 依赖（已存在）
    ├── app.py                # Flask 应用（已存在）
    ├── deploy_railway.sh     # 一键部署脚本（新）
    ├── test_railway_deploy.sh # 测试脚本（新）
    ├── RAILWAY_DEPLOY.md     # 完整部署指南（新）
    ├── RAILWAY_QUICKSTART.md # 快速开始（新）
    └── COMPARISON.md         # 平台对比（新）
```

## 使用哪些文件？

### 最简单的方式（Dashboard 部署）

只需要：
- `railway.toml` 或 `railway.json`（任选一个）
- 现有的 `Dockerfile`、`app.py`、`requirements.txt`

Railway 会自动检测和使用这些文件。

### 使用 CLI 部署

运行：
```bash
cd web
./deploy_railway.sh
```

这个脚本会处理一切。

### 使用 GitHub Actions 自动部署

1. 在 Railway Dashboard 获取 Token
2. 在 GitHub 仓库添加 `RAILWAY_TOKEN` secret
3. 推送代码，自动触发部署

## 配置文件优先级

Railway 按以下优先级读取配置：

1. **railway.toml** (如果存在)
2. **railway.json** (如果 toml 不存在)
3. **Dockerfile** (自动检测)
4. **Procfile** (备用)

**建议**: 使用 `railway.toml`（项目根目录的那个），其他作为备份。

## 下一步行动

### 步骤 1: 测试本地配置（可选）

```bash
cd web
./test_railway_deploy.sh
```

### 步骤 2: 选择部署方式

**选项 A: Dashboard 部署（推荐新手）**
1. 访问 https://railway.app
2. 连接 GitHub 仓库
3. 等待自动部署

**选项 B: CLI 部署**
```bash
cd web
./deploy_railway.sh
```

**选项 C: GitHub Actions（推荐团队）**
1. 获取 Railway Token
2. 添加 GitHub Secret
3. 推送代码

### 步骤 3: 验证部署

访问以下 URL：
- `https://your-app.up.railway.app/` - 首页
- `https://your-app.up.railway.app/health` - 健康检查
- `https://your-app.up.railway.app/kb` - 知识库报告
- `https://your-app.up.railway.app/memory` - 记忆报告

## 保留 Zeabur 配置？

**建议保留**，原因：
1. 作为备份方案
2. 测试不同平台性能
3. 迁移时可以平滑过渡

已保留的 Zeabur 文件：
- `.zeabur/config.yaml`
- `web/zbpack.json`
- `web/ZEABUR_DEPLOY.md`

## 清理不需要的文件（可选）

如果确定只使用 Railway，可以删除：
```bash
# 删除 Zeabur 配置
rm -rf .zeabur
rm web/zbpack.json

# 删除多余的配置文件（保留一个即可）
rm railway.json  # 如果使用 railway.toml
# 或
rm railway.toml  # 如果使用 railway.json
```

**建议**: 先测试 Railway 成功后再清理。

## 需要帮助？

- **Railway 部署问题**: 查看 `web/RAILWAY_DEPLOY.md`
- **快速开始**: 查看 `web/RAILWAY_QUICKSTART.md`
- **平台对比**: 查看 `web/COMPARISON.md`
- **运行脚本**: 查看 `web/deploy_railway.sh` 注释

## 总结

所有 Railway 部署文件已准备就绪！你现在可以：

1. ✅ 通过 Dashboard 部署（最简单）
2. ✅ 使用一键脚本部署
3. ✅ 手动使用 CLI 部署
4. ✅ 通过 GitHub Actions 自动部署

选择任一方式开始部署！
