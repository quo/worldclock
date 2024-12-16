#!/usr/bin/python3

import sys, gzip, pickle, time, shapefile, shapely

PRECISION = 8

def record_to_polygons(sr):
	# convert shapefile record to shapely geometry
	geo = sr.shape.__geo_interface__
	if geo['type'] == 'Polygon': polygons = [geo['coordinates']]
	elif geo['type'] == 'MultiPolygon': polygons = geo['coordinates']
	else: raise Exception('unsupported shape type ' + geo['type'])
	for rings in polygons:
		shell, *holes = (shapely.LinearRing([(x*PRECISION,y*PRECISION) for x,y in r]) for r in rings)
		p = shapely.Polygon(shell, holes)
		try:
			p = shapely.set_precision(p, grid_size=1)
			yield p
		except Exception as ex:
			print('WARNING: Fixing invalid polygon %i (%r, %i ext pts, %i holes, %i hole pts)' %
				(sr.shape.oid, ex, len(shell.coords), len(holes), sum(len(h.coords) for h in holes)))
			try:
				p = shapely.simplify(p, 0.1) # XXX make_valid() doesn't seem to help?
				p = shapely.set_precision(p, grid_size=1)
				yield p
			except Exception as ex:
				print('ERROR: Failed to fix polygon!', ex)

def read_shapes(fn, ycutoff, groupfn):
	print('Reading', fn, '...')
	reader = shapefile.Reader(fn)
	records = reader.shapeRecords()
	print('Processing...')
	groups = {}
	last = 0
	for i, sr in enumerate(records):
		group = groupfn(sr)
		for p in record_to_polygons(sr):
			if p is not None:
				minx, miny, maxx, maxy = p.bounds
				if maxy > ycutoff*PRECISION:
					groups.setdefault(group, []).append(p)
		# show progress
		tm = time.time()
		if tm - last > 1 or i+1 == len(records):
			print('\r%6.2f%% (%i/%i) ' % ((i+1)/len(records)*100, i+1, len(records)), end='')
			last = tm
	print()
	return { g: shapely.union_all(p, grid_size=1) for g,p in groups.items() }

def iter_polygons(g):
	if isinstance(g, shapely.Polygon):
		if len(g.exterior.coords) > 2:
			p = shapely.geometry.polygon.orient(g)
			yield [(round(x),round(y)) for x,y in p.exterior.coords]
			for i in p.interiors:
				if len(i.coords) > 2:
					yield [(round(x),round(y)) for x,y in i.coords]
	elif isinstance(g, shapely.MultiPolygon):
		for x in g.geoms: yield from iter_polygons(x)
	elif isinstance(g, shapely.GeometryCollection):
		for x in g.geoms: yield from iter_polygons(x)
	#else: print('WARNING: Ignoring unsupported geometry', type(g).__name__)

def make_zones(tz, land):
	for tzid,mp in sorted(tz.items()):
		print(tzid)
		mp = shapely.intersection(mp, land, grid_size=1)
		polygons = list(iter_polygons(mp))
		if polygons: yield (tzid, polygons)
	notz = shapely.difference(land, shapely.union_all(list(tz.values()), grid_size=1), grid_size=1)
	polygons = list(iter_polygons(notz))
	if polygons: yield ('', polygons)

if __name__ == '__main__':
	# usage: ./convert.py timezones.shapefile.zip land-polygons-complete-*.zip
	_, tzfile, landfile = sys.argv

	tz = read_shapes(tzfile, -60, lambda sr: sr.record.tzid)
	tz = { t:s for t,s in tz.items() if not t.startswith('Etc/') }

	land = read_shapes(landfile, -999, lambda sr: None)[None]
	shapely.prepare(land)

	zones = list(make_zones(tz, land))

	print('Writing...')
	with gzip.GzipFile('tz_world.pickled.gz', 'wb') as out:
		pickle.dump((PRECISION, zones), out)
	print('Done!')

