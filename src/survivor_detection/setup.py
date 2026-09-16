from setuptools import setup
import os
from glob import glob
from setuptools import setup
package_name = 'survivor_detection'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.sdf')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Ishan Choudhary',
    maintainer_email='123ishanchoudharystudent@gmail.com',
    description='Survivor detection for NIDAR AirMouse (YOLO11 on ONNX, GPS-denied search)',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'detection_node = survivor_detection.survivor_detection_node:main',
        ],
    },
)