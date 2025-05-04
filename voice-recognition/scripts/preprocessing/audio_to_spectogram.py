import os
import numpy as np
import librosa
from tqdm import tqdm
from scipy.ndimage import zoom

# Define base, input, and output directories
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))  # 2 level up
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'processed')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'spectogram')

# Desired output spectrogram size
TARGET_SIZE = (64, 64)

os.makedirs(os.path.join(OUTPUT_DIR, 'human'), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, 'nonhuman'), exist_ok=True)

def convert_to_spectrogram(file_path, target_size):
    """
    Load an audio file and convert it into a resized mel spectrogram.
    
    Args:
        file_path (str): Path to the audio file (.wav)
        target_size (tuple): Desired spectrogram size (height, width)
    
    Returns:
        np.ndarray or None: Resized spectrogram array or None if invalid
    """
    y, sr = librosa.load(file_path, sr=16000, mono=True) # Force mono and 16kHz sample rate
    
    if y.size == 0:
        print(f"Skipped empty audio: {file_path}")
        return None

    # Compute mel spectrogram
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=target_size[0])
    S_dB = librosa.power_to_db(S, ref=np.max)

    # Resize the spectrogram smoothly using zoom
    zoom_factors = (target_size[0] / S_dB.shape[0], target_size[1] / S_dB.shape[1])
    S_resized = zoom(S_dB, zoom_factors, order=1) # Linear interpolation

    return S_resized

def process_directory(label):
    """
    Process all WAV files in the given label directory (e.g., 'human' or 'nonhuman'),
    convert them to spectrograms, and save as .npy files.

    Args:
        label (str): The subfolder name indicating class label
    """
    input_folder = os.path.join(INPUT_DIR, label)
    output_folder = os.path.join(OUTPUT_DIR, label)

    for filename in tqdm(os.listdir(input_folder), desc=f"Processing {label}"):
        if filename.endswith('.wav'):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename.replace('.wav', '.npy'))

            spectrogram = convert_to_spectrogram(input_path, TARGET_SIZE)

            if spectrogram is None or np.max(spectrogram) == 0:
                print(f"Skipped invalid spectrogram: {input_path}")
            else:
                np.save(output_path, spectrogram)

# Process both human and nonhuman audio datasets
process_directory('human')
process_directory('nonhuman')
print("✅ Done converting.")
