import os
import time
import logging
logger = logging.getLogger(__name__)
import requests
import hashlib
from dotenv import load_dotenv
from p115client.client import P115Client
from p115client.tool.upload import multipart_upload_init
from p123client import P123Client

# 加载.env文件中的环境变量
load_dotenv(dotenv_path="db/user.env",override=True)
load_dotenv(dotenv_path="sys.env",override=True)
# 安全地获取整数值，避免异常
def get_int_env(env_name, default_value=0):
    try:
        value = os.getenv(env_name, str(default_value))
        return int(value) if value else default_value
    except (ValueError, TypeError):
        TelegramNotifier(os.getenv("ENV_TG_BOT_TOKEN", ""), int(os.getenv("ENV_TG_ADMIN_USER_ID", "0"))).send_message(f"[警告] 环境变量 {env_name} 值不是有效的整数，使用默认值 {default_value}")
        logger.warning(f"环境变量 {env_name} 值不是有效的整数，使用默认值 {default_value}")
        return default_value
# ======================== 环境变量配置（从.env文件读取） ========================
# 客户端配置
version = "1.0.4"
TG_BOT_TOKEN = os.getenv("ENV_TG_BOT_TOKEN", "")
TG_ADMIN_USER_ID = get_int_env("ENV_TG_ADMIN_USER_ID", 0)

# 秒传功能开关
PTTO123_SWITCH = get_int_env("ENV_PTTO123_SWITCH", 0)
PTTO115_SWITCH = get_int_env("ENV_PTTO115_SWITCH", 0)

# 最大尝试次数
TRY_MAX_COUNT = 999999

try:
    # 读取115 cookies
    COOKIES = os.getenv("ENV_115_COOKIES", "")

    # 读取上传目标目录ID
    PTTO123_UPLOAD_PID = get_int_env("ENV_PTTO123_UPLOAD_PID", 0)
    PTTO115_UPLOAD_PID = get_int_env("ENV_PTTO115_UPLOAD_PID", 0)

except (ValueError, TypeError) as e:
    # 环境变量值格式错误或未设置
    logger.error(f"环境变量错误：{e}")
    logger.error("请确保.env文件中已正确设置所有必要的环境变量")
    # 终止程序，因为缺少必要的环境变量
    exit(1)

# ======================== 其他固定配置 ========================
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "upload")  # 待上传目录
SLEEP_AFTER_FILE = 10  # 单个文件处理后休眠（秒）
SLEEP_AFTER_ROUND = 60  # 一轮遍历后休眠（秒）


# ======================== 工具函数 ========================
def check_file_size_stability(file_path, check_interval=30, max_attempts=1000):
    """检查文件大小稳定性，防止文件不完整"""
    for attempt in range(max_attempts):
        size1 = os.path.getsize(file_path)
        time.sleep(check_interval)
        size2 = os.path.getsize(file_path)
        if size1 == size2:
            logger.info(f"文件大小稳定：{file_path}")
            return True
        logger.warning(f"文件大小不稳定，第 {attempt + 1} 次检查：{file_path}")
    logger.error(f"文件大小不稳定，放弃上传：{file_path}")
    return False


def init_115_client():
    """初始化115客户端（cookies认证）"""
    try:
        client = P115Client(COOKIES)
        logger.info("客户端初始化成功（cookies有效）")
        return client
    except Exception as e:
        logger.error(f"客户端初始化失败（检查cookies是否有效）：{e}")
        raise

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

