import paho.mqtt.client as mqtt
import json
import time
import random
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="MQTT Test Publisher for SAR Robot Beacon Position Data"
    )
    parser.add_argument("--host", default="vlg2.local", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument(
        "--topic", default="sar-robot/position", help="MQTT topic for position data"
    )
    parser.add_argument(
        "--interval", type=float, default=1.5, help="Publish interval in seconds"
    )
    parser.add_argument(
        "--range",
        type=float,
        default=80.0,
        help="Max absolute value for x and y coordinates",
    )
    parser.add_argument(
        "--num-beacons", type=int, default=3, help="Number of beacons to simulate"
    )
    args = parser.parse_args()

    client = mqtt.Client()
    beacon_ids = [f"beacon-{i + 1}" for i in range(args.num_beacons)]
    current_beacon_index = 0

    try:
        print(f"Connecting to MQTT broker at {args.host}:{args.port}...")
        client.connect(args.host, args.port, 60)
        print("Connected!")
        client.loop_start()

        print(
            f"Publishing test beacon position messages to {args.topic} every {args.interval} seconds"
        )
        print(f"Simulating {args.num_beacons} beacons: {beacon_ids}")
        print(f"Coordinate range: -{args.range} to +{args.range}")
        print("Press Ctrl+C to stop")

        while True:
            # Update one beacon at a time to make changes more observable
            beacon_to_update = beacon_ids[current_beacon_index]
            current_beacon_index = (current_beacon_index + 1) % args.num_beacons

            x_coord = random.uniform(-args.range, args.range)
            y_coord = random.uniform(-args.range, args.range)

            message_payload = {
                beacon_to_update: {"x": round(x_coord, 2), "y": round(y_coord, 2)}
            }

            client.publish(args.topic, json.dumps(message_payload))
            print(f"Published: {message_payload}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nStopping position publisher...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if client.is_connected():
            client.loop_stop()
            client.disconnect()
        print("Disconnected from broker")


if __name__ == "__main__":
    main()
