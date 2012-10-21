import datetime
from gi.repository import GObject, Gtk

def spin_format(spin, fmt):
    spin.set_text(fmt % spin.get_value_as_int())
    return True

def spin(min, max, step=1, page=10, fmt='%02i'):
	s = Gtk.SpinButton.new(Gtk.Adjustment(min, min, max, step, page, 0), 1, 0)
	s.set_numeric(True)
	s.set_wrap(True)
	s.set_alignment(1)
	s.set_width_chars(len(str(max)))
	s.connect('output', spin_format, fmt)
	return s

def days_in_month(year, month):
	month += 1
	if month == 13:
		year += 1
		month = 1
	return (datetime.datetime(year, month, 1) - datetime.timedelta(days=1)).day

class DateTimeEntry(Gtk.HBox):
	def __init__(self):
		Gtk.HBox.__init__(self)
		self.set_can_focus(True)
		self.set_spacing(2)
		self.year = spin(1001, 9998)
		self.month = spin(1, 12)
		self.day = spin(1, 31)
		self.hour = spin(0, 23)
		self.minute = spin(0, 59)
		prev = None
		for s in [self.year, self.month, self.day, self.hour, self.minute]:
			self.pack_start(s, False, True, 0)
			s.connect('value-changed', self._on_changed)
			if prev: s.connect('wrapped', self._on_wrap, prev)
			prev = s
		self.pack_start(Gtk.Label('UTC'), False, True, 0)
	
	def _on_wrap(self, spin, prev):
		v = spin.get_value_as_int()
		min, max = spin.get_range()
		prev.spin(Gtk.SpinType.STEP_FORWARD if v == min else Gtk.SpinType.STEP_BACKWARD, 1)
		# day wraps before month has changed, so it can be set to the wrong max
		if spin == self.day and v != min: spin.set_value(99)

	def _on_changed(self, spin):
		if spin in (self.year, self.month):
			self.day.set_range(1, days_in_month(self.year.get_value_as_int(), self.month.get_value_as_int()))
		self.emit('value-changed')

	def _get_time(self):
		return datetime.datetime(
			self.year.get_value_as_int(), self.month.get_value_as_int(), self.day.get_value_as_int(),
			self.hour.get_value_as_int(), self.minute.get_value_as_int()
		)
	def _set_time(self, t):
		self.year.set_value(t.year)
		self.month.set_value(t.month)
		self.day.set_value(t.day)
		self.hour.set_value(t.hour)
		self.minute.set_value(t.minute)
	time = property(_get_time, _set_time)

GObject.signal_new('value-changed', DateTimeEntry, GObject.SIGNAL_RUN_LAST | GObject.SIGNAL_ACTION, GObject.TYPE_NONE, ())

