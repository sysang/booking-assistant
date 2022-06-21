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
