import re
import os
import time
import random
import logging
import requests
import json
import guessit
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv(dotenv_path="db/user.env",override=True)


ADD_TITLE=os.getenv("ENV_ADD_TITLE", "")
# ========================= 全局配置 =========================
# 媒体类型判断规则
TV_KEYWORDS = {
    'patterns': [
        r'S\d{1,3}E\d{1,3}',    # 季集格式
        r'[Ee][Pp]?\d{1,3}',     # EP/E格式
        r'第[0-9一二三四五六七八九十]+集', # 中文集数
        r'[第].[季]'             # 季数标识
    ],
    'folder_keywords': [
        'season', 'seasons',
        '季', '多季',
        '第.季', r'\bs\d\b'
    ]
}

CONFIG = {
    "tmdb": {
        "api_key": os.getenv("ENV_TMDB_API_KEY", "") or ""  # 请填写实际TMDB API密钥
    },
    "forum": {
        "cookie": os.getenv("ENV_123PANFX_COOKIE", ""),
        # 请填写实际论坛Cookie
        "base_url": os.getenv("ENV_123PANFX_BASE_URL", "https://pan1.me"),
        "fid_mapping": {
            "tv": "48",  # 电视剧版块ID
            "movie": "2",  # 电影版块ID
            "anime": "37"
        },
        "fixed_tags": [],
        "interval": 65  # 发帖间隔秒数
    },
    "test_mode": False,
    "post_record": "db/posted_records.txt",
    "blocked_record": "db/blocked_records.txt",
    "debug": True,
    # 标签映射配置
    "tag_mapping": {
        "tv": {
            "quality": {"480p": "22", "720p": "23", "1080p": "24", "2k": "25", "4k": "26", "2160p": "26",
                        "default": "24"},
            "source": {"hdtv": "221", "hdrip": "221", "bluray": "218", "remux": "218", "webdl": "220", "webrip": "220",
                       "bdrip": "219", "nlurayncode": "219", "default": "221"},
            "region": {"大陆": "49", "香港": "50", "台湾": "51", "韩国": "52", "日本": "53", "欧美": "54", "其他": "55",
                       "default": "55"}
        },
        "movie": {
            "quality": {"480p": "7", "720p": "8", "1080p": "1", "2k": "2", "4k": "3", "2160p": "3", "default": "1"},
            "source": {"hdtv": "258", "hdrip": "258", "bluray": "257", "remux": "257", "webdl": "259", "webrip": "259",
                       "bdrip": "258", "nlurayncode": "258", "default": "258"},
            "region": {"大陆": "41", "香港": "42", "台湾": "43", "韩国": "44", "日本": "46", "欧美": "47", "其他": "48",
                       "default": "48"}
        },
        "anime": {
            "quality": {"480p": "113", "720p": "114", "1080p": "115", "2k": "116", "4k": "117", "2160p": "117", "default": "115"},
            "source": {"hdtv": "221", "hdrip": "221", "bluray": "218", "remux": "218", "webdl": "220", "webrip": "220",
                       "bdrip": "219", "nlurayncode": "219", "default": "221"},
            "region": {"大陆": "70", "香港": "70", "台湾": "70", "韩国": "73", "日本": "71", "欧美": "72", "其他": "73",
                       "default": "73"}
        }
    },
    # 国家到地区映射
    "country_region_mapping": {"CN": "大陆", "HK": "香港", "TW": "台湾", "KR": "韩国", "JP": "日本", "US": "欧美",
                               "GB": "欧美", "FR": "欧美", "DE": "欧美", "CA": "欧美", "AU": "欧美", "default": "其他"},
    # 类型标签映射
    "genre_tag_mapping": {
        "tv": {"古装": "27", "喜剧": "39", "动作": "38", "爱情": "36", "悬疑": "35", "奇幻": "34", "冒险": "33",
               "犯罪": "32", "战争": "37", "惊悚": "31", "剧情": "30", "历史": "29", "纪录片": "28", "动画": "40"},
        "movie": {"古装": "21", "家庭": "212", "恐怖": "198", "灾难": "194", "科幻": "193", "动画": "20",
                  "纪录片": "19", "历史": "18", "剧情": "17", "惊悚": "16", "犯罪": "15", "冒险": "14", "奇幻": "13",
                  "悬疑": "12", "爱情": "11", "战争": "10", "动作": "9", "喜剧": "6", "演唱会": "215"},
        "anime": {"古装": "233", "喜剧": "230", "动作": "229", "爱情": "238", "悬疑": "237", "奇幻": "228", "冒险": "240", "犯罪": "247", "战争": "226", "惊悚": "237", "剧情": "231", "历史": "241", "纪录片": "241", "动画": "223"}
    },
    "video_extensions": ['.mkv', '.ts', '.mp4', '.avi', '.rmvb', '.wmv', '.m2ts', '.mpg', '.flv', '.rm', '.mov']
}

# ========================= 日志配置 =========================
logger = logging.getLogger(__name__)

