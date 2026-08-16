from modules.audio.preprocessing import preprocess_audio

result = preprocess_audio(
    "data/input/2_marathi.wav",
    "data/temp",
)

print(result)