import os
import sys
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import json
import logging
import time

# 全局模型，避免重复加载
global_model = None

def suppress_vosk_logs():
    """隐藏Vosk的日志输出"""
    vosk_logger = logging.getLogger("vosk")
    vosk_logger.setLevel(logging.WARNING)
    vosk_logger.propagate = False
    
    # 重定向Kaldi日志
    if not hasattr(sys, 'stderr_orig'):
        sys.stderr_orig = sys.stderr
        sys.stderr = open(os.devnull, 'w')

def load_model(model_path="/home/fcs/xbot_ws/src/xbot_voice_communication/models/vosk/vosk-model-cn-0.22"):
    """提前加载模型并隐藏日志"""
    global global_model
    if global_model is None:
        # 隐藏日志
        suppress_vosk_logs()
        
        # 加载模型
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"未找到语音模型: {model_path}")
            
        global_model = Model(model_path)
        
        # 恢复stderr
        if hasattr(sys, 'stderr_orig'):
            sys.stderr = sys.stderr_orig
            del sys.stderr_orig
            
        print(f"语音模型已加载: {model_path}")
    return global_model

def create_recognizer(model):
    """创建新的识别器实例"""
    return KaldiRecognizer(model, 16000)

def init_recorder():
    """初始化录音设备"""
    # 预加载录音设备，避免首次录音延迟
    try:
        with sd.InputStream(samplerate=16000, blocksize=8000, dtype='int16', channels=1):
            pass
    except Exception as e:
        print(f"录音设备初始化失败: {str(e)}")
        # 继续运行，可能在后续录音中恢复

def record_audio(recognizer):
    """使用提供的识别器进行录音"""
    q = queue.Queue()
    
    def callback(indata, frames, time, status):
        q.put(bytes(indata))
    
    try:
        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                              channels=1, callback=callback):
            start_time = time.time()
            while True:
                try:
                    data = q.get(timeout=5.0)  # 增加超时时间
                except queue.Empty:
                    return ""  # 超时返回空
                
                if recognizer.AcceptWaveform(data):
                    result = recognizer.Result()
                    text = json.loads(result).get("text", "")
                    if text:
                        print(f"识别结果: {text}")
                        return text
                        
                # 超时处理
                if time.time() - start_time > 30:
                    return ""
                    
    except Exception as e:
        print(f"录音过程中发生异常: {e}")
        return ""