# ========================= TMDB元数据处理器 =========================
class TMDBHelper:
    def __init__(self):
        self.base_url = "https://api.themoviedb.org/3"
        self.session = requests.Session()

    def parse_metadata(self, folder_name: str) -> Dict:
        logger.debug(f"▷ 解析文件夹名称（提取TMDB信息）: {folder_name}")

        # 2. 提取TMDB ID（保持原有逻辑）
        tmdb_id_pattern = r'[{\[](?:tmdb(?:id)?)(?:=|-)(\d+)[}\]]'
        tmdb_match = re.search(tmdb_id_pattern, folder_name)
        tmdb_id = tmdb_match.group(1) if tmdb_match else None

        # 1. 预处理文件夹名称，提高guessit识别率
        # 1.1 转换中文括号为英文括号
        folder_name = folder_name.replace('（', '(').replace('）', ')')
        # 1.2 标准化空格和分隔符
        folder_name = re.sub(r'[\s\-_]+', ' ', folder_name).strip()
        # 1.3 移除常见的标记和后缀
        folder_name = re.sub(r'\[.*?\]|\{.*?\}', '', folder_name).strip()
        # 1.4 移除分辨率、格式等信息
        format_patterns = [
            r'\d{3,4}p', r'\d{3,4}i', r'HD', r'4K', r'8K',
            r'WEB[-_.]?DL', r'BD[-_.]?REMUX', r'BD[-_.]?RIP',
            r'DVDRIP', r'CAM', r'HDTV', r'Blu[-_.]?ray',
            r'x264', r'x265', r'H\.264', r'H\.265',
            r'DDP\d+\.\d+', r'AC3', r'DTS', r'FLAC'
        ]
        for pattern in format_patterns:
            folder_name = re.sub(pattern, '', folder_name, flags=re.IGNORECASE)
        folder_name = re.sub(r'\s+', ' ', folder_name).strip()
        
        # 3. 如果找到tmdb_id，从文件夹名中移除该部分
        cleaned_name = re.sub(re.escape(tmdb_match.group(0)), '', folder_name) if tmdb_match else folder_name
        cleaned_name = cleaned_name.strip()

        # 4. 使用guessit提取标题和年份，提供类型提示提高准确性
        # 尝试电影类型
        guess = guessit.guessit(cleaned_name)
        # 如果没有识别到标题，尝试电视剧类型
        #if not guess.get('title'):
           # guess = guessit.guessit(cleaned_name, options={'type': 'episode'})
            # 如果还是没有识别到，尝试通用类型
           # if not guess.get('title'):
              #  guess = guessit.guessit(cleaned_name)
        title = guess.get('title')
        year = guess.get('year')

        # 如果guessit没有提取到标题，回退到原有正则表达式
        if not title:
            pattern = r"(.+?)[^\d]*(?:\b(\d{4})\b)?.*"
            match = re.match(pattern, cleaned_name.strip())
            if match and match.group(1):
                title = match.group(1).strip()
            # 如果guessit没有提取到年份，且正则表达式匹配到了，使用正则表达式的年份
            if not year and match and match.group(2):
                year = match.group(2)

        if not title and not tmdb_id:
            logger.warning("✘ 文件夹名称格式错误（未找到可识别的信息）")
            return {}

        return {
            "title": title,
            "year": year,
            "tmdb_id": tmdb_id
        }

    def get_metadata(self, folder_name: str, media_type: str = "tv") -> Dict:
        parsed = self.parse_metadata(folder_name)
        logger.info(f"媒体类型: {media_type.upper()} | 标题: {parsed['title']}")
        if parsed.get("tmdb_id"):
            logger.info(f"→ 使用TMDB ID查询: {parsed['tmdb_id']}")
            actual_media_type = "tv" if media_type == "anime" else media_type
            metadata = self._get_by_id(parsed["tmdb_id"], actual_media_type)
            if metadata:
                return metadata
            logger.warning("ID查询失败")
        search_year = parsed.get("year")
        logger.info(f"→ 执行标题搜索: {parsed['title']}{f' ({search_year})' if search_year else ''}")
        metadata = self._search(parsed["title"], search_year, media_type)
        if metadata:
            return metadata
        logger.error("✘ 所有查询方式均失败")
        return {}
    
    def get_metadata_optimize(self, folder_name: str, file_name: str) -> Dict:
        # 判断是否是剧集
        is_tv_show = False
        # 检查文件名中的剧集特征
        for pattern in TV_KEYWORDS['patterns']:
            if re.search(pattern, file_name):
                is_tv_show = True
                break
        # 检查文件夹名中的剧集关键词
        if not is_tv_show:
            for keyword in TV_KEYWORDS['folder_keywords']:
                if re.search(keyword, folder_name, re.IGNORECASE):
                    is_tv_show = True
                    break
        
        media_type = 'tv' if is_tv_show else 'movie'
        parsed = self.parse_metadata(folder_name)
        logger.info(f"媒体类型: {media_type.upper()} | 标题: {parsed['title']}")
        
        if parsed.get("tmdb_id"):
            logger.info(f"→ 使用TMDB ID查询: {parsed['tmdb_id']}")
            actual_media_type = "tv" if media_type == "anime" else media_type
            metadata = self._get_by_id(parsed["tmdb_id"], actual_media_type)
            if metadata:
                return metadata
            logger.warning("ID查询失败，尝试标题搜索")
        
        search_year = parsed.get("year")
        logger.info(f"→ 执行标题搜索: {parsed['title']}{f' ({search_year})' if search_year else ''}")
        metadata = self._search(parsed["title"], search_year, media_type)
        
        # 验证TMDB返回的标题是否在文件夹名中
        if metadata:
            return metadata
            tmdb_title = metadata.get('title', '').lower()
            if tmdb_title and tmdb_title not in folder_name.lower():
                logger.warning(f"✘ 搜索结果标题 '{metadata['title']}' 未在文件夹名 '{folder_name}' 中找到，可能不匹配")
                # 尝试使用更精确的搜索
                precise_metadata = self._search(f"{parsed['title']} {search_year}" if search_year else parsed['title'], None, media_type)
                if precise_metadata and precise_metadata.get('title', '').lower() in folder_name.lower():
                    metadata = precise_metadata
                else:
                    # 如果仍不匹配，返回空字典
                    return {}
            return metadata
        
        logger.error("✘ 所有查询方式均失败")
        return {}
    
    def get_metadata_onlyid(self, folder_name: str, media_type: str = "tv") -> Dict:
        parsed = self.parse_metadata(folder_name)
        logger.info(f"媒体类型: {media_type.upper()} | 标题: {parsed['title']}")
        if parsed.get("tmdb_id"):
            logger.debug(f"→ 使用TMDB ID查询: {parsed['tmdb_id']}")
            actual_media_type = "tv" if media_type == "anime" else media_type
            metadata = self._get_by_id(parsed["tmdb_id"], actual_media_type)
            if metadata:
                return metadata
            logger.warning("ID查询失败，尝试标题搜索")        
        return {}

    def _get_by_id(self, tmdb_id: str, media_type: str) -> Dict:
        try:
            endpoint = f"{self.base_url}/{media_type}/{tmdb_id}"
            params = {
                "api_key": CONFIG["tmdb"]["api_key"],
                "language": "zh-CN",
                "append_to_response": "credits"
            }
            response = self.session.get(
                endpoint,
                params=params,
                timeout=15
            )
            #print(response.json())
            response.raise_for_status()
            return self._format_data(response.json(), media_type)
        except Exception as e:
            logger.error(f"ID查询失败: {str(e)}")
            return {}

    def _search(self, title: str, year: str = None, media_type: str = "tv") -> Dict:
        try:
            endpoint = f"{self.base_url}/search/{media_type}"
            params = {
                "api_key": CONFIG["tmdb"]["api_key"],
                "query": title,
                "year": year,
                "language": "zh-CN"
            }
            if media_type == "tv":
                params["first_air_date_year"] = year
            else:
                params["year"] = year
            response = self.session.get(
                endpoint,
                params=params,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("results"):
                logger.warning("✘ 未找到匹配结果")
                return {}
            best_match = data["results"][0]
            logger.info(f"找到最佳匹配: {best_match.get('title', best_match.get('name'))} (ID: {best_match['id']})")
            return self._get_by_id(str(best_match["id"]), media_type)
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return {}

    def _format_data(self, data: Dict, media_type: str) -> Dict:
        status = data.get("status", "Ended" if media_type == "tv" else "Released").lower()
        result = {
            "tmdb_id": data.get("id"),
            "title": data.get("title") if media_type == "movie" else data.get("name"),
            "year": self._get_year(data, media_type),
            "rating": round(data.get("vote_average", 0), 1),
            "genres": [g["name"] for g in data.get("genres", [])],
            "poster": f"https://image.tmdb.org/t/p/w500{data.get('poster_path', '')}",
            "backdrop": f"https://image.tmdb.org/t/p/w1280{data.get('backdrop_path', '')}" if data.get('backdrop_path', '') else "",
            "plot": data.get("overview", "暂无简介"),
            "countries": self._get_countries(data, media_type),
            "status": status
        }
        result["director"] = self._get_director(data, media_type)
        result["cast"] = self._get_main_cast(data, media_type)
        if media_type == "tv":
            result["seasons"] = data.get("number_of_seasons", 0)
            result["episodes"] = data.get("number_of_episodes", 0)
        logger.info(f"格式化元数据成功: {result['title']}")
        return result

    def _get_year(self, data: Dict, media_type: str) -> str:
        date_field = "release_date" if media_type == "movie" else "first_air_date"
        date_str = data.get(date_field, "")
        return date_str[:4] if date_str and len(date_str) >= 4 else "未知年份"

    def _get_director(self, data: Dict, media_type: str) -> str:
        if media_type == "movie":
            crew = data.get("credits", {}).get("crew", [])
            directors = [p["name"] for p in crew if p.get("job") == "Director"]
            return " / ".join(directors[:3]) if directors else "未知"
        else:
            creators = [c["name"] for c in data.get("created_by", [])]
            return " / ".join(creators) if creators else "未知"

    def _get_main_cast(self, data: Dict, media_type: str) -> str:
        cast = data.get("credits", {}).get("cast", [])
        max_cast = 4 if media_type == "movie" else 6
        return " / ".join([p["name"] for p in cast[:max_cast]]) if cast else "未知"

    def _get_countries(self, data: Dict, media_type: str) -> List[str]:
        if media_type == "movie":
            return [c["iso_3166_1"] for c in data.get("production_countries", [])]
        else:
            return data.get("origin_country", [])


# ========================= 论坛发帖器 =========================
class ForumPoster:
    def __init__(self):
        self.test_mode = CONFIG["test_mode"]
        self.base_url = CONFIG["forum"]["base_url"]
        self.interval = CONFIG["forum"].get("interval", 90)
        self.last_post_time = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": CONFIG["forum"]["cookie"],
            "X-Requested-With": "XMLHttpRequest"
        }

    def _get_status_tag(self, status: str, media_type: str) -> str:
        if not status:
            logger.warning("状态值为空，使用默认标签")
            # 状态为空时，动漫默认返回111，其他类型返回109
            return "111" if media_type == "anime" else "109"

        tv_status_mapping = {
            "ended": "109",
            "returning series": "110",
            "planned": "110",
            "in production": "110"
        }
        movie_status_mapping = {
            "released": "109",
            "post production": "110",
            "in production": "110"
        }
        # 新增动漫专属状态映射
        anime_status_mapping = {
            "ended": "111",
            "returning series": "112",
            "planned": "112",
            "in production": "112"
        }

        # 根据媒体类型选择对应的映射表
        if media_type == "tv":
            mapping = tv_status_mapping
        elif media_type == "anime":
            mapping = anime_status_mapping  # 动漫使用专属映射
        else:
            mapping = movie_status_mapping

        status_lower = status.lower()
        # 精确匹配状态
        if status_lower in mapping:
            return mapping[status_lower]
        # 模糊匹配状态（包含关键词）
        for key in mapping.keys():
            if key in status_lower:
                return mapping[key]

        # 未匹配到任何状态时，动漫默认返回111，其他类型返回109
        return "111" if media_type == "anime" else "109"

    def _get_genre_tag(self, genres: List[str], media_type: str) -> str:
        mapping = CONFIG["genre_tag_mapping"].get(media_type, {})
        for genre in genres:
            if genre in mapping:
                return mapping[genre]
            clean_genre = genre.strip().replace(" ", "")
            if clean_genre in mapping:
                return mapping[clean_genre]
        # 为动漫单独设置默认标签（使用论坛允许的标签ID）
        if media_type == "tv":
            return "30"
        elif media_type == "movie":
            return "17"
        else:  # anime
            return "250"  # 默认为“日常”标签（对应tagid=231，属于动漫版块允许的标签）

    def post(self, title: str, content: Dict, media_type: str, video_info: Dict) -> bool:
        try:
            fid = CONFIG["forum"]["fid_mapping"].get(media_type, CONFIG["forum"]["fid_mapping"]["tv"])
            logger.info(f"自动匹配版块ID: {fid}（媒体类型: {media_type}）")

            if not self.test_mode:
                self._enforce_post_interval()

            self.headers["Referer"] = f"{self.base_url}/thread-create-{fid}.htm"

            formatted_content = self._generate_content(content)
            if self.test_mode:
                self._show_preview(title, formatted_content)
                return True

            tags = self._get_tags(content, video_info, media_type)
            genre_tag = self._get_genre_tag(content.get("genres", []), media_type)
            tags.append(genre_tag)
            status = content.get("status", "")
            status_tag = self._get_status_tag(status, media_type)
            # 电视剧和动漫都添加状态标签
            if media_type in ["tv", "anime"]:
                tags.append(status_tag)

            success = self._submit_post(title, formatted_content, tags, fid)
            human_delay = random.uniform(1, 3) if success else 0
            time.sleep(human_delay)
            return success
        except Exception as e:
            logger.error(f"发帖失败: {str(e)}")
            self.last_post_time = None
            return False

    def _enforce_post_interval(self):
        if self.last_post_time and (time.time() - self.last_post_time) < self.interval:
            wait = self.interval - (time.time() - self.last_post_time)
            logger.info(f"发帖冷却中 | 等待: {wait:.1f}s")
            time.sleep(wait)

    def _generate_content(self, content: Dict) -> str:
        return f'''
    <div class="movie-card">
    <div class="movie-poster"><img src="{content.get('poster', '')}" alt="{content.get('title', '')} 海报"></div>
    <div class="movie-info">
    <h2 class="movie-title">{content.get('title', '未知标题')}</h2>
    <div class="movie-details">
    <div class="detail-label">评分：</div>
    <div>{content.get('rating', '无')}</div>
    <div class="detail-label">年份：</div>
    <div>{content.get('year', '未知年份')}</div>
    <div class="detail-label">类型：</div>
    <div>{'/ '.join(content.get('genres', ['未知']))}</div>
    <div class="detail-label">导演：</div>
    <div>{content.get('director', '未知')}</div>
    <div class="detail-label">主演：</div>
    <div>{content.get('cast', '未知')}</div>
    </div>
    </div>
    </div>
    <div class="movie-plot">
    <h3 class="plot-title">剧情简介：</h3>
    <p class="plot-content">{content.get('plot', '暂无简介')}</p>
    </div>
    <p>&nbsp;[ttreply] <a href="{content.get('share_url', '#')}" target="_blank" rel="noopener"><span style="color: #0070c0;">{content.get('share_url', '链接获取失败')}</span></a> [/ttreply]</p>
    '''

    def _get_region_tag(self, countries: List[str], media_type: str) -> str:
        mapping = CONFIG["tag_mapping"][media_type]["region"]
        country_mapping = CONFIG["country_region_mapping"]
        for country in countries:
            region = country_mapping.get(country, country_mapping["default"])
            if region in mapping:
                return mapping[region]
        return mapping[country_mapping["default"]]

    def _get_quality_tag(self, video_info: Dict, media_type: str) -> str:
        resolution = video_info.get("screen_size", video_info.get("resolution", "")).lower()
        if not resolution:
            return CONFIG["tag_mapping"][media_type]["quality"]["default"]
        mapping = CONFIG["tag_mapping"][media_type]["quality"]
        if resolution in mapping:
            return mapping[resolution]
        for key in mapping.keys():
            if key in resolution:
                return mapping[key]
        if "1080" in resolution:
            return mapping.get("1080p", mapping["default"])
        elif "720" in resolution:
            return mapping.get("720p", mapping["default"])
        elif "480" in resolution:
            return mapping.get("480p", mapping["default"])
        elif "4k" in resolution or "2160" in resolution:
            return mapping.get("4k", mapping["default"])
        elif "2k" in resolution:
            return mapping.get("2k", mapping["default"])
        return mapping["default"]

    def _get_source_tag(self, video_info: Dict, media_type: str) -> str:
        source = video_info.get("source", "").lower()
        if not source:
            return CONFIG["tag_mapping"][media_type]["source"]["default"]
        mapping = CONFIG["tag_mapping"][media_type]["source"]
        if source in mapping:
            return mapping[source]
        for key in mapping.keys():
            if key in source:
                return mapping[key]
        if "blu" in source or "bd" in source:
            return mapping.get("bluray", mapping["default"])
        elif "remux" in source:
            return mapping.get("remux", mapping["default"])
        elif "web" in source:
            return mapping.get("webdl", mapping["default"])
        elif "tv" in source:
            return mapping.get("hdtv", mapping["default"])
        elif "rip" in source:
            return mapping.get("bdrip", mapping["default"])
        return mapping["default"]

    def _get_hdr_tag(self, video_info: Dict, media_type: str) -> str:
        profile = video_info.get("video_profile", "").lower()
        hdr_formats = ["hdr10", "hdr10+", "dolby vision", "hlg"]
        for hdr in hdr_formats:
            if hdr in profile:
                return hdr.upper()
        codec = video_info.get("video_codec", "").lower()
        for hdr in hdr_formats:
            if hdr in codec:
                return hdr.upper()
        return ""

    def _get_tags(self, content: Dict, video_info: Dict, media_type: str) -> List[str]:
        tags = []
        region_tag = self._get_region_tag(content.get("countries", []), media_type)
        if region_tag:
            tags.append(region_tag)
        quality_tag = self._get_quality_tag(video_info, media_type)
        tags.append(quality_tag)
        source_tag = self._get_source_tag(video_info, media_type)
        tags.append(source_tag)
        hdr_tag = self._get_hdr_tag(video_info, media_type)
        if hdr_tag:
            tags.append(hdr_tag)
        tags.extend(CONFIG["forum"]["fixed_tags"])
        return tags

    def _show_preview(self, title: str, content: str):
        logger.info("\n" + "=" * 120)
        logger.info(f"测试预览 | 标题: {title}")
        logger.info("完整内容:\n" + content)
        logger.info("=" * 120 + "\n")

    def _submit_post(self, title: str, content: str, tags: List[str], fid: str) -> bool:
        try:
            human_delay = random.uniform(1.5, 3.5)
            time.sleep(human_delay)
            form_data = {
                "doctype": "0",
                "quotepid": "0",
                "subject": title + (' ' + ADD_TITLE if ADD_TITLE else ''),
                "message": content,
                "fid": fid,
                "tagid[]": tags
            }
            response = requests.post(
                f"{self.base_url}/thread-create.htm",
                headers=self.headers,
                data=form_data,
                timeout=15
            )
            self.last_post_time = time.time()
            return self._check_response(response)
        except Exception as e:
            logger.error(f"提交失败: {str(e)}")
            return False

    def _check_response(self, response):
        try:
            resp = response.json()
            success = resp.get("code") == 0 or "成功" in resp.get("message", "")
            if success:
                logger.info(f"发帖成功 | 响应: {resp.get('message')}")
            else:
                logger.error(f"发帖失败 | 错误: {resp.get('message')}")
            return success
        except:
            return False

