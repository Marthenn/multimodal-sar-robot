import asyncio
import sounddevice as sd
import numpy as np
import threading
import queue
import json
import time
import tensorflow as tf
import librosa
import resampy
import soundfile as sf
import os
import warnings
import websockets
import paho.mqtt.client as mqtt

warnings.filterwarnings("ignore", category=UserWarning)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# Config
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION = 3  # seconds
CHUNK_SIZE = CHUNK_DURATION * SAMPLE_RATE
DEVICE_INDEX = None  # or use specific index like 2
current_position = 512

# Queues
inference_queue = queue.Queue()
broadcast_queue = queue.Queue()

# MQTT Setup
MQTT_HOST = "vlg2.local"
MQTT_PORT = 1883
MQTT_TOPIC = "sar-robot/sound"
mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_start()

def convert_position(position: int) -> float:
    return (1023 - position) / 1023.0 * 300.0

def on_message(client, userdata, msg):
    global current_position
    try:
        if msg.topic == "sar-robot/pan_angle":
            payload = msg.payload.decode('utf-8')
            new_position = int(float(payload))
            # Ensure position is within valid range (0-1023)
            new_position = max(0, min(1023, new_position))
            current_position = new_position
            print(f"[🔄] Updated pan position to {current_position} ({convert_position(current_position):.2f}°)")
    except Exception as e:
        print(f"[❌] Error processing pan angle update: {e}")

mqtt_client.on_message = on_message
mqtt_client.subscribe("sar-robot/pan_angle")
print("[📡] MQTT client started and subscribed to 'sar-robot/pan_angle'")

# Inference
def run_inference(audio_data: np.ndarray, model_path: str):
    melspec = librosa.feature.melspectrogram(y=audio_data, sr=SAMPLE_RATE, n_mels=64, fmax=8000)
    log_mel = librosa.power_to_db(melspec, ref=np.max)
    log_mel_resized = librosa.util.fix_length(log_mel, size=64, axis=1)
    log_mel_resized = np.clip(log_mel_resized, -80, 0)
    log_mel_resized = (log_mel_resized + 80) / 80.0
    input_data = np.expand_dims(log_mel_resized, axis=(0, -1)).astype(np.float32)

    interpreter = tf.lite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    interpreter.set_tensor(input_details[0]['index'], input_data)
    start_time = time.time()
    interpreter.invoke()
    inference_time = time.time() - start_time

    output_data = interpreter.get_tensor(output_details[0]['index'])
    score = float(output_data[0][0])
    label = 1 if score > 0.5 else 0

    curr_position_angle = convert_position(current_position)

    message = {
        "position": round(curr_position_angle, 4),
        "human_confidence": round(score, 4)
    }
    mqtt_client.publish(MQTT_TOPIC, json.dumps(message))
    print(f"[📤] Published: {message} | Inference time: {inference_time:.3f}s")

# Audio callback
def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    audio_chunk = indata[:, 0].copy()  # mono
    inference_queue.put(audio_chunk)
    broadcast_queue.put(audio_chunk)

# Inference Thread
def inference_loop(model_path):
    buffer = np.array([], dtype=np.float32)
    while True:
        chunk = inference_queue.get()
        buffer = np.concatenate((buffer, chunk))
        if len(buffer) >= CHUNK_SIZE:
            to_process = buffer[:CHUNK_SIZE]
            run_inference(to_process, model_path)
            buffer = buffer[CHUNK_SIZE:]

# WebSocket Streamer
connected_clients = set()

async def ws_handler(websocket, path=None):
    connected_clients.add(websocket)
    print(f"[🌐] New WebSocket client connected.")
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        connected_clients.remove(websocket)

async def ws_broadcaster():
    buffer = np.array([], dtype=np.float32)
    while True:
        try:
            chunk = broadcast_queue.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.001)
            continue
        buffer = np.concatenate((buffer, chunk))
        if len(buffer) >= CHUNK_SIZE:
            data = buffer[:CHUNK_SIZE].tobytes()
            buffer = buffer[CHUNK_SIZE:]
            if connected_clients:
                await asyncio.gather(*[client.send(data) for client in connected_clients])


async def start_websocket_server():
    print("[🌐] Starting WebSocket server...")
    async with websockets.serve(ws_handler, "0.0.0.0", 8765):
        await ws_broadcaster()  # this will run forever

def main():
    model_path = "../models/model.tflite"

    print("[🎙️] Starting microphone...")
    stream = sd.InputStream(callback=audio_callback,
                            channels=CHANNELS,
                            samplerate=SAMPLE_RATE,
                            device=DEVICE_INDEX,
                            blocksize=1024)
    stream.start()

    threading.Thread(target=inference_loop, args=(model_path,), daemon=True).start()

    asyncio.run(start_websocket_server())

if __name__ == "__main__":
    main()
