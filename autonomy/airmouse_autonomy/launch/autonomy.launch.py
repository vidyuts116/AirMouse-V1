from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # Priority 1: TF2 Tree
        Node(package='airmouse_autonomy', executable='static_transforms_node', name='static_transforms_node'),
        
        # Priority 2: Safety Bridge
        Node(package='airmouse_autonomy', executable='offboard_bridge_node', name='offboard_bridge_node'),
        
        # Priority 3: Perception
        Node(package='airmouse_autonomy', executable='perception_filter_node', name='perception_filter_node'),
        
        # Priority 4: Mapping
        Node(package='airmouse_autonomy', executable='slam_mapping_node', name='slam_mapping_node'),
        
        # Priority 5: Local Planner
        Node(package='airmouse_autonomy', executable='local_trajectory_node', name='local_trajectory_node'),
        
        # Priority 6: Mission Executive
        Node(package='airmouse_autonomy', executable='mission_executive_node', name='mission_executive_node')
    ])
