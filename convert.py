#!/usr/bin/python3

import zipfile, gzip, io, shapefile, pickle

PRECISION = 8

def simplify(pts):
	ret = []
	px, py = pts[-1]
	pdx = None
	for x, y in pts:
		dx = x-px
		dy = y-py
		if dx or dy:
			if pdx is None or dx*pdy != dy*pdx:
				ret.append((px, py))
				pdx = dx
				pdy = dy
			px = x
			py = y
	return ret

def read_shapes():
	with zipfile.ZipFile('tz_world.zip') as z:
		r = shapefile.Reader(**{
			ext: io.BytesIO(z.read('world/tz_world.'+ext))
			for ext in ['shp', 'shx', 'dbf']
		})
	tzid_col, = (i for i, (name, _, _, _) in enumerate(r.fields, -1) if name == 'TZID')
	shapes = {}
	for sr in r.shapeRecords():
		if sr.shape.shapeType != shapefile.POLYGON:
			raise Exception('found shapeType ' + str(sr.shape.shapeType))
		polygon = simplify([(round(x*PRECISION),round(y*PRECISION)) for x,y in sr.shape.points])
		if len(polygon) > 2:
			shapes.setdefault(sr.record[tzid_col], []).append(polygon)
	return list(shapes.items())

if __name__ == '__main__':
	with gzip.GzipFile('tz_world.pickled.gz', 'wb') as out:
		pickle.dump((PRECISION, read_shapes()), out)

