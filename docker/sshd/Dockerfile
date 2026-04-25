FROM alpine:3.19

RUN apk add --no-cache openssh bash

# Create tunnel user — no shell, only for port forwarding
RUN addgroup -S tunnel && \
    adduser -S -G tunnel -s /sbin/nologin -h /home/tunnel tunnel && \
    mkdir -p /home/tunnel/.ssh && \
    chmod 700 /home/tunnel/.ssh && \
    chown tunnel:tunnel /home/tunnel/.ssh

# Store sshd_config outside the /etc/ssh volume so it's always fresh from the image
COPY sshd_config /etc/sshd_config.image
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
