import os, stat,time
import config

from subprocess import Popen, PIPE, STDOUT, check_call
from md5_hash import md5_hash_file
from database import Node,RemoteNode
from tqdm import tqdm

import colorama

# colorama.init(autoreset=True)

# class FileProgress(object):
# 	def __init__(self):
# 		self.current = 0

# 	def update(self, chunk):
# 		self.current += chunk.__sizeof__()
# 		print(self.current)



def log(message,msg_type = 'info'):
	if msg_type == 'info':
		msg_color = colorama.Fore.YELLOW
	elif msg_type == 'error':
		msg_color = colorama.Fore.RED
	elif msg_type == 'debug':
		msg_color = colorama.Fore.WHITE
	tqdm.write(colorama.Fore.GREEN + time.strftime('%Y-%m-%d %H:%M:%S') + " " + msg_color + message + colorama.Style.RESET_ALL)

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

def walk_directory_and_create_node(parent_id, current_directory, progress_bar, last_seen_at = None):
	(root, directories, files) = next(os.walk(current_directory))
	for dir_file in files:
		if os.path.islink(os.path.join(current_directory,dir_file)): continue
		progress_bar.update(1)
		node = Node.find_or_create_node(parent_id, dir_file, "F")
		if last_seen_at: Node.update_last_seen_at(node,last_seen_at)
	for dir_subdir in directories:
		progress_bar.update(1)
		node = Node.find_or_create_node(parent_id, dir_subdir, "D")
		if last_seen_at: Node.update_last_seen_at(node,last_seen_at)
		walk_directory_and_create_node(node, os.path.join(current_directory, dir_subdir), progress_bar, last_seen_at)

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
	remote_nodes_already_exits = RemoteNode.get_file_by_name_and_parent(local_node.name, remote_parent)
	if remote_nodes_already_exits: # overwrite file
		log('Soubor k prepsani: ' + str(remote_nodes_already_exits.first().get_node_path('plain')),'debug')
	else: # upload file
		log('Soubor k uploadovani : ' + str(local_node.get_node_path('plain')),'debug')

def move_and_upload_files(remote_chroot_node, last_seen_at, progress_bar):
	known_md5 = []
	for node in Node.select().where(Node.last_seen_at == last_seen_at).where(Node.node_type == 'F'):#.offset(170000):
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
			upload_file_on_server(node, remote_parent)
			# log("Upload file " + node.get_node_path('plain'), 'debug')
			continue
		# elif len(remote_nodes) == 1:
			# if not remote_chroot_node.id in remote_nodes.first().get_node_path('id'):
			# 	log("File is outside backup dir: " + remote_nodes.first().get_node_path('plain'))
			# 	# handle as new file to upload
			# 	continue
			# # test jestli je v backup directory
			# if remote_nodes.first().parent != remote_parent:
			# 	if remote_nodes.first().name == node.name:
			# 		log("File moved " + node.get_node_path('plain') + " to " + remote_nodes.first().get_node_path('plain', remote_chroot_node.id))
			# 	else:
			# 		log("File moved and renamed " + node.get_node_path('plain') + " to " + remote_nodes.first().get_node_path('plain', remote_chroot_node.id))
			# elif remote_nodes.first().parent == remote_parent and remote_nodes.first().name != node.name:
			# 	log("File renamed " + node.plain_name + " / " + remote_nodes.first().plain_name)

		# if not node.parent:
		# 	parent_node_path = ""
		# 	r = RemoteNode.find_node_by_path(parent_node_path,None,remote_chroot_node)
		# 	log("Parent missing! " + node.get_node_path() + ' = '+ r.get_node_path('plain'), 'error')

		# if len(remote_nodes) > 1 and not node.md5 in known_md5:
		# 	log(node.plain_name + " x " + str(len(remote_nodes)),'debug')
		# 	known_md5.append(node.md5)
		# 	for remote_node in remote_nodes:
		# 		log(remote_node.get_node_path('plain'))
		#
		# if len(remote_nodes) == 0:
		# 	if not node.parent:
		# 		log("Parent missing! " + node.get_node_path() + ' = '+ node.get_node_path('plain'), 'error')
		# 	# parent_node_id = RemoteNode.find_node_by_path(Node.get_node_path(),None,remote_chroot_node)
			# if parent_node_id == None:
			# 	log("Parent missing! " + node.get_node_path() + ' = '+ node.get_node_path('plain'), 'error')
			# else:
			# 	log(node.plain_name + " new file into " + parent_node_id)

		progress_bar.update(node.size)

class AcdProgressBar(object):
	def __init__(self, progress_bar):
		self.progress_bar = progress_bar

	def update(self, chunk):
		self.progress_bar.update(chunk.__sizeof__())
