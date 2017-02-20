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

    def get_node_path(self, path_type = 'name'):
        node_id = self.id
        path_list = []
        while True:
            node = type(self).get(type(self).id == node_id)
            if path_type == 'name':
                path_list.append(node.name)
            elif path_type == 'plain':
                path_list.append(node.plain_name)
            if node.parent_id == None: break
            node_id = node.parent_id
        path_list.reverse()
        return (os.path.join(*path_list))

from nodes import Node
from remote_node import RemoteNode

db.connect()
db.create_tables([Node,RemoteNode], safe = True)
