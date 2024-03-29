# SSL Setup using acme.sh
wget -O -  https://get.acme.sh | sh -s email="sysangtiger@gmail.com" --install --force --home /etc/certbot  
/etc/certbot/acme.sh --issue -d dsysang.site --nginx /etc/nginx/conf.d/rasax.nginx --home /etc/certbot/ --server buypass --force  
/etc/certbot/acme.sh --install-cert -d dsysang.site --fullchain-file /etc/certs/fullchain.pem --key-file /etc/certs/privkey.pem --home /etc/certbot/

docker exec rasachatbot-nginx-1 bash -c '/etc/certbot/acme.sh --issue -d dsysang.site --nginx /etc/nginx/conf.d/rasax.nginx --home /etc/certbot/ --server buypass'
docker exec rasachatbot-nginx-1 bash -c '/etc/certbot/acme.sh --install-cert -d dsysang.site --fullchain-file /etc/certs/fullchain.pem --key-file /etc/certs/privkey.pem --home /etc/certbot/'

docker exec rasachatbot-nginx-1 bash -c '/etc/certbot/acme.sh --issue -d cs.dsysang.site --nginx /etc/nginx/conf.d/chatwoot.nginx --home /etc/certbot/ --server buypass'
docker exec rasachatbot-nginx-1 bash -c '/etc/certbot/acme.sh --install-cert -d cs.dsysang.site --fullchain-file /etc/certs/cs.fullchain.pem --key-file /etc/certs/cs.privkey.pem --home /etc/certbot/'

# botfrontend static file
docker exec rasachatbot-botfrontend-1 bash -c 'python manage.py collectstatic --noinput'

# To inspect training dataset
```python
from rasa.core.training import load_data
from rasa.shared.core.domain import Domain
import asyncio

domain = Domain.from_file('domain.yml')
training_trackers = asyncio.run(load_data(resource_name='data', domain=domain, augmentation_factor=0))

interpreter = create_interpreter('/tmp/tmp01_hudjq/nlu')  # trained nlu model
tracker_state_features, label_ids, entity_tags = ted._featurize_for_training(training_trackers, domain, interpreter)
```

```python
sample_no = 0
for tracker_state, label in zip(tracker_state_features, label_ids):
  print('\nsample: ', sample_no)
  print('label: ', label)
  print('features: ')
  for features in tracker_state:
    print(features.keys())
  sample_no += 1
```

# Docker fails to connect with archive.ubuntu.com, https://mklasen.com/docker-fails-to-connect-with-archive-ubuntu-com/
`sudo nvim /etc/docker/daemon.json`
`{"dns": ["192.168.1.1"]}`
`sudo service docker restart`

# Build rasa:localdev for old processor which does not support new computing instruction set
- rasa-3.2.1, tensorflow-2.7.3
  + `wget https://github.com/RasaHQ/rasa/archive/refs/tags/3.2.1.tar.gz`
  + `wget https://github.com/tensorflow/tensorflow/archive/refs/tags/v2.7.3.tar.gz`
  + use Dockerfile-tf-v2.7.3 to build image -> sysang/tf-2.7.3-source-build
  + replace base image in rasa-3.2.1/docker/Dockerfile.base by sysang/tf-2.7.3-source-build:latest
  + replace rasa-3.2.1/Dockerfile by Dockerfile-rasa-3.2.1, use Dockerfile-rasa-3.2.1 to build rasa:localdev
  + (replace peotry.lock by peotry-rasa-3.2.1.lock which is resolved by pyproject.toml after exclude tensorflow section and set numpy===1.21.4)

# To make nlu training cache has chane to happen -> terminate `rasa train` when it come train core
(a trick to overcome a tricky bug, it caches nlu part for combining just only for curren  process, not for reusing in other process)

# IMPOTANT: remember to run `make copyaddons`

# Facebook Messenger Chanell
- Reference: https://developers.facebook.com/docs/messenger-platform/webhooks
- Reference: https://developers.facebook.com/docs/graph-api/reference/v14.0/app/subscriptions#readperms
- Reference: https://developers.facebook.com/docs/facebook-login/guides/access-tokens#apptokens
- Reference: https://rasa.com/docs/rasa/connectors/facebook-messenger
- Go to https://developers.facebook.com/ -> [create app] -> (Business) -> [Messenger]
- Go to Settings -> Basic -> use: App ID, App Secret
- Go to Messenger -> Setting -> add page, add callback url, copy page access token to `page-access-token`
- Go to Messenger -> Setting (Webhooks) to subsribe `message` filed for webhook

# Setting domain session_expiration_time has no effect
- issue: https://github.com/RasaHQ/rasa/issues/11061
- advise: https://github.com/RasaHQ/rasa/issues/11061#issuecomment-1119870053
- `nvim /opt/venv/lib/python3.8/site-packages/rasa/shared/constants.py`, DEFAULT_SESSION_EXPIRATION_TIME_IN_MINUTES -> False

# chatwoot
- Be for running `docker compose up -d` prepare the database by running the migrations by `docker compose run --rm rails bundle exec rails db:chatwoot_prepare`
- Access Rails console, `docker exec -it chatwoot_rails_1 bundle exec rails c`
- (optional) `chmod 777 -R mounts/cw/storage`
- (optional) `chmod 777 -R mounts/cwdb`
- (optional) `rm -rf mounts/cwdb/*`
- Add AgentBot: https://www.chatwoot.com/docs/product/others/agent-bots
> `bot = AgentBot.create!(name: "Rasa Chatbot for Website", outgoing_url: "http://rasa-production:5005/webhooks/chatwoot/cwwebsite")`
> `bot.access_token.token`
> `AgentBotInbox.create!(inbox: Inbox.find(1), agent_bot: AgentBot.find(1))`
- Super admin Console
> https://www.chatwoot.com/docs/self-hosted/monitoring/super-admin-sidekiq/
> `docker exec -it chatwoot_rails_1 bundle exec rails c`
> `s = SuperAdmin.create!(email: 'sysangtiger@gmail.com', password: 'Qwer!234', name: 'Admin')`
> `s.confirm`
> `https://cs.dsysang.site/super_admin/sign_in`
- Fix the way chatwoot request to sendMessage api
> `sudo docker cp telegram.rb rasachatbot-sidekiq-1:/app/app/models/channel/telegram.rb`
