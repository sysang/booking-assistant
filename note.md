# SSL Setup using acme.sh
wget -O -  https://get.acme.sh | sh -s email="sysangtiger@gmail.com" --install --force --home /etc/certbot  
/root/.acme.sh/acme.sh --issue -d dsysang.site --nginx /etc/nginx/conf.d/rasax.nginx --home /etc/certbot/ --server buypass --force  
/root/.acme.sh/acme.sh --install-cert -d dsysang.site --cert-file /etc/certs/fullchain.pem --key-file /etc/certs/privkey.pem --home /etc/certbot/