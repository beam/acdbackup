from peewee import *
from tqdm import tqdm

import time

from config import ACD_CACHE_PATH, ACD_SETTINGS_PATH
from acdcli.api import client as acdclient_api
from acdcli.api.common import RequestError as acd_RequestError
acd_client = acdclient_api.ACDClient(ACD_CACHE_PATH,ACD_SETTINGS_PATH)

# https://github.com/yadayada/acd_cli/blob/master/acd_cli.py
# https://github.com/yadayada/acd_cli/blob/master/acdcli/api/metadata.py
# https://github.com/yadayada/acd_cli/blob/master/acdcli/cache/sync.py

from database import BaseNode

class RemoteNode(BaseNode):

	id = FixedCharField(max_length = 22, unique = True, null = True,primary_key = True)
	parent = ForeignKeyField("self", null = True, default = None)
	node_type = FixedCharField(max_length = 1)
	name = TextField(index = True)
	plain_name = TextField(null = True, default = None)
	md5 = FixedCharField(max_length = 32, null = True, default = None, index = True)

	class Meta:
		indexes = (
			(('parent', 'name', 'node_type'), True),
		)

	## Remote calling
	def create_folder(folder_name, parent_id, plain_name = None):
		for attempt in range(10):
			try:
				new_folder = acd_client.create_folder(folder_name, parent_id)
				RemoteNode.insert_node(new_folder, plain_name)
				return RemoteNode.get(RemoteNode.id == new_folder.get('id'))
			except acd_RequestError as e:
				if e.msg.find("Rate exceeded") != -1 and e.status_code == 429:
					for i in tqdm(range((attempt+1)*30),desc='Waiting for another try', unit='sec', dynamic_ncols=True):
						time.sleep(1)
				else:
					tqdm.write(str(e))
					return None
		else:
			return None

	## Local cache
	def truncate():
		RemoteNode.delete().execute()

	def get_root_node():
		node = RemoteNode.select().where(RemoteNode.parent_id == None).naive()
		if node:
		    return node.first()
		else:
		    return None

	def set_checkpoint(last_checkpoint):
		RemoteNode.insert(id = 'checkpoint', node_type = 'A', name = last_checkpoint).upsert().execute()
		return last_checkpoint

	def insert_nodes(nodes, show_progress = True):
		nodes_count = len(nodes)
		if show_progress: progress_bar = tqdm(total=nodes_count, desc='Creating remote nodes in cache', unit='node', dynamic_ncols=True)
		for node in nodes:
			RemoteNode.insert_node(node)
			if show_progress: progress_bar.update()
		if show_progress: progress_bar.close()

	def insert_node(node, plain_name = None):
		if node['status'] == 'PENDING': return False
		if node['status'] == 'TRASH': return False
		if node['kind'] == 'FILE':
			if not 'name' in node or not node['name']: return False
			RemoteNode.insert(id = node['id'], node_type = 'F', name = node.get('name'), md5 = node.get('contentProperties').get('md5'), parent = node.get('parents')[0], plain_name = plain_name).upsert().execute()
		elif node['kind'] == 'FOLDER':
			if 'isRoot' in node and node['isRoot']:
				node['name'] = '/'
				node['parents'] = [None]
				plain_name = '/'
			if not 'name' in node or not node['name']: return False
			RemoteNode.insert(id = node['id'], node_type = 'D', name = node.get('name'), parent = node.get('parents')[0], plain_name = plain_name).upsert().execute()
		else:
			return False
		return RemoteNode.get(id = node['id'])

	def remove_nodes(nodes, show_progress = True):
		if show_progress: progress_bar = tqdm(total=len(nodes), desc='Removing remote nodes from cache', unit='node', dynamic_ncols=True)
		for node in nodes:
			RemoteNode.remove_node(node)
			if show_progress: progress_bar.update()
		if show_progress: progress_bar.close()

	def remove_node(node_id):
		return RemoteNode.delete().where(RemoteNode.id == node_id).execute()

	def checkpoint():
		try:
			return RemoteNode.get(id = 'checkpoint', node_type = 'A').name
		except DoesNotExist:
			return None

	def sync():
		checkpoint = RemoteNode.checkpoint()
		if checkpoint == None: RemoteNode.truncate()
		acd_changeset_file = acd_client.get_changes(checkpoint=checkpoint, include_purged=bool(checkpoint))
		changeset_count = sum(1 for line in acd_changeset_file) - 1
		acd_changeset_file.seek(0)
		progress_bar = tqdm(total=changeset_count, desc='Processing changesets', unit='changeset', dynamic_ncols=True)
		for changeset in acd_client._iter_changes_lines(acd_changeset_file):
			if changeset.reset:
				RemoteNode.truncate()
			else:
				if len(changeset.purged_nodes) > 0: RemoteNode.remove_nodes(changeset.purged_nodes)

			if len(changeset.nodes) > 0: RemoteNode.insert_nodes(changeset.nodes)
			if len(changeset.nodes) > 0 or len(changeset.purged_nodes) > 0: RemoteNode.set_checkpoint(changeset.checkpoint)
			progress_bar.update()
		progress_bar.close()
