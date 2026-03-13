import json
import time

import requests
from urllib import parse
from concurrent.futures import ThreadPoolExecutor
import threading
from Crypto.Cipher import PKCS1_v1_5 as Cipher_pksc1_v1_5
from Crypto.PublicKey import RSA
import logging
import argparse
from tqdm import tqdm

import requests
import os
from bs4 import BeautifulSoup
import time
import sqlite3
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlsplit, parse_qs
import re
import schedule
import time
from dotenv import load_dotenv
import os

logger = logging.getLogger(__name__)

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
CHANNEL_URL = os.getenv("ENV_189_TG_CHANNEL", "")
ENV_189_TG_CHANNEL = os.getenv("ENV_189_TG_CHANNEL","")
ENV_189_CLIENT_ID = os.getenv("ENV_189_CLIENT_ID","")
ENV_189_CLIENT_SECRET = os.getenv("ENV_189_CLIENT_SECRET","")
ENV_189_UPLOAD_PID = os.getenv("ENV_189_UPLOAD_PID","")

TG_BOT_TOKEN = os.getenv("ENV_TG_BOT_TOKEN", "")
TG_ADMIN_USER_ID = get_int_env("ENV_TG_ADMIN_USER_ID", 0)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 修改数据库文件路径到 db 目录下
DB_DIR = "db"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)
DATABASE_FILE = os.path.join(DB_DIR, "TG_monitor-189.db")
CHECK_INTERVAL = get_int_env("ENV_CHECK_INTERVAL", 5)  # 检查间隔（分钟）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
]
RETRY_TIMES = 3
TIMEOUT = 15

def rsaEncrpt(password, public_key):
    rsakey = RSA.importKey(public_key)
    cipher = Cipher_pksc1_v1_5.new(rsakey)
    return cipher.encrypt(password.encode()).hex()


def format_size(size):
    units = ['B', 'KB', 'MB', 'GB', 'TB']

    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    return f"{size:.2f} {units[unit_index]}"


config = {
    "clientId": '538135150693412',
    "model": 'KB2000',
    "version": '9.0.6',
    "pubKey": 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCZLyV4gHNDUGJMZoOcYauxmNEsKrc0TlLeBEVVIIQNzG4WqjimceOj5R9ETwDeeSN3yejAKLGHgx83lyy2wBjvnbfm/nLObyWwQD/09CmpZdxoFYCH6rdDjRpwZOZ2nXSZpgkZXoOBkfNXNxnN74aXtho2dqBynTw3NFTWyQl8BQIDAQAB',
}

def clean_filename(name):
    # 定义非法字符
    illegal_chars = '"\\/:*?|><'
    # 移除非法字符
    for char in illegal_chars:
        name = name.replace(char, '')
    # 限制长度为255个字符
    return name[:255]
