# SSL Setup using acme.sh
wget -O -  https://get.acme.sh | sh -s email="sysangtiger@gmail.com" --install --force --home /etc/certbot  
/etc/certbot/acme.sh --issue -d dsysang.site --nginx /etc/nginx/conf.d/rasax.nginx --home /etc/certbot/ --server buypass --force  
/etc/certbot/acme.sh --install-cert -d dsysang.site --fullchain-file /etc/certs/fullchain.pem --key-file /etc/certs/privkey.pem --home /etc/certbot/

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
