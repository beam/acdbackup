import os, stat, time, sys
import config

from subprocess import Popen, PIPE, STDOUT, check_call
from md5_hash import md5_hash_file
from database import Node,RemoteNode
from tqdm import tqdm

import threading
from queue import Queue

thread_lock = threading.Lock()

import colorama
from acdcli.api.common import RequestError as acd_RequestError

def log(message,msg_type = 'info'):
	if msg_type == 'info':
		msg_color = colorama.Fore.YELLOW
	elif msg_type == 'error':
		msg_color = colorama.Fore.RED
	elif msg_type == 'debug':
		msg_color = colorama.Fore.WHITE
	with thread_lock:
		full_message = colorama.Fore.GREEN + time.strftime('%Y-%m-%d %H:%M:%S') + " " + msg_color + message + colorama.Style.RESET_ALL
		tqdm.write(full_message)
		if config.LOG_FILE:
			f = open(config.LOG_FILE,"a")
			f.write(full_message)
			f.write("\n")
			f.close()

def query_yes_no(question, default="yes"):
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")

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

def walk_directory_and_create_node(parent_id, nodes_id, current_directory, progress_bar):
	(root, directories, files) = next(os.walk(current_directory))
	for dir_file in files:
		if os.path.islink(os.path.join(current_directory,dir_file)): continue
		progress_bar.update()
		node = Node.find_or_create_node(parent_id, dir_file, "F")
		nodes_id.append(node.id)
	for dir_subdir in directories:
		progress_bar.update()
		node = Node.find_or_create_node(parent_id, dir_subdir, "D")
		nodes_id.append(node.id)
		walk_directory_and_create_node(node, nodes_id, os.path.join(current_directory, dir_subdir), progress_bar)

def walk_cache_and_create_remote_directories(local_parent_id, remote_parent_id, progress_bar = None, last_seen_at = None):
	for node in Node.get_all_subdirectories(local_parent_id, last_seen_at):
		remote_node = RemoteNode.get_dir_by_name_and_parent(node.name, remote_parent_id)
		if len(remote_node) == 1:
			remote_node = remote_node.first()
		elif len(remote_node) == 0:
			remote_node = RemoteNode.create_folder(node.name,remote_parent_id,node.plain_name)
			if not remote_node:
				log("Creating directory " + node.get_node_path('plain') + ' failed!', 'error')
				raise Exception("Something wrong")
			log("Directory: " + remote_node.get_node_path('plain') + " created",'debug')
		elif len(remote_node) > 1:
			 raise Exception("More than one result by name")
		if progress_bar: progress_bar.update()
		walk_cache_and_create_remote_directories(node.id, remote_node.id, progress_bar, last_seen_at)

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
		if translated_name.find("decode err: ") != -1:
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
	file_stat = os.lstat(file_path)
	if not node.mtime or not node.md5 or int(file_stat.st_mtime) != node.mtime.timestamp() or file_stat.st_size != node.size:
		node.mtime = int(file_stat.st_mtime)
		node.size = file_stat.st_size
		node.save()
		return True
	else:
		return False

def upload_file_on_server(local_node, remote_parent):
	remote_nodes_already_exits = RemoteNode.get_file_by_name_and_parent(local_node.name, remote_parent.id).first()
	local_file = os.path.join(config.BACKUP_DIR,local_node.get_node_path())
	local_file_size = os.lstat(local_file).st_size
	with thread_lock: progress_bar = tqdm(total=local_file_size, desc='Uploading file: ' + str(local_node.plain_name), unit='B', unit_scale=True, dynamic_ncols=True, mininterval=1)

	if remote_nodes_already_exits: # overwrite file
		RemoteNode.replace_file(os.path.join(config.BACKUP_DIR, local_file), remote_nodes_already_exits.id, local_node.plain_name, (progress_bar, thread_lock))
		log('File ' + str(local_node.get_node_path('plain')) + ' uploaded and overwritten','debug')
	else: # upload file
		RemoteNode.upload_file(os.path.join(config.BACKUP_DIR, local_file), remote_parent.id, local_node.plain_name, (progress_bar, thread_lock))
		log('File ' + str(local_node.get_node_path('plain')) + ' uploaded','debug')

	with thread_lock:
		progress_bar.clear()
		progress_bar.close()

def threaded_upload_file_on_server(upload_queue):
	while True:
		local_node, remote_parent, retry_count, progress_bar = upload_queue.get()
		for attempt in range(retry_count):
			try:
				upload_file_on_server(local_node, remote_parent)
				break
			except acd_RequestError as e:
				log("Error: " + str(e) + " on file " + local_node.plain_name + ". Retry " + str(attempt), 'error')
				time.sleep(5)
				pass
		with thread_lock: progress_bar.update(local_node.size)
		upload_queue.task_done()


