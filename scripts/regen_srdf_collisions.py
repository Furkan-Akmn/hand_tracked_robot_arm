#!/usr/bin/env python3
"""Regenerate the gripper collision exclusions in the MoveIt SRDF.

MoveIt collision-checks every link pair the SRDF does not disable - directly
jointed (adjacent) links included; nothing is allowed implicitly. The UR5e
SRDF shipped in ur_moveit_config knows nothing about the Robotiq gripper, so
MoveIt collision-checks every gripper-internal pair and every gripper link
against the last arm links - all neighbours that touch in the design pose
itself (e.g. each knuckle against the gripper base it is hinged to). MoveIt
Servo emergency-stops on them ("Collision detected, emergency stop").

This script renders the composed robot description (urdf/*.xacro), collects
all pairs that involve at least one gripper link (plus the wrist_1..tool0
chain against the gripper) - adjacent ones as reason "Adjacent", the rest as
"Never" - and rewrites

    src/arm_bringup/srdf/ur5e_robotiq.srdf.xacro

Run it through the project environment so xacro and the ament index are set
up:

    scripts/run.sh python scripts/regen_srdf_collisions.py

Re-run it whenever the gripper or the adapter mount changes. Commit the
regenerated file so the SRDF stays reviewable in git.
"""
import os
import xml.etree.ElementTree as ET

import xacro

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESCRIPTION = os.path.join(ROOT, "src", "arm_bringup", "urdf", "ur5e_robotiq_gz.urdf.xacro")
OUTPUT = os.path.join(ROOT, "src", "arm_bringup", "srdf", "ur5e_robotiq.srdf.xacro")

# Arm links close enough to the gripper to collide with it. The stock SRDF
# already excludes tool0/wrist_1..wrist_3 pairs among themselves.
ARM_LINKS = ["wrist_1_link", "wrist_2_link", "wrist_3_link", "flange", "tool0"]

# Everything from the flange adapter down to the finger tips.
GRIPPER_LINKS = [
    "ur_to_robotiq_link",
    "gripper_mount_link",
    "robotiq_85_base_link",
    "robotiq_85_left_knuckle_link",
    "robotiq_85_right_knuckle_link",
    "robotiq_85_left_finger_link",
    "robotiq_85_right_finger_link",
    "robotiq_85_left_inner_knuckle_link",
    "robotiq_85_right_inner_knuckle_link",
    "robotiq_85_left_finger_tip_link",
    "robotiq_85_right_finger_tip_link",
]

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Semantic description (SRDF) for the UR5e + Robotiq 2F-85 cell.

     The stock UR5e SRDF only knows the arm links, so every pair of
     gripper links - and every gripper link against the last arm links -
     is collision checked. The gripper is rigidly mounted, its links sit
     a few mm apart and the finger links interleave, so MoveIt Servo
     would halt on "self-collisions" that are actually the design pose.

     The block below disables exactly those pairs. MoveIt does not allow
     directly jointed links implicitly, so they are listed too (reason
     Adjacent, the others Never). The list is generated from the URDF
     kinematics and covers the gripper-internal pairs plus the
     wrist_1..tool0 chain against the 11 gripper links.

     Regenerate with scripts/regen_srdf_collisions.py after any gripper
     or adapter change.
-->
<robot xmlns:xacro="http://wiki.ros.org/xacro" name="$(arg name)">

  <!-- robot name parameter -->
  <xacro:arg name="name" default="ur"/>

  <!-- Stock UR5e arm semantics: groups, named states, arm self-collisions -->
  <xacro:include filename="$(find ur_moveit_config)/srdf/ur_macro.srdf.xacro"/>
  <xacro:ur_srdf/>

  <!-- Gripper assembly vs arm links and gripper internal pairs -->
{pairs}
</robot>
"""


def adjacency(root):
    """Pairs of links that are directly connected by a joint."""
    adjacent = set()
    for joint in root.findall("joint"):
        parent = joint.find("parent").get("link")
        child = joint.find("child").get("link")
        adjacent.add(frozenset((parent, child)))
    return adjacent


def generate_pairs(adjacent):
    """(link_a, link_b, reason) for every arm-gripper and gripper-gripper pair."""
    pairs = [(a, b) for a in ARM_LINKS for b in GRIPPER_LINKS]
    pairs += [
        (a, b) for i, a in enumerate(GRIPPER_LINKS) for b in GRIPPER_LINKS[i + 1:]
    ]
    return [
        (a, b, "Adjacent" if frozenset((a, b)) in adjacent else "Never")
        for a, b in pairs
    ]


def main():
    # `name` is used in the <robot> tag itself, before the xacro:arg default
    # can apply when using the Python API - pass it explicitly.
    robot = ET.fromstring(xacro.process_file(DESCRIPTION, mappings={"name": "ur"}).toxml())
    pairs = generate_pairs(adjacency(robot))
    lines = "\n".join(
        f'  <disable_collisions link1="{a}" link2="{b}" reason="{reason}"/>'
        for a, b, reason in pairs
    )
    with open(OUTPUT, "w") as output_file:
        output_file.write(TEMPLATE.format(pairs=lines))
    print(f"{OUTPUT}: {len(pairs)} disable_collisions entries")


if __name__ == "__main__":
    main()