class BatchSaveTask:
    def __init__(self, shareInfo, batchSize, targetFolderId, shareFolderId=None, maxWorkers=3):
        self.shareInfo = shareInfo
        self.batchSize = batchSize
        self.shareFolderId = shareFolderId
        self.targetFolderId = targetFolderId
        self.tqLock = threading.Lock()
        self.taskNum = 0
        self.walkDirNum = 0
        self.saveDirNum = 0
        self.savedFileNum = 0
        self.savedFileSize = 0
        self.failed = False
        self.threadPool = ThreadPoolExecutor(max_workers=maxWorkers)
        self.tq = tqdm(desc='正在保存')

    def __updateTq(self, num=1):
        data = {
            "剩余任务数": self.taskNum,
            "已保存文件数": self.savedFileNum,
            "已保存目录数:": self.saveDirNum,
            "已遍历目录数:": self.walkDirNum
            ##"已保存文件总大小": format_size(self.savedFileSize)
        }
        if num:
            self.tq.set_postfix(data, refresh=False)
            self.tq.update(num)
        else:
            self.tq.set_postfix(data)

    def __incTaskNum(self, num):
        self.tqLock.acquire()
        self.taskNum += num
        self.__updateTq(0)
        self.tqLock.release()

    def getTaskNum(self):
        self.tqLock.acquire()
        num = self.taskNum
        self.tqLock.release()
        return num

    def __incWalkDirNum(self, num=1):
        self.tqLock.acquire()
        self.walkDirNum += num
        self.__updateTq(num)
        self.tqLock.release()

    def __incSaveDirNum(self, num=1):
        self.tqLock.acquire()
        self.saveDirNum += num
        self.__updateTq(num)
        self.tqLock.release()

    def __incSavedFileInfo(self, fileInfos):
        fileNum = len(fileInfos)
        totalSize = 0
        for i in fileInfos:
            totalSize += i.get("size")
        self.tqLock.acquire()
        self.savedFileNum += fileNum
        self.savedFileSize += totalSize
        self.__updateTq(fileNum)
        self.tqLock.release()

    def run(self, checkInterval=1):
        with self.tq:
            self.__incTaskNum(1)
            self.threadPool.submit(self.__batchSave, self.targetFolderId, self.shareFolderId)
            while self.getTaskNum() > 0:
                time.sleep(checkInterval)
            self.threadPool.shutdown()
        return self.failed

    def __testAndSaveDir(self, folderInfo, targetFolderId):
        try:
            folderName = folderInfo["name"]
            shareFolderId = folderInfo["id"]
            # 清理文件夹名称中的非法字符
            clean_folder_name = clean_filename(folderName)
            code = self.shareInfo.saveShareFiles([{
                "fileId": shareFolderId,
                "fileName": clean_folder_name,
                "isFolder": 1}],
                targetFolderId)
            if code:
                if code == "ShareDumpFileOverload":
                    try:
                        nextFolderId = self.shareInfo.client.createFolder(parentFolderId=targetFolderId,
                                                                          name=folderName)
                        if nextFolderId:
                            self.__incTaskNum(1)
                            self.threadPool.submit(self.__batchSave, nextFolderId, shareFolderId)
                            return
                        else:
                            log.error(f"failed to create folder[{folderInfo}] at [{targetFolderId}]")
                            self.failed = True
                    except Exception as e1:
                        log.error(f"failed to create folder[{folderInfo}] at [{targetFolderId}]: {e1}")
                        self.failed = True
                else:
                    log.error(f"save dir response unknown code: {code}")
                    self.failed = True
            else:
                self.__incSaveDirNum()
        except Exception as e2:
            log.error(f"TestAndSaveDir occurred exception: {e2}")
            self.failed = True
        finally:
            self.__incTaskNum(-1)

    def __mustSave(self, saveFiles, targetFolderId):
        try:
            taskInfos = []
            for fileInfo in saveFiles:
                taskInfos.append(
                    {
                            "fileId": fileInfo.get("id"),
                            "fileName": clean_filename(fileInfo.get("name")),
                            "isFolder": 0
                        }
                )
            code = self.shareInfo.saveShareFiles(taskInfos, targetFolderId)
            if code:
                log.error(f"save only files response unexpected code [num={len(saveFiles)}][code: {code}]")
                self.failed = True
            else:
                self.__incSavedFileInfo(saveFiles)
                return
        except Exception as e1:
            log.error(f"mustSave occurred exception: {e1}")
            self.failed = True
        finally:
            self.__incTaskNum(-1)

    def __splitFileListAndSave(self, fileList: list, targetFolderId):
        for i in range(0, len(fileList), self.batchSize):
            if self.failed:
                return
            self.__incTaskNum(1)
            self.threadPool.submit(self.__mustSave, fileList[i: i + self.batchSize], targetFolderId)

    def __batchSave(self, targetFolderId, shareFolderId: None):
        try:
            rootFiles = self.shareInfo.getAllShareFiles(shareFolderId)
            self.__incWalkDirNum()
            
            # 确保rootFiles包含files和folders键
            files = rootFiles.get("files", [])
            folders = rootFiles.get("folders", [])
            
            self.__splitFileListAndSave(files, targetFolderId)

            for folderInfo in folders:
                if self.failed:
                    return
                self.__incTaskNum(1)
                self.threadPool.submit(self.__testAndSaveDir, folderInfo, targetFolderId)
            return
        except Exception as e1:
            log.error(f"batchSave occurred exception: {e1}")
        finally:
            self.__incTaskNum(-1)
        self.failed = True


