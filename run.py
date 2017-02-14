#!/usr/local/bin/python3

import sys
import os, stat
import json
import time

import config

from subprocess import Popen, PIPE, STDOUT, check_call
from acdcli.api import client
from md5_hash import md5_hash_file
from nodes import Node

from tqdm import tqdm

import colorama

# colorama.init(autoreset=True)

# class FileProgress(object):
# 	def __init__(self):
# 		self.current = 0

# 	def update(self, chunk):
# 		self.current += chunk.__sizeof__()
# 		print(self.current)


def log(message):
	tqdm.write(colorama.Fore.GREEN + time.strftime('%Y-%m-%d %H:%M:%S') + " " + colorama.Fore.WHITE + message + colorama.Style.RESET_ALL)

def encfs_password_file(create = True):
	file_path = os.path.join(config.TMP_DIR,"encfs-pass.sh")
	if create:
		if os.path.exists(file_path): return file_path
		open(file_path, 'a').close()
		os.chmod(file_path, stat.S_IEXEC)	
		file = open(file_path, 'w')
		file.write("echo '" + config.ENCFS_PASS + "'")
		file.close
	else:
		if os.path.exists(file_path):
			os.remove(file_path)
	return file_path


def prepare_destination(backup_item):
	if not os.path.isdir(backup_item['dest']):
		os.makedirs(backup_item['dest'])

def mount_encrypted_destination(backup_item):
	if not os.path.ismount(backup_item['dest']):
		my_env = os.environ
		my_env['ENCFS6_CONFIG'] = config.ENCFS6_CONFIG
		proc = Popen(['encfs','--reverse','--extpass=' + encfs_password_file(),backup_item['source'],backup_item['dest']])
		# proc.communicate(input = ENCFS_PASS.encode())
		proc.wait()
	encfs_password_file(False)

def umount_encrypted_destination(backup_item):
	if os.path.ismount(backup_item['dest']):
		check_call(['umount',backup_item['dest']])

def walk_directory_and_create_node(parent_id, current_directory):
	(root, directories, files) = next(os.walk(current_directory))
	for dir_file in files:
		progress_bar.update(1)
		Node.find_or_create_node(parent_id, dir_file, "F")
	for dir_subdir in directories:
		progress_bar.update(1)
		dir_id = Node.find_or_create_node(parent_id, dir_subdir, "D")
		walk_directory_and_create_node(dir_id, os.path.join(current_directory, dir_subdir))

def descrypt_encfs_names(node_names, delete_pass_file = True):
	my_env = os.environ
	my_env['ENCFS6_CONFIG'] = config.ENCFS6_CONFIG
	proc = Popen(['encfsctl','decode',"--extpass=" + encfs_password_file(),config.TMP_DIR,"--"],stdin=PIPE,stdout=PIPE,stderr=PIPE)
	output, error = proc.communicate(input = "\n".join(node_names).encode())
	proc.wait()
	list_for_process = output.decode('utf8','replace').strip().split("\n")
	list_id = 0
	last_error = False
	list_for_return = []
	progress_bar = tqdm(total=len(list_for_process), desc='Parsing decrypted data', unit='node', dynamic_ncols=True)
	for translated_name in list_for_process:
		progress_bar.update()
		if last_error: 
			last_error = False
			continue
		if translated_name.find("decode err: Filename too small to decode") != -1:
			last_error = True
			translated_name = node_names[list_id]
		list_for_return.append([node_names[list_id], translated_name])
		list_id += 1
	if delete_pass_file: encfs_password_file(False)
	progress_bar.close()
	return list_for_return

def full_node_path(node):
	return os.path.join(config.BACKUP_DIR, node.get_node_path())

def check_if_files_in_changed(node):
	file_path = full_node_path(node)
	file_stat = os.stat(file_path)
	if not node.mtime or not node.md5 or int(file_stat.st_mtime) != node.mtime.timestamp() or file_stat.st_size != node.size:
		node.mtime = int(file_stat.st_mtime)
		node.size = file_stat.st_size
		node.save()
		return True
	else:
		return False

# STARTING
log("Starting")

for backup_item in config.BACKUP:
	log("Mounting " + backup_item["dest"])
	prepare_destination(backup_item)
	mount_encrypted_destination(backup_item)

# DO BACKUP

# Walk local data

log("Walking for collect nodes")
# total_count = Node.select().count()
# progress_bar = tqdm(total=total_count, desc='Collecting nodes', unit='node', dynamic_ncols=True)
# walk_directory_and_create_node(None, config.BACKUP_DIR)
# progress_bar.clear()
# progress_bar.close()

# Descrypt name
log("Decrypting encrypted node names")
# unencrypted_nodes = Node.find_all_unencrypted_names()
# if unencrypted_nodes.count() > 0:
# 	progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Collecting names for decrypting', unit='node', dynamic_ncols=True)
# 	names = []
# 	for node in unencrypted_nodes:
# 		names.append(node.name)
# 		progress_bar.update()
# 	progress_bar.close()

# 	decrpyted_data = descrypt_encfs_names(names)

# 	# Save decrypted data
# 	progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Saving decrypted names', unit='node', dynamic_ncols=True)
# 	for node in decrpyted_data:
# 		progress_bar.update()
# 		Node.save_decrypted_name(node[0],node[1])
# 	progress_bar.close()

# Get last modify and hash
log("Checking for changed nodes and counting hash for changed/new nodes")
all_files = Node.select().where(Node.node_type == "F")
progress_bar = tqdm(total=all_files.count(), desc='Searching for changes', unit='node', dynamic_ncols=True)
for node in all_files:
	if not os.path.exists(full_node_path(node)):
		log("File: " + node.plain_name + " missing!")
		continue
	if check_if_files_in_changed(node):
		node.md5 = md5_hash_file(full_node_path(node), True, node.size, 'Hashing: ' + node.plain_name)
		node.save()
		log("File: " + node.plain_name + " hashed")
	progress_bar.update()
progress_bar.close()

# Create directory tree on server

for backup_item in config.BACKUP:
	log("Unmounting " + backup_item['dest'])
	umount_encrypted_destination(backup_item)
	# cleanup

log("End")

#progress = FileProgress()

# def pprint(d: dict):
#         print(json.dumps(d, indent=4, sort_keys=True))

# acd_client = client.ACDClient(CACHE_PATH)
# # r = acd_client.get_metadata("-2SS12klSW2g8jr2WOxvpw")
# r = acd_client.upload_file("/storage/praha2.parking.jpg","-PvToOMHSOesHdc7tg7TTw") # ,read_callbacks=[progress.update])
# print(r)
# pprint(r)
