from setuptools import find_packages, setup


package_name = "airmouse_ros_adapter"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        (
            "share/" + package_name,
            ["package.xml"],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="AirMouse V1 Team",
    maintainer_email="maintainer@example.com",
    description=(
        "ROS 2 adapter exposing the AirMouse flight-control core."
    ),
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "airmouse_adapter = "
            "airmouse_ros_adapter.main:main",
        ],
    },
)
