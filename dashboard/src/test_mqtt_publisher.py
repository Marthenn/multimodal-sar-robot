import paho.mqtt.client as mqtt
import json
import time
import random
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="MQTT Test Publisher for SAR Robot Sound Direction"
    )
    parser.add_argument("--host", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--topic", default="sar-robot/sound", help="MQTT topic")
    parser.add_argument(
        "--interval", type=float, default=1.0, help="Publish interval in seconds"
    )
    args = parser.parse_args()

    # Create MQTT client
    client = mqtt.Client()

    try:
        # Connect to broker
        print(f"Connecting to MQTT broker at {args.host}:{args.port}...")
        client.connect(args.host, args.port, 60)
        print("Connected!")

        # Start the loop
        client.loop_start()

        print(f"Publishing test messages to {args.topic} every {args.interval} seconds")
        print("Press Ctrl+C to stop")

        while True:
            # Generate test data
            position = random.uniform(0, 360)  # Random angle between 0 and 360
            confidence = random.uniform(
                0.5, 1.0
            )  # Random confidence between 0.5 and 1.0

            # Create message
            message = {"position": position, "human_confidence": confidence}

            # Publish message
            client.publish(args.topic, json.dumps(message))
            print(f"Published: {message}")

            # Wait for interval
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nStopping publisher...")
    finally:
        client.loop_stop()
        client.disconnect()
        print("Disconnected from broker")


if __name__ == "__main__":
    main()
