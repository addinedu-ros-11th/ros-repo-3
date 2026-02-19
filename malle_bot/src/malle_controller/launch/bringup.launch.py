from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='malle_controller',
            executable='bridge_node',
            name='bridge_node',
            output='screen',
            emulate_tty=True,
            parameters=[
                {'use_sim_time': False}
            ]
        )
    ])
