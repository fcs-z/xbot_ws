#!/usr/bin/env python3
import os
import queue
import sounddevice as sd
import json
from vosk import Model, KaldiRecognizer, SetLogLevel
import numpy as np
from pinyin import get
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import threading
import time

# 禁用 Vosk 日志输出
SetLogLevel(-1)

# 配置参数
MODEL_PATH = os.path.expanduser("/home/fcs/xbot_ws/src/xbot_voice_control/models/vosk-model-small-cn-0.22")
SAMPLE_RATE = 16000
BLOCKSIZE = 16000
WAKE_WORD = "小广"

# 定义控制指令及其拼音
COMMANDS = {
    "前进": "qianjin",
    "后退": "houtui",
    "向左": "xiangzuo",
    "向右": "xiangyou",
    "停下": "tingxia"
}

class RobotController(Node):
    def __init__(self):
        super().__init__('robot_voice_controller')
        # 创建/cmd_vel话题的发布者
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.get_logger().info("语音控制器节点已启动，准备接收指令...")
        
        # 定义移动参数
        self.linear_speed = 0.2  # 线速度(m/s)
        self.angular_speed = 0.5  # 角速度(rad/s)
        
        # 移动控制相关变量
        self.current_direction = None
        self.is_moving = False
        self.move_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.move_thread = None
        
        # 启动移动控制线程
        self.move_control_thread = threading.Thread(target=self._move_control_loop)
        self.move_control_thread.daemon = True
        self.move_control_thread.start()
    
    def _move_control_loop(self):
        """移动控制循环，独立线程运行"""
        while rclpy.ok():
            if self.current_direction:
                # 创建Twist消息
                twist = Twist()
                
                # 设置运动参数
                if self.current_direction == "前进":
                    twist.linear.x = self.linear_speed
                elif self.current_direction == "后退":
                    twist.linear.x = -self.linear_speed
                elif self.current_direction == "向左":
                    twist.angular.z = self.angular_speed
                elif self.current_direction == "向右":
                    twist.angular.z = -self.angular_speed
                
                # 发布运动指令
                self.cmd_vel_pub.publish(twist)
            
            # 短暂休眠
            time.sleep(0.1)
    
    def start_move(self, direction):
        """开始向指定方向移动"""
        with self.move_lock:
            if self.current_direction == direction:
                self.get_logger().info(f"已经在{direction}，无需重复操作")
                return
                
            # 停止当前移动
            self._stop_move()
            
            # 设置新方向
            self.current_direction = direction
            self.is_moving = True
            self.stop_event.clear()
            self.get_logger().info(f"开始{direction}")
    
    def _stop_move(self):
        """停止移动并发布零速度"""
        if self.current_direction:
            self.get_logger().info(f"停止{self.current_direction}")
            self.current_direction = None
            self.is_moving = False
            
            # 发布停止指令
            stop_twist = Twist()
            self.cmd_vel_pub.publish(stop_twist)
    
    def stop(self):
        """立即停止机器人运动"""
        with self.move_lock:
            if self.is_moving:
                self._stop_move()
                self.stop_event.set()
                self.get_logger().info("已停止移动")
            else:
                self.get_logger().info("当前未移动")

def levenshtein_similarity(s1, s2):
    """
    计算两个字符串的编辑距离相似度（0.0-1.0）
    """
    if len(s1) == 0 or len(s2) == 0:
        return 0.0
        
    # 创建距离矩阵
    d = np.zeros((len(s1)+1, len(s2)+1))
    for i in range(len(s1)+1):
        d[i][0] = i
    for j in range(len(s2)+1):
        d[0][j] = j

    # 计算编辑距离
    for i in range(1, len(s1)+1):
        for j in range(1, len(s2)+1):
            cost = 0 if s1[i-1] == s2[j-1] else 1
            d[i][j] = min(d[i-1][j] + 1,      # 删除
                          d[i][j-1] + 1,      # 插入
                          d[i-1][j-1] + cost)  # 替换

    # 计算相似度（1 - 标准化编辑距离）
    max_len = max(len(s1), len(s2))
    return 1.0 - d[-1][-1] / max_len

def text_to_pinyin(text):
    """
    将中文字符串转换为拼音（小写，无空格，无音调）
    示例: "你好" -> "nihao"
    """
    if not text:
        return ""
    
    # 使用pinyin库获取拼音列表
    pinyin_list = get(text, format="strip", delimiter=",").split(',')
    # 合并拼音并移除数字（音调）
    return ''.join([p.rstrip('012345') for p in pinyin_list])

