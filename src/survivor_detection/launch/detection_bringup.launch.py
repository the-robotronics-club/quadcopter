"""
detection_bringup.launch.py
=============================

Starts everything needed for survivor detection to work, regardless of
WHAT is publishing the camera feed -- the test rig (detection_test_camera_rig.sdf)
today, or the real drone (once Navigation adds camera_sensor_snippet.sdf to
their model) later. Neither this launch file nor the detection node itself
needs to change when that swap happens -- see INTEGRATION_CONTRACT.md.

Usage:
    ros2 launch survivor_detection detection_bringup.launch.py

    # Run headless (no debug window) for actual mission use:
    ros2 launch survivor_detection detection_bringup.launch.py show_debug_window:=false
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    show_debug_window_arg = DeclareLaunchArgument(
        "show_debug_window", default_value="true",
        description="Show the live detection window (disable for headless/actual mission runs)"
    )

    # Bridges the Gazebo camera topic "cam" (see INTEGRATION_CONTRACT.md)
    # into a standard ROS2 sensor_msgs/Image topic of the same name.
    # This works identically whether "cam" is published by the test rig
    # or by the real drone's camera sensor -- the bridge doesn't care
    # which model the topic came from, only the topic name.
    camera_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="camera_bridge",
        arguments=["/cam@sensor_msgs/msg/Image@gz.msgs.Image"],
        output="screen",
    )

    detection_node = Node(
        package="survivor_detection",
        executable="detection_node",
        name="survivor_detection_node",
        parameters=[{
            "camera_topic": "/cam",
            "show_debug_window": LaunchConfiguration("show_debug_window"),
        }],
        output="screen",
    )

    return LaunchDescription([
        show_debug_window_arg,
        camera_bridge,
        detection_node,
    ])