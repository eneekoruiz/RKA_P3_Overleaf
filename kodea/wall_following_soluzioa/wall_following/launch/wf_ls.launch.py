import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import TextSubstitution, LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch_ros.actions import Node
import os


def generate_launch_description():
    kp_arg = DeclareLaunchArgument(
        "kp", default_value=TextSubstitution(text="1.5")
    )
    ki_arg = DeclareLaunchArgument(
        "ki", default_value=TextSubstitution(text="0.0")
    )
    kd_arg = DeclareLaunchArgument(
        "kd", default_value=TextSubstitution(text="0.0")
    )

    wall_following_node = Node(
        package="wall_following",
		executable="wall_follow_ls",
        name='wall_follow_ls',
		parameters = [
            {"kp": LaunchConfiguration('kp')},
            {"ki": LaunchConfiguration('ki')},
            {"kd": LaunchConfiguration('kd')},
            {"lidar_type": "s2"}, # Options: a1, s2, turtle
            ],
        output = "screen"
    )

    return LaunchDescription([
        kp_arg,
        ki_arg,
        kd_arg, 
        wall_following_node,
    ])