def get_hdr_info(video_info: Dict) -> str:
    hdr_formats = ["hdr10", "hdr10+", "dolby vision", "hlg"]
    # Dolby Vision的特殊缩写形式
    dv_abbreviations = [
    # 基础缩写（含大小写变体）
    "dovi", "Dovi", "DOVI", 
    ".dv", ".DV", 
    " dv", " DV",
    "-dv", "-DV",
    "DoVi", "DoV", "dov", "DOV",
    
    # 全称变体（含大小写）
    "dolbyvision", "DolbyVision", "DOLBYVISION",
    
    # 与HDR/编码结合的标识
    "dv-hdr", "DV-HDR", 
    "dv-hevc", "DV-HEVC", 
    "dv-h.265", "DV-H.265"]
    
    # 首先，直接从原始文件名检查（如果available）
    # 尝试从video_info中获取原始文件名
    original_filename = ""
    # 检查是否有filename或title字段
    if "filename" in video_info:
        original_filename = video_info["filename"].lower()
    elif "title" in video_info and isinstance(video_info["title"], str):
        # 如果没有filename，尝试从title中提取
        original_filename = video_info["title"].lower()
    
    # 如果获取到了原始文件名，直接检查其中的DoVi和DV标识
    if original_filename:
        for abbr in dv_abbreviations:
            if abbr.lower() in original_filename:
                return "DOLBY VISION"
    
    # 检查video_profile字段
    profile = video_info.get("video_profile", "").lower()
    # 先检查常规HDR格式
    for hdr in hdr_formats:
        if hdr in profile:
            return hdr.upper()
    # 检查Dolby Vision缩写
    for abbr in dv_abbreviations:
        if abbr in profile:
            return "DOLBY VISION"
    
    # 检查hdr字段
    hdr_value = video_info.get("hdr", "")
    if isinstance(hdr_value, str):
        hdr_lower = hdr_value.lower()
        if hdr_lower in hdr_formats:
            return hdr_value.upper()
        for abbr in dv_abbreviations:
            if abbr in hdr_lower:
                return "DOLBY VISION"
    
    # 检查other字段
    other_value = video_info.get("other", "")
    if isinstance(other_value, str):
        other_lower = other_value.lower()
        for hdr in hdr_formats:
            if hdr in other_lower:
                return hdr.upper()
        for abbr in dv_abbreviations:
            if abbr in other_lower:
                return "DOLBY VISION"
    
    # 如果是列表形式的other字段
    elif isinstance(other_value, list):
        for item in other_value:
            if isinstance(item, str):
                item_lower = item.lower()
                # 检查常规HDR格式
                if any(hdr in item_lower for hdr in hdr_formats):
                    return [hdr.upper() for hdr in hdr_formats if hdr in item_lower][0]
                # 检查Dolby Vision缩写
                for abbr in dv_abbreviations:
                    if abbr in item_lower:
                        return "DOLBY VISION"
    
    return ""

