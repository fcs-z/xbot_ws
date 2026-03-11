import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge
import cv2
import numpy as np
import math

class FollowNode(Node):
    def __init__(self):
        super().__init__('follow_node')
        # 初始化CvBridge，用于在ROS图像消息与OpenCV图像之间转换
        self.bridge = CvBridge()

        # 订阅相机图像（/camera/image_raw）和激光雷达扫描数据（/scan）
        # ROS2中通过create_subscription创建订阅者:contentReference[oaicite:8]{index=8}:contentReference[oaicite:9]{index=9}
        self.image_sub = self.create_subscription(Image, '/camera/image_raw', self.image_callback, 10)
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)

        # 发布机器人速度命令到 /cmd_vel
        # 通过create_publisher创建Twist类型的发布者:contentReference[oaicite:10]{index=10}
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # HOG 行人检测器初始化
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

        # 目标相关状态
        self.target_box = None    # 当前目标的矩形框 (x, y, w, h)
        self.target_lost = False  # 目标是否丢失标志
        self.locked = False       # 是否已锁定目标
        # 激光雷达最新数据
        self.latest_scan = None

    def image_callback(self, msg):
        # 图像回调：接收Camera图像并检测/跟踪目标
        try:
            # 将ROS图像消息转为OpenCV图像（BGR格式）:contentReference[oaicite:11]{index=11}
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f"图像转换失败: {e}")
            return

        # 转为灰度图像提高检测速度
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

        # 使用HOG检测行人:contentReference[oaicite:12]{index=12}
        rects, weights = self.hog.detectMultiScale(gray, winStride=(8,8), padding=(8,8), scale=1.05)
        detections = []
        for i, (x, y, w, h) in enumerate(rects):
            # 根据检测权重过滤低置信度的结果（可选）
            if weights[i] < 0.5:
                continue
            # 保存检测到的行人框 (x, y, w, h)
            detections.append((x, y, w, h))

        target_box = self.target_box

        if not self.locked:
            # 如果还未锁定目标，选择最近（最大检测框面积）的行人作为目标
            if detections:
                # 计算每个检测框的面积并选取最大面积的目标
                areas = [w*h for (x, y, w, h) in detections]
                max_idx = int(np.argmax(areas))
                target_box = detections[max_idx]
                self.locked = True
                self.target_lost = False
            else:
                # 未检测到目标，保持等待状态
                target_box = None
        else:
            # 已锁定目标，尝试更新目标框，忽略新出现的行人
            if detections and target_box is not None:
                # 计算当前目标框与各检测框的IOU，选择最佳匹配继续跟踪
                best_iou = 0.0
                best_box = None
                x0, y0, w0, h0 = target_box
                for (x, y, w, h) in detections:
                    # 计算IOU
                    xi1 = max(x0, x)
                    yi1 = max(y0, y)
                    xi2 = min(x0+w0, x+w)
                    yi2 = min(y0+h0, y+h)
                    inter_w = max(0, xi2 - xi1)
                    inter_h = max(0, yi2 - yi1)
                    inter_area = inter_w * inter_h
                    union_area = w0*h0 + w*h - inter_area
                    iou = inter_area / union_area if union_area > 0 else 0
                    if iou > best_iou:
                        best_iou = iou
                        best_box = (x, y, w, h)
                # 如果新的检测与之前目标有较高重叠，则更新目标，否则视为目标丢失
                if best_iou > 0.5 and best_box is not None:
                    target_box = best_box
                    self.target_lost = False
                else:
                    # 目标丢失，停止移动并切换到搜索状态
                    self.target_box = None
                    self.locked = False
                    self.target_lost = True
                    target_box = None
            else:
                # 没有检测到任何行人，也视为目标丢失
                self.target_box = None
                self.locked = False
                self.target_lost = True
                target_box = None

        # 更新当前目标框
        self.target_box = target_box

        # 初始化控制命令
        cmd = Twist()
        cmd.linear.x = 0.0
        cmd.angular.z = 0.0

        # 如果锁定目标，则计算距离和运动控制
        if target_box is not None:
            x, y, w, h = target_box
            # 计算目标中心在图像中的水平角度偏差（假设相机水平视场角为60度）
            img_h, img_w = gray.shape
            center_x = x + w/2.0
            # 角度偏差（弧度），HFOV假设60度
            HFOV = math.radians(60.0)
            angle_offset = (center_x - img_w/2) * HFOV / img_w

            distance = None
            # 优先使用激光雷达测距
            if self.latest_scan is not None:
                scan = self.latest_scan
                # 将角度转换为索引
                # LaserScan 0角为前方，逆时针为正方向:contentReference[oaicite:13]{index=13}
                angle = angle_offset
                if scan.angle_min <= angle <= scan.angle_max and scan.angle_increment != 0:
                    index = int((angle - scan.angle_min) / scan.angle_increment)
                    if 0 <= index < len(scan.ranges):
                        d = scan.ranges[index]
                        # 如果激光数据有效，使用该距离
                        if not math.isinf(d) and d >= scan.range_min and d <= scan.range_max:
                            distance = d
            # 如果激光测距无效，则使用图像中人的高度进行估算
            if distance is None:
                # 假设实际身高约1.7米，使用针孔相机模型估算距离
                VFOV = math.radians(45.0)  # 假设垂直视场角45度
                focal_length = img_h / (2 * math.tan(VFOV/2))
                real_person_height = 1.7  # 假定平均身高为1.7米
                distance = (real_person_height * focal_length) / h

            # 根据距离决定前进或停止（>1米前进，否则停止）
            if distance > 1.0:
                cmd.linear.x = 0.2  # 向前速度（可根据需求调整）
            else:
                cmd.linear.x = 0.0

            # 计算转向指令，使机器人朝向目标中心
            cmd.angular.z = -0.002 * (center_x - img_w/2)

            # 简单避障：检查前方±30度范围内的最近距离
            if self.latest_scan is not None:
                scan = self.latest_scan
                start_angle = -math.radians(30)
                end_angle = math.radians(30)
                start_idx = int((start_angle - scan.angle_min) / scan.angle_increment)
                end_idx = int((end_angle - scan.angle_min) / scan.angle_increment)
                start_idx = max(0, start_idx)
                end_idx = min(len(scan.ranges)-1, end_idx)
                if start_idx < end_idx:
                    segment = [r for r in scan.ranges[start_idx:end_idx+1] if not math.isinf(r)]
                    if segment:
                        min_dist = min(segment)
                        # 如果最近障碍物小于阈值，则停止前进:contentReference[oaicite:14]{index=14}
                        if min_dist < 0.5:
                            cmd.linear.x = 0.0
        else:
            # 未锁定目标时，停止运动
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0

        # 发布速度指令
        self.cmd_pub.publish(cmd)

        # 可视化调试信息：在图像中绘制目标框并显示状态和距离
        display = cv_image.copy()
        if target_box is not None:
            x, y, w, h = target_box
            cv2.rectangle(display, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(display, f"目标", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 
                        0.5, (0, 255, 0), 1)
        status_text = "跟踪目标" if self.locked else ("搜索目标" if self.target_lost else "等待目标")
        cv2.putText(display, f"状态: {status_text}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 
                    0.6, (255, 255, 255), 2)
        if target_box is not None and distance is not None:
            cv2.putText(display, f"距离: {distance:.2f} m", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 
                        0.6, (255, 255, 255), 2)

        cv2.imshow("Follow Debug", display)
        cv2.waitKey(1)

    def scan_callback(self, msg):
        # 激光雷达数据回调：存储最新的扫描信息
        self.latest_scan = msg

def main(args=None):
    rclpy.init(args=args)
    node = FollowNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
