import json
from pathlib import Path

area_type_hotel = {
    'phra_nang': json.loads(Path('raw_data/phra_nang.json').read_text()),
}
