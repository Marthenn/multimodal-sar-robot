import os
import shutil
import pandas as pd

# Define base, input, and output directories
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')) # 2 level up
RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw', 'chime_home', 'chunks')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'processed')

os.makedirs(os.path.join(OUTPUT_DIR, 'human'), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, 'nonhuman'), exist_ok=True)

def is_human(label):
    return any(tag in label for tag in ['c', 'm', 'f'])

for file in os.listdir(RAW_DIR):
    if file.endswith('.csv'):
        csv_path = os.path.join(RAW_DIR, file)
        df = pd.read_csv(csv_path, header=None)

        # majority vote
        label = df[df[0] == 'majorityvote'][1].values[0]
        if pd.isna(label):
            print(f"⚠️ Skip: {file} no label majorityvote.")
            continue

        # get the 16kHz.wav
        chunkname = df[df[0] == 'chunkname'][1].values[0]
        wav_file = chunkname + '.16kHz.wav'
        wav_path = os.path.join(RAW_DIR, wav_file)

        if os.path.exists(wav_path):
            if is_human(label):
                dest = os.path.join(OUTPUT_DIR, 'human', wav_file)
            else:
                dest = os.path.join(OUTPUT_DIR, 'nonhuman', wav_file)

            shutil.copy(wav_path, dest)
            print(f"Copied: {wav_file} -> {dest}")
        else:
            print(f"⚠️ Audio file not found for {chunkname}")

print("Done sorting.")