def move_and_upload_files(remote_chroot_node, last_seen_at, progress_bar):
	known_md5 = []
	retry_count = 3 # move to config
	thread_upload_count = 6 # move to config
	upload_queue = Queue(thread_upload_count - 1)
	for x in range(thread_upload_count):
		t = threading.Thread(target=threaded_upload_file_on_server,args=(upload_queue,))
		t.daemon = True
		t.start()

	for node in Node.select().where(Node.last_seen_at == last_seen_at).where(Node.node_type == 'F'):#.offset(172850).limit(100):
		if not node.md5:
			log("File " + node.get_node_path('plain') + " without MD5 hash!",'error')
			raise Exception("Something wrong")
		remote_nodes = RemoteNode.select().where(RemoteNode.md5 == node.md5).execute()
		local_node_directory = node.parent.get_node_path() if node.parent else ""
		remote_parent = RemoteNode.find_node_by_path(local_node_directory,None,remote_chroot_node.id)
		if remote_parent == None:
			log("Parent missing! " + node.get_node_path() + ' = '+ node.get_node_path('plain'), 'error')
			raise Exception("Something wrong")

		if len(remote_nodes) == 0:
			upload_queue.put((node, remote_parent, retry_count, progress_bar))
			continue
		else:
			found_right_file = False
			for remote_node in remote_nodes: # check if one of files is in right directory and have a same name
				if remote_parent.id == remote_node.parent_id and remote_node.name == node.name:
					found_right_file = True
					selected_remote_node = remote_node
					break

			if not found_right_file:
				for remote_node in remote_nodes: # check if one of files is in right directory (and maybe renamed)
					remote_node_path = remote_node.get_node_path('name', remote_chroot_node.id)
					if remote_parent.id == remote_node.parent_id and not Node.find_node_by_path(remote_node_path, last_seen_at):
						found_right_file = True
						selected_remote_node = remote_node
						break

			if not found_right_file:
				for remote_node in remote_nodes: # check if is one of files is not on local file system (moved)
					if not remote_node.is_chrooted(remote_chroot_node.id):
						# log("File " + node.get_node_path('plain') + " is outside chroot " + remote_node.get_node_path('plain', remote_chroot_node.id))
						continue # file is outside backup directory
					remote_node_path = remote_node.get_node_path('name', remote_chroot_node.id)
					if Node.find_node_by_path(remote_node_path, last_seen_at) == None:
						found_right_file = True
						selected_remote_node = remote_node
						remote_nodes_already_exits = RemoteNode.get_file_by_name_and_parent(selected_remote_node.name, remote_parent.id).first()
						if remote_nodes_already_exits: # can't move because there is already file with the same name and renaming is later
							log("File " + selected_remote_node.plain_name + " already exists in " + remote_parent.get_node_path('plain', remote_chroot_node.id) + ". Temporary renaming.", 'debug')
							selected_remote_node = RemoteNode.rename_file(selected_remote_node.id,str(last_seen_at) + "-" + selected_remote_node.md5, str(last_seen_at) + "-" + selected_remote_node.md5 )
						selected_remote_node_path = selected_remote_node.get_node_path('plain', remote_chroot_node.id)
						selected_remote_node = RemoteNode.move_file(selected_remote_node.id, remote_parent.id)
						log("File " + selected_remote_node_path + " moved to " + remote_parent.get_node_path('plain',remote_chroot_node.id), 'debug')
						break

			if found_right_file == False:
				upload_queue.put((node, remote_parent, retry_count, progress_bar))
				continue
			else:
				if selected_remote_node.name != node.name:
					log(selected_remote_node.id)
					remote_nodes_already_exits = RemoteNode.get_file_by_name_and_parent(node.name, remote_parent.id).first()
					selected_remote_node_path = selected_remote_node.get_node_path('plain', remote_chroot_node.id)
					if not remote_nodes_already_exits:
						RemoteNode.rename_file(selected_remote_node.id, node.name, node.plain_name)
						log("File " + selected_remote_node_path + " (" + selected_remote_node.id + ") renamed to " + node.plain_name + " (" + str(node.id) + ")", 'debug')
					else:
						log("File " + selected_remote_node_path + " (" + selected_remote_node.id + ") can't be renamed to " + node.plain_name + " (" + str(node.id) + ")" + ". File already exists!", 'error')

				selected_remote_node.clear_my_relevant_cache()
				remote_parent.clear_my_relevant_cache()

			with thread_lock: progress_bar.update(node.size)

	upload_queue.join()
	with thread_lock: progress_bar.close()
