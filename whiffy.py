#!/usr/bin/env python3

#
# Whiffy, a WFS downloader (currently works against Geoserver WFS)
#

import sys, collections, urllib.request, urllib.parse, json, sys
from functioncache import cache_result
from pprint import pprint

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

def retrieve_uri(uri):
    sys.stderr.write(" (get: %s) " % uri)
    sys.stderr.flush()
    req = urllib.request.Request(uri)
    req.add_header('User-Agent', 'potd.py')
    return urllib.request.urlopen(req)

@cache_result
def get_json_data(bbox):
    uri = wrapper.get_uri(bbox)
    fd = retrieve_uri(uri)
    return fd.read()

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
            params['bbox'] = '%f,%f,%f,%f' % (bbox.sw.lng, bbox.sw.lat, bbox.ne.lng, bbox.ne.lat)
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

        # go through and get our data. if we hit the query limit (acceptance function returns False)
        # we split the bbox into four, and recurse (effectively)
        accepted = {}
        queue = [(0, bounds)]
        depth = 0
        while queue:
            pending = []
            for i, (depth, bbox) in enumerate(queue):
                sys.stderr.write("[%d/%d @ %d :%d] %s" % (i, len(queue), depth, len(pending), str(bbox)))
                sys.stderr.flush()
                json_data = get_json_data(bbox)
                try:
                    geom_data = json.loads(json_data.decode('utf8'))
                except ValueError:
                    sys.stderr.write("Invalid data:", json_data)
                    sys.stderr.flush()
                    raise
                sys.stderr.write(" -> %d\n" % (len(geom_data['features'])))
                sys.stderr.flush()
                if acceptance_fn(geom_data):
                    accepted[bbox] = geom_data
                else:
                    pending += [(depth+1, t) for t in quad_split(bbox)]
            queue = pending

        # debug plot of how the recursion worked
        plot(bounds, list(accepted.keys()))
        # combine into one result, then return it (as GeoJSON)
        combined = { }
        combined['features'] = features = []
        seen_uids = set()
        dups = 0
        for geom_data in accepted.values():
            nfeat = len(geom_data['features'])
            if nfeat == 0:
                continue
            for k, v in geom_data.items():
                if k == 'features':
                    for feat in v:
                        uid = feat['properties']['gid']
                        if uid not in seen_uids:
                            seen_uids.add(uid)
                            features.append(v)
                        else:
                            dups += 1
                elif k == 'bbox':
                    continue
                else:
                    if k in combined:
                        assert(combined[k] == v)
                    else:
                        combined[k] = v
        sys.stderr.write("done! dumping GeoJSON to stdout; %d geoms, %d dups (%.2f%%)\n" % 
                (len(combined['features']), dups, 100. * len(combined['features']) / (dups+len(combined['features']))))
        sys.stderr.flush()
        json.dump(combined, sys.stdout)

if __name__ == '__main__':
    wrapper = WfsWrapper('https://www2.landgate.wa.gov.au/ows/wfspublic_4283/wfs', 'WCORP-001')
    wrapper.get_everything(BBox(ne=LatLng(-14, 129), sw=LatLng(-35, 112)), 
            lambda geom_data: len(geom_data['features']) < 5000)

