import requests
import os
import logging
from bs4 import BeautifulSoup
import time
import sqlite3
logger = logging.getLogger(__name__)
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from p115client.client import P115Client, check_response, normalize_attr_simple
from p115client.exception import P115OSError, AuthenticationError
from urllib.parse import urlsplit, parse_qs
import re
import schedule
banbenhao = "1.0.7"

from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv(dotenv_path="db/user.env",override=True)
load_dotenv(dotenv_path="sys.env",override=True)
# 配置部分
# 安全地获取整数值，避免异常
def get_int_env(env_name, default_value=0):
    try:
        value = os.getenv(env_name, str(default_value))
        return int(value) if value else default_value
    except (ValueError, TypeError):
        TelegramNotifier(os.getenv("ENV_TG_BOT_TOKEN", ""), int(os.getenv("ENV_TG_ADMIN_USER_ID", "0"))).send_message(f"[警告] 环境变量 {env_name} 值不是有效的整数，使用默认值 {default_value}")
        logger.warning(f"环境变量 {env_name} 值不是有效的整数，使用默认值 {default_value}")
        return default_value

CHANNEL_URL = os.getenv("ENV_115_TG_CHANNEL", "")
COOKIES = os.getenv("ENV_115_COOKIES",
                    "")
UPLOAD_TARGET_PID = get_int_env("ENV_UPLOAD_PID", 0)
UPLOAD_TRANSFER_PID = get_int_env("ENV_115_UPLOAD_PID", 0)

TG_BOT_TOKEN = os.getenv("ENV_TG_BOT_TOKEN", "")
TG_ADMIN_USER_ID = get_int_env("ENV_TG_ADMIN_USER_ID", 0)

# 清理任务配置参数
CLEAN_TARGET_PID = os.getenv("ENV_115_CLEAN_PID", "0,0")  # 默认空字符串
TRASH_PASSWORD = get_int_env("ENV_115_TRASH_PASSWORD", 0)

# 修改数据库文件路径到 db 目录下
DB_DIR = "db"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)
DATABASE_FILE = os.path.join(DB_DIR, "TG_monitor-115.db")
CHECK_INTERVAL = get_int_env("ENV_CHECK_INTERVAL", 5)  # 检查间隔（分钟）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
]
RETRY_TIMES = 3
TIMEOUT = 15

# 全局115客户端（避免重复初始化）
client_115 = None

# 精简全局计数器
stats = {
    "total_files": 0
}

def init_115_client():
    """初始化115客户端（cookies认证）"""
    global client_115
    if not client_115:
        try:
            client_115 = P115Client(cookies=COOKIES)
            # 验证客户端是否有效
            client_115.user_info()
            #print("[115客户端] 初始化成功")
        except Exception as e:
            logger.error(f"115客户端初始化失败：{e}")
            TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID).send_message(f"[115客户端] 初始化失败：{e}")
            raise
    return client_115

def init_database():
    """初始化数据库（增加转存状态字段）"""
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
    """保存消息到数据库，包含转存状态"""
    conn = sqlite3.connect(DATABASE_FILE)
    try:
        conn.execute("INSERT INTO messages (id, date, message_url, target_url, transfer_status, transfer_time, transfer_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (message_id, date, message_url, target_url,
                      status, transfer_time or datetime.now().isoformat(), result))
        conn.commit()
        logger.info(f"已记录: {message_id} | {target_url} | 状态: {status}")
    except sqlite3.IntegrityError:
        # 更新已有记录的状态
        conn.execute("UPDATE messages SET transfer_status=?, transfer_result=?, transfer_time=? WHERE id=?",
                     (status, result, transfer_time or datetime.now().isoformat(), message_id))
        conn.commit()
    finally:
        conn.close()

