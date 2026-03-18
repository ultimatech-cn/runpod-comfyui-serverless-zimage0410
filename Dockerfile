FROM runpod/worker-comfyui:5.7.1-base-cuda12.8.1

ENV COMFYUI_PATH=/comfyui
ENV DEBIAN_FRONTEND=noninteractive

COPY handler.py /handler.py
COPY src/start.sh /start.sh
COPY scripts/comfy-node-install.sh /usr/local/bin/comfy-node-install
COPY scripts/comfy-manager-set-mode.sh /usr/local/bin/comfy-manager-set-mode
COPY scripts/install-custom-nodes.sh /usr/local/bin/install-custom-nodes
COPY project-config /project-config

RUN chmod +x /start.sh /usr/local/bin/comfy-node-install /usr/local/bin/comfy-manager-set-mode /usr/local/bin/install-custom-nodes && \
    sed -i 's/\r$//' /start.sh /usr/local/bin/comfy-node-install /usr/local/bin/comfy-manager-set-mode /usr/local/bin/install-custom-nodes

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        git \
        unzip \
        ffmpeg \
        curl \
        ca-certificates \
        build-essential \
        g++ \
        python3-dev && \
    rm -rf /var/lib/apt/lists/*

RUN git config --global --add safe.directory '*' && \
    git config --global credential.helper '' && \
    git config --global url."https://github.com/".insteadOf git@github.com: && \
    git config --global http.sslVerify true && \
    git config --global http.postBuffer 524288000

RUN install-custom-nodes /project-config/custom-nodes.txt
