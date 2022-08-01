FROM nginx:1.23.1

RUN openssl dhparam -out /etc/nginx/dhparam.pem 1024

RUN apt-get update && apt-get upgrade -y && apt-get install -y lsb-release \
	 wget \
	 && rm -rf /var/lib/apt/lists/*

RUN wget -O -  https://get.acme.sh | sh -s email="sysangtiger@gmail.com" --install --force --home /etc/certbot

RUN mkdir -p /var/static
