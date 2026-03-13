from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import re
import secrets
import sys
import logging
from get_download_url_by_path import get_download_url_by_path
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # 生成安全的随机密钥

# 配置文件路径
TEMPLATE_ENV_PATH = 'templete.env'
ENV_FILE_PATH = os.path.join('db', 'user.env')

# 从环境变量或默认值获取认证信息
ENV_WEB_PASSPORT = os.getenv("ENV_WEB_PASSPORT", "admin")
ENV_WEB_PASSWORD = os.getenv("ENV_WEB_PASSWORD", "123456")

# 确保db目录存在
os.makedirs('db', exist_ok=True)

# 读取模板文件和配置文件，生成页面选项
@app.route('/api/env')
def get_env():
    # 首先读取模板文件获取结构和注释
    template_structure = {}
    template_order = []
    current_section = None
    current_comment = ''

    if not os.path.exists(TEMPLATE_ENV_PATH):
        return jsonify({'error': 'Template file not found'}), 404

    with open(TEMPLATE_ENV_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 检测一级章节标题 (# 标题)
            if line.startswith('# ') and not line.startswith('## '):
                current_section = line[2:]
                if current_section not in template_structure:
                    template_structure[current_section] = []
                    template_order.append(current_section)
                current_comment = ''
            # 检测二级标题或注释 (## 或 # 但不是章节标题)
            elif line.startswith('#'):
                # 提取注释内容（去掉#或##前缀）
                if line.startswith('## '):
                    current_comment = line[3:]
                else:
                    current_comment = line[2:]
            # 检测配置项
            elif '=' in line and not line.startswith('#'):
                key, _ = line.split('=', 1)
                config_item = {
                    'key': key.strip(),
                    'value': '',  # 模板中值留空
                    'comment': current_comment
                }
                # 添加到当前章节
                if current_section:
                    template_structure[current_section].append(config_item)
                # 重置当前注释
                current_comment = ''

    # 然后读取实际配置文件获取值
    if os.path.exists(ENV_FILE_PATH):
        with open(ENV_FILE_PATH, 'r', encoding='utf-8') as f:
            env_values = {}
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_values[key.strip()] = value.strip()

        # 用实际值填充模板结构
        for section in template_structure:
            for item in template_structure[section]:
                if item['key'] in env_values:
                    item['value'] = env_values[item['key']]

    return jsonify({'sections': template_structure, 'order': template_order})

# 保存.env文件
@app.route('/api/env', methods=['POST'])
def save_env():
    data = request.json
    with open(ENV_FILE_PATH, 'w', encoding='utf-8') as f:
        for section, items in data.items():
            f.write(f'# {section}\n')
            for item in items:
                f.write(f'## {item["comment"]}\n')
                f.write(f'{item["key"]}={item["value"]}\n')
            f.write('\n')
    # 保存成功后退出程序，触发容器重启
    logger.info("配置已保存，程序将退出以触发容器重启...")
    # 延迟1秒退出，确保响应能发送回客户端
    import time
    time.sleep(1)
    # 使用os._exit(0)强制终止整个进程，包括所有线程
    os._exit(0)
    return jsonify({'success': True})

# 登录API
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    # 验证用户名和密码
    if username == ENV_WEB_PASSPORT and password == ENV_WEB_PASSWORD:
        session['logged_in'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False})

# 登出API
@app.route('/api/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login_page'))

# 登录页面
@app.route('/login')
def login_page():
    # 如果已登录则重定向到主页
    if session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('login.html')

# 提供静态文件
@app.route('/')
def index():
    # 检查是否已登录
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    return render_template('index.html')

# 直接下载端点：302重定向到实际下载链接
@app.route('/d/<path:file_path>')
def handle_direct_download(file_path):
    try:
        # 添加前导斜杠确保路径格式正确
        full_path = f"/{file_path}"
        download_url = get_download_url_by_path(full_path)
        if download_url:
            return redirect(download_url, code=302)
        else:
            return jsonify({'error': "文件未找到"}), 404
    except Exception as e:
        logger.error(f"下载处理异常: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 确保templates和static文件夹存在
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    app.run(host='0.0.0.0', port=12366, debug=True)