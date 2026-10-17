"""UR5e + Robotiq 2F-85 in Gazebo (gz sim) with ros2_control.

This is the simulation cell for the hand teleop project: the arm runs
forward_position_controller by default so MoveIt Servo can stream Cartesian
twists into it (see servo_sim.launch.py), and the Robotiq gripper is exposed
as a ParallelGripperCommand action.

  ros2 launch arm_bringup sim.launch.py
  ros2 launch arm_bringup sim.launch.py gazebo_gui:=false launch_rviz:=false

Moving the arm without Servo (e.g. for checks):

  ros2 control list_controllers
  ros2 topic pub --once /forward_position_controller/commands \
      std_msgs/msg/Float64MultiArray "{data: [0.0, -1.57, 0.0, -1.57, 0.0, 0.0]}"

Opening/closing the gripper (0.0 = open, 0.8 = closed):

  ros2 action send_goal /robotiq_gripper_controller/gripper_cmd \
      control_msgs/action/ParallelGripperCommand \
      "{command: {name: [robotiq_85_left_knuckle_joint], position: [0.8]}}"

For MoveIt plan-and-execute instead of Servo, switch the arm controller:

  ros2 control switch_controllers --deactivate forward_position_controller \
      --activate scaled_joint_trajectory_controller

Notes for the next reader:
- launch/sim_control.launch.py is a vendored, patched copy of
  ur_simulation_gz's ur_sim_control.launch.py - see its header for the patch.
- GZ_SIM_RESOURCE_PATH gets robotiq_description's share parent directory so
  Gazebo can resolve the adapter's model:// mesh URIs.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    IncludeLaunchDescription,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    ur_type = LaunchConfiguration("ur_type")
    gazebo_gui = LaunchConfiguration("gazebo_gui")
    launch_rviz = LaunchConfiguration("launch_rviz")
    world_file = LaunchConfiguration("world_file")
    initial_joint_controller = LaunchConfiguration("initial_joint_controller")

    declared_arguments = [
        DeclareLaunchArgument("ur_type", default_value="ur5e"),
        DeclareLaunchArgument("gazebo_gui", default_value="true"),
        DeclareLaunchArgument("launch_rviz", default_value="true"),
        DeclareLaunchArgument(
            "world_file",
            default_value="empty.sdf",
            description="Gazebo world (absolute path or a name from the gazebo worlds collection)",
        ),
        DeclareLaunchArgument(
            "initial_joint_controller",
            default_value="forward_position_controller",
            description="Arm controller to activate. Servo streams into "
            "forward_position_controller; use scaled_joint_trajectory_controller "
            "for MoveIt plan-and-execute.",
        ),
    ]

    # Gazebo resolves the Robotiq adapter's meshes as
    # model://robotiq_description/... - point it at the share parent directory.
    gazebo_resource_path = AppendEnvironmentVariable(
        "GZ_SIM_RESOURCE_PATH",
        os.path.dirname(get_package_share_directory("robotiq_description")),
    )

    ur_control = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("arm_bringup"), "launch", "sim_control.launch.py"]
            )
        ),
        launch_arguments={
            "ur_type": ur_type,
            "description_file": PathJoinSubstitution(
                [FindPackageShare("arm_bringup"), "urdf", "ur5e_robotiq_gz.urdf.xacro"]
            ),
            "controllers_file": PathJoinSubstitution(
                [FindPackageShare("arm_bringup"), "config", "arm_controllers.yaml"]
            ),
            "initial_joint_controller": initial_joint_controller,
            "gazebo_gui": gazebo_gui,
            "launch_rviz": launch_rviz,
            "world_file": world_file,
        }.items(),
    )

    gripper_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["robotiq_gripper_controller", "-c", "/controller_manager"],
        output="screen",
    )

    return LaunchDescription(
        declared_arguments
        + [gazebo_resource_path, ur_control, gripper_controller_spawner]
    )