class Cloud189ShareInfo:
    def __init__(self, shareDirFileId, shareId, shareMode, cloud189Client):
        self.shareDirFileId = shareDirFileId
        self.shareId = shareId
        self.session = cloud189Client.session
        self.client = cloud189Client
        self.shareMode = shareMode

    def getAllShareFiles(self, folder_id=None):
        if folder_id is None:
            folder_id = self.shareDirFileId
        fileList = []
        folders = []
        pageNumber = 1
        while True:
            result = self.session.get("https://cloud.189.cn/api/open/share/listShareDir.action", params={
                "pageNum": pageNumber,
                "pageSize": "10000",
                "fileId": folder_id,
                "shareDirFileId": self.shareDirFileId,
                "isFolder": "true",
                "shareId": self.shareId,
                "shareMode": self.shareMode,
                "iconOption": "5",
                "orderBy": "lastOpTime",
                "descending": "true",
                "accessCode": "",
            }).json()
            #print(result)
            if result['res_code'] != 0:
                raise Exception(result['res_message'])
            
            # 确保fileListAO存在且是字典
            if not isinstance(result.get("fileListAO"), dict):
                log.error(f"Invalid fileListAO format: {result}")
                break
            
            fileListAO = result["fileListAO"]
            
            # 确保fileList和folderList存在
            current_files = fileListAO.get("fileList", [])
            current_folders = fileListAO.get("folderList", [])
            
            # 只有当文件列表和文件夹列表都为空时才退出循环
            if fileListAO.get("fileListSize", 0) == 0 and len(current_folders) == 0:
                break
            
            fileList += current_files
            folders += current_folders
            #print(fileList)
            #print(folders)
            pageNumber += 1
        return {"files": fileList, "folders": folders}

    def saveShareFiles(self, tasksInfos, targetFolderId):
        """
        保存文件到指定路径
        :param tasksInfos: ["fileId":"32313191387622589","fileName":"高血脂食疗药膳.epub","isFolder":0]
        :param targetFolderId: 保存到当前账户的指定目录：12474193948415710
        :return: "ShareDumpFileOverload"、None
        """
        try:
            # 统一参数格式为str，与cloud189.py保持一致
            response = self.session.post("https://cloud.189.cn/api/open/batch/createBatchTask.action", data={
                "type": "SHARE_SAVE",
                "taskInfos": str(tasksInfos),
                "targetFolderId": targetFolderId,
                "shareId": self.shareId,
            })
            # 检查响应状态码
            if response.status_code != 200:
                log.error(f"保存文件请求失败，状态码: {response.status_code}")
                return f"HTTP_ERROR_{response.status_code}"
            
            # 检查响应内容是否为空
            if not response.content.strip():
                log.error("保存文件请求返回空响应")
                return "EMPTY_RESPONSE"
            
            # 尝试解析JSON
            result = response.json()
            if result["res_code"] != 0:
                log.error(f"保存文件失败: {result.get('res_message', '未知错误')}")
                return result.get('res_message', 'UNKNOWN_ERROR')
            
            return None
        except json.JSONDecodeError as e:
            log.error(f"JSON解析错误: {e}")
            return f"JSON_ERROR: {str(e)}"
        except Exception as e:
            log.error(f"保存文件时发生异常: {e}")
            return f"EXCEPTION: {str(e)}"
        taskId = result["taskId"]
        while True:
            result = self.session.post("https://cloud.189.cn/api/open/batch/checkBatchTask.action", data={
                "taskId": taskId,
                "type": "SHARE_SAVE"
            }).json()
            taskStatus = result["taskStatus"]
            errorCode = result.get("errorCode")
            if taskStatus != 3 or errorCode:
                break
            time.sleep(1)
        return errorCode

    def createBatchSaveTask(self, targetFolderId, batchSize, shareFolderId=None, maxWorkers=3):
        return BatchSaveTask(shareInfo=self, batchSize=batchSize, targetFolderId=targetFolderId,
                             shareFolderId=shareFolderId, maxWorkers=3)


