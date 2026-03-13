import requests
import os
import time
import re  # 导入正则表达式模块

from dotenv import load_dotenv
load_dotenv(dotenv_path="db/user.env", override=True)
load_dotenv(dotenv_path="sys.env", override=True)
import logging
#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# 原有强制放在首位的目标助力码（保留原顺序，确保核心码优先）
original_boost_codes = []

# 请求URL
url = "https://act.115.com/api/1.0/web/1.0/invite_boost/accept_invite"

# 请求头，包含cookie信息
headers = {
    "Cookie": os.getenv("ENV_115_COOKIES", ""),
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded"
}

def accept_invite(new_boost_codes_text):
    logger.info("开始处理115助力（正则提取6位邀请码）")
    
    # -------------------------- 核心：正则提取6位邀请码 --------------------------
    # 正则表达式规则：
    # [A-Z0-9]{6}：匹配6位字符，仅包含大写字母（A-Z）和数字（0-9）
    # 若邀请码可能含小写字母，可改为 [A-Za-z0-9]{6}
    pattern = r'[A-Z0-9]{6}'
    # 提取文本中所有符合规则的6位字符，返回列表
    new_boost_codes = re.findall(pattern, new_boost_codes_text)
    # ------------------------------------------------------------------------------
    
    # 打印提取结果，便于排查（可选，可删除）
    if new_boost_codes:
        logger.info(f"正则提取到 {len(new_boost_codes)} 个6位邀请码：{new_boost_codes}")
    else:
        logger.warning("未从传入文本中提取到符合要求的6位邀请码")
        return False  # 无有效码时直接返回，避免空循环
    
    # 合并原有码与新提取的码，去重并保持原有顺序
    seen_codes = set()  # 记录已存在的码，用于去重
    boost_codes = []
    
    # 1. 先添加原有强制码（确保首位顺序不变）
    for code in original_boost_codes:
        if code not in seen_codes:
            seen_codes.add(code)
            boost_codes.append(code)
    
    # 2. 再添加新提取的码（去重后追加，避免与原有码重复）
    for code in new_boost_codes:
        if code not in seen_codes:
            seen_codes.add(code)
            boost_codes.append(code)
    
    # 遍历处理所有去重后的邀请码
    for code in boost_codes:
        try:
            # 构建form表单数据
            form_data = {
                "boost_code": code,
                "source": "code"
            }
            
            # 发送POST请求，设置超时防止卡死
            response = requests.post(url, headers=headers, data=form_data, timeout=10)
            response_data = response.json()
            time.sleep(1)  # 间隔0.2秒，避免请求过于频繁被拦截
            logger.info(f"处理邀请码: {code} | 响应状态: {response_data.get('state')} | 响应信息: {response_data}")
            
            # 如需启用「exceed_boost=true时停止」，取消以下注释
            # if response_data.get('data', {}).get('exceed_boost', False):
            #     logger.info(f"邀请码 {code} 触发exceed_boost=true，停止后续处理")
            #     break
                
        except Exception as e:
            # 捕获所有异常（超时、连接错误等），跳过当前码继续处理下一个
            logger.error(f"处理邀请码 {code} 失败，原因: {str(e)}，已跳过")
            continue

    logger.info(f"115助力处理完成")
    return True

if __name__ == "__main__":
    # 示例：传入的文本（可含多余字符，正则会自动提取6位码）
    sample_codes_text = """
    这是一段混合文本，包含邀请码：AAW5LR、HZL28V，还有无效的5位码12345和7位码1234567。
    换行后继续：5RRNY8（有效），U5QX86_多余字符，ZWT3RH；无效码：ABCDE（5位）、12345678（8位）。
    最后几个有效码：1F31VB、NKMMB5、E861QV、QR9HLK
    """
    # 调用函数，传递文本参数
    accept_invite(sample_codes_text)