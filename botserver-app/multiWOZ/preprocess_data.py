import json
from datasets import load_dataset

storage_dir = 'hotel_setting/%s'
DOMAIN_FILTER = 'hotel'
dataset = load_dataset('multi_woz_v22', split='train')

encoder = json.JSONEncoder()

counter = 0
for item in dataset:
    services = item['services']
    dialogue_id = item['dialogue_id']
    storage_path = storage_dir % (dialogue_id)
    if DOMAIN_FILTER in services and len(services) == 1:
        counter += 1
        print('Processed file number: ', counter)

        encoded = encoder.encode(item)
        with open(storage_path, 'a') as file:
            file.write(encoded)



