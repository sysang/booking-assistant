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
    "search_location_result_little_corn": load_data(filename='search_location_result_little_corn.json'),
}

area_district = {
    "search_location_result_san_francisco_north": load_data(filename='search_location_result_san_francisco_north.json'),
    "search_location_result_ho_chi_minh_city_district_1": load_data(filename='search_location_result_ho_chi_minh_city_district_1.json'),
}

area_exact = {
    "search_location_result_rocky_mountain_resort": load_data(filename='search_location_result_rocky_mountain_resort.json'),
    "search_location_result_hambug": load_data(filename='search_location_result_hambug.json'),
    "search_location_result_boston_us": load_data(filename='search_location_result_boston_us.json'),
    "search_location_result_mexico_city_new_york": load_data(filename='search_location_result_mexico_city_new_york.json'),
}

area_country = {
    "search_location_result_essex": load_data(filename='search_location_result_essex.json'),
}

area_region = {
    "search_location_result_essex": load_data(filename='search_location_result_essex.json'),
}

area_notype_notexact_landmark = {
    "search_location_result_phra_nang": load_data(filename='search_location_result_phra_nang.json'),
}

area_notype_notexact_region = {
    "search_location_result_tameside": load_data(filename='search_location_result_tameside.json'),
    "search_location_result_continental_vietnam": load_data(filename='search_location_result_continental_vietnam.json'),
}

area_notype_notexact_hotel = {
    "search_location_result_san_francisco_north": load_data(filename='search_location_result_san_francisco_north.json'),
}
