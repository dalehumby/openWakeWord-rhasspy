import argparse
import io
import queue
import socket
import threading
import time
import wave
from json import dumps

import numpy as np
import paho.mqtt.client as mqtt
import yaml
from openwakeword.model import Model

RHASSPY_BYTES = 2092
RHASSPY_FRAMES = 1024
CHUNK = 1280  # 80 ms window @ 16 kHz = 1280 frames
OWW_FRAMES = CHUNK * 3  # Increase efficiency of detection but higher latency

q = queue.Queue()

parser = argparse.ArgumentParser(description="PiJuice to MQTT")
parser.add_argument(
    "-c",
    "--config",
    default="config.yaml",
    help="Configuration yaml file, defaults to `config.yaml`",
    dest="config_file",
)
args = parser.parse_args()


def load_config(config_file):
    """Load the configuration from config yaml file and use it to override the defaults."""
    with open(config_file, "r") as f:
        config_override = yaml.safe_load(f)

    default_config = {
        "mqtt": {
            "broker": "127.0.0.1",
            "port": 1883,
            "username": None,
            "password": None,
        },
        "oww": {
            "activation_threshold": 0.5,
            "vad_threshold": 0,
            "enable_speex_noise_suppression": False,
        },
    }

    config = {**default_config, **config_override}
    return config


def receive_udp_audio(port=12102):
    """
    Get audio from UDP stream and add to wake word detection queue.

    Rhasspy sends 1024 x 16bit frames + header = 2092 bytes
    Open Wake Word expects minimum of 1280 x 16bit frames
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", port))

    print(f"Listening on UDP port {port}")

    audio_buffer = []
    while True:
        data, addr = sock.recvfrom(RHASSPY_BYTES)
        audio = wave.open(io.BytesIO(data))
        frames = audio.readframes(RHASSPY_FRAMES)
        audio_buffer.extend(np.frombuffer(frames, dtype=np.int16))
        print(".", end="", flush=True)
        if len(audio_buffer) > OWW_FRAMES:
            q.put(
                np.asarray(audio_buffer[:OWW_FRAMES], dtype=np.int16)
            )  # Must be np array for VAD
            audio_buffer = audio_buffer[OWW_FRAMES:]


def on_connect(client, userdata, flags, rc):
    client.subscribe("hermes/hotword/#")


def on_message(client, userdata, msg):
    # print(f"{msg.topic} {msg.payload}")
    pass


config = load_config(args.config_file)

if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.username_pw_set(config["mqtt"]["username"], config["mqtt"]["password"])
    client.connect(config["mqtt"]["broker"], config["mqtt"]["port"], 60)
    print("Connected to MQTT broker")

    oww = Model(
        vad_threshold=config["oww"]["vad_threshold"],
        enable_speex_noise_suppression=config["oww"]["enable_speex_noise_suppression"],
    )
    receive_audio_thread = threading.Thread(target=receive_udp_audio)
    receive_audio_thread.start()

    published = 0
    client.loop_start()
    while True:
        prediction = oww.predict(q.get())
        for model_name in prediction.keys():
            prediction_level = prediction[model_name]
            if prediction_level >= config["oww"]["activation_threshold"]:
                delta = time.time() - published
                print(f"{model_name} {prediction_level:.3f} {delta:.3f}")
                if delta > 5:
                    payload = {
                        "modelId": model_name,
                        "modelVersion": "",
                        "modelType": "universal",
                        "currentSensitivity": config["oww"]["activation_threshold"],
                        "siteId": "bedroom",
                        "sessionId": None,
                        "sendAudioCaptured": None,
                        "lang": None,
                        "customEntities": None,
                    }
                    client.publish(
                        f"hermes/hotword/{model_name}/detected", dumps(payload)
                    )
                    print("Sent wakeword to Rhasspy")
                published = time.time()
