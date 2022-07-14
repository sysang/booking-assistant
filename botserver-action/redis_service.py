import redis


def set_cache(key, data):
    pool = redis.ConnectionPool(host='redis', port=6379, db=0,  password='qwer1234')
    r = redis.Redis(connection_pool=pool)
    r.set(key, data)


def get_cache(key):
    pool = redis.ConnectionPool(host='redis', port=6379, db=0,  password='qwer1234')
    r = redis.Redis(connection_pool=pool)
    return r.get(key)
