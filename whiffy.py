#!/usr/bin/env python3

#
# Whiffy, a WFS downloader (currently works against Geoserver WFS)
#

import sys, collections, urllib.request, urllib.parse, json
from functioncache import cache_result
from pprint import pprint

LatLng = collections.namedtuple('LatLng', ('lat', 'lng'))
BBox = collections.namedtuple('BBox', ('ne', 'sw'))

def retrieve_uri(uri):
    sys.stderr.write("retrieving: %s\n" % uri)
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

    def get_everything(self, bbox, acceptance_fn):
        def quad_split(bbox):
            h = bbox.ne.lat - bbox.sw.lat
            w = bbox.ne.lng - bbox.sw.lng
            return [ BBox(bbox.sw, LatLng(bbox.sw.lat + h/2, bbox.sw.lng + w/2)), 
                     BBox(LatLng(bbox.sw.lat, bbox.sw.lng + w/2), LatLng(bbox.sw.lat + h/2, bbox.ne.lng)), 
                     BBox(LatLng(bbox.sw.lat + h/2, bbox.sw.lng), LatLng(bbox.ne.lat, bbox.sw.lng + w/2)), 
                     BBox(LatLng(bbox.sw.lat + h/2, bbox.sw.lng + w/2), LatLng(bbox.ne.lat, bbox.ne.lng)) ]

        bbox_data_ok = {}
        queue = [bbox]
        while queue:
            pending = []
            pprint(queue)
            for bbox in queue:
                print("GET", bbox)
                json_data = get_json_data(bbox)
                try:
                    geom_data = json.loads(json_data.decode('utf8'))
                except ValueError:
                    print("Invalid data:", json_data)
                    raise
                if acceptance_fn(geom_data):
                    bbox_data_ok[bbox] = geom_data
                else:
                    pending += quad_split(bbox)
            queue = pending

if __name__ == '__main__':
    wrapper = WfsWrapper('https://www2.landgate.wa.gov.au/ows/wfspublic_4283/wfs', 'WCORP-001')
    wrapper.get_everything(BBox(ne=LatLng(-14, 129), sw=LatLng(-35, 112)), 
            lambda geom_data: len(geom_data['features']) < 5000)
