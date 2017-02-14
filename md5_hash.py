#!/usr/local/bin/python3
import hashlib
from tqdm import tqdm

def hash_file_obj(fo, progress = False):
	hasher = hashlib.md5()
	fo.seek(0)
	for chunk in iter(lambda: fo.read(1024 ** 2), b''):
		hasher.update(chunk)
		if progress: progress.update(int(chunk.__sizeof__()))
	return hasher.hexdigest()

def md5_hash_file(file_name, show_progress_bar = False, total_size = 0, title = ''):
	if show_progress_bar:
		progress = tqdm(total=total_size, desc=title, unit_scale=True ,unit='B', dynamic_ncols=True)
	else:
		progress = False

	with open(file_name,'rb') as f:
		md5 = hash_file_obj(f, progress)

	if progress: progress.close()
	return md5
