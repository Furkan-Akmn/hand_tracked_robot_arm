import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    default_model = os.environ.get("HAND_TRACKING_MODEL",
                                   "models/hand_landmarker.task")

    args = [
        DeclareLaunchArgument("camera", default_value="0",
                              description="OpenCV camera index"),
        DeclareLaunchArgument("model_path", default_value=default_model,
                              description="Path to hand_landmarker.task"),
        DeclareLaunchArgument("show_window", default_value="false",
                              description="Open a local OpenCV preview window"),
        DeclareLaunchArgument("debug_image", default_value="true",
                              description="Publish /hand/debug_image"),
        DeclareLaunchArgument("min_cutoff", default_value="1.0",
                              description="One-Euro filter: minimum cutoff [Hz]"),
        DeclareLaunchArgument("beta", default_value="4.0",
                              description="One-Euro filter: speed coefficient"),
    ]

    node = Node(
        package="hand_tracking",
        executable="landmark_node",
        name="hand_tracking",
        output="screen",
        parameters=[{
            "camera": ParameterValue(LaunchConfiguration("camera"), value_type=int),
            "model_path": ParameterValue(LaunchConfiguration("model_path"), value_type=str),
            "show_window": ParameterValue(LaunchConfiguration("show_window"), value_type=bool),
            "debug_image": ParameterValue(LaunchConfiguration("debug_image"), value_type=bool),
            "min_cutoff": ParameterValue(LaunchConfiguration("min_cutoff"), value_type=float),
            "beta": ParameterValue(LaunchConfiguration("beta"), value_type=float),
        }],
    )

    return LaunchDescription(args + [node])
