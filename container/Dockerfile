# Debian 12 supplies an actual ABI-5 ncurses package. No game content enters the image.
FROM --platform=linux/amd64 debian:bookworm-20261027-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
ARG DEBIAN_FRONTEND=noninteractive
# Date-pinned package snapshot; apt still authenticates the signed archive metadata.
RUN rm -f /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20261101T000000Z bookworm main' > /etc/apt/sources.list \
    && apt-get -o Acquire::https::Verify-Peer=true update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl python3 libncurses5=6.4-4 libstdc++6 zlib1g binutils file iproute2 \
    && readelf -d /lib/x86_64-linux-gnu/libncurses.so.5 | grep -F '[libncurses.so.5]' \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -d /home/container -s /bin/bash container
COPY container/entrypoint.sh /entrypoint.sh
COPY container/supervise.py /supervise.py
RUN chmod 0755 /entrypoint.sh
# Wings runs game containers as its per-server UID. Keep the image default as
# root so the same image can also execute the panel installer against a
# root-owned volume before publishing files for the runtime UID.
ENV USER=container HOME=/home/container LANG=C TERM=xterm
WORKDIR /home/container
STOPSIGNAL SIGINT
ENTRYPOINT ["/entrypoint.sh"]