class Cloud189:
    def __init__(self):
        self.session = requests.session()
        self.session.headers = {
            'User-Agent': f"Mozilla/5.0 (Linux; U; Android 11; {config['model']} Build/RP1A.201005.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/74.0.3729.136 Mobile Safari/537.36 Ecloud/{config['version']} Android/30 clientId/{config['clientId']} clientModel/{config['model']} clientChannelId/qq proVersion/1.0.6",
            "Accept": "application/json;charset=UTF-8",
        }

    def getObjectFolderNodes(self, folderId=-11):
        """
        获取目录列表
        :param folderId: 目录ID
        :return: [{"isParent": "true", "name": "ePUBee图书", "pId": "-11", "id": "12474193948415710"}]
        """
        return self.session.post("https://cloud.189.cn/api/portal/getObjectFolderNodes.action", data={
            "id": folderId,
            "orderBy": 1,
            "order": "ASC"
        }).json()

    def empty_recycle_bin(self):
        """
        清空回收站
        :return: 是否成功
        """
        try:
            response = self.session.post("https://cloud.189.cn/api/open/batch/createBatchTask.action", data={
                "type": "EMPTY_RECYCLE",
                "taskInfos": "[]",
                "targetFolderId": "",
            })
            
            # 检查响应状态码
            if response.status_code != 200:
                log.error(f"清空回收站请求失败，状态码: {response.json}")
                return False
            
            # 检查响应内容是否为空
            if not response.content.strip():
                log.error("清空回收站请求返回空响应")
                return False
            
            # 尝试解析JSON
            result = response.json()
            if result.get("res_code") != 0:
                log.error(f"清空回收站失败: {result.get('res_message', '未知错误')}")
                return False
            
            log.info("清空回收站成功")
            return True
        except json.JSONDecodeError as e:
            log.error(f"JSON解析错误: {e}")
            return False
        except Exception as e:
            log.error(f"清空回收站时发生异常: {e}")
            return False
            
    def list_files(self, folder_id: str = "-11") -> dict:
        """
        获取文件列表
        :param folder_id: 文件夹ID，默认为根目录(-11)
        :return: 文件列表数据
        """
        try:
            response = self.session.get(
                "https://cloud.189.cn/api/open/file/listFiles.action",
                params={
                    "folderId": folder_id,
                    "mediaType": 0,
                    "orderBy": "lastOpTime",
                    "descending": True,
                    "pageNum": 1,
                    "pageSize": 1000
                }
            )
            
            if response.status_code != 200:
                log.error(f"获取文件列表请求失败，状态码: {response.status_code}")
                return {}
            
            result = response.json()
            if result.get("res_code") != 0:
                log.error(f"获取文件列表失败: {result.get('res_message', '未知错误')}")
                return {}
            
            return result
        except json.JSONDecodeError as e:
            log.error(f"JSON解析错误: {e}")
            return {}
        except Exception as e:
            log.error(f"获取文件列表时发生异常: {e}")
            return {}
            
    def delete_files(self, file_ids: list) -> dict:
        """
        删除文件或文件夹
        :param file_ids: 要删除的文件信息列表，格式为：[{"fileId": "xxx", "fileName": "xxx", "isFolder": 1}]
        :return: 删除结果
        """
        try:
            # 创建删除任务
            task_params = {
                "type": "DELETE",
                "taskInfos": str(file_ids),
                "targetFolderId": "",
            }
            
            response = self.session.post(
                "https://cloud.189.cn/api/open/batch/createBatchTask.action",
                data=task_params
            )
            
            if response.status_code != 200:
                log.error(f"创建删除任务请求失败，状态码: {response.status_code}")
                return {
                    "success": False,
                    "message": f"创建删除任务请求失败，状态码: {response.status_code}"
                }
            
            result = response.json()
            if result.get("res_code") != 0:
                log.error(f"创建删除任务失败: {result.get('res_message', '未知错误')}")
                return {
                    "success": False,
                    "message": f"创建删除任务失败: {result.get('res_message', '未知错误')}"
                }
            
            task_id = result.get("taskId")
            if not task_id:
                log.error("创建删除任务成功，但未返回taskId")
                return {
                    "success": False,
                    "message": "创建删除任务成功，但未返回taskId"
                }
            
            # 检查任务状态
            start_time = time.time()
            max_timeout = 30  # 最大超时时间(秒)
            
            while True:
                # 检查是否超时
                if time.time() - start_time > max_timeout:
                    log.error(f"任务 {task_id} 执行超时")
                    return {
                        "success": False,
                        "message": "文件删除失败：任务执行超时",
                        "task_id": task_id
                    }
                
                # 检查任务状态
                status_response = self.session.post(
                    "https://cloud.189.cn/api/open/batch/checkBatchTask.action",
                    data={
                        "taskId": task_id,
                        "type": "DELETE"
                    }
                )
                
                if status_response.status_code != 200:
                    log.error(f"检查任务状态请求失败，状态码: {status_response.status_code}")
                    time.sleep(1)
                    continue
                
                status_result = status_response.json()
                if status_result.get("res_code") != 0:
                    log.error(f"检查任务状态失败: {status_result.get('res_message', '未知错误')}")
                    time.sleep(1)
                    continue
                
                task_status = status_result.get("taskStatus")
                
                if task_status == 4:  # 4表示任务成功完成
                    # 检查是否有失败的文件
                    failed_count = status_result.get("failedCount", 0)
                    
                    if failed_count > 0:
                        log.warning(f"任务 {task_id} 完成，但有 {failed_count} 个文件未成功删除")
                        return {
                            "success": True,
                            "partial": True,
                            "message": f"部分文件删除失败，共 {failed_count} 个",
                            "task_id": task_id,
                            "status": status_result,
                            "failed_count": failed_count
                        }
                    else:
                        log.info(f"任务 {task_id} 成功完成，所有文件已删除")
                        return {
                            "success": True,
                            "message": "文件删除成功",
                            "task_id": task_id,
                            "status": status_result
                        }
                elif task_status in [1, 3]:  # 1和3表示任务进行中
                    time.sleep(1)  # 暂停1秒后继续检查
                else:  # 其他状态视为失败
                    log.error(f"文件删除失败: 任务状态异常 {task_status}")
                    return {
                        "success": False,
                        "message": f"文件删除失败: 任务状态异常 {task_status}",
                        "task_id": task_id,
                        "status": status_result
                    }
        except json.JSONDecodeError as e:
            log.error(f"JSON解析错误: {e}")
            return {
                "success": False,
                "message": f"JSON解析错误: {str(e)}"
            }
        except Exception as e:
            log.error(f"删除文件失败：{str(e)}")
            return {
                "success": False,
                "message": f"删除文件失败：{str(e)}"
            }
            
    def delete_folder_contents(self, folder_id: str) -> dict:
        """
        删除指定ID文件夹下的所有子文件和子文件夹
        :param folder_id: 文件夹ID
        :return: 删除结果
        """
        try:
            log.info(f"开始删除文件夹 {folder_id} 下的所有内容")
            
            # 获取文件夹下的所有文件和子文件夹
            files_result = self.list_files(folder_id)
            
            if not files_result or not files_result.get("fileListAO"):
                log.warning(f"文件夹 {folder_id} 为空或获取文件列表失败")
                return {
                    "success": True,
                    "message": f"文件夹 {folder_id} 为空或获取文件列表失败"
                }
            
            file_list = files_result["fileListAO"].get("fileList", [])
            folder_list = files_result["fileListAO"].get("folderList", [])
            
            # 构造删除任务信息
            task_infos = []
            
            # 添加文件
            for file in file_list:
                # 检查id字段是否存在
                if "id" not in file:
                    log.warning(f"文件缺少id字段: {file}")
                    continue
                task_infos.append({
                    "fileId": file["id"],
                    "fileName": file.get("fileName", "未命名文件"),
                    "isFolder": 0
                })
            
            # 添加文件夹
            for folder in folder_list:
                # 检查id字段是否存在
                if "id" not in folder:
                    log.warning(f"文件夹缺少id字段: {folder}")
                    continue
                task_infos.append({
                    "fileId": folder["id"],
                    "fileName": folder.get("fileName", "未命名文件夹"),
                    "isFolder": 1
                })
            
            if not task_infos:
                log.info(f"文件夹 {folder_id} 下没有需要删除的内容")
                return {
                    "success": True,
                    "message": f"文件夹 {folder_id} 下没有需要删除的内容"
                }
            
            log.info(f"找到 {len(task_infos)} 个项目需要删除")
            
            # 执行删除
            delete_result = self.delete_files(task_infos)
            
            return delete_result
        except Exception as e:
            log.error(f"删除文件夹内容时发生异常: {e}")
            return {
                "success": False,
                "message": f"删除文件夹内容时发生异常: {str(e)}"
            }

    def getFolderIdByPath(self, path, folderId=-11):
        """
        通过路径获取目录ID
        :param path: 路径
        :param folderId: 起始目录ID
        :return: 目录ID
        """
        path = path.strip("/")
        if not path:
            return folderId
        for name in path.split("/"):
            found = False
            filesData = self.getObjectFolderNodes(folderId)
            for node in filesData:
                if node["name"] == name:
                    folderId = node["id"]
                    found = True
                    break
            if not found:
                return None
        return folderId

    def getShareInfo(self, link):
        # 尝试从查询参数中提取分享码，如果失败则尝试从路径中提取
        url = parse.urlparse(link)
        try:
            code = parse.parse_qs(url.query)["code"][0]
        except (KeyError, IndexError):
            # 从路径中提取分享码 (格式: /t/xxxx)
            path_parts = url.path.split('/')
            if len(path_parts) >= 3 and path_parts[1] == 't':
                code = path_parts[2]
            else:
                raise Exception("无法从分享链接中提取分享码")
        result = self.session.get("https://cloud.189.cn/api/open/share/getShareInfoByCodeV2.action", params={
            "shareCode": code
        }).json()
        #print(result)
        if result['res_code'] != 0:
            raise Exception(result['res_message'])
        return Cloud189ShareInfo(
            shareId=result["shareId"],
            shareDirFileId=result["fileId"],
            cloud189Client=self,
            shareMode=result["shareMode"]
        )

    def getEncrypt(self):
        result = self.session.post("https://open.e.189.cn/api/logbox/config/encryptConf.do", data={
            'appId': 'cloud'
        }).json()
        return result['data']['pubKey']

    def getRedirectURL(self):
        rsp = self.session.get('https://cloud.189.cn/api/portal/loginUrl.action?redirectURL=https://cloud.189.cn/web'
                               '/redirect.html?returnURL=/main.action')
        if rsp.status_code == 200:
            return parse.parse_qs(parse.urlparse(rsp.url).query)
        else:
            raise Exception(f"status code must be 200, but real is {rsp.status_code}")

    def getLoginFormData(self, username, password, encryptKey):
        query = self.getRedirectURL()
        resData = self.session.post('https://open.e.189.cn/api/logbox/oauth2/appConf.do', data={
            "version": '2.0',
            "appKey": 'cloud',
        }, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/76.0',
            "Referer": 'https://open.e.189.cn/',
            "lt": query["lt"][0],
            "REQID": query["reqId"][0],
        }).json()
        if resData.get('result') == '0':
            keyData = f"-----BEGIN PUBLIC KEY-----\n{encryptKey}\n-----END PUBLIC KEY-----"
            usernameEncrypt = rsaEncrpt(username, keyData)
            passwordEncrypt = rsaEncrpt(password, keyData)
            return {
                "returnUrl": resData['data']['returnUrl'],
                "paramId": resData['data']['paramId'],
                "lt": query['lt'][0],
                "REQID": query['reqId'][0],
                "userName": f"{{NRP}}{usernameEncrypt}",
                "password": f"{{NRP}}{passwordEncrypt}",
            }
        else:
            raise Exception(resData["msg"])

    def createFolderFromShareLink(self, link, parentFolderId):
        """
        从分享链接创建同名文件夹
        :param link: 分享链接
        :param parentFolderId: 父文件夹ID，默认为323141206736999024
        :return: 创建的文件夹ID
        """
        try:
            # 提取分享码
            # 尝试从查询参数中提取分享码，如果失败则尝试从路径中提取
            url = parse.urlparse(link)
            try:
                code = parse.parse_qs(url.query)["code"][0]
            except (KeyError, IndexError):
                # 从路径中提取分享码 (格式: /t/xxxx)
                path_parts = url.path.split('/')
                if len(path_parts) >= 3 and path_parts[1] == 't':
                    code = path_parts[2]
                else:
                    raise Exception("无法从分享链接中提取分享码")
            # 获取分享信息
            result = self.session.get("https://cloud.189.cn/api/open/share/getShareInfoByCodeV2.action", params={
                "shareCode": code
            }).json()
            if result['res_code'] != 0:
                log.error(f"获取分享信息失败: {result.get('res_message', '未知错误')}")
                return None
            # 提取文件名
            fileName = result['fileName']
            logger.info(f"原始文件名：{fileName}")
            if not fileName:
                log.error("分享信息中未找到fileName字段")
                return None
            
            # 清理文件名：移除非法字符并限制长度
            cleaned_fileName = clean_filename(fileName) + " " + time.strftime("[%m%d%H%M%S]")
            logger.info(f"清理后文件名：{cleaned_fileName}")
            
            # 创建文件夹
            folderId = self.createFolder(cleaned_fileName, parentFolderId)
            return folderId
        except Exception as e:
            log.error(f"从分享链接创建文件夹时发生异常: {e}")
            return None

    def login(self, username, password):
        notifier = TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID)
        encryptKey = self.getEncrypt()
        formData = self.getLoginFormData(username, password, encryptKey)
        data = {
            "appKey": 'cloud',
            "version": '2.0',
            "accountType": '01',
            "mailSuffix": '@189.cn',
            "validateCode": '',
            "returnUrl": formData['returnUrl'],
            "paramId": formData['paramId'],
            "captchaToken": '',
            "dynamicCheck": 'FALSE',
            "clientType": '1',
            "cb_SaveName": '0',
            "isOauth2": "false",
            "userName": formData['userName'],
            "password": formData['password'],
        }
        result = self.session.post('https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do', data=data, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/76.0',
            'Referer': 'https://open.e.189.cn/',
            'lt': formData['lt'],
            'REQID': formData['REQID'],
        }).json()
        if result['result'] == 0:
            self.session.get(result['toUrl'], headers={
                "Referer": 'https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1',
                'Accept-Encoding': 'gzip, deflate',
                "Host": 'cloud.189.cn',
            })
        else:
            notifier.send_message(f"天翼云盘登录失败，失败原因：{result['msg']}")

    def createFolder(self, name, parentFolderId=-11):
        """
        创建目录返回文件ID
        :param parentFolderId: 父目录ID
        :param name: 要创建的文件ID
        :return:
        """
        result = self.session.post("https://cloud.189.cn/api/open/file/createFolder.action", data={
            "parentFolderId": parentFolderId,
            "folderName": name,
        }).json()
        if result["res_code"] != 0:
            raise Exception(result["res_message"])
        return result["id"]

    def mkdirAll(self, path, parentFolderId=-11):
        """
        创建所有路径
        :param path: 需要创建的路径
        :param parentFolderId: 父目录ID
        :return: 创建完成的目录ID
        """
        path = path.strip("/")
        if path:
            for name in path.split("/"):
                parentFolderId = self.createFolder(name=name, parentFolderId=parentFolderId)
        return parentFolderId


