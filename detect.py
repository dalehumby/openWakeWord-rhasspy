"""
Listen on UDP for audio from Rhasspy, detect wake words using Open Wake Word,
and publish on MQTT when wake word is detected to trigger Rhasspy speech-to-text.
"""

import argparse
import io
import queue
import socket
import threading
import time
import wave
from collections import deque
from json import dumps

import numpy as np
import paho.mqtt.client
import yaml
from openwakeword.model import Model

RHASSPY_BYTES = 2092
RHASSPY_FRAMES = 1024
OWW_FRAMES = 1280  # 80 ms window @ 16 kHz = 1280 frames


parser = argparse.ArgumentParser(description="Open Wake Word detection for Rhasspy")
parser.add_argument(
    "-c",
    "--config",
    default="config.yaml",
    help="Configuration yaml file, defaults to `config.yaml`",
    dest="config_file",
)
args = parser.parse_args()


def load_config(config_file):
    """Use config.yaml to override the default configuration."""
    try:
        with open(config_file, "r") as f:
            config_override = yaml.safe_load(f)
    except FileNotFoundError:
        config_override = {}

    default_config = {
        "mqtt": {
            "broker": "127.0.0.1",
            "port": 1883,
            "username": None,
            "password": None,
        },
        "oww": {
            "model_names": ["alexa", "hey_mycroft", "hey_jarvis", "timer", "weather"],
            "activation_threshold": 0.7,
            "deactivation_threshold": 0.2,
            "activation_samples": 3,
            "vad_threshold": 0,
            "enable_speex_noise_suppression": False,
        },
        "udp_ports": {"base": 12202},
    }

    config = {**default_config, **config_override}
    if not config["udp_ports"]:
        print(
            "No UDP ports configured. Configure UDP ports to receive audio for wakeword detection.",
            flush=True,
        )
        exit()
    return config


class RhasspyUdpAudio(threading.Thread):
    """Get audio from UDP stream and add to wake word detection queue."""

    def __init__(self, roomname, port, queue):
        threading.Thread.__init__(self)
        self.roomname = roomname
        self.port = port
        self.queue = queue
        self.buffer = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", port))

    def run(self):
        """Thread to receive UDP audio and add to processing queue."""
        print(
            f"Listening for {self.roomname} audio on UDP port {self.port}", flush=True
        )
        while True:
            data, addr = self.sock.recvfrom(RHASSPY_BYTES)
            audio = wave.open(io.BytesIO(data))
            frames = audio.readframes(RHASSPY_FRAMES)
            self.buffer.extend(np.frombuffer(frames, dtype=np.int16))
            if len(self.buffer) > OWW_FRAMES:
                self.queue.put(
                    (
                        self.roomname,
                        time.time(),
                        np.asarray(self.buffer[:OWW_FRAMES], dtype=np.int16),
                    )
                )
                self.buffer = self.buffer[OWW_FRAMES:]


class Prediction(threading.Thread):
    """Process wake word detection queue and publishing MQTT message when a wake word is detected."""

    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue
        self.filters = {}
        self.mqtt = paho.mqtt.client.Client()
        self.mqtt.username_pw_set(
            config["mqtt"]["username"], config["mqtt"]["password"]
        )
        self.mqtt.connect(config["mqtt"]["broker"], config["mqtt"]["port"], 60)
        self.mqtt.loop_start()
        print("MQTT: Connected to broker", flush=True)

        self.oww = Model(
            vad_threshold=config["oww"]["vad_threshold"],
            enable_speex_noise_suppression=config["oww"][
                "enable_speex_noise_suppression"
            ],
        )

    def run(self):
        """
        Wake word detection thread.

        Detect and filter all wake-words, but only publish to MQTT if wake-word model name is listed
        in config.yaml.
        """
        while True:
            roomname, timestamp, audio = self.queue.get()
            prediction = self.oww.predict(audio)
            for wakeword in prediction.keys():
                confidence = prediction[wakeword]
                if (
                    self.__filter(wakeword, confidence)
                    and wakeword in config["oww"]["model_names"]
                ):
                    self.__publish(wakeword, roomname)

    def __filter(self, wakeword, confidence):
        """
        Filter so that a wakeword is only triggered once per utterance.

        When simple moving average (of length `activation_samples`) crosses the `activation_threshold`
        for the first time, then trigger Rhasspy. Only "re-arm" the wakeword when the moving average
        drops below the `deactivation_threshold`.
        """
        try:
            self.filters[wakeword]["samples"].append(confidence)
        except KeyError:
            self.filters[wakeword] = {
                "samples": deque(
                    [confidence], maxlen=config["oww"]["activation_samples"]
                ),
                "active": False,
            }
        moving_average = np.average(self.filters[wakeword]["samples"])
        activated = False
        if (
            not self.filters[wakeword]["active"]
            and moving_average >= config["oww"]["activation_threshold"]
        ):
            self.filters[wakeword]["active"] = True
            activated = True
        elif (
            self.filters[wakeword]["active"]
            and moving_average < config["oww"]["deactivation_threshold"]
        ):
            self.filters[wakeword]["active"] = False
        if moving_average > 0.1:
            print(
                f"{wakeword:<16} {activated!s:<8} {self.filters[wakeword]}", flush=True
            )
        return activated

    def __publish(self, wakeword, roomname):
        """Publish wake word message to Rhasspy Hermes/MQTT."""
        payload = {
            "modelId": wakeword,
            "modelVersion": "",
            "modelType": "universal",
            "currentSensitivity": config["oww"]["activation_threshold"],
            "siteId": roomname,
            "sessionId": None,
            "sendAudioCaptured": None,
            "lang": None,
            "customEntities": None,
        }
        self.mqtt.publish(f"hermes/hotword/{wakeword}/detected", dumps(payload))
        print(
            "MQTT: Published wakeword {wakeword}, siteId {roomname} to Rhasspy",
            flush=True,
        )


if __name__ == "__main__":
    config = load_config(args.config_file)
    q = queue.Queue()
    threads = []
    for roomname, port in config["udp_ports"].items():
        t = RhasspyUdpAudio(roomname, port, q)
        t.daemon = True
        t.start()
        threads.append(t)
    t = Prediction(q)
    t.start()
    threads.append(t)
    print(f"Threads: {threads}")
