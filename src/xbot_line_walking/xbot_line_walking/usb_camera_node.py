#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class USBCameraNode(Node):
    def __init__(self):
        super().__init__('usb_camera_node')
        # 初始化摄像头（设备号默认为 /dev/video0）
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.get_logger().error("无法打开摄像头！检查设备连接或权限")
            raise RuntimeError("摄像头初始化失败")
        
        # 设置摄像头参数（可选）
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # 创建图像发布者和 OpenCV 桥接
        self.publisher = self.create_publisher(Image,'/camera_sensor/image_raw', 10)
        self.bridge = CvBridge()
        
        # 定时器（30 FPS）
        self.timer = self.create_timer(0.033, self.timer_callback)
        self.get_logger().info("USB 摄像头节点已启动")

    def timer_callback(self):
        ret, frame = self.cap.read()
        if ret:
            try:
                # 转换为 ROS2 图像消息并发布
                ros_image = self.bridge.cv2_to_imgmsg(frame, "bgr8")
                ros_image.header.stamp = self.get_clock().now().to_msg()
                ros_image.header.frame_id = "camera_frame"
                self.publisher.publish(ros_image)
                
                # 本地显示（可选）
                cv2.imshow("Camera Feed", frame)
                cv2.waitKey(1)
            except Exception as e:
                self.get_logger().error(f"图像转换失败: {str(e)}")
        else:
            self.get_logger().warning("摄像头读取失败")

    def __del__(self):
        self.cap.release()
        cv2.destroyAllWindows()

def main(args=None):
    rclpy.init(args=args)
    node = USBCameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()