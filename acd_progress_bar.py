class AcdProgressBar(object):
	def __init__(self, progress_bar_and_lock = None):
		self.progress_bar, self.thlock = progress_bar_and_lock

	def update(self, chunk):
		if self.progress_bar:
			with self.thlock:
				self.progress_bar.update(chunk.__sizeof__())
