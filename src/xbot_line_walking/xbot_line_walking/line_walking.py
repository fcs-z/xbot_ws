#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
import cv2
import numpy as np
import threading

class RedTrackNode(Node):
    def __init__(self):
        super().__init__('red_track_node')
        
        # 初始化参数
        self.declare_parameter('h_min', 0)
        self.declare_parameter('h_max', 10)
        self.declare_parameter('s_min', 100)
        self.declare_parameter('s_max', 255)
        self.declare_parameter('v_min', 100)
        self.declare_parameter('v_max', 255)
        self.declare_parameter('safe_distance', 0.7)  # 安全距离阈值
        
        # 创建订阅者和发布者
        self.image_sub = self.create_subscription(
            Image,
            '/camera_sensor/image_raw',
            self.image_callback,
            10)
        
        # 添加激光雷达订阅
        self.scan_sub = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10)
        
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # 初始化CV桥接
        self.bridge = CvBridge()
        
        # 初始化HSV阈值
        self.h_min = self.get_parameter('h_min').value
        self.h_max = self.get_parameter('h_max').value
        self.s_min = self.get_parameter('s_min').value
        self.s_max = self.get_parameter('s_max').value
        self.v_min = self.get_parameter('v_min').value
        self.v_max = self.get_parameter('v_max').value
        self.safe_distance = self.get_parameter('safe_distance').value
        
        # 创建显示窗口（调试用）
        cv2.namedWindow("Red Tracking", cv2.WINDOW_NORMAL)
        
        # 障碍物检测标志和距离
        self.obstacle_detected = False
        self.min_distance = float('inf')  # 存储最近障碍物距离[7](@ref)
        self.lock = threading.Lock()  # 线程锁保证数据安全

    def scan_callback(self, msg):
        """激光雷达回调函数，检测前方障碍物"""
        # 获取前方120度范围内的扫描数据（-60度到60度）[1,8](@ref)
        total_ranges = len(msg.ranges)
        # 计算角度范围索引（0°为正前方）
        front_start = int(total_ranges * 300/360)  # -60°位置（300°）
        front_end = int(total_ranges * 60/360)     # +60°位置
        
        # 获取两个区间的数据并合并（跨越0°的扇形区域）[7](@ref)
        front_ranges = msg.ranges[front_start:] + msg.ranges[:front_end]
        
        # 过滤无效值并找到最小距离
        valid_ranges = [r for r in front_ranges if not np.isnan(r) and r > msg.range_min]
        min_distance = min(valid_ranges) if valid_ranges else float('inf')
        
        # 更新障碍物状态和距离（使用线程锁保证数据一致性）
        with self.lock:
            self.obstacle_detected = min_distance < self.safe_distance
            self.min_distance = min_distance
            
            # 打印最近障碍物距离
            self.get_logger().info(f'[-60°~60°] 最近障碍物距离: {min_distance:.2f}m')
    def image_callback(self, msg):
        try:
            # 转换图像格式
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            self.get_logger().error(f'图像转换错误: {e}')
            return

        # 颜色过滤（红色有两个范围）
        hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, self.s_min, self.v_min])
        upper_red1 = np.array([10, self.s_max, self.v_max])
        lower_red2 = np.array([170, self.s_min, self.v_min])
        upper_red2 = np.array([180, self.s_max, self.v_max])
        
        # 创建掩膜
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)

        # # 形态学操作去噪
        # kernel = np.ones((3,3), np.uint8)
        # mask = cv2.erode(mask, kernel, iterations=1)
        # mask = cv2.dilate(mask, kernel, iterations=2)

        # 寻找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        twist = Twist()  # 初始化速度命令
        
        if len(contours) > 0:
            # 找到最大轮廓
            max_contour = max(contours, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(max_contour)
            
            if radius > 50:  # 过滤小区域
                # 绘制跟踪结果
                cv2.circle(cv_image, (int(x), int(y)), int(radius), (0, 255, 255), 2)
                
                # 计算控制指令（简单比例控制）
                error = x - cv_image.shape[1]/2
                kp = 0.001  # 比例系数
                
                twist.linear.x = 0.05  # 前进速度
                twist.angular.z = -float(error) * kp  # 转向速度
        
        # 检查障碍物状态并显示距离信息
        with self.lock:
            # 在图像上显示最近障碍物距离[5](@ref)
            dist_text = f"Min Dist: {self.min_distance:.2f}m"
            cv2.putText(cv_image, dist_text, (50, 120), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            if self.obstacle_detected:
                # 障碍物在安全距离内，停止运动
                twist.linear.x = 0.0
                twist.angular.z = 0.0
                cv2.putText(cv_image, "OBSTACLE DETECTED!", (50, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # 发布速度命令
        # self.cmd_pub.publish(twist)
        
        # 显示调试图像
        cv2.imshow("Red", mask)
        cv2.imshow("Red Tracking", cv_image)
        cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = RedTrackNode()
    rclpy.spin(node)
    
    # 销毁节点
    node.destroy_node()
    rclpy.shutdown()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()