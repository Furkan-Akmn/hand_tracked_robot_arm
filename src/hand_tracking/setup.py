from setuptools import find_packages, setup

package_name = "hand_tracking"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/hand_tracking.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Moses",
    maintainer_email="moses@example.com",
    description="Webcam hand tracking (MediaPipe) publishing /hand/state.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "landmark_node = hand_tracking.landmark_node:main",
        ],
    },
)
