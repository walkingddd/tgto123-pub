import requests
import json

def submit_magnet_video_download(magnet_link, token, upload_dir_id):
    """
    解析磁力链并提交视频文件下载任务，使用目录ID指定上传位置
    
    参数:
        magnet_link: 磁力链字符串
        token: 认证令牌
        upload_dir_id: 上传目录的ID（整数形式，如21994788）
    
    返回:
        提交结果的字典，如果成功包含task_id等信息
    """
    # 1. 解析磁力链获取文件列表
    resolve_url = "https://www.123pan.com/b/api/v2/offline_download/task/resolve"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 发送解析请求
    resolve_payload = {"urls": magnet_link}
    try:
        resolve_response = requests.post(
            resolve_url,
            headers=headers,
            data=json.dumps(resolve_payload)
        )
        resolve_response.raise_for_status()  # 检查请求是否成功
    except requests.exceptions.RequestException as e:
        return {"code": -1, "message": f"解析磁力链失败: {str(e)}"}
    
    # 解析响应结果
    resolve_data = resolve_response.json()
    if resolve_data.get("code") != 0:
        return {"code": -1, "message": f"解析磁力链返回错误: {resolve_data.get('message')}"}
    
    # 检查是否有资源数据
    if not resolve_data.get("data", {}).get("list"):
        return {"code": -1, "message": "未找到对应的资源数据"}
    
    resource_info = resolve_data["data"]["list"][0]
    resource_id = resource_info.get("id")
    if not resource_id:
        return {"code": -1, "message": "无法获取资源ID"}
    
    # 2. 筛选视频文件（根据category=2或文件名以.mp4结尾判断）
    video_file_ids = []
    for file in resource_info.get("files", []):
        # 判断是否为视频文件
        is_video = (file.get("category") == 2) or \
                  (file.get("name", "").lower().endswith(".mp4")) or \
                  (file.get("name", "").lower().endswith(".mkv"))
        
        if is_video:
            video_file_ids.append(file.get("id"))
    
    if not video_file_ids:
        return {"code": -1, "message": "未找到视频文件"}
    
    # 3. 提交下载任务，使用目录ID作为upload_dir参数
    submit_url = "https://www.123pan.com/b/api/v2/offline_download/task/submit"
    submit_payload = {
        "resource_list": [
            {
                "resource_id": resource_id,
                "select_file_id": video_file_ids
            }
        ],
        "upload_dir": upload_dir_id  # 这里使用目录ID（整数）
    }
    
    try:
        submit_response = requests.post(
            submit_url,
            headers=headers,
            data=json.dumps(submit_payload)
        )
        submit_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"code": -1, "message": f"提交下载任务失败: {str(e)}"}
    
    submit_data = submit_response.json()
    if submit_data.get("code") != 0:
        return {"code": -1, "message": f"提交下载任务返回错误: {submit_data.get('message')}"}
    
    return submit_data

# 使用示例
if __name__ == "__main__":
    # 示例参数（实际使用时替换为真实值）
    example_magnet = ""
    example_token = ""
    example_upload_dir_id = 27610239  # 目录ID形式的上传目录
    
    result = submit_magnet_video_download(example_magnet, example_token, example_upload_dir_id)
    print(result)
