from operator import inv
from pickle import NONE
import requests
import os
import shutil
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import time
import sqlite3
from datetime import datetime, timedelta
from datetime import time as time_datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from p123client.client import P123Client, check_response
from urllib.parse import urlsplit, parse_qs
import re
import telebot
import threading
import schedule
import json
import logging
from logging.handlers import TimedRotatingFileHandler
from collections import defaultdict
from content_check import check_porn_content

# 设置httpx日志级别为WARNING，避免INFO级别的输出
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.getLogger("telebot").setLevel(logging.ERROR)
version = "6.6.4"  # 版本更新
newest_id = 47
# 加载.env文件中的环境变量
load_dotenv(dotenv_path="db/user.env",override=True)
load_dotenv(dotenv_path="sys.env",override=True)
# 1. 确保日志目录存在
log_dir = os.path.join("db", "log")
os.makedirs(log_dir, exist_ok=True)
class MsFormatter(logging.Formatter):
    # 重写时间格式化方法
    def formatTime(self, record, datefmt=None):
        # 将时间戳转换为包含毫秒的datetime对象
        dt = datetime.fromtimestamp(record.created)
        # 格式化到毫秒（取微秒的前3位）
        return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # 保留到毫秒
# 使用自定义的Formatter
formatter = MsFormatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S.%f'  # 这里可以正常使用%f了
)

root_logger = logging.getLogger()  # 获取根日志器
root_logger.setLevel(logging.INFO)  # 全局日志级别

if __name__ == "__mp_main__":
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "log.log"),
        when='D',          # 每天轮转
        interval=1,        # 间隔1天
        backupCount=3,     # 最多保留3天日志
        encoding='utf-8',
        atTime=time_datetime(0, 0, 1)
    )
    # 获取当前日期
    today = datetime.now().date()
    # 计算今天的atTime时间戳
    today_at_time = datetime.combine(today, file_handler.atTime).timestamp()
    # 当前时间戳
    now = datetime.now().timestamp()
    # 如果当前时间在今天的atTime之前，则首次轮转时间为今天atTime
    # 如果当前时间已过今天的atTime，则首次轮转时间为明天atTime
    if now < today_at_time:
        target_rollover = today_at_time
    else:
        target_rollover = datetime.combine(today + timedelta(days=1), file_handler.atTime).timestamp()
    # 强制修正下一次轮转时间
    file_handler.rolloverAt = target_rollover
    
if __name__ == "__main__":
    file_handler = logging.FileHandler(
                        filename=os.path.join(log_dir, "start-log.log"),
                        encoding='utf-8'
                    )
console_handler = logging.StreamHandler()

# 4. 定义全局日志格式（所有日志共用）
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
# 6. 将处理器添加到根日志器（关键：根日志器的配置会被所有子logger继承）
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)
# ----------------------
# 测试：任意模块的logger都会遵循全局配置
# ----------------------
# 示例1：当前模块的logger
logger = logging.getLogger(__name__)
import threading
import concurrent.futures
# 创建大小为1的线程池用于发送消息
reply_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=20)
# 安全地获取整数值，避免异常
def get_int_env(env_name, default_value=0):
    try:
        value = os.getenv(env_name, str(default_value))
        return int(value) if value else default_value
    except (ValueError, TypeError):
        reply_thread_pool.submit(send_message,f"[警告] 环境变量 {env_name} 值不是有效的整数，使用默认值 {default_value}")
        logger.warning(f"环境变量 {env_name} 值不是有效的整数，使用默认值 {default_value}")
        return default_value
CHANNEL_URL = os.getenv("ENV_TG_CHANNEL", "")

AUTO_MAKE_JSON = get_int_env("ENV_AUTO_MAKE_JSON", 1)

#TG BOT的token
TG_BOT_TOKEN = os.getenv("ENV_TG_BOT_TOKEN", "")
#TG 用户ID
TG_ADMIN_USER_ID = get_int_env("ENV_TG_ADMIN_USER_ID", 0)

#是否开启监控功能，1为开启，0为关闭
AUTHORIZATION = get_int_env("ENV_AUTHORIZATION", 0)
#123账号
CLIENT_ID = os.getenv("ENV_123_CLIENT_ID", "")
DIY_LINK_PWD = os.getenv("ENV_DIY_LINK_PWD", "")
#123密码
CLIENT_SECRET = os.getenv("ENV_123_CLIENT_SECRET", "")
FILTER = os.getenv("ENV_FILTER", "")
filter_pattern = re.compile(FILTER, re.IGNORECASE)
#需要转存的123目录ID
UPLOAD_TARGET_PID = get_int_env("ENV_123_UPLOAD_PID", 0)

UPLOAD_JSON_TARGET_PID = get_int_env("ENV_123_JSON_UPLOAD_PID", 0)
UPLOAD_LINK_TARGET_PID = get_int_env("ENV_123_LINK_UPLOAD_PID", UPLOAD_JSON_TARGET_PID)
USE_METHOD="🔍 使用方法：\n      1、创建分享请使用 /share 关键词 来搜索文件夹，例如：/share 权力的游戏\n      2、转存分享可直接把123、115、天翼链接转发至此，支持频道中带图片的那种分享\n      3、转存秒传json可直接把json转发至此\n      4、转存秒传链接可直接把秒传链接转发至此\n      5、123批量离线磁力链请直接把磁力链发送至此\n      6、创建完成分享链接后可一键发帖至123资源社区\n      7、123、115、天翼等频道监控转存在后台定时执行\n      8、PT上下载的本地文件无限尝试秒传123或115网盘，以避免运营商制裁，需要配置compose里的路径映射\n      9、访问 http://127.0.0.1:12366/d/file (例如 http://127.0.0.1:12366/d/权力的游戏.mp4) 即可获取123文件下载直链\n      10、支持misaka_danmu_server弹幕服务，当触发302播放时，会自动调用misaka_danmu_server API来下载对应集以及下一集的弹幕\n      11、支持123转存夸克分享（原理是从夸克分享生成秒传给123转存）\n⚠️ 注：以上功能的使用需要在 NasIP:12366（如192.168.1.1:12366）的配置页面完成功能配置"
# 数据库路径（保持不变）
DB_DIR = "db"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)
DATABASE_FILE = os.path.join(DB_DIR, "TG_monitor-123.db")
USER_STATE_DB = os.path.join(DB_DIR, "user_states.db")
CHECK_INTERVAL = get_int_env("ENV_CHECK_INTERVAL", 0)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
]
RETRY_TIMES = 3
TIMEOUT = 15

TOKENSHARE = os.getenv("TOKEN", "")
if TOKENSHARE:
    botshare = telebot.TeleBot(TOKENSHARE)
#TG 用户ID
    TARGET_CHAT_ID_SHARE = get_int_env("TARGET_CHAT_ID", 0)

from share import get_quality
import re
from urllib.parse import urlparse, parse_qs

def parse_share_url(share_url):
    """解析分享链接，提取ShareKey和提取码"""
    try:
        # 使用正则表达式匹配分享链接
        pattern = r'(https?://(?:[a-zA-Z0-9-]+\.)*123[a-zA-Z0-9-]*\.[a-z]{2,6}/s/([a-zA-Z0-9\-_]+))'
        match = re.search(pattern, share_url, re.IGNORECASE)

        if match:
            # 完整URL
            full_url = match.group(1)
            # ShareKey
            share_key = match.group(2)
            # 尝试从原始URL查询参数中获取提取码
            parsed = urlparse(share_url)
            query_params = parse_qs(parsed.query)
            share_pwd = query_params.get('pwd', [''])[0]
            return share_key, share_pwd

        logger.warning(f"无法解析分享链接: {share_url}")
        return '', ''
    except Exception as e:
        logger.error(f"解析分享链接失败: {str(e)}")
        return '', ''

def recursive_count_files(client: P123Client, parent_file_id, share_key, share_pwd):
    """递归获取分享中的文件并统计视频文件数量"""
    logger.info(f"开始递归获取分享中的文件数量，文件夹ID: {parent_file_id}")
    video_extensions = {'.mkv', '.ts', '.mp4', '.avi', '.rmvb', '.wmv', '.m2ts', '.mpg', '.flv', '.rm', '.mov', '.iso'}
    video_count = 0
    try:
        page = 1
        while True:
            resp = client.share_fs_list({
                "ShareKey": share_key,
                "SharePwd": share_pwd,
                "parentFileId": parent_file_id,
                "limit": 100,
                "Page": page
            })
            check_response(resp)
            data = resp["data"]

            if data and "InfoList" in data:
                for item in data["InfoList"]:
                    if item["Type"] == 1:  # 目录
                        # 递归计算子目录中的视频文件
                        video_count += recursive_count_files(client, item["FileId"], share_key, share_pwd)
                    else:  # 文件
                        # 检查是否为视频文件
                        ext = os.path.splitext(item["FileName"])[1].lower()
                        if ext in video_extensions:
                            video_count += 1
            
            # 检查是否为最后一页
            if not data or len(data.get("InfoList", [])) < 100:
                break            
            page += 1
    except Exception as e:
        logger.error(f"获取文件列表失败（父ID: {parent_file_id}）: {str(e)}")
        raise
    return video_count

def build_share_message(metadata, client, file_id, folder_name, file_name, share_info):
    # 使用元数据美化消息
    #logger.info(get_first_video_file(client, file_id))
    get_quality(file_name)

    poster_url = metadata.get('backdrop', '').strip('` ') or metadata.get('poster', '').strip('` ')
    # 内容类型判断 
    content_type = '📺 电视剧' if 'seasons' in metadata and 'episodes' in metadata else '🎬 电影' 
    # 构建标题行 
    share_message = f"{content_type}｜{metadata.get('title')} ({metadata.get('year')})\n\n" 
    # 评分 
    genres = metadata.get('genres', [])[0] if metadata.get('genres', []) else ''
    share_message += f"⭐️ 评分: {metadata.get('rating')} / 地区: {', '.join(metadata.get('countries', []))} / 类型: {genres[:15]}{'...' if len(genres) > 15 else ''}\n" 
    # 类型 
    #genres = ', '.join(metadata.get('genres', []))
    #share_message += f"📽️ 类型: {genres[:15]}{'...' if len(genres) > 15 else ''}\n" 
    # 地区 
    #share_message += f"🌍 地区: {', '.join(metadata.get('countries', []))}\n" 
    # 语言 
    # share_message += f"🗣 语言: {', '.join(metadata.get('languages', ['未知']))}\n" 
    # 导演 
    if metadata.get('director'): 
        share_message += f"🎬 导演: {metadata.get('director', '')[:10]}{'...' if len(metadata.get('director', '')) > 10 else ''}\n" 
    # 主演 
    share_message += f"👥 主演: {metadata.get('cast', '')[:10]}{'...' if len(metadata.get('cast', '')) > 10 else ''}\n" 
    # 集数（如适用） 
    if 'seasons' in metadata and 'episodes' in metadata: 
        share_message += f"📺 共{metadata.get('seasons')}季 ({metadata.get('episodes')}集)\n" 
    # 简介（使用blockquote） 
    # 从分享链接中解析ShareKey和提取码
    share_key, share_pwd = parse_share_url(share_info['url'])
    share_pwd = share_pwd or share_info.get('password','')  
    # 获取文件夹内文件列表
    files = get_directory_files(client, file_id, folder_name)
    logger.info(f"获取实际文件数量: {len(files)}")
    actual_video_count = recursive_count_files(client, file_id, share_key, share_pwd)
    logger.info(f"获取分享中的文件数量: {actual_video_count}")
    # 定义视频文件扩展名
    video_extensions = {'.mkv', '.ts', '.mp4', '.avi', '.rmvb', '.wmv', '.m2ts', '.mpg', '.flv', '.rm', '.mov', '.iso'}
    # 筛选视频文件
    video_files = []
    for file_info in files:
        filename = file_info["path"]
        ext = os.path.splitext(filename)[1].lower()
        if ext in video_extensions:
            video_files.append(file_info)
    
    if not video_files:
        file_info_text = f"📁 没有找到视频文件 | 实际视频数量: {actual_video_count}"
        file_info_text2 = f"📁 没有找到视频文件"
    else:
        total_files_count = len(video_files)
        total_size = sum(file_info["size"] for file_info in video_files)
        # 计算平均大小
        avg_size = total_size / total_files_count if total_files_count > 0 else 0
        # 格式化文件大小
        if total_size < 1024:
            size_str = f"{total_size} B"
        elif total_size < 1024 * 1024:
            size_str = f"{total_size / 1024:.2f} KB"
        elif total_size < 1024 * 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024):.2f} MB"
        elif total_size < 1024 * 1024 * 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024 * 1024):.2f} GB"
        else:
            size_str = f"{total_size / (1024 * 1024 * 1024 * 1024):.2f} TB"
        # 格式化平均大小
        if avg_size < 1024:
            avg_size_str = f"{avg_size:.2f} B"
        elif avg_size < 1024 * 1024:
            avg_size_str = f"{avg_size / 1024:.2f} KB"
        elif avg_size < 1024 * 1024 * 1024:
            avg_size_str = f"{avg_size / (1024 * 1024):.2f} MB"
        elif avg_size < 1024 * 1024 * 1024 * 1024:
            avg_size_str = f"{avg_size / (1024 * 1024 * 1024):.2f} GB"
        else:
            avg_size_str = f"{avg_size / (1024 * 1024 * 1024 * 1024):.2f} TB"
        file_info_text = f"🎬 视频数量: {total_files_count} | 总大小: {size_str} | 平均大小：{avg_size_str} | 实际视频数量: {actual_video_count} | 已和谐：{total_files_count-actual_video_count}"
        file_info_text2 = f"🎬 视频数量: {total_files_count} | 总大小: {size_str} | 平均大小：{avg_size_str}" 
    share_message2 = share_message
    share_message2 += f"\n📖 简介: <blockquote expandable=\"\">{metadata.get('plot')[:500]}{'...' if len(metadata.get('plot')) > 500 else ''}</blockquote>\n\n{file_info_text2}\n"
    share_message += f"\n📖 简介: <blockquote expandable=\"\">{metadata.get('plot')[:500]}{'...' if len(metadata.get('plot')) > 500 else ''}</blockquote>\n\n{file_info_text}\n" 
    quality = get_quality(get_first_video_file(client, file_id))
    if quality:
        share_message += f"🏷 视频质量: {quality}\n"
        share_message2 += f"🏷 视频质量: {quality}\n"
    share_message += f"🔗 链接: {share_info['url']}{'?pwd=' + share_info['password'] if share_info.get('password') else ''}\n" 
    #share_message += f"🔗 链接: <a href=\"{share_info['url']}{'?pwd=' + share_info['password'] if share_info.get('password') else ''}\" target=\"_blank\" rel=\"noopener\" onclick=\"return confirm('Open this link?\n\n'+this.href);\">查看链接</a>\n"
    share_message += f"🙋 来自tgto123自动创建的分享" 
    share_message2 += f"🙋 来自tgto123自动创建的分享" 
    return share_message, share_message2, poster_url, files

def get_directory_files(client: P123Client, directory_id, folder_name, current_path="", is_root=True):
    """
    获取目录下的所有文件（使用V2 API）
    directory_id: 目录ID
    folder_name: 文件夹名称
    current_path: 当前路径，用于构建完整的相对路径
    """
    # 对于根目录，commonPath就是folder_name
    # 对于子目录，current_path是相对于commonPath的路径
    if is_root:
        common_path = folder_name
        # 根目录的current_path为空
        current_path = ""
    else:
        common_path = current_path.split('/')[0] if current_path else folder_name

    # 构建当前相对于commonPath的路径
    # 对于根目录，relative_path为空
    # 对于子目录，relative_path是相对于commonPath的路径
    if is_root:
        relative_path = ""
    else:
        relative_path = f"{current_path}/{folder_name}" if current_path else folder_name
        # 移除开头可能的/
        relative_path = relative_path.lstrip('/')
    logger.info(f"获取目录内容 (ID: {directory_id}, commonPath: '{common_path}', 相对路径: '{relative_path}')")
    all_files = []
    OPEN_API_HOST = "https://open-api.123pan.com"
    API_PATHS = {
        'LIST_FILES_V2': '/api/v2/file/list'
    }
    retry_delay = 31  # 重试延迟秒数

    # 使用V2 API获取目录内容
    last_file_id = 0  # 初始值为0
    while True:
        url = f"{OPEN_API_HOST}{API_PATHS['LIST_FILES_V2']}"
        params = {
            "parentFileId": directory_id,
            "trashed": 0,  # 排除回收站文件
            "limit": 100,   # 最大不超过100
            "lastFileId": last_file_id
        }
        headers = {
            "Authorization": f"Bearer {client.token}",
            "Platform": "open_platform",
            "Content-Type": "application/json"
        }

        try:
            logger.info(f"请求目录列表: {url}, 参数: {params}")
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if not response:
                logger.error(f"获取目录列表失败")
                return all_files

            if response.status_code != 200:
                logger.error(f"获取目录列表失败: HTTP {response.status_code}")
                return all_files

            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"响应JSON解析失败: {str(e)}")
                logger.error(f"完整响应: {response.text}")
                return all_files

            if data.get("code") != 0:
                error_msg = data.get("message", "未知错误")
                
                # 如果是限流错误，等待后重试
                if "操作频繁" in error_msg or "限流" in error_msg:
                    logger.warning(f"API限流: {error_msg}, 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue
                
                logger.error(f"API错误: {error_msg}")
                return all_files

            # 处理当前页的文件
            for item in data["data"].get("fileList", []):
                # 排除回收站文件
                if item.get("trashed", 1) != 0:
                    continue
                
                # 构建文件相对路径
                item_path = item['filename']
                
                if item["type"] == 0:  # 文件
                    # 构建相对于commonPath的路径（使用/作为分隔符）
                    # 注意：不包含commonPath
                    if relative_path:
                        full_item_path = f"{relative_path}/{item_path}"
                    else:
                        full_item_path = item_path
                    # 确保使用/作为分隔符
                    full_item_path = full_item_path.replace('\\', '/')
                    file_info = {
                        "path": full_item_path,  # 存储相对于commonPath的路径
                        "etag": item["etag"],
                        "size": item["size"]
                    }
                    all_files.append(file_info)
                elif item["type"] == 1:  # 文件夹
                    # 递归获取子目录（添加延迟避免限流）
                    #time.sleep(0.05)  # 增加延迟
                    sub_files = get_directory_files(
                        client,
                        item["fileId"],
                        item['filename'],
                        relative_path,
                        False
                    )
                    all_files.extend(sub_files)

            # 检查是否有更多页面
            last_file_id = data["data"].get("lastFileId", -1)
            #time.sleep(0.05)
            if last_file_id == -1:
                break
                
        except Exception as e:
            logger.error(f"获取目录列表出错: {str(e)}")
            return all_files

    logger.info(f"找到 {len(all_files)} 个文件 (ID: {directory_id})")
    return all_files

# 全局变量（使用安全的方式初始化bot）
# 处理JSON文件转存

import time
# 创建锁对象确保文件依次转存
json_process_lock = threading.Lock()

# 跟踪上次发送消息的时间
last_send_time = 0
RETRY_DELAY = 60  # 重试等待时间（秒）
MAX_RETRIES = 30  # 最大重试次数
# 定义线程池中的发送函数
def send_message(text):
    send_retry_count = 0
    while send_retry_count < MAX_RETRIES:
        try:
            bot.send_message(TG_ADMIN_USER_ID, text)
            logger.info(f"消息 '{text.replace('\n', '').replace('\r', '')[:20]}...' ，已成功发送给用户 {TG_ADMIN_USER_ID}（第{send_retry_count+1}/{MAX_RETRIES}次尝试）")
            break
        except Exception as e:
            logger.error(f"发送回复失败，{RETRY_DELAY}秒后重发，消息：{text}，错误：{str(e)}")
            time.sleep(RETRY_DELAY)
            send_retry_count += 1

def send_message_with_id(chatid, text):
    send_retry_count = 0
    while send_retry_count < MAX_RETRIES:
        try:
            bot.send_message(chatid, text)
            logger.info(f"消息 '{text.replace('\n', '').replace('\r', '')[:20]}...' ，已成功发送给用户 {chatid}（第{send_retry_count+1}/{MAX_RETRIES}次尝试）")
            break
        except Exception as e:
            logger.error(f"发送回复失败，{RETRY_DELAY}秒后重发，消息：{text}，错误：{str(e)}")
            time.sleep(RETRY_DELAY)
            send_retry_count += 1

def send_reply(message, text):
    send_retry_count = 0
    while send_retry_count < MAX_RETRIES:
        try:
            bot.reply_to(message, text)
            logger.info(f"消息 '{text.replace('\n', '').replace('\r', '')[:20]}...' ，已成功发送给用户 {message.chat.id}（第{send_retry_count+1}/{MAX_RETRIES}次尝试）")
            break
        except Exception as e:
            logger.error(f"发送回复失败，{RETRY_DELAY}秒后重发，消息：{text}，错误：{str(e)}")
            time.sleep(RETRY_DELAY)
            send_retry_count += 1

def send_reply_delete(message, text):
    global last_send_time
    current_time = time.time()
    if current_time - last_send_time < 10:
        #logger.info(f"[节流] 10秒内已发送消息，忽略当前消息: {text}")
        return
    # 限制文本长度，保留开头和末尾的200字符
    max_length = 400
    if len(text) > max_length:
        text = text[:200] + '\n     ......\n' + text[-200:]  
    try:
        sent_message = bot.reply_to(message, text)
        # 更新上次发送时间
        last_send_time = current_time
        time.sleep(12)  # 等待10秒后删除消息
        bot.delete_message(chat_id=sent_message.chat.id, message_id=sent_message.message_id)
    except Exception as e:
        logger.error(f"发送回复失败: {str(e)}")
bot = telebot.TeleBot(TG_BOT_TOKEN)
from telebot.types import BotCommand
# 安全初始化TeleBot
while True and __name__ == "__mp_main__":
    try:
        bot = telebot.TeleBot(TG_BOT_TOKEN)
        # 定义命令菜单（包含/start和/share）
        commands = [
            BotCommand("start", "开始使用机器人"),
            BotCommand("share", "创建分享链接"),
            BotCommand("info", "打印当前账户的信息"),
            BotCommand("add", "添加123监控过滤词，发送/add可查看使用方法"),
            BotCommand("remove", "删除123监控过滤词，发送/remove可查看使用方法"),
            BotCommand("zhuli115", "115最新活动幸运5分钟自动助力，支持多个助力码，例如/zhuli115 AAAAAA BBBBBB CCCCCC")
        ]
        # 设置命令菜单
        bot.set_my_commands(commands)
        logger.info("已设置Bot命令菜单：/start, /share, /info, /add, /remove")
        logger.info("TeleBot初始化成功")
        break  # 初始化成功，退出循环
    except Exception as e:
        logger.error(f"由于网络等原因无法与TG Bot建立通信，30秒后重试...: {str(e)}")
        time.sleep(30)

# 初始化123客户端
def init_123_client(retry: bool = False) -> P123Client:
    import requests
    token_path = os.path.join(DB_DIR, "config.txt")
    token = None
    
    # 尝试加载持久化的token
    if os.path.exists(token_path):
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                token = f.read().strip()
            logger.info("已加载持久化token")
        except Exception as e:
            logger.warning(f"读取token文件失败：{e}，将重新获取")
    
    # 尝试使用token初始化客户端
    if token:
        while True:
            try:
                client = P123Client(token=token)
                res = client.user_info()  # 验证token有效性

                # 检查API返回结果是否表示token过期
                if res.get('code') != 0 or res.get('message') != "ok":
                    reply_thread_pool.submit(send_message, "123 token过期，将重新获取")
                    logger.info("检测到token过期，将重新获取")
                    if os.path.exists(token_path):
                        os.remove(token_path)
                    break
                else:
                    logger.info("123客户端初始化成功（使用持久化token）")
                    return client
            except Exception as e:
                if "token is expired" in str(e).lower() or (
                        hasattr(e, 'args') and "token is expired" in str(e.args).lower()):
                    logger.info("检测到token过期，将重新获取")
                    if os.path.exists(token_path):
                        os.remove(token_path)
                    break
                else:
                    logger.warning(f"token健康检查异常，稍后重试：{e}")
                    time.sleep(RETRY_DELAY)
                

    # 通过API接口获取新token
    try:

        # 使用新token初始化客户端
        client = P123Client(CLIENT_ID, CLIENT_SECRET)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(client.token)

        logger.info("123客户端初始化成功（使用新获取的token）")
        return client
    except Exception as e:
        if not retry:
            logger.error(f"获取token失败：{e}，尝试重试...")
            return init_123_client(retry=True)
        logger.error(f"获取token失败（已重试）：{e}")
        raise


# 数据库相关函数（保持不变）
def init_database():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.execute('''CREATE TABLE IF NOT EXISTS messages
                  (msg_id INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, date TEXT, message_url TEXT, target_url TEXT, 
                   transfer_status TEXT, transfer_time TEXT, transfer_result TEXT)''')
    conn.commit()
    conn.close()


def is_message_processed(message_url):
    """检查消息是否已处理（无论转存是否成功）"""
    conn = sqlite3.connect(DATABASE_FILE)
    result = conn.execute("SELECT 1 FROM messages WHERE message_url = ?",
                          (message_url,)).fetchone()
    conn.close()
    return result is not None


def save_message(message_id, date, message_url, target_url,
                 status="待转存", result="", transfer_time=None):
    conn = sqlite3.connect(DATABASE_FILE)
    try:
        conn.execute("INSERT INTO messages (id, date, message_url, target_url, transfer_status, transfer_time, transfer_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (message_id, date, message_url, target_url,
                      status, transfer_time or datetime.now().isoformat(), result))
        conn.commit()
        logger.info(f"已记录: {message_id} | {target_url} | 状态: {status}")
    except sqlite3.IntegrityError:
        conn.execute("UPDATE messages SET transfer_status=?, transfer_result=?, transfer_time=? WHERE id=?",
                     (status, result, transfer_time or datetime.now().isoformat(), message_id))
        conn.commit()
    finally:
        conn.close()


