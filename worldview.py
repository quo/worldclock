import sys, datetime, math, cairo, pytz
from gi.repository import GObject, Gtk, Gdk

OUTLINE_STEP = 5

RAD = math.pi/180

COLORS = [
	(.80, .85, .36),
	(.44, .75, .40),
	(.90, .85, .50),
	(.73, .72, .35),
]
def color(offset):
	if offset is None: return .8, .8, .8
	d = offset.total_seconds() / 60 / 60
	f = d % 1
	a = COLORS[int(d) % len(COLORS)]
	if f == 0: return a
	b = COLORS[(int(d)+1) % len(COLORS)]
	return tuple(x*(1-f)+y*f for x,y in zip(a,b))

def get_points_extents(points):
	minx = miny = float('inf')
	maxx = maxy = float('-inf')
	for x, y in points:
		if x < minx: minx = x
		if x > maxx: maxx = x
		if y < miny: miny = y
		if y > maxy: maxy = y
	return minx, miny, maxx, maxy

def get_sun_position(t):
	# adapted from http://www.stargazing.net/kepler/sun.html
	days = (t - datetime.datetime(2000,1,1)).total_seconds() / 60 / 60 / 24 - .5
	# mean longitude of the Sun
	L = (280.461 + .9856474 * days) * RAD % (2*math.pi)
	# mean anomaly of the Sun
	g = (357.528 + .9856003 * days) * RAD
	# ecliptic longitude of the Sun
	lam = L + (1.915 * math.sin(g) + .02 * math.sin(2 * g)) * RAD
	# obliquity of the ecliptic
	obliq = (23.439 - .0000004 * days) * RAD
	# find the RA and DEC of the Sun
	alpha = (math.atan2(math.cos(obliq) * math.sin(lam), math.cos(lam))) % (2*math.pi)
	delta = math.asin(math.sin(obliq) * math.sin(lam))
	# find the equation of time
	equation = (L - alpha) / RAD * 4
	return -delta, -(t.hour+(t.minute+equation)/60)/24 * 2*math.pi

# map projections

def project_rect(x, y):
	return x, y, True

XY = 180**2/3
def project_wagner(x, y):
	x *= math.sqrt(1 - y*y/XY)
	return x, y, True

def make_project_ortho(c):
	def project_ortho(x, y):
		x = min(max(x-c, -90), 90)
		return (
			90 * math.cos(y*RAD) * math.sin(x*RAD),
			90 * math.sin(y*RAD),
			 -85 < x < 85
		)
	return project_ortho

project_ortho_europe = make_project_ortho(20)
project_ortho_america = make_project_ortho(-90)
project_ortho_asia = make_project_ortho(100)

# Wrapper class to bundle tzinfo and polygons
class TimeZone:
	def __init__(self, tzid, polygons):
		self.tzid = tzid
		self.polygons = polygons
		try:
			self.tz = pytz.timezone(tzid)
		except:
			sys.stderr.write('Unknown time zone: %r\n' % tzid)
			self.tz = None
	def time(self, utc):
		if self.tz is None: return None
		return self.tz.fromutc(utc).replace(tzinfo=None)
	def name(self, utc):
		if self.tz is None: return None
		return self.tz.fromutc(utc).tzname()

# A region is a collection of time zones with the same local time at a specific point in time
class Region:
	def __init__(self, offset, name, timezones):
		self.offset = offset
		self.name = name
		self.timezones = frozenset(timezones)
		self.color = color(self.offset)
		self.polygons = [p for tz in timezones for p in tz.polygons]
		self._eq_tup = self.name, self.offset, self.timezones
	def __hash__(self):
		return hash(self._eq_tup)
	def __eq__(self, other):
		return isinstance(other, Region) and self._eq_tup == other._eq_tup
def get_regions(utc, timezones, names):
	groups = {}
	for tz in timezones:
		groups.setdefault((tz.time(utc), tz.name(utc) if names else None), []).append(tz)
	return sorted(
		(Region(None if t is None else t-utc, nm, zg) for (t, nm), zg in groups.items()),
		key=lambda r: (r.offset or datetime.timedelta(), r.name or '')
	)

