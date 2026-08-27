import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():

    package_path = get_package_share_directory(
        'destruction_scenarios'
    )

    ros_gz_sim_path = get_package_share_directory(
        'ros_gz_sim'
    )

    world_path = os.path.join(
        package_path,
        'worlds',
        'house_hard_ignition.world'
    )

    worlds_path = os.path.join(
        package_path,
        'worlds'
    )

    gz_launch = os.path.join(
        ros_gz_sim_path,
        'launch',
        'gz_sim.launch.py'
    )

    return LaunchDescription([
        SetEnvironmentVariable(
            name='IGN_GAZEBO_RESOURCE_PATH',
            value=worlds_path
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gz_launch),
            launch_arguments={
                'gz_args': f'-r {world_path}'
            }.items()
        )
    ])