def get_latest_messages():
    """获取最新消息（从最后一条开始检查）"""
    try:
        # 获取多个频道链接
        channel_urls = os.getenv("ENV_115_TG_CHANNEL", "").split('|')
        if not channel_urls or channel_urls == ['']:
            logger.warning("未配置ENV_115_TG_CHANNEL环境变量")
            return []
            
        all_new_messages = []
        
        for channel_idx, channel_url in enumerate(channel_urls):
            channel_url = channel_url.strip()
            if not channel_url:
                continue

            if channel_url.startswith('https://t.me/') and '/s/' not in channel_url:
                # 提取频道名称部分
                channel_name = channel_url.split('https://t.me/')[-1]
                # 重构URL，添加/s/
                channel_url = f'https://t.me/s/{channel_name}'

            logger.info(f"===== 处理第{channel_idx + 1}个频道: {channel_url} =====")
            
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
                msg_index = total - 1 - i  # 从最后一条（最新）开始
                msg = message_divs[msg_index]
                data_post = msg.get('data-post', '')
                message_id = data_post.split('/')[-1] if data_post else f"未知ID_{msg_index}"
                logger.info(f"检查第{i + 1}新消息（倒数第{i + 1}条，ID: {message_id}）")

                time_elem = msg.find('time')
                date_str = time_elem.get('datetime') if time_elem else datetime.now().isoformat()
                link_elem = msg.find('a', class_='tgme_widget_message_date')
                message_url = f"{link_elem.get('href').lstrip('/')}" if link_elem else ''
                text_elem = msg.find('div', class_='tgme_widget_message_text')

                if text_elem:
                    # 提取消息文本内容（清理空格和换行）
                    message_text = text_elem.get_text(strip=True).replace('\n', ' ')
                    target_urls = extract_target_url(f"{msg}")
                    if target_urls:
                        for url in target_urls:
                            if not is_message_processed(message_url):
                                new_messages.append((message_id, date_str, message_url, url, message_text))
                                logger.info(message_url)
                            else:
                                logger.info(f"第{i + 1}新消息已处理，跳过")
                                logger.info(f"tg消息链接：{message_url}")
                                logger.info(f"115链接：{url}")
                    else:
                        logger.info("未发现目标115链接")
            
            all_new_messages.extend(new_messages)
        
        # 按时间正序排列所有消息
        all_new_messages.sort(key=lambda x: x[1])
        logger.info(f"===== 所有频道处理完成，共发现{len(all_new_messages)}条新的115分享链接 =====")
        return all_new_messages

    except requests.exceptions.RequestException as e:
        logger.error(f"网络请求失败: {str(e)[:100]}")
        return []

def extract_target_url(text):
    import re
    pattern = r'https?:\/\/(?:115|115cdn|anxia)\.com\/s\/\w+\?password\=\w+'
    matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
    if matches:
        # 去除重复链接
        unique_matches = list(set([match.strip() for match in matches]))
        return unique_matches
    return []

