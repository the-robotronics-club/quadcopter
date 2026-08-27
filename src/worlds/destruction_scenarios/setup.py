from setuptools import setup
import os
from glob import glob

package_name = 'destruction_scenarios'

setup(
    name=package_name,
    version='1.0.0',
    packages=[],
    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name]
        ),
        (
            'share/' + package_name,
            ['package.xml']
        ),
        (
            os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')
        ),
        (
            os.path.join('share', package_name, 'worlds'),
            glob('worlds/*.world')
        ),
        (
            os.path.join('share', package_name, 'worlds', 'house'),
            glob('worlds/house/*')
        ),
        (
            os.path.join('share', package_name, 'worlds', 'garage'),
            glob('worlds/garage/*')
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
)