def get_quality(file_name):
    video_info = guessit.guessit(file_name)
    
    # 把原始文件名也加入video_info，方便get_hdr_info函数直接从文件名检查
    video_info['filename'] = file_name
    
    # 提取质量相关参数
    quality_parts = []
    
    # 添加屏幕尺寸（如2160p、1080p等）
    if video_info.get('screen_size'):
        quality_parts.append(video_info['screen_size'])
    
    # 添加视频编码
    if video_info.get('video_codec'):
        quality_parts.append(video_info['video_codec'])
    
    # 添加帧率
    if video_info.get('frame_rate'):
        quality_parts.append(str(video_info['frame_rate']))
    
    # 添加流媒体服务
    if video_info.get('streaming_service'):
        quality_parts.append(video_info['streaming_service'])
    
    # 添加视频来源
    if video_info.get('source'):
        source = video_info['source']
        # 处理Ultra HD Blu-ray这种特殊情况
        if isinstance(source, str) and 'ultra hd' in source.lower():
            quality_parts.append('Ultra HD Blu-ray')
        else:
            quality_parts.append(source)
    
    # 添加音频编码和声道数
    audio_codec = video_info.get('audio_codec')
    audio_channels = video_info.get('audio_channels')
    if audio_codec and audio_channels:
        # 处理多个音频编码的情况
        if isinstance(audio_codec, list):
            quality_parts.append(f"{'+'.join(audio_codec)} {audio_channels}")
        else:
            quality_parts.append(f"{audio_codec} {audio_channels}")
    elif audio_codec:
        if isinstance(audio_codec, list):
            quality_parts.append('+'.join(audio_codec))
        else:
            quality_parts.append(audio_codec)
    elif audio_channels:
        quality_parts.append(f"Audio {audio_channels}")
    
    # 添加HDR信息（如果有）
    hdr_info = get_hdr_info(video_info)
    if hdr_info:
        quality_parts.append(hdr_info)
    
    # 添加其他质量相关标签
    other_value = video_info.get('other', '')
    quality_tags = []
    if isinstance(other_value, str):
        # 检查常见的质量标签
        quality_keywords = ['remux', 'high quality', 'hq']
        for keyword in quality_keywords:
            if keyword in other_value.lower():
                if keyword == 'high quality':
                    quality_tags.append('HQ')
                else:
                    quality_tags.append(keyword.upper())
    elif isinstance(other_value, list):
        # 检查列表中的每个元素
        for item in other_value:
            if isinstance(item, str):
                if 'remux' in item.lower():
                    quality_tags.append('REMUX')
                elif 'high quality' in item.lower() or 'hq' in item.lower():
                    quality_tags.append('HQ')
    
    if quality_tags:
        quality_parts.extend(quality_tags)
    
    # 如果没有提取到任何质量参数，返回"Unknown"
    if not quality_parts:
        return None
    
    return " · ".join(quality_parts)


