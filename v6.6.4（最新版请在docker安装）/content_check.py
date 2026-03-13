import requests
import json
from dotenv import load_dotenv
import os

# 加载.env文件中的环境变量
load_dotenv(dotenv_path="db/user.env",override=True)
load_dotenv(dotenv_path="sys.env",override=True)

def check_porn_content(
    content: str,
    api_url=os.getenv("AI_API_URL", ""),
    api_key=os.getenv("AI_API_KEY", ""),
    model_name=os.getenv("AI_API_MODEL", ""),
    max_tokens=15000
) -> dict:
    """
    严格检测内容是否涉及色情（支持用户自定义API参数）
    
    参数:
        content: 需要检测的文本内容（用户输入）
        api_url: API接口完整地址（用户手动填写，如https://api.siliconflow.cn/v1/chat/completions）
        api_key: 访问API的密钥（用户手动填写）
        model_name: 模型标识（用户手动填写，如deepseek-ai/DeepSeek-V2.5）
        
    返回:
        包含检测结果的字典，格式为:
        {
            "is_pornographic": bool,  # 是否涉及色情
            "confidence": float,      # 置信度(0-1)
            "reason": str             # 判断依据
        }
    """
    # 严格模式提示词（保持"宁可错杀"原则）
    prompt = f"""
    请以"宁可错杀一千，不可放过一个"的严格标准判断以下内容是否涉及色情。
    判断标准：
    1. 任何直接/间接描述性行为、性器官、性暗示的内容均判定为色情
    2. 涉及低俗挑逗、性诱惑、性交易的内容均判定为色情
    3. 对身体敏感部位的不当描述或暗示均判定为色情
    4. 模糊不清、疑似涉及色情的内容一律判定为色情
    5. 即使只有部分内容违规，整体判定为涉及色情
    
    需要判断的内容：
    {content}
    
    请按照以下格式输出，不得添加额外内容：
    是否色情：是/否
    置信度：0.0-1.0之间的数值
    判断依据：简要说明判断理由（50字以内）
    """
    
    # 构建请求参数（使用用户传入的模型名称）
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "你是严格的内容审核员，对色情内容采取零容忍态度，任何疑似内容都判定为违规。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens
    }
    
    # 请求头（使用用户传入的API密钥）
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        # 发送请求（使用用户传入的API地址）
        response = requests.post(
            api_url+"/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=30
        )
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        response_text = result["choices"][0]["message"]["content"].strip()
        
        # 提取结果字段
        lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        is_porn = None
        confidence = None
        reason = ""
        
        for line in lines:
            if line.startswith("是否色情："):
                is_porn = line.split("：")[1].strip() == "是"
            elif line.startswith("置信度："):
                confidence = float(line.split("：")[1].strip())
            elif line.startswith("判断依据："):
                reason = line.split("：")[1].strip()
        
        if is_porn is None or confidence is None:
            raise ValueError("模型返回格式不符合要求")
            
        return {
            "is_pornographic": is_porn,
            "confidence": confidence,
            "reason": reason
        }
        
    except requests.exceptions.RequestException as e:
        print(f"API请求失败: {str(e)}")
        return None
    except (KeyError, ValueError) as e:
        print(f"结果解析错误: {str(e)}")
        return None

# 使用示例（用户需手动填写以下参数）
if __name__ == "__main__":
    # 用户手动输入参数
    user_api_url = os.getenv("AI_API_URL", "")
    user_api_key = os.getenv("AI_API_KEY", "")
    user_model = os.getenv("AI_API_MODEL", "")
    user_content = "异种族风俗娘评鉴指南动画改编自masha创作的同名漫画，动画由Passione负责制作，于2020年1月开始播出。这里是除了人类以外，还有精灵、妖精、兽人、魔族、妖怪、天使与恶魔等，各种异种族混杂在一起居住的世界。自然，这里也会有各异种族的风俗小店…。经常光顾店里接受不可描述杀必死的人类冒险者·史坦克，某天与种族间（性方面的）感性不同的损友——好色精灵杰尔发生冲突。他们决斗的方法是……风俗娘的评鉴！？将各异种族娘的杀必死以交叉评价的方式打分，并作为“能派上用场”的情报提供给其他同伴的史坦克等人的活跃，正是性战士的作风！评价者们今天也启程前去追求全新的快乐……。"
    user_content2 = "民国年间，战乱频发。五庆班班主侯喜亭（陈佩斯 饰）带着一众名角儿来到德祥大戏院演出，谁成想首演压轴登场的却是包子铺的伙计大嗓儿（黄渤 饰）？全场观众都在翘首以盼名角儿金啸天（尹正 饰）亮相，可刚攻城称王的洪大帅（姜武 饰）却偏偏指名让大嗓儿唱这出《霸王别姬》！眼看戏班的招牌就要砸了，前台戏迷退票砸场让戏院吴经理（杨皓宇 饰）苦不堪言，后台洪大帅持枪闹事更是让人吓破了胆！台前台后都乱了套，男旦凤小桐（余少群 饰）、教化处处长徐明礼（陈大愚 饰）、怀有异心的六姨太（徐卓儿 饰）等人也被卷入这场令人啼笑皆非的闹剧之中……台上霸王声声唱，台下荒唐众生相，既要保住戏班饭碗，又要哄好台下观众，大幕拉开之后，这场戏到底要怎么唱？"
    user_content3 = "女主角幸是一个不幸的女生，她在家被父母虐待在学校被同学欺凌，而且就连老师也侵犯她。但在某一天，幸的人生被一个诱拐犯拯救了。虽然男主角犯下了罪行，但却把幸从可怕的地狱中解救出来。罪犯与受害人在相处之后，逐渐喜欢上了对方，幸与诱拐犯定下结婚的誓言。"
    user_content4 = "本是岭南大学学生的王佳芝（汤唯 饰）因战争辗转到了香港读书，她在香港大学加入了爱国青年邝裕民（王力宏 饰）组织的话剧组，他们主演的爱国话剧更激起了他们的爱国情操。当邝裕民得知汪伪政府的特务头子易先生（梁朝伟 饰）正在香港的时候，他们便密谋要刺杀易先生。化名“麦太太”的王佳芝很快得到了易太太（陈冲 饰）的信任与喜爱，同时美丽的“麦太太”也吸引了易先生的眼球，正当事情进行得如火如荼之际，易先生突然要回到上海去。 此后王佳芝一直生活在上海，没想到重遇了邝裕民。当得知刺杀行动还没结束时，王佳芝再次成为了特务，再次以“麦太太”的身份出现在易先生的面前。重逢后的二人关系进一步发展，此时的易先生因爱上了王佳芝而对她毫无忌讳，王佳芝的内心也变得起伏不定。刺杀行动进行正顺利，但当易先生送给王佳芝璀璨钻戒表达爱意时，王佳芝做出了惊人的决定……"
    # 调用检测函数
    detection_result = check_porn_content(
        content=user_content4,
        api_url="https://api.edgefn.net",
        api_key="",
        model_name="",
        max_tokens=15000
    )
    
    # 输出结果
    if detection_result:
        print("\n检测结果:")
        print(f"是否涉及色情: {'是' if detection_result['is_pornographic'] else '否'}")
        print(f"置信度: {detection_result['confidence']}")
        print(f"判断依据: {detection_result['reason']}")
    