def getArgs():
    parser = argparse.ArgumentParser(description="天翼云盘保存分享文件(无单次转存上限)")
    parser.add_argument('-l', help='分享链接(形如 https://cloud.189.cn/web/share?code=XXXXXXXXX)', required=True)
    parser.add_argument('-u', help='云盘用户名', required=True)
    parser.add_argument('-p', help='云盘用户密码', required=True)
    parser.add_argument('-d', help='保存到的云盘的路径(不存在会自动创建, 形如: /A/B)', required=True)
    parser.add_argument('-t', help='转存线程数', default=5)
    return parser.parse_args()


def save_189_link(client : Cloud189, link, parentFolderId):
    notifier = TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID)
    log.info("正在获取文件分享信息...")
    info = None
    try:
        info = client.getShareInfo(link)
    except Exception as e:
        log.error(f"获取分享信息出现错误: 链接错误或链接正在审核中 {e}")
        notifier.send_message(f"获取分享信息出现错误: 链接错误或链接正在审核中 {e}")
        return 0
    log.info("正在检查并创建目录...")
    saveDir = None
    try:
        saveDir = client.createFolderFromShareLink(link,parentFolderId)
    except Exception as e:
        log.error(f"检查并创建目录出现错误: {e}")
        notifier.send_message(f"检查并创建目录出现错误: {e}")
        return 0
    if not saveDir:
        log.error("无法获取保存目录信息，请检查天翼账号登录情况")
        notifier.send_message(f"无法获取保存目录信息，请检查天翼账号登录情况")
        return 0
    else:
        log.info("开始转储分享文件,耗时较长请耐心等待...")
        ret = info.createBatchSaveTask(saveDir, 500, maxWorkers=5).run()
        if not ret:
            log.info("所有分享文件已保存.")
            return 1
        else:
            log.error("保存分享文件出现出现错误：重复转存或其他异常")
            notifier.send_message(f"保存分享文件出现出现错误：重复转存或其他异常")
            return 0

