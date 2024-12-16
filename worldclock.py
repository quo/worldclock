#!/usr/bin/python3

# TODO
# draw map in bg thread
# timezone dropdown (+ dst toggle) in datetimeentry (click on map -> set to clicked zone)
# fullscreen button
# config dialog for colors, etc
# map dragging

# show window asap, then continue loading:
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
win = Gtk.Window()
win.set_title('World clock')
win.set_default_size(1000, 550)
win.connect('destroy', Gtk.main_quit)
win.set_position(Gtk.WindowPosition.CENTER)
win.show()
while Gtk.events_pending(): Gtk.main_iteration()

import gzip, pickle, datetime
from gi.repository import GLib, Gdk
import worldview, datetimeentry

tb_now = Gtk.ToggleToolButton()
tb_now.set_label('Now')
def on_now_toggled(toggle):
	tb_datetime.set_sensitive(not toggle.get_active())
	set_current_time()
tb_now.connect('toggled', on_now_toggled)

tb_datetime = datetimeentry.DateTimeEntry()
def on_datetime_changed(entry):
	world.time = entry.time
tb_datetime.connect('value-changed', on_datetime_changed)

tb_day_night = Gtk.ToggleToolButton()
tb_day_night.set_label('Show day/night')
def on_day_night_toggled(toggle):
	world.show_day_night = toggle.get_active()
tb_day_night.connect('toggled', on_day_night_toggled)

tb_names = Gtk.ToggleToolButton()
tb_names.set_label('Show names')
def on_names_toggled(toggle):
	world.show_names = toggle.get_active()
tb_names.connect('toggled', on_names_toggled)

projections = Gtk.ListStore(str, object)
for name, func in [
	('Equirectangular', worldview.project_rect),
	('Wagner VI', worldview.project_wagner),
	('Orthographic (Americas)', worldview.project_ortho_america),
	('Orthographic (Europe/Africa)', worldview.project_ortho_europe),
	('Orthographic (Asia/Australia)', worldview.project_ortho_asia),
]: projections.append((name, func))
tb_projection = Gtk.ComboBox.new_with_model(projections)
def on_projection_changed(cb):
	world.projection = projections.get_value(cb.get_active_iter(), 1)
tb_projection.connect('changed', on_projection_changed)
text = Gtk.CellRendererText()
tb_projection.pack_start(text, True)
tb_projection.add_attribute(text, 'text', 0)

tb = Gtk.Toolbar()
for c in [tb_now, tb_datetime, Gtk.SeparatorToolItem(), tb_day_night, tb_names, tb_projection]:
	if not isinstance(c, Gtk.ToolItem):
		ti = Gtk.ToolItem()
		ti.add(c)
		c = ti
	c.set_margin_end(4)
	tb.insert(c, -1)

world = worldview.WorldView()

v = Gtk.VBox()
v.pack_start(tb, False, True, 0)
v.pack_start(world, True, True, 0)
win.add(v)
win.show_all()

with gzip.GzipFile('tz_world.pickled.gz') as f:
	precision, shapes = pickle.load(f)
zones = [worldview.TimeZone(tzid, [[(x/precision, y/precision) for x, y in pg] for pg in polygons]) for tzid, polygons in shapes]
del shapes
world.timezones = zones

timer_source = None
def set_current_time():
	global timer_source
	if timer_source is not None:
		GLib.source_remove(timer_source)
		timer_source = None
	if tb_now.get_active():
		now = datetime.datetime.now(datetime.UTC)
		tb_datetime.time = now
		timer_source = GLib.timeout_add(60100 - now.second * 1000, set_current_time)

# defaults
tb_now.set_active(True)
tb_day_night.set_active(True)
tb_names.set_active(False)
tb_projection.set_active(0)

Gtk.main()

