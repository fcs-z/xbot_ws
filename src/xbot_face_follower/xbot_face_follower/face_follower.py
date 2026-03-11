#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo, LaserScan
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge
import cv2
import numpy as np
import time
from rclpy.qos import qos_profile_sensor_data

class PersonFollower(Node):
    def __init__(self):
        super().__init__('person_follower')
        
        # 创建图像订阅者（使用传感器数据QoS）
        self.image_sub = self.create_subscription(
            Image,
            'camera/image_raw',
            self.image_callback,
            qos_profile_sensor_data)
        
        # 创建激光雷达订阅者
        self.scan_sub = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10)
        
        # 创建速度发布者
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # 用于图像转换的CV Bridge
        self.bridge = CvBridge()
        
        # 创建内置的LBP人脸检测器
        self.face_cascade = cv2.CascadeClassifier()
        if not self.face_cascade.load('/usr/share/opencv4/haarcascades/haarcascade_frontalface_alt2.xml'):
            self.get_logger().error("Failed to load face detector")
        else:
            self.get_logger().info("Loaded face detector")
        
        # 跟踪状态
        self.target_detected = False
        self.last_detection_time = 0
        self.searching_direction = 1  # 1: 顺时针, -1: 逆时针
        self.searching_state = 0      # 0: 旋转, 1: 完成360度
        
        # 控制参数
        self.center_threshold = 0.1       # 图像中心区域阈值
        self.following_distance = 0.7     # 期望跟随距离（米）
        self.linear_speed_scale = 0.3     # 线速度比例
        self.angular_speed_scale = 1.0    # 角速度比例
        self.max_linear_speed = 0.1       # 最大线速度
        self.max_angular_speed = 0.8      # 最大角速度
        self.search_rotation_speed = 0.1  # 搜索旋转速度
        self.search_angle = 360           # 每次搜索旋转角度
        self.current_search_angle = 0     # 当前已旋转角度
        self.last_search_time = time.time()
        
        # 目标跟踪信息
        self.target_history = []
        self.max_history_length = 10
        
        # 雷达数据
        self.obstacle_detected = False
        self.min_obstacle_distance = float('inf')
        self.safety_distance = 0.7        # 安全距离（米）
        
        self.get_logger().info('Person follower node initialized')

    def scan_callback(self, msg):
        """处理激光雷达数据"""
        # 获取前方区域的扫描数据（正前方±30度）
        front_angle_start = int(len(msg.ranges) * 0.25)  # 前方-30度
        front_angle_end = int(len(msg.ranges) * 0.75)    # 前方+30度
        
        # 提取前方区域的扫描距离
        front_ranges = msg.ranges[front_angle_start:front_angle_end]
        
        # 过滤无效值（0.0或NaN）
        valid_ranges = [r for r in front_ranges if not (np.isnan(r) or np.isinf(r))]
        
        # 找到最小距离
        if valid_ranges:
            self.min_obstacle_distance = min(valid_ranges)
            self.obstacle_detected = self.min_obstacle_distance < self.safety_distance
        else:
            self.min_obstacle_distance = float('inf')
            self.obstacle_detected = False

    def image_callback(self, msg):
        """处理图像消息，检测目标并生成控制指令"""
        try:
            # 将ROS图像消息转换为OpenCV格式
            cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            
            # 检测图像中的人脸
            face_detected, target_center, _, bbox = self.detect_face(cv_image)
            
            # 更新跟踪状态
            if face_detected:
                self.target_detected = True
                self.last_detection_time = time.time()
                self.current_search_angle = 0  # 重置搜索角度
                self.searching_state = 0       # 重置搜索状态
                self.target_history.append(target_center)
                if len(self.target_history) > self.max_history_length:
                    self.target_history.pop(0)
                
                self.get_logger().info(f"Face detected - Center: {target_center}")
                
                # 计算控制指令
                cmd = self.calculate_control(target_center, cv_image.shape)
            else:
                # 如果一段时间内未检测到目标，则开始搜索
                if time.time() - self.last_detection_time > 1.5:
                    self.target_detected = False
                    self.get_logger().info(f"Searching for face... Current angle: {self.current_search_angle:.1f}/{self.search_angle}")
                    cmd = self.create_search_command()
                else:
                    # 短暂丢失目标时，保持当前位置
                    cmd = Twist()
            
            # 应用安全限制（基于雷达）
            cmd = self.apply_safety_limits(cmd)
            
            # 发布控制指令
            self.cmd_pub.publish(cmd)
            
            # 可视化结果
            self.visualize_results(cv_image, face_detected, target_center, bbox)
            
        except Exception as e:
            self.get_logger().error(f"Error processing image: {str(e)}")

    def detect_face(self, image):
        """使用Haar级联分类器检测人脸"""
        # 转换为灰度图像以提高检测效率
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 使用Haar分类器检测人脸
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,      # 图像缩放比例
            minNeighbors=5,        # 检测框合并的最小邻居数
            minSize=(50, 50),      # 最小检测尺寸
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        if len(faces) > 0:
            # 选择最大的人脸作为目标
            largest_face = max(faces, key=lambda x: x[2] * x[3])
            x, y, w, h = largest_face
            
            # 计算目标中心
            target_center = (x + w//2, y + h//2)
            
            return True, target_center, w, (x, y, w, h)
        else:
            return False, (0, 0), 0, None

    def calculate_control(self, target_center, image_shape):
        """根据目标位置计算控制指令（不考虑距离）"""
        cmd = Twist()
        
        # 获取图像中心
        image_height, image_width = image_shape[:2]
        image_center_x = image_width // 2
        
        # 计算目标在图像中的相对位置
        target_x_rel = (target_center[0] - image_center_x) / image_center_x
        
        # 横向误差（目标是否在图像中心）
        lateral_error = target_x_rel
        
        # 根据横向误差计算角速度
        if abs(lateral_error) > self.center_threshold:
            cmd.angular.z = -lateral_error * self.angular_speed_scale
            # 限制最大旋转速度
            cmd.angular.z = max(-self.max_angular_speed, min(self.max_angular_speed, cmd.angular.z))
        else:
            cmd.angular.z = 0.0
        
        # 线速度控制 - 基于雷达避障，而不是目标距离
        # 这里只设置角速度，线速度将在apply_safety_limits中设置
        
        return cmd

    def apply_safety_limits(self, cmd):
        """应用安全限制（基于雷达数据）"""
        # 如果有障碍物在安全距离内
        if self.obstacle_detected:
            # 如果障碍物很近，停止并可能后退
            if self.min_obstacle_distance < self.safety_distance * 0.8:
                cmd.linear.x = 0.0  # 缓慢后退
                self.get_logger().warn(f"Obstacle too close ({self.min_obstacle_distance:.2f}m)! Backing up")
            else:
                cmd.linear.x = 0.0  # 停止前进
                self.get_logger().info(f"Obstacle detected at {self.min_obstacle_distance:.2f}m, stopping")
        else:
            # 没有障碍物时，根据是否检测到目标设置线速度
            if self.target_detected:
                # 检测到目标且没有障碍物，以固定速度前进
                cmd.linear.x = self.max_linear_speed
            else:
                # 没有检测到目标，只旋转不前进
                cmd.linear.x = 0.0
        
        return cmd

    def create_search_command(self):
        """创建搜索指令（360度旋转）"""
        cmd = Twist()
        current_time = time.time()
        
        if self.searching_state == 0:  # 旋转状态
            # 计算从上次调用到现在的时间差和旋转角度
            dt = current_time - self.last_search_time
            self.last_search_time = current_time
            
            # 根据时间和速度计算旋转角度（rad转度）
            angle_increment = abs(self.search_rotation_speed * dt) * (180.0 / np.pi)
            self.current_search_angle += angle_increment
            
            cmd.angular.z = self.search_rotation_speed * self.searching_direction
            
            # 检查是否达到360度
            if self.current_search_angle >= self.search_angle:
                self.current_search_angle = 0  # 重置角度
                self.searching_direction *= -1  # 切换方向下次搜索反向旋转
                self.searching_state = 1       # 标记为完成一次360度搜索
                self.get_logger().info("Completed 360 degree search, switching direction")
                
        elif self.searching_state == 1:  # 完成360度搜索状态
            # 短暂暂停后继续搜索
            if current_time - self.last_search_time > 0.5:
                self.searching_state = 0  # 切换回旋转状态
                self.last_search_time = current_time
                self.get_logger().info("Resuming search rotation...")
        
        return cmd

    def visualize_results(self, image, face_detected, target_center, bbox):
        """可视化检测结果"""
        # 绘制图像中心参考线
        height, width = image.shape[:2]
        cv2.line(image, (width//2, 0), (width//2, height), (0, 0, 255), 2)
        
        if face_detected:
            # 绘制人脸边界框
            x, y, w, h = bbox
            cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # 绘制目标中心
            cv2.circle(image, target_center, 5, (0, 0, 255), -1)
            
            # 绘制跟踪轨迹
            if len(self.target_history) > 1:
                for i in range(1, len(self.target_history)):
                    cv2.line(image, self.target_history[i-1], self.target_history[i], (255, 0, 0), 2)
        
        # 添加状态文本
        if face_detected:
            status_text = "Tracking"
            status_color = (0, 255, 0)
        else:
            status_text = f"Searching - Angle: {self.current_search_angle:.1f}/{self.search_angle}"
            status_color = (0, 0, 255)
            
        cv2.putText(image, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)
        
        # 显示雷达距离信息
        dist_text = f"Obstacle: {self.min_obstacle_distance:.2f}m"
        cv2.putText(image, dist_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        # 显示当前速度
        speed_text = f"Speed: {self.max_linear_speed:.1f}m/s, Rot: {self.search_rotation_speed:.1f}rad/s"
        cv2.putText(image, speed_text, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        # 显示图像
        cv2.imshow('Face Follower', image)
        cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    person_follower = PersonFollower()
    rclpy.spin(person_follower)
    person_follower.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
