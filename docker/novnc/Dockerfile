FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-websockify \
    novnc \
    && rm -rf /var/lib/apt/lists/*

# noVNC static files are at /usr/share/novnc
# websockify binary at /usr/bin/websockify

RUN mkdir -p /tokens
VOLUME ["/tokens"]

EXPOSE 6080

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
