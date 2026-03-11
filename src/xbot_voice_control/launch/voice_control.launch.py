import os 
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions  import PathJoinSubstitution  
from launch.actions import TimerAction

def generate_launch_description():
    
    xbot_description_dir = get_package_share_directory('fishbot_description')
    xbot_voice_control_dir = get_package_share_directory('xbot_voice_control')
    
    world_file = PathJoinSubstitution([xbot_voice_control_dir, 'worlds', 'custom_room.world'])
    
    # 创建跟随节点，并把 camera_fov_deg 设置为 100
    xbot_voice_control = Node(
        package='xbot_voice_control',
        executable='voice_control',
        name='voice_control',
        output='screen',
    )
    
    gazebo_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([xbot_description_dir, '/launch', '/gazebo_simulation.launch.py']),
        launch_arguments={'world': world_file, 'verbose': 'true'}.items()
    )
    
    ld = LaunchDescription()
    # ld.add_action(TimerAction(period=0.0,  actions=[gazebo_cmd]))
    ld.add_action(TimerAction(period=3.0,  actions=[xbot_voice_control]))
    return ld
    
    # return LaunchDescription([
     
    #     gazebo_cmd,                 
    #     xbot_voice_control,
    # ])
