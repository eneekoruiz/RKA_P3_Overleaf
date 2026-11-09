# -*- coding: utf-8 -*-
"""
wall_follow_ls nodoa abiarazten du. Parametro guztiak komando-lerrotik alda daitezke:

    ros2 launch wall_following wf_ls.launch.py kp:=2.0 ki:=0.05 kd:=0.1 v0:=0.2 kv:=0.0 d_max:=1.2
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

# Parametroen izenak eta balio lehenetsiak
ARGUMENTUAK = {
    'kp': '1.5',    # Irabazi proportzionala
    'ki': '0.0',    # Irabazi integrala
    'kd': '0.0',    # Irabazi deribatiboa
    'v0': '0.2',    # Oinarrizko abiadura lineala (m/s)
    'kv': '0.0',    # Biraketetan moteltzeko irabazia (0: abiadura konstantea)
    'd_max': '1.2', # Irakurketa motzen muga (m); robotaren paretarako distantzia finkatzen du
}


def generate_launch_description():
    # value_type=float: horrela "kp:=1" bezalako balio osoek ere balio dute
    parametroak = {izena: ParameterValue(LaunchConfiguration(izena), value_type=float)
                   for izena in ARGUMENTUAK}
    parametroak['lidar_type'] = 's2'    # Aukerak: a1, s2, turtle

    wall_following_node = Node(
        package='wall_following',
        executable='wall_follow_ls',
        name='wall_follow_ls',
        parameters=[parametroak],
        output='screen',
    )

    return LaunchDescription(
        [DeclareLaunchArgument(izena, default_value=balioa)
         for izena, balioa in ARGUMENTUAK.items()] + [wall_following_node]
    )
