import time
from collections import OrderedDict


class MemoryCache:
    def __init__(self, max_size=100, expiration=3600):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.expiration = expiration

    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.expiration:
                self.set(key, value)
                self.cache.move_to_end(key)
                return value
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = (value, time.time())
        self.cache.move_to_end(key)

    def delete(self, key):
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        self.cache.clear()

    def size(self):
        return len(self.cache)

    def all_cache(self):
        return self.cache


thumbnail_cache = MemoryCache()
