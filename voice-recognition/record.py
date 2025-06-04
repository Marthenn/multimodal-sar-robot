import subprocess
import librosa
import numpy as np
import tensorflow as tf
from scipy.ndimage import zoom
import os
import warnings
import time
import resampy
import soundfile as sf
import paho.mqtt.client as mqtt
import json

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore", category=UserWarning)

# MQTT Setup
MQTT_HOST = "vlg2.local"
MQTT_PORT = 1883
MQTT_TOPIC = "sar-robot/sound"

client = mqtt.Client()
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()

# Audio recording
def record_audio(filename, duration, device="plughw:1,0"):
    cmd = ["arecord", "-D", device, "-d", str(duration), "-f", "cd", filename]
    subprocess.run(cmd, check=True)

# Load + preprocess
def load_audio(filepath, target_sr=16000):
    audio, sr = sf.read(filepath)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    if sr != target_sr:
        audio = resampy.resample(audio, sr, target_sr)
    return audio.astype(np.float32), target_sr

def preprocess_audio_to_input(filepath):
    audio, sr = load_audio(filepath, target_sr=16000)
    melspec = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=64, fmax=8000)
    log_mel = librosa.power_to_db(melspec, ref=np.max)
    zoom_factors = (64 / log_mel.shape[0], 64 / log_mel.shape[1])
    log_mel_resized = zoom(log_mel, zoom_factors, order=1)
    log_mel_resized = np.clip(log_mel_resized, -80, 0)
    log_mel_resized = (log_mel_resized + 80) / 80.0
    return np.expand_dims(log_mel_resized, axis=(0, -1)).astype(np.float32)

# Inference & MQTT publish
def predict_and_publish(filepath, model_path):
    input_data = preprocess_audio_to_input(filepath)

    interpreter = tf.lite.Interpreter(model_path=model_path, num_threads=1)
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

    message = {
        "position": "dummy",
        "human_confidence": round(score, 4)
    }
    client.publish(MQTT_TOPIC, json.dumps(message))
    print(f"[📤] Published: {message} | Inference time: {inference_time:.3f}s")

    return score, label

# Main loop
def main():
    model_path = "../models/model.tflite"
    t = 3
    device = "plughw:2,0"
    output_dir = "recordings"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("Recording & Inference loop started. Ctrl+C to stop.")
    i = 1
    try:
        while True:
            filename = os.path.join(output_dir, f"recording_chunk_{i}.wav")
            print(f"[🎙️] Recording {t} seconds audio (chunk {i})...")
            record_audio(filename, t, device)
            print(f"[🤖] Running inference...")
            predict_and_publish(filename, model_path)
            os.remove(filename)
            i += 1
    except KeyboardInterrupt:
        print("\n[🛑] Stopped by user.")
    finally:
        client.loop_stop()
        client.disconnect()
        print("[✅] MQTT disconnected.")

if __name__ == "__main__":
    main()
