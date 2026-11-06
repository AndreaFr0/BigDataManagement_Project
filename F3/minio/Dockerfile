FROM alpine:3.20

COPY minio /usr/local/bin/minio

RUN chmod +x /usr/local/bin/minio

EXPOSE 9000 9001

ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data", "--console-address", ":9001"]
