import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.actions import GroupAction
from launch.actions import TimerAction
from launch.actions import DeclareLaunchArgument
from launch.substitutions  import PathJoinSubstitution  

def generate_launch_description():
    
    # navigation2
    xbot_description_dir = get_package_share_directory('fishbot_description')
    xbot_navigation2_dir = get_package_share_directory('xbot_navigation2')
    
    # nav2_bringup
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    
    # rviz2
    # rviz2_dir = os.path.join(nav2_bringup_dir, 'rviz', 'nav2_default_view.rviz')
    # 导航时保存的rviz2
    rviz2_dir = os.path.join(xbot_navigation2_dir, 'rviz', 'navigation_test.rviz')              
    
    # map   
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    # 建图保存的地图
    map_file = LaunchConfiguration('map', default=os.path.join(xbot_navigation2_dir, 'maps', 'map_test.yaml'))   
    
    # config
    nav2_params_file = LaunchConfiguration('params_file', default=os.path.join(xbot_navigation2_dir, 'config', 'nav2_params.yaml'))
    
    # world
    world_file = PathJoinSubstitution([xbot_navigation2_dir, 'worlds', 'custom_room.world'])

    # ros2 launch nav2_bringup bringup_launch.py
    navigation2_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([nav2_bringup_dir, '/launch', '/bringup_launch.py']),
        launch_arguments={
            'map': map_file,
            'use_sim_time': use_sim_time,
            'params_file': nav2_params_file}.items(),
    )
    
    # 打开rviz2
    rviz2_cmd = Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz2_dir],
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen',
    )
    
    # 打开gazebo仿真环境
    gazebo_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([xbot_description_dir, '/launch', '/gazebo_simulation.launch.py']),
        launch_arguments={'world': world_file, 'verbose': 'true'}.items()
    )
    
    
    ld = LaunchDescription()
    
    # 这些 LaunchConfiguration 对象在没有 DeclareLaunchArgument 的情况下：
    # 不会被注册到ROS 2参数系统
    # 无法正确解析为实际值
    # 当传递给其他launch文件时，可能变为空值
    ld.add_action(DeclareLaunchArgument('use_sim_time', default_value=use_sim_time, description='Use simulation (Gazebo) clock if true')),
    ld.add_action(DeclareLaunchArgument('map', default_value=map_file, description='Full path to map file to load')),
    ld.add_action(DeclareLaunchArgument('params_file', default_value=nav2_params_file, description='Full path to param file to load')),
    
    ld.add_action(TimerAction(period=0.0,  actions=[gazebo_cmd]))   
    ld.add_action(TimerAction(period=2.0,  actions=[navigation2_cmd]))
    ld.add_action(TimerAction(period=3.0,  actions=[rviz2_cmd]))
    
    return ld