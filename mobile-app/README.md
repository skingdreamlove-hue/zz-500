# 中证500量化信号 - 手机端部署指南

## 前置条件

- GitHub 账号
- Git 命令行工具

## 一、创建 GitHub 仓库

1. 在 GitHub 上创建一个**私有仓库**（推荐私有，因为会包含 Token）
2. 仓库名随意，例如 `zz500-mobile`

## 二、上传代码

```bash
cd mobile-app
git init
git add .
git commit -m "init: mobile app"
git remote add origin https://github.com/<你的用户名>/zz500-mobile.git
git push -u origin main
```

## 三、开启 GitHub Pages

1. 进入仓库 → Settings → Pages
2. Source 选择 `Deploy from a branch`
3. Branch 选择 `main`，目录选 `/ (root)`
4. 点击 Save
5. 等待 1-2 分钟，页面会显示访问地址：`https://<你的用户名>.github.io/zz500-mobile/`

## 四、配置更新数据功能

### 4.1 创建 GitHub Personal Access Token

1. 进入 GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. 点击 `Generate new token`
3. 设置：
   - Token name: `zz500-mobile-update`
   - Expiration: 选最长的（1年）
   - Repository access: Only select repositories → 选 `zz500-mobile`
   - Permissions → Repository permissions → Actions: `Read and write`
4. 生成后**复制 Token**（只显示一次）

### 4.2 在 index.html 中填入配置

打开 `index.html`，找到开头的两行：

```javascript
var GITHUB_REPO='';  // 填入: 你的用户名/仓库名
var GITHUB_TOKEN=''; // 填入: 上一步生成的 Token
```

改为：

```javascript
var GITHUB_REPO='你的用户名/zz500-mobile';
var GITHUB_TOKEN='github_xxxxxxxxxxxxxxxxxxxx';
```

### 4.3 提交配置

```bash
git add .
git commit -m "config: add github token"
git push
```

## 五、初始化数据

首次部署需要手动触发一次数据抓取：

1. 进入仓库 → Actions → Update Data
2. 点击 `Run workflow` → `Run workflow`
3. 等待约 30 秒完成
4. 刷新手机页面即可看到数据

## 六、手机使用

1. 手机浏览器打开：`https://<你的用户名>.github.io/zz500-mobile/`
2. 点击浏览器菜单 → "添加到主屏幕"
3. 之后从桌面图标打开，体验类似原生 App

### 更新数据

- 打开主页 → 点击"↻ 更新数据"按钮
- 系统会触发 GitHub Actions 抓取最新数据
- 约 30 秒后页面自动刷新显示最新数据

## 文件结构

```
mobile-app/
├── .github/workflows/
│   └── update-data.yml      # GitHub Actions 工作流
├── scripts/
│   └── fetch_data.py         # 数据抓取脚本
├── vendor/
│   └── papaparse.min.js      # CSV 解析库
├── index.html                # 主页（信号+复盘）
├── strategy-debug.html       # 策略调试
├── review.html               # 复盘
├── strategy-common.js        # 共享逻辑
├── manifest.json             # PWA 配置
├── sw.js                     # Service Worker
├── zz500_factors.csv         # 因子数据（自动生成）
├── zz500_full_data.csv       # 原始数据（自动生成）
└── signal.json               # 最新信号（自动生成）
```

## 注意事项

- Token 存储在前端 JS 中，私有仓库下风险可控。如果仓库改为公开，必须移除 Token
- GitHub Actions 每月免费 2000 分钟，每次更新约 1 分钟，足够日常使用
- GitHub Pages 有时需要 1-2 分钟才能更新静态文件，更新数据后如果没看到变化，稍等再刷新
