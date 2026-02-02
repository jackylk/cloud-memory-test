# 部署到 Zeabur 详细指南

本指南将帮助你将测试报告网站部署到 Zeabur。

## 前置准备

1. **注册 Zeabur 账号**
   - 访问 https://zeabur.com
   - 使用 GitHub 账号登录

2. **准备 Git 仓库**
   - 确保代码已推送到 GitHub/GitLab/Gitee

## 部署步骤

### 步骤 1: 创建项目

1. 登录 [Zeabur Dashboard](https://dash.zeabur.com)
2. 点击右上角 **"Create Project"** 按钮
3. 输入项目名称，例如 "cloud-memory-test"
4. 选择部署区域（建议选择离你最近的区域）

### 步骤 2: 添加服务

1. 在项目页面，点击 **"Add Service"**
2. 选择 **"Git"**
3. 选择你的 Git 仓库（如果是首次使用，需要授权 Zeabur 访问）
4. 选择包含 `web/` 目录的仓库

### 步骤 3: 配置服务

1. **选择根目录**
   - 在服务设置中，找到 "Root Directory" 选项
   - 设置为 `web`（因为我们的应用在 web 目录下）

2. **自动检测**
   - Zeabur 会自动检测到这是 Python 应用
   - 会自动读取 `requirements.txt`
   - 会自动使用 `Procfile` 或 `zbpack.json` 中的启动命令

3. **环境变量（可选）**
   - 一般不需要额外配置
   - Zeabur 会自动设置 `PORT` 环境变量

### 步骤 4: 部署

1. 点击 **"Deploy"** 按钮
2. 等待部署完成（通常 2-5 分钟）
3. 查看部署日志，确认没有错误

### 步骤 5: 访问应用

1. 部署成功后，点击服务卡片
2. 找到 **"Domains"** 选项卡
3. Zeabur 会自动分配一个域名，例如：
   - `https://cloud-memory-test-xxx.zeabur.app`
4. 点击域名即可访问你的应用

### 步骤 6: 绑定自定义域名（可选）

如果你有自己的域名：

1. 在服务详情页，点击 **"Domains"**
2. 点击 **"Add Domain"**
3. 输入你的域名，例如 `reports.yourdomain.com`
4. 在你的 DNS 服务商处添加 CNAME 记录：
   ```
   Type: CNAME
   Name: reports
   Value: <Zeabur提供的CNAME值>
   ```
5. 等待 DNS 生效（通常 10-30 分钟）

## 目录结构要求

确保 Git 仓库中包含以下结构：

```
your-repo/
├── web/                    # ← Zeabur 部署的根目录
│   ├── app.py
│   ├── requirements.txt
│   ├── Procfile
│   ├── zbpack.json
│   ├── templates/
│   └── static/
└── docs/
    └── test-reports/       # 报告文件
```

## 更新报告文件

### 方法 1: 通过 Git 提交（推荐）

每次生成新报告后：

```bash
# 在项目根目录
git add docs/test-reports/
git commit -m "Add new test reports"
git push
```

Zeabur 会自动检测到更新并重新部署（如果启用了自动部署）。

### 方法 2: 手动触发部署

1. 在 Zeabur Dashboard 中找到你的服务
2. 点击 **"Redeploy"** 按钮
3. 等待部署完成

## 自动部署配置

启用自动部署后，每次 push 代码都会自动部署：

1. 在服务设置中找到 **"Git"** 选项卡
2. 启用 **"Auto Deploy"**
3. 选择要监听的分支（通常是 `main` 或 `master`）

## 监控和日志

### 查看日志

1. 在服务详情页，点击 **"Logs"** 选项卡
2. 可以查看实时日志和历史日志
3. 支持搜索和过滤

### 查看指标

1. 点击 **"Metrics"** 选项卡
2. 可以查看：
   - CPU 使用率
   - 内存使用率
   - 网络流量
   - 请求数量

## 常见问题

### 1. 部署失败

**检查日志**：在部署日志中查找错误信息

常见原因：
- `requirements.txt` 中的依赖版本问题
- Python 版本不兼容
- 路径配置错误

**解决方法**：
- 确认 `requirements.txt` 正确
- 检查 Root Directory 设置为 `web`
- 查看详细错误日志

### 2. 应用无法访问

**可能原因**：
- 应用未正确启动
- 端口配置问题

**检查**：
- 确认日志中有 "Running on http://0.0.0.0:PORT"
- 确认 `app.py` 中使用了 `os.environ.get('PORT', 5000)`

### 3. 找不到报告文件

**原因**：报告文件路径不正确

**解决**：
- 确认 `docs/test-reports/` 目录存在
- 确认报告文件已提交到 Git
- 检查 `app.py` 中的路径配置

### 4. 报告没有更新

**原因**：新报告未重新部署

**解决**：
- 提交新报告到 Git 并 push
- 手动触发 Redeploy
- 或等待自动部署（如果已启用）

## 成本说明

Zeabur 提供免费套餐：
- 每月一定额度的免费使用时间
- 超出部分按量计费
- 详见：https://zeabur.com/pricing

对于这个轻量级应用，免费套餐通常够用。

## 性能优化建议

1. **启用 CDN**（如果绑定了自定义域名）
2. **压缩静态资源**
3. **启用缓存**（在 Flask 中配置）
4. **定期清理旧报告**以减少存储空间

## 支持

- Zeabur 文档: https://zeabur.com/docs
- Zeabur Discord: https://discord.gg/zeabur
- GitHub Issues: 在你的仓库中创建 issue

## 下一步

部署成功后：
1. ✅ 测试所有页面功能
2. ✅ 验证报告是否正确显示
3. ✅ 配置自动部署（可选）
4. ✅ 绑定自定义域名（可选）
5. ✅ 设置监控告警（可选）

祝你部署顺利！🚀
