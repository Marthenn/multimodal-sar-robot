import librosa
import numpy as np
import tensorflow as tf
from scipy.ndimage import zoom

def preprocess_audio_to_input(filepath):
    # Load audio
    audio, sr = librosa.load(filepath, sr=16000)
    if audio.size == 0:
        raise ValueError("Audio file is empty.")
    
    # Convert to mel spectrogram
    melspec = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=64, fmax=8000)
    log_mel = librosa.power_to_db(melspec, ref=np.max)

    # Resize pakai scipy.ndimage.zoom (konsisten dengan training)
    zoom_factors = (64 / log_mel.shape[0], 64 / log_mel.shape[1])
    log_mel_resized = zoom(log_mel, zoom_factors, order=1)

    # Normalisasi: dB [-80, 0] → [0, 1]
    log_mel_resized = np.clip(log_mel_resized, -80, 0)
    log_mel_resized = (log_mel_resized + 80) / 80

    # Final input shape: (1, 64, 64, 1)
    input_data = np.expand_dims(log_mel_resized, axis=(0, -1)).astype(np.float32)
    return input_data

def predict_with_tflite(filepath, model_path):
    # Preprocess audio
    input_data = preprocess_audio_to_input(filepath)

    # Load TFLite model
    interpreter = tf.lite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()

    # Get input/output details
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    # Set input tensor
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()

    # Get output
    output_data = interpreter.get_tensor(output_details[0]['index'])
    score = float(output_data[0][0])
    label = 1 if score > 0.5 else 0

    print(f"Raw score: {score:.4f}")
    print("Predicted label:", "Human" if label == 1 else "Non-human")
    return score, label

# 🔧 Contoh penggunaan:
predict_with_tflite("voice_202499.wav", "../models/model_cnn_64x64.tflite")
