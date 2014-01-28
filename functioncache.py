
# Copyright 2013 Grahame Bowland
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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

