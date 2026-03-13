# 🎬 TgtoDrive (TTD) | 网盘资源自动化管理助手（原名Tgto123）

<p align="center">
  <a href="https://hub.docker.com/r/walkingd/tgto123">
    <img src="https://img.shields.io/docker/pulls/walkingd/tgto123?style=flat-square&logo=docker&label=Docker%20Pulls" alt="Docker Pulls">
  </a>
  <img src="https://img.shields.io/badge/Python-3.13%2B-blue?style=flat-square&logo=python" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey?style=flat-square" alt="Platform">
</p>

<p align="center">
<strong>一条龙网盘媒体自动化平台：从找资源、自动转存、智能整理、挂载 STRM、到 Emby 302 直链播放，全流程打通；重点强化 115 / 123 云盘整理、115 / 123 STRM 全量与增量生成、以及 Emby 反向代理 302 播放能力。本软件完全免费，后续也不会收费，如果这个项目对你有帮助，请点击右上角 ⭐ Star 支持一下！</strong>
</p>

---

## 如有使用疑问，可加交流群：[https://t.me/TgtoDriveChat](https://t.me/TgtoDriveChat)

## ✨ 核心定位：找资源 → 转存 → 整理 → 挂 STRM → Emby 播放

你可以把它理解成一个“网盘媒体库自动化流水线”：

1. **找资源**：通过 Telegram 频道监控、榜单订阅、关键词白名单、Pansou、Nullbr、RevoHD、影巢等入口发现资源。
2. **转存资源**：自动把 123 / 115 / 天翼 / 夸克 / 影巢 / 分享链接资源转存到目标网盘目录。
3. **智能整理**：对 115 与 123 网盘里的影视资源自动识别、分类、重命名、洗版。
4. **挂载 STRM**：对 115 与 123 目录生成 STRM，并支持全量扫描、整理后增量同步、元数据下载与失效清理。
5. **Emby 播放**：通过 Emby 反向代理劫持播放请求改写为 302 网盘直链，实现更轻的播放链路。

---

## 🚀 重点功能总览

### 1. 📦 115 / 123 网盘整理功能是核心主线能力

项目当前最值得强调的能力，不是“单点转存”，而是 **115 与 123 的影视库自动整理**：

* **TMDB 自动识别刮削**：根据文件名自动匹配影视元数据，减少手工整理成本。
* **主分类自动归档**：电影 / 剧集 / 动漫 / 纪录片 / 综艺 自动归类。
* **地区二级归类**：支持把五大类继续按 国产 / 欧美 / 日韩 / 其他 二次分流。
* **命名标准化**：支持统一重命名规则，提升后续 Emby / Jellyfin / Plex 识别成功率。
* **洗版覆盖策略**：可按剧集“杜比优先”或“非杜比优先”，“大文件优先”或“小文件优先”自动洗版，减少重复资源。
* **115 / 123 双平台覆盖**：不是只有 123，也不是只有 115，而是两套整理链路都已打通。

一句话总结：**把“转存来的资源”自动变成“像样的影视库”。**

### 2. 🎞️ 115 / 123 STRM 全量 + 增量生成能力

项目第二条主线能力，是 **115 / 123 双平台 STRM 输出能力**：

* **123 STRM 全量生成**：按目录扫描批量生成 `.strm`，strm采用fileid类型，疾速请求直链。
* **115 STRM 全量生成**：与 123 同样支持整库扫描输出，strm采用pickcode类型，疾速请求直链。
* **整理后自动增量同步**：整理完成后，只对本轮实际变化目录做增量 STRM 更新。
* **元数据增量下载**：字幕、封面、NFO、音频等元数据可一起同步到 STRM 目录。
* **失效 STRM / 空目录清理**：自动维护 STRM 目录整洁度。
* **目录级去重与脏标记重试**：同目录不会重复并发；更新过程中若再次变更会自动重新入队。

也就是说，项目不是“能生成 STRM”这么简单，而是已经形成了：

