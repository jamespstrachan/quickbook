FROM python:3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

RUN echo "deb https://dl.bintray.com/sobolevn/deb git-secret main" | tee -a /etc/apt/sources.list
RUN wget -qO - https://api.bintray.com/users/sobolevn/keys/gpg/public.key | apt-key add -

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git-secret \
        nano \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .

CMD ["bash"]
