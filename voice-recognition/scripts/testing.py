import librosa
import numpy as np
import tensorflow as tf
from scipy.ndimage import zoom
import os
import warnings
import time
import resampy
import soundfile as sf

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore", category=UserWarning)

def load_audio(filepath, target_sr=16000):
    audio, sr = sf.read(filepath)

    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    if sr != target_sr:
        audio = resampy.resample(audio, sr, target_sr)

    return audio.astype(np.float32), target_sr

def preprocess_audio_to_input(filepath):
    start_total = time.time()

    t0 = time.time()
    audio, sr = load_audio(filepath, target_sr=16000)
    print(f"[⏱️ load] {time.time() - t0:.3f}s")

    t0 = time.time()
    melspec = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=64, fmax=8000)
    log_mel = librosa.power_to_db(melspec, ref=np.max)
    print(f"[⏱️ mel+db] {time.time() - t0:.3f}s")

    t0 = time.time()
    zoom_factors = (64 / log_mel.shape[0], 64 / log_mel.shape[1])
    log_mel_resized = zoom(log_mel, zoom_factors, order=1)
    print(f"[⏱️ zoom] {time.time() - t0:.3f}s")

    t0 = time.time()
    log_mel_resized = np.clip(log_mel_resized, -80, 0)
    log_mel_resized = (log_mel_resized + 80) / 80.0
    print(f"[⏱️ normalize] {time.time() - t0:.3f}s")

    print(f"[⏱️ TOTAL preprocess] {time.time() - start_total:.3f}s")
    return np.expand_dims(log_mel_resized, axis=(0, -1)).astype(np.float32)


def predict_with_tflite(filepath, model_path):
    input_data = preprocess_audio_to_input(filepath)

    interpreter = tf.lite.Interpreter(model_path=model_path, num_threads=1)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    print("Input dtype:", input_details[0]['dtype'])
    print("Output dtype:", output_details[0]['dtype'])

    interpreter.set_tensor(input_details[0]['index'], input_data)

    start_time = time.time()
    interpreter.invoke()
    end_time = time.time()

    output_data = interpreter.get_tensor(output_details[0]['index'])

    score = float(output_data[0][0])
    label = 1 if score > 0.5 else 0

    print(f"Raw score: {score:.4f}")
    print("Predicted label:", "Human" if label == 1 else "Non-human")
    print(f"[⏱️ inference time] {end_time - start_time:.3f} seconds")
    return score, label

# Panggil dengan model baru
predict_with_tflite("voice_204890.wav", "../models/model.tflite")