**整理 → 增量检测 → STRM 更新 → 元数据同步 → 清理失效项** 的闭环。

### 3. 🎬 Emby 反向代理 + 302 直链播放

项目第三条主线能力，是 **Emby 反向代理直链播放**：

* 在 Web 管理页内置 **Emby反代** 配置页，支持多实例卡片式管理。
* 自动劫持 Emby 的播放请求。
* 把播放请求改写为网盘真实播放地址。
* 结合strm疾速请求直链，返回 **302 跳转直链**，而不是继续让本地服务做重流量代理。
* 失败时会做严格回退与剔除失效播放源，避免播放器乱选错误地址。

这个能力真正解决的是：

**资源明明在网盘里，但 Emby 客户端如何尽量轻量、尽量稳定地直接播放。**

### 4. 🤖 找资源与自动转存能力

为了把上面的“整理 + STRM + Emby”链路喂满，项目还提供了一整套前置资源入口：

* **Telegram 频道监控**：支持 123 / 115 / 天翼 / 影巢频道自动监听与转存。
* **榜单订阅**：支持豆瓣榜单、猫眼榜单自动参与转存判断。
* **关键词白名单 / 黑名单 / 二次分类规则**：对转存触发条件进行精细控制。
* **123 分享链接增量监控**：自动转存新增文件。
* **影巢 / HDHive 深度集成**：支持影巢频道、影巢链接转存与积分阈值控制。
* **万能转发**：对私有频道消息也能通过用户侧复制转发方式触发处理。

### 5. ⚡ 搜索、秒传、离线，补足整条资源链路

为了把“找资源 → 转存入库”做完整，项目还补齐了很多高频工具：

* **多源搜索**：
  * `/share 关键词`：搜索 123 网盘并生成分享链接
  * `/pansou 关键词`：搜索 Pansou 聚合资源
  * `/revohd 关键词`：搜索清影论坛资源
  * `/hdhive 关键词`：搜索影巢资源
* **跨盘秒传**：115 → 123、天翼 → 123、夸克 → 123 等。
* **本地文件秒传**：支持 PT 本地文件扫描后尝试秒传至 123 / 115。
* **多协议离线下载**：Magnet / ed2k / Torrent 自动提交到 123 或 115。
* **短视频下载**：Bilibili / 抖音视频下载。

### 6. 🧰 管理与运维能力

除了资源主链路，本项目也提供了完整的运维辅助能力：

* **全局设置页面**：统一管理代理、全局 TMDB Key、频道监控轮询节奏。
* **关键词白名单可视化配置**：通过卡片式 UI 管理 TMDB 搜索规则、自定义正则和最终表达式预览。
* **Web SSH 终端**：在浏览器里直接连接远程机器。
* **Emby 海报缺失自动检测与刷新**。
* **日志中心 / 监控历史 / 整理历史**。
* **企业微信通知、资源社区发帖、服务器联通性检测**。

---

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
  tgtodrive-service:
    image: walkingd/tgto123:latest
    container_name: TgtoDrive
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
      # [推荐] B站、抖音等视频下载保存路径
      - ./downloads:/app/downloads
      # [可选] PT下载目录映射：左侧填NAS本地路径，右侧固定为 /app/upload
      # 用于实现本地文件秒传到网盘，不需要可去掉
      - /vol3/1000/Video/MoviePilot/transfer:/app/upload
      # STRM输出目录：用于保存 /app/strm 下生成内容,/vol1/1000/Emby/strm 改成你的目录
      - /vol1/1000/Emby/strm:/app/strm

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
  * 新增功能配置：WebSSH、Emby海报刷新、Emby反代、STRM同步等设置。

---

## ❓ 常见问题 (Troubleshooting)

<details>
<summary><strong>Q: 为什么部分功能无法使用？</strong></summary>

请务必检查是否已在 Web 后台 (`http://IP:12366`) 完成了对应网盘的账号配置和目录设置。**大部分高级功能依赖于 Web 页面的配置。**

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