class Fake115Client(object):
    def __init__(self, cookies, cliHelper: P115Client):
        self.cookies = cookies
        self.ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
        self.content_type = 'application/x-www-form-urlencoded'
        self.header = {"User-Agent": self.ua,
                       "Content-Type": self.content_type, "Cookie": self.cookies}
        self.get_userid()
        self.cliHelper = cliHelper

    # 获取UID
    def get_userid(self):
        try:
            self.user_id = ''
            url = "https://my.115.com/?ct=ajax&ac=get_user_aq"
            p = requests.get(url, headers=self.header)
            if p:
                rootobject = p.json()
                if not rootobject.get("state"):
                    self.err = "[x] 获取 UID 错误：{}".format(rootobject.get("error_msg"))
                    return False
                self.user_id = rootobject.get("data").get("uid")
                return True
        except Exception as result:
            logger.error(f"异常错误：{result}")
        return False

    def request_datalist(self, share_code, receive_code):
        url = f"https://webapi.115.com/share/snap?share_code={share_code}&offset=0&limit=20&receive_code={receive_code}&cid="
        data_list = []
        share_info = {}
        try:
            response = requests.get(url, headers=self.header)
            response_json = response.json()
            share_info = response_json['data'].get('shareinfo')
            if response_json['state'] == False:
                logger.error(f"error: {response_json['error']}")
                return share_info, []
            count = response_json['data']['count']
            data_list.extend(response_json['data']['list'])
            while len(data_list) < count:
                offset = len(data_list)
                response = requests.get(f"{url}&offset={offset}")
                response_json = response.json()
                data_list.extend(response_json['data']['list'])
        except:
            data_list = []
        return share_info, data_list

    def post_save(self, share_code, receive_code, file_ids, pid='', req_delay=2):
        time.sleep(req_delay)
        file_id_str = ','.join(file_ids)
        if pid == '':
            payload = {
                'user_id': self.user_id,
                'share_code': share_code,
                'receive_code': receive_code,
                'file_id': file_id_str
            }
        else:
            payload = {
                'user_id': self.user_id,
                'share_code': share_code,
                'receive_code': receive_code,
                'file_id': file_id_str,
                'cid': pid
            }
        try:
            response = requests.post('https://webapi.115.com/share/receive', data=payload, headers=self.header)
        except Exception as e:
            logger.error(f"转存失败: {str(e)}")
            notifier = TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID)
            notifier.send_message(f"转存失败: {str(e)}")
            return False
        result = response.json()
        if not result['state']:
            error_msg = result.get("error", "")
            logger.error(f'转存 {share_code}:{receive_code} 失败，原因：{error_msg}')
            # 当错误信息为"文件已接收，无需重复接收！"时，视为转存成功
            if "无需重复接收" in error_msg:
                response.close()
                return True
            TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID).send_message(f"115转存失败，失败原因：{error_msg}")
        response.close()
        return result['state']

    def share_link_parser(self, link) -> tuple:
        match = re.search(r'https?:\/\/(115|115cdn|anxia)\.com\/s\/(\w+)\?password\=(\w+)', link, re.IGNORECASE | re.DOTALL)
        if not match:
            logger.error(f'链接格式错误, link={link}')
            TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID).send_message(f'链接格式错误, link={link}')
            return None
        share_code = match.group(2)
        receive_code = match.group(3)
        return (share_code, receive_code)

    def save_link(self, share_item, pid="") -> bool:
        share_code = share_item[0]
        receive_code = share_item[1]
        share_info, data_list = self.request_datalist(share_code, receive_code)
        file_ids = []
        for data in data_list:
            cid = data.get('fid', data['cid'])
            file_ids.append(cid)
        if self.post_save(share_code=share_code, receive_code=receive_code, file_ids=file_ids, pid=pid):
            return True
        return False

def transfer_shared_link(client: P115Client, share_url: str, target_pid: int):
    """
    转存 115 分享链接到指定目录
    :param client: P115Client 实例
    :param share_url: 115 分享链接（含提取码）
    :param target_pid: 目标目录 PID
    """
    try:       
        fake_client = Fake115Client(cookies=COOKIES, cliHelper=client)
        share_item = fake_client.share_link_parser(share_url)
        if share_item:
            return fake_client.save_link(share_item, str(target_pid))

    except Exception as e:
        logger.error(f"转存失败: {str(e)}")
        notifier = TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID)
        notifier.send_message(f"转存失败: {str(e)}")
        return False

def print_progress(msg, indent=0):
    """带缩进的进度输出"""
    prefix = "  " * indent
    logger.info(f"{prefix}[{time.strftime('%H:%M:%S')}] {msg}")

