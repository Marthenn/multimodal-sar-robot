import serial
import re
import paho.mqtt.client as mqtt
import json
import csv
import os
import time

broker = "vlg2.local"  # Change to your MQTT broker address
port = 1883  # Default MQTT port
topic = "sar-robot/position"

client = mqtt.Client()
client.connect(broker, port)

# Adjust to your actual port (e.g., COM3 for Windows, /dev/ttyUSB0 for Linux)
PORT = '/dev/ttyUSB0'
BAUD = 115200

csv_filename = "beacon_output5.csv"
file_exists = os.path.isfile(csv_filename)

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print(f"Listening on {PORT} at {BAUD} baud...\n")

    # if not file_exists or os.stat(csv_filename).st_size == 0:
    #     with open(csv_filename, mode="w", newline='') as file:
    #         writer = csv.writer(file)
    #         writer.writerow(["beacon", "millis", "x", "y"])  # CSV header

    while True:
        millis = int(round(time.time() * 1000))
        try:
            line = ser.readline().decode('utf-8').strip()
            print(f"Raw line: {line}")
            if line and re.match(r"Beacon .:.+\)", line):
                print(f"Received: {line}")
                res = line.lower()
                beaconid = ord(res[7]) - ord('a') + 1
                res = res.split('(')[1][:-1].split(',')
                x = float(res[0].strip())
                y = float(res[1].strip())
                message = {
                    f"beacon-{beaconid}": {
                        "x": x,
                        "y": y
                    }
                }

                # with open(csv_filename, mode="a", newline='') as file:
                #     writer = csv.writer(file)
                #     writer.writerow([f"beacon-{beaconid}", millis, x, y])

                
                print(f"Processed message: {message}")
                client.publish(topic, json.dumps(message))
        except:
            continue

except serial.SerialException as e:
    print(f"Serial error: {e}")
except KeyboardInterrupt:
    print("Stopped by user.")
client.disconnect()
