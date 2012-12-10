
from hashlib import sha1
import os.path, pickle, urllib.parse

cache_path = './cache/'
def cache_result(fn):
    def _wrapped(*args, **kwargs):
        arg_hash = sha1()
        arg_hash.update(pickle.dumps(args))
        arg_hash.update(pickle.dumps(kwargs))
        cache_file = os.path.join(cache_path, urllib.parse.quote(fn.__name__) + '.' + arg_hash.hexdigest())
        try:
            with open(cache_file, 'rb') as fd:
                c_args, c_kwargs, rv = pickle.load(fd)
                assert(c_args == args)
                assert(c_kwargs == kwargs)
                return rv
        except IOError:
            pass
        rv = fn(*args, **kwargs)
        with open(cache_file+'.tmp', 'wb') as fd:
            pickle.dump((args, kwargs, rv), fd)
        os.rename(cache_file+'.tmp', cache_file)
        return rv
    return _wrapped

