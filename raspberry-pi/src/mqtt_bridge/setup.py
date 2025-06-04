from setuptools import setup

package_name = 'mqtt_bridge'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'paho-mqtt'],
    zip_safe=True,
    maintainer='Marthen',
    maintainer_email='marthen.bintangdwi@gmail.com',
    description='MQTT to micro-ROS bridge for TurtleBot3',
    license='MIT',
    entry_points={
        'console_scripts': [
            'mqtt_to_micro_ros = mqtt_bridge.mqtt_to_micro_ros:main',
        ],
    },
)
