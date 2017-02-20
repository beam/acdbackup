from peewee import *

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

from nodes import Node
from remote_node import RemoteNode

db.connect()
db.create_tables([Node,RemoteNode], safe = True)
