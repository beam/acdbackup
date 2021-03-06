from peewee import *
from tqdm import tqdm

import os
import time

from acd_progress_bar import AcdProgressBar

from config import ACD_CACHE_PATH, ACD_SETTINGS_PATH
from acdcli.api import client as acdclient_api
from acdcli.api.common import RequestError as acd_RequestError
acd_client = acdclient_api.ACDClient(ACD_CACHE_PATH,ACD_SETTINGS_PATH)

# https://github.com/yadayada/acd_cli/blob/master/acd_cli.py
# https://github.com/yadayada/acd_cli/blob/master/acdcli/api/metadata.py
# https://github.com/yadayada/acd_cli/blob/master/acdcli/cache/sync.py

from database import BaseNode,NodeCache

class RemoteNode(BaseNode):

	id = FixedCharField(max_length = 22, unique = True, null = True,primary_key = True)
	parent = ForeignKeyField("self", null = True, default = None)
	node_type = FixedCharField(max_length = 1)
	name = TextField(index = True)
	plain_name = TextField(null = True, default = None)
	md5 = FixedCharField(max_length = 32, null = True, default = None, index = True)

	cache_section = "R"

	class Meta:
		indexes = (
			(('parent', 'name', 'node_type'), True),
		)

	## Remote calling
	def create_folder(folder_name, parent_id, plain_name = None):
		for attempt in range(10):
			try:
				new_folder = acd_client.create_folder(folder_name, parent_id)
				node = RemoteNode.insert_node_into_cache(new_folder, plain_name)
				node.clear_my_relevant_cache()
				return node
			except acd_RequestError as e:
				if e.msg.find("Rate exceeded") != -1 and e.status_code == 429:
					for i in tqdm(range((attempt+1)*30),desc='Waiting for another try', unit='sec', dynamic_ncols=True):
						time.sleep(1)
				else:
					tqdm.write(str(e))
					return None
		else:
			return None

	def upload_file(local_path, parent_node_id, plain_file_name = None, progress_bar = None):
		result = acd_client.upload_file(local_path, parent_node_id, [AcdProgressBar(progress_bar).update])
		node = RemoteNode.insert_node_into_cache(result, plain_file_name)
		node.clear_my_relevant_cache()
		return node

	def replace_file(local_path, node_id, plain_file_name = None, progress_bar = None):
		result = acd_client.overwrite_file(node_id, local_path, [AcdProgressBar(progress_bar).update])
		node = RemoteNode.insert_node_into_cache(result, plain_file_name)
		node.clear_my_relevant_cache()
		return node

	def rename_file(node_id, new_name, plain_file_name = None):
		for attempt in range(10):
			try:
				result = acd_client.rename_node(node_id, new_name)
				node = RemoteNode.insert_node_into_cache(result, plain_file_name)
				node.clear_my_relevant_cache()
				return node
			except acd_RequestError as e:
				if e.msg.find("Concurrent Access on same node") != -1 and e.status_code == 429:
					for i in tqdm(range((attempt+1)*30),desc='Waiting for another try', unit='sec', dynamic_ncols=True):
						time.sleep(1)
				else:
					tqdm.write(str(e))
					return None
		else:
			return None

	def move_file(node_id, new_parent_id):
		for attempt in range(10):
			try:
				node = RemoteNode.get(id = node_id)
				node.clear_my_relevant_cache()
				result = acd_client.move_node(node_id, new_parent_id)
				node = RemoteNode.insert_node_into_cache(result, node.plain_name)
				node.clear_my_relevant_cache()
				return node
			except acd_RequestError as e:
				if e.msg.find("Concurrent Access on same node") != -1 and e.status_code == 429:
					for i in tqdm(range((attempt+1)*30),desc='Waiting for another try', unit='sec', dynamic_ncols=True):
						time.sleep(1)
				else:
					tqdm.write(str(e))
					return None
		else:
			return None

	## Local cache
	def truncate_cache():
		RemoteNode.delete().execute()

	def get_root_node():
		return RemoteNode.select().where(RemoteNode.parent_id == None).execute().first()

	def set_checkpoint(last_checkpoint):
		RemoteNode.insert(id = 'checkpoint', node_type = 'A', name = last_checkpoint).upsert().execute()
		return last_checkpoint

	def insert_nodes_into_cache(nodes, show_progress = True, handle_cache = True):
		nodes_count = len(nodes)
		if show_progress: progress_bar = tqdm(total=nodes_count, desc='Creating remote nodes in cache', unit='node', dynamic_ncols=True)
		for node in nodes:
			RemoteNode.insert_node_into_cache(node, None, handle_cache)
			if show_progress: progress_bar.update()
		if show_progress: progress_bar.close()

	def insert_node_into_cache(node, plain_name = None, handle_cache = True):
		if node['status'] == 'PENDING': return False
		if node['status'] == 'TRASH': return False
		if node['kind'] == 'FILE':
			if not 'name' in node or not node['name']: return False
			if handle_cache:
				old_node = RemoteNode.select().where(RemoteNode.id == node['id']).limit(1).first()
				if old_node: old_node.clear_my_relevant_cache()
			RemoteNode.insert(id = node['id'], node_type = 'F', name = node.get('name'), md5 = node.get('contentProperties').get('md5'), parent = node.get('parents')[0], plain_name = plain_name).upsert().execute()
		elif node['kind'] == 'FOLDER':
			if 'isRoot' in node and node['isRoot']:
				node['name'] = '/'
				node['parents'] = [None]
				plain_name = '/'
			if not 'name' in node or not node['name']: return False
			if handle_cache:
				old_node = RemoteNode.select().where(RemoteNode.id == node['id']).limit(1).first()
				if old_node: old_node.clear_my_relevant_cache()
			RemoteNode.insert(id = node['id'], node_type = 'D', name = node.get('name'), parent = node.get('parents')[0], plain_name = plain_name).upsert().execute()
		else:
			return False

		inserted_node = RemoteNode.get(id = node['id'])
		inserted_node.clear_my_relevant_cache()
		return inserted_node

	def remove_nodes_from_cache(nodes, show_progress = True, handle_cache = True):
		if show_progress: progress_bar = tqdm(total=len(nodes), desc='Removing remote nodes from cache', unit='node', dynamic_ncols=True)
		for node in nodes:
			RemoteNode.remove_node_from_cache(node,handle_cache)
			if show_progress: progress_bar.update()
		if show_progress: progress_bar.close()

	def remove_node_from_cache(node_id, handle_cache = True):
		if handle_cache:
			node = RemoteNode.select().where(RemoteNode.id == node_id).limit(1).first()
			if node: node.clear_my_relevant_cache()
		return RemoteNode.delete().where(RemoteNode.id == node_id).execute()

	def checkpoint():
		try:
			return RemoteNode.get(id = 'checkpoint', node_type = 'A').name
		except DoesNotExist:
			return None

	def sync():
		checkpoint = RemoteNode.checkpoint()
		if checkpoint == None: RemoteNode.truncate_cache()
		acd_changeset_file = acd_client.get_changes(checkpoint=checkpoint, include_purged=bool(checkpoint))
		changeset_count = sum(1 for line in acd_changeset_file) - 1
		acd_changeset_file.seek(0)
		progress_bar = tqdm(total=changeset_count, desc='Processing changesets', unit='changeset', dynamic_ncols=True)
		for changeset in acd_client._iter_changes_lines(acd_changeset_file):
			if changeset.reset:
				RemoteNode.truncate_cache()
			else:
				if len(changeset.purged_nodes) > 0: RemoteNode.remove_nodes_from_cache(changeset.purged_nodes, True, False)

			if len(changeset.nodes) > 0: RemoteNode.insert_nodes_into_cache(changeset.nodes, True, False)
			if len(changeset.nodes) > 0 or len(changeset.purged_nodes) > 0: RemoteNode.set_checkpoint(changeset.checkpoint)
			progress_bar.update()
		progress_bar.close()
		NodeCache.clear_section(RemoteNode.cache_section)

	def is_chrooted(self, chroot_node_id):
		return chroot_node_id in self.get_node_path('id')
