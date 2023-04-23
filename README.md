# openWakeWord for Rhasspy 

[openWakeWord](https://github.com/dscripka/openWakeWord) is an open-source library for detecting common wake-words like "alexa", "hey mycroft", "hey jarvis", and [other models](https://github.com/dscripka/openWakeWord#pre-trained-models). [Rhasspy](https://rhasspy.readthedocs.io/en/latest/) is an open-source voice assistant. openWakeWord is not bundled into Rhasspy. 

This project runs openWakeWord as a stand-alone Docker service, which receives audio from Rhasspy, detects when a wake-word is said, and then notifies Rhasspy.
