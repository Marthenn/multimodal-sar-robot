import paho.mqtt.client as mqtt
import curses
import time

MQTT_BROKER = "vlg2.local"  # or IP address of Raspberry Pi
MQTT_PORT = 1883
MQTT_TOPIC = "sar-robot/control"

client = mqtt.Client()

def connect_mqtt():
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        exit(1)

def send_command(cmd):
    client.publish(MQTT_TOPIC, cmd)

def main(stdscr):
    connect_mqtt()
    client.loop_start()

    stdscr.nodelay(True)
    stdscr.clear()
    stdscr.addstr("W/A/S/D = move, Q/E = pan, SPACE = stop, ESC = quit\n")

    try:
        while True:
            key = stdscr.getch()

            if key == -1:
                time.sleep(0.05)
                continue

            if key in [ord('w'), ord('W')]:
                send_command("forward")
                stdscr.addstr(1, 0, "Sent: forward       ")
            elif key in [ord('s'), ord('S')]:
                send_command("backward")
                stdscr.addstr(1, 0, "Sent: backward      ")
            elif key in [ord('a'), ord('A')]:
                send_command("left")
                stdscr.addstr(1, 0, "Sent: left          ")
            elif key in [ord('d'), ord('D')]:
                send_command("right")
                stdscr.addstr(1, 0, "Sent: right         ")
            elif key in [ord('q'), ord('Q')]:
                send_command("pan_left")
                stdscr.addstr(1, 0, "Sent: pan_left      ")
            elif key in [ord('e'), ord('E')]:
                send_command("pan_right")
                stdscr.addstr(1, 0, "Sent: pan_right     ")
            elif key == ord(' '):  # Spacebar
                send_command("stop")
                stdscr.addstr(1, 0, "Sent: stop          ")
            elif key == 27:  # ESC
                break

            stdscr.refresh()
            time.sleep(0.05)

    finally:
        send_command("stop")
        client.loop_stop()
        client.disconnect()
        stdscr.addstr(2, 0, "Disconnected. Press any key to exit.")
        stdscr.nodelay(False)
        stdscr.getch()

if __name__ == "__main__":
    curses.wrapper(main)