# ========================= 核心函数 =========================
def post_to_forum(share_url: str, folder_name: str, file_name: str, media_type: str = "tv") -> Tuple[bool, str]:
    
    """
    将分享链接、文件夹名和文件名合并处理并发布到论坛
    参数:
        share_url: 分享链接
        folder_name: 包含标题、年份和TMDB ID的文件夹名（如"龙之谷：破晓奇兵 (2014) {tmdb-257932}"）
        file_name: 包含视频细节的文件名（如"龙之谷：破晓奇兵 (2014) - 1080p.H.264.DTS-HD MA 5.1.mkv"）
        media_type: 媒体类型，"tv"或"movie"
    返回:
        元组(发帖成功返回True，否则返回False, 帖子URL)
    """
    # 初始化组件
    tmdb = TMDBHelper()
    poster = ForumPoster()

    # 读取记录文件
    posted_ids = set()
    if os.path.exists(CONFIG["post_record"]):
        with open(CONFIG["post_record"], "r", encoding="utf-8") as f:
            posted_ids = {line.strip() for line in f if line.strip()}
    blocked_ids = set()
    if os.path.exists(CONFIG["blocked_record"]):
        with open(CONFIG["blocked_record"], "r", encoding="utf-8") as f:
            blocked_ids = {line.strip() for line in f if line.strip()}

    metadata = tmdb.get_metadata_optimize(folder_name, file_name)
    if not metadata:
        logger.error("元数据获取失败")
        return False, "元数据获取失败"
    metadata["share_url"] = share_url
    unique_id = metadata["tmdb_id"]
    # 检查是否已处理
    if unique_id in posted_ids:
        logger.info(f"已发布过该内容，跳过: {folder_name}")        
        # 即使跳过发帖，也需要生成标题并查询链接
        # 从folder_name获取元数据（标题、年份等核心信息）
        # 生成帖子标题
        def generate_title():
            title_parts = []
            region = get_region_name(metadata.get("countries", []))
            if region:
                title_parts.extend([
                    region,
                    "电视剧" if media_type == "tv"
                    else "动漫" if media_type == "anime"
                    else "电影"
                ])
            title_parts.append(metadata["title"])
            title_parts.append(f"({metadata['year']})")
            return " ".join(title_parts)

        def get_region_name(countries: List[str]) -> str:
            country_mapping = CONFIG["country_region_mapping"]
            for country in countries:
                region = country_mapping.get(country, country_mapping["default"])
                if region:
                    return region
            return country_mapping["default"]

        post_title = generate_title()

        # 提取用于查询的标题（只保留到年份）
        year_match = re.search(r'(.*?\(\d{4}\))', post_title)
        search_title = year_match.group(1) if year_match else post_title
        logger.info(f"查询标题: {search_title}")

        # 调用论坛搜索接口
        forum_url = ""
        forum_uid = os.getenv("ENV_FORUM_UID", "")
        if forum_uid:
            search_url = f"{os.getenv("ENV_123PANFX_BASE_URL", "https://pan1.me")}/?search.htm&keyword={requests.utils.quote(search_title)}"
            try:
                response = requests.get(search_url, timeout=15)
                soup = BeautifulSoup(response.text, 'html.parser')

                # 查找特定的ul元素
                thread_list = soup.find('ul', class_='list-unstyled threadlist mb-0')
                if thread_list:
                    # 查找特定UID的帖子
                    target_li = None
                    for li in thread_list.find_all('li', class_='media thread tap'):
                        # 检查UID
                        data_content = li.find('a', {'data-toggle': 'popover'})['data-content'] if li.find('a', {'data-toggle': 'popover'}) else ''
                        if f'UID:{forum_uid}' in data_content:
                            target_li = li
                            break

                    if target_li:
                        # 提取thread URL
                        thread_href = target_li.get('data-href', '')
                        if thread_href:
                            forum_url = f"{os.getenv("ENV_123PANFX_BASE_URL", "https://pan1.me")}/{thread_href}"
                            logger.info(f"找到帖子URL: {forum_url}")
                        else:
                            logger.warning("未找到帖子URL")
                    else:
                        logger.warning(f"未找到UID为{forum_uid}的帖子")
                else:
                    logger.warning("未找到帖子列表")
            except Exception as e:
                logger.error(f"查询论坛失败: {str(e)}")
        else:
            logger.warning("未设置论坛UID环境变量")
        return True, forum_url
    if unique_id in blocked_ids:
        logger.info(f"已标记为违规，跳过: {folder_name}")
        return False, f"已标记为违规，跳过: {folder_name}"
    '''
    # 从folder_name获取元数据（标题、年份等核心信息）
    metadata = tmdb.get_metadata(folder_name, media_type)
    if not metadata:
        logger.error("元数据获取失败")
        return False, "元数据获取失败"
    metadata["share_url"] = share_url
    '''
    # 从合并后的名称解析视频信息（分辨率、编码等）
    video_info = guessit.guessit(file_name)
    # 设置默认值确保稳定性
    video_info.setdefault("screen_size", "")
    video_info.setdefault("source", "")
    video_info.setdefault("video_profile", "")
    video_info.setdefault("video_codec", "")
    video_info.setdefault("audio_codec", "")
    video_info.setdefault("audio_profile", "")
    video_info.setdefault("audio_channels", "")

    # 生成帖子标题
    def generate_title():
        title_parts = []
        region = get_region_name(metadata.get("countries", []))
        if region:
            title_parts.extend([
                region,
                "电视剧" if media_type == "tv"
                else "动漫" if media_type == "anime"
                else "电影"
            ])
        title_parts.append(metadata["title"])
        title_parts.append(f"({metadata['year']})")

        # 从video_info提取分辨率
        resolution = video_info.get("screen_size", "").lower()
        if "1080" in resolution:
            title_parts.append("1080P")
        elif "720" in resolution:
            title_parts.append("720P")
        elif "480" in resolution:
            title_parts.append("480P")
        elif "2160" in resolution or "4k" in resolution:
            title_parts.append("4K")
        elif "2k" in resolution:
            title_parts.append("2K")

        # 提取来源
        source = video_info.get("source", "").lower()
        if "blu" in source or "bd" in source:
            title_parts.append("BluRay")
        elif "remux" in source:
            title_parts.append("REMUX")
        elif "web" in source:
            title_parts.append("WEB-DL")
        elif "hdtv" in source:
            title_parts.append("HDTV")

        # 提取HDR信息
        hdr = get_hdr_info(video_info)
        if hdr:
            title_parts.append(hdr)

        # 提取音频信息
        audio_parts = []
        audio_codec = video_info.get("audio_codec", "")
        audio_profile = video_info.get("audio_profile", "")
        audio_channels = video_info.get("audio_channels", "")
        if audio_codec:
            audio_codec_map = {
                "aac": "AAC", "ac3": "AC3", "dts": "DTS", "dolby digital": "DD", "dolby digital plus": "DDP",
                "dolby truehd": "TrueHD", "dolby atmos": "Atmos", "dolby ac3": "AC3", "dolby eac3": "E-AC3",
                "flac": "FLAC", "mp3": "MP3", "ogg": "OGG", "lpcm": "LPCM", "pcm": "PCM", "thd": "TrueHD"
            }
            if isinstance(audio_codec, list):
                primary_codec = audio_codec[0]
                matched_codec = audio_codec_map.get(primary_codec.lower(), primary_codec.upper())
            else:
                matched_codec = audio_codec_map.get(audio_codec.lower(), audio_codec.upper())
            audio_parts.append(matched_codec)
        if audio_profile:
            audio_parts.append(audio_profile.upper())
        if audio_channels:
            audio_parts.append(str(audio_channels))
        if audio_parts:
            title_parts.append(".".join(audio_parts))

        return " ".join(title_parts)

    def get_region_name(countries: List[str]) -> str:
        country_mapping = CONFIG["country_region_mapping"]
        for country in countries:
            region = country_mapping.get(country, country_mapping["default"])
            if region:
                return region
        return country_mapping["default"]

    post_title = generate_title()

    # 执行发帖
    success = poster.post(post_title, metadata, media_type, video_info)

    # 记录结果
    forum_url = ""
    if success and not CONFIG["test_mode"]:
        with open(CONFIG["post_record"], "a", encoding="utf-8") as f:
            f.write(f"{unique_id}\n")
        logger.info(f"已记录成功发布: {folder_name}")

        # 提取用于查询的标题（只保留到年份）
        # 使用re.search代替re.match以支持年份在标题中的任何位置
        year_match = re.search(r'(.*?\(\d{4}\))', post_title)
        search_title = year_match.group(1) if year_match else post_title
        logger.info(f"查询标题: {search_title}")

        # 调用论坛搜索接口
        forum_uid = os.getenv("ENV_FORUM_UID", "")
        if forum_uid:
            search_url = f"{os.getenv("ENV_123PANFX_BASE_URL", "https://pan1.me")}/?search.htm&keyword={requests.utils.quote(search_title)}"
            try:
                response = requests.get(search_url, timeout=15)
                soup = BeautifulSoup(response.text, 'html.parser')

                # 查找特定的ul元素
                thread_list = soup.find('ul', class_='list-unstyled threadlist mb-0')
                if thread_list:
                    # 查找特定UID的帖子
                    target_li = None
                    for li in thread_list.find_all('li', class_='media thread tap'):
                        # 检查UID
                        data_content = li.find('a', {'data-toggle': 'popover'})['data-content'] if li.find('a', {'data-toggle': 'popover'}) else ''
                        if f'UID:{forum_uid}' in data_content:
                            target_li = li
                            break

                    if target_li:
                        # 提取thread URL
                        thread_href = target_li.get('data-href', '')
                        if thread_href:
                            forum_url = f"{os.getenv("ENV_123PANFX_BASE_URL", "https://pan1.me")}/{thread_href}"
                            logger.info(f"找到帖子URL: {forum_url}")
                        else:
                            logger.warning("未找到帖子URL")
                    else:
                        logger.warning(f"未找到UID为{forum_uid}的帖子")
                else:
                    logger.warning("未找到帖子列表")
            except Exception as e:
                logger.error(f"查询论坛失败: {str(e)}")
        else:
            logger.warning("未设置论坛UID环境变量")

    return success, forum_url


