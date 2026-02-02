# Railway 部署快速开始

## 最快部署方式（3 步完成）

### 方式一：通过 Railway Dashboard（推荐，无需 CLI）

1. **访问 Railway**
   - 打开 https://railway.app
   - 使用 GitHub 账号登录

2. **创建项目并部署**
   - 点击 "New Project"
   - 选择 "Deploy from GitHub repo"
   - 选择 `cloud-memory-test` 仓库
   - Railway 会自动检测 `railway.toml` 和 `Dockerfile`
   - 等待构建完成（通常 2-5 分钟）

3. **访问应用**
   - Railway 会自动生成一个 URL，如：`https://xxx.up.railway.app`
   - 点击 URL 或在项目页面找到 "View Deployment"
   - 访问 `/health` 端点确认服务正常

### 方式二：使用一键部署脚本

```bash
# 1. 进入 web 目录
cd web

# 2. 运行部署前测试（可选）
./test_railway_deploy.sh

# 3. 运行部署脚本
./deploy_railway.sh
```

脚本会自动：
- 检查 Railway CLI 是否安装
- 提示登录（如果未登录）
- 初始化或链接项目
- 部署应用

### 方式三：手动使用 CLI

```bash
# 1. 安装 Railway CLI
npm install -g @railway/cli
# 或使用 Homebrew (macOS)
brew install railway

# 2. 登录
railway login

# 3. 初始化项目（首次部署）
railway init

# 4. 部署
railway up

# 5. 查看 URL
railway open
```

## 验证部署

部署成功后，访问以下端点：

- **首页**: `https://your-app.up.railway.app/`
- **健康检查**: `https://your-app.up.railway.app/health`
- **知识库报告**: `https://your-app.up.railway.app/kb`
- **记忆系统报告**: `https://your-app.up.railway.app/memory`

## 常用命令

```bash
# 查看日志
railway logs

# 查看实时日志
railway logs -f

# 查看部署状态
railway status

# 打开应用
railway open

# 查看环境变量
railway variables

# 设置环境变量
railway variables set KEY=VALUE

# 重启应用
railway restart

# 删除项目
railway down
```

## 配置说明

Railway 会读取以下配置文件：

1. **railway.toml**（项目根目录）
   - 定义构建和部署配置
   - 指定 Dockerfile 路径
   - 设置健康检查

2. **Dockerfile**（web 目录）
   - 定义容器镜像
   - 安装依赖
   - 配置启动命令

3. **Procfile**（web 目录）
   - 备用启动命令配置
   - Railway 会优先使用 Dockerfile

## 环境变量

Railway 自动提供以下环境变量：

- `PORT`: 应用监听的端口（自动分配）
- `RAILWAY_ENVIRONMENT`: 部署环境（production/staging）
- `RAILWAY_SERVICE_NAME`: 服务名称

如需添加自定义环境变量：

```bash
# 通过 CLI
railway variables set DB_URL=postgresql://...
railway variables set API_KEY=your-key

# 或在 Dashboard > Variables 页面添加
```

## 自定义域名

1. 在 Railway Dashboard 进入项目
2. 点击 "Settings" > "Domains"
3. 点击 "Add Domain"
4. 输入你的域名（如 `example.com`）
5. 在你的 DNS 提供商添加 CNAME 记录：
   ```
   CNAME @ your-app.up.railway.app
   ```
6. 等待 DNS 生效（通常几分钟）

## 监控和日志

### 查看实时日志
```bash
railway logs -f
```

### 在 Dashboard 查看
- **Deployments**: 部署历史和状态
- **Metrics**: CPU、内存、网络使用情况
- **Logs**: 实时和历史日志

### 设置告警
Railway Pro 计划支持告警，可以监控：
- CPU 使用率
- 内存使用
- 应用健康状态

## 故障排查

### 1. 构建失败

**检查 Dockerfile**:
```bash
cd web
docker build -t test-app .
```

**常见问题**:
- 依赖安装失败：检查 `requirements.txt`
- 路径问题：确认 Dockerfile 中的 COPY 路径正确

### 2. 应用无法访问

**检查日志**:
```bash
railway logs
```

**常见问题**:
- 端口配置：确保应用监听 `0.0.0.0:$PORT`
- 启动失败：检查 Python 版本和依赖

### 3. 健康检查失败

**测试本地**:
```bash
cd web
python app.py
curl http://localhost:5000/health
```

**检查**:
- `/health` 端点是否存在
- 返回的 HTTP 状态码是否为 200

### 4. 查看详细错误

```bash
# 查看最近 100 行日志
railway logs --limit 100

# 查看特定部署的日志
railway logs --deployment <deployment-id>
```

## 回滚到上一个版本

如果新部署出现问题：

1. 在 Dashboard > Deployments 找到之前的成功部署
2. 点击 "Redeploy"
3. 或使用 CLI：
   ```bash
   railway rollback
   ```

## 成本控制

### Developer Plan ($5/月)

对于你的应用，预估使用量：
- CPU: 0.5 vCPU × 730 小时 = ~$2
- Memory: 512MB × 730 小时 = ~$1
- Network: 5GB = ~$1
- **总计**: ~$4/月（在 $5 额度内）

### 优化建议

1. **减少 workers**:
   ```toml
   # railway.toml
   startCommand = "gunicorn app:app --workers 1 ..."
   ```

2. **减少超时**:
   ```toml
   startCommand = "gunicorn app:app --timeout 60 ..."
   ```

3. **使用 Railway Sleep**:
   - 低流量应用会自动进入睡眠模式
   - 收到请求时自动唤醒

## 下一步

- [ ] 部署应用到 Railway
- [ ] 验证所有端点正常工作
- [ ] 配置自定义域名（可选）
- [ ] 设置环境变量（如需要）
- [ ] 配置 GitHub Actions 自动部署
- [ ] 监控应用性能和成本

## 需要帮助？

- 📖 Railway 文档: https://docs.railway.app
- 💬 Railway Discord: https://discord.gg/railway
- 🐛 GitHub Issues: https://github.com/railwayapp/railway/issues
- 📧 Railway Support: help@railway.app
