import math

hotel_id_list = list(range(20))

total_num = len(hotel_id_list)
reqnum_limit = 5
total_page = math.ceil(total_num / reqnum_limit)
schedule = []
for idx in range(total_page):
    start = idx * reqnum_limit
    end = start + reqnum_limit
    schedule.append(hotel_id_list[start:end])

print(schedule)
