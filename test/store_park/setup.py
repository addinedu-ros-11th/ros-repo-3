from setuptools import setup
from glob import glob
import os

package_name = 'store_park'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        # 패키지 인덱스 등록
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        # package.xml 등록
        ('share/' + package_name, ['package.xml']),
        # configs/stores.json 등록
        ('share/' + package_name + '/configs',
            glob('configs/*.json')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='mj',
    maintainer_email='mj@todo.todo',
    description='store_park navigation package',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # ↓ main_park Node 등록
            'main_park = store_park.main_park:main',
        ],
    },
)