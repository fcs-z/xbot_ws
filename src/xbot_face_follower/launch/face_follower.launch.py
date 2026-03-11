import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions  import PathJoinSubstitution  

def generate_launch_description():

    xbot_description_dir = get_package_share_directory('fishbot_description')
    xbot_face_follower_dir = get_package_share_directory('xbot_face_follower')
    
    world_file = PathJoinSubstitution([xbot_face_follower_dir, 'worlds', 'custom_room.world'])
    
    # USB摄像头节点配置
    usb_camera_cmd = Node(
        package='xbot_face_follower',  # 使用你的包名
        executable='usb_camera_node',  # 可执行文件名
        name='usb_camera_node',
        output='screen',
        parameters=[
            {'camera_frame_id': 'camera_link'},  # 设置相机坐标系名称
            {'device_id': 0},  # 摄像头设备ID，默认为0
            {'frame_width': 640},  # 图像宽度
            {'frame_height': 480},  # 图像高度
            {'fps': 30.0}  # 帧率
        ]
    )

    # 人物跟随节点配置
    person_follower_cmd = Node(
        package='xbot_face_follower',
        executable='face_follower',
        name='person_follower',
        output='screen',
        parameters=[
            {'image_topic': '/camera/image_raw'},  # 确保图像主题匹配
            {'camera_info_topic': '/camera/camera_info'},  # 相机信息主题
            {'cmd_vel_topic': '/cmd_vel'}  # 速度命令主题
        ]
    )
    
    gazebo_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([xbot_description_dir, '/launch', '/gazebo_simulation.launch.py']),
        launch_arguments={'world': world_file, 'verbose': 'true'}.items()
    )

    ld = LaunchDescription()
    # ld.add_action(gazebo_cmd)          
    ld.add_action(usb_camera_cmd)        
    ld.add_action(person_follower_cmd)   

    return ld
