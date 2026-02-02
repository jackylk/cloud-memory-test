# Zeabur 部署完整指南

## 🚀 快速部署（修复后的版本）

### 步骤 1: 准备部署文件

在项目根目录运行：

```bash
cd web
./prepare_deploy.sh
```

这会将测试报告复制到 `web/reports/` 目录。

### 步骤 2: 提交代码到 Git

```bash
# 回到项目根目录
cd ..

# 添加所有变更
git add .

# 提交
git commit -m "Add web application with Dockerfile for Zeabur deployment"

# 推送到远程仓库
git push
```

### 步骤 3: 在 Zeabur 部署

#### 方式 A: 使用 Dockerfile（推荐）

1. 登录 [Zeabur Dashboard](https://dash.zeabur.com)
2. 选择你的项目
3. 点击 "Add Service" → "Git"
4. 选择你的仓库
5. **重要配置**:
   - **Root Directory**: 设置为 `web`
   - **Build Method**: Zeabur 会自动检测到 Dockerfile
6. 点击 "Deploy"

#### 方式 B: 使用 Buildpack（备选）

如果 Dockerfile 部署失败，可以尝试：

1. 删除 `web/Dockerfile`（临时）
2. Zeabur 会使用 Python Buildpack
3. 确保 `web/zbpack.json` 配置正确
4. 重新部署

### 步骤 4: 配置环境变量（可选）

在 Zeabur 控制台的服务设置中：

- `PORT`: 自动设置，无需手动配置
- `FLASK_ENV`: 设置为 `production`（可选）

### 步骤 5: 访问应用

部署成功后：
1. 在 Zeabur 控制台找到服务的 URL
2. 例如：`https://your-app.zeabur.app`
3. 访问即可查看报告

## 🔧 问题排查

### 问题 1: 编译 pydantic-core 失败

**症状**: 构建日志显示 "Failed building wheel for pydantic-core"

**原因**: 项目根目录的 requirements.txt 包含需要编译的包

**解决方案**: ✅ 已通过以下方式修复：
1. 使用 Dockerfile 明确指定构建步骤
2. 只安装 `web/requirements.txt` 中的依赖
3. 使用 Python 3.11（更好的二进制包支持）

### 问题 2: 找不到报告文件

**症状**: 网站显示"暂无报告"

**原因**: 报告文件未包含在构建中

**解决方案**:
1. 运行 `./prepare_deploy.sh` 复制报告到 `web/reports/`
2. 提交并推送更改
3. 重新部署

### 问题 3: 端口配置错误

**症状**: 应用启动失败或无法访问

**解决方案**:
- Dockerfile 中使用 `${PORT:-5000}` 自动读取 Zeabur 的端口
- 无需手动配置

## 📁 项目结构说明

```
cloud-memory-test/
├── web/                    # ← Zeabur 部署的根目录
│   ├── Dockerfile         # Docker 构建配置
│   ├── requirements.txt   # Web 应用依赖（精简）
│   ├── app.py            # Flask 应用
│   ├── templates/        # HTML 模板
│   ├── static/           # CSS/JS 静态文件
│   ├── reports/          # 测试报告（部署时）
│   ├── prepare_deploy.sh # 部署准备脚本
│   └── zbpack.json       # Buildpack 配置（备用）
├── docs/
│   └── test-reports/     # 测试报告（开发时）
└── requirements.txt      # 测试框架依赖（不用于部署）
```

## ✅ 验证部署成功

访问以下 URL 验证：

1. **首页**: `https://your-app.zeabur.app/`
   - 应该看到两个卡片：知识库和记忆系统

2. **健康检查**: `https://your-app.zeabur.app/health`
   - 应该返回：`{"status": "ok", "service": "cloud-memory-test-reports"}`

3. **知识库报告**: `https://your-app.zeabur.app/kb`
   - 应该跳转到最新的知识库报告

4. **记忆系统报告**: `https://your-app.zeabur.app/memory`
   - 应该跳转到最新的记忆系统报告

## 🔄 更新报告

当生成新报告后：

```bash
cd web
./prepare_deploy.sh
cd ..
git add web/reports/
git commit -m "Update test reports"
git push
```

Zeabur 会自动重新部署（如果启用了自动部署）。

## 🎯 关键配置文件

### 1. Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY templates ./templates
COPY static ./static
RUN mkdir -p reports
COPY --chown=root:root reports ./reports || true
EXPOSE 5000
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120
```

### 2. web/requirements.txt

```txt
Flask==3.0.0
gunicorn==21.2.0
```

**注意**: 只包含 Web 应用必需的依赖，不包含测试框架的依赖。

### 3. .zeabur/config.yaml（可选）

```yaml
services:
  - name: web
    path: web
    build:
      dockerfile: Dockerfile
```

## 💰 成本说明

Zeabur 免费套餐：
- 每月免费额度
- 轻量级应用（如本项目）通常在免费额度内
- 详见：https://zeabur.com/pricing

## 📞 获取帮助

如果遇到问题：

1. 查看 Zeabur 控制台的 Build Logs
2. 查看 Runtime Logs
3. 参考 Zeabur 文档：https://zeabur.com/docs
4. 在项目 GitHub 提 issue

## ✨ 部署成功后

恭喜！你的测试报告网站已经上线了！

接下来可以：
1. 🔗 绑定自定义域名
2. 📊 查看访问统计
3. 🔄 配置 CI/CD 自动部署
4. 📈 监控应用性能

---

最后更新：2026-02-02