class WorldView(Gtk.Widget):

	def __init__(self):
		Gtk.Widget.__init__(self)
		self.add_events(Gdk.EventMask.EXPOSURE_MASK)
		self._time = datetime.datetime(1970, 1, 1)
		self._projection = project_rect
		self._timezones = []
		self._show_names = self._show_day_night = False
		self._cur_regions_key = self._cur_map_key = self._cur_map = self._cur_labels = None

	def _get_time(self):
		return self._time
	def _set_time(self, utc):
		if utc != self._time:
			self._time = utc
			self.queue_draw()
	time = property(_get_time, _set_time)

	def _get_projection(self):
		return self._projection
	def _set_projection(self, project):
		if project != self._projection:
			self._projection = project or project_rect
			self.queue_draw()
	projection = property(_get_projection, _set_projection)

	def _get_timezones(self):
		return self._timezones
	def _set_timezones(self, zones):
		self._timezones = zones
		self.queue_draw()
	timezones = property(_get_timezones, _set_timezones)

	def _get_show_names(self):
		return self._show_names
	def _set_show_names(self, b):
		self._show_names = b
		self.queue_draw()
	show_names = property(_get_show_names, _set_show_names)

	def _get_show_day_night(self):
		return self._show_day_night
	def _set_show_day_night(self, b):
		self._show_day_night = b
		self.queue_draw()
	show_day_night = property(_get_show_day_night, _set_show_day_night)

	def do_realize(self):
		self.set_realized(True)
		a = Gdk.WindowAttr()
		a.x = self.get_allocation().x
		a.y = self.get_allocation().y
		a.width = self.get_allocation().width
		a.height = self.get_allocation().height
		a.window_type = Gdk.WindowType.CHILD
		a.wclass = Gdk.WindowWindowClass.INPUT_OUTPUT
		a.event_mask = self.get_events()
		self.set_window(Gdk.Window(self.get_parent_window(), a, Gdk.WindowAttributesType.X|Gdk.WindowAttributesType.Y))
		self.get_window().set_user_data(self)
		self.get_style_context().set_background(self.get_window())
		self.size_allocate(self.get_allocation())

	def draw_outline(self, cr):
		project = self.projection
		cr.move_to(*project(-180, -90)[:2])
		for y in range(-90, 90, OUTLINE_STEP): cr.line_to(*project(180, y)[:2])
		cr.line_to(*project(180, 90)[:2])
		for y in range(90, -90, -OUTLINE_STEP): cr.line_to(*project(-180, y)[:2])
		cr.close_path()
		cr.set_source_rgb(0, 0, 0)
		cr.stroke_preserve()
		cr.set_source_rgb(.2, .3, .5)
		cr.fill()

	def draw_regions(self, cr, regions):
		project = self.projection
		for r in regions:
			for points in r.polygons:
				cr.new_sub_path()
				for x, y in points:
					# FIXME add some intermediate points for long line segments
					x, y, vis = project(x, y)
					cr.line_to(x, y)
				cr.close_path()
			cr.set_source_rgb(0, 0, 0)
			cr.stroke_preserve()
			cr.set_source_rgb(*r.color)
			cr.fill()

	def get_labels(self, regions):
		GRANULARITY = 2
		regionmap = {}
		for r in regions:
			if r.offset is not None:
				for points in r.polygons:
					minx, miny, maxx, maxy = (round(GRANULARITY*x) for x in get_points_extents(points))
					for x in range(minx,maxx+1):
						for y in range(miny,maxy+1):
							regionmap[x,y] = r
		# flood fill regions
		DXY = [(-1,0),(1,0),(0,-1),(0,1)]
		labels = []
		while regionmap:
			xy, r = regionmap.popitem()
			todo = [xy]
			points = []
			while todo:
				x, y = xy = todo.pop()
				points.append(xy)
				for dx, dy in DXY:
					xy = x+dx, y+dy
					if regionmap.get(xy) is r:
						del regionmap[xy]
						todo.append(xy)
			minx, miny, maxx, maxy = get_points_extents(points)
			labels.append((len(points)/GRANULARITY**2, (minx+maxx)/2/GRANULARITY, (miny+maxy)/2/GRANULARITY, r))
		return labels

	def draw_text_box(self, cr, lines):
		x, y = cr.get_current_point()
		extents = [cr.text_extents(s) for s in lines]
		maxw = max(w for _, _, w, h, _, _ in extents)
		maxh = max(h for _, _, w, h, _, _ in extents)
		padw = padh = maxh/3
		totalh = (maxh+padh)*len(lines)+padh
		cr.rectangle(x-maxw/2-padw, y-totalh/2, maxw+padw*2, totalh)
		cr.fill_preserve()
		cr.set_source_rgba(0, 0, 0, .3)
		cr.stroke()
		cr.set_source_rgb(0, 0, 0)
		for i, (xb, yb, w, h, xa, ya) in enumerate(extents):
			cr.move_to(x-w/2-xb, y-totalh/2+(i+1)*(maxh+padh))
			cr.show_text(lines[i])

	def draw_labels(self, cr, labels):
		project = self.projection
		cr.set_font_size(3)
		for sz, x, y, r in labels:
			if sz < 60: continue
			x, y, vis = project(x, y)
			if vis:
				lines = [(self.time+r.offset).strftime(' %H:%M')]
				if self.show_names: lines.insert(0, r.name)
				cr.move_to(x, -y)
				cr.set_source_rgb(*r.color)
				self.draw_text_box(cr, lines)
	
	def draw_day_night(self, cr):
		lat, lon = get_sun_position(self.time)

		# calc boundary points
		dn = []
		for p in range(0, 360, 2):
			p *= RAD
			a = -math.sin(lat)*math.sin(p)
			x = a*math.cos(lon) - math.sin(lon)*math.cos(p)
			y = a*math.sin(lon) + math.cos(lon)*math.cos(p)
			dn.append((math.atan2(y,x)/RAD, math.asin(math.cos(lat)*math.sin(p))/RAD))
		dn.sort(key=lambda pt: pt[0])

		# draw
		edgey = (dn[0][1]+dn[-1][1])/2
		latsign = 1 if lat > 0 else -1
		cr.scale(1, -1)
		# left side
		cr.move_to(*self.projection(-180, 90*latsign)[:2])
		for y in range(90*latsign, round(edgey), -OUTLINE_STEP*latsign):
			cr.line_to(*self.projection(-180, y)[:2])
		cr.line_to(*self.projection(-180, edgey)[:2])
		# boundary
		for x, y in dn:
			cr.line_to(*self.projection(x, y)[:2])
		# right side
		for y in range(round(edgey), 90*latsign, OUTLINE_STEP*latsign):
			cr.line_to(*self.projection(180, y)[:2])
		cr.line_to(*self.projection(180, 90*latsign)[:2])
		# fill shadow
		cr.close_path()
		cr.set_source_rgba(0,0,0,.3)
		cr.fill()

	def configure_cairo(self, cr):
		cr.set_line_width(.3)
		cr.set_font_face(cr.select_font_face('sans-serif'))

	def do_draw(self, cr):
		self.configure_cairo(cr)

		w = self.get_allocated_width()
		h = self.get_allocated_height()
		left, _, _ = self.projection(-180, 0)
		right, _, _ = self.projection(180, 0)
		_, top, _ = self.projection(0, -90)
		_, bottom, _ = self.projection(0, 90)
		scale = min(w/(right-left), h/(bottom-top))

		regions = get_regions(self.time, self.timezones, self.show_names)

		regions_key = frozenset(regions)
		if regions_key != self._cur_regions_key:
			# recalculate label positions
			self._cur_labels = self.get_labels(regions)
			self._cur_regions_key = regions_key

		map_key = regions_key, self.projection, w, h
		if map_key != self._cur_map_key:
			# redraw map
			self._cur_map = cairo.Surface.create_similar(cr.get_target(), cairo.CONTENT_COLOR, w, h)
			map_cr = cairo.Context(self._cur_map)
			self.configure_cairo(map_cr)
			map_cr.translate(w/2, h/2)
			map_cr.scale(scale, -scale)
			self.draw_outline(map_cr)
			self.draw_regions(map_cr, regions)
			self._cur_map_key = map_key

		# draw
		cr.set_source_surface(self._cur_map)
		cr.paint()
		cr.translate(w/2, h/2)
		cr.scale(scale, scale)
		self.draw_labels(cr, self._cur_labels)
		for x, d in [(left, -.5), (right, .5)]:
			cr.set_source_rgb(.8, .8, .8)
			cr.move_to(x*.9, bottom*.9)
			self.draw_text_box(cr, [(self.time+datetime.timedelta(days=d)).strftime('%Y-%m-%d')])
		if self.show_day_night: self.draw_day_night(cr)

GObject.type_register(WorldView)

