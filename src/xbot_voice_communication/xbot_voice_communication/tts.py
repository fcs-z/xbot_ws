import asyncio
from edge_tts import Communicate
import os
import hashlib
import time
import re  # 添加正则表达式模块

# 创建缓存目录
CACHE_DIR = "tts_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def clean_text_for_tts(text):
    """清理文本中不需要朗读的特殊符号"""
    # 移除 Markdown 格式符号（* _ ~ `）
    text = re.sub(r'[\*\_\~\`]', '', text)
    # 移除 URL
    text = re.sub(r'https?:\/\/\S+', '', text)
    # 替换特殊符号为空格（避免拼接单词）
    text = re.sub(r'[<>\[\](){}|\\:;="^%$#@!&+]', ' ', text)
    # 合并连续空格
    return re.sub(r'\s+', ' ', text).strip()

async def async_synthesize(text, output_file="output.mp3"):
    try:
        # 清洗文本
        cleaned_text = clean_text_for_tts(text)
        # 使用微软晓晓中文语音
        communicate = Communicate(cleaned_text, voice="zh-CN-XiaoxiaoNeural")
        await communicate.save(output_file)
        return output_file
    except Exception as e:
        print(f"TTS合成失败: {str(e)}")
        return None

def text_to_speech(text, output_file=None):
    if not text or len(text.strip()) == 0:
        return None
        
    # 生成文件名哈希
    if output_file is None:
        text_hash = hashlib.md5(text.encode()).hexdigest()
        output_file = os.path.join(CACHE_DIR, f"{text_hash}.mp3")
    
    # 检查缓存
    if os.path.exists(output_file):
        return output_file
    
    # 包装异步函数
    try:
        result = asyncio.run(async_synthesize(text, output_file))
    except RuntimeError:
        # 处理事件循环问题
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(async_synthesize(text, output_file))
        loop.close()
    
    # 返回结果（即使失败也返回路径）
    return result if result else output_file
