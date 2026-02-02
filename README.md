# 云端Agent知识库和记忆系统性能测试框架

## 部署选项

### Railway 部署（推荐）

**方式一：通过 Dashboard（最简单）**
1. 访问 https://railway.app 并登录
2. 点击 "New Project" > "Deploy from GitHub repo"
3. 选择此仓库
4. Railway 会自动检测配置并部署
5. 等待构建完成，访问生成的 URL

**方式二：使用一键脚本**
```bash
cd web
./deploy_railway.sh
```

**方式三：使用 CLI 手动部署**
```bash
# 安装 Railway CLI
npm install -g @railway/cli
# 或使用 Homebrew (macOS)
brew install railway

# 登录
railway login

# 初始化项目
railway init

# 部署
railway up

# 查看日志
railway logs

# 打开应用
railway open
```

详细说明请查看：[web/RAILWAY_DEPLOY.md](web/RAILWAY_DEPLOY.md)

### Zeabur 部署

详细说明请查看：[web/ZEABUR_DEPLOY.md](web/ZEABUR_DEPLOY.md)

## 本地开发

```bash
# 进入 web 目录
cd web

# 安装依赖
pip install -r requirements.txt

# 运行应用
python app.py

# 访问
open http://localhost:5000
```

## 项目结构

详见 [CLAUDE.md](CLAUDE.md)
