#!/usr/local/bin/python3

from utils import log,query_yes_no
from base import *

# STARTING
log("Starting")

walk_local_dirs = query_yes_no("Walk local file system?")

if walk_local_dirs:
	import time
	LAST_SEEN_AT = int(time.time())
else:
	log("Run ID: " + str(LAST_SEEN_AT))

# Mounting encrypted folders
if query_yes_no("Mount encfs?"): mount_encrypted_dirs()

# Walk local data
if walk_local_dirs: walk_and_collect_local_nodes(LAST_SEEN_AT)

# Descrypt local name
if walk_local_dirs: decrypt_local_node_names(LAST_SEEN_AT)

# Get last modify and hash
if walk_local_dirs: collect_local_node_last_modify_and_hash(LAST_SEEN_AT)

# Synchronize remote nodes with local cache
if query_yes_no("Synchronize remote nodes?"):
	synchronize_remote_node()
	# Decrypt remote names
	decrypt_remote_node_names()
	clear_cache()

CHROOT_NODE = get_remote_chroot()
clear_cache()

# Create directory tree on server
if query_yes_no("Create remote directories?"):
	create_remote_directory_tree(LAST_SEEN_AT, CHROOT_NODE)
	clear_cache()

# Move exist file and upload new
if query_yes_no("Sync local nodes with remote?"): sync_local_and_remote_nodes(LAST_SEEN_AT, CHROOT_NODE)

# Unmounting encrypted folders
if query_yes_no("Umount encfs?", "no"): umount_encrypted_dirs(s)

log("End")
