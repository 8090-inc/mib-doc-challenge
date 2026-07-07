FROM python:3.12-slim

WORKDIR /app
COPY run.sh solution.py /app/
RUN chmod +x /app/run.sh

ENTRYPOINT ["/app/run.sh"]
