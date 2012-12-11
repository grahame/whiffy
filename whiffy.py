#!/usr/bin/env python3

#
# Whiffy, a WFS downloader (currently works against Geoserver WFS)
#

import sys, collections, urllib.request, urllib.parse, json, sys
from functioncache import cache_result

LatLng = collections.namedtuple('LatLng', ('lat', 'lng'))
BBox = collections.namedtuple('BBox', ('ne', 'sw'))

def plot(bounds, done):
    import matplotlib.pylab as pylab
    ax = pylab.gca()
    for bbox in done:
        x = bbox.sw.lng
        y = bbox.sw.lat
        h = bbox.ne.lat - bbox.sw.lat
        w = bbox.ne.lng - bbox.sw.lng
        ax.add_patch(pylab.Rectangle((x,y), w, h, fill=False))
    ax.set_xlim(bounds.sw.lng, bounds.ne.lng)
    ax.set_ylim(bounds.sw.lat, bounds.ne.lat)
    pylab.show()

@cache_result
def retrieve_uri(uri):
    sys.stderr.write(" (get: %s) " % uri)
    sys.stderr.flush()
    req = urllib.request.Request(uri)
    req.add_header('User-Agent', 'potd.py')
    fd = urllib.request.urlopen(req)
    data = fd.read()
    fd.close()
    return data

def next_or_none(it):
    try:
        return next(it)
    except StopIteration:
        return None

def json_listout(fd, it):
    fd.write('[')
    pending = next_or_none(it)
    while pending is not None:
        next_obj = next_or_none(it)
        if pending is not None:
            json.dump(pending, fd)
        if next_obj is not None:
            fd.write(', \n')
        pending = next_obj
        if pending is None:
            break
    fd.write(']\n')

def wfs_bbox(bbox):
    return [ bbox.sw.lng, bbox.sw.lat, bbox.ne.lng, bbox.ne.lat ]

def bbox_format(bbox):
    return '%f,%f,%f,%f' % tuple(wfs_bbox(bbox))

class WfsWrapper:
    def __init__(self, base_uri, typename):
        self.base_uri = base_uri
        self.params = {
                'request' : 'GetFeature',
                'version-1.0.0' : None,
                'outputformat' : 'json',
                'typename' : typename
                }
    
    def get_uri(self, bbox=None):
        params = self.params.copy()
        if bbox is not None:
            params['bbox'] = bbox_format(bbox)
        parts = []
        parts.append(self.base_uri)
        parts.append("?")
        qparts = []
        for k, v in params.items():
            q = urllib.parse.quote(k)
            if v is not None:
                q += "=" + urllib.parse.quote(v)
            qparts.append(q)
        return ''.join(parts) + '&'.join(qparts)

    def get_everything(self, bounds, acceptance_fn):
        def quad_split(bbox):
            h = bbox.ne.lat - bbox.sw.lat
            w = bbox.ne.lng - bbox.sw.lng
            return [ BBox(sw=bbox.sw, ne=LatLng(bbox.sw.lat + h/2, bbox.sw.lng + w/2)), 
                     BBox(sw=LatLng(bbox.sw.lat, bbox.sw.lng + w/2), ne=LatLng(bbox.sw.lat + h/2, bbox.ne.lng)), 
                     BBox(sw=LatLng(bbox.sw.lat + h/2, bbox.sw.lng), ne=LatLng(bbox.ne.lat, bbox.sw.lng + w/2)), 
                     BBox(sw=LatLng(bbox.sw.lat + h/2, bbox.sw.lng + w/2), ne=LatLng(bbox.ne.lat, bbox.ne.lng)) ]

        def get_json_data(bbox):
            uri = self.get_uri(bbox)
            return retrieve_uri(uri)

        def get_geom_data(bbox):
            json_data = get_json_data(bbox)
            try:
                return json.loads(json_data.decode('utf8'))
            except ValueError:
                sys.stderr.write("Invalid data:", json_data)
                sys.stderr.flush()
                raise

        # go through and get our data. if we hit the query limit (acceptance function returns False)
        # we split the bbox into four, and recurse (effectively)
        accepted = []
        queue = [(0, bounds)]
        discarded = 0
        depth = 0
        while queue:
            pending = []
            for i, (depth, bbox) in enumerate(queue):
                sys.stderr.write("[%d/%d @ %d :%d] %s" % (i, len(queue), depth, len(pending), str(bbox)))
                sys.stderr.flush()
                geom_data = get_geom_data(bbox)
                feat_len = len(geom_data['features'])
                sys.stderr.write(" -> %d\n" % (feat_len))
                sys.stderr.flush()
                if acceptance_fn(geom_data):
                    accepted.append(bbox)
                else:
                    pending += [(depth+1, t) for t in quad_split(bbox)]
                    discarded += feat_len
                del geom_data
            queue = pending

        # debug plot of how the recursion worked
        # combine into one result, then return it (as GeoJSON)
        plot(bounds, accepted)
        seen_uids = set()
        # grab the dictionary for the first item
        geom_data = get_geom_data(accepted[0])
        initial_dict = {}
        for k, v in geom_data.items():
            if k == 'features':
                continue
            elif k == 'bbox':
                v = wfs_bbox(bounds)
            initial_dict[k] = v
        initial_str = json.dumps(initial_dict)
        assert(initial_str.endswith('}'))
        sys.stdout.write(initial_str[:-1])
        sys.stdout.write(', "features": ')
        def feature_output():
            written = 0
            dups = 0
            for bbox in accepted:
                geom_data = get_geom_data(bbox)
                features = geom_data['features']
                if len(features) == 0:
                    continue
                for feature in features:
                    uid = feature['properties']['gid']
                    if uid not in seen_uids:
                        seen_uids.add(uid)
                        written += 1
                        if written % 1000 == 0:
                            sys.stderr.write("!")
                            sys.stderr.flush()
                        yield feature
                    else:
                        dups += 1
            sys.stderr.write("output complete: written %d dups %d discarded %d\n" % (written, dups, discarded))
            sys.stderr.flush()
        json_listout(sys.stdout, feature_output())
        sys.stdout.write('}\n')

from config import wfs_servers

if __name__ == '__main__':
    def floats(s):
        return [float(t) for t in s.split(',')]
    wfs_name, typename, latlng1, latlng2, feature_limit = sys.argv[1:]
    feature_limit = int(feature_limit)
    wrapper = WfsWrapper(wfs_servers[wfs_name], typename)
    wrapper.get_everything(BBox(ne=LatLng(*floats(latlng1)), sw=LatLng(*floats(latlng2))), 
            lambda geom_data: len(geom_data['features']) < feature_limit)

