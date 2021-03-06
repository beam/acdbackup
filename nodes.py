from peewee import *

from database import BaseNode,NodeCache

class Node(BaseNode):

	parent = ForeignKeyField("self", null = True, default = None)
	node_type = FixedCharField(max_length = 1) # F - files, D - directory, E - excluded directory, I - excluded file
	name = TextField(index = True)
	plain_name = TextField(null = True, default = None)
	mtime = TimestampField(null = True, default = None)
	md5 = FixedCharField(max_length = 32, null = True, default = None, index = True)
	size = BigIntegerField(null = True, default = None)
	last_seen_at = TimestampField(null = True, default = None, index = True)

	cache_section = "N"

	class Meta:
		indexes = (
			(('parent', 'last_seen_at'), False),
		)

	def include_all_excluded_files():
		Node.update(node_type = 'D').where(Node.node_type == 'E').execute()
		Node.update(node_type = 'F').where(Node.node_type == 'I').execute()
		return True

	def exclude_node(node_id):
		Node.update(node_type = 'I').where(Node.node_type == 'F').where(Node.parent_id == node_id).execute()
		for excluded_node_dir in Node.select().where(Node.node_type == 'D').where(Node.parent_id == node_id):
			Node.exclude_node(excluded_node_dir.id)
		Node.update(node_type = 'E').where(Node.node_type == 'D').where(Node.parent_id == node_id).execute()

	def get_total_size(last_seen_at):
		node = Node.select(fn.SUM(Node.size)).where(Node.last_seen_at == last_seen_at).where(Node.node_type == 'F').scalar()
		return int(node) if node else 0

	def get_last_seen_at():
		node = Node.select(fn.MAX(Node.last_seen_at)).scalar()
		return int(node) if node else 0

	def update_last_seen_at(nodes_ids, last_seen_at, progress_bar = None):
		if not type(nodes_ids) is list: nodes_ids = [nodes_ids]
		for chunker_pos in range(0, len(nodes_ids), 100): # chunk list for SQL
			nodes_chunk = nodes_ids[chunker_pos:chunker_pos+100]
			Node.update(last_seen_at=last_seen_at).where(Node.id << nodes_chunk).execute()
			if progress_bar: progress_bar.update(len(nodes_chunk))
		return True

	def find_or_create_node(parent_node, node_name, node_type):
		node = Node.find_node(parent_node, node_name, node_type)
		if node == None:
			node = Node.create_node(parent_node, node_name, node_type)
		node.clear_my_relevant_cache()
		return node

	def create_node(parent_node, node_name, node_type):
		new_node = Node.create(parent = parent_node, name = node_name, node_type = node_type)
		new_node.clear_my_relevant_cache()
		return new_node

	def find_node(parent_node, node_name, node_type):
		try:
			return Node.get(Node.parent == parent_node, Node.name == node_name, Node.node_type == node_type)
		except DoesNotExist:
			return None

	# def last_node_from_directory_path(directory):
	# 	last_node, directory_list = None, directory.split(os.sep)
	# 	if directory_list[0] == "": directory_list.pop(0)
	#
	# 	for directory_name in directory_list:
	# 		last_node, new = Node.get_or_create(parent = last_node, name = directory_name, node_type = "D")
	#
	# 	return last_node
	#
	# def node_from_file_path(file_name, file_parent):
	# 	file_node, new = Node.get_or_create(parent = file_parent, name = file_name, node_type = "F")
	# 	return file_node


	# def directory_id_from_folder_name(self, folder_name, parent_id, read_only = False):
	# 	value = self.find_folder(folder_name, parent_id)
	# 	if value is None:
	# 		if read_only == True:
	# 			return None
	# 		else:
	# 			value = {}
	# 			value["id"] = self.insert_folder(folder_name, parent_id)

	# 	return value["id"]

	# def directory_id_from_path(self, directory, read_only = False):
	# 	directory = os.path.realpath(directory)
	# 	parent_id, directory_list = 0, directory.split(os.sep)
	# 	if directory_list[0] == "": directory_list.pop(0)

	# 	for directory_name in directory_list:
	# 		parent_id = self.directory_id_from_folder_name(directory_name, parent_id, read_only)
	# 		if parent_id == None: return None

	# 	return parent_id
