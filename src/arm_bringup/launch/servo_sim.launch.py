"""UR5e + Robotiq sim + MoveIt move_group + MoveIt Servo.

MoveIt loads the robot description from the /robot_description topic
(robot_state_publisher of the sim publishes the full UR5e + Robotiq model),
so the planning scene matches what you see in Gazebo.

Servo accepts Cartesian twists on /servo_node/delta_twist_cmds
(geometry_msgs/TwistStamped) and streams joint positions into
/forward_position_controller/commands.

Servo (Jazzy) ignores all input until a command type is selected - there is
no start_servo service any more; otherwise it logs "Command type has not been
set, cannot accept input". Select twist input (1 = TWIST), then stream:

  ros2 service call /servo_node/switch_command_type \
      moveit_msgs/srv/ServoCommandType "{command_type: 1}"
  ros2 topic pub -r 10 /servo_node/delta_twist_cmds \
      geometry_msgs/msg/TwistStamped \
      "{header: {frame_id: tool0}, twist: {linear: {x: 0.05}, angular: {z: 0.2}}}"

Servo stops by itself if no command arrives for `incoming_command_timeout`
(0.1 s in arm_bringup's config/servo_params.yaml).
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
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
            description="Arm controller to activate (Servo streams into "
            "forward_position_controller).",
        ),
    ]

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("arm_bringup"), "launch", "sim.launch.py"]
            )
        ),
        launch_arguments={
            "ur_type": ur_type,
            "gazebo_gui": gazebo_gui,
            "launch_rviz": "false",  # MoveIt brings its own RViz config below
            "world_file": world_file,
            "initial_joint_controller": initial_joint_controller,
        }.items(),
    )

    moveit_servo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("arm_bringup"), "launch", "moveit_servo.launch.py"]
            )
        ),
        launch_arguments={
            "ur_type": ur_type,
            "use_sim_time": "true",
            "launch_rviz": launch_rviz,
            "launch_servo": "true",
        }.items(),
    )

    return LaunchDescription(declared_arguments + [sim, moveit_servo])