# ========================= 示例调用 =========================
if __name__ == "__main__":
    #print(guessit.guessit("Doraemon.Nobitas.Art.World.Tales.2025.V2.1080p.BluRay.Remux.AVC.TrueHD.7.1.Atmos-Nest@ADE.mkv"))
    #print(get_quality("Doraemon.Nobitas.Art.World.Tales.2025.V2.1080p.BluRay.Remux.AVC.TrueHD.7.1.Atmos-Nest@ADE.mkv"))
    tmdb = TMDBHelper()
    print(tmdb.get_metadata_optimize("哪吒之魔童闹海 (2025) 4K HQ DV 60fps DDP5.1.Atmos DTS5.1 内嵌简中字幕 ⭐豆瓣 8.5 HiveWeb (33.47GB)","Ne.Zha.2.2025.2160p.WEB-DL.HQ.DV.H265.60FPS.DTS5.1-HiveWeb.mkv"))
    #print(tmdb.get_metadata_optimize("异种族风俗娘评鉴指南-Interspecies Reviewers (2020) 1080p {tmdbid-96444}","异种族风俗娘评鉴指南.Interspecies Reviewers.2020.S01E04.低级淫魔就算说射不出来了仍不断榨精，根本就是拷问之城。火龙小姐的身心虽然都热情如火，但热过头了都快往生了.1080p.AVC.FLAC.2.0.{tmdbid-96444}"))
    #print(guessit.guessit("大理寺少卿游.White.Cat.Legend.S01E02.2024.2160p.WEB-DL.H265.EDR.DDP5.1.Atmos-HHWEB"))
    #print(guessit.guessit("坏蛋联盟2 (2025) - 2160p.WEB-DL.DoVi.H.265.DDP.5.1.mkv"))
    #print(tmdb.get_metadata_optimize("黑寡妇","黑寡妇 4K原盘REMUX [HDR] [国英双语] [内封简英双字]"))

    #print(tmdb.get_metadata_optimize("绝命毒师.2008","绝命毒师.2008.S05E16"))
    #print(get_quality("坏蛋联盟2 (2025) - 2160p.WEB-DL.DoVi.H.265.DDP.5.1.mkv"))
    '''
    result = post_to_forum(
        share_url="https://www.123pan.com/s/CqeVTd-qaAj3",
        folder_name="仙逆 (2023) {tmdb-223911}",
        file_name="仙逆.2023.S01E12.第12集.2160p.WEB-DL.H.265.mkv",
        media_type="anime"
    )
    '''
    #print(f"post_to_forum函数返回内容: {result}")