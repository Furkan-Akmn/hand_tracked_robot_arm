#!/usr/bin/env python3
"""Publish stamped TwistStamped commands to MoveIt Servo.

Why this exists: MoveIt Servo (Jazzy) drops a twist as stale when

    now - msg.header.stamp >= incoming_command_timeout

(0.1 s in arm_bringup/config/servo_params.yaml). `ros2 topic pub` leaves the
header stamp at zero, so every twist is instantly stale and Servo silently
ignores it (it just halts). This helper stamps each message with the current
time - sim time when running against the Gazebo simulation - so Servo
actually follows the commands.

Run it in the project environment, e.g.:

    scripts/run.sh python scripts/servo_twist.py --linear 0.05 0 0 --duration 3
    scripts/run.sh python scripts/servo_twist.py --linear 0 0 -0.05 \
        --angular 0 0 0.2 --frame tool0 --rate 20 --duration 4

Before the first command in a session, select the twist input once:

    scripts/run.sh ros2 service call /servo_node/switch_command_type \
        moveit_msgs/srv/ServoCommandType "{command_type: 1}"
"""

import argparse
import sys

import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node
from rclpy.parameter import Parameter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish TwistStamped commands with fresh (sim) timestamps.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--linear", nargs=3, type=float, default=[0.0, 0.0, 0.0],
                        metavar=("X", "Y", "Z"), help="linear velocity [m/s]")
    parser.add_argument("--angular", nargs=3, type=float, default=[0.0, 0.0, 0.0],
                        metavar=("X", "Y", "Z"), help="angular velocity [rad/s]")
    parser.add_argument("--frame", default="tool0",
                        help="command frame (must be a robot link or tf frame)")
    parser.add_argument("--rate", type=float, default=20.0,
                        help="publish rate [Hz]; must be > 1/incoming_command_timeout")
    parser.add_argument("--duration", type=float, default=3.0,
                        help="seconds to publish (0 = until Ctrl+C)")
    parser.add_argument("--topic", default="/servo_node/delta_twist_cmds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    rclpy.init()
    node = Node(
        "servo_twist_publisher",
        parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)],
    )
    publisher = node.create_publisher(TwistStamped, args.topic, 10)

    msg = TwistStamped()
    msg.header.frame_id = args.frame
    msg.twist.linear.x, msg.twist.linear.y, msg.twist.linear.z = args.linear
    msg.twist.angular.x, msg.twist.angular.y, msg.twist.angular.z = args.angular

    state = {"count": 0}

    def tick() -> None:
        now = node.get_clock().now()
        if now.nanoseconds == 0:
            if state["count"] % int(args.rate) == 0:
                node.get_logger().info("waiting for /clock (is the sim running?)")
            return
        msg.header.stamp = now.to_msg()
        publisher.publish(msg)
        state["count"] += 1

    timer = node.create_timer(1.0 / args.rate, tick)
    node.get_logger().info(
        f"publishing on {args.topic}: frame={args.frame} "
        f"linear={args.linear} angular={args.angular} rate={args.rate} Hz"
    )

    target = args.duration * args.rate if args.duration > 0 else None
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)
            if target is not None and state["count"] >= target:
                break
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info(f"published {state['count']} messages")
        node.destroy_timer(timer)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
