[![Docker Image CI](https://github.com/dalehumby/openWakeWord-rhasspy/actions/workflows/docker-image.yml/badge.svg)](https://github.com/dalehumby/openWakeWord-rhasspy/actions/workflows/docker-image.yml)

# openWakeWord for Rhasspy 

[openWakeWord](https://github.com/dscripka/openWakeWord) is an open-source library for detecting common wake-words like "alexa", "hey mycroft", "hey jarvis", and [other models](https://github.com/dscripka/openWakeWord#pre-trained-models). [Rhasspy](https://rhasspy.readthedocs.io/en/latest/) is an open-source voice assistant.

This project runs openWakeWord as a stand-alone service, receives audio from Rhasspy via UDP, detects when a wake-word is spoken, and notifies Rhasspy using the Hermes MQTT protocol.

## Why
I run Rhasspy in [Base/Satellite mode](https://rhasspy.readthedocs.io/en/latest/tutorials/#server-with-satellites). Currently each Satellite captures audio, does the wake-word detection locally and streams audio to the Base which does everything else. The Pi4 satellites runs the Rhasspy Docker container, launched with  [compose](https://github.com/dalehumby/rhasspy-config/blob/main/satellite-compose.yaml). The Base Rhasspy container runs on a more powerful i7 (runs other [home automation software](https://github.com/dalehumby/homelab).)

Running openWakeWord in Docker eases distribution and setup (Python dependencies), allows openWakeWord to develop at a separate pace to Rhasspy (instead of bundled and released with Rhasspy.) A single instance of openWakeWord centralises configuration, and allows lower power satellites (e.g. ESP32s) richer wake-word options.

In the future I plan to add a web UI for configuration: which words to detect, thresholds,  [custom verifier models](https://github.com/dscripka/openWakeWord/blob/main/docs/custom_verifier_models.md)  and maybe  [speaker identification](https://github.com/dscripka/openWakeWord/discussions/22). It could also include  [live visualisation](https://huggingface.co/spaces/davidscripka/openWakeWord)  for testing and diagnostics.

## Installation

### Docker

Using Docker CLI

```bash
docker run -d --name openwakeword -p 12202:12202/udp -v /path/to/config/:/config dalehumby/openwakeword-rhasspy
```

In `docker-compose.yml` (or a Docker Swarm stack file)

```yaml
  openwakeword:
    image: dalehumby/openwakeword-rhasspy
    restart: always
    ports:
      - "12202:12202/udp"
    volumes:
      - /path/to/config:/config
```

### Python local install

For testing and experimentation you can run this project locally:

1. Clone the repo `git clone git@github.com:dalehumby/openWakeWord-rhasspy.git` 
2. Create a Python virtul environment _(optional)_
   - `python3 -m venv env`
   - `source env/bin/activate`
3. Install requirements `pip3 install -r requirements.txt`
4. After you've done the [Configuration](README.md#configuration) below
5. Run `python3 detect.py`

## Configuration

1. Create a file called `config.yaml`, for example `nano /path/to/config/config.yaml`
2. Paste the contents of [`config.yaml.example`](config.yaml.example) into `config.yaml` to get started

### UDP Ports

Rhasspy streams audio from its microphone to openWakeWord over the network using the UDP protocol. On each Rhasspy device that has a microhone attached (typically a [Satellite](https://rhasspy.readthedocs.io/en/latest/tutorials/#shared-mqtt-broker)) go to Rhasspy - Settings - Audio Recording and in `UDP Audio (Output)` insert the IP address of the host that's running openWakeWord, and choose a port number, usually starting at `12202`. If you have multiple Rhasspy devices then each device needs its own port number, `12202`, `12203`, `12204`, etc.

![Screenshot 2023-05-01 at 11 34 39](https://user-images.githubusercontent.com/5817143/235435660-23b847b9-2cd4-4800-bb54-3f8d415185e4.png)

In openWakeWord `config.yaml`, `udp_ports` has kay:value pairs. The key is the `siteId` shown at the top of Rhasspy - Settings. It might be: `base`, `satellite`, `kitchen`, or `bedroom`, etc. The value is the port listed under Rhasspy - Settings - Audio Recording.

```yaml
udp_ports:
  base: 12202
  kitchen: 12203
  bedroom: 12204
```

If you are using Docker you need to open the ports to allow UDP network traffic into the container. 

Using Docker CLI 

```bash
docker run -d --name openwakeword -p 12202:12202/udp -p 12203:12203/udp -p 12204:12204/udp -v /path/to/config/:/config dalehumby/openwakeword-rhasspy
```

Or in `docker-compose.yml`

```yaml
  openwakeword:
    image: dalehumby/openwakeword-rhasspy
    restart: always
    ports:
      - "12202:12202/udp"  # base
      - "12203:12203/udp"  # kitchen
      - "12204:12204/udp"  # bedroom
      # ... etc
    volumes:
      - /path/to/config:/config
```

### MQTT

openWakeWord notifies Rhasspy that a wake-word has been spoken using the [Hermes MQTT](https://rhasspy.readthedocs.io/en/latest/wake-word/#mqtthermes) protocol. The MQTT broker needs to be accessible by both Rhasspy and openWakeWord. Rhasspy's internal MQTT broker is not reachable from outside of Rhasspy, so you will need to run a [shared broker](https://rhasspy.readthedocs.io/en/latest/tutorials/#shared-mqtt-broker), like [Mosquitto](https://mosquitto.org/).

Once the broker is running, go to Rhasspy - Settings - MQTT. Choose `External` broker, set the IP address of the `Host` that the broker is running on, the `Port` number, and the `Username`/`Password` if required, similar to:

![Screenshot 2023-04-30 at 18 25 56](https://user-images.githubusercontent.com/5817143/235364431-75d50e0a-2e11-413f-96ff-66c76c83ac6d.png)

openWakeWord `config.yaml` would then have:

```yaml
mqtt:
  broker: 10.0.0.10
  port: 1883
  username: yourusername  # Delete row if not required
  password: yourpassword  # Delete row if not required

```

On each Rhasspy, in Rhasspy - Settings - Wake Word, set `Hermes MQTT`, like

![Screenshot 2023-04-30 at 19 06 45](https://user-images.githubusercontent.com/5817143/235366440-2fd5fcc7-d049-447c-aabc-fd710939ac18.png)

### openWakeWord

openWakeWord listens for all wake-words like "alexa", "hey mycroft", "hey jarvis", and [others](https://github.com/dscripka/openWakeWord#pre-trained-models). These settings ensure Rhasspy is only activated once per wake-word, and help reduce false activations.

```yaml
oww:
  activation_samples: 3  # Number of samples in moving average
  activation_threshold: 0.7  # Trigger wakeword when average above this threshold
  deactivation_threshold: 0.2  # Do not trigger again until average falls below this threshold
  # OWW config, see https://github.com/dscripka/openWakeWord#recommendations-for-usage
  vad_threshold: 0.5
  enable_speex_noise_suppression: false
```

In the example above, the latest 3 audio samples received over UDP are averaged together, and if the average confidence that a wake-word has been spoken is above 0.7 (70%), then Rhasspy is notified. Rhasspy will not be notified again until the average confidence drops below 0.2 (20%), i.e. the wake-word has ended.

Settings for voice activity detection (VAD) and noise suppression are also provided. See openWakeWord's [Recommendations for Usage](https://github.com/dscripka/openWakeWord#recommendations-for-usage).

## Contributing
Feel free to open an Issue if you have a problem, need help or have an idea. PRs always welcome.
