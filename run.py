#!/usr/local/bin/python3

import os, time
import config

from md5_hash import md5_hash_file
from database import Node,RemoteNode
from tqdm import tqdm

from utils import *

# STARTING
log("Starting")

# LAST_SEEN_AT = int(time.time())
LAST_SEEN_AT = Node.get_last_seen_at()
log("Run ID: " + str(LAST_SEEN_AT))

# Mounting encrypted folders
# for backup_item in config.BACKUP:
# 	log("Mounting " + backup_item["dest"])
# 	prepare_destination(backup_item)
# 	mount_encrypted_destination(backup_item)

# DO BACKUP

# Walk local data
# log("Walking for collect nodes")
# total_count = Node.select().where(Node.last_seen_at == Node.get_last_seen_at()).count()
# progress_bar = tqdm(total=total_count, desc='Collecting nodes', unit='node', dynamic_ncols=True)
# walk_directory_and_create_node(None, config.BACKUP_DIR, progress_bar, LAST_SEEN_AT)
# progress_bar.clear()
# progress_bar.close()

# Descrypt local name
# log("Decrypting encrypted local node names")
# unencrypted_nodes = Node.find_all_unencrypted_names()
# if unencrypted_nodes.count() > 0:
# 	progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Collecting names for decrypting', unit='node', dynamic_ncols=True)
# 	names = []
# 	for node in unencrypted_nodes:
# 		names.append(node.name)
# 		progress_bar.update()
# 	progress_bar.close()
#
# 	decrpyted_data = descrypt_encfs_names(names)
#
# 	# Save decrypted data
# 	progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Saving decrypted names', unit='node', dynamic_ncols=True)
# 	for node in decrpyted_data:
# 		progress_bar.update()
# 		Node.save_decrypted_name(node[0],node[1])
# 	progress_bar.close()

# Get last modify and hash
# log("Checking for changed nodes and counting hash for changed/new nodes")
# all_files = Node.select().where(Node.node_type == "F",Node.last_seen_at == LAST_SEEN_AT)
# progress_bar = tqdm(total=all_files.count(), desc='Searching for changes', unit='node', dynamic_ncols=True)
# for node in all_files:
# 	if not os.path.exists(full_node_path(node)):
# 		log("File: " + node.get_node_path('plain') + " missing!",'error')
# 		continue
# 	if check_if_files_in_changed(node):
# 		node.md5 = md5_hash_file(full_node_path(node), True, node.size, 'Hashing: ' + node.plain_name)
# 		node.save()
# 		log("File: " + node.get_node_path('plain') + " hashed",'debug')
# 	progress_bar.update()
# progress_bar.close()

# Synchronize remote nodes with local cache
# log("Synchronize remote nodes")
# RemoteNode.sync()

# Decrypt remote names
# log("Decrypting encrypted remote node names")
# unencrypted_nodes = RemoteNode.find_all_unencrypted_names()
# if unencrypted_nodes.count() > 0:
# 	progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Collecting names for decrypting', unit='node', dynamic_ncols=True)
# 	names = []
# 	for node in unencrypted_nodes:
# 		names.append(node.name)
# 		progress_bar.update()
# 	progress_bar.close()
# 	decrpyted_data = descrypt_encfs_names(names)
#
# 	# Save decrypted data
# 	progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Saving decrypted names', unit='node', dynamic_ncols=True)
# 	for node in decrpyted_data:
# 		progress_bar.update()
# 		RemoteNode.save_decrypted_name(node[0],node[1])
# 	progress_bar.close()

if RemoteNode.get_root_node() == None: raise Exception("Missing root node on remote cache, please resync")
CHROOT_NODE = RemoteNode.find_node_by_path(config.REMOTE_BACKUP_DESTINATION)
if CHROOT_NODE == None: raise Exception("Missing backup dir, please create on server")

# Create directory tree on server
# log("Creating directory tree on remote server")
# total_count = Node.select().where(Node.last_seen_at == LAST_SEEN_AT).where(Node.node_type == 'D').count()
# progress_bar = tqdm(total=total_count, desc='Creating remote directories', unit='dir', dynamic_ncols=True)
# walk_cache_and_create_remote_directories(None, CHROOT_NODE, progress_bar, LAST_SEEN_AT)
# progress_bar.close()

# Move exist file and upload new
log("Moving and upload files")
total_size = Node.get_total_size(LAST_SEEN_AT)
progress_bar = tqdm(total=total_size, desc='Moving and uploading files', unit='B', unit_scale=True, dynamic_ncols=True)
move_and_upload_files(CHROOT_NODE, LAST_SEEN_AT, progress_bar)
progress_bar.close()

# Unmounting encrypted folders
# for backup_item in config.BACKUP:
# 	log("Unmounting " + backup_item['dest'])
# 	umount_encrypted_destination(backup_item)

log("End")

#progress = FileProgress()

# def pprint(d: dict):
#         print(json.dumps(d, indent=4, sort_keys=True))

# acd_client = client.ACDClient(CACHE_PATH)
# # r = acd_client.get_metadata("-2SS12klSW2g8jr2WOxvpw")
# r = acd_client.upload_file("/storage/praha2.parking.jpg","-PvToOMHSOesHdc7tg7TTw") # ,read_callbacks=[progress.update])
# print(r)
# pprint(r)
