import os
from setuptools import find_packages, setup
from glob import glob

package_name = 'wall_following'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), 
         glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
        (os.path.join('share', package_name, 'config'),
         glob(os.path.join('config', '*.yaml'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Eneko Ruiz, Eneko Pardavila, Omar Ouinas',
    maintainer_email='eruiz@ikasle.ehu.eus',
    description='Wall following controller using LiDAR regression and PID',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'wall_follow_ls = wall_following.wall_follow_ls:main'
        ],
    },
)
