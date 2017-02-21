from peewee import *
import os

db = SqliteDatabase('acdbackup.db', pragmas = ( ("synchronous","OFF"), ("journal_mode","MEMORY") ) )

class BaseNode(Model):
    class Meta:
        database = db

    @classmethod
    def save_decrypted_name(cls,encrypted_name, translated_name):
    	return cls.update(plain_name=translated_name).where(cls.name == encrypted_name).execute()

    @classmethod
    def find_all_unencrypted_names(cls):
    	return cls.select().group_by(cls.name).where(cls.plain_name == None)

    @classmethod
    def find_node_by_path(cls, search_path, last_seen_at = None):
        split_path = search_path.split(os.path.sep)
        parent_node = None
        for counter, path_part in enumerate(split_path):
            if path_part == "": path_part = "/"
            nodes = cls.select().where(cls.name == path_part).where(cls.node_type << ["F","D"]).where(cls.parent_id == parent_node)
            if last_seen_at: nodes = nodes.where(cls.last_seen_at == last_seen_at) # for local Node
            nodes = nodes.naive()
            if len(nodes) == 0:
                return None
            elif len(nodes) == 1:
                parent_node = nodes.first().id
            elif len(nodes) > 1:
                print(path_part, parent_node)
                raise Exception("More than one result by name")
        return nodes.first()

    @classmethod
    def get_all_subdirectories(cls, parent_id, last_seen_at = None):
        nodes = cls.select().where(cls.parent_id == parent_id).where(cls.node_type == 'D')
        if last_seen_at: nodes = nodes.where(cls.last_seen_at == last_seen_at) # for local Node
        return nodes.naive()

    @classmethod
    def get_dir_by_name_and_parent(cls, directory_name, parent_id, last_seen_at = None):
        nodes =  cls.select().where(cls.parent_id == parent_id).where(cls.node_type == 'D').where(cls.name == directory_name)
        if last_seen_at: nodes = nodes.where(cls.last_seen_at == last_seen_at) # for local Node
        return nodes.naive()

    def get_node_path(self, path_type = 'name', stop_on_node = None):
        node_id = self.id
        path_list = []
        while True:
            node = type(self).get(type(self).id == node_id)
            if path_type == 'name':
                path_list.append(node.name)
            elif path_type == 'plain':
                path_list.append(node.plain_name)
            if node.parent_id == None or node.parent_id == stop_on_node: break
            node_id = node.parent_id
        path_list.reverse()
        return (os.path.join(*path_list))


from nodes import Node
from remote_node import RemoteNode

db.connect()
db.create_tables([Node,RemoteNode], safe = True)
