from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'arm_control'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Launch files
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.py')),
        # Web assets
        (os.path.join('share', package_name, 'web'),
            glob('web/*.html') + glob('web/*.js')),
        (os.path.join('share', package_name, 'web', 'meshes'),
            glob('web/meshes/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Arm Developer',
    maintainer_email='arm@robot.local',
    description='6-DOF arm ROS2 control nodes',
    license='MIT',
    entry_points={
        'console_scripts': [
            'uart_node       = arm_control.uart_node:main',
            'web_server_node = arm_control.web_server_node:main',
            'stm32_encoder_node = arm_control.stm32_encoder_node:main', 
        ],
    },
) 
