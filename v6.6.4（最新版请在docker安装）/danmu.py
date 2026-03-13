import os
import re
import requests
import sys
import logging
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv(dotenv_path="db/user.env",override=True)
load_dotenv(dotenv_path="sys.env",override=True)

# 配置logger
logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def extract_tmdb_id(file_path):
    """从文件路径中提取TMDB ID"""
    tmdb_id_pattern = r'[{\[](?:tmdb(?:id)?)(?:=|-)(\d+)[}\]]'
    match = re.search(tmdb_id_pattern, file_path)
    if match:
        return match.group(1)
    return None

def is_tv_series(file_path):
    """判断是否为电视剧（包含Season）"""
    return 'Season' in file_path

def extract_season(file_path):
    """从文件路径中提取季数"""
    # 从路径中的"Season X"提取
    season_pattern = r'Season\s+(\d+)'
    match = re.search(season_pattern, file_path, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # 从文件名中的Sxx模式提取
    season_pattern = r'S(\d+)'
    match = re.search(season_pattern, file_path, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    return 1  # 默认季数

def extract_episode(file_path):
    """从文件路径中提取当前集数"""
    # 匹配文件名中的Exx模式（如E01、E10）
    episode_pattern = r'E(\d+)'
    match = re.search(episode_pattern, file_path, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # 匹配"第X集"格式
    episode_pattern = r'第(\d+)集'
    match = re.search(episode_pattern, file_path, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    return 1  # 默认集数

def extract_work_title(file_path):
    """从文件路径中提取作品标题"""
    title_pattern = r'([^/\\]+?)\s*\(\d{4}\)\s*(?:\{|\[|$)'
    match = re.search(title_pattern, file_path, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # 备选：取路径最后一段（文件名）的前缀作为关键词
    return os.path.basename(file_path).split('.')[0].strip()

def download_single_episode(api_url, api_key, tmdb_id, season, episode):
    """下载单集弹幕的工具函数"""
    download_url = f"{api_url}/api/control/import/auto"
    params = {
        'api_key': api_key,
        'searchType': 'tmdb',
        'searchTerm': tmdb_id,
        'mediaType': 'tv_series',
        'season': season,
        'episode': episode  # 新增：指定单集
    }
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        logger.info(f"  正在下载 S{season:02d}E{episode:02d} 弹幕...")
        response = requests.post(download_url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"  S{season:02d}E{episode:02d} 下载成功！任务ID：{result.get('taskId', '未知')}")
        return True
    
    except requests.exceptions.RequestException as e:
        logger.error(f"  S{season:02d}E{episode:02d} 下载失败：{e}")
        if hasattr(response, 'status_code'):
            logger.error(f"  - HTTP状态码：{response.status_code}")
            if response.status_code == 422:
                logger.error(f"  - 验证错误详情：{response.json().get('detail')}")
        return False

def download_danmaku(file_path):
    """全自动流程：直接下载，剧集下载当前集+下一集，电影下载全片"""
    # 1. 提取核心信息
    tmdb_id = extract_tmdb_id(file_path)
    if not tmdb_id:
        logger.warning(f"[终止] 无法从路径中提取TMDB ID：{file_path}")
        return
    
    tv_series = is_tv_series(file_path)
    work_title = extract_work_title(file_path)
    media_type_desc = "电视剧" if tv_series else "电影"

    # 2. 获取API配置
    api_url = os.getenv('DANMAKU_API_URL', "")
    api_key = os.getenv('DANMAKU_API_KEY', "")
    
    if not api_url or not api_key:
        logger.warning("[终止] 请设置环境变量 DANMAKU_API_URL 和 DANMAKU_API_KEY")
        return

    # 3. 直接下载（移除搜索步骤）
    logger.info(f"[开始下载] {media_type_desc}：{work_title}（TMDB ID：{tmdb_id}）")
    
    if tv_series:
        # 电视剧：下载当前集 + 下一集
        season = extract_season(file_path)
        current_episode = extract_episode(file_path)
        next_episode = current_episode + 1  # 计算下一集
        
        logger.info(f"[剧集信息] 第{season}季，当前集：{current_episode}，下一集：{next_episode}")
        logger.info("[下载计划] 共需下载2集弹幕：")
        
        # 下载当前集
        download_single_episode(api_url, api_key, tmdb_id, season, current_episode)
        # 下载下一集
        download_single_episode(api_url, api_key, tmdb_id, season, next_episode)
        
        logger.info("[剧集下载完成] 已尝试下载当前集和下一集弹幕\n")
        
    else:
        # 电影：下载全片弹幕
        download_url = f"{api_url}/api/control/import/auto"
        params = {
            'api_key': api_key,
            'searchType': 'tmdb',
            'searchTerm': tmdb_id,
            'mediaType': 'movie'
        }
        
        headers = {'Content-Type': 'application/json'}
        
        try:
            logger.info("  正在下载电影弹幕...")
            response = requests.post(download_url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"[电影下载完成] 任务ID：{result.get('taskId', '未知')}，消息：{result.get('message', '无')}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[电影下载失败] {e}")
            if hasattr(response, 'status_code'):
                logger.error(f"  - HTTP状态码：{response.status_code}")
                if response.status_code == 422:
                    logger.error(f"  - 验证错误详情：{response.json().get('detail')}")
            logger.info("")

if __name__ == "__main__":
    # 测试路径：可替换为实际文件路径（包含集数信息，如E01、第1集）
    target_file_path = "/CloudNAS/CloudDrive/123云盘/Video/通用格式影视库/电视节目/国产剧集/2025/长安的荔枝 (2025) {tmdb-203367}/Season 1/长安的荔枝.2025.S01E28.第28集.2160p.DoVi.H.265.mp4"
    logger.info(f"处理文件路径：{target_file_path}")
    download_danmaku(target_file_path)
    