# ======================== 工具函数 ========================
def fast_md5(file_path: str) -> str:
    """快速计算文件MD5（分块读取，适用于大文件）"""
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        # 64KB分块读取，平衡速度和内存占用
        for chunk in iter(lambda: f.read(65536), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()

CLIENT_ID = os.getenv("ENV_123_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ENV_123_CLIENT_SECRET", "")
DB_DIR = "db"

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
        try:
            client = P123Client(token=token)
            res = client.user_info()
            if res.get('code') != 0 or res.get('message') != "ok":
                notifier = TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID)
                notifier.send_message("123 token过期，将重新获取")
                logger.info("检测到token过期，将重新获取")
                if os.path.exists(token_path):
                    os.remove(token_path)
            else:
                logger.info("123客户端初始化成功（使用持久化token）")
                return client
        except Exception as e:
            if "token is expired" in str(e).lower() or (
                    hasattr(e, 'args') and "token is expired" in str(e.args).lower()):
                logger.info("检测到token过期，将重新获取")
            else:
                logger.warning(f"token无效或初始化失败：{e}，将重新获取")
            if os.path.exists(token_path):
                os.remove(token_path)
    try:
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
# ======================== 核心逻辑 ========================
def ptto123process():
    # 初始化Telegram通知器
    notifier = TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID)
    # 先根据开关状态判断秒传顺序描述
    if PTTO123_SWITCH and PTTO115_SWITCH:
        order_desc = "先尝试123秒传，再尝试115秒传"
    elif PTTO123_SWITCH:
        order_desc = "只启用123网盘秒传"
    elif PTTO115_SWITCH:
        order_desc = "只启用115网盘秒传"
    else:
        order_desc = "均未启用秒传"

    # 发送完善后的消息
    notifier.send_message(
        f"开始监控本地待上传目录\n"
        f"123网盘秒传：{'开启' if PTTO123_SWITCH else '关闭'}\n"
        f"115网盘秒传：{'开启' if PTTO115_SWITCH else '关闭'}\n"
        f"当前秒传顺序：{order_desc}"
    )
    # 发送启动通知（如果配置了Telegram）
    cache = {}  # 内存缓存：{文件绝对路径: {'md5': '', 'sha1': ''}}
    attempt_count = {}  # 跟踪每个文件的尝试次数：{文件绝对路径: 次数}
    last_delete_time = time.time()

    while True:
        #logger.info("开始遍历待上传目录")
        # 遍历upload目录文件
        for root, _, files in os.walk(UPLOAD_DIR):
            for filename in files:
                file_path = os.path.join(root, filename)
                file_key = file_path

                logger.info(f"正在检查文件 {file_path} 的大小稳定性...")
                # 检查文件大小稳定性
                if not check_file_size_stability(file_path):
                    continue

                # 获取文件大小
                try:
                    filesize = os.path.getsize(file_path)
                    logger.info(f"获取到文件 {file_path} 的大小为 {filesize} 字节")
                except FileNotFoundError:
                    logger.info(f"文件已删除：{file_path}")
                    if file_key in cache:
                        del cache[file_key]
                    continue

                # 初始化文件尝试次数
                if file_key not in attempt_count:
                    attempt_count[file_key] = 0
                
                # 增加尝试次数
                attempt_count[file_key] += 1
                logger.info(f"正在尝试上传文件（第 {attempt_count[file_key]} 次）：{file_path}")
                
                '''
                # 检查是否达到最大尝试次数
                if attempt_count[file_key] > TRY_MAX_COUNT:
                    try:
                        os.remove(file_path)
                        logger.info(f"文件“{filename}”尝试上传 {TRY_MAX_COUNT} 次失败，已删除")
                        # 发送失败通知（如果配置了Telegram）
                        if TG_BOT_TOKEN and TG_ADMIN_USER_ID:
                            notifier.send_message(f"文件“{filename}”尝试上传 {TRY_MAX_COUNT} 次失败，已删除")
                        if file_key in cache:
                            del cache[file_key]
                        if file_key in attempt_count:
                            del attempt_count[file_key]
                    except Exception as e:
                        logger.error(f"文件“{filename}”尝试上传 {TRY_MAX_COUNT} 次失败")
                    continue
                '''
                # 初始化缓存
                if file_key not in cache:
                    cache[file_key] = {'md5': '', 'sha1': ''}
                
                # 先尝试123网盘秒传（如果启用）
                if PTTO123_SWITCH:
                    client = init_123_client()
                    if not cache[file_key]['md5']:
                        logger.info(f"计算文件MD5：{file_path}")
                        cache[file_key]['md5'] = fast_md5(file_path)
                        logger.info(f"已缓存文件MD5：{file_path} → {cache[file_key]['md5']}")
                    else:
                        logger.info(f"使用缓存的MD5值：{file_path} → {cache[file_key]['md5']}")
                    
                    try:
                        logger.info(f"开始尝试123网盘秒传：{file_path}")
                        upload_result = client.upload_file_fast(
                            file=file_path,
                            file_md5=cache[file_key]['md5'],
                            file_name=filename,
                            file_size=filesize,
                            parent_id=PTTO123_UPLOAD_PID,
                            duplicate=2,  # 覆盖同名文件
                            async_=False
                        )

                        # 检查123网盘秒传结果（code=0且reuse=True表示秒传成功）
                        if upload_result.get("code") == 0 and upload_result["data"].get("Reuse"):
                            logger.info(f"123网盘秒传成功：{file_path}（文件ID：{upload_result['data']['Info']['FileId']}）")
                            # 发送成功通知（如果配置了Telegram）
                            if TG_BOT_TOKEN and TG_ADMIN_USER_ID:
                                notifier.send_message(f"本地文件“{filename}”123网盘秒传成功（目标目录ID：{PTTO123_UPLOAD_PID}）")
                            os.remove(file_path)
                            logger.info(f"已删除本地文件：{file_path}")
                            if file_key in cache:
                                del cache[file_key]
                            if file_key in attempt_count:
                                del attempt_count[file_key]
                            continue  # 成功后跳过后续处理
                        else:
                            logger.warning(f"123网盘秒传未成功：{file_path}")
                    except Exception as e:
                        logger.error(f"123网盘上传失败：{file_path} → {e}")
                else:
                    logger.info("123网盘秒传功能未启用或客户端未初始化")
                
                # 如果123网盘秒传失败或未启用，尝试115网盘秒传（如果启用）
                if PTTO115_SWITCH:
                    client_115 = init_115_client()
                    try:
                        logger.info(f"开始尝试115网盘秒传：{file_path}")
                        upload_result = multipart_upload_init(
                            client=client_115,
                            path=file_path,
                            filename=filename,
                            filesize=filesize,
                            filesha1=cache[file_key]['sha1'] or '',  # 使用缓存的哈希值或留空让接口自动计算
                            pid=PTTO115_UPLOAD_PID
                        )

                        # 处理115网盘秒传结果
                        if "status" in upload_result:
                            logger.info(f"115网盘秒传成功：{file_path}（目标目录ID：{PTTO115_UPLOAD_PID}）")
                            # 发送成功通知（如果配置了Telegram）
                            if TG_BOT_TOKEN and TG_ADMIN_USER_ID:
                                notifier.send_message(f"本地文件“{filename}”115网盘秒传成功（目标目录ID：{PTTO115_UPLOAD_PID}）")
                            os.remove(file_path)
                            logger.info(f"已删除本地文件：{file_path}")
                            if file_key in cache:
                                del cache[file_key]
                            if file_key in attempt_count:
                                del attempt_count[file_key]
                        else:
                            logger.warning(f"115网盘秒传未成功：{file_path}，从上传配置信息里获取哈希值并缓存")
                            # 从上传配置信息里获取哈希值
                            filesha1 = upload_result.get('filesha1', '')
                            if filesha1:
                                cache[file_key]['sha1'] = filesha1
                                logger.info(f"已缓存文件SHA1值：{file_path} → {filesha1}")

                    except Exception as e:
                        logger.error(f"115网盘上传失败,尝试重新初始化客户端：{file_path} → {e}")
                        if PTTO115_SWITCH:
                            client_115 = init_115_client()


                # 单个文件处理完成，休眠指定时间
                time.sleep(SLEEP_AFTER_FILE)

        #logger.info(f"一轮遍历完成，休眠 {SLEEP_AFTER_ROUND} 秒...")
        time.sleep(SLEEP_AFTER_ROUND)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("用户终止程序")
    except Exception as e:
        logger.error(f"程序异常：{e}")