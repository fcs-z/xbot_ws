from setuptools import find_packages, setup
from glob import glob
import os


package_name = 'xbot_voice_communication'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        
        ('share/' + package_name+'/launch',glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools','rclpy',
        'sounddevice',
        'vosk',
        'edge_tts',
        'requests'],
    zip_safe=True,
    maintainer='fcs',
    maintainer_email='11118754+fcsz@user.noreply.gitee.com',
    description='TODO: Package description',
    license='Apache-2.0',
    # tests_require=['pytest'],
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'voice_communication = xbot_voice_communication.voice_communication:main',
        ],
    },
)
