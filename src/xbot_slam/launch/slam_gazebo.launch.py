import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions  import PathJoinSubstitution  

def generate_launch_description():

    xbot_description_dir = get_package_share_directory('fishbot_description')
    xbot_slam_dir = get_package_share_directory('xbot_slam')
    slam_toolbox_dir = get_package_share_directory('slam_toolbox')
    
    world_file = PathJoinSubstitution([xbot_slam_dir, 'worlds', 'custom_room.world'])
    
    # slam算法(1): ros2 run slam_toolbox sync_slam_toolbox_node
    slam_cmd = Node(
        package="slam_toolbox",
        executable="sync_slam_toolbox_node",
        parameters=[{
            "use_sim_time": True,
            "base_frame": "base_footprint",
            "odom_frame": "odom",
            "map_frame": "map"
        }]
    )
    
    # slam算法(2): ros2 launch slam_toolbox online_async_launch.py
    slam_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([slam_toolbox_dir, '/launch', '/online_async_launch.py']),
    )

    # 打开rviz2，并指定要打开的.rviz文件
    rviz2_cmd = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', [os.path.join(get_package_share_directory('nav2_bringup'), 'rviz', 'nav2_default_view.rviz')]]
    )
    
    # 打开gazebo仿真环境
    gazebo_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([xbot_description_dir, '/launch', '/gazebo_simulation.launch.py']),
        launch_arguments={'world': world_file, 'verbose': 'true'}.items()
    )


    ld = LaunchDescription()
    ld.add_action(gazebo_cmd)
    # ld.add_action(slam_cmd)
    ld.add_action(slam_launch_cmd)
    ld.add_action(rviz2_cmd)
    

    return ld