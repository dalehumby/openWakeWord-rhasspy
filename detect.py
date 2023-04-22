import io
import queue
import socket
import threading
import wave

import numpy as np
from openwakeword.model import Model

CHUNK = 1280

oww = Model()
q = queue.Queue()


def receive_udp_audio(port=12102):
    """
    Get audio from UDP stream and add to wake word detection queue.

    Rhasspy sends 1024 x 16bit frames + header = 2092 bytes
    Open Wake Word expects 1280 x 16bit frames (CHUNK)
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", port))
    print(f"Listening on UDP port {port}")

    audio_buffer = []
    while True:
        data, addr = sock.recvfrom(2092)
        audio = wave.open(io.BytesIO(data))
        frames = audio.readframes(1024)
        audio_buffer.extend(np.frombuffer(frames, dtype=np.int16))
        if len(audio_buffer) > CHUNK:
            q.put(audio_buffer[:CHUNK])
            audio_buffer = audio_buffer[CHUNK:]


receive_audio_thread = threading.Thread(target=receive_udp_audio)
receive_audio_thread.start()
while True:
    prediction = oww.predict(q.get())
    for model_name in prediction.keys():
        prediction_level = prediction[model_name]
        if prediction_level >= 0.5:
            print(model_name, prediction_level)