# 获取最新消息（保持不变）
def get_latest_messages():
    try:
        # 从环境变量获取多个频道链接
        channel_urls = os.getenv("ENV_TG_CHANNEL", "").split('|')
        if not channel_urls or channel_urls == ['']:
            logger.warning("未设置ENV_TG_CHANNEL环境变量")
            return []
            
        all_new_messages = []
        
        # 对每个频道链接执行获取消息逻辑
        for channel_url in channel_urls:
            channel_url = channel_url.strip()
            if not channel_url:
                continue
                
            # 预处理channel_url，确保格式正确
            if channel_url.startswith('https://t.me/') and '/s/' not in channel_url:
                # 提取频道名称部分
                channel_name = channel_url.split('https://t.me/')[-1]
                # 重构URL，添加/s/
                channel_url = f'https://t.me/s/{channel_name}'
            logger.info(f"===== 处理频道: {channel_url} =====")
            
            session = requests.Session()
            retry = Retry(total=RETRY_TIMES, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
            session.mount("https://", HTTPAdapter(max_retries=retry))
            headers = {"User-Agent": USER_AGENTS[int(time.time()) % len(USER_AGENTS)]}
            response = session.get(channel_url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            message_divs = soup.find_all('div', class_='tgme_widget_message')
            total = len(message_divs)
            logger.info(f"共解析到{total}条消息（最新的在最后）")
            new_messages = []
            for i in range(total):
                msg_index = total - 1 - i
                msg = message_divs[msg_index]
                data_post = msg.get('data-post', '')
                message_id = data_post.split('/')[-1] if data_post else f"未知ID_{msg_index}"
                logger.info(f"检查第{i + 1}新消息（倒数第{i + 1}条，ID: {message_id}）")
                time_elem = msg.find('time')
                date_str = time_elem.get('datetime') if time_elem else datetime.now().isoformat()
                link_elem = msg.find('a', class_='tgme_widget_message_date')
                message_url = f"{link_elem.get('href').lstrip('/')}" if link_elem else ''
                text_elem = msg.find('div', class_='tgme_widget_message_text')
                #print(str(text_elem))
                if text_elem:
                    message_text = text_elem.get_text(separator='\\n', strip=True)
                    target_urls = extract_target_url(f"{msg}")
                    if target_urls:
                        for url in target_urls:
                            # 检查是否有提取码但URL中没有pwd参数
                            pwd_match = re.search(r'提取码\s*[:：]\s*(\w+)', str(text_elem), re.IGNORECASE)
                            if pwd_match and 'pwd=' not in url:
                                pwd = pwd_match.group(1)
                                # 确保URL格式正确，添加pwd参数
                                if '?' in url:
                                    url = f"{url}&pwd={pwd}"
                                else:
                                    url = f"{url}?pwd={pwd}"
                                logger.info(f"已为URL添加提取码: {url}")
                            if not is_message_processed(message_url):
                                new_messages.append((message_id, date_str, message_url, url, message_text))                               
                            else:
                                logger.info(f"第{i + 1}新消息已处理，跳过")
                            #print(f"tg消息链接：{message_url}")
                            #print(f"123链接：{url}")
                    else:
                        if not is_message_processed(message_url):
                            new_messages.append((message_id, date_str, message_url, "", message_text))
                        else:
                            logger.info(f"第{i + 1}新消息已处理，跳过")                       
                        #print("未发现目标123链接")
            new_messages.reverse()
            logger.info(f"发现{len(new_messages)}条新的123分享链接")
            all_new_messages.extend(new_messages)
        
        # 按时间排序所有消息
        all_new_messages.sort(key=lambda x: x[1])
        logger.info(f"===== 所有频道共发现{len(all_new_messages)}条新的123分享链接 =====")
        return all_new_messages
    except requests.exceptions.RequestException as e:
        logger.error(f"网络请求失败: {str(e)[:100]}")
        return []


def extract_target_url(text):
    pattern = r'https?:\/\/www\.123(?:\d+|pan)\.\w+\/s\/[\w-]+(?:\?pwd=\w+|(?:\s*提取码\s*[:：]\s*\w+))?'
    matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
    if matches:
        # 去除重复链接
        unique_matches = list(set([match.strip() for match in matches]))
        return unique_matches
    return []


# 转存分享链接（优化版）
from collections import defaultdict, deque
def transfer_shared_link_optimize(client: P123Client, target_url: str, UPLOAD_TARGET_PID: int | str) -> bool:
    parsed_url = urlsplit(target_url)
    if '/s/' in parsed_url.path:
        after_s = parsed_url.path.split('/s/')[-1]
        temp_key = after_s.split('/')[0]
        pwd_sep_index = re.search(r'提取码[:：]', temp_key)
        share_key = temp_key[:pwd_sep_index.start()].strip() if pwd_sep_index else temp_key
    else:
        share_key = None
    if not share_key:
        logger.error(f"无效的分享链接: {target_url}")
        reply_thread_pool.submit(send_message, f"无效的分享链接: {target_url}")
        return False

    # 解析密码
    query_params = parse_qs(parsed_url.query)
    share_pwd = query_params.get('pwd', [None])[0]
    if not share_pwd:
        pwd_match = re.search(r'提取码\s*[:：]\s*(\w+)', parsed_url.path, re.IGNORECASE)
        if not pwd_match:
            pwd_match = re.search(r'提取码\s*[:：]\s*(\w+)', target_url, re.IGNORECASE)
        share_pwd = pwd_match.group(1) if pwd_match else ""

    # 存储所有文件和目录信息
    all_items = []  # {"file_id": "", "name": "", "etag": "", "parent_dir_id": "", "size": "", "Type": 0}

    def recursive_fetch(parent_file_id: int = 0) -> None:
        """递归获取分享中的文件和目录"""
        try:
            page = 1
            while True:
                resp = client.share_fs_list({
                    "ShareKey": share_key,
                    "SharePwd": share_pwd,
                    "parentFileId": parent_file_id,
                    "limit": 100,
                    "Page": page
                })
                check_response(resp)
                data = resp["data"]
                
                # 处理当前页数据
                if data and "InfoList" in data:
                    for item in data["InfoList"]:
                        # 将所有项目（目录和文件）都添加到all_items列表
                        all_items.append({
                            "file_id": item["FileId"],
                            "name": item["FileName"],
                            "etag": item.get("Etag", ""),
                            "parent_dir_id": parent_file_id,
                            "size": item.get("Size", 0),
                            "Type": item["Type"]  # 保留原始类型值
                        })
                # 检查是否为最后一页
                if not data or len(data.get("InfoList", [])) < 100:
                    break
                page += 1
        except Exception as e:
            logger.error(f"获取列表失败（父ID: {parent_file_id}）: {str(e)}")
            raise
    try:
        # 递归获取文件和目录列表
        recursive_fetch()
        # 统计文件和目录数量
        file_count = sum(1 for item in all_items if item["Type"] != 1)
        dir_count = sum(1 for item in all_items if item["Type"] == 1)
        logger.info(f"共发现{file_count}个文件和{dir_count}个目录，准备转存（顶层目录: {UPLOAD_TARGET_PID}）")
    except Exception as e:
        logger.error(f"获取资源结构失败: {str(e)}")
        reply_thread_pool.submit(send_message, f"获取资源结构失败: {str(e)}")
        return False
    # 构建fileList数组
    fileList = [
        {
            "fileID": item["file_id"],
            "size": item["size"],
            "etag": item["etag"],
            "type": item["Type"],  # 使用原始类型值
            "parentFileID": UPLOAD_TARGET_PID,  # 所有项目都直接保存到目标目录
            "fileName": item["name"],
            "driveID": 0
        } for item in all_items
    ]
    logger.info(f"准备转存文件列表（顶层目录: {UPLOAD_TARGET_PID}）")
    try:
        # 构建API请求
        url = "https://www.123pan.com/b/api/restful/goapi/v1/file/copy/save"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {client.token}"
        }
        
        payload = {
            "fileList": fileList,
            "shareKey": share_key,
            "sharePwd": share_pwd,
            "currentLevel": 0
        }
        # 发送请求
        response = requests.post(url, json=payload, headers=headers)
        # 处理响应
        if response.status_code == 200:
            try:
                response_json = response.json()
                logger.info(response_json)
                if response_json.get("message") == "ok":
                    logger.info(f"{target_url} 转存成功")
                    return True
                else:
                    logger.error(f"{target_url} 转存失败: {response_json.get('message')}")
                    reply_thread_pool.submit(send_message, f"{target_url} 转存失败: {response_json.get('message')}")
                    return False
            except ValueError:
                logger.error(f"响应不是有效的JSON格式: {response.text}")
                reply_thread_pool.submit(send_message, f"响应不是有效的JSON格式: {response.text}")
                return False
        else:
            logger.error(f"请求失败，状态码: {response.status_code}，响应内容: {response.text}")
            reply_thread_pool.submit(send_message, f"请求失败，状态码: {response.status_code}，响应内容: {response.text}")
            return False
    except Exception as e:
        logger.error(f"转存过程中发生错误: {str(e)}")
        reply_thread_pool.submit(send_message, f"转存过程中发生错误: {str(e)}")
        return False

def transfer_shared_link(client: P123Client, target_url: str, UPLOAD_TARGET_PID: int | str) -> bool:
    parsed_url = urlsplit(target_url)
    if '/s/' in parsed_url.path:
        after_s = parsed_url.path.split('/s/')[-1]
        temp_key = after_s.split('/')[0]
        pwd_sep_index = re.search(r'提取码[:：]', temp_key)
        share_key = temp_key[:pwd_sep_index.start()].strip() if pwd_sep_index else temp_key
    else:
        share_key = None
    if not share_key:
        logger.error(f"无效的分享链接: {target_url}")
        reply_thread_pool.submit(send_message, f"无效的分享链接: {target_url}")
        return False

    # 解析密码
    query_params = parse_qs(parsed_url.query)
    share_pwd = query_params.get('pwd', [None])[0]
    if not share_pwd:
        pwd_match = re.search(r'提取码\s*[:：]\s*(\w+)', parsed_url.path, re.IGNORECASE)
        if not pwd_match:
            pwd_match = re.search(r'提取码\s*[:：]\s*(\w+)', target_url, re.IGNORECASE)
        share_pwd = pwd_match.group(1) if pwd_match else ""

    # 存储所有目录和文件信息
    all_dirs = []  # {"dir_id": "", "name": "", "parent_dir_id": ""}
    all_files = []  # {"file_id": "", "name": "", "etag": "", "parent_dir_id": "", "size": ""}

    def recursive_fetch(parent_file_id: int = 0) -> None:
        """递归获取分享中的目录和文件"""
        try:
            page = 1
            while True:
                resp = client.share_fs_list({
                    "ShareKey": share_key,
                    "SharePwd": share_pwd,
                    "parentFileId": parent_file_id,
                    "limit": 100,
                    "Page": page
                })
                check_response(resp)
                data = resp["data"]
                
                # 处理当前页数据
                if data and "InfoList" in data:
                    for item in data["InfoList"]:
                        if item["Type"] == 1:  # 目录
                            all_dirs.append({
                                "dir_id": item["FileId"],
                                "name": item["FileName"],
                                "parent_dir_id": parent_file_id
                            })
                            # 递归处理子目录
                            recursive_fetch(item["FileId"])
                        else:  # 文件
                            all_files.append({
                                "file_id": item["FileId"],
                                "name": item["FileName"],
                                "etag": item["Etag"],
                                "parent_dir_id": parent_file_id,
                                "size": item["Size"]
                            })
                
                # 检查是否为最后一页
                if not data or len(data.get("InfoList", [])) < 100:
                    break
                
                page += 1
            # 安全处理Next参数，确保是有效的整数
            
        except Exception as e:
            logger.error(f"获取列表失败（父ID: {parent_file_id}）: {str(e)}")
            raise

    try:
        recursive_fetch()
        logger.info(f"共发现{len(all_dirs)}个目录和{len(all_files)}个文件，准备转存（顶层目录: {UPLOAD_TARGET_PID}）")
    except Exception as e:
        logger.error(f"获取资源结构失败: {str(e)}")
        reply_thread_pool.submit(send_message, f"获取资源结构失败: {str(e)}")
        return False

    # 第一步：构建目录层级（核心调整）
    # 1. 识别分享中的所有目录的父-子关系（无论原始parent_dir_id是什么）
    dir_children = defaultdict(list)  # 原目录ID → 子目录列表
    all_dir_ids = {d["dir_id"] for d in all_dirs}  # 所有目录ID集合
    share_top_dirs = []  # 分享中的顶层目录（即没有上级目录在all_dirs中的目录）

    for dir_info in all_dirs:
        parent_id = dir_info["parent_dir_id"]
        # 若父目录ID不在分享的目录列表中，说明是分享的顶层目录
        if parent_id not in all_dir_ids:
            share_top_dirs.append(dir_info)
        else:
            dir_children[parent_id].append(dir_info)

    logger.info(f"分享中的顶层目录（直接创建在目标目录下）: {[d['name'] for d in share_top_dirs]}")

    # 2. 按层级创建目录（以UPLOAD_TARGET_PID为根）
    dir_queue = deque(share_top_dirs)  # 队列存储待创建目录
    dir_id_mapping = {}  # 原目录ID → 新目录ID（新目录的父目录为UPLOAD_TARGET_PID或对应子目录）

    # 强制将分享的顶层目录的父目录设为UPLOAD_TARGET_PID
    for dir_info in share_top_dirs:
        dir_id_mapping[dir_info["dir_id"]] = None  # 标记待创建

    all_success = True

    while dir_queue:
        dir_info = dir_queue.popleft()
        original_dir_id = dir_info["dir_id"]
        dir_name = dir_info["name"]
        original_parent_id = dir_info["parent_dir_id"]

        # 确定新父目录ID：
        # - 若为分享的顶层目录 → 新父目录是UPLOAD_TARGET_PID
        # - 否则 → 新父目录是原父目录对应的新目录ID
        if original_dir_id in [d["dir_id"] for d in share_top_dirs]:
            new_parent_id = UPLOAD_TARGET_PID
        else:
            new_parent_id = dir_id_mapping.get(original_parent_id)

        if not new_parent_id:
            logger.warning(f"目录 {dir_name}（原ID: {original_dir_id}）的新父目录不存在，跳过")
            reply_thread_pool.submit(send_message, f"警告：目录 {dir_name}（原ID: {original_dir_id}）的新父目录不存在，跳过")
            return False

        # 创建目录
        try:
            # 正确传递参数（name作为位置参数）
            create_resp = client.fs_mkdir(
                dir_name,  # 目录名（位置参数）
                parent_id=new_parent_id,
                duplicate=1
            )
            check_response(create_resp)
            # print(f"fs_mkdir完整响应: {create_resp}")  # 调试用

            # 关键修复：从data.Info.FileId提取新目录ID
            new_dir_id = create_resp["data"]["Info"]["FileId"]
            if not new_dir_id:
                raise ValueError(f"新目录ID为空，响应: {create_resp}")

            dir_id_mapping[original_dir_id] = new_dir_id
            logger.info(f"创建目录成功：{dir_name} → 新ID: {new_dir_id}，父目录: {new_parent_id}")

            # 添加子目录到队列
            child_dirs = dir_children.get(original_dir_id, [])
            dir_queue.extend(child_dirs)
            logger.info(f"待创建子目录: {[d['name'] for d in child_dirs]}")
        except Exception as e:
            logger.error(f"创建目录 {dir_name} 失败: {str(e)}，跳过该目录及子目录")
            reply_thread_pool.submit(send_message, f"创建目录 {dir_name} 失败: {str(e)}，跳过该目录及子目录")
            return False

    logger.info(f"目录映射关系: {dir_id_mapping}")

    # 第二步：按文件数量分组，每组最多100个文件进行转存
    # 1. 按目标目录ID和文件数量分组
    MAX_BATCH_SIZE = 100
    file_batches = defaultdict(list)  # (target_parent_id) → 批次列表
    batch_by_dir = defaultdict(list)  # (target_parent_id, batch_index) → 文件列表
    
    # 先按目标目录ID分组
    for file_info in all_files:
        file_id = file_info["file_id"]
        file_name = file_info["name"]
        original_parent_id = file_info["parent_dir_id"]
        
        # 确定文件的目标目录ID
        target_parent_id = dir_id_mapping.get(original_parent_id, UPLOAD_TARGET_PID)
        logger.info(f"文件 {file_name} 的原父目录ID: {original_parent_id} → 目标目录ID: {target_parent_id}")
        
        # 构建文件信息
        file_data = {
            "file_id": file_id,
            "file_name": file_name,
            "etag": file_info["etag"],
            "parent_file_id": original_parent_id,
            "size": file_info["size"]
        }
        
        # 添加到对应目录的批次列表
        file_batches[target_parent_id].append(file_data)
    
    # 2. 对每个目录的文件列表按最大批次大小分割
    all_batches = []
    for target_parent_id, files_in_dir in file_batches.items():
        # 将目录中的文件分成多个批次，每批最多MAX_BATCH_SIZE个文件
        for i in range(0, len(files_in_dir), MAX_BATCH_SIZE):
            batch_files = files_in_dir[i:i + MAX_BATCH_SIZE]
            all_batches.append((target_parent_id, batch_files))
    
    # 3. 逐个批次转存文件
    total_batches = len(all_batches)
    logger.info(f"共分为 {total_batches} 个批次转存文件，每批最多 {MAX_BATCH_SIZE} 个文件")
    
    for batch_index, (target_parent_id, batch_files) in enumerate(all_batches, 1):
        try:
            copy_resp = client.share_fs_copy({
                "share_key": share_key,
                "share_pwd": share_pwd,
                "file_list": batch_files,
                "current_level": 1,
                "event": "transfer"
            }, parent_id=target_parent_id)
            
            check_response(copy_resp)
            if copy_resp.get("code") in (0, 200):
                file_names = [f["file_name"] for f in batch_files]
                logger.info(f"批次 {batch_index}/{total_batches} 成功转存 {len(batch_files)} 个文件到目录ID: {target_parent_id} → 文件名: {', '.join(file_names[:3])}{'...' if len(file_names) > 3 else ''}")
            else:
                file_names = [f["file_name"] for f in batch_files]
                logger.error(f"批次 {batch_index}/{total_batches} 转存 {len(batch_files)} 个文件到目录ID: {target_parent_id} 失败（响应: {copy_resp}）")
                reply_thread_pool.submit(send_message, f"批次 {batch_index}/{total_batches} 转存 {len(batch_files)} 个文件到目录ID: {target_parent_id} 失败（响应: {copy_resp}）")
                return False
        except Exception as e:
            file_names = [f["file_name"] for f in batch_files]
            logger.error(f"批次 {batch_index}/{total_batches} 转存 {len(batch_files)} 个文件到目录ID: {target_parent_id} 异常: {str(e)}")
            reply_thread_pool.submit(send_message, f"批次 {batch_index}/{total_batches} 转存 {len(batch_files)} 个文件到目录ID: {target_parent_id} 异常: {str(e)}")
            return False
    
    logger.info(f"所有 {len(all_files)} 个文件已成功转存！")
    return True
class UserStateManager:
    def __init__(self, db_file):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        conn.execute('''CREATE TABLE IF NOT EXISTS user_states
                     (user_id INTEGER PRIMARY KEY, state TEXT, data TEXT)''')
        conn.commit()
        conn.close()

    def set_state(self, user_id, state, data=None):
        conn = sqlite3.connect(self.db_file)
        conn.execute("INSERT OR REPLACE INTO user_states VALUES (?, ?, ?)",
                     (user_id, state, data))
        conn.commit()
        conn.close()

    def get_state(self, user_id):
        conn = sqlite3.connect(self.db_file)
        result = conn.execute("SELECT state, data FROM user_states WHERE user_id = ?",
                              (user_id,)).fetchone()
        conn.close()
        return result if result else (None, None)

    def clear_state(self, user_id):
        conn = sqlite3.connect(self.db_file)
        conn.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()


# 初始化用户状态管理器
user_state_manager = UserStateManager(USER_STATE_DB)


# 搜索123网盘文件夹（修改结果数量为15）
async def search_123_files(client: P123Client, keyword: str) -> list:
    """搜索123网盘中的文件夹（返回最多15个结果）"""
    all_items = []
    last_file_id = 0
    try:
        for i in range(5):  # 最多3页
            response = requests.get(
                f"https://open-api.123pan.com/api/v2/file/list?parentFileId=0&searchData={encodeURIComponent(keyword)}&searchMode=1&limit=100&lastFileId={last_file_id}",
                headers={
                    'Authorization': f'Bearer {client.token}',
                    'Platform': 'open_platform'
                },
                timeout=TIMEOUT
            )
            data = response.json()
            if data.get('code') == 401 or 'expired' in str(data.get('message', '')).lower():
                raise Exception("token expired")
            if data.get('code') != 0:
                raise Exception(f"搜索失败: {data.get('message', '未知错误')}")
            items = data.get('data', {}).get('fileList', [])
            # 仅筛选文件夹（type=1）
            folder_items = [item for item in items if item.get('type') == 1]
            all_items.extend(folder_items)
            last_file_id = data.get('data', {}).get('lastFileId', -1)
            if last_file_id == -1:
                break

        # 限制最多返回15个结果
        results = []
        # 批量处理15个结果，获取完整路径
        items_to_process = all_items[:20]  # 限制为15个结果
        logger.info(f"准备批量处理{len(items_to_process)}个文件夹结果")
        
        # 使用批量构建路径函数
        # 注意：即使只有15个文件夹项目，由于需要获取各级父目录信息，所以实际查询的ID数量会多于15个
        # 这种设计可以显著减少API调用次数，提高路径构建效率

        paths_map = await batch_build_full_paths(client, items_to_process)
        
        # 创建映射，以便快速查找item信息
        item_map = {str(item.get('fileId', '')): item for item in items_to_process if str(item.get('fileId', ''))}
        
        # 遍历paths_map的键值对，使results的顺序与paths_map的顺序保持一致
        for file_id, full_path in paths_map.items():
            item = item_map.get(file_id)
            if not item:
                continue
            
            results.append({
                "id": file_id,
                "name": item.get('filename'),
                "type": "文件夹",
                "path": full_path,  # 完整路径
                "create_time": item.get('createTime')
            })
        
        # 如果还有未在paths_map中的项目，也添加到results中
        for item in items_to_process:
            file_id = str(item.get('fileId', ''))
            if not file_id or file_id in paths_map:
                continue
            
            full_path = item.get('filename', '')
            results.append({
                "id": file_id,
                "name": item.get('filename'),
                "type": "文件夹",
                "path": full_path,  # 完整路径
                "create_time": item.get('createTime')
            })
        return results
    except Exception as e:
        logger.error(f"搜索文件夹失败: {str(e)}")
        raise


def get_folder_detail(client: P123Client, file_id: str) -> dict:
    """获取文件夹详情"""
    if not file_id:
        logger.error("文件夹ID为空")
        return {"filename": ""}
    try:
        response = requests.get(
            f"https://open-api.123pan.com/api/v1/file/detail?fileID={file_id}",
            headers={
                'Authorization': f'Bearer {client.token}',
                'Platform': 'open_platform'
            },
            timeout=TIMEOUT
        )
        data = response.json()
        if data.get('code') != 0:
            logger.error(f"获取文件夹{file_id}详情失败: {data.get('message')}")
            return {"filename": ""}
        return data.get('data', {})
    except Exception as e:
        logger.error(f"获取文件夹{file_id}详情异常: {str(e)}")
        return {"filename": ""}


def get_files_details(client: P123Client, file_ids: list) -> dict:
    """批量获取文件/文件夹详情"""
    if not file_ids:
        logger.error("文件ID列表为空")
        return {}
    try:
        logger.info(f"请求以下父目录ID详情：{file_ids}")
        response = requests.post(
            "https://open-api.123pan.com/api/v1/file/infos",
            headers={
                'Authorization': f'Bearer {client.token}',
                'Platform': 'open_platform',
                'Content-Type': 'application/json'
            },
            json={"fileIds": file_ids},
            timeout=TIMEOUT
        )
        data = response.json()
        #logger.info(f"以下父目录详情：{data}")
        if data.get('code') != 0:
            logger.error(f"批量获取文件详情失败: {data.get('message', '未知错误')}")
            return {}
        details_map = {}
        # 注意：API返回的字段名是fileList，不是list
        for item in data.get('data', {}).get('fileList', []):
            file_id = str(item.get('fileId'))
            details_map[file_id] = item
        return details_map
    except Exception as e:
        logger.error(f"批量获取文件详情异常: {str(e)}")
        return {}


async def build_full_path(client: P123Client, item: dict) -> str:
    """构建文件夹完整路径（用于显示） - 单个处理版本（保持向后兼容）"""
    # 由于已经实现了批量构建路径的功能，这里可以保留为向后兼容或简单调用
    paths_map = await batch_build_full_paths(client, [item])
    file_id = str(item.get('fileId', ''))
    return paths_map.get(file_id, item.get('filename', ''))


async def batch_build_full_paths(client: P123Client, items: list) -> dict:
    """批量构建多个文件夹的完整路径（修复全局缓存问题，确保父ID详情不丢失）"""
    path_map = {}
    if not items:
        return path_map
    
    query_level = 4  # 保持固定4层
    temp_path_map = {}
    queried_ids = set()  # 已查询过的ID（避免重复请求）
    current_query_ids = set()  # 当前轮需查询的ID
    global_details_cache = {}  # 新增：全局缓存，保存所有已查询的父目录详情（跨轮复用）
    
    # 初始化：收集每个文件的初始信息
    logger.info(f"开始处理{len(items)}个文件夹项目，query_level={query_level}")
    for item in items:
        file_id = str(item.get('fileId', ''))
        if not file_id:
            continue
        
        temp_path_map[file_id] = {
            'path_parts': [item.get('filename', '')],
            'current_parent_id': item.get('parentFileId'),
            'remaining_levels': query_level
        }
        
        parent_id = item.get('parentFileId')
        if parent_id and parent_id != 0:
            current_query_ids.add(str(parent_id))
    
    logger.info(f"第一轮查询（第1层父目录）：{len(current_query_ids)}个ID，处理{len(temp_path_map)}个文件")
    
    # 迭代查询父目录（4轮）
    for level in range(query_level):
        if not current_query_ids:
            logger.info(f"第{level+1}轮无父ID可查，提前结束")
            break
        
        logger.info(f"第{level+1}轮查询（剩余层级：{query_level - level}）：{len(current_query_ids)}个ID")
        
        # 1. 新增：查询当前轮ID，合并到全局缓存
        current_details = get_files_details(client, list(current_query_ids))
        global_details_cache.update(current_details)  # 关键：将当前轮详情存入全局缓存
        
        next_query_ids = set()
        
        # 2. 处理每个文件的父目录链：从全局缓存获取详情，而非当前轮缓存
        for file_id, info in temp_path_map.items():
            if info['remaining_levels'] <= 0:
                continue
            
            current_parent_id = info['current_parent_id']
            if not current_parent_id or current_parent_id == 0:
                continue
            
            current_parent_id_str = str(current_parent_id)
            # 关键：从全局缓存获取详情，而非当前轮缓存
            parent_detail = global_details_cache.get(current_parent_id_str)
            
            if not parent_detail:
                logger.warning(f"第{level+1}轮：全局缓存中未找到ID[{current_parent_id_str}]的详情，停止该文件的上层查询")
                info['remaining_levels'] = 0
                continue
            
            # 提取父目录名称，更新路径
            parent_name = parent_detail.get('filename', '')
            if parent_name:
                # 新增：避免重复添加同一目录（防止异常情况下的重复）
                if not info['path_parts'] or info['path_parts'][0] != parent_name:
                    info['path_parts'].insert(0, parent_name)
                logger.debug(f"文件[{file_id}]第{level+1}层父目录：{parent_name}，当前路径：{'/'.join(info['path_parts'])}")
            
            # 获取下一层父ID，加入下轮查询（需未查询过）
            next_parent_id = parent_detail.get('parentFileId')
            if next_parent_id and next_parent_id != 0:
                next_parent_id_str = str(next_parent_id)
                if (next_parent_id_str not in queried_ids and 
                    next_parent_id_str not in current_query_ids and 
                    next_parent_id_str not in next_query_ids):
                    next_query_ids.add(next_parent_id_str)
                info['current_parent_id'] = next_parent_id
            else:
                info['remaining_levels'] = 0
            
            # 剩余层级-1
            info['remaining_levels'] -= 1
        
        # 更新已查询ID和下轮查询ID
        queried_ids.update(current_query_ids)
        current_query_ids = next_query_ids
    
    # 4轮查询完成后，从全局缓存中继续构建路径（不发起新请求）
    logger.info("4轮查询已完成，开始从全局缓存中继续构建路径（不发起新请求）")
    has_more_to_process = True
    while has_more_to_process:
        has_more_to_process = False
        for file_id, info in temp_path_map.items():
            current_parent_id = info['current_parent_id']
            if not current_parent_id or current_parent_id == 0:
                continue
            
            current_parent_id_str = str(current_parent_id)
            # 只从全局缓存中获取详情，不发起新请求
            parent_detail = global_details_cache.get(current_parent_id_str)
            
            if parent_detail:
                # 提取父目录名称，更新路径
                parent_name = parent_detail.get('filename', '')
                if parent_name:
                    if not info['path_parts'] or info['path_parts'][0] != parent_name:
                        info['path_parts'].insert(0, parent_name)
                    logger.debug(f"从缓存中补充路径：文件[{file_id}]新增父目录：{parent_name}，当前路径：{'/'.join(info['path_parts'])}")
                
                # 更新下一层父ID
                next_parent_id = parent_detail.get('parentFileId')
                if next_parent_id and next_parent_id != 0:
                    info['current_parent_id'] = next_parent_id
                    has_more_to_process = True  # 还有更多父ID可以从缓存中查找
                else:
                    info['current_parent_id'] = 0
            else:
                info['current_parent_id'] = 0  # 缓存中没有，停止查找
    
    # 构建最终路径 - 按路径字符串排序，使相同公共前缀的文件夹优先放在一起
    # 首先获取所有项，然后按路径字符串排序
    sorted_items = sorted(temp_path_map.items(), key=lambda x: '/'.join(x[1]['path_parts']))

    for file_id, info in sorted_items:
        full_path = '/'.join(info['path_parts'])
        path_map[file_id] = full_path
        logger.debug(f"文件[{file_id}]最终路径：{full_path}")
    logger.info(f"批量路径构建完成，生成{len(path_map)}个文件路径（query_level=4，缓存补充完成）")
    return path_map


def encodeURIComponent(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s, safe='~()*!.\'')


def create_share_link(client: P123Client, file_id: str, expiry_days: int = 0, password: str = None) -> dict:
    """创建分享链接"""
    if not file_id or not str(file_id).strip():
        raise ValueError("文件夹ID为空或无效")

    valid_expire_days = {0, 1, 7, 30}
    if expiry_days not in valid_expire_days:
        logger.warning(f"过期天数{expiry_days}无效，自动使用7天")
        expiry_days = 7

    try:
        folder_detail = get_folder_detail(client, file_id)
        folder_name = folder_detail.get('filename', f"分享文件夹_{file_id}")
        if not folder_name:
            logger.warning(f"文件夹ID{file_id}不存在，可能已被删除")

        response = requests.post(
            "https://open-api.123pan.com/api/v1/share/create",
            headers={
                'Authorization': f'Bearer {client.token}',
                'Platform': 'open_platform',
                'Content-Type': 'application/json'
            },
            json={
                "shareName": folder_name,
                "shareExpire": expiry_days,
                "fileIDList": file_id,
                "sharePwd": DIY_LINK_PWD
            },
            timeout=TIMEOUT
        )
        data = response.json()
        if data.get('code') != 0:
            raise Exception(f"创建分享失败: {data.get('message', '未知错误')}（ID: {file_id}）")
        share_info = data.get('data', {})
        if expiry_days == 0:
            expiry_str = "永久有效"
        else:
            expiry_time = int(time.time()) + expiry_days * 86400
            expiry_str = datetime.fromtimestamp(expiry_time).strftime('%Y-%m-%d %H:%M:%S')
        return {
            "url": f"https://www.123pan.com/s/{share_info.get('shareKey')}{'?pwd=' + DIY_LINK_PWD if DIY_LINK_PWD else ''}",
            "password": share_info.get('sharePwd'),
            "expiry": expiry_str
        }
    except Exception as e:
        logger.error(f"创建分享链接失败: {str(e)}")
        raise


def get_first_video_file(client: P123Client, file_id: str) -> str:
    """获取文件夹或子文件夹中第一个视频文件的名称"""
    video_extensions = {'.mkv', '.ts', '.mp4', '.avi', '.rmvb', '.wmv', '.m2ts', '.mpg', '.flv', '.rm', '.mov', '.iso'}

    def recursive_search(folder_id: str) -> str:
        try:
            # 调用123网盘API列出文件夹内容
            resp = client.fs_list(folder_id)
            check_response(resp)
            items = resp["data"]["InfoList"]

            # 优先检查当前文件夹的文件
            for item in items:
                if item["Type"] == 0:  # 类型为文件
                    filename = item["FileName"]
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in video_extensions:
                        return filename

            # 递归检查子文件夹
            for item in items:
                if item["Type"] == 1:  # 类型为文件夹
                    sub_result = recursive_search(item["FileId"])
                    if sub_result:
                        return sub_result
            return None
        except Exception as e:
            logger.error(f"搜索视频文件失败: {str(e)}")
            return None

    return recursive_search(file_id)
@bot.message_handler(commands=['info'])
def handle_info(message):
    user_id = message.from_user.id
    if user_id != TG_ADMIN_USER_ID:
        reply_thread_pool.submit(send_reply, message, "您没有权限使用此机器人。")
        return
    client = init_123_client()
    response = client.user_info()  # 验证token有效性
    def mask_uid(uid):
        """账户ID脱敏：1846764956 → 184****956"""
        uid_str = str(uid)
        return f"{uid_str[:3]}****{uid_str[-3:]}" if len(uid_str)>=6 else uid_str

    def mask_mobile(mobile):
        """手机号脱敏：18221643386 → 182****3386"""
        mobile_str = str(mobile)
        return f"{mobile_str[:3]}****{mobile_str[-4:]}" if len(mobile_str)==11 else mobile_str

    def format_size(size):
        """字节转TB/GB（自动适配单位）"""
        if size <= 0:
            return "0.00 GB"
        tb = size / (1024 **4)
        return f"{tb:.2f} TB" if tb >= 1 else f"{size / (1024** 3):.2f} GB"

    def space_progress(used, total, bar_len=10):
        """生成进度条：▓=已用，░=剩余"""
        if total == 0:
            return "□□□□□□□□□□ (0%)"
        ratio = used / total
        filled = int(ratio * bar_len)
        bar = "▓" * filled + "░" * (bar_len - filled)
        percent = f"{ratio*100:.1f}%"
        return f"{bar} ({percent})"

    # 假设响应数据为 `response`
    data = response["data"]

    # 1. 标题与账户信息
    base_title = "🚀 123云盘信息"

    account_info = f"""👤 账户信息
    ├─ 昵称：{data['Nickname']} {'🎖️VIP' if data['Vip'] else ''}
    ├─ 账户ID：{mask_uid(data['UID'])}
    ├─ 手机号：{mask_mobile(data['Passport'])}
    └─ 微信绑定：{"✅已绑" if data['BindWechat'] else "❌未绑"}"""

    # 2. 存储空间（带进度条）
    used = data['SpaceUsed']
    total = data['SpacePermanent']
    storage_progress = space_progress(used, total)

    storage_info = f"""💾 存储空间 {storage_progress}
    ├─ 已用：{format_size(used)}
    ├─ 永久：{format_size(total)}
    └─ 文件总数：{data['FileCount']:,} 个"""

    # 3. VIP详情（拆分多个权益）
    vip_details = []
    # 添加基础VIP信息
    #vip_details.append(f"├─ 等级：{data['VipLevel']} | 类型：{data['VipExplain']}")
    #vip_details.append(f"├─ 到期时间：{data['VipExpire']}")
    #vip_details.append(f"└─ 权益列表：")

    # 逐个添加VIP权益（单独成项）
    for i, vip in enumerate(data['VipInfo'], 1):
        # 最后一个权益用特殊符号
        symbol = "    └─" if i == len(data['VipInfo']) else "    ├─"
        vip_details.append(f"{symbol} {vip['vip_label']}：{vip['start_time']} → {vip['end_time']}")

    vip_info = "💎 VIP会员\n" + "\n".join(vip_details)

    # 4. 流量与功能状态
    traffic_info = f"""🚀 流量与功能
    ├─ 直连流量：{format_size(data['DirectTraffic'])}
    ├─ 分享流量：{format_size(data['ShareTraffic'])}
    └─ 直链功能：{"✅开启" if data['StraightLink'] else "❌关闭"}"""

    # 5. 备份信息
    backup_info = f"""📦 备份配置
    ├─ 移动端：{data['BackupFileInfo']['MobileTerminalBackupFileName']}
    └─ 桌面端：{data['BackupFileInfo']['DesktopTerminalBackupFileName']}"""

    # 拼接最终消息
    tg_message = "\n\n".join([
        base_title,
        account_info,
        storage_info,
        vip_info,
        traffic_info,
        backup_info
    ])
    # 最后一次性打印完整消息
    reply_thread_pool.submit(send_reply, message, tg_message)
from zhuli115 import accept_invite
# Telegram机器人消息处理（修改显示格式）
@bot.message_handler(commands=['zhuli115'])
def handle_start(message):
    user_id = message.from_user.id
    if user_id != TG_ADMIN_USER_ID:
        reply_thread_pool.submit(send_reply, message, "您没有权限使用此机器人。")
        return
    if os.getenv("ENV_115_COOKIES", ""):
        reply_thread_pool.submit(send_reply, message, "开始自动助力。助力成功后请刷新115活动页面查看。")
        accept_invite(f"{message.text}")
        reply_thread_pool.submit(send_reply, message, "已完成自动助力，请刷新115活动页面查看。")
    else:
        reply_thread_pool.submit(send_reply, message, "115账号未配置，无法助力，请先配置账号信息。使用方法例如/zhuli115 AAAAAA BBBBBB CCCCCC")

# Telegram机器人消息处理（修改显示格式）
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    if user_id != TG_ADMIN_USER_ID:
        reply_thread_pool.submit(send_reply, message, "您没有权限使用此机器人。")
        return
    reply_thread_pool.submit(send_reply, message,
                 f"🚀 欢迎使用tgto123网盘助手 v{version}！\n项目地址：https://github.com/walkingddd/tgto123-public 觉得好用能否帮忙点个小星星\n\n{USE_METHOD}")
    try:
        # 等待bot对象初始化完成
        if bot:
            # 获取频道信息（返回Chat对象，而非字典）
            channel_chat = bot.get_chat('@tgto123update')
            # 获取置顶消息（直接访问对象属性，而非字典get）
            pinned_message = channel_chat.pinned_message
            reply_thread_pool.submit(send_message,f"🚀 tgto123 当前版本为{version}，最新版本请见：\nhttps://t.me/tgto123update/{pinned_message.message_id}")
    except Exception as e:
        logger.error(f"转发频道消息失败: {str(e)}")

def save_env_filter(new_filter_value):
    """持久化保存过滤词到db/user.env文件"""
    env_file_path = os.path.join('db', 'user.env')
    
    # 确保文件存在
    if not os.path.exists(env_file_path):
        logger.warning(f"{env_file_path} 文件不存在")
        return False
    
    try:
        # 读取文件内容
        with open(env_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 查找并替换ENV_FILTER行
        updated_lines = []
        found = False
        for line in lines:
            if line.startswith('ENV_FILTER='):
                updated_lines.append(f'ENV_FILTER={new_filter_value}\n')
                found = True
            else:
                updated_lines.append(line)
        
        # 如果没找到ENV_FILTER行，则添加
        if not found:
            # 找到频道监控配置部分，在合适的位置添加
            insert_index = -1
            for i, line in enumerate(lines):
                if '# 检查新消息的时间间隔（分钟）' in line:
                    insert_index = i + 2
                    break
            if insert_index != -1:
                updated_lines.insert(insert_index, f'ENV_FILTER={new_filter_value}\n')
            else:
                # 如果找不到合适位置，就添加到文件末尾
                updated_lines.append(f'\nENV_FILTER={new_filter_value}\n')
        
        # 写回文件
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        
        return True
    except Exception as e:
        logger.error(f"保存环境变量失败：{str(e)}")
        return False

@bot.message_handler(commands=['add'])
def add_filter(message):
    user_id = message.from_user.id
    if user_id != TG_ADMIN_USER_ID:
        reply_thread_pool.submit(send_reply, message, "您没有权限使用此机器人。")
        return
    global FILTER, filter_pattern
    try:
        # 展示当前过滤词和用法
        current_filters_text = FILTER if FILTER else "无（未设置任何过滤词）"
        usage_text = "ℹ️ 用法：\n- 添加过滤词：/add 关键词\n（例：/add WALK   /add WALK|权力的游戏）\n- 删除过滤词：/remove 关键词\n（例：/remove 权力的游戏   /remove WALK|权力的游戏）"
        
        # 检查是否有参数
        if len(message.text.split()) < 2:
            reply_thread_pool.submit(send_reply, message, f"📌 当前过滤词：{current_filters_text} （多个用|分隔，命中的内容会被转存，为空则会转存所有资源）\n❌ 请输入要添加的过滤词（例：/add WALK）\n\n{usage_text}")
            logger.error(f"用户 {message.from_user.id} 执行/add失败：无输入参数")
            return
        
        # 获取用户输入的过滤词并清理
        new_filters_text = message.text.split(maxsplit=1)[1].strip()
        
        # 检查是否为空字符串
        if not new_filters_text:
            reply_thread_pool.submit(send_reply, message, f"📌 当前过滤词：{current_filters_text} （多个用|分隔，命中的内容会被转存，为空则会转存所有资源）\n❌ 请输入要添加的过滤词（例：/add WALK 或 /add WALK|权力的游戏）\n\n{usage_text}")
            logger.error(f"用户 {message.from_user.id} 执行/add失败：参数为空")
            return
        
        # 拆分用户输入的多个过滤词
        new_filters_list = [f.strip() for f in new_filters_text.split("|") if f.strip()]
        
        # 拆分现有过滤词
        current_filters = FILTER.split("|") if FILTER else []
        
        # 记录添加结果
        added_filters = []
        existing_filters = []
        
        # 检查每个过滤词是否已存在并添加
        for new_filter in new_filters_list:
            if new_filter not in current_filters:
                added_filters.append(new_filter)
                current_filters.append(new_filter)
            else:
                existing_filters.append(new_filter)
        
        # 如果没有添加任何新过滤词
        if not added_filters:
            reply_thread_pool.submit(send_reply, message, f"📌 当前过滤词：{current_filters_text} （多个用|分隔，命中的内容会被转存，为空则会转存所有资源）\n⚠️ 所有过滤词「{', '.join(existing_filters)}」已存在，无需重复添加\n\n{usage_text}")
            return
        
        # 构建新的过滤词字符串
        FILTER = "|".join(current_filters)
        
        # 持久化保存到文件
        if not save_env_filter(FILTER):
            reply_thread_pool.submit(send_reply, message, f"📌 当前过滤词：{current_filters_text} （多个用|分隔，命中的内容会被转存，为空则会转存所有资源）\n⚠️ 过滤词添加成功，但保存到文件失败，请手动在配置页面更新\n\n{usage_text}")
        
        # 重建正则对象
        filter_pattern = re.compile(FILTER, re.IGNORECASE)
        
        # 构建反馈消息
        feedback_msg = f"📌 当前过滤词：{current_filters_text} （多个用|分隔，命中的内容会被转存，为空则会转存所有资源）\n"
        
        if added_filters:
            feedback_msg += f"✅ 已添加过滤词：「{', '.join(added_filters)}」\n"
        
        if existing_filters:
            feedback_msg += f"⚠️ 已存在的过滤词：「{', '.join(existing_filters)}」\n"
        
        feedback_msg += f"📌 更新后过滤词：{FILTER}\n\n{usage_text}"
        
        # 发送成功反馈
        reply_thread_pool.submit(send_reply, message, feedback_msg)
        logger.info(f"用户 {message.from_user.id} 执行/add，添加过滤词：{', '.join(added_filters)}，已存在：{', '.join(existing_filters)}，更新后：{FILTER}")
        
    except Exception as e:
        reply_thread_pool.submit(send_reply, message, f"操作失败：{str(e)}")
        logger.info(f"用户 {message.from_user.id} 执行/add出错：{str(e)}")

@bot.message_handler(commands=['remove'])
def remove_filter(message):
    user_id = message.from_user.id
    if user_id != TG_ADMIN_USER_ID:
        reply_thread_pool.submit(send_reply, message, "您没有权限使用此机器人。")
        return

    global FILTER, filter_pattern
    try:
        # 展示当前过滤词和用法
        current_filters_text = FILTER if FILTER else "无（未设置任何过滤词）"
        usage_text = "ℹ️ 用法：\n- 添加过滤词：/add 关键词（例：/add WALK）\n- 删除过滤词：/remove 关键词（例：/remove 权力的游戏）"
        
        # 检查当前是否有过滤词
        if not FILTER:
            reply_thread_pool.submit(send_reply, message, f"📌 当前过滤词：{current_filters_text} （多个用|分隔，命中的内容会被转存，为空则会转存所有资源）\n⚠️ 当前无任何过滤词，无需删除\n\n{usage_text}")
            logger.error(f"用户 {message.from_user.id} 执行/remove失败：当前无过滤词")
            return
        
        # 检查是否有参数
        if len(message.text.split()) < 2:
            reply_thread_pool.submit(send_reply, message, f"📌 当前过滤词：{current_filters_text} （多个用|分隔，命中的内容会被转存，为空则会转存所有资源）\n❌ 请输入要删除的过滤词（例：/remove 权力的游戏）\n\n{usage_text}")
            logger.error(f"用户 {message.from_user.id} 执行/remove失败：无输入参数")
            return
        
        # 获取用户输入的过滤词并清理
        del_filters_text = message.text.split(maxsplit=1)[1].strip()
        
        # 检查是否为空字符串
        if not del_filters_text:
            reply_thread_pool.submit(send_reply, message, f"📌 当前过滤词：{current_filters_text} （多个用|分隔，命中的内容会被转存，为空则会转存所有资源）\n❌ 请输入要删除的过滤词（例：/remove 权力的游戏 或 /remove WALK|权力的游戏）\n\n{usage_text}")
            logger.error(f"用户 {message.from_user.id} 执行/remove失败：参数为空")
            return
        
        # 拆分用户输入的多个过滤词
        del_filters = [f.strip() for f in del_filters_text.split("|") if f.strip()]
        
        # 拆分现有过滤词
        current_filters = FILTER.split("|") if FILTER else []
        
        # 记录删除结果
        deleted_filters = []
        not_found_filters = []
        
        # 检查每个过滤词是否存在并删除
        for del_filter in del_filters:
            if del_filter in current_filters:
                deleted_filters.append(del_filter)
            else:
                not_found_filters.append(del_filter)
        
        # 删除存在的过滤词
        new_filters = [f for f in current_filters if f not in deleted_filters]
        FILTER = "|".join(new_filters) if new_filters else ""
        
        # 持久化保存到文件
        if not save_env_filter(FILTER):
            reply_thread_pool.submit(send_reply, message, f"📌 当前过滤词：{current_filters_text} （多个用|分隔，命中的内容会被转存，为空则会转存所有资源）\n⚠️ 过滤词删除成功，但保存到文件失败，请手动在配置页面更新\n\n{usage_text}")

        # 重建正则对象
        filter_pattern = re.compile(FILTER, re.IGNORECASE)
        
        # 构建反馈消息
        updated_filters_text = FILTER if FILTER else "无"
        feedback_msg = f"📌 当前过滤词：{current_filters_text} （多个用|分隔，命中的内容会被转存，为空则会转存所有资源）\n"
        
        if deleted_filters:
            feedback_msg += f"✅ 已删除过滤词：「{', '.join(deleted_filters)}」\n"
        
        if not_found_filters:
            feedback_msg += f"⚠️ 未找到的过滤词：「{', '.join(not_found_filters)}」\n"
        
        feedback_msg += f"📌 更新后过滤词：{updated_filters_text}\n\n{usage_text}"
        
        # 发送成功反馈
        reply_thread_pool.submit(send_reply, message, feedback_msg)
        logger.info(f"用户 {message.from_user.id} 执行/remove，删除过滤词：{', '.join(deleted_filters)}，未找到：{', '.join(not_found_filters)}，更新后：{FILTER}")
        
    except Exception as e:
        reply_thread_pool.submit(send_reply, message, f"操作失败：{str(e)}")
        logger.error(f"用户 {message.from_user.id} 执行/remove出错：{str(e)}")

@bot.message_handler(commands=['share'])
def handle_share_command(message):
    user_id = message.from_user.id
    if user_id != TG_ADMIN_USER_ID:
        reply_thread_pool.submit(send_reply, message, "您没有权限使用此命令。")
        return
    try:
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2 or not command_parts[1].strip():
            reply_thread_pool.submit(send_reply, message, "请提供搜索关键词，例如：/share 权力的游戏")
            return
        keyword = command_parts[1].strip()
        user_id = message.from_user.id
        reply_thread_pool.submit(send_reply, message, f"正在搜索包含 '{keyword}' 的文件夹...")
        client = init_123_client()
        import threading
        threading.Thread(target=perform_search, args=(client, keyword, user_id, message.chat.id)).start()
    except Exception as e:
        reply_thread_pool.submit(send_reply, message, f"操作失败: {str(e)}")
        logger.error(f"处理/share命令失败: {str(e)}")

def build_folder_message(results):
    """
    核心规则：
    1. 编号顺序：1-20严格对应输入顺序，不打乱、不重排
    2. 大组划分：按“原始编号连续+前两层目录相同”划大组（非连续/前缀不同则单独成组）
    3. 组内合并：每个大组内计算所有路径的公共前缀（含前两层外的深层前缀），合并为父目录
    4. 单独组处理：组内仅1条路径时，自动作为单独组，不强制合并公共前缀
    """
    # 步骤1：预处理路径，提取关键信息（保留原始编号）
    path_info_list = []
    for orig_seq, item in enumerate(results, start=1):  # 原始编号1-20
        raw_path = item.get("path", "").strip("/")
        dir_list = [p.strip() for p in raw_path.split("/") if p.strip()]  # 拆分目录列表
        dir_len = len(dir_list)
        
        # 提取前两层目录作为分组key（不足两层则取实际层数，如1层）
        if dir_len >= 2:
            group_key = tuple(dir_list[:2])  # 前两层目录作为key（如("Resource","大包资源")）
        else:
            group_key = tuple(dir_list)  # 不足两层，用全部目录作为key（如("Video",)）
        
        path_info_list.append({
            "orig_seq": orig_seq,
            "raw_path": raw_path,
            "dir_list": dir_list,
            "dir_len": dir_len,
            "group_key": group_key,
            "is_root": dir_len == 1  # 根目录判断：仅1层目录
        })
    if not path_info_list:
        return "未找到匹配文件夹"

    # 工具函数1：计算一组路径的公共前缀长度（核心修正！）
    def get_group_common_prefix(group_paths):
        if len(group_paths) == 1:
            # 单独组：公共前缀取到“倒数第二层”，确保子路径显示最后1层
            single_path = group_paths[0]
            return max(0, single_path["dir_len"] - 1)
        # 多路径组：关键修正——公共前缀长度 ≤ 最短路径的dir_len - 1
        min_dir_len = min(p["dir_len"] for p in group_paths)
        max_allowed_len = min_dir_len - 1  # 禁止公共前缀包含最短路径的最后一层
        base_dir = group_paths[0]["dir_list"]
        common_len = max_allowed_len  # 初始化为最大允许长度
        # 比较所有路径，找到最长公共前缀（不超过max_allowed_len）
        for p in group_paths[1:]:
            curr_dir = p["dir_list"]
            curr_common = 0
            while curr_common < common_len and curr_dir[curr_common] == base_dir[curr_common]:
                curr_common += 1
            if curr_common < common_len:
                common_len = curr_common
            if common_len == 0:
                break
        return common_len

    # 工具函数2：生成父目录字符串和子路径字符串
    def get_parent_subpath(path, common_len):
        dir_list = path["dir_list"]
        # 父目录：公共前缀部分
        parent_dir = dir_list[:common_len] if common_len > 0 else []
        parent_str = " / ".join(parent_dir) if parent_dir else ("根目录" if path["is_root"] else "")
        # 子路径：公共前缀之后的部分（若为空，显示最后1层目录）
        sub_dir = dir_list[common_len:] if common_len < path["dir_len"] else [dir_list[-1]]
        sub_path_str = " / ".join(sub_dir)
        return parent_str, sub_path_str

    # 步骤2：按“编号连续+group_key相同”划大组（核心分组逻辑）
    groups = []
    if path_info_list:
        current_group = [path_info_list[0]]  # 初始化当前组（第一个路径）
        for path in path_info_list[1:]:
            prev_path = current_group[-1]
            # 判断：当前路径与前一个路径“编号连续（必然满足，按顺序遍历）且group_key相同”
            if path["group_key"] == prev_path["group_key"]:
                current_group.append(path)
            else:
                # 不同group_key，保存当前组，新建组
                groups.append(current_group)
                current_group = [path]
        groups.append(current_group)  # 加入最后一个组

    # 步骤3：处理每个大组，合并组内公共前缀
    processed_groups = []
    for group in groups:
        common_len = get_group_common_prefix(group)  # 组内公共前缀长度
        group_parent = ""  # 组的统一父目录（取第一条路径的父目录，组内所有路径父目录相同）
        group_paths = []
        
        for path in group:
            parent_str, sub_path_str = get_parent_subpath(path, common_len)
            # 统一组的父目录（组内所有路径父目录一致，取第一条的即可）
            if not group_parent:
                group_parent = parent_str
            # 收集组内路径（含原始编号和子路径）
            group_paths.append({
                "orig_seq": path["orig_seq"],
                "sub_path": sub_path_str
            })
        
        processed_groups.append({
            "parent_str": group_parent,
            "paths": group_paths  # 组内路径按原始编号顺序
        })

    # 步骤4：按原始编号1-20拼接最终消息（确保顺序不变）
    msg = "找到以下匹配的文件夹，请输入序号选择：\n\n"
    # 用字典暂存所有路径（key=原始编号，value=（父目录，子路径））
    seq_path_dict = {}
    for group in processed_groups:
        parent = group["parent_str"]
        for path in group["paths"]:
            seq_path_dict[path["orig_seq"]] = (parent, path["sub_path"])

    # 按编号1-20依次遍历，显示结果
    last_parent = None  # 避免重复显示父目录
    for orig_seq in range(1, len(seq_path_dict) + 1):
        parent, sub_path = seq_path_dict[orig_seq]
        
        # 父目录变化时，显示新父目录
        if parent != last_parent:
            msg += f"📁 {parent}\n"
            last_parent = parent
        
        # 显示编号和子路径
        msg += f"      {orig_seq}：{sub_path}\n"

        # 组间空行（判断下一个编号的父目录是否变化）
        next_seq = orig_seq + 1
        if next_seq in seq_path_dict:
            next_parent = seq_path_dict[next_seq][0]
            if next_parent != parent:
                msg += "\n"

    msg += "\n请输入序号（例：1）选择，多选用空格分隔（例：1 2 3）"
    return msg




def perform_search(client, keyword, user_id, chat_id):
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(search_123_files(client, keyword))
        if not results:
            reply_thread_pool.submit(send_message_with_id, chat_id, "没有找到匹配的文件夹")
            return
        user_state_manager.set_state(user_id, "SELECTING_FILE", json.dumps(results))
        # 构建符合要求的结果消息
        #message = "找到以下匹配的文件夹，请输入序号选择：\n"  # 移除多余空行
        #for i, item in enumerate(results, 1):
            # 仅显示序号和完整路径，无其他信息
            #message += f"{i}. {item['path']}\n"  # 路径直接取自item['path']
        #message += "\n请输入序号（例如：1）来选择需要分享的文件夹\n支持多选，以空格分隔（例如1 2 3 4 5）"
        #logger.info(message)
        #print(results)
        folder_message = build_folder_message(results)
        logger.info("搜索结果合并完成")
        reply_thread_pool.submit(send_message_with_id, chat_id, folder_message)
    except Exception as e:
        reply_thread_pool.submit(send_message_with_id, chat_id, f"搜索文件夹失败: {str(e)}")
        logger.error(f"搜索文件夹失败: {str(e)}")
from add_mag import submit_magnet_video_download
def add_magnet_links(client:P123Client, text, upload_dir=None, message=None):
    """识别文本中的多个磁力链接并添加到离线下载

    :param client: P123Client实例
    :param text: 包含磁力链接的文本
    :param upload_dir: 保存到目录的id
    :return: 接口响应信息，包含成功提交的链接数量
    """
    import re
    # 精确匹配32/40位哈希，避免后面多字符
    magnet_pattern = r'magnet:\?xt=urn:btih:(?:[A-Fa-f0-9]{40}(?![A-Fa-f0-9])|[A-Za-z0-9]{32}(?![A-Za-z0-9]))(?:&.*?)?'
    # 提取所有磁力链接
    magnet_links = re.findall(magnet_pattern, text)
    magnet_links = list(set(magnet_links))
    if not magnet_links:
        return {'status': 'error', 'message': '未找到磁力链接', 'added_count': 0}
    logger.debug(f"找到磁力链接:{magnet_links}")
    if message:
        reply_thread_pool.submit(send_reply, message, f"找到{len(magnet_links)}条磁力链\n{magnet_links}\n正在添加，请耐心等待")
    added_count = 0
    responses = []
    try:
        # 依次提交每个磁力链接
        for link in magnet_links:
            response = submit_magnet_video_download(link, client.token, upload_dir)
            ##response = client.offline_add(
            #    url=link,
            #    upload_dir=upload_dir,
             #   async_=False
            #)
            time.sleep(0.5)
            # 保存链接和响应的对应关系
            responses.append({'link': link, 'response': response})
            added_count += 1
        return {'status': 'success', 'data': responses, 'added_count': added_count}
    except Exception as e:
        return {'status': 'error', 'message': f'添加磁力链接失败: {str(e)}', 'added_count': added_count}
import base64
import binascii
import re

def robust_normalize_md5(input_str):
    """
    自动识别MD5格式并转换为十六进制格式，异常时返回原始输入
    
    参数:
        input_str: 待处理的输入（可以是任何类型）
    
    返回:
        转换后的十六进制MD5（小写），或原始输入（处理失败时）
    """
    # 先检查是否为字符串类型，非字符串直接返回原始值
    if not isinstance(input_str, str):
        return input_str
    
    # 处理空字符串
    if not input_str:
        return input_str
    
    # 去除首尾空格
    processed_str = input_str.strip()
    
    # 检查是否为十六进制MD5（32位，仅含0-9、a-f、A-F）
    hex_pattern = re.compile(r'^[0-9a-fA-F]{32}$')
    if hex_pattern.match(processed_str):
        return processed_str.lower()
    
    # 尝试Base64解码处理
    try:
        # 尝试Base64解码（处理标准Base64和URL安全的Base64）
        binary_data = base64.b64decode(processed_str, validate=True)
        
        # 验证MD5固定长度（16字节）
        if len(binary_data) == 16:
            # 转换为十六进制字符串（小写）
            return binascii.hexlify(binary_data).decode('utf-8').lower()
    
    # 捕捉Base64解码相关异常
    except binascii.Error:
        pass
    # 捕捉其他可能的异常
    except Exception:
        pass
    
    # 所有处理失败，返回原始输入
    return input_str

def parse_share_link(message, share_link, up_load_pid=UPLOAD_JSON_TARGET_PID, send_messages=True):
    """解析秒传链接"""
    if '#' and '$' in share_link:
        None
    else:
        return False
    logger.info("解析秒传链接...")
    common_base_path = ""
    is_common_path_format = False
    is_v2_etag_format = False
    LEGACY_FOLDER_LINK_PREFIX_V1 = "123FSLinkV1$"
    LEGACY_FOLDER_LINK_PREFIX_V2 = "123FSLinkV2$"
    COMMON_PATH_LINK_PREFIX_V1 = "123FLCPV1$"
    COMMON_PATH_LINK_PREFIX_V2 = "123FLCPV2$"
    COMMON_PATH_DELIMITER = "%"
    
    if share_link.startswith(COMMON_PATH_LINK_PREFIX_V2):
        is_common_path_format = True
        is_v2_etag_format = True
        share_link = share_link[len(COMMON_PATH_LINK_PREFIX_V2):]
    elif share_link.startswith(COMMON_PATH_LINK_PREFIX_V1):
        is_common_path_format = True
        share_link = share_link[len(COMMON_PATH_LINK_PREFIX_V1):]
    elif share_link.startswith(LEGACY_FOLDER_LINK_PREFIX_V2):
        is_v2_etag_format = True
        share_link = share_link[len(LEGACY_FOLDER_LINK_PREFIX_V2):]
    elif share_link.startswith(LEGACY_FOLDER_LINK_PREFIX_V1):
        share_link = share_link[len(LEGACY_FOLDER_LINK_PREFIX_V1):]
    if is_common_path_format:
        delimiter_pos = share_link.find(COMMON_PATH_DELIMITER)
        if delimiter_pos > -1:
            common_base_path = share_link[:delimiter_pos]
            share_link = share_link[delimiter_pos + 1:]
    files = []
    for s_link in share_link.split('$'):
        if not s_link:
            continue
        parts = s_link.split('#')
        if len(parts) < 3:
            continue
        etag = parts[0]
        size = parts[1]
        file_path = '#'.join(parts[2:])
        if is_common_path_format and common_base_path:
            file_path = common_base_path + file_path
        files.append({
            "etag": etag,
            "size": int(size),
            "file_name": file_path,
            "is_v2_etag": is_v2_etag_format
        })
    
    logger.info(f"解析到 {len(files)} 个文件")
    
    if not files:
        # 使用线程池发送回复
        #if send_messages:
            #reply_thread_pool.submit(send_reply, message, "未找到可转存的文件。")
        return False
    status = True
    # 使用线程池发送回复
    if send_messages:
        reply_thread_pool.submit(send_reply_delete, message, f"开始转存 {len(files)} 个文件...")
    
    try:
        # 开始计时
        start_time = time.time()
        
        # 初始化123客户端
        client = init_123_client()
        
        # 转存文件
        results = []
        total_files = len(files)
        message_batch = []  # 用于存储每批消息
        batch_size = 0      # 批次大小计数器
        total_size = 0      # 累计成功转存文件体积(字节)
        skip_count = 0      # 跳过的重复文件数量
        last_etag = None    # 上一个成功转存文件的etag
        
        # 创建文件夹缓存
        folder_cache = {}
        # 使用UPLOAD_TARGET_PID作为根目录
        target_dir_id = up_load_pid
        
        for i, file_info in enumerate(files):
            file_path = file_info.get('file_name', '')
            etag = file_info.get('etag', '')
            size = int(file_info.get('size', 0))
            is_v2_etag = file_info.get('is_v2_etag', False)
            
            if not all([file_path, etag, size]):
                results.append({
                    "success": False,
                    "file_name": file_path or "未知文件",
                    "error": "文件信息不完整"
                })
                continue
            
            try:
                # 处理文件路径
                path_parts = file_path.split('/')
                file_name = path_parts.pop()
                parent_id = target_dir_id
                
                # 创建目录结构
                current_path = ""
                for part in path_parts:
                    if not part:
                        continue
                    
                    current_path = f"{current_path}/{part}" if current_path else part
                    cache_key = f"{parent_id}/{current_path}"
                    
                    # 检查缓存
                    if cache_key in folder_cache:
                        parent_id = folder_cache[cache_key]
                        continue
                    
                    # 创建新文件夹（带重试）
                    retry_count = 3
                    folder = None
                    while retry_count > 0:
                        try:
                            folder = client.fs_mkdir(part, parent_id=parent_id, duplicate=1)
                            time.sleep(0.2)
                            check_response(folder)
                            break
                        except Exception as e:
                            retry_count -= 1
                            logger.warning(f"创建文件夹 {part} 失败 (剩余重试: {retry_count}): {str(e)}")
                            time.sleep(31)
                    
                    if not folder:
                        logger.warning(f"创建文件夹失败: {part}，将使用当前目录")
                    else:
                        folder_id = folder["data"]["Info"]["FileId"]
                        folder_cache[cache_key] = folder_id
                        parent_id = folder_id
                
                # 处理ETag
                if is_v2_etag:
                    # 实现Base62 ETag转Hex
                    etag = optimized_etag_to_hex(etag, True)
                
                # 秒传文件（带重试）
                retry_count = 3
                rapid_resp = None
                while retry_count > 0:
                    # 检查etag是否与上一个成功转存的文件相同
                    if last_etag == etag:
                        skip_count += 1
                        logger.info(f"跳过重复文件: {file_path}")
                        rapid_resp = {"data": {"Reuse": True, "Skip": True}, "code": 0}  # 标记为跳过
                        break
                    
                    try:
                        rapid_resp = client.upload_file_fast(
                            file_name=file_name,
                            parent_id=parent_id,
                            file_md5=robust_normalize_md5(etag),
                            file_size=size,
                            duplicate=1
                        )
                        check_response(rapid_resp)
                        break
                    except Exception as e:
                        retry_count -= 1
                        logger.warning(f"转存文件 {file_name} 失败 (剩余重试: {retry_count}): {str(e)}")
                        if rapid_resp and ("同名文件" in rapid_resp.get("message", {})):
                            if send_messages:
                                reply_thread_pool.submit(send_reply, message, rapid_resp.get("message", {}))
                            break
                        if rapid_resp and ("Etag" in rapid_resp.get("message", {})):
                            break
                        time.sleep(31)
                
                #if rapid_resp and rapid_resp.get("data", {}):
                if rapid_resp is None:
                    # 处理所有重试失败且 rapid_resp 为 None 的场景
                    error_msg = "秒传失败：接口返回空值且重试耗尽"
                    results.append({
                        "success": False,
                        "file_name": file_path,
                        "error": error_msg
                    })
                    dir_path, file_name = os.path.split(file_path)
                    msg = {
                        'status': '❌',
                        'dir': dir_path,
                        'file': f"{file_name} ({error_msg})"
                    }
                    message_batch.append(msg)
                    batch_size += 1
                    logger.error(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                elif rapid_resp.get("code") == 0 and rapid_resp.get("data", {}) and rapid_resp.get("data", {}).get("Reuse", False):
                    # 检查是否是跳过的文件
                    if rapid_resp.get("data", {}).get("Skip"):
                        # 解析路径结构
                        dir_path, file_name = os.path.split(file_path)
                        msg = {
                            'status': '🔄',
                            'dir': dir_path,
                            'file': f"{file_name} (重复跳过)"
                        }
                        message_batch.append(msg)
                        batch_size += 1
                        logger.info(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                    else:
                        # 更新上一个成功转存文件的etag
                        last_etag = etag
                        results.append({
                            "success": True,
                            "file_name": file_path,
                            "file_id": rapid_resp.get("data", {}).get("FileId", ""),
                            "size": size
                        })
                        total_size += size
                        # 解析路径结构
                        dir_path, file_name = os.path.split(file_path)
                        msg = {
                            'status': '✅',
                            'dir': dir_path,
                            'file': file_name
                        }
                        message_batch.append(msg)
                        batch_size += 1
                        logger.info(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                else:
                    results.append({
                        "success": False,
                        "file_name": file_path,
                        "error": "此文件在123服务器不存在，无法秒传" if rapid_resp.get("data", {}) and (rapid_resp.get("data", {}).get("Reuse", True) == False) else rapid_resp.get("message", "未知错误")
                    })
                    # 解析路径结构
                    dir_path, file_name = os.path.split(file_path)
                    error_msg = "此文件在123服务器不存在，无法秒传" if rapid_resp.get("data", {}) and (rapid_resp.get("data", {}).get("Reuse", True) == False) else rapid_resp.get("message", "未知错误")
                    msg = {
                        'status': '❌',
                        'dir': dir_path,
                        'file': f"{file_name} ({error_msg})"
                    }
                    message_batch.append(msg)
                    batch_size += 1
                    logger.warning(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                
                # 每10条消息发送一次
                if batch_size % 10 == 0:
                    # 生成树状结构消息
                    tree_messages = defaultdict(lambda: {'✅': [], '❌': [], '🔄': []})
                    for entry in message_batch:
                        tree_messages[entry['dir']][entry['status']].append(entry['file'])
                    
                    batch_msg = []
                    for dir_path, status_files in tree_messages.items():
                        for status, files in status_files.items():
                            if files:
                                batch_msg.append(f"--- {status} {dir_path}")
                                for i, file in enumerate(files):
                                    prefix = '      └──' if i == len(files)-1 else '      ├──'
                                    batch_msg.append(f"{prefix} {file}")
                    batch_msg = "\n".join(batch_msg)
                    if send_messages:
                        reply_thread_pool.submit(send_reply_delete, message, f"📊 {batch_size}/{total_files} ({int(batch_size/total_files*100)}%) 个文件已处理\n\n{batch_msg}")
                    message_batch = []
                time.sleep(1/get_int_env("ENV_FILE_PER_SECOND", 5))  # 避免限流
            
            except Exception as e:
                results.append({
                    "success": False,
                    "file_name": file_path,
                    "error": str(e)
                })
                # 解析路径结构
                dir_path, file_name = os.path.split(file_path)
                msg = {
                    'status': '❌',
                    'dir': dir_path,
                    'file': f"{file_name} ({str(e)})"
                }
                message_batch.append(msg)
                batch_size += 1
                logger.warning(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                time.sleep(3)
        
        # 发送剩余的消息
        if message_batch:
            # 生成树状结构消息
            tree_messages = defaultdict(lambda: {'✅': [], '❌': [], '🔄': []})
            for entry in message_batch:
                tree_messages[entry['dir']][entry['status']].append(entry['file'])
            
            batch_msg = []
            for dir_path, status_files in tree_messages.items():
                for status, files in status_files.items():
                    if files:
                        batch_msg.append(f"--- {status} {dir_path}")
                        for i, file in enumerate(files):
                            prefix = '      └──' if i == len(files)-1 else '      ├──'
                            batch_msg.append(f"{prefix} {file}")
            batch_msg = "\n".join(batch_msg)
            if send_messages:
                reply_thread_pool.submit(send_reply_delete, message, f"📊 {batch_size}/{total_files} (100%) 个文件已处理\n\n{batch_msg}")
        
        # 计算耗时
        end_time = time.time()
        elapsed_time = round(end_time - start_time, 2)
        
        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count
        
        # 发送最终结果
        result_msg = f"✅ 秒传链接转存完成！\n✅成功: {success_count}个\n❌失败: {fail_count}个\n🔄跳过重复文件: {skip_count}个\n📁共 {total_files} 个文件\n"
        # 将字节转换为GB并保留两位小数
        result_msg += f"📊成功转存体积: {total_size / (1024 ** 3):.2f}GB\n📊平均文件大小: {total_size / (1024 ** 3)/total_files:.2f}GB\n⏱️耗时: {elapsed_time} 秒"
        result_msg_error = ""
        # 添加失败文件和失败原因
        if fail_count > 0:
            # 收集所有失败的文件和原因
            fail_files = [(r['file_name'], r['error']) for r in results if not r['success']]
            
            # 限制消息长度，Telegram消息有长度限制
            max_fail_files = 10  # 最多显示10个失败文件
            show_fail_files = fail_files[:max_fail_files]
            
            result_msg_error = "❌失败文件列表："
            for file_name, error in show_fail_files:
                # 截断过长的文件名和错误信息
                display_name = file_name
                display_error = error
                result_msg_error += f"\n- {display_name}: {display_error}"
            
            # 如果有更多失败文件，提示用户
            if len(fail_files) > max_fail_files:
                result_msg_error += f"\n\n... 还有 {len(fail_files) - max_fail_files} 个失败文件未显示 ..."
        
        if send_messages:
            reply_thread_pool.submit(send_reply, message, result_msg)
            if result_msg_error:
                reply_thread_pool.submit(send_reply, message, result_msg_error)
                status = False
        else:
            if result_msg_error:
                reply_thread_pool.submit(send_message, result_msg_error)
                status = False
        #print(result_msg)
        
    except Exception as e:
        logger.error(f"处理秒传链接异常: {str(e)}")
        if send_messages:
            reply_thread_pool.submit(send_reply, message, f"处理秒传链接时发生错误: {str(e)}")
        else:
            reply_thread_pool.submit(send_message, f"处理秒传链接时发生错误: {str(e)}")
        status = False
    
    return status

def extract_123_links_from_full_text(message_str):
    """
    提取符合条件的123系列秒传链接
    特征：以123FSLinkV1/2、123FLCPV1/2开头，以文本形式\n（字符串"\\n"）或🔍为结束标志
          若未匹配到结束标志，则自动匹配到文本末尾
    :param message_str: 完整的原始字符串
    :return: 匹配到的链接列表（去重并保留原始顺序）
    """
    # 构建正则：
    # 1. 匹配指定开头 (123FSLinkV1/2 或 123FLCPV1/2)
    # 2. .*? 非贪婪匹配任意字符（包括实际换行，因启用DOTALL）
    # 3. (?=\\n|🔍|$) 正向预查：匹配到文本"\\n"、"🔍"或文本末尾时停止（不包含结束标志本身）
    # 注意：正则中用\\n表示文本中的"\n"（需转义反斜杠）
    link_pattern = re.compile(
        r'(123FSLinkV[12]|123FLCPV[12]).*?(?=\\n|\'}|\',|$)',
        re.DOTALL  # 让.匹配实际换行符（若文本中存在）
    )

    # 提取所有匹配的链接
    matched_links = [match.group(0) for match in link_pattern.finditer(message_str)]
    
    # 去重并保留原始顺序
    return list(dict.fromkeys(matched_links))

def extract_kuake_target_url(text):
    # 匹配标准夸克链接（http/https开头，提取核心share_id）
    link_pattern = r'https?://pan\.quark\.cn/s/([\w-]+)(?:[#?].*)?'
    # 匹配链接自带的pwd参数
    pwd_in_link_pattern = r'[?&]pwd=(\w+)'
    # 匹配文本中的提取码（兼容多种格式）
    pwd_text_pattern = r'提取码[：:]?\s*(\w+)'

    # 关键优化1：用集合记录已处理的share_id，避免重复添加同一链接
    processed_share_ids = set()
    link_info_list = []
    
    for match in re.finditer(link_pattern, text, re.IGNORECASE):
        share_id = match.group(1)
        if not share_id or share_id in processed_share_ids:  # 重复share_id直接跳过
            continue
        
        original_link = match.group(0)
        built_in_pwd = re.search(pwd_in_link_pattern, original_link).group(1) if re.search(pwd_in_link_pattern, original_link) else None
        
        link_info_list.append({"share_id": share_id.strip(), "built_in_pwd": built_in_pwd})
        processed_share_ids.add(share_id)  # 标记为已处理

    # 提取文本提取码（去重保序）
    passwords = list(dict.fromkeys(re.findall(pwd_text_pattern, text, re.IGNORECASE)))

    # 生成标准化链接
    processed_links = []
    for idx, info in enumerate(link_info_list):
        base_url = f"https://pan.quark.cn/s/{info['share_id']}"
        # 关键优化2：确保pwd匹配逻辑不错位（优先自带pwd，无则按索引取文本pwd）
        final_pwd = info['built_in_pwd']
        if not final_pwd and idx < len(passwords):
            final_pwd = passwords[idx]
        
        final_url = f"{base_url}?pwd={final_pwd}" if final_pwd else base_url
        processed_links.append(final_url)

    # 最终去重（保序）
    return list(dict.fromkeys(processed_links))

from quark_export_share import export_share_info
from share import TMDBHelper
tmdb = TMDBHelper()
# 创建锁对象确保文件依次转存
link_process_lock = threading.Lock()
@bot.message_handler(content_types=['text', 'photo'])
def handle_general_message(message):
    logger.info("进入handle_general_message")
    user_id = message.from_user.id
    if user_id != TG_ADMIN_USER_ID:
        reply_thread_pool.submit(send_reply, message, "您没有权限使用此机器人。")
        return
    
    with link_process_lock:
        text = f"{message}"
        client = init_123_client()             
        # 执行匹配
        full_links = extract_123_links_from_full_text(text)
        if full_links:
            for link in full_links:
                parse_share_link(message, link)
            user_state_manager.clear_state(user_id)
            return
        # 调用函数并获取返回值
        result = add_magnet_links(client,text,get_int_env("ENV_123_MAGNET_UPLOAD_PID", 0),message)

        # 根据返回值状态执行不同的print
        if result['status'] == 'success':
            success_count = 0
            fail_count = 0
            fail_messages = []
            
            # 检查每个链接的添加结果
            for item in result['data']:
                link = item['link']
                response = item['response']
                if isinstance(response, dict) and response.get('code') == 0:
                    success_count += 1
                else:
                    fail_count += 1
                    # 截取链接的前40个字符作为标识
                    link_identifier = link
                    msg = f"\n{link_identifier}: {response.get('message', '未知错误')}" if isinstance(response, dict) else f"{link_identifier}: {str(response)}"
                    fail_messages.append(msg)
            
            # 打印结果
            logger.info(f"123磁力链接添加结果: 成功{success_count}个, 失败{fail_count}个")
            if fail_count > 0:
                logger.error(f"失败详情:{', '.join(fail_messages)}")
                reply_thread_pool.submit(send_reply, message, f"123磁力链接添加部分失败: 成功{success_count}个, 失败{fail_count}个\n失败详情: {', '.join(fail_messages)}")
            else:
                reply_thread_pool.submit(send_reply, message, f"123磁力链接添加成功: 共添加了{success_count}个链接")
            user_state_manager.clear_state(user_id)
            return
        else:
            if result['message'] == '未找到磁力链接':
                #logger.info("未找到任何磁力链接")
                None
            else:
                logger.error(f"123磁力链接添加失败: {result['message']}")
                reply_thread_pool.submit(send_reply_delete, message, f"123磁力链接添加失败: {result['message']}")
                user_state_manager.clear_state(user_id)
                return
        if "提取码" in text and "www.123" in text:
            reply_thread_pool.submit(send_reply, message, f"仅支持形如 https://www.123pan.com/s/abcde-fghi?pwd=ABCD 的提取码格式")
            return
        target_urls = extract_target_url(text)
        if target_urls:
            reply_thread_pool.submit(send_reply_delete, message, f"发现{len(target_urls)}个123分享链接，开始转存...")
            success_count = 0
            fail_count = 0
            for url in target_urls:
                try:
                    result = transfer_shared_link_optimize(client, url, UPLOAD_LINK_TARGET_PID)
                    if result:
                        success_count += 1
                        logger.info(f"转存成功: {url}")
                    else:
                        fail_count += 1
                        logger.error(f"转存失败: {url}")
                except Exception as e:
                    fail_count += 1
                    logger.error(f"转存异常: {url}, 错误: {str(e)}")
                    
            #time.sleep(3)
            reply_thread_pool.submit(send_reply, message, f"转存完成：成功{success_count}个，失败{fail_count}个")
            user_state_manager.clear_state(user_id)
            return
        
        target_urls = extract_kuake_target_url(text)
        if target_urls:
            if not os.getenv("ENV_KUAKE_COOKIE", ""):
                logger.error(f"请填写夸克COOKIE")
                reply_thread_pool.submit(send_reply, message, f"请填写夸克COOKIE")
                return
            reply_thread_pool.submit(send_reply, message, f"发现{len(target_urls)}个夸克分享链接，开始尝试秒传到123...")
            success_count = 0   
            fail_count = 0
            for url in target_urls:
                try:
                    json_data = export_share_info(url,os.getenv("ENV_KUAKE_COOKIE", ""))
                    if json_data:
                        save_json_file_quark(message,json_data)
                        #parse_share_link(message, kuake_link, get_int_env("ENV_123_KUAKE_UPLOAD_PID", 0))                
                    else:
                        logger.error(f"夸克分享转存123出错")
                        reply_thread_pool.submit(send_reply, message, f"夸克分享转存123出错")
                except Exception as e:
                    fail_count += 1
                    logger.error(f"转存异常: {url}, 错误: {str(e)}")
            #time.sleep(3)
            #reply_thread_pool.submit(send_reply, message, f"转存完成：成功{success_count}个，失败{fail_count}个")
            user_state_manager.clear_state(user_id)
            return

        from tgto189 import extract_target_url as  extract_target_url_189
        from tgto189 import save_189_link
        target_urls = extract_target_url_189(text)
        if target_urls:
            reply_thread_pool.submit(send_reply_delete, message, f"发现{len(target_urls)}个天翼云盘分享链接，开始转存...")
            success_count = 0
            fail_count = 0
            for url in target_urls:
                try:                    
                    result = save_189_link(client189, url, os.getenv("ENV_189_LINK_UPLOAD_PID","-11"))
                    if result:
                        success_count += 1
                        logger.info(f"转存成功: {url}")
                    else:
                        fail_count += 1
                        logger.error(f"转存失败: {url}")
                except Exception as e:
                    fail_count += 1
                    logger.error(f"转存异常: {url}, 错误: {str(e)}")
            #time.sleep(3)
            reply_thread_pool.submit(send_reply, message, f"转存完成：成功{success_count}个，失败{fail_count}个")
            user_state_manager.clear_state(user_id)
            return
        from tgto115 import extract_target_url as  extract_target_url_115
        from tgto115 import transfer_shared_link as  transfer_shared_link_115
        from tgto115 import init_115_client
        target_urls = extract_target_url_115(text)
        if target_urls:
            reply_thread_pool.submit(send_reply_delete, message, f"发现{len(target_urls)}个115分享链接，开始转存...")
            client = init_115_client()
            success_count = 0
            fail_count = 0
            for url in target_urls:
                try:
                    result = transfer_shared_link_115(client, url, os.getenv("ENV_115_LINK_UPLOAD_PID","0"))
                    if result:
                        success_count += 1
                        logger.info(f"转存成功: {url}")
                    else:
                        fail_count += 1
                        logger.error(f"转存失败: {url}")
                except Exception as e:
                    fail_count += 1
                    logger.error(f"转存异常: {url}, 错误: {str(e)}")
            reply_thread_pool.submit(send_reply, message, f"转存完成：成功{success_count}个，失败{fail_count}个")
            user_state_manager.clear_state(user_id)
            return
        if message.content_type == 'photo':
            user_state_manager.clear_state(user_id)
            reply_thread_pool.submit(send_reply, message, f"该条消息未找到分享链接、秒传链接、秒传JSON、磁力链等有效内容")
            return
    
    state, data = user_state_manager.get_state(user_id)
    if state == "SELECTING_FILE":
        try:
            raw_text = message.text.strip()
            text = raw_text.replace('　', ' ').strip()
            full_width = '０１２３４５６７８９'
            half_width = '0123456789'
            trans_table = str.maketrans(full_width, half_width)
            text = text.translate(trans_table)
            try:
                # 支持空格分隔的多个数字，如 "1 2 3 5"
                selections = [int(num) - 1 for num in text.split()]
                if not selections:
                    raise ValueError("请至少输入一个有效的序号")
                # 检查是否有重复的序号
                if len(selections) != len(set(selections)):
                    raise ValueError("序号不能重复")
            except ValueError as e:
                if "invalid literal" in str(e):
                    raise ValueError("请输入有效的数字序号（例如：1 2 3 4），不要包含字母或符号")
                else:
                    raise e

            results = json.loads(data)
            if not results:
                reply_thread_pool.submit(send_reply, message, "搜索结果已失效，请重新搜索")
                user_state_manager.clear_state(user_id)
                return
            
            # 验证所有选择是否在有效范围内
            for idx in selections:
                if not (0 <= idx < len(results)):
                    raise ValueError(f"序号 {idx+1} 超出范围，请重新输入")
            
            # 初始化客户端（只需初始化一次）
            client = init_123_client()
            
            # 遍历所有选择的文件夹
            for selection in selections:
                selected_item = results[selection]
                file_id = selected_item['id']
                folder_name = selected_item['name']
                logger.info(f"选中文件夹ID: {file_id}, 名称: {folder_name}")
                # 只为第一个文件夹发送创建分享链接的消息，避免重复
                if selection == selections[0]:
                    reply_thread_pool.submit(send_reply, message, f"正在为 {len(selections)} 个文件夹创建分享链接...")
                if get_int_env("ENV_MAKE_NEW_LINK", 1):
                    existing_share = get_existing_shares(client, folder_name)
                else:
                    existing_share = None
                if existing_share:
                    # 尝试获取TMDB元数据
                    file_name=get_first_video_file(client, file_id)
                    metadata = tmdb.get_metadata_optimize(folder_name, file_name)
                    share_data = {
                        "share_url": f"{existing_share['url']}{'?pwd=' + existing_share['password'] if existing_share['password'] else ''}",
                        "folder_name": folder_name,
                        "file_id": file_id  # 选中的文件夹ID，用于后续查询文件
                    }

                    if not metadata:
                        logger.warning(f"未获取到TMDB元数据: {folder_name}/{file_name}")
                        reply_thread_pool.submit(send_message_with_id, message.chat.id, f"未获取到TMDB元数据，不予分享，请规范文件夹名: {folder_name}/{file_name}")
                        user_state_manager.clear_state(user_id)
                        return

                    # 仅当metadata存在且title在folder_name中时才执行
                    if metadata:
                        # 使用封装函数构建消息
                        share_message, share_message2, poster_url, files = build_share_message(metadata, client, file_id, folder_name, file_name, existing_share)

                        # 发送图片和消息
                        try:
                            bot.send_photo(message.chat.id, poster_url, caption=share_message, parse_mode='HTML')
                            if TOKENSHARE:
                                botshare.send_photo(TARGET_CHAT_ID_SHARE, poster_url, caption=share_message, parse_mode='HTML')
                        except Exception as e:
                            logger.error(f"发送图片失败: {str(e)}")
                            reply_thread_pool.submit(send_message_with_id, message.chat.id, share_message)
                    else:
                        files = get_directory_files(client, file_id, folder_name)
                        # 使用原来的消息格式
                        share_message = f"✅ 已存在分享链接：\n{folder_name}\n"
                        share_message += f"链接：{existing_share['url']}{'?pwd=' + existing_share['password'] if existing_share['password'] else ''}\n"
                        if existing_share['password']:
                            share_message += f"提取码：{existing_share['password']}\n"
                        share_message += f"过期时间：{existing_share['expiry']}"
                        reply_thread_pool.submit(send_message_with_id, message.chat.id, share_message)

                    if AUTO_MAKE_JSON:
                        try:
                            # 获取文件夹内文件列表
                            #files = get_directory_files(client, file_id, folder_name)
                            if not files:
                                logger.warning(f"文件夹为空: {folder_name}")
                            else:
                                # 创建JSON结构
                                # 计算总文件数和总体积
                                total_files_count = len(files)
                                total_size = sum(file_info["size"] for file_info in files)

                                json_data = {
                                    "commonPath": f"{folder_name}/",
                                    "usesBase62EtagsInExport": False,
                                    "totalFilesCount": total_files_count,
                                    "totalSize": total_size,
                                    "files": [
                                        {
                                            "path": file_info["path"],
                                            "etag": file_info["etag"],
                                            "size": file_info["size"]
                                        }
                                        for file_info in files
                                    ]
                                }
                                # 保存JSON文件
                                json_file_path = f"{folder_name}.json"
                                with open(json_file_path, 'w', encoding='utf-8') as f:
                                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                                # 发送JSON文件
                                # 将字节转换为GB (1GB = 1024^3 B)
                                total_size_gb = total_size / (1024 ** 3)
                                size_str = f"{total_size_gb:.2f}GB"
                                with open(json_file_path, 'rb') as f:
                                    # 计算平均文件大小
                                    avg_size = total_size / total_files_count if total_files_count > 0 else 0
                                    avg_size_gb = avg_size / (1024 ** 3)
                                    avg_size_str = f"{avg_size_gb:.2f}GB" if avg_size_gb >= 0.01 else f"{avg_size / (1024 ** 2):.2f}MB"
                                    if metadata:
                                        bot.send_document(message.chat.id, f, caption=share_message2, parse_mode='HTML')
                                        if TOKENSHARE:
                                            f.seek(0)  # 重置文件指针到开头
                                            botshare.send_document(TARGET_CHAT_ID_SHARE, f, caption=share_message2, parse_mode='HTML')
                                    else:
                                        bot.send_document(message.chat.id, f, caption=f"📁 {folder_name}\n📝文件数: {total_files_count}个\n📦总体积: {size_str}\n📊平均文件大小: {avg_size_str}")
                                # 删除临时文件
                                os.remove(json_file_path)
                        except Exception as e:
                            logger.error(f"生成或发送JSON文件失败: {str(e)}")
                            reply_thread_pool.submit(send_message_with_id, message.chat.id, f"生成文件列表失败，请重试")
                    
                    
                    if os.getenv("ENV_123PANFX_COOKIE","") and len(selections)==1:
                        user_state_manager.set_state(user_id, "ASK_POST", json.dumps(share_data))
                        ask_msg = "是否需要将该内容发布到论坛？\n1. 放弃发帖\n2. 发送到电影板块\n3. 发送到电视剧板块\n4. 发送到动漫板块"
                        reply_thread_pool.submit(send_message_with_id, message.chat.id, ask_msg)
                    #else:
                        #bot.send_message(message.chat.id, "tgto123：如需自动发贴功能，请配置123panfx.com的Cookie")
                    #user_state_manager.clear_state(user_id)
                    #return
                else:
                    # 尝试获取TMDB元数据
                    file_name = get_first_video_file(client,file_id)
                    metadata = tmdb.get_metadata_optimize(folder_name, file_name)
                    porn_result = None

                    if not metadata:
                        logger.warning(f"未获取到TMDB元数据: {folder_name}/{file_name}")
                        reply_thread_pool.submit(send_message_with_id, message.chat.id, f"未获取到TMDB元数据，不予分享，请规范文件夹名: {folder_name}/{file_name}")
                        user_state_manager.clear_state(user_id)
                        return
                    # 检查内容是否涉及色情
                    if os.getenv("AI_API_KEY", ""):
                        porn_result = check_porn_content(folder_name+"/"+file_name+"："+metadata.get('plot'))
                    else:
                        porn_result = check_porn_content(
                                        content=folder_name+"/"+file_name+"："+metadata.get('plot'),
                                        api_url="https://api.edgefn.net",
                                        api_key="",
                                        model_name="",
                                        max_tokens=15000
                                    )
                    
                    # 根据检测结果决定后续操作
                    if porn_result and porn_result['is_pornographic']:
                        logger.warning(f"检测到色情内容，已拒绝分享: {folder_name}")
                        reply_thread_pool.submit(send_message_with_id, message.chat.id, f"影视介绍中检测到涉及色情内容，拒绝分享，判断依据：{porn_result['reason']}")
                        user_state_manager.clear_state(user_id)
                        return
                    
                    # 非色情内容，继续创建分享链接
                    share_info = create_share_link(client, file_id)
                    share_data = {
                        "share_url": share_info["url"],
                        "folder_name": folder_name,
                        "file_id": file_id  # 选中的文件夹ID，用于后续查询文件
                    }

                    # 仅当metadata存在且title在folder_name中时才执行
                    if metadata:
                        # 使用封装函数构建消息
                        share_message, share_message2, poster_url, files = build_share_message(metadata, client, file_id, folder_name, file_name, share_info)

                        # 发送图片和消息
                        try:
                            bot.send_photo(message.chat.id, poster_url, caption=share_message, parse_mode='HTML')
                            if TOKENSHARE:
                                botshare.send_photo(TARGET_CHAT_ID_SHARE, poster_url, caption=share_message, parse_mode='HTML')
                        except Exception as e:
                            logger.error(f"发送图片失败: {str(e)}")
                            reply_thread_pool.submit(send_message_with_id, message.chat.id, share_message)
                    else:
                        files = get_directory_files(client, file_id, folder_name)
                        # 使用原来的消息格式
                        share_message = f"✅ 分享链接已创建：\n{folder_name}\n"
                        share_message += f"链接：{share_info['url']}\n"
                        if share_info['password']:
                            share_message += f"提取码：{share_info['password']}\n"
                        share_message += f"过期时间：{share_info['expiry']}"
                        reply_thread_pool.submit(send_message_with_id, message.chat.id, share_message)
                    if AUTO_MAKE_JSON:
                        # 生成JSON文件
                        try:
                            # 获取文件夹内文件列表
                            #files = get_directory_files(client, file_id, folder_name)
                            if not files:
                                logger.warning(f"文件夹为空: {folder_name}")
                            else:                                                               # 计算总文件数和总体积
                                total_files_count = len(files)
                                total_size = sum(file_info["size"] for file_info in files)
                                # 创建JSON结构
                                json_data = {
                                    "commonPath": f"{folder_name}/",
                                    "usesBase62EtagsInExport": False,
                                    "totalFilesCount": total_files_count,
                                    "totalSize": total_size,
                                    "files": [
                                        {
                                            "path": file_info["path"],
                                            "etag": file_info["etag"],
                                            "size": file_info["size"]
                                        }
                                        for file_info in files
                                    ]
                                }
                                # 保存JSON文件
                                json_file_path = f"{folder_name}.json"
                                with open(json_file_path, 'w', encoding='utf-8') as f:
                                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                                # 发送JSON文件

                                # 将字节转换为GB并保留两位小数
                                total_size_gb = total_size / (1024 ** 3)
                                size_str = f"{total_size_gb:.2f}GB"
                                
                                with open(json_file_path, 'rb') as f:
                                    # 计算平均文件大小
                                    avg_size = total_size / total_files_count if total_files_count > 0 else 0
                                    avg_size_gb = avg_size / (1024 ** 3)
                                    avg_size_str = f"{avg_size_gb:.2f}GB" if avg_size_gb >= 0.01 else f"{avg_size / (1024 ** 2):.2f}MB"
                                    if metadata:
                                        bot.send_document(message.chat.id, f, caption=share_message2, parse_mode='HTML')
                                        if TOKENSHARE:
                                            f.seek(0)
                                            botshare.send_document(TARGET_CHAT_ID_SHARE, f, caption=share_message2, parse_mode='HTML')
                                    else:
                                        bot.send_document(message.chat.id, f, caption=f"📁 {folder_name}\n📝文件数: {total_files_count}个\n📦总体积: {size_str}\n📊平均文件大小: {avg_size_str}")
                                # 删除临时文件
                                os.remove(json_file_path)
                        except Exception as e:
                            logger.error(f"生成或发送JSON文件失败: {str(e)}")
                            reply_thread_pool.submit(send_message_with_id, message.chat.id, f"生成文件列表失败，请重试")
                    if os.getenv("ENV_123PANFX_COOKIE","") and len(selections)==1:
                        user_state_manager.set_state(user_id, "ASK_POST", json.dumps(share_data))
                        ask_msg = "是否需要将该内容发布到论坛？\n1. 放弃发帖\n2. 发送到电影板块\n3. 发送到电视剧板块\n4. 发送到动漫板块"
                        reply_thread_pool.submit(send_message_with_id, message.chat.id, ask_msg)
                    #else:
                        #bot.send_message(message.chat.id, "tgto123：如需自动发贴功能，请配置123panfx.com的Cookie")
                    #user_state_manager.clear_state(user_id)

            #else:
                #raise ValueError(f"序号超出范围，请输入 1-{len(results)} 之间的数字")
        except ValueError as e:
            reply_thread_pool.submit(send_reply, message, str(e))
        except Exception as e:
            reply_thread_pool.submit(send_reply, message, f"创建分享链接失败: 请检查文件夹是否为空，{str(e)}")
            logger.error(f"创建分享链接失败: {str(e)}")
    elif state == "ASK_POST":
        try:
            selection = message.text.strip()
            if selection not in ["1", "2", "3", "4"]:
                raise ValueError("请输入1、2、3或4选择操作")
            #global json
            # 解析保存的分享数据
            share_data = json.loads(data)
            share_url = share_data["share_url"]
            folder_name = share_data["folder_name"]
            file_id = share_data["file_id"]

            if selection == "1":
                # 放弃发帖
                reply_thread_pool.submit(send_reply, message, "已取消发帖")
                user_state_manager.clear_state(user_id)
            else:
                # 确定媒体类型（2=电影，3=电视剧）
                # 根据选择确定媒体类型：2->电影，3->动画，其他->电视剧
                if selection == "2":
                    media_type = "movie"  # 选择2：电影
                elif selection == "3":
                    media_type = "tv"  # 选择3：电视剧
                elif selection == "4":
                    media_type = "anime"  # 选择4：动漫
                else:
                    media_type = None  # 选择1：放弃（无需处理）

                # 获取第一个视频文件名称
                reply_thread_pool.submit(send_reply, message, "正在查找视频文件以确定影视的分辨率及音频等信息...")
                client = init_123_client()
                file_name = get_first_video_file(client, file_id)
                if not file_name:
                    reply_thread_pool.submit(send_reply, message, "未找到视频文件，无法发帖")
                    user_state_manager.clear_state(user_id)
                    return

                # 调用share.py中的post_to_forum发布
                from share import post_to_forum
                reply_thread_pool.submit(send_reply, message, "正在发布到论坛...")
                success, forum_url = post_to_forum(
                    share_url=share_url,
                    folder_name=folder_name,
                    file_name=file_name,
                    media_type=media_type
                )

                # 反馈结果
                if success:
                    reply_thread_pool.submit(send_reply, message, f"发帖成功！\n{folder_name}\n社区链接：{forum_url}\n123资源社区因您的分享而更美好❤️")
                else:
                    reply_thread_pool.submit(send_reply, message, f"发帖失败，{forum_url}, 请重试")
                user_state_manager.clear_state(user_id)

        except ValueError as e:
            reply_thread_pool.submit(send_reply, message, str(e))
        except Exception as e:
            reply_thread_pool.submit(send_reply, message, f"操作失败: {str(e)}")
            logger.error(f"处理发帖选择错误: {e}")
    else:
        reply_thread_pool.submit(send_reply, message, f"🚀 欢迎使用tgto123网盘助手 v{version}！\n项目地址：https://github.com/walkingddd/tgto123-public 觉得好用能否帮忙点个小星星\n\n{USE_METHOD}")



# 新增函数：查询已存在的未失效分享链接
def get_existing_shares(client: P123Client, folder_name: str) -> dict:
    """查询已存在的未失效分享链接"""
    shares = []
    last_share_id = 0
    try:
        while True:
            # 调用分享列表API
            response = requests.get(
                f"https://open-api.123pan.com/api/v1/share/list?limit=100&lastShareId={last_share_id}",
                headers={
                    'Authorization': f'Bearer {client.token}',
                    'Platform': 'open_platform'
                },
                timeout=TIMEOUT
            )
            data = response.json()

            if data.get('code') != 0:
                logger.error(f"获取分享列表失败: {data.get('message')}")
                break

            # 提取当前页分享数据
            share_list = data.get('data', {}).get('shareList', [])
            shares.extend(share_list)

            # 处理分页
            last_share_id = data.get('data', {}).get('lastShareId', -1)
            if last_share_id == -1:
                break  # 已到最后一页

        # 筛选出名称匹配且未失效的分享
        for share in shares:
            if (share.get('shareName') == folder_name and
                    share.get('expired') == 0 and  # expired=0表示未失效
                    share.get('expiration', '') > '2050-06-30 00:00:00'):  # 过期时间大于2050-06-30 00:00:00
                return {
                    "url": f"https://www.123pan.com/s/{share.get('shareKey')}",
                    "password": share.get('sharePwd'),
                    "expiry": "永久有效"
                }

        # 未找到匹配的有效分享
        return None

    except Exception as e:
        logger.error(f"查询已存在分享失败: {str(e)}")
        return None


@bot.message_handler(content_types=['document'], func=lambda message: message.document.mime_type == 'application/json' or message.document.file_name.endswith('.json'))
def process_json_file(message):
    with link_process_lock:  # 获取锁，确保多个请求依次处理
        user_id = message.from_user.id
        if user_id != TG_ADMIN_USER_ID:
            # 使用线程池发送回复
            reply_thread_pool.submit(send_reply, message, "您没有权限使用此功能。")
            return
        logger.info("进入转存json\n")
        try:
            # 开始计时
            start_time = time.time()
            
            file_retry_count = 0
            # 获取文件ID
            while file_retry_count < 10:
                try:
                    file_id = message.document.file_id
                    file_info = bot.get_file(file_id)
                    file_path = file_info.file_path
                    break
                except Exception as e:
                    logger.error(f"从TG获取文件失败，尝试重试: {str(e)}")
                    file_retry_count += 1
                    time.sleep(30)

            # 下载JSON文件
            json_url = f'https://api.telegram.org/file/bot{TG_BOT_TOKEN}/{file_path}'
            response = requests.get(json_url)
            json_data = response.json()

            # 提取commonPath、files、totalFilesCount和totalSize
            common_path = json_data.get('commonPath', '').strip()
            if common_path.endswith('/'):
                common_path = common_path[:-1]
            files = json_data.get('files', [])
            uses_v2_etag = json_data.get('usesBase62EtagsInExport', False)
            total_files_count = json_data.get('totalFilesCount', len(files))
            total_size_json = json_data.get('totalSize', 0)

            if not files:
                # 使用线程池发送回复
                reply_thread_pool.submit(send_reply, message, "JSON文件中没有找到文件信息。")
                return

            # 使用线程池发送回复
            reply_thread_pool.submit(send_reply_delete, message, f"开始转存JSON文件中的{len(files)}个文件...")
            start_time = time.time()
            # 初始化123客户端
            client = init_123_client()

            # 转存文件
            results = []
            total_files = len(files)
            message_batch = []  # 用于存储每批消息(包括成功和失败)
            batch_size = 0      # 批次大小计数器
            total_size = 0      # 累计成功转存文件体积(字节)
            skip_count = 0      # 跳过的重复文件数量
            last_etag = None    # 上一个成功转存文件的etag

            # 创建文件夹缓存
            folder_cache = {}
            target_dir_name = common_path if common_path else 'JSON转存'
            # 使用UPLOAD_TARGET_PID作为根目录
            target_dir_id = UPLOAD_JSON_TARGET_PID

            for i, file_info in enumerate(files):
                file_path = file_info.get('path', '')
                
                # 构建完整文件路径
                if common_path:
                    file_path = f"{common_path}/{file_path}"
                etag = file_info.get('etag', '')
                size = int(file_info.get('size', 0))

                if not all([file_path, etag, size]):
                    results.append({
                        "success": False,
                        "file_name": file_path or "未知文件",
                        "error": "文件信息不完整"
                    })
                    continue

                try:
                    # 处理文件路径
                    path_parts = file_path.split('/')
                    file_name = path_parts.pop()
                    parent_id = target_dir_id

                    # 创建目录结构
                    current_path = ""
                    for part in path_parts:
                        if not part:
                            continue

                        current_path = f"{current_path}/{part}" if current_path else part
                        cache_key = f"{parent_id}/{current_path}"

                        # 检查缓存
                        if cache_key in folder_cache:
                            parent_id = folder_cache[cache_key]
                            continue

                        # 创建新文件夹（带重试）
                        retry_count = 3
                        folder = None
                        while retry_count > 0:
                            try:
                                folder = client.fs_mkdir(part, parent_id=parent_id, duplicate=1)     
                                time.sleep(0.2)                  
                                check_response(folder)
                                break
                            except Exception as e:
                                retry_count -= 1
                                logger.warning(f"创建文件夹 {part} 失败 (剩余重试: {retry_count}): {str(e)}")
                                time.sleep(31)

                        if not folder:
                            logger.warning(f"创建文件夹失败: {part}，将使用当前目录")
                        else:
                            folder_id = folder["data"]["Info"]["FileId"]
                            folder_cache[cache_key] = folder_id
                            parent_id = folder_id
                        #time.sleep(1/get_int_env("ENV_FILE_PER_SECOND", 5))  # 避免限流

                    # 处理ETag
                    if uses_v2_etag:
                        # 实现Base62 ETag转Hex（参考123pan_bot中的实现）
                        etag = optimized_etag_to_hex(etag, True)

                    # 秒传文件（带重试）
                    retry_count = 3
                    rapid_resp = None
                    while retry_count > 0:
                        # 检查etag是否与上一个成功转存的文件相同
                        if last_etag == etag:
                            skip_count += 1
                            logger.info(f"跳过重复文件: {file_path}")
                            rapid_resp = {"data": {"Reuse": True, "Skip": True}, "code": 0}  # 标记为跳过
                            break
                        
                        try:
                            rapid_resp = client.upload_file_fast(
                                file_name=file_name,
                                parent_id=parent_id,
                                file_md5=robust_normalize_md5(etag),
                                file_size=size,
                                duplicate=1
                            )
                            check_response(rapid_resp)
                            break
                        except Exception as e:
                            retry_count -= 1
                            logger.warning(f"转存文件 {file_name} 失败 (剩余重试: {retry_count}): {str(e)}")
                            if rapid_resp and ("Etag" in rapid_resp.get("message", {})):
                                break                            
                            time.sleep(31)

                    if rapid_resp is None:
                        # 处理所有重试失败且 rapid_resp 为 None 的场景
                        error_msg = "秒传失败：接口返回空值且重试耗尽"
                        results.append({
                            "success": False,
                            "file_name": file_path,
                            "error": error_msg
                        })
                        dir_path, file_name = os.path.split(file_path)
                        msg = {
                            'status': '❌',
                            'dir': dir_path,
                            'file': f"{file_name} ({error_msg})"
                        }
                        message_batch.append(msg)
                        batch_size += 1
                        logger.error(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                    elif rapid_resp.get("code") == 0 and rapid_resp.get("data", {}) and rapid_resp.get("data", {}).get("Reuse", False):
                        # 检查是否是跳过的文件
                        if rapid_resp.get("data", {}).get("Skip"):
                            # 解析路径结构
                            dir_path, file_name = os.path.split(file_path)
                            msg = {
                                'status': '🔄',
                                'dir': dir_path,
                                'file': f"{file_name} (重复跳过)"
                            }
                            message_batch.append(msg)
                            batch_size += 1
                            logger.info(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                        else:
                            # 更新上一个成功转存文件的etag
                            last_etag = etag
                            results.append({
                                "success": True,
                                "file_name": file_path,
                                "file_id": rapid_resp.get("data", {}).get("FileId", ""),
                                "size": size
                            })
                            total_size += size
                            # 解析路径结构
                            dir_path, file_name = os.path.split(file_path)
                            msg = {
                                'status': '✅',
                                'dir': dir_path,
                                'file': file_name
                            }
                            message_batch.append(msg)
                            batch_size += 1
                            logger.info(f"{msg['status']}:{msg['dir']}/{msg['file']}")

                    else:
                        results.append({
                            "success": False,
                            "file_name": file_path,
                            "error": "此文件在123服务器不存在，无法秒传" if rapid_resp.get("data", {}) and (rapid_resp.get("data", {}).get("Reuse", True) == False) else rapid_resp.get("message", "未知错误")
                        })
                        # 解析路径结构
                        dir_path, file_name = os.path.split(file_path)
                        msg = {
                            'status': '❌',
                            'dir': dir_path,
                            'file': f"{file_name} ({"此文件在123服务器不存在，无法秒传" if rapid_resp.get("data", {}) and (rapid_resp.get("data", {}).get("Reuse", True) == False) else rapid_resp.get("message", "未知错误")})"
                        }
                        message_batch.append(msg)
                        batch_size += 1
                        logger.info(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                                        
                    # 每10条消息发送一次
                    if batch_size % 10 == 0:
                        # 生成树状结构消息
                        tree_messages = defaultdict(lambda: {'✅': [], '❌': [], '🔄': []})
                        for entry in message_batch:
                            tree_messages[entry['dir']][entry['status']].append(entry['file'])
                        
                        batch_msg = []
                        for dir_path, status_files in tree_messages.items():
                            for status, files in status_files.items():
                                if files:
                                    batch_msg.append(f"--- {status} {dir_path}")
                                    for i, file in enumerate(files):
                                        prefix = '      └──' if i == len(files)-1 else '      ├──'
                                        batch_msg.append(f"{prefix} {file}")
                        batch_msg = "\n".join(batch_msg)
                        reply_thread_pool.submit(send_reply_delete, message, f"📊 {batch_size}/{total_files_count} ({int(batch_size/total_files_count*100)}%) 个文件已处理\n\n{batch_msg}")
                        message_batch = []
                    time.sleep(1/get_int_env("ENV_FILE_PER_SECOND", 5))  # 避免限流

                except Exception as e:
                        # 解析路径结构
                        dir_path, file_name = os.path.split(file_path)
                        msg = {
                            'status': '❌',
                            'dir': dir_path,
                            'file': f"{file_name} ({str(e)})"
                        }
                        message_batch.append(msg)
                        batch_size += 1
                        logger.info(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                        results.append({
                            "success": False,
                            "file_name": file_path,
                            "error": str(e)
                        })
                        # 每10条消息发送一次
                        if batch_size % 10 == 0:
                            # 生成树状结构消息
                            tree_messages = defaultdict(lambda: {'✅': [], '❌': [], '🔄': []})
                            for entry in message_batch:
                                tree_messages[entry['dir']][entry['status']].append(entry['file'])
                            
                            batch_msg = []
                            for dir_path, status_files in tree_messages.items():
                                for status, files in status_files.items():
                                    if files:
                                        batch_msg.append(f"--- {status} {dir_path}")
                                        for i, file in enumerate(files):
                                            prefix = '      └──' if i == len(files)-1 else '      ├──'
                                            batch_msg.append(f"{prefix} {file}")
                            batch_msg = "\n".join(batch_msg)
                            reply_thread_pool.submit(send_reply_delete, message, f"📊 {batch_size}/{total_files_count} ({int(batch_size/total_files_count*100)}%) 个文件已处理\n\n{batch_msg}")
                            message_batch = []
                        time.sleep(1/get_int_env("ENV_FILE_PER_SECOND", 5))  # 避免限流

            # 发送剩余的消息
            if message_batch:
                # 生成树状结构消息
                tree_messages = defaultdict(lambda: {'✅': [], '❌': [], '🔄': []})
                for entry in message_batch:
                    tree_messages[entry['dir']][entry['status']].append(entry['file'])
                
                batch_msg = []
                for dir_path, status_files in tree_messages.items():
                    for status, files in status_files.items():
                        if files:
                            batch_msg.append(f"--- {status} {dir_path}")
                            for i, file in enumerate(files):
                                prefix = '      └──' if i == len(files)-1 else '      ├──'
                                batch_msg.append(f"{prefix} {file}")
                batch_msg = "\n".join(batch_msg)
                reply_thread_pool.submit(send_reply_delete, message, f"📊 {batch_size}/{total_files_count} ({int(batch_size/total_files_count*100)}%) 个文件已处理\n\n{batch_msg}")

            # 结束计时并计算耗时
            end_time = time.time()
            elapsed_time = end_time - start_time
            hours, remainder = divmod(int(elapsed_time), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            # 发送转存结果
            success_count = sum(1 for r in results if r['success'])
            fail_count = len(results) - success_count

            # 将字节转换为GB (1GB = 1024^3 B)
            total_size_gb = total_size / (1024 ** 3)
            size_str = f"{total_size_gb:.2f}GB"

            # 处理JSON文件中的总体积
            total_size_json_gb = total_size_json / (1024 ** 3)
            total_size_json_str = f"{total_size_json_gb:.2f}GB"

            # 计算平均文件大小
            avg_size = total_size / success_count if success_count > 0 else 0
            avg_size_gb = avg_size / (1024 ** 3)
            avg_size_str = f"{avg_size_gb:.2f}GB" if avg_size_gb >= 0.01 else f"{avg_size / (1024 ** 2):.2f}MB"
            # 添加跳过的重复文件数量显示
            result_msg = f"✅ JSON文件转存完成！\n✅成功: {success_count}个\n❌失败: {fail_count}个\n🔄跳过同一目录下的重复文件: {skip_count}个\n📊成功转存体积: {size_str}\n📊平均文件大小: {avg_size_str}\n📝JSON文件理论文件数: {total_files_count}个\n📦JSON文件理论总体积: {total_size_json_str}\n📁目标目录: {target_dir_name}\n⏱️耗时: {time_str}"
            reply_thread_pool.submit(send_reply, message, f"{result_msg}")
            time.sleep(0.5)
            # 添加失败文件详情
            if fail_count > 0:
                failed_files = []
                for result in results:
                    if not result["success"]:
                        # 简化文件名显示
                        file_name = result["file_name"]
                        failed_files.append(f"• {file_name}（失败原因：{result['error']}）")
                # 分批发送所有失败文件，每批最多10个
                batch_size = 10

                for idx in range(0, len(failed_files), batch_size):
                    batch = failed_files[idx:idx+batch_size]
                    batch_msg = "❌ 失败文件 (批次 {}/{}):\n".format((idx//batch_size)+1, (len(failed_files)+batch_size-1)//batch_size) + "\n".join(batch)
                    reply_thread_pool.submit(send_reply, message, batch_msg)
                    time.sleep(0.5)
        except Exception as e:
            logger.error(f"处理JSON文件失败: {str(e)}")
            reply_thread_pool.submit(send_reply, message, f"❌ 处理JSON文件失败:\n{str(e)}")

def save_json_file_quark(message,json_data):
    logger.info("进入123转存夸克")
    try:
        # 开始计时
        start_time = time.time()
        # 提取commonPath、files、totalFilesCount和totalSize
        common_path = json_data.get('commonPath', '').strip()
        if common_path.endswith('/'):
            common_path = common_path[:-1]
        files = json_data.get('files', [])
        uses_v2_etag = json_data.get('usesBase62EtagsInExport', False)
        total_files_count = json_data.get('totalFilesCount', len(files))
        total_size_json = json_data.get('totalSize', 0)

        if not files:
            # 使用线程池发送回复
            reply_thread_pool.submit(send_reply, message, "夸克分享中没有找到文件信息。")
            return

        # 使用线程池发送回复
        reply_thread_pool.submit(send_reply_delete, message, f"开始123转存夸克文件中的{len(files)}个文件...")
        start_time = time.time()
        # 初始化123客户端
        client = init_123_client()

        # 转存文件
        results = []
        total_files = len(files)
        message_batch = []  # 用于存储每批消息(包括成功和失败)
        batch_size = 0      # 批次大小计数器
        total_size = 0      # 累计成功转存文件体积(字节)
        skip_count = 0      # 跳过的重复文件数量
        last_etag = None    # 上一个成功转存文件的etag

        # 创建文件夹缓存
        folder_cache = {}
        target_dir_name = common_path if common_path else 'JSON转存'
        # 使用UPLOAD_TARGET_PID作为根目录
        target_dir_id = get_int_env("ENV_123_KUAKE_UPLOAD_PID", 0)

        for i, file_info in enumerate(files):
            file_path = file_info.get('path', '')
            
            # 构建完整文件路径
            if common_path:
                file_path = f"{common_path}/{file_path}"
            etag = file_info.get('etag', '')
            size = int(file_info.get('size', 0))

            if not all([file_path, etag, size]):
                results.append({
                    "success": False,
                    "file_name": file_path or "未知文件",
                    "error": "文件信息不完整"
                })
                continue

            try:
                # 处理文件路径
                path_parts = file_path.split('/')
                file_name = path_parts.pop()
                parent_id = target_dir_id

                # 创建目录结构
                current_path = ""
                for part in path_parts:
                    if not part:
                        continue

                    current_path = f"{current_path}/{part}" if current_path else part
                    cache_key = f"{parent_id}/{current_path}"

                    # 检查缓存
                    if cache_key in folder_cache:
                        parent_id = folder_cache[cache_key]
                        continue

                    # 创建新文件夹（带重试）
                    retry_count = 3
                    folder = None
                    while retry_count > 0:
                        try:
                            folder = client.fs_mkdir(part, parent_id=parent_id, duplicate=1)     
                            time.sleep(0.2)                  
                            check_response(folder)
                            break
                        except Exception as e:
                            retry_count -= 1
                            logger.warning(f"创建文件夹 {part} 失败 (剩余重试: {retry_count}): {str(e)}")
                            time.sleep(31)

                    if not folder:
                        logger.warning(f"创建文件夹失败: {part}，将使用当前目录")
                    else:
                        folder_id = folder["data"]["Info"]["FileId"]
                        folder_cache[cache_key] = folder_id
                        parent_id = folder_id
                    #time.sleep(1/get_int_env("ENV_FILE_PER_SECOND", 5))  # 避免限流

                # 处理ETag
                if uses_v2_etag:
                    # 实现Base62 ETag转Hex（参考123pan_bot中的实现）
                    etag = optimized_etag_to_hex(etag, True)

                # 秒传文件（带重试）
                retry_count = 3
                rapid_resp = None
                while retry_count > 0:
                    # 检查etag是否与上一个成功转存的文件相同
                    if last_etag == etag:
                        skip_count += 1
                        logger.info(f"跳过重复文件: {file_path}")
                        rapid_resp = {"data": {"Reuse": True, "Skip": True}, "code": 0}  # 标记为跳过
                        break
                    
                    try:
                        rapid_resp = client.upload_file_fast(
                            file_name=file_name,
                            parent_id=parent_id,
                            file_md5=robust_normalize_md5(etag),
                            file_size=size,
                            duplicate=1
                        )
                        check_response(rapid_resp)
                        break
                    except Exception as e:
                        retry_count -= 1
                        logger.warning(f"转存文件 {file_name} 失败 (剩余重试: {retry_count}): {str(e)}")
                        if rapid_resp and ("同名文件" in rapid_resp.get("message", {})):
                            reply_thread_pool.submit(send_reply, message, rapid_resp.get("message", {}))
                        if rapid_resp and ("Etag" in rapid_resp.get("message", {})):
                            break
                        if rapid_resp and ("文件信息" in rapid_resp.get("message", {})):
                            reply_thread_pool.submit(send_reply, message, "请检查夸克的Cookie是否过期，或是否添加- NO_PROXY=*.quark.cn")
                            break
                        time.sleep(31)

                if rapid_resp is None:
                    # 处理所有重试失败且 rapid_resp 为 None 的场景
                    error_msg = "秒传失败：接口返回空值且重试耗尽"
                    results.append({
                        "success": False,
                        "file_name": file_path,
                        "error": error_msg
                    })
                    dir_path, file_name = os.path.split(file_path)
                    msg = {
                        'status': '❌',
                        'dir': dir_path,
                        'file': f"{file_name} ({error_msg})"
                    }
                    message_batch.append(msg)
                    batch_size += 1
                    logger.error(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                elif rapid_resp.get("code") == 0 and rapid_resp.get("data", {}) and rapid_resp.get("data", {}).get("Reuse", False):
                    # 检查是否是跳过的文件
                    if rapid_resp.get("data", {}).get("Skip"):
                        # 解析路径结构
                        dir_path, file_name = os.path.split(file_path)
                        msg = {
                            'status': '🔄',
                            'dir': dir_path,
                            'file': f"{file_name} (重复跳过)"
                        }
                        message_batch.append(msg)
                        batch_size += 1
                        logger.info(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                    else:
                        # 更新上一个成功转存文件的etag
                        last_etag = etag
                        results.append({
                            "success": True,
                            "file_name": file_path,
                            "file_id": rapid_resp.get("data", {}).get("FileId", ""),
                            "size": size
                        })
                        total_size += size
                        # 解析路径结构
                        dir_path, file_name = os.path.split(file_path)
                        msg = {
                            'status': '✅',
                            'dir': dir_path,
                            'file': file_name
                        }
                        message_batch.append(msg)
                        batch_size += 1
                        logger.info(f"{msg['status']}:{msg['dir']}/{msg['file']}")

                else:
                    results.append({
                        "success": False,
                        "file_name": file_path,
                        "error": "此文件在123服务器不存在，无法秒传" if rapid_resp.get("data", {}) and (rapid_resp.get("data", {}).get("Reuse", True) == False) else rapid_resp.get("message", "未知错误")
                    })
                    # 解析路径结构
                    dir_path, file_name = os.path.split(file_path)
                    msg = {
                        'status': '❌',
                        'dir': dir_path,
                        'file': f"{file_name} ({"此文件在123服务器不存在，无法秒传" if rapid_resp.get("data", {}) and (rapid_resp.get("data", {}).get("Reuse", True) == False) else rapid_resp.get("message", "未知错误")})"
                    }
                    message_batch.append(msg)
                    batch_size += 1
                    logger.info(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                                    
                # 每10条消息发送一次
                if batch_size % 10 == 0:
                    # 生成树状结构消息
                    tree_messages = defaultdict(lambda: {'✅': [], '❌': [], '🔄': []})
                    for entry in message_batch:
                        tree_messages[entry['dir']][entry['status']].append(entry['file'])
                    
                    batch_msg = []
                    for dir_path, status_files in tree_messages.items():
                        for status, files in status_files.items():
                            if files:
                                batch_msg.append(f"--- {status} {dir_path}")
                                for i, file in enumerate(files):
                                    prefix = '      └──' if i == len(files)-1 else '      ├──'
                                    batch_msg.append(f"{prefix} {file}")
                    batch_msg = "\n".join(batch_msg)
                    reply_thread_pool.submit(send_reply_delete, message, f"📊 {batch_size}/{total_files_count} ({int(batch_size/total_files_count*100)}%) 个文件已处理\n\n{batch_msg}")
                    message_batch = []
                time.sleep(1/get_int_env("ENV_FILE_PER_SECOND", 5))  # 避免限流

            except Exception as e:
                    # 解析路径结构
                    dir_path, file_name = os.path.split(file_path)
                    msg = {
                        'status': '❌',
                        'dir': dir_path,
                        'file': f"{file_name} ({str(e)})"
                    }
                    message_batch.append(msg)
                    batch_size += 1
                    logger.info(f"{msg['status']}:{msg['dir']}/{msg['file']}")
                    results.append({
                        "success": False,
                        "file_name": file_path,
                        "error": str(e)
                    })
                    # 每10条消息发送一次
                    if batch_size % 10 == 0:
                        # 生成树状结构消息
                        tree_messages = defaultdict(lambda: {'✅': [], '❌': [], '🔄': []})
                        for entry in message_batch:
                            tree_messages[entry['dir']][entry['status']].append(entry['file'])
                        
                        batch_msg = []
                        for dir_path, status_files in tree_messages.items():
                            for status, files in status_files.items():
                                if files:
                                    batch_msg.append(f"--- {status} {dir_path}")
                                    for i, file in enumerate(files):
                                        prefix = '      └──' if i == len(files)-1 else '      ├──'
                                        batch_msg.append(f"{prefix} {file}")
                        batch_msg = "\n".join(batch_msg)
                        reply_thread_pool.submit(send_reply_delete, message, f"📊 {batch_size}/{total_files_count} ({int(batch_size/total_files_count*100)}%) 个文件已处理\n\n{batch_msg}")
                        message_batch = []
                    time.sleep(1/get_int_env("ENV_FILE_PER_SECOND", 5))  # 避免限流

        # 发送剩余的消息
        if message_batch:
            # 生成树状结构消息
            tree_messages = defaultdict(lambda: {'✅': [], '❌': [], '🔄': []})
            for entry in message_batch:
                tree_messages[entry['dir']][entry['status']].append(entry['file'])
            
            batch_msg = []
            for dir_path, status_files in tree_messages.items():
                for status, files in status_files.items():
                    if files:
                        batch_msg.append(f"--- {status} {dir_path}")
                        for i, file in enumerate(files):
                            prefix = '      └──' if i == len(files)-1 else '      ├──'
                            batch_msg.append(f"{prefix} {file}")
            batch_msg = "\n".join(batch_msg)
            reply_thread_pool.submit(send_reply_delete, message, f"📊 {batch_size}/{total_files_count} ({int(batch_size/total_files_count*100)}%) 个文件已处理\n\n{batch_msg}")

        # 结束计时并计算耗时
        end_time = time.time()
        elapsed_time = end_time - start_time
        hours, remainder = divmod(int(elapsed_time), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # 发送转存结果
        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count

        # 将字节转换为GB (1GB = 1024^3 B)
        total_size_gb = total_size / (1024 ** 3)
        size_str = f"{total_size_gb:.2f}GB"

        # 处理JSON文件中的总体积
        total_size_json_gb = total_size_json / (1024 ** 3)
        total_size_json_str = f"{total_size_json_gb:.2f}GB"

        # 计算平均文件大小
        avg_size = total_size / success_count if success_count > 0 else 0
        avg_size_gb = avg_size / (1024 ** 3)
        avg_size_str = f"{avg_size_gb:.2f}GB" if avg_size_gb >= 0.01 else f"{avg_size / (1024 ** 2):.2f}MB"
        # 添加跳过的重复文件数量显示
        result_msg = f"✅ 123转存夸克完成！\n✅成功: {success_count}个\n❌失败: {fail_count}个\n🔄跳过同一目录下的重复文件: {skip_count}个\n📊成功转存体积: {size_str}\n📊平均文件大小: {avg_size_str}\n📝夸克分享理论文件数: {total_files_count}个\n⏱️耗时: {time_str}"
        reply_thread_pool.submit(send_reply, message, f"{result_msg}")
        time.sleep(0.5)
        # 添加失败文件详情
        if fail_count > 0:
            failed_files = []
            for result in results:
                if not result["success"]:
                    # 简化文件名显示
                    file_name = result["file_name"]
                    failed_files.append(f"• {file_name}（失败原因：{result['error']}）")
            # 分批发送所有失败文件，每批最多10个
            batch_size = 10

            for idx in range(0, len(failed_files), batch_size):
                batch = failed_files[idx:idx+batch_size]
                batch_msg = "❌ 失败文件 (批次 {}/{}):\n".format((idx//batch_size)+1, (len(failed_files)+batch_size-1)//batch_size) + "\n".join(batch)
                reply_thread_pool.submit(send_reply, message, batch_msg)
                time.sleep(0.5)
    except Exception as e:
        logger.error(f"处理夸克文件失败: {str(e)}")
        reply_thread_pool.submit(send_reply, message, f"❌ 处理夸克文件失败:\n{str(e)}")

# Base62字符表（123云盘V2 API使用）
BASE62_CHARS = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

def optimized_etag_to_hex(etag, is_v2=False):
    """将Base62编码的ETag转换为十六进制格式（参考123pan_bot中的实现）"""
    if not is_v2:
        return etag
    
    try:
        # 检查是否是有效的MD5格式（32位十六进制）
        if len(etag) == 32 and all(c in '0123456789abcdefABCDEF' for c in etag):
            return etag.lower()
        
        # 转换Base62到十六进制
        num = 0
        for char in etag:
            if char not in BASE62_CHARS:
                logger.error(f"❌ ETag包含无效字符: {char}")
                return etag
            num = num * 62 + BASE62_CHARS.index(char)
        
        # 转换为十六进制并确保32位
        hex_str = hex(num)[2:].lower()
        if len(hex_str) > 32:
            # 取后32位
            hex_str = hex_str[-32:]
            logger.warning(f"ETag转换后长度超过32位，截断为: {hex_str}")
        elif len(hex_str) < 32:
            # 前面补零
            hex_str = hex_str.zfill(32)
            logger.warning(f"ETag转换后不足32位，补零后: {hex_str}")
        
        # 验证是否为有效的MD5
        if len(hex_str) != 32 or not all(c in '0123456789abcdef' for c in hex_str):
            logger.error(f"❌ 转换后ETag格式无效: {hex_str}")
            return etag
        
        return hex_str
    except Exception as e:
        logger.error(f"❌ ETag转换失败: {str(e)}")
        return etag

# 注册文档消息处理器（已移至start_bot_thread函数内部）
# bot.message_handler(content_types=['document'])(process_json_file)

# 定义bot线程变量
bot_thread = None

def start_bot_thread():
    global bot
    # 确保bot实例存在
    if not bot:
        bot = telebot.TeleBot(TG_BOT_TOKEN)
    while True:
        try:
            #bot.polling(none_stop=True, interval=1)
            bot.infinity_polling(logger_level=logging.ERROR)
        except Exception as e:
            logger.warning(f"代理网络不稳定，与TG尝试重连中...\n错误原因:{str(e)}")
    return threading.current_thread()



def check_task():
    global bot_thread
    # 检查bot线程状态（固定20秒检查一次）
    if not bot_thread or not bot_thread.is_alive():
        logger.warning(f"代理网络不稳定，与TG尝试重连中...")
        bot_thread = threading.Thread(target=start_bot_thread, daemon=True)
        bot_thread.start()

if __name__ == "__mp_main__":
    from tgto115 import tg_115monitor
    from tgto189 import tg_189monitor,Cloud189
    client189 = Cloud189()
    ENV_189_CLIENT_ID = os.getenv("ENV_189_CLIENT_ID","")
    ENV_189_CLIENT_SECRET = os.getenv("ENV_189_CLIENT_SECRET","")

    if (ENV_189_CLIENT_ID and ENV_189_CLIENT_SECRET):
        logger.info("天翼云盘正在尝试登录 ...")
        client189.login(ENV_189_CLIENT_ID, ENV_189_CLIENT_SECRET)

def main():     
    from server import app
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=12366, debug=False, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    while (os.getenv("ENV_WEB_PASSPORT", "") == "") or (os.getenv("ENV_123_CLIENT_ID", "") == ""):
        try:
            logger.warning("请检查docker-compose.yml中的 ENV_WEB_PASSPORT 以及配置web页面的 ENV_123_CLIENT_ID 是否填写完整，可前往 https://hub.docker.com/r/walkingd/tgto123 查看部署方法")
            bot.send_message(TG_ADMIN_USER_ID,f"请检查docker-compose.yml中的 ENV_WEB_PASSPORT 以及配置web页面的 ENV_123_CLIENT_ID 是否填写完整，可前往 https://hub.docker.com/r/walkingd/tgto123 查看部署方法")
        except Exception as e:
            logger.error(f"发送消息失败: {str(e)}")
        time.sleep(60)
    threading.Thread(target=ptto123, daemon=True).start()
    #print(f"开始监控: {CHANNEL_URL}")
    logger.info(f"123转存目标目录ID: {UPLOAD_TARGET_PID} | 检查间隔: {CHECK_INTERVAL}分钟")
    init_database()
    client = init_123_client()

    global bot_thread
    # 初始启动bot线程
    bot_thread = threading.Thread(target=start_bot_thread, daemon=True)
    bot_thread.start()
    schedule.every(20).seconds.do(check_task)

    if get_int_env("ENV_189_TGMONITOR_SWITCH", 0):
        
        try:            
            # 读取189清理配置
            env_189_clear_pid = os.getenv("ENV_189_CLEAR_PID", "")
            env_189_clear_period = get_int_env("ENV_189_CLEAR_PERIOD", 6)
            clear_folder_ids = [pid.strip() for pid in env_189_clear_pid.split(",") if pid.strip()]
            
            # 定义定时清理函数
            def clear_189_folders():
                logger.info(f"===== 开始执行天翼云盘文件夹清理任务（{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）=====")
                try:
                    # 尝试删除文件夹内容（不检查登录状态，依赖方法内部处理）
                    for folder_id in clear_folder_ids:
                        logger.info(f"删除文件夹 {folder_id} 中的内容...")
                        try:
                            client189.delete_folder_contents(folder_id)
                            logger.info(f"成功删除文件夹 {folder_id} 中的内容")
                        except Exception as e:
                            logger.error(f"删除文件夹 {folder_id} 内容失败: {str(e)}")
                    
                    # 清空回收站
                    logger.info("清空回收站...")
                    try:
                        if client189.empty_recycle_bin():
                            logger.info("成功执行天翼网盘文件清理任务")
                            reply_thread_pool.submit(send_message, f"✅成功执行天翼网盘清空回收站任务（{datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
                        else:
                            logger.info("天翼网盘文件清理失败")
                            reply_thread_pool.submit(send_message, f"❌天翼网盘清空回收站失败（{datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
                    except Exception as e:
                        logger.error(f"清空回收站失败: {str(e)}")
                        reply_thread_pool.submit(send_message, f"❌天翼网盘清空回收站失败: {str(e)}（{datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
                except Exception as e:
                    logger.error(f"天翼云盘清理任务执行失败: {str(e)}")
                logger.info("===== 天翼云盘文件夹清理任务执行完毕 =====")
            
            # 设置定时任务，每env_189_clear_period小时执行一次
            if clear_folder_ids:
                logger.info(f"设置天翼云盘文件夹定时清理任务，每{env_189_clear_period}小时执行一次")
                schedule.every(env_189_clear_period).hours.do(clear_189_folders)
                # 立即执行一次清理任务
                clear_189_folders()
            else:
                logger.info("未配置ENV_189_CLEAR_PID，跳过天翼云盘文件夹定时清理任务")
        except Exception as e:
            logger.error(f"登录出现错误: {e}")

    try:
        while True:
            logger.info(f"===== 开始检查（{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}），当前版本 {version}=====")
            if AUTHORIZATION:
                client = init_123_client()
                new_messages = get_latest_messages()
                schedule.run_pending()
                if new_messages:
                    for msg in new_messages:
                        message_id, date_str, message_url, target_url, message_text = msg
                        logger.info(f"处理新消息: {message_id} | {target_url}")
                        # 获取排除关键词环境变量（多个关键词用|分隔）
                        # 当排除关键词为空时，全都不排除
                        exclude_filter = os.environ.get('ENV_EXCLUDE_FILTER', '')
                        exclude_pattern = re.compile(exclude_filter) if exclude_filter else None

                        # 检查是否匹配过滤条件且不包含排除关键词
                        is_match = filter_pattern.search(target_url) or filter_pattern.search(message_text)
                        is_excluded = exclude_pattern and (exclude_pattern.search(target_url) or exclude_pattern.search(message_text))

                        if not is_match:
                            status = "未转存"
                            result_msg = f"未匹配过滤条件（{FILTER}），跳过转存"
                            logger.info(result_msg)
                            time.sleep(1)
                        elif is_excluded:
                            status = "未转存"
                            result_msg = f"包含排除关键词（{exclude_filter}），跳过转存"
                            logger.info(result_msg)
                            time.sleep(1)
                        else:
                            logger.info(f"消息匹配过滤条件（{FILTER}），开始转存...")
                            
                            # 二次过滤关键词配置（当某条消息触发转存后，如进一步满足下面的要求，则转移到特定的文件夹）
                            # 格式为：DV:1,DOLBY VISION:2,SSTA:3 即满足DV关键词转移到ID为1的文件夹，满足SSTA关键词转移到ID为3的文件夹
                            # 如果ENV_SECOND_FILTER为空，则全部转移至ENV_123_UPLOAD_PID
                            ENV_SECOND_FILTER = os.getenv("ENV_SECOND_FILTER", "")
                            transfer_id=UPLOAD_TARGET_PID
                            
                            # 根据关键词筛选并设置transfer_id
                            # ENV_SECOND_FILTER.strip() 用于去除字符串前后的空白字符（空格、制表符、换行符等）
                            # 这样可以确保即使环境变量值前后有空格也能正确处理，避免因空白字符导致的逻辑错误
                            # 如果去除空白后字符串不为空，则执行二次过滤逻辑
                            if ENV_SECOND_FILTER.strip():
                                try:
                                    # 解析二次过滤规则，格式为：关键词:文件夹ID,关键词:文件夹ID,...
                                    filter_rules = ENV_SECOND_FILTER.split(',')
                                    for rule in filter_rules:
                                        if ':' in rule:
                                            # 分割关键词和文件夹ID，但保留关键词中的空格（如"DOLBY VISION"中的空格会被保留）
                                            keyword, folder_id = rule.split(':', 1)
                                            # keyword.strip() 用于确保关键词不为空字符串
                                            # 注意：关键词内部的空格（如"DOLBY VISION"中的空格）不会被去除，会作为关键词的一部分进行匹配
                                            if (keyword.strip() and 
                                                (keyword in message_text or 
                                                 (target_url and keyword in target_url))):
                                                transfer_id = int(folder_id.strip())
                                                logger.info(f"消息匹配二次过滤关键词 '{keyword}'，将转存到文件夹ID: {folder_id}")
                                                reply_thread_pool.submit(send_message, f"消息匹配二次过滤关键词 '{keyword}'，将转存到文件夹ID: {folder_id}")
                                                break
                                except Exception as e:
                                    logger.error(f"解析二次过滤规则失败: {e}")
                                    reply_thread_pool.submit(send_message, f"解析二次过滤规则失败: {e}")
                            if target_url:                                
                                result = transfer_shared_link_optimize(client, target_url, transfer_id)
                                if result:
                                    status = "转存成功"
                                    result_msg = f"✅123云盘转存成功\n消息内容: {message_url}\n链接: {target_url}"
                                    reply_thread_pool.submit(send_message, result_msg)
                                else:                               
                                    status = "转存失败"
                                    result_msg = f"❌123云盘转存失败\n消息内容: {message_url}\n链接: {target_url}"
                                    reply_thread_pool.submit(send_message, result_msg)
                            else:
                                full_links = extract_123_links_from_full_text(message_text)
                                if full_links:
                                    for link in full_links:
                                        if parse_share_link(message_text, link, transfer_id, False):
                                            status = "转存成功"
                                            result_msg = f"✅123云盘秒传链接转存成功\n消息内容: {message_url}\n"
                                            reply_thread_pool.submit(send_message, result_msg)
                                        else:
                                            status = "转存失败"
                                            result_msg = f"❌123云盘秒传链接转存失败\n消息内容: {message_url}\n"  
                                            #notifier.send_message(result_msg)     
                                else:
                                    status = "转存失败"
                                    result_msg = f"❌123云盘秒传链接转存失败\n消息内容: {message_url}\n"  
                                    #notifier.send_message(result_msg)     
                            time.sleep(2)
                        save_message(message_id, date_str, message_url, target_url, status, result_msg)
                else:
                    logger.info("未发现新的123分享链接")
            if get_int_env("ENV_115_TGMONITOR_SWITCH", 0):
                tg_115monitor()
            if get_int_env("ENV_189_TGMONITOR_SWITCH", 0):
                tg_189monitor(client189)
            logger.info(f"休息{CHECK_INTERVAL}分钟，当前版本 {version}...")
            total_wait_seconds = CHECK_INTERVAL * 60
            elapsed_seconds = 0
            # 拆分等待时间，每1秒检查一次定时任务（20秒内会检查20次，满足20秒检查一次的需求）
            exit=0
            while elapsed_seconds < total_wait_seconds:
                # 检查是否需要退出（在休息前检查，确保只在记录日志后退出）
                try:
                    # 直接访问should_exit变量而不是通过globals()检查
                    with should_exit.get_lock():
                        if link_process_lock.acquire(blocking=False):
                            try:
                                if should_exit.value:
                                    logger.info("检测到退出标志，子进程将在休息前退出")
                                    exit=1
                                    break   
                            finally:
                                link_process_lock.release()
                except Exception as e:
                    logger.error(f"检查退出标志时发生错误: {str(e)}")
                time.sleep(1)  # 短间隔休眠，保证20秒内至少检查一次
                elapsed_seconds += 1
            if exit:
                break
            try:
                channel_chat = bot.get_chat('@tgto123update')
                # 获取置顶消息（直接访问对象属性，而非字典get）
                pinned_message = channel_chat.pinned_message
                if pinned_message.message_id != newest_id:
                    bot.send_message(TG_ADMIN_USER_ID, f"🚀 tgto123 当前版本为{version}，最新版本请见：\nhttps://t.me/tgto123update/{pinned_message.message_id}")
                    bot.send_message(TG_ADMIN_USER_ID, f"请更新最新版本")
            except Exception as e:
                logger.error(f"转发频道消息失败: {str(e)}")
    except KeyboardInterrupt:
        logger.info("程序已停止")
    except Exception as e:
        logger.error(f"程序异常终止: {str(e)}")
        #notifier.send_message(f"tgto123：程序异常终止: {str(e)}")
from ptto115 import ptto123process
def ptto123():
    while get_int_env("ENV_PTTO123_SWITCH", 0) or get_int_env("ENV_PTTO115_SWITCH", 0):
        try:
            ptto123process()
        except Exception as e:
            logger.error(f"ptto123线程异常终止: {str(e)}")
            bot.send_message(TG_ADMIN_USER_ID, f"ptto123线程异常终止: {str(e)}")
            time.sleep(300)

import threading
import multiprocessing
import signal

if __name__ == "__main__":
    # 设置全局默认模式为 spawn
    multiprocessing.set_start_method('spawn')
# 全局共享标志，用于通知子进程退出
should_exit = multiprocessing.Value('b', False)

# 子进程运行的函数
def run_main(exit_flag):
    # 将共享变量设置为全局变量，以便main函数可以访问
    global should_exit
    should_exit = exit_flag
    try:
        main()
    except Exception as e:
        logger.error(f"子进程运行异常: {str(e)}")

if __name__ == "__main__":
    # 检查db\user.env文件是否存在，如果不存在则从templete.env创建
    user_state_manager.clear_state(TG_ADMIN_USER_ID)
    user_env_path = os.path.join('db', 'user.env')
    if not os.path.exists(user_env_path):
        logger.info(f"user.env文件不存在，从templete.env创建...")
        # 确保db目录存在
        os.makedirs('db', exist_ok=True)
        # 复制templete.env到db目录并重命名为user.env
        if os.path.exists('templete.env'):
            shutil.copy2('templete.env', user_env_path)
            logger.info(f"成功创建user.env文件")
        else:
            logger.warning(f"警告: templete.env文件不存在，无法创建user.env")
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    disclaimer_text = '''⚠️ 免责声明 & 合规说明

        本工具仅为方便网盘分享与转存，所有资源均来自网络用户的公开分享内容：
        - 开发者非资源的上传者、所有者或版权方，不对资源的合法性、准确性、完整性承担责任。
        - 工具内置AI内容识别机制，自动过滤涉政、色情、暴力等违规资源的分享创建，坚决抵制非法内容传播。

        用户在使用本工具时需知悉：
        - 需自行核实资源版权归属，确保合规使用，避免侵犯第三方权益；
        - 对下载、存储、传播资源可能引发的法律纠纷、数据安全风险（如病毒感染）等，由用户自行承担全部责任；
        - 开发者不对上述风险导致的任何损失承担责任；

        - 如您继续使用本工具，则视为已完整阅读、理解并接受以上所有声明内容。'''

    while True:
        try:            
            bot.send_message(TG_ADMIN_USER_ID,f"🚀 tgto123：当前版本 {version}\n项目地址：https://github.com/walkingddd/tgto123-public 觉得好用能否帮忙点个小星星\n\n{USE_METHOD}")
            try:
            # 等待bot对象初始化完成
                if bot:
                    # 获取频道信息（返回Chat对象，而非字典）
                    channel_chat = bot.get_chat('@tgto123update')
                    # 获取置顶消息（直接访问对象属性，而非字典get）
                    pinned_message = channel_chat.pinned_message
                    while True:                    
                        bot.send_message(TG_ADMIN_USER_ID, f"🚀 tgto123 当前版本为{version}，最新版本请见：\nhttps://t.me/tgto123update/{pinned_message.message_id}")
                        bot.send_message(TG_ADMIN_USER_ID,disclaimer_text)
                        if pinned_message.message_id == newest_id:
                            break
                        logger.warning(f"请更新最新版本，否则无法正常使用")
                        bot.send_message(TG_ADMIN_USER_ID, f"请更新最新版本，否则无法正常使用")
                        time.sleep(60)
                break
            except Exception as e:
                logger.error(f"转发频道消息失败: {str(e)}")
        except Exception as e:
            logger.error(f"由于网络等原因无法与TG Bot建立通信，30秒后重试...: {str(e)}")
            time.sleep(30)
    # 主进程控制逻辑
    restart_time = time_datetime(3, 0, 0)  # 设置在每天下午6:50:00重启
    
    # 计算初始的下一次重启时间戳
    def calculate_next_restart_time():
        today = datetime.now().date()
        # 计算今天的重启时间时间戳
        today_restart_time = datetime.combine(today, restart_time).timestamp()
        # 当前时间戳
        now = datetime.now().timestamp()
        # 如果当前时间在今天的重启时间之前，则下一次重启时间为今天重启时间
        # 如果当前时间已过今天的重启时间，则下一次重启时间为明天重启时间
        if now < today_restart_time:
            next_restart = today_restart_time
        else:
            next_restart = datetime.combine(today + timedelta(days=1), restart_time).timestamp()
        return next_restart
    
    next_restart_time = calculate_next_restart_time()
    
    while True:
        try:
            # 创建并启动子进程，传递共享变量
            main_process = multiprocessing.Process(target=run_main, args=(should_exit,))
            main_process.daemon = False
            main_process.start()
            logger.info(f"子进程 {main_process.pid} 已启动")
            logger.info(f"下一次计划清理内存时间: {datetime.fromtimestamp(next_restart_time).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 监控子进程和重启时间
            while main_process.is_alive():
                # 检查是否到达重启时间
                now = datetime.now().timestamp()
                
                if now >= next_restart_time:
                    # 设置退出标志，通知子进程
                    with should_exit.get_lock():
                        should_exit.value = True
                    
                    # 等待子进程退出，最多等待60秒
                    wait_time = 0
                    max_wait = 1800
                    while main_process.is_alive() and wait_time < max_wait:
                        time.sleep(1)
                        wait_time += 1
                    
                    # 如果子进程还在运行，跳过此次重启
                    if main_process.is_alive():
                        logger.warning(f"子进程 {main_process.pid} 未能在规定时间内自行退出,跳过此次重启")
                        with should_exit.get_lock():
                            should_exit.value = False
                        next_restart_time = calculate_next_restart_time()
                        logger.info(f"下一次计划清理内存时间: {datetime.fromtimestamp(next_restart_time).strftime('%Y-%m-%d %H:%M:%S')}")
                        continue

                    # 重置退出标志
                    with should_exit.get_lock():
                        should_exit.value = False                    
                    # 计算下一次重启时间
                    next_restart_time = calculate_next_restart_time()
                    logger.info(f"已完成清理内存，下一次计划清理内存时间: {datetime.fromtimestamp(next_restart_time).strftime('%Y-%m-%d %H:%M:%S')}")
                    break
                
                # 每10秒检查一次
                time.sleep(10)
            
            # 子进程退出后，等待一段时间再重启
            if not main_process.is_alive():
                logger.info(f"子进程 {main_process.pid} 已退出，等待5秒后重启")
                time.sleep(5)
            
        except KeyboardInterrupt:
            logger.info("接收到中断信号，正在终止子进程...")
            if 'main_process' in locals() and main_process.is_alive():
                try:
                    main_process.terminate()
                    main_process.join(timeout=10)
                except Exception as e:
                    logger.error(f"终止子进程时发生错误: {str(e)}")
            logger.info("程序已停止")
            break
