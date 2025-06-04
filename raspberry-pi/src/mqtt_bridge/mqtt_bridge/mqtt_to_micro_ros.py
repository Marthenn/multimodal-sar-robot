import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
import paho.mqtt.client as mqtt

MQTT_BROKER = "vlg2.local"
MQTT_PORT = 1883
MQTT_TOPIC = "sar-robot/control"
MQTT_TOPIC_PAN = "sar-robot/pan_angle"

PAN_STEP = 32
PAN_MIN = 0
PAN_MAX = 1023
current_pan = 512

# Define wheel speeds (can be tuned)
LINEAR_SPEED = 200  # forward/backward speed
TURN_SPEED = 150    # turning speed

class MqttToMicroROS(Node):
    def __init__(self):
        super().__init__('mqtt_to_micro_ros')
        self.left_pub = self.create_publisher(Int32, '/left_wheel_vel', 10)
        self.right_pub = self.create_publisher(Int32, '/right_wheel_vel', 10)
        self.pan_pub = self.create_publisher(Int32, '/pan_angle', 10)

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

        try:
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        except Exception as e:
            self.get_logger().error(f"MQTT connection failed: {e}")
            rclpy.shutdown()
            return

        self.mqtt_client.loop_start()
        self.get_logger().info("MQTT to micro-ROS bridge started")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.get_logger().info("Connected to MQTT broker")
            client.subscribe(MQTT_TOPIC)
        else:
            self.get_logger().error(f"Failed to connect to MQTT broker. Code: {rc}")

    def on_message(self, client, userdata, msg):
        global current_pan
        command = msg.payload.decode()
        left = 0
        right = 0

        if command == "forward":
            left = -LINEAR_SPEED
            right = -LINEAR_SPEED
        elif command == "backward":
            left = LINEAR_SPEED
            right = LINEAR_SPEED
        elif command == "left":
            left = -TURN_SPEED
            right = TURN_SPEED
        elif command == "right":
            left = TURN_SPEED
            right = -TURN_SPEED
        elif command == "stop":
            left = 0
            right = 0
        elif command == "pan_right":
            current_pan = max(PAN_MIN, current_pan - PAN_STEP)
            self.send_pan(current_pan)
            return
        elif command == "pan_left":
            current_pan = min(PAN_MAX, current_pan + PAN_STEP)
            self.send_pan(current_pan)
            return
        else:
            self.get_logger().warn(f"Unknown command: {command}")
            return

        self.send_wheel_vel(left, right)
        self.get_logger().info(f"Published wheels: L={left} R={right}")

    def send_wheel_vel(self, left, right):
        lmsg = Int32()
        rmsg = Int32()
        lmsg.data = left
        rmsg.data = right
        self.left_pub.publish(lmsg)
        self.right_pub.publish(rmsg)

    def send_pan(self, angle):
        msg = Int32()
        msg.data = angle
        self.pan_pub.publish(msg

        try:
            self.mqtt_client.publish(MQTT_TOPIC_PAN, str(angle))
            self.get_logger().info(f"Published pan angle: {angle}")
        except Exception as e:
            self.get_logger().error(f"Failed to publish pan angle: {e}")

def main():
    rclpy.init()
    node = MqttToMicroROS()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.mqtt_client.loop_stop()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