def init_database():
    """初始化数据库（增加转存状态字段）"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.execute('''CREATE TABLE IF NOT EXISTS messages
                 (msg_id INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, date TEXT, message_url TEXT, target_url TEXT, 
                   transfer_status TEXT, transfer_time TEXT, transfer_result TEXT)''')
    conn.commit()
    conn.close()

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
        channel_urls = os.getenv("ENV_189_TG_CHANNEL", "").split('|')
        if not channel_urls or channel_urls == ['']:
            logger.warning("未配置ENV_189_TG_CHANNEL环境变量")
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
                    # print(str(text_elem))
                    target_urls = extract_target_url(f"{msg}")
                    if target_urls:
                        for url in target_urls:
                            if not is_message_processed(message_url):
                                new_messages.append((message_id, date_str, message_url, url, message_text))
                                logger.info(message_url)
                            else:
                                logger.info(f"第{i + 1}新消息已处理，跳过")
                            logger.info(f"tg消息链接：{message_url}")
                            logger.info(f"天翼网盘链接：{url}")
                    else:
                        logger.info("未发现目标天翼网盘链接")
            
            all_new_messages.extend(new_messages)
        
        # 按时间正序排列所有消息
        all_new_messages.sort(key=lambda x: x[1])
        logger.info(f"===== 所有频道处理完成，共发现{len(all_new_messages)}条新的天翼网盘分享链接 =====")
        return all_new_messages

    except requests.exceptions.RequestException as e:
        logger.error(f"网络请求失败: {str(e)[:100]}")
        return []

def extract_target_url(text):
    import re
    # 正则模式：同时匹配两种链接格式
    # 1. /t/xxx 格式：https://cloud.189.cn/t/任意字母数字组合
    # 2. /web/share?code=xxx 格式：https://cloud.189.cn/web/share?code=任意字母数字组合
    pattern = r'https?:\/\/cloud\.189\.cn\/(t\/\w+|web\/share\?code=\w+)'
    # 忽略大小写、支持多行文本匹配
    matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
    if matches:
        # 去除重复链接并清理空格
        unique_matches = list(set([match.strip() for match in matches]))
        # 拼接完整链接（因为正则分组可能只匹配路径部分，需补全域名）
        # 注：如果原始文本中的链接是完整的，这步可省略；若仅匹配到路径，需拼接
        full_links = [f"https://cloud.189.cn/{link}" if not link.startswith("http") else link for link in unique_matches]
        return full_links
    return []

def tg_189monitor(client):
    init_database()
    
    notifier = TelegramNotifier(TG_BOT_TOKEN, TG_ADMIN_USER_ID)
    logger.info(f"===== 开始检查 天翼网盘监控（{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）=====")
    new_messages = get_latest_messages()
    #schedule.run_pending()
    if new_messages:
        for msg in new_messages:
            message_id, date_str, message_url, target_url, message_text = msg
            logger.info(f"处理新消息: {message_id} | {target_url}")

            # 转存到115
            result = save_189_link(client, target_url, ENV_189_UPLOAD_PID)
            if result:
                status = "转存成功"
                result_msg = f"✅天翼云盘转存成功\n消息内容: {message_url}\n链接: {target_url}"
            else:
                status = "转存失败"
                result_msg = f"❌天翼云盘转存失败\n消息内容: {message_url}\n链接: {target_url}"

            notifier.send_message(result_msg)

            # 保存结果到数据库
            save_message(message_id, date_str, message_url, target_url, status, result_msg)
    else:
        logger.info("未发现新的天翼网盘分享链接")

if __name__ == '__main__':
    
    #save_189_link(client, "https://cloud.189.cn/t/3QnUbejaMvui", ENV_189_UPLOAD_PID)
    #save_189_link(client, "https://cloud.189.cn/t/iu2MJ3BjqMBj", ENV_189_UPLOAD_PID)
    #tg_189monitor()
    client = Cloud189()
    try:
        logger.info("189正在登录 ...")
        client.login(ENV_189_CLIENT_ID, ENV_189_CLIENT_SECRET)
    except Exception as e:
        logger.error(f"登录出现错误: {e}")
    info = client.getShareInfo("https://cloud.189.cn/t/NZzmYrQjMb6z")
    info = client.getShareInfo("https://cloud.189.cn/t/ZzyYfmeE3uIb")
    logger.info(info)
    save_189_link(client, "https://cloud.189.cn/t/NZzmYrQjMb6z", 923961206742226023)
    #client.delete_folder_contents("724071207997330113")
    #client.empty_recycle_bin()
    exit(-1)
