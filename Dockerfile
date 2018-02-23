FROM python:3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        cron \
        nano \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .

RUN crontab crontab

CMD ["cron", "-f"]
