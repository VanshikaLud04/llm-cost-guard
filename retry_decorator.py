import time
import random
from functools import wraps

def retry(max_attempts=3):
    def decorator(func) :
        @wraps(func)
        def wrapper(*args, **kwargs) :
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)  
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise 
                    wait = (2 ** attempt) + random.random()  
                    time.sleep(wait)
            pass
        return wrapper
    return decorator