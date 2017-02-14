#!/usr/local/bin/python3

import os, time
import config

from md5_hash import md5_hash_file
from nodes import Node
from tqdm import tqdm

from utils import *

# STARTING
log("Starting")

LAST_SEEN_AT = int(time.time())
log("Run ID: " + str(LAST_SEEN_AT))

# Mounting encrypted folders
for backup_item in config.BACKUP:
	log("Mounting " + backup_item["dest"])
	prepare_destination(backup_item)
	mount_encrypted_destination(backup_item)

# DO BACKUP

# Walk local data
log("Walking for collect nodes")
total_count = Node.select().count()
node_ids = []
progress_bar = tqdm(total=total_count, desc='Collecting nodes', unit='node', dynamic_ncols=True)
walk_directory_and_create_node(None, config.BACKUP_DIR, progress_bar, LAST_SEEN_AT)
progress_bar.clear()
progress_bar.close()

# Descrypt name
log("Decrypting encrypted node names")
unencrypted_nodes = Node.find_all_unencrypted_names()
if unencrypted_nodes.count() > 0:
	progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Collecting names for decrypting', unit='node', dynamic_ncols=True)
	names = []
	for node in unencrypted_nodes:
		names.append(node.name)
		progress_bar.update()
	progress_bar.close()

	decrpyted_data = descrypt_encfs_names(names)

	# Save decrypted data
	progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Saving decrypted names', unit='node', dynamic_ncols=True)
	for node in decrpyted_data:
		progress_bar.update()
		Node.save_decrypted_name(node[0],node[1])
	progress_bar.close()

# Get last modify and hash
log("Checking for changed nodes and counting hash for changed/new nodes")
all_files = Node.select().where(Node.node_type == "F",Node.last_seen_at == LAST_SEEN_AT)
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

# Unmounting encrypted folders
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
