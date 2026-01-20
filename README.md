---

# 🎬 tgto123 (TG-Cloud-Sync) | 网盘资源自动化管理助手

<p align="center">
  <a href="https://hub.docker.com/r/walkingd/tgto123">
    <img src="https://img.shields.io/docker/pulls/walkingd/tgto123?style=flat-square&logo=docker&label=Docker%20Pulls" alt="Docker Pulls">
  </a>
  <img src="https://img.shields.io/badge/Python-3.13%2B-blue?style=flat-square&logo=python" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey?style=flat-square" alt="Platform">
</p>

<p align="center">
<strong>全能型网盘助手：支持 Telegram 频道监控、多网盘（123/115/天翼/夸克）自动转存、影巢/清影资源搜索、磁力/ed2k离线、PT本地文件秒传及直链播放。</strong>
</p>

---

## ✨ 核心功能

### 🤖 自动化与监控

* **全能频道监控**：实时监控 Telegram 频道（如 [115网盘资源收藏](https://t.me/oneonefivewpfx)），支持 **123、115、天翼云盘** 资源的自动捕获。
* **增量更新监控**：支持对指定的 **123网盘分享链接** 进行监控，自动转存新增的文件（需在 Web 端配置）。
* **影巢/HDHive 深度集成**：
* 支持直接转发 **影巢 (HDHive)** 频道消息进行转存。
* 支持监控 **影巢 115 频道**（*注：可开通影巢长期 Premium VIP 获得免积分解锁*）。



### 🛠️ 交互与转存工具

* **万能一键转存**：
* **基础支持**：123 / 115 / 天翼云盘 / 夸克网盘 链接直接转发。
* **跨盘黑科技**：
* **夸克 -> 123**：转发夸克链接，自动生成秒传转存至 123。
* **天翼 -> 123**：使用指令 `/189to123`，将天翼资源秒传至 123。




* **多协议离线下载**：
* **磁力链 (Magnet)**：发送给机器人，自动提交至 123 离线列表。
* **电驴 (ed2k)**：发送给机器人，自动提交至 115 离线列表。


* **秒传神器**：支持转发 `JSON` 文件或发送秒传链接，支持 **PT本地文件** 扫描并无限尝试秒传至 123/115（防运营商制裁）。

### 🔍 搜索与社区

* **双向搜索**：
* `/share 关键词`：搜索 123网盘内容并生成分享链接。
* `/revohd 关键词`：搜索 **清影论坛 (RevoHD)** 资源。


* **一键发帖**：生成的分享链接可一键发布至 123 资源社区。

### ⚡ 媒体服务

* **直链播放**：内置 Web Server，访问 `http://IP:12366/d/path` 获取 123 文件直链。
* **弹幕自动挂载**：支持 `misaka_danmu_server`，触发 302 播放时自动下载对应集及下一集的弹幕。

---

## 🐳 Docker 快速部署 (推荐)

### 1. 准备工作

* 安装 Docker 20.10+ & Docker Compose 2.0+。
* **网络环境**：容器需要能访问 Telegram API（建议配置 HTTP 代理）。

### 2. 创建配置文件

在项目目录下创建 `docker-compose.yml`：

```yaml
version: '3'

services:
  tgto123-service:
    image: walkingd/tgto123:latest
    container_name: tgto123
    network_mode: host  # 推荐 host 模式以简化端口映射和直链访问
    environment:
      # --- 基础配置 ---
      - TZ=Asia/Shanghai
      # 必填：WEB管理页面的登录账号密码
      - ENV_WEB_PASSPORT=admin
      - ENV_WEB_PASSWORD=password
      
      # --- Telegram配置 ---
      # 必填：从 @BotFather 获取
      - ENV_TG_BOT_TOKEN=your_bot_token
      # 必填：从 @userinfobot 获取管理员ID
      - ENV_TG_ADMIN_USER_ID=123456789
      
      # --- 网络代理配置 (可选) ---
      # 若本机已开启全局透明代理，则无需配置以下三项
      # Clash用户通常填 http://127.0.0.1:7890
      - HTTP_PROXY=http://127.0.0.1:7890
      - HTTPS_PROXY=http://127.0.0.1:7890
      - NO_PROXY=localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8,123pan.com,115.com,189.cn,quark.cn

    volumes:
      # 数据库与日志持久化
      - ./db:/app/db
      # [可选] B站、抖音等视频下载保存路径
      - ./downloads:/app/downloads
      # [可选] PT下载目录映射：左侧填NAS本地路径，右侧固定为 /app/upload
      # 用于实现本地文件秒传到网盘，不需要可去掉
      - /vol3/1000/Video/MoviePilot/transfer:/app/upload
      
    restart: always

```

### 3. 启动服务

```bash
docker-compose pull  # 拉取最新镜像
docker-compose up -d # 后台启动

```

### 4. ⚠️ 关键步骤：Web端初始化配置

容器启动后，**必须** 访问 Web 管理页面进行详细配置，否则大部分功能无法使用。

* **访问地址**: `http://你的NAS_IP:12366` (例如 `http://192.168.1.5:12366`)
* **配置内容**:
* 填写网盘 Cookie/Token。
* 配置监控频道（支持 123/115/天翼/影巢 等）。
* 配置增量监控的分享链接。



---

## 💻 使用指南

### 🤖 Telegram 机器人指令与操作

| 分类 | 操作/指令 | 说明 |
| --- | --- | --- |
| **🔍 搜索** | `/share 关键词` | 搜索 **123网盘**，选择文件夹生成分享链接（支持一键发帖）。 |
|  | `/revohd 关键词` | 搜索 **清影论坛 (RevoHD)** 资源。 |
| **💾 转存** | 转发/发送链接 | 直接发送 **123 / 115 / 天翼 / 夸克 / 影巢(HDHive)** 的链接或频道消息，自动转存。 |
|  | `/189to123 <链接>` | 将 **天翼云盘** 分享链接通过秒传转存至 **123网盘**。 |
|  | 发送 `JSON` / `秒传链` | 解析并尝试秒传至 123网盘。 |
| **📥 离线** | 发送 `magnet:?xt=...` | **123网盘** 离线下载（直接发送磁力链）。 |
|  | 发送 `ed2k://...` | **115网盘** 离线下载（直接发送 ed2k 链接）。 |
| **⚙️ 其他** | `/start` | 查看当前版本号及系统状态。 |

### 📺 直链播放服务

该功能适合配合 Emby/Plex 或本地播放器（如 PotPlayer）使用。

* **URL 格式**: `http://NAS_IP:12366/d/<完整文件路径>`
* **示例**:
```
http://192.168.1.1:12366/d/123云盘/Video/电影/权力的游戏.mp4

```



### 📥 PT文件秒传 (防制裁模式)

如果你是 PT 玩家，想把 NAS 里的电影存到网盘但不想跑上传流量：

1. 在 Docker Compose 中映射下载目录到 `/app/upload`。
2. 程序会自动扫描该目录下的新文件。
3. 系统计算特征码，尝试在 123/115 网盘中进行“秒传”。

---

## ❓ 常见问题 (Troubleshooting)

<details>
<summary><strong>Q: 为什么部分功能无法使用？</strong></summary>

请务必检查是否已在 Web 后台 (`http://IP:12366`) 完成了对应网盘的账号配置和目录设置。**大部分高级功能依赖于 Web 页面的配置。**

</details>

<details>
<summary><strong>Q: 网页管理后台无法访问 (Port 12366)</strong></summary>

1. 检查防火墙是否放行 12366 端口。
2. 确认 `network_mode: host` 是否生效。

</details>

---

## ⚠️ 免责声明

* 本工具仅作为网盘文件管理的辅助工具，所有资源均来源于互联网公开分享。
* **开发者不存储、不分发任何受版权保护的文件。**
* 工具内置 AI 识别机制，会自动过滤非法违规内容的分享创建。
* 用户需自行承担因使用本工具下载、传播内容而产生的任何法律责任及数据风险。

---

<p align="center">
<strong>如果这个项目对你有帮助，请点击右上角 ⭐ Star 支持一下！</strong>
</p>
