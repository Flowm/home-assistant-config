FROM alpine:3.17

RUN apk add wget curl perl bash && \
    mkdir /pcap
COPY pcap.sh /pcap.sh

ENTRYPOINT ["/pcap.sh"]
