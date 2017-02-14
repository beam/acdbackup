#!/usr/local/bin/python3

import os
import re
from peewee import *

db = SqliteDatabase('acdbackup.db', pragmas = ( ("synchronous","OFF"), ("journal_mode","MEMORY") ) )

class Node(Model):

	parent = ForeignKeyField("self", null = True, default = None)
	node_type = FixedCharField(max_length = 1)
	name = TextField(index = True)
	plain_name = TextField(null = True, default = None)
	mtime = TimestampField(null = True, default = None)
	md5 = FixedCharField(max_length = 32, null = True, default = None, index = True)
	size = BigIntegerField(null = True, default = None)

	class Meta:
		database = db

	def save_decrypted_name(encrypted_name, translated_name):
		query = Node.update(plain_name=translated_name).where(Node.name == encrypted_name).execute()

	def find_all_unencrypted_names():
		# return Node.select().where(Node.plain_name == None).limit(10)
		return Node.select().group_by(Node.name).where(Node.plain_name == None)#.limit(1000)

	def find_or_create_node(parent_node, node_name, node_type):
		node = Node.find_node(parent_node, node_name, node_type)
		if node == None:
			node = Node.create_node(parent_node, node_name, node_type)
		return node

	def create_node(parent_node, node_name, node_type):
		return Node.create(parent = parent_node, name = node_name, node_type = node_type)

	def find_node(parent_node, node_name, node_type):
		try:
			return Node.get(Node.parent == parent_node, Node.name == node_name, Node.node_type == node_type)
		except DoesNotExist:
			return None

	def get_node_path(self, path_type = 'name'):
		node_id = self.id
		path_list = []
		while True:
			node = Node.get(Node.id == node_id)
			if path_type == 'name':
				path_list.append(node.name)
			elif path_type == 'plain':
				path_list.append(node.plain_name)
			if node.parent_id == None: break
			node_id = node.parent_id
		path_list.reverse()
		return (os.path.join(*path_list))

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

db.connect()
db.create_tables([Node], safe = True)

