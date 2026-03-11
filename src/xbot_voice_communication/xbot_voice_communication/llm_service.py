import os
import requests
import json
import time

def call_llm(prompt, context=None, use_local=False):
    if use_local:
        # 本地模型调用（保留此接口）
        return "本地模型调用未实现"
    else:
        # DeepSeek API调用
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return "未设置DeepSeek API Key"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 构建消息历史
        messages = []
        if context:
            messages = context[-6:]  # 限制上下文长度
        else:
            messages = [{"role": "user", "content": prompt}]
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        
        retries = 3
        for attempt in range(retries):
            try:
                response = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                return data['choices'][0]['message']['content']
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    print(f"API调用失败，{wait_time}秒后重试... ({str(e)})")
                    time.sleep(wait_time)
                else:
                    return f"API调用失败: {str(e)}"
            except Exception as e:
                return f"处理响应失败: {str(e)}"
        
