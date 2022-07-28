import json
from pathlib import Path

raw_data_dir = Path(__file__).parent / 'raw_data'
search_location_result_essex_json_file = raw_data_dir / 'search_location_result_essex.json'
search_location_result_bullock_json_file = raw_data_dir / 'search_location_result_bullock.json'
search_location_result_san_francisco_north_json_file = raw_data_dir / 'search_location_result_san_francisco_north.json'

area_type_hotel = {
    'search_location_result_essex': json.loads(search_location_result_essex_json_file.read_text()),
}

area_type_landmark = {
    'search_location_result_bullock': json.loads(search_location_result_bullock_json_file.read_text()),
}

area_type_city = {
    'search_location_result_essex': json.loads(search_location_result_essex_json_file.read_text()),
}

area_district = {
    'search_location_result_san_francisco_north': json.loads(search_location_result_san_francisco_north_json_file.read_text()),
}
