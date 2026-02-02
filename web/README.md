# 云端记忆与知识库性能测试报告网站

这是一个简洁的 Web 应用，用于展示云端记忆系统和知识库的性能测试报告。

## 功能特点

- 📊 展示知识库和记忆系统测试报告
- 📈 按时间排序，最新报告优先
- 🎨 现代化响应式设计
- 🚀 轻量级 Flask 应用，易于部署

## 本地运行

### 1. 安装依赖

```bash
cd web
pip install -r requirements.txt
```

### 2. 启动应用

```bash
python app.py
```

应用将在 http://localhost:5000 启动。

## 部署到 Zeabur

### 方法一：通过 Git 部署（推荐）

1. **将代码推送到 Git 仓库**

```bash
# 在项目根目录
git add web/
git commit -m "Add web application for test reports"
git push
```

2. **在 Zeabur 创建项目**
   - 访问 [Zeabur Dashboard](https://dash.zeabur.com)
   - 点击 "Create Project"
   - 选择 "Deploy from Git"
   - 选择你的 Git 仓库
   - 选择 `web` 目录作为根目录

3. **配置部署**
   - Zeabur 会自动检测到这是 Python/Flask 应用
   - 会自动使用 `requirements.txt` 安装依赖
   - 会使用 `Procfile` 或 `zbpack.json` 中的启动命令

4. **访问应用**
   - 部署完成后，Zeabur 会提供一个公开访问的 URL
   - 例如：`https://your-app.zeabur.app`

### 方法二：通过 Zeabur CLI 部署

1. **安装 Zeabur CLI**

```bash
npm install -g @zeabur/cli
```

2. **登录 Zeabur**

```bash
zeabur login
```

3. **部署应用**

```bash
cd web
zeabur deploy
```

### 环境变量配置（可选）

在 Zeabur 控制台可以设置以下环境变量：

- `PORT`: 应用监听端口（Zeabur 会自动设置）
- `FLASK_ENV`: 设置为 `production`（生产环境）

## 项目结构

```
web/
├── app.py              # Flask 应用主文件
├── requirements.txt    # Python 依赖
├── Procfile           # Gunicorn 启动配置
├── zbpack.json        # Zeabur 配置
├── templates/         # HTML 模板
│   ├── index.html           # 首页
│   ├── kb_reports.html      # 知识库报告列表
│   └── memory_reports.html  # 记忆系统报告列表
└── static/            # 静态资源
    └── css/
        └── style.css  # 样式文件
```

## 自动更新报告

当你运行测试并生成新报告后：

1. 报告会自动保存到 `docs/test-reports/` 目录
2. Web 应用会自动读取最新报告
3. 无需重启应用，刷新页面即可看到新报告

## 路由说明

- `/` - 首页，显示最新报告和统计信息
- `/kb` - 知识库报告列表
- `/memory` - 记忆系统报告列表
- `/report/<filename>` - 查看具体报告详情
- `/health` - 健康检查接口

## 技术栈

- **后端**: Flask 3.0
- **Web服务器**: Gunicorn
- **前端**: HTML5 + CSS3（无需构建）
- **部署平台**: Zeabur

## 维护建议

1. **定期清理旧报告**: 定期删除过时的测试报告以节省存储空间
2. **监控应用**: 使用 Zeabur 的监控功能查看应用运行状态
3. **日志查看**: 在 Zeabur 控制台查看应用日志

## 许可证

与主项目保持一致