def callback(indata, frames, time, status):
    """
    回调函数负责接收音频帧并放入队列
    """
    if status:
        print(f"声音输入状态：{status}")
    audio_queue.put(bytes(indata))

def execute_command(controller, text):
    """
    根据识别到的文本执行相应的命令
    """
    text_pinyin = text_to_pinyin(text)
    print(f"指令文本: {text}, 拼音: {text_pinyin}")
    
    best_match = None
    max_similarity = 0
    
    # 计算与所有指令的相似度
    for cmd, cmd_pinyin in COMMANDS.items():
        similarity = levenshtein_similarity(text_pinyin, cmd_pinyin)
        print(f"  - '{cmd}' ({cmd_pinyin}) 相似度: {similarity:.2f}")
        
        if similarity > max_similarity:
            max_similarity = similarity
            best_match = cmd
    
    # 如果最高相似度超过阈值，执行对应命令
    if best_match and max_similarity >= 0.5:
        print(f"匹配指令: {best_match}, 相似度: {max_similarity:.2f}")
        
        if best_match == "停下":
            controller.stop()
        else:
            controller.start_move(best_match)
        return True
    
    print("未匹配到有效指令")
    return False

def main():
    # 初始化ROS2节点
    rclpy.init()
    
    # 创建机器人控制器
    controller = RobotController()
    
    # 检查模型文件夹是否存在
    if not os.path.exists(MODEL_PATH):
        controller.get_logger().error(f"模型目录不存在：{MODEL_PATH}")
        return

    # 加载 Vosk 模型
    controller.get_logger().info("正在加载模型，请稍候……")
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, SAMPLE_RATE)
    controller.get_logger().info("模型加载完毕，准备打开音频流。")
    
    # 预计算唤醒词的拼音
    wake_pinyin = text_to_pinyin(WAKE_WORD)
    controller.get_logger().info(f"唤醒词 '{WAKE_WORD}' 拼音: {wake_pinyin}")
    
    # 打印可用指令
    controller.get_logger().info("可用指令:")
    for cmd, pinyin in COMMANDS.items():
        controller.get_logger().info(f"  - {cmd} ({pinyin})")

    # 创建线程安全队列
    global audio_queue
    audio_queue = queue.Queue()
    
    # 唤醒状态标志
    is_awake = False

    # 创建一个单独的线程用于处理ROS2的spin
    def spin_ros():
        rclpy.spin(controller)
    
    ros_thread = threading.Thread(target=spin_ros)
    ros_thread.daemon = True
    ros_thread.start()

    try:
        # 打开音频流
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCKSIZE,
            dtype="int16",
            channels=1,
            device=None,
            callback=callback
        ):
            controller.get_logger().info(f"开始监听唤醒词: '{WAKE_WORD}' (拼音: {wake_pinyin})")
            controller.get_logger().info("按 Ctrl+C 停止程序")
            while rclpy.ok():
                data = audio_queue.get()
                
                if recognizer.AcceptWaveform(data):
                    # 获取最终识别结果
                    result_json = recognizer.Result()
                    result_dict = json.loads(result_json)
                    text = result_dict.get("text", "")
                    
                    if text:
                        if not is_awake:
                            # 检查唤醒词
                            text_pinyin = text_to_pinyin(text)
                            similarity = levenshtein_similarity(text_pinyin, wake_pinyin)
                            
                            controller.get_logger().info(f"识别文本: {text}")
                            controller.get_logger().info(f"拼音转换: {text_pinyin}")
                            controller.get_logger().info(f"相似度: {similarity:.2f}")
                            
                            # 检查唤醒条件
                            if similarity >= 0.5:
                                controller.get_logger().info("=== 唤醒成功! ===")
                                controller.get_logger().info("请说出指令：前进、后退、向左、向右、停下")
                                is_awake = True
                        else:
                            # 已唤醒状态，处理指令
                            controller.get_logger().info(f"识别到指令: {text}")
                            execute_command(controller, text)
                            
                else:
                    # 获取部分识别结果
                    partial_json = recognizer.PartialResult()
                    partial_dict = json.loads(partial_json)
                    partial_text = partial_dict.get("partial", "")
                    
                    if partial_text:
                        # 实时显示部分识别结果
                        if is_awake:
                            print(f"\r等待指令: {partial_text}", end='', flush=True)
                        else:
                            print(f"\r监听中: {partial_text}", end='', flush=True)
                        
    except KeyboardInterrupt:
        # 用户手动终止时退出
        controller.get_logger().info("\n程序已停止")
    except Exception as e:
        controller.get_logger().error(f"运行时发生异常：{e}")
    finally:
        # 关闭ROS2节点
        controller.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()