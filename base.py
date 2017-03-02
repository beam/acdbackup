import os, time
import config

from md5_hash import md5_hash_file
from database import Node,RemoteNode,NodeCache
from tqdm import tqdm

from utils import *

def get_last_local_seen_at():
    return Node.get_last_seen_at()

# Mounting encrypted folders
def mount_encrypted_dirs():
    for backup_item in config.BACKUP:
    	log("Mounting " + backup_item["dest"])
    	prepare_destination(backup_item)
    	mount_encrypted_destination(backup_item)
    return True

# Walk local data
def walk_and_collect_local_nodes(LAST_SEEN_AT):
    log("Walking for collect nodes")
    total_count = Node.select().where(Node.last_seen_at == Node.get_last_seen_at()).count()
    progress_bar = tqdm(total=total_count, desc='Collecting nodes', unit='node', dynamic_ncols=True)
    nodes_ids = []
    Node.include_all_excluded_files()
    walk_directory_and_create_node(None, nodes_ids, config.BACKUP_DIR, progress_bar)
    progress_bar.clear()
    progress_bar.close()

    log("Updating last seen_at")
    progress_bar = tqdm(total=len(nodes_ids), desc='Updating last seen at', unit='node', dynamic_ncols=True)
    Node.update_last_seen_at(nodes_ids, LAST_SEEN_AT, progress_bar)
    progress_bar.clear()
    progress_bar.close()
    return True

# Descrypt local name
def decrypt_local_node_names(LAST_SEEN_AT):
    log("Decrypting encrypted local node names")
    unencrypted_nodes = Node.find_all_unencrypted_names()
    if unencrypted_nodes.count() > 0:
        progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Collecting names for decrypting', unit='node', dynamic_ncols=True)
        names = []
        for node in unencrypted_nodes:
            names.append(node.name)
            progress_bar.update()

        progress_bar.clear()
        progress_bar.close()

        decrpyted_data = descrypt_encfs_names(names)

        # Save decrypted data
        progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Saving decrypted names', unit='node', dynamic_ncols=True)
        for node in decrpyted_data:
            progress_bar.update()
            Node.save_decrypted_name(node[0],node[1])

        progress_bar.clear()
        progress_bar.close()
    return True

def exclude_directories_and_files(LAST_SEEN_AT):
    if not hasattr(config,'BACKUP_EXCLUDE'): return False
    if not config.BACKUP_EXCLUDE: return False
    excluded_nodes = []
    for excluded_dir in config.BACKUP_EXCLUDE:
        excluded_node = Node.find_node_by_path(excluded_dir, None,None, 'plain')
        if excluded_node: excluded_nodes.append(excluded_node.id)

    if excluded_nodes:
        for excluded_node in excluded_nodes:
            Node.exclude_node(excluded_node)

    return excluded_nodes

# Get last modify and hash
def collect_local_node_last_modify_and_hash(LAST_SEEN_AT):
    log("Checking for changed nodes and counting hash for changed/new nodes")
    all_files = Node.select().where(Node.node_type == "F",Node.last_seen_at == LAST_SEEN_AT)
    progress_bar = tqdm(total=all_files.count(), desc='Searching for changes', unit='node', dynamic_ncols=True)
    for node in all_files:
    	if not os.path.exists(full_node_path(node)):
    		log("File: " + node.get_node_path('plain') + " missing!",'error')
    		continue
    	if check_if_files_in_changed(node):
    		node.md5 = md5_hash_file(full_node_path(node), True, node.size, 'Hashing: ' + node.plain_name)
    		node.save()
    		log("File: " + node.get_node_path('plain') + " hashed",'debug')
    	progress_bar.update()
    progress_bar.clear()
    progress_bar.close()
    return True

# Synchronize remote nodes with local cache
def synchronize_remote_node():
    log("Synchronize remote nodes")
    RemoteNode.sync()
    return True


# Decrypt remote names
def decrypt_remote_node_names():
    log("Decrypting encrypted remote node names")
    unencrypted_nodes = RemoteNode.find_all_unencrypted_names()
    if unencrypted_nodes.count() > 0:
        progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Collecting names for decrypting', unit='node', dynamic_ncols=True)
        names = []
        for node in unencrypted_nodes:
            names.append(node.name)
            progress_bar.update()
        progress_bar.clear()
        progress_bar.close()
        decrpyted_data = descrypt_encfs_names(names)

        # Save decrypted data
        progress_bar = tqdm(total=unencrypted_nodes.count(), desc='Saving decrypted names', unit='node', dynamic_ncols=True)
        for node in decrpyted_data:
            progress_bar.update()
            RemoteNode.save_decrypted_name(node[0],node[1])
        progress_bar.close()
    return True

def clear_cache():
    NodeCache.clear()
    return True

def get_remote_chroot():
    if RemoteNode.get_root_node() == None: raise Exception("Missing root node on remote cache, please resync")
    CHROOT_NODE = RemoteNode.find_node_by_path(config.REMOTE_BACKUP_DESTINATION)
    if CHROOT_NODE == None: raise Exception("Missing backup dir, please create on server")
    return CHROOT_NODE

# Create directory tree on server
def create_remote_directory_tree(LAST_SEEN_AT, CHROOT_NODE):
    log("Creating directory tree on remote server")
    total_count = Node.select().where(Node.last_seen_at == LAST_SEEN_AT).where(Node.node_type == 'D').count()
    progress_bar = tqdm(total=total_count, desc='Creating remote directories', unit='dir', dynamic_ncols=True)
    walk_cache_and_create_remote_directories(None, CHROOT_NODE, progress_bar, LAST_SEEN_AT)
    progress_bar.clear()
    progress_bar.close()


# Move exist file and upload new
def sync_local_and_remote_nodes(LAST_SEEN_AT, CHROOT_NODE):
    log("Moving and upload files")
    total_size = Node.get_total_size(LAST_SEEN_AT)
    progress_bar = tqdm(total=total_size, desc='Moving and uploading files', unit='B', unit_scale=True, dynamic_ncols=True)
    move_and_upload_files(CHROOT_NODE, LAST_SEEN_AT, progress_bar)
    progress_bar.clear()
    progress_bar.close()

# Unmounting encrypted folders
def umount_encrypted_dirs():
    for backup_item in config.BACKUP:
    	log("Unmounting " + backup_item['dest'])
    	umount_encrypted_destination(backup_item)
