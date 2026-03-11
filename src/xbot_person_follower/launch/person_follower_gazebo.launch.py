import os 
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions  import PathJoinSubstitution  

def generate_launch_description():
    
    xbot_description_dir = get_package_share_directory('fishbot_description')
    xbot_person_follower_dir = get_package_share_directory('xbot_person_follower')
    
    world_file = PathJoinSubstitution([xbot_person_follower_dir, 'worlds', 'test.world'])
    
    # 创建跟随节点，并把 camera_fov_deg 设置为 100
    xbot_person_follower = Node(
        package='xbot_person_follower',
        executable='person_follower',
        name='person_follower',
        output='screen',
        parameters=[{
            'desired_distance': 1.0,      # 跟随距离 1m
            'max_linear_speed': 0.25,     # 最大线速度
            'max_angular_speed': 0.8,     # 最大角速度
            'use_lidar': True,            # 使用激光雷达
            'debug_view': True,           # 调试视图
            'camera_fov_deg': 100.0,      # 摄像头视野改为 100 度
            'obstacle_distance': 0.5      # 障碍物检测距离
        }]
    )
    
    world_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([xbot_person_follower_dir, '/launch', '/world.launch.py']),
    )
    
    gazebo_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([xbot_description_dir, '/launch', '/gazebo_simulation.launch.py']),
        launch_arguments={'world': world_file, 'verbose': 'true'}.items()
    )
    
    
    return LaunchDescription([
        # 自定义世界
        # world_cmd,      
        
        gazebo_cmd,                 
        xbot_person_follower,
    ])
