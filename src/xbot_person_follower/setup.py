from setuptools import find_packages, setup
from glob import glob
import os  

package_name = 'xbot_person_follower'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        
        ('share/' + package_name+'/launch',glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='fcs',
    maintainer_email='3433582395@qq.com',
    description='TODO: Package description',
    license='Apache-2.0',
    # tests_require=['pytest'],
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'person_follower = xbot_person_follower.person_follower:main',
        ],
    },
)
