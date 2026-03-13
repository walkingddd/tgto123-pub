import os
import time
import hashlib
import logging
logger = logging.getLogger(__name__)
from p123client import P123Client  # 导入123网盘客户端
from filewrap import SupportsRead  # 从原依赖导入必要类
from hashtools import file_digest  # 用于高效计算MD5
from dotenv import load_dotenv
import requests
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
# ======================== 其他固定配置 ========================
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "upload")  # 待上传目录
SLEEP_AFTER_FILE = 10  # 单个文件处理后休眠（秒）
SLEEP_AFTER_ROUND = 60  # 一轮遍历后休眠（秒）
TG_BOT_TOKEN = os.getenv("ENV_TG_BOT_TOKEN", "")
TG_ADMIN_USER_ID = get_int_env("ENV_TG_ADMIN_USER_ID", 0)
class TelegramNotifier:
    def __init__(self, bot_token, user_id):
        self.bot_token = bot_token
        self.user_id = user_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/" if self.bot_token else None

    def send_message(self, message):
        if not self.bot_token:
            logger.warning("未设置bot_token，跳过发送消息")
            return False
        if not message:
            logger.warning("消息内容不能为空")
            return False
        success_count = 0
        fail_count = 0
        params = {"chat_id": self.user_id, "text": message}
        try:
            response = requests.get(f"{self.base_url}sendMessage", params=params)
            response.raise_for_status()
            result = response.json()
            if result.get("ok", False):
                logger.info(f"消息已成功发送给用户 {self.user_id}")
                success_count += 1
            else:
                logger.error(f"发送消息给用户 {self.user_id} 失败: {result.get('description', '未知错误')}")
                fail_count += 1
        except requests.exceptions.RequestException as e:
            logger.error(f"发送消息给用户 {self.user_id} 时发生错误: {str(e)}")
            fail_count += 1
        logger.info(f"消息发送完成 - 成功: {success_count}, 失败: {fail_count}")
        return success_count > 0

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

def fast_md5(file_path: str) -> str:
    """快速计算文件MD5（分块读取，适用于大文件）"""
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        # 64KB分块读取，平衡速度和内存占用
        for chunk in iter(lambda: f.read(65536), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()

# ======================== 核心逻辑 ========================
def ptto123process(client: P123Client,UPLOAD_TARGET_PID):
    cache = {}  # 内存缓存：{文件绝对路径: MD5}
    last_delete_time = time.time()
    
    while True:
        logger.info("开始遍历本地待上传目录")
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

                # 计算并缓存MD5（优先使用缓存）
                cached_md5 = cache.get(file_key)
                if cached_md5:
                    logger.info(f"使用缓存的MD5值：{file_path} → {cached_md5}")
                else:
                    logger.info(f"计算文件MD5：{file_path}")
                    cached_md5 = fast_md5(file_path)
                    cache[file_key] = cached_md5
                    logger.info(f"已缓存文件MD5：{file_path} → {cached_md5}")

                # 调用123网盘秒传接口
                retry = False
                while True:
                    try:
                        logger.info(f"开始上传文件：{file_path}")
                        upload_result = client.upload_file_fast(
                            file=file_path,
                            file_md5=cached_md5,
                            file_name=filename,
                            file_size=filesize,
                            parent_id=UPLOAD_TARGET_PID,
                            duplicate=2,  # 覆盖同名文件
                            async_=False
                        )

                        # 检查秒传结果（123网盘接口成功标识：code=0且reuse=True）
                        if upload_result.get("code") == 0 and upload_result["data"].get("Reuse"):
                            logger.info(f"秒传成功：{file_path}（文件ID：{upload_result['data']['Info']['FileId']}）")
                            TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID).send_message(f"[成功] 本地文件秒传123云盘成功：{file_path}（文件ID：{upload_result['data']['Info']['FileId']}）")
                            os.remove(file_path)
                            logger.info(f"已删除本地文件：{file_path}")
                            if file_key in cache:
                                del cache[file_key]
                        else:
                            logger.warning(f"秒传未成功：{file_path}，响应：{upload_result}")
                    except Exception as e:
                        logger.error(f"上传失败：{file_path} → {e}")
                    break
                time.sleep(SLEEP_AFTER_FILE)
        # 一轮遍历结束后休眠
        logger.info(f"一轮遍历完成，休眠 {SLEEP_AFTER_ROUND} 秒...")
        time.sleep(SLEEP_AFTER_ROUND)

if __name__ == "__main__":
    try:
        None
    except KeyboardInterrupt:
        logger.info("用户终止程序")
    except Exception as e:
        logger.error(f"程序异常：{e}")