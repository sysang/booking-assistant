# SSL Setup using acme.sh
wget -O -  https://get.acme.sh | sh -s email="sysangtiger@gmail.com" --install --force --home /etc/certbot  
/root/.acme.sh/acme.sh --issue -d dsysang.site --nginx /etc/nginx/conf.d/rasax.nginx --home /etc/certbot/ --server buypass --force  
/root/.acme.sh/acme.sh --install-cert -d dsysang.site --cert-file /etc/certs/fullchain.pem --key-file /etc/certs/privkey.pem --home /etc/certbot/

# Trigger intent from custom action
https://forum.rasa.com/t/trigger-intent-from-custom-action/51727/6

# Rule data (Rule-based Policies)
Training data must declare condition (slot information), otherwise training machenisim will impose initinal slot information as condition (very implicit).  
This makes rules (were not declare condition) mostly uneffective in runtime because the condition mostly would have been changed.

# It seems that action without preceded intent is ingored
