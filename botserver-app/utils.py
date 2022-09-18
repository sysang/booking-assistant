import random


FORMAT = {
    'no_space_no_country_code': 1,
    'space_no_country_code': 2,
    'no_space_country_code': 3,
    'space_country_code': 4,
}

def generate_phone_numbers(format, country_code=''):
    codes = [300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 320, 321, 322, 323, 324, 325, 326, 330, 331, 332, 333, 334, 335, 336, 337, 340, 341, 342, 343, 344, 345, 346, 347, 348, 349, 355, 364]

    phone_numbers = []
    for code in codes:
        for i in range(3):
                n = ''.join([str(random.randrange(0, 10, 1)) for i in range(7)])
                prefix = str(code)
                phone_numbers.append(prefix + n)


    for number in phone_numbers:

        if format == FORMAT['no_space_no_country_code']:
            print(f"- {number}")

        if format == FORMAT['space_no_country_code']:
            print(f"- {number[0:3]} {number[3:]}")

        if format == FORMAT['no_space_country_code']:
            print(f"- {country_code}{number}")

        if format == FORMAT['space_country_code']:
            print(f"- {country_code} {number[0:3]} {number[3:]}")


generate_phone_numbers(country_code='+92', format=4)
