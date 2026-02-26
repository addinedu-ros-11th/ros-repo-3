from setuptools import find_packages, setup

package_name = 'malle_controller'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='hyo',
    maintainer_email='hyoinyang02@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'mission_executor = malle_controller.mission_executor:main',
            'bridge_node       = malle_controller.bridge_node:main',

            'mission_guide     = malle_controller.mission_guide:main',
            'mission_follow    = malle_controller.mission_follow:main',
            'mission_errand    = malle_controller.mission_errand:main',

            'tag_tracker       = malle_controller.tag_tracker:main',
            'lockbox_controller= malle_controller.lockbox_controller:main',
            'battery_monitor   = malle_controller.battery_monitor:main',
            'topic_relay       = malle_controller.topic_relay:main',
        ],
    },
)