def transfer_and_clean():
    """递归转移文件并清理空目录（带详细日志）"""
    global stats
    client = P115Client(cookies=COOKIES)

    def recursive_transfer(current_pid: int, depth=0):
        # 获取当前目录名称
        try:
            dir_info = client.fs_get_info(current_pid)
            dir_name = dir_info.get("name", f"目录#{current_pid}")
        except:
            dir_name = f"目录#{current_pid}"
        print_progress(f"扫描目录: {dir_name} ({current_pid})", depth)

        # 获取当前目录内容（带分页处理）
        items = []
        offset = 0
        while True:
            try:
                resp = client.fs_files_app({
                    "cid": current_pid,
                    "limit": 1000,
                    "offset": offset
                })
                check_response(resp)
                page_items = resp["data"]
                items.extend(page_items)

                if len(page_items) < 1000:
                    break  # 没有更多数据
                offset += 1000
                print_progress(f"  读取分页: {offset / 1000 + 1}", depth + 1)
            except Exception as e:
                print_progress(f"⚠️ 获取目录内容失败: {str(e)}", depth + 1)
                break

        print_progress(f"发现 {len(items)} 个项目", depth + 1)

        # 分离文件和目录（先处理文件）
        files = [item for item in items if not normalize_attr_simple(item)["is_dir"]]
        dirs = [item for item in items if normalize_attr_simple(item)["is_dir"]]

        # 转移所有文件
        for i, file in enumerate(files, 1):
            normalized = normalize_attr_simple(file)
            file_name = normalized.get("name", f"文件#{normalized['id']}")
            progress = f"{i}/{len(files)}"
            try:
                move_resp = client.fs_move_app(
                    {"ids": normalized["id"], "to_cid": UPLOAD_TARGET_PID},
                    app="android"
                )
                check_response(move_resp)
                print_progress(f"✅ 移动文件: {file_name} ({progress})", depth + 1)
                stats["total_files"] += 1
            except Exception as e:
                print_progress(f"❌ 移动失败: {file_name} ({progress}) - {str(e)}", depth + 1)
            time.sleep(0.2)  # 每个文件转移后休眠 0.2 秒

        # 递归处理子目录
        for directory in dirs:
            dir_id = normalize_attr_simple(directory)["id"]
            if dir_id == UPLOAD_TARGET_PID:
                print_progress(f"⏩ 跳过目标目录: {dir_id}", depth + 1)
                continue
            recursive_transfer(dir_id, depth + 1)

        # 清理空目录
        try:
            after_resp = client.fs_files_app(current_pid)
            check_response(after_resp)
            if (not after_resp["data"]
                    and current_pid != UPLOAD_TARGET_PID
                    and current_pid != UPLOAD_TRANSFER_PID):
                del_resp = client.fs_delete_app(current_pid)
                check_response(del_resp)
                print_progress(f"🗑️ 删除空目录: {dir_name} ({current_pid})", depth)
                time.sleep(1)  # 每个目录清理后休眠 1 秒
        except Exception as e:
            print_progress(f"⚠️ 删除目录失败: {dir_name} ({current_pid}) - {str(e)}", depth)

    # 执行前检查
    if UPLOAD_TRANSFER_PID == 0:
        raise ValueError("转移目录ID不能为0")

    logger.info("===== 开始文件转移和目录清理 =====")
    logger.info(f"源目录: {UPLOAD_TRANSFER_PID}")
    logger.info(f"目标目录: {UPLOAD_TARGET_PID}")
    logger.info("==================================\n")

    # 执行转移
    try:
        recursive_transfer(UPLOAD_TRANSFER_PID)
    except KeyboardInterrupt:
        logger.warning("\n⚠️ 操作被用户中断")
    finally:
        # 输出统计信息
        logger.info("===== 操作完成 =====")
        logger.info(f"程序自启动后共转存文件数: {stats['total_files']}")
        logger.info("===================\n")


def clean_task():
    """执行清理任务：仅当目标文件夹ID存在时才执行操作"""
    # 解析目标文件夹ID（过滤空值）
    target_pids = [
        pid.strip()
        for pid in CLEAN_TARGET_PID.split(",")
        if pid.strip()
    ]

    # 如果目标文件夹ID为空，直接退出
    if not target_pids:
        logger.warning("未配置有效目标文件夹ID，不执行清理操作")
        return

    # 初始化客户端（使用全局配置的COOKIES）
    client = P115Client(cookies=COOKIES)

    try:
        # 清理每个目标文件夹内的内容
        for cid in target_pids:
            logger.info(f"开始清理文件夹 {cid} 内的内容...")
            offset = 0
            limit = 100  # 分页大小

            while True:
                # 获取文件夹内容
                try:
                    # 注意：这里使用fs_files_app可能比fs_files更稳定（参考transfer_and_clean中的用法）
                    resp = client.fs_files_app({
                        "cid": cid,
                        "limit": limit,
                        "offset": offset,
                        "show_dir": 1
                    })
                    check_response(resp)
                    contents = resp.get("data", [])

                    if not contents:
                        logger.info(f"文件夹 {cid} 内无内容，清理完成")
                        break

                    # 遍历删除内容
                    for item in contents:
                        # 关键修复：使用normalize_attr_simple规范化属性（原代码中已有该工具函数）
                        normalized_item = normalize_attr_simple(item)
                        item_id = normalized_item.get("id")
                        item_name = normalized_item.get("name", "未知名称")
                        is_dir = normalized_item.get("is_dir", False)

                        # 新增校验：跳过无ID的无效项目
                        if not item_id:
                            logger.warning(f"跳过无效项目（无ID）：{item_name}")
                            continue

                        try:
                            logger.info(f"删除{'目录' if is_dir else '文件'}: {item_name} (ID: {item_id})")
                            # 注意：根据原代码风格，使用fs_delete_app更兼容
                            client.fs_delete_app(item_id)
                            time.sleep(0.5)  # 增加小延迟，避免请求过于频繁
                        except Exception as e:
                            logger.error(f"删除 {item_name} 失败: {str(e)}")

                    # 处理分页
                    if len(contents) < limit:
                        logger.info(f"文件夹 {cid} 内容已全部清理")
                        break
                    offset += limit

                except Exception as e:
                    logger.error(f"获取文件夹 {cid} 内容失败: {str(e)}")
                    break

        # 清空回收站
        logger.info("开始清空回收站...")
        client.recyclebin_clean(password=TRASH_PASSWORD)
        logger.info("回收站清空完成")

    finally:
        client.close()

