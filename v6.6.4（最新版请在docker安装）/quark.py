import asyncio
import json
import os
import random
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple
import base64
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import logging
#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from yarl import URL

import aiohttp


class QuarkUcSDK:
    """夸克网盘 SDK"""

    BASE_URL = "https://pc-api.uc.cn"
    QuarkBaseURL = 'https://drive-h.quark.cn'
    QUARK_BASE_URL = 'https://pc-api.uc.cn'
    # is_debug = True
    is_debug = True
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0"

    def __init__(self, cookie: str = '', pr='ucpro', fr='pc',timeout: int = 15):
        self.pr = pr
        self.cookie = cookie.strip()
        self.fr = fr
        self._timeout = timeout
        self._session: aiohttp.ClientSession = None

    async def __aenter__(self):
        if not self._session or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session and not self._session.closed:
            await self._session.close()

    async def share_file_list(self, code: str, passcode, token: str, dir_id=0, page=1, fetch_share=0,
                              sort="file_type:asc,updated_at:desc", page_size=1000, **kwargs):
        # if self.pr in ['ucpro']:
        #     url = f"{self.QuarkBaseURL}/1/clouddrive/share/sharepage/detail"
        # else:
        url = f"{self.BASE_URL}/1/clouddrive/share/sharepage/detail"
        params = {
            "pwd_id": code,
            "passcode": passcode,
            "stoken": token,
            "pdir_fid": dir_id,
            "force": "0",
            "_page": page,
            "_size": page_size,
            "_fetch_banner": "0",
            "_fetch_share": fetch_share,
            "_fetch_total": "1",
            "_sort": sort,
            "__dt": int(random.uniform(1, 5) * 60 * 1000),
            "__t": int(datetime.now().timestamp())
        }
        return await self._send_request("GET", url, params=params, **kwargs)

    async def _send_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """发送 HTTP 请求"""
        if not self._session or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

        headers = {
            "cookie": self.cookie,
            "content-type": "application/json",
            "user-agent": self.USER_AGENT,
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "priority": "u=1, i",
            "sec-ch-ua": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }

        if "headers" in kwargs:
            headers.update(kwargs["headers"])
            del kwargs["headers"]

        if 'params' not in kwargs:
            kwargs['params'] = {}
        if 'pr' not in kwargs['params']:
            kwargs['params']['pr'] = self.pr
            # kwargs['params']['pr'] = 'UCBrowser'
        if 'fr' not in kwargs['params']:
            kwargs['params']['fr'] = self.fr

        for i in list(kwargs.get('params', {}).keys()):
            if isinstance(kwargs['params'][i], bool):
                kwargs['params'][i] = str(kwargs['params'][i]).lower()
            elif isinstance(kwargs['params'][i], int):
                kwargs['params'][i] = str(kwargs['params'][i])
            elif kwargs['params'][i] is None:
                kwargs['params'].pop(i, None)

        if self.is_debug is True:
            logger.debug(f"send {method} request, url: {url}, headers: {headers}, kwargs: {kwargs}")

        # response = await http_client.request(
        #     method=method,
        #     url=url,
        #     headers=headers,
        #     **kwargs
        # )
        async with self._session.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            ) as response:
            if self.is_debug is True:
                logger.debug(f"send {method} request, url: {url}, headers: {headers}, kwargs: {kwargs}, resp: {response}")
            # if isinstance(response, str):
            #     return json.loads(response)
            return await response.json()

    async def get_share_info(self, share_id: str, password: str | None = "") -> Dict[str, Any]:
        """
        获取分享信息
        :param share_id: 分享 ID
        :param password: 分享密码
        """
        # if self.pr in ['ucpro']:
        #     url = f"{self.QuarkBaseURL}/1/clouddrive/share/sharepage/token"
        # else:
        url = f"{self.BASE_URL}/1/clouddrive/share/sharepage/token"
        data = {"pwd_id": share_id, "passcode": password}
        return await self._send_request("POST", url, json=data)

    async def get_share_file_list(self, code: str, passcode, stoken: str, dir_id=0, page=1, fetch_share=0,
                                  sort="file_type:asc,updated_at:desc", page_size=1000, is_get_folder=False,
                                  is_recursion=True, parent_name='', is_get_all_page=True, **kwargs):
        """
        获取分享文件列表
        :param is_get_all_page:
        :param is_get_folder:
        :param parent_name:
        :param is_recursion:
        :param page_size:
        :param sort:
        :param page:
        :param code: 分享 ID
        :param passcode: 分享秘钥
        :param stoken: 分享 token
        :param dir_id: 文件夹 ID
        :param fetch_share: 是否获取分享信息，默认为0
        :return: 分享文件列表信息
        """
        resp = await self.share_file_list(code, passcode, stoken, dir_id, page, fetch_share, sort, page_size, **kwargs)
        if resp['code'] == 0:
            for i in resp["data"]["list"]:
                if is_recursion is True and i['dir'] is True:
                    async for j in self.get_share_file_list(code, passcode, stoken, i['fid'], 1, fetch_share, sort,
                                                            page_size, is_get_folder, is_recursion,
                                                            parent_name + "/" + i['file_name'], is_get_all_page,
                                                            **kwargs):
                        yield j
                if is_get_folder is False and i['dir'] is True:
                    continue
                yield dict(i, RootPath=parent_name + '/' + i['file_name'])
            current_page = resp.get("metadata", {}).get("_page", 1)
            current_count = resp.get("metadata", {}).get("_size", 1)
            total = resp.get("metadata", {}).get("_total", 0)
            if is_get_all_page and total > current_page * current_count:
                async for i in self.get_share_file_list(code, passcode, stoken, dir_id, page+1, fetch_share, sort,
                                                        page_size, is_get_folder, is_recursion, parent_name,
                                                        is_get_all_page, **kwargs):
                    yield i

    async def save_share_files(self, share_id: str, pwd: str, token: str, file_ids: List[str],
                               file_tokens: List[str], target_dir_id: str = "0", pdir_fid: str = "0") -> Dict[str, Any]:
        """
        保存分享文件
        :param share_id: 分享 ID
        :param token: 分享 token
        :param file_ids: 文件 ID 列表
        :param file_tokens: 文件 token 列表
        :param target_dir_id: 目标文件夹 ID
        """
        url = f"{self.BASE_URL}/1/clouddrive/share/sharepage/save"
        params = {
            "__dt": int(random.uniform(1, 5) * 60 * 1000),
            "__t": int(datetime.now().timestamp())
        }
        data = {
            "fid_list": file_ids,
            "fid_token_list": file_tokens,
            "to_pdir_fid": target_dir_id,
            "pdir_save_all": False,
            "pdir_fid": pdir_fid,
            "pwd_id": share_id,
            "passcode": pwd,
            "stoken": token,
            "scene": "link"
        }
        return await self._send_request("POST", url, params=params, json=data)

    async def _create_download_request(self, code, pwd, stoken, fids, fids_tokens):
        """
        创建下载请求的内部方法，支持单个或多个文件
        
        参数:
            code: 分享ID
            pwd: 分享密码
            stoken: 分享token
            fids: 文件ID列表
            fids_tokens: 文件token列表
        
        返回:
            dict或list: 单个文件时返回dict，多个文件时返回list
        """
        data = {
            "fids": fids,
            "pwd_id": code,
            "stoken": stoken,
            "fids_token": fids_tokens
        }
        if pwd is not None:
            data['passcode'] = pwd
        params = {'entry': 'ft', 'uc_param_str': ""}
        url = f"{self.BASE_URL}/1/clouddrive/file/download"
        headers = {}
        if self.pr in ['ucpro']:
            headers['user-agent'] = 'quark-cloud-drive'
            headers['referer'] = 'https://drive.quark.cn/'
        else:
            headers['referer'] = 'https://fast.uc.cn/'
        
        return await self._send_request("POST", url, json=data, params=params, headers=headers)

    async def send_create_share_download_request(self, code, pwd, stoken, fid, fids_token):
        """
        获取单个分享文件的下载信息
        
        参数:
            code: 分享ID
            pwd: 分享密码
            stoken: 分享token
            fid: 文件ID
            fids_token: 文件token
        
        返回:
            dict: 文件信息
        """
        resp = await self._create_download_request(code, pwd, stoken, [fid], [fids_token])
        if 'data' not in resp:
            logger.error(resp)
            # 返回一个默认的错误信息，避免程序崩溃
            return {'md5': ''}

        info = resp['data'][0]
        return info
    
    async def batch_send_create_share_download_request(self, code, pwd, stoken, file_info_list: List[Tuple[str, str]], batch_size: int = 10):
        """
        批量获取分享文件的下载信息
        
        参数:
            code: 分享ID
            pwd: 分享密码
            stoken: 分享token
            file_info_list: 文件信息列表，每个元素是(fid, fids_token)的元组
            batch_size: 每批处理的文件数量
        
        返回:
            dict: 以fid为key，文件信息为value的字典
        """
        results = {}
        total_files = len(file_info_list)
        request_count = 1  # 初始化请求计数器
        
        # 分批处理文件
        for i in range(0, total_files, batch_size):
            batch_end = min(i + batch_size, total_files)
            current_batch = file_info_list[i:batch_end]
            
            if self.is_debug:
                logger.debug(f"--- 处理批次 {i//batch_size + 1}: 处理文件 {i+1}-{batch_end}/{total_files} ---")
            
            # 构建批量请求的数据
            fids = []
            fids_tokens = []
            fid_map = []  # 用于跟踪响应和fid的对应关系
            
            for fid, fids_token in current_batch:
                fids.append(fid)
                fids_tokens.append(fids_token)
                fid_map.append(fid)
            
            # 记录当前请求信息
            if self.is_debug:
                logger.debug(f"--- 第 {request_count} 次请求，包含 {len(fids)} 个文件，fid列表: {fids} --- ")
            request_count += 1
            
            # 复用_create_download_request方法发送批量请求
            try:
                resp = await self._create_download_request(code, pwd, stoken, fids, fids_tokens)

                # 处理批量响应
                if 'data' in resp and isinstance(resp['data'], list):
                    # 确保响应数量与请求数量匹配
                    for idx, info in enumerate(resp['data']):
                        if idx < len(fid_map):
                            fid = fid_map[idx]
                            results[fid] = info
                else:
                    if self.is_debug:
                        logger.error(f"批量请求返回格式异常: {resp}")
                    # 为当前批次的所有文件设置默认值
                    for fid in fid_map:
                        results[fid] = {'md5': ''}
            except Exception as e:
                if self.is_debug:
                    logger.error(f"批量请求失败: {str(e)}")
                # 为当前批次的所有文件设置默认值
                for fid in fid_map:
                    results[fid] = {'md5': ''}
        
        return results

    async def create_share_download_url(self, code, pwd, stoken, fid, fids_token):
        info = await self.send_create_share_download_request(code, pwd, stoken, fid, fids_token)
        download_url = info['download_url']
        if URL(download_url).query.get('Expires') is None:
            logger.debug(self.cookie)
            logger.debug(download_url)
        expired = int(URL(download_url).query.get('Expires', str(int(time.time())+1400))[:10]) - int(time.time()) - 1000
        return download_url, expired

    # def get_proxy_url(self, url):
    #     encrypted_data = self.encrypt_data(self.cookie, b'ThisIsASecretKey1234567890123456')
    #     return ApiSettings.ProxyUrl + "/" + url + f"&encrypted_data={encrypted_data}"

    def encrypt_data(self, plaintext, key):
        """使用 AES-256-CBC 和 PKCS7 填充加密数据，并返回 URL 安全的 Base64 编码字符串。"""
        # 1. 生成 16 字节的随机初始化向量 (IV)
        iv = os.urandom(16)

        # 2. 对明文进行 PKCS7 填充
        padder = padding.PKCS7(128).padder()  # 128 bits = 16 bytes block size for AES
        data_bytes = plaintext.encode('utf-8')
        padded_data = padder.update(data_bytes) + padder.finalize()

        # 3. 使用 AES-256-CBC 加密
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # 4. 将 IV 和密文连接
        combined_data = iv + ciphertext

        # 5. 使用 URL 安全的 Base64 编码，以便安全地通过 URL 传输
        encoded_data = base64.urlsafe_b64encode(combined_data).decode('utf-8')
        return encoded_data


class QuarkSdk(QuarkUcSDK):

    def __init__(self, cookie: str = ""):
        super().__init__(cookie, 'ucpro', 'pc')


class UcSdk(QuarkUcSDK):

    def __init__(self, cookie: str = ""):
        super().__init__(cookie, 'UCBrowser', 'pc')


