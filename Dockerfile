FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    git-lfs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY detect.py .

CMD [ "python3", "-u", "detect.py", "-c", "/config/config.yaml"]
