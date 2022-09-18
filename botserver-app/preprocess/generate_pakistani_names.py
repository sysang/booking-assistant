import io
import random
from ruamel.yaml import YAML
yaml = YAML(typ="safe", pure=True)

with open('pakistani_given_family_names.yml') as file:
    data = yaml.load(file)

family_names = data['family_names']
female_given_names = data['female_given_names']
male_given_names = data['male_given_name']

full_names = []

def generate_names(given_names, surnames):
    for given in given_names:
        for surname in surnames:
            if given != surname:
                name = f"{given} {surname}"
                if name not in full_names:
                    full_names.append(name)


generate_names(given_names=female_given_names, surnames=family_names+male_given_names)
generate_names(given_names=male_given_names, surnames=family_names)

random.shuffle(full_names)

expression_name = {
    'version': '3.1',
    'nlu': [
        {
            'intent': 'expression_name',
            'examples': [ f"[{name}](full_name)" for name in full_names[0:1000]]
        }
    ]
}

# with open('expression_name.yml', 'w') as handle:
#     buf = io.BytesIO()
#     yaml.dump(expression_name, buf)
#     handle.write(buf.getvalue().decode('utf-8'))

lookup_name = {
    'version': '3.1',
    'nlu': [
        {
            'lookup': 'full_name',
            'examples': full_names
        }
    ]
}

with open('lookup_name.yml', 'w') as handle:
    yaml = YAML()
    buf = io.BytesIO()
    yaml.dump(lookup_name, buf)
    handle.write(buf.getvalue().decode('utf-8'))
