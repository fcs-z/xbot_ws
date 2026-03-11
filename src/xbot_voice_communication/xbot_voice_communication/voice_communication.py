#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import time
import threading
import subprocess
import sys
import tty
import termios

import rclpy
from rclpy.node import Node

# 从同级包中导入模块
from .asr import record_audio, load_model, init_recorder, create_recognizer
from .llm_service import call_llm
from .tts import text_to_speech

class KeyboardListener:
    def __init__(self, node, player):
        self.node = node
        self.player = player
        self.interrupt_requested = False
        self.listening = False
        self.thread = None
    
    def start(self):
        """启动键盘监听线程"""
        if self.listening:
            return
        self.listening = True
        self.interrupt_requested = False
        self.thread = threading.Thread(target=self._keyboard_listen, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止键盘监听"""
        self.listening = False
        if self.thread:
            self.thread.join(timeout=0.1)
        self.thread = None
    
    def _keyboard_listen(self):
        self.node.get_logger().info("按空格键可打断语音播放...")
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        
        try:
            # 设置非阻塞输入
            tty.setcbreak(fd)
            while self.listening:
                try:
                    ch = sys.stdin.read(1)
                    if ch == ' ':
                        self.node.get_logger().info("检测到空格键，请求打断...")
                        self.interrupt_requested = True
                        self.player.stop()
                except IOError:
                    pass
                time.sleep(0.01)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

class AudioPlayer:
    """使用 mpg123 在子进程中播放音频文件，并支持被打断"""
    def __init__(self, node):
        self.node = node
        self.process = None
        self.is_playing = False
        self.interrupt_event = threading.Event()
        self.lock = threading.Lock()
    
    def play(self, file_path: str):
        """非阻塞播放音频文件"""
        with self.lock:
            if self.is_playing:
                self.stop()
            
            self.is_playing = True
            self.interrupt_event.clear()
            
            def play_thread():
                try:
                    # -q 表示静默模式（不输出信息）
                    self.process = subprocess.Popen(
                        ["mpg123", "-q", file_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    # 等待播放完成或被中断
                    while self.process.poll() is None:
                        if self.interrupt_event.is_set():
                            self.node.get_logger().debug("播放线程检测到中断请求，终止播放")
                            self.process.terminate()
                            break
                        time.sleep(0.1)
                finally:
                    with self.lock:
                        self.is_playing = False
            
            threading.Thread(target=play_thread, daemon=True).start()
    
    def stop(self):
        """请求停止当前播放"""
        with self.lock:
            if self.is_playing:
                self.interrupt_event.set()
                if self.process:
                    self.process.terminate()
                self.is_playing = False

class VoiceAssistantNode(Node):
    def __init__(self):
        super().__init__('voice_assistant_node')
        self.get_logger().info("语音助手 ROS2 节点启动")
        
        # 提前加载语音识别模型
        self.get_logger().info("加载语音识别模型...")
        self.model = load_model()
        init_recorder()
        self.get_logger().info("模型加载并初始化录音设备完成")
        
        # 播放器与键盘监听器
        self.player = AudioPlayer(self)
        self.keyboard_listener = KeyboardListener(self, self.player)
        
        # 播放启动问候语
        greeting = "你好，我是您的语音助手，有什么可以帮您？"
        greeting_file = text_to_speech(greeting, "greeting.mp3")
        if greeting_file:
            self.get_logger().info("播放问候语...")
            self.player.play(greeting_file)
            while self.player.is_playing:
                time.sleep(0.1)
        
        # 对话上下文
        self.conversation_context = []
        
        # 直接调用循环监听语音
        self._main_loop()
    
    def _main_loop(self):
        """持续循环：1. 语音识别 → 2. LLM 问答 → 3. TTS 播放"""
        while rclpy.ok():
            try:
                self.get_logger().info("请开始说话...")
                recognizer = create_recognizer(self.model)
                user_input = record_audio(recognizer)
                
                if not user_input or len(user_input.strip()) == 0:
                    self.get_logger().info("未检测到有效语音输入，继续监听...")
                    continue
                
                self.get_logger().info(f"用户提问: {user_input}")
                self.conversation_context.append({"role": "user", "content": user_input})
                
                # 调用 LLM
                self.get_logger().info("正在生成回答...")
                start_time = time.time()
                response = call_llm(user_input, context=self.conversation_context)
                gen_time = time.time() - start_time
                self.get_logger().info(f"回答生成完成 (耗时: {gen_time:.2f} 秒)")
                self.get_logger().info(f"助手回答: {response}")
                
                # TTS 合成
                self.get_logger().info("正在合成语音...")
                audio_file = text_to_speech(response)
                
                if audio_file and os.path.exists(audio_file):
                    self.get_logger().info("播放回答...")
                    # 启动键盘监听：支持用空格打断
                    self.keyboard_listener.start()
                    self.player.play(audio_file)
                    
                    # 等待播放结束或被中断
                    while self.player.is_playing:
                        time.sleep(0.1)
                    
                    # 停止监听
                    self.keyboard_listener.stop()
                    
                    if self.keyboard_listener.interrupt_requested:
                        self.get_logger().info("检测到用户打断，移除本轮上下文并继续下一轮")
                        # 移除用户提问上下文
                        if (self.conversation_context and  
                            self.conversation_context[-1]["role"] == "user"):
                            self.conversation_context.pop()
                        # 播放打断提示
                        interrupt_audio = text_to_speech("请说", "interrupt.mp3")
                        if interrupt_audio:
                            self.player.play(interrupt_audio)
                            while self.player.is_playing:
                                time.sleep(0.1)
                        continue
                    
                    # 正常播放完毕，将回答加入上下文
                    self.conversation_context.append({"role": "assistant", "content": response})
                    self.get_logger().info("=" * 50)
                else:
                    self.get_logger().warn("语音合成失败，跳过播放")
            
            except Exception as e:
                self.get_logger().error(f"发生错误: {e}")
                time.sleep(1.0)

def main(args=None):
    rclpy.init(args=args)
    
    # 检查并安装 mpg123 与 PyAudio
    try:
        if os.system("which mpg123 > /dev/null") != 0:
            print("安装 mpg123 播放器...")
            os.system("sudo apt install -y mpg123")
        import pyaudio
    except ImportError:
        print("安装 PyAudio 库...")
        os.system("pip install pyaudio")
    
    node = VoiceAssistantNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
