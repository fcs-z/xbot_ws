import os 
from ament_index_python.packages  import get_package_share_directory 
from launch import LaunchDescription 
from launch.actions  import ExecuteProcess, IncludeLaunchDescription 
from launch.launch_description_sources  import PythonLaunchDescriptionSource 
from launch_ros.actions  import Node 
from launch.substitutions  import PathJoinSubstitution  
 
def generate_launch_description():
    
    xbot_description_dir = get_package_share_directory('fishbot_description')
    xbot_line_walking_dir = get_package_share_directory('xbot_line_walking')

    # world_file = PathJoinSubstitution([xbot_line_walking_dir, 'worlds', 'custom_room.world'])
    world_file = PathJoinSubstitution([xbot_line_walking_dir, 'worlds', 'test.world'])
    
    gazebo_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([xbot_description_dir, '/launch', '/gazebo_simulation.launch.py']),
        launch_arguments={'world': world_file, 'verbose': 'true'}.items()
    )
    
    usb_camera_cmd = Node(
        package='xbot_line_walking',  
        executable='usb_camera_node',  
        name='usb_camera_node',
    )
    
    line_walking_cmd = Node(
        package='xbot_line_walking',
        executable='line_walking',
        output='screen',
        name='line_walking',
    )
    
    
    return LaunchDescription([     
        # gazebo_cmd,   
        usb_camera_cmd,    
        line_walking_cmd,        
    ])