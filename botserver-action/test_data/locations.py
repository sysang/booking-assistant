import json
from pathlib import Path


def load_data(filename):
    raw_data_dir = Path(__file__).parent / "raw_data"
    json_file = raw_data_dir / filename
    return json.loads(json_file.read_text())

area_type_hotel = {
    "search_location_result_essex": load_data(filename='search_location_result_essex.json'),
}

area_type_landmark = {
    "search_location_result_bullock": load_data(filename='search_location_result_bullock.json'),
}

area_type_city = {
    "search_location_result_essex": load_data(filename='search_location_result_essex.json'),
}

area_district = {
    "search_location_result_san_francisco_north": load_data(filename='search_location_result_san_francisco_north.json'),
}

area_exact = {
    "search_location_result_rocky_mountain_resort": load_data(filename='search_location_result_rocky_mountain_resort.json'),
}
