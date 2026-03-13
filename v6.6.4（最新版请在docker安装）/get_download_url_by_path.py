import logging
import requests
import time
import os
import re
import logging
import threading
import guessit
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv(dotenv_path="db/user.env",override=True)
load_dotenv(dotenv_path="sys.env",override=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 设置日志级别为INFO，确保info级别的日志能被输出
#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# 创建缓存字典，用于存储文件名对应的fileid、download_url，以及缓存时间
# 格式: {filename: (fileid, download_url, timestamp)}
url_cache = {}
CACHE_EXPIRATION = 720 * 60  # 缓存有效期，30分钟（秒）
def get_int_env(env_name, default_value=0):
    try:
        value = os.getenv(env_name, str(default_value))
        return int(value) if value else default_value
    except (ValueError, TypeError):
        logger.warning(f"环境变量 {env_name} 值不是有效的整数，使用默认值 {default_value}")
        return default_value
# 创建父目录ID缓存字典，用于存储父目录ID的缓存时间
# 格式: {parent_file_id: timestamp}
parent_dir_cache = {}
PARENT_DIR_CACHE_EXPIRATION = 12 * 3600  # 父目录ID缓存有效期，12小时（秒）

# 创建弹幕下载缓存字典，用于存储文件路径对应的缓存时间
# 格式: {file_path: timestamp}
danmu_cache = {}
DANMU_CACHE_EXPIRATION = 12 * 3600  # 弹幕下载缓存有效期，12小时（秒）

# 线程锁，用于确保precache_parent_directory_files函数同一时间只能运行一个实例
precache_lock = threading.Lock()
from danmu import download_danmaku
def get_token_from_config() -> str:
    """从db目录下的config.txt文件中读取token"""
    config_path = os.path.join('db', 'config.txt')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            token = f.read().strip()
            logger.info("成功从配置文件读取token")
            return token
    except Exception as e:
        logger.error(f"读取配置文件失败: {str(e)}")
        raise Exception(f"无法从配置文件读取token: {str(e)}")

def remove_chinese_symbols(text: str) -> str:
    """去除文本中的所有中文符号，保留英文的特殊字符"""
    # 中文符号正则表达式
    chinese_symbols = re.compile(r'[\u3000-\u303f\uff00-\uffef\u2000-\u206f·]')
    # 移除所有中文符号
    result = chinese_symbols.sub('', text)
    return result

def get_download_url_by_path(file_path: str) -> str:
    """
    从文件路径中提取文件名并搜索文件，返回与文件名完全匹配且文件大小最大的文件的下载直链
    优先使用缓存中的链接（有效期30分钟）
    参数:
        file_path: 完整的文件路径，例如："/CloudNAS/CloudDrive/123云盘/Video/通用格式影视库/电视节目/国产剧集/2025/侠医 (2025) {tmdb-298444}/Season 1/侠医.2025.S01E01.第1集.1080p.MyTVSuper.WEB-DL.H.265.mkv"
    返回:
        字符串 (下载直链)，如果没有找到匹配项则返回 None
    """
    if os.getenv('DANMAKU_API_URL', "") and os.getenv('DANMAKU_API_KEY', ""):
        # 检查弹幕下载缓存
        current_time = time.time()
        if file_path in danmu_cache:
            cache_time = danmu_cache[file_path]
            if current_time - cache_time < DANMU_CACHE_EXPIRATION:
                remaining_time = (DANMU_CACHE_EXPIRATION - (current_time - cache_time)) / 3600
                logger.info(f"弹幕下载已缓存，剩余有效期: {remaining_time:.1f}小时，跳过下载操作")
            else:
                # 缓存已过期，执行弹幕下载
                logger.info("弹幕下载缓存已过期，重新执行下载操作")
                download_danmaku(file_path)
                # 更新缓存时间
                danmu_cache[file_path] = current_time
        else:
            # 缓存不存在，执行弹幕下载
            logger.info("弹幕下载缓存不存在，执行下载操作")
            download_danmaku(file_path)
            # 设置缓存时间
            danmu_cache[file_path] = current_time
        
    # 从文件路径中提取文件名（包含扩展名）作为缓存键
    file_name_with_ext = os.path.basename(file_path)
    
    # 检查缓存中是否有有效链接
    current_time = time.time()
    file_id = None
    if file_name_with_ext in url_cache:
        file_id, cached_url, cache_time = url_cache[file_name_with_ext]
        if (current_time - cache_time < CACHE_EXPIRATION) and cached_url:
            logger.info(f"使用缓存的下载链接，剩余有效期: {(CACHE_EXPIRATION - (current_time - cache_time))/60:.1f}分钟")
            return cached_url
        else:
            del url_cache[file_name_with_ext]  # 删除过期缓存
    
    # 如果有缓存的文件ID，尝试使用它重新获取下载链接
    if file_id:
        logger.info(f"使用缓存的文件ID: {file_id} 获取下载链接")
        token = get_token_from_config()
        download_url = get_file_download_url(file_id, token)
        if download_url:
            logger.info(f"使用文件ID成功获取下载链接: {download_url[:50]}...")
            # 更新缓存
            url_cache[file_name_with_ext] = (file_id, download_url, current_time)
            return download_url
    
    # 记录从文件路径提取的搜索关键词
    logger.info(f"从文件路径提取的搜索关键词: {file_name_with_ext}")
    
    # 去除文件名中的中文符号
    #cleaned_file_name = remove_chinese_symbols(file_name_with_ext)
    #logger.info(f"去除中文符号后的搜索关键词: {cleaned_file_name}")
    cleaned_file_name = file_name_with_ext
    # 2. 使用处理后的文件名调用搜索API
    all_items = []
    try:
        # 从配置文件获取token
        token = get_token_from_config()
        search_url = f"https://www.123pan.com/b/api/file/list/new?driveId=0&limit=100&next=0&orderBy=update_time&orderDirection=desc&parentFileId=0&trashed=false&SearchData={cleaned_file_name}&Page=1&OnlyLookAbnormalFile=0&event=homeListFile&operateType=2&inDirectSpace=false"
        headers = {
            'Authorization': f'Bearer {token}',
            'Platform': 'web'
        }           
        response = requests.get(
            search_url,
            headers=headers,
            timeout=15
        )            
        data = response.json()        
        # 检查是否搜索成功
        if data.get('code') != 0:
            logger.warning(f"未找到文件: {file_name_with_ext}")
            return None       
        items = data.get('data', {}).get('InfoList', [])
        all_items.extend(items)
            
        logger.info(f"找到 {len(all_items)} 个匹配的搜索结果")
        # 3. 筛选出与文件名完全一致的结果（包含扩展名）
        exact_matches = []
        for item in all_items:
            # 确保item是字典类型且包含'FileName'字段，并且Type为0
            if isinstance(item, dict) and 'FileName' in item and item.get('Type') == 0:
                # 比较文件名（包含扩展名）是否完全匹配
                item_name = item['FileName']
                # 去掉扩展名后检查是否在目标文件名中存在，并且扩展名一致
                file_name_no_ext = file_name_with_ext.rsplit('.', 1)[0] if '.' in file_name_with_ext else file_name_with_ext
                item_ext = item_name.rsplit('.', 1)[1].lower() if '.' in item_name else ''
                target_ext = file_name_with_ext.rsplit('.', 1)[1].lower() if '.' in file_name_with_ext else ''
                if file_name_no_ext in item_name and item_ext == target_ext and not item.get('Trashed'):
                    logger.info(f"找到匹配: '{item_name}'")
                    exact_matches.append(item)
        logger.info(f"筛选出 {len(exact_matches)} 个与文件名一致的结果")
        # 4. 如果有多个匹配结果，返回文件大小最大的那个
        download_url = None
        if exact_matches:
            # 找到文件大小最大的项
            largest_file = max(exact_matches, key=lambda x: x.get('BaseSize', 0))
            file_id = largest_file.get('FileId')           
            # 5. 直接获取下载直链
            logger.info(f"获取下载链接: {file_id}")
            url = f"https://open-api.123pan.com/api/v1/file/download_info?fileId={file_id}"
            headers = {
                'Content-Type': 'application/json',
                'Platform': 'open_platform',
                'Authorization': f'Bearer {token}'
            }
            response = requests.get(url, headers=headers)           
            if response.status_code != 200:
                logger.warning(f"未找到文件: {file_name_with_ext}")
                return None
            else:
                data = response.json()
                if data['code'] == 0:
                    download_url = data['data']['downloadUrl']
                    logger.info(f"获取到下载链接: {download_url[:50]}...")
                    if download_url:
                        # 将结果存入缓存（使用文件名作为键）
                        url_cache[file_name_with_ext] = (file_id, download_url, current_time)           
                        # 启动新线程异步预缓存父目录的其他文件
                        if 'ParentFileId' in largest_file:
                            parent_file_id = largest_file['ParentFileId']
                        file_name = largest_file['FileName']
                        threading.Thread(target=precache_parent_directory_files, 
                                        args=(parent_file_id, token, file_name), 
                                        daemon=True).start()
                        return download_url
                else:
                    logger.warning(f"未找到文件: {file_name_with_ext}")
                    return None
           
        if download_url == None:
            # 使用guessit获取标题名
            guess_result = guessit.guessit(cleaned_file_name)
            
            # 后备方案：优先使用空格分割，如果没有空格则使用点号分割
            if 'title' not in guess_result:
                if ' ' in cleaned_file_name:
                    first_part = cleaned_file_name.split(' ')[0]
                elif '.' in cleaned_file_name:
                    first_part = cleaned_file_name.split('.')[0]
                else:
                    first_part = cleaned_file_name
            else:
                if guess_result['type'] == 'episode':
                    # 从原始文件名中提取S01E05或s01e02格式的季数和集数（不区分大小写）
                    season_episode_match = re.search(r'S\d+E\d+', file_path, re.IGNORECASE)
                    if season_episode_match:
                        season_episode = season_episode_match.group()
                        first_part = guess_result['title'] + season_episode
                    else:
                        first_part = guess_result['title']
                else:
                    first_part = guess_result['title']
            print(first_part)
            logger.info(f"进行第二轮搜索，使用guessit提取的标题名: {first_part}")
            search_url_first_part = f"https://www.123pan.com/b/api/file/list/new?driveId=0&limit=100&next=0&orderBy=update_time&orderDirection=desc&parentFileId=0&trashed=false&SearchData={first_part}&Page=1&OnlyLookAbnormalFile=0&event=homeListFile&operateType=2&inDirectSpace=false"
            response_second = requests.get(
                search_url_first_part,
                headers=headers,
                timeout=15
            )
            data_second = response_second.json()
            if data_second.get('code') == 0:
                items_second = data_second.get('data', {}).get('InfoList', [])
                all_items=[]
                all_items.extend(items_second)
                logger.info(f"第二轮搜索找到 {len(items_second)} 个匹配的搜索结果")
                exact_matches = []
                for item in all_items:
                     # 确保item是字典类型且包含'FileName'字段，并且Type为0
                    if isinstance(item, dict) and 'FileName' in item and item.get('Type') == 0:
                        # 比较文件名（包含扩展名）是否完全匹配
                        item_name = item['FileName']
                        # 去掉扩展名后检查是否在目标文件名中存在，并且扩展名一致
                        file_name_no_ext = file_name_with_ext.rsplit('.', 1)[0] if '.' in file_name_with_ext else file_name_with_ext
                        item_ext = item_name.rsplit('.', 1)[1].lower() if '.' in item_name else ''
                        target_ext = file_name_with_ext.rsplit('.', 1)[1].lower() if '.' in file_name_with_ext else ''
                        if file_name_no_ext in item_name and item_ext == target_ext and not item.get('Trashed'):
                            logger.info(f"找到匹配: '{item_name}'")
                            exact_matches.append(item)
                logger.info(f"筛选出 {len(exact_matches)} 个与文件名完全一致的结果")
                # 4. 如果有多个匹配结果，返回文件大小最大的那个
                download_url = None
                if exact_matches:
                    # 找到文件大小最大的项
                    largest_file = max(exact_matches, key=lambda x: x.get('BaseSize', 0))
                    file_id = largest_file.get('FileId')           
                    # 5. 直接获取下载直链
                    logger.info(f"获取下载链接: {file_id}")
                    url = f"https://open-api.123pan.com/api/v1/file/download_info?fileId={file_id}"
                    headers = {
                        'Content-Type': 'application/json',
                        'Platform': 'open_platform',
                        'Authorization': f'Bearer {token}'
                    }
                    response = requests.get(url, headers=headers)           
                    if response.status_code != 200:
                        logger.warning(f"未找到文件: {file_name_with_ext}")
                        return None
                    else:
                        data = response.json()
                        if data['code'] == 0:
                            download_url = data['data']['downloadUrl']
                            logger.info(f"获取到下载链接: {download_url[:50]}...")
                            if download_url:
                                # 将结果存入缓存（使用文件名作为键）
                                url_cache[file_name_with_ext] = (file_id, download_url, current_time)           
                                # 启动新线程异步预缓存父目录的其他文件
                                if 'ParentFileId' in largest_file:
                                    parent_file_id = largest_file['ParentFileId']
                                file_name = largest_file['FileName']
                                threading.Thread(target=precache_parent_directory_files, 
                                                args=(parent_file_id, token, file_name), 
                                                daemon=True).start()
                                return download_url
                        else:
                            logger.warning(f"未找到文件: {file_name_with_ext}")
                            return None
            else:
                logger.warning(f"第二轮搜索失败: {data_second.get('message', '未知错误')}")
                return None

        logger.warning(f"未找到文件: {file_name_with_ext}")
        return download_url
    except Exception as e:
        logger.error(f"搜索或获取下载链接过程中发生错误: {str(e)}")
        return None

def precache_parent_directory_files(parent_file_id: str, token: str, current_file_name: str) -> None:
    """
    预缓存父目录中的其他文件下载链接
    参数:
        parent_file_id: 父目录ID
        token: 认证token
        current_file_name: 当前正在处理的文件名
    说明:
        使用线程锁确保同一时间只能有一个实例运行，多个并发请求会排队依次执行
    """
    # 获取锁，如果已被占用则等待
    logger.info("尝试获取预缓存函数执行锁")
    precache_lock.acquire()
    logger.info("成功获取预缓存函数执行锁")
    
    try:
        
        
        # 清理过期缓存
        cleaned_count = 0
        current_time = time.time()
        expired_keys = []
        
        for key, (_, _, cache_time) in url_cache.items():
            if current_time - cache_time > CACHE_EXPIRATION:
                expired_keys.append(key)
        
        for key in expired_keys:
            del url_cache[key]
            cleaned_count += 1
        
        logger.info(f"清理了{cleaned_count}个过期缓存项")
        
        # 清理过期的父目录缓存
        parent_cleaned_count = 0
        parent_expired_keys = []
        for key, cache_time in parent_dir_cache.items():
            if current_time - cache_time > PARENT_DIR_CACHE_EXPIRATION:
                parent_expired_keys.append(key)
        
        for key in parent_expired_keys:
            del parent_dir_cache[key]
            parent_cleaned_count += 1
        
        if parent_cleaned_count > 0:
            logger.info(f"清理了{parent_cleaned_count}个过期父目录缓存项")
        
        # 检查父目录ID是否已缓存，如果已缓存且在有效期内则跳过预缓存
        current_time = time.time()
        if parent_file_id in parent_dir_cache:
            cache_time = parent_dir_cache[parent_file_id]
            if current_time - cache_time < PARENT_DIR_CACHE_EXPIRATION:
                remaining_time = (PARENT_DIR_CACHE_EXPIRATION - (current_time - cache_time)) / 3600
                logger.info(f"父目录(ID: {parent_file_id})已缓存，剩余有效期: {remaining_time:.1f}小时，跳过预缓存操作")
                return
        
        # 调用API获取父目录的文件列表，支持翻页
        headers = {
            'Authorization': f'Bearer {token}',
            'Platform': 'open_platform'
        }
        logger.info(f"开始预缓存父目录(ID: {parent_file_id})中的其他文件")
        # 初始化变量
        all_files = []
        last_file_id = 0
        page = 1
        
        while True:
            # 构建请求URL，包含翻页参数
            list_url = f"https://open-api.123pan.com/api/v2/file/list?parentFileId={parent_file_id}&limit=100&lastFileId={last_file_id}"
            response = requests.get(list_url, headers=headers, timeout=15)
            data = response.json()
            
            if data.get('code') != 0:
                logger.error(f"获取父目录文件列表失败(第{page}页): {data.get('message')}")
                if page == 1:  # 第一页就失败，直接返回
                    return
                else:  # 非第一页失败，使用已获取的文件继续处理
                    break
            
            # 获取当前页的文件列表
            page_files = data.get('data', {}).get('fileList', [])
            all_files.extend(page_files)
            
            logger.info(f"获取到父目录第{page}页文件，数量: {len(page_files)}, 累计: {len(all_files)}个文件")
            
            # 判断是否需要继续翻页
            if len(page_files) < 100:
                # 文件数量不足100，说明没有更多文件
                break
            
            # 更新lastFileId为当前页最后一个文件的ID
            last_file_id = page_files[-1].get('fileId', -1)
            if last_file_id == -1:
                # 达到最后一页
                logger.info(f"已获取到最后一页文件")
                break
            
            page += 1
            # 避免请求过于频繁
            time.sleep(0.2)
        
        # 获取文件列表
        files = all_files
        logger.info(f"获取到父目录中所有文件，总计{len(files)}个文件")
        
        # 定义允许预缓存的视频文件扩展名
        allowed_extensions = {'.mp4', '.mkv', '.ts', '.rmvb', '.avi', '.mov', '.mpeg', '.mpg', '.wmv', '.3gp', '.asf', '.m4v', '.flv', '.m2ts', '.tp', '.f4v', '.rm', '.iso'}
        
        # 过滤出非当前文件、类型为文件(非目录)、符合视频扩展名且尚未缓存的项
        file_items = []
        for f in files:
            if f.get('type') == 0 and f.get('filename') != current_file_name and f.get('trashed') == 0:
                filename = f.get('filename')
                if filename:
                    # 检查文件扩展名是否在允许的列表中
                    _, ext = os.path.splitext(filename)
                    if ext.lower() not in allowed_extensions:
                        continue
                    
                    # 构建缓存键并检查是否已缓存
                    cache_key = f"{filename}"
                    if cache_key not in url_cache:
                        file_items.append(f)
        logger.info(f"过滤后需预缓存{len(file_items)}个视频文件")
        
        # 依次获取这些文件的信息并缓存
        cached_count = 0
        need_cache_count = len(file_items)
        is_large_batch = need_cache_count > get_int_env("MAX_CACHE_302LINK", 100)
        
        for file_item in file_items:
            file_id = file_item.get('fileId')
            filename = file_item.get('filename')
            
            if not file_id or not filename:
                continue
            
            try:
                # 直接使用文件名作为缓存键
                # 检查是否已缓存
                if filename in url_cache:
                    continue
                
                if is_large_batch:
                    # 如果文件数量大于100，只缓存文件ID和时间戳，不获取直链
                    url_cache[filename] = (file_id, None, time.time())
                    cached_count += 1
                    #logger.info(f"成功预缓存文件ID: {filename}")
                else:
                    # 获取下载链接
                    download_url = get_file_download_url(file_id, token)
                    time.sleep(0.5)
                    if download_url:
                        # 缓存链接（使用文件名作为键）
                        url_cache[filename] = (file_id, download_url, time.time())
                        cached_count += 1
                        logger.info(f"成功预缓存文件: {filename}，{download_url}")
                
                # 间隔0.5秒请求下一个
                
            except Exception as e:
                logger.error(f"预缓存文件{filename}失败: {str(e)}")
                continue
        
        logger.info(f"父目录文件预缓存完成，成功缓存{cached_count}个文件")
        
        # 缓存父目录ID，有效期12小时
        parent_dir_cache[parent_file_id] = time.time()
        logger.info(f"已缓存父目录ID: {parent_file_id}，有效期12小时")
    except Exception as e:
        logger.error(f"预缓存父目录文件过程中发生错误: {str(e)}")
    finally:
        # 确保在函数结束时释放锁
        precache_lock.release()

def get_file_download_url(file_id: str, token: str) -> str:
    """
    获取单个文件的下载链接
    参数:
        file_id: 文件ID
        token: 认证token
    返回:
        下载链接字符串，失败返回None
    """
    try:
        url = f"https://open-api.123pan.com/api/v1/file/download_info?fileId={file_id}"
        headers = {
            'Content-Type': 'application/json',
            'Platform': 'open_platform',
            'Authorization': f'Bearer {token}'
        }
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        if data['code'] != 0:
            return None
        
        return data['data']['downloadUrl']
    except Exception as e:
        logger.error(f"获取文件ID {file_id} 的下载链接失败: {str(e)}")
        return None

if __name__ == "__main__":
    # 测试get_download_url_by_path函数
    test_file_path = "非我所愿.2020.S01E05.第5集.1080p.HDR10.H.265.10-bit.24fps.mkv"
    
    try:
        print("\n===== 测试get_download_url_by_path函数 =====")
        print(f"测试文件路径: {test_file_path}")
        
        # 为搜索调用添加计时
        search_start_time = time.time()
        download_url = get_download_url_by_path(test_file_path)
        search_end_time = time.time()
        
        print(f"搜索完成，耗时: {search_end_time - search_start_time:.4f} 秒")
        
        # 打印找到的下载链接信息
        if download_url:
            print(f"找到匹配的文件并获取到下载链接：")
            print(f"下载链接: {download_url}")
        else:
            print("未找到与文件名完全匹配的结果")
        
    except Exception as e:
        print(f"搜索或获取下载链接过程中发生错误: {str(e)}")

