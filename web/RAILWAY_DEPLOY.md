# Railway 部署指南

## 前提条件

1. 注册 Railway 账号：https://railway.app
2. 安装 Railway CLI（可选）：
   ```bash
   npm install -g @railway/cli
   # 或使用 Homebrew (macOS)
   brew install railway
   ```

## 部署方式

### 方式一：通过 Railway Dashboard（推荐，最简单）

1. **登录 Railway Dashboard**
   - 访问 https://railway.app
   - 使用 GitHub 账号登录

2. **创建新项目**
   - 点击 "New Project"
   - 选择 "Deploy from GitHub repo"
   - 授权 Railway 访问你的 GitHub 仓库
   - 选择 `cloud-memory-test` 仓库

3. **配置部署设置**
   - Railway 会自动检测到 Dockerfile
   - 如果项目根目录有 `railway.toml` 或 `railway.json`，Railway 会自动使用
   - Railway 会自动分配一个公开 URL

4. **验证部署**
   - 等待构建完成（通常 2-5 分钟）
   - 点击生成的 URL 访问应用
   - 访问 `/health` 端点检查服务状态

### 方式二：通过 Railway CLI

1. **安装并登录 Railway CLI**
   ```bash
   # 安装 CLI
   npm install -g @railway/cli

   # 登录
   railway login
   ```

2. **初始化项目并部署**
   ```bash
   # 在项目根目录
   cd /path/to/cloud-memory-test

   # 初始化 Railway 项目
   railway init

   # 链接到 Railway 项目（如果已经创建）
   railway link

   # 部署
   railway up
   ```

3. **查看部署状态**
   ```bash
   # 查看日志
   railway logs

   # 查看服务状态
   railway status

   # 打开应用
   railway open
   ```

### 方式三：通过 GitHub Actions 自动部署

1. **在 Railway Dashboard 获取 Token**
   - 进入项目设置
   - 生成 Railway Token
   - 复制 Token

2. **在 GitHub 仓库设置 Secret**
   - 进入仓库 Settings > Secrets > Actions
   - 添加 `RAILWAY_TOKEN` secret

3. **创建 GitHub Actions 工作流**（已在下方配置）

## 配置文件说明

### railway.toml / railway.json
Railway 配置文件，定义构建和部署参数：
- **builder**: 使用 Dockerfile
- **dockerfilePath**: Dockerfile 路径
- **startCommand**: 启动命令
- **healthcheckPath**: 健康检查路径

### Dockerfile
已存在的 Dockerfile 无需修改，Railway 会自动使用。

## 环境变量

Railway 会自动设置 `PORT` 环境变量，应用会监听该端口。

如需添加其他环境变量：
```bash
# 通过 CLI
railway variables set KEY=VALUE

# 或在 Dashboard 的 Variables 页面添加
```

## 域名配置

### 使用 Railway 提供的域名
Railway 会自动生成一个域名，格式如：
- `https://your-app.up.railway.app`

### 使用自定义域名
1. 在 Railway Dashboard 进入项目设置
2. 点击 "Settings" > "Domains"
3. 添加自定义域名
4. 在你的 DNS 提供商处添加 CNAME 记录

## 常见问题

### 1. 构建失败
检查 Dockerfile 和依赖是否正确：
```bash
# 本地测试构建
cd web
docker build -t test-app .
docker run -p 5000:5000 -e PORT=5000 test-app
```

### 2. 应用无法访问
- 确认应用监听 `0.0.0.0:$PORT`
- 检查 Railway Dashboard 的日志
- 确认健康检查路径 `/health` 可访问

### 3. 查看日志
```bash
# 通过 CLI
railway logs

# 或在 Dashboard 的 Deployments 页面查看
```

### 4. 端口问题
确保应用使用环境变量 `PORT`：
```python
port = int(os.environ.get('PORT', 5000))
app.run(host='0.0.0.0', port=port)
```

## 费用

Railway 提供：
- **Developer Plan**: $5/月，包含 $5 使用额度
- **Hobby Plan**: $20/月，包含 $20 使用额度
- 超出部分按实际使用量计费

对于小型 Flask 应用，$5/月的额度通常足够。

## 监控和维护

### 查看部署状态
```bash
railway status
```

### 查看资源使用
在 Railway Dashboard 的 Metrics 页面查看：
- CPU 使用率
- 内存使用
- 网络流量

### 重启应用
```bash
railway restart
```

### 回滚到上一个版本
在 Dashboard 的 Deployments 页面点击 "Rollback"

## 与 Zeabur 的对比

| 特性 | Railway | Zeabur |
|------|---------|--------|
| 部署速度 | 快 | 快 |
| 配置复杂度 | 简单 | 简单 |
| 免费额度 | 无免费层 | 有免费层 |
| 定价 | $5/月起 | 更灵活 |
| GitHub 集成 | 优秀 | 良好 |
| CLI 工具 | 强大 | 良好 |
| 文档 | 详细 | 中文友好 |

## 下一步

1. 推送代码到 GitHub
2. 在 Railway Dashboard 创建项目并连接仓库
3. 等待自动部署完成
4. 访问生成的 URL 验证应用运行正常

## 参考资源

- Railway 官方文档：https://docs.railway.app
- Railway CLI 文档：https://docs.railway.app/develop/cli
- Railway 示例项目：https://railway.app/examples
