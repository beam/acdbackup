from threading import Lock as thLock

class AcdProgressBar(object):
	def __init__(self, progress_bar = None):
		self.progress_bar = progress_bar
		self.thlock = thLock()

	def update(self, chunk):
		if self.progress_bar: with self.thlock: self.progress_bar.update(chunk.__sizeof__())