class TelegramNotifier:
    def __init__(self, bot_token, user_id):
        self.bot_token = bot_token
        self.user_id = user_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/" if self.bot_token else None

    def send_message(self, message):
        """向指定用户发送消息，若bot_token未设置则跳过发送，失败自动重试"""
        # 局部变量定义重试参数
        max_retries = 30  # 重试次数
        retry_delay = 60  # 重试间隔

        # 检查bot_token是否存在
        if not self.bot_token:
            logger.error("未设置bot_token，跳过发送消息")
            return False
        if not message:
            logger.error("警告：消息内容不能为空")
            return False
        success_count = 0
        fail_count = 0
        params = {
            "chat_id": self.user_id,
            "text": message
        }

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"{self.base_url}sendMessage",
                    params=params,
                    timeout=15  # 使用全局超时配置
                )
                response.raise_for_status()
                result = response.json()
                if result.get("ok", False):
                    logger.info(f"消息 '{message.replace('\n', '').replace('\r', '')[:20]}...' ，已成功发送给用户 {TG_ADMIN_USER_ID}（第{attempt+1}/{max_retries}次尝试）")
                    success_count += 1
                    break  # 成功则终止重试
                else:
                    error_msg = result.get('description', '未知错误')
                    logger.error(f"发送回复失败，{retry_delay}秒后重发，消息：{message}，错误：{error_msg}")
                    fail_count += 1
            except requests.exceptions.RequestException as e:
                logger.error(f"发送回复失败，{retry_delay}秒后重发，消息：{message}，错误：{str(e)}")
                fail_count += 1

            # 非最后一次尝试则等待重试
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

        #logger.info(f"消息发送完成 - 成功: {success_count}, 失败: {fail_count}")
        return success_count > 0  # 保持原有返回值逻辑

def tg_115monitor():
    init_database()
    client = init_115_client()
    notifier = TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID)
    logger.info(f"===== 开始检查 115（{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）=====")
    new_messages = get_latest_messages()
    #schedule.run_pending()
    if new_messages:
        for msg in new_messages:
            message_id, date_str, message_url, target_url, message_text = msg
            logger.info(f"处理新消息: {message_id} | {target_url}")

            # 转存到115
            result = transfer_shared_link(client, target_url, UPLOAD_TRANSFER_PID)
            if result:
                status = "转存成功"
                result_msg = f"✅115网盘转存成功\n消息内容: {message_url}\n链接: {target_url}"
            else:
                status = "转存失败"
                result_msg = f"❌115网盘转存失败\n消息内容: {message_url}\n链接: {target_url}"

            notifier.send_message(result_msg)

            # 保存结果到数据库
            save_message(message_id, date_str, message_url, target_url, status, result_msg)
    else:
        logger.info("未发现新的115分享链接")

def main():
    try:       
        while True:
            tg_115monitor()
            time.sleep(CHECK_INTERVAL * 60)

    except KeyboardInterrupt:
        logger.info("程序已停止")
    except Exception as e:
        logger.error(f"程序异常终止: {str(e)}")

if __name__ == "__main__":
    main()