from peewee import *
import re, os

db = SqliteDatabase('acdbackup.db', threadlocals=False, check_same_thread=False, pragmas = (
    ( 'busy_timeout', 30000 ), # 30 s
    ( 'synchronous' , 'OFF' ),
))

from peewee import NaiveQueryResultWrapper
def query_first(self):
    if self.count == 0: return None
    for item in self.__iter__():
        return item
NaiveQueryResultWrapper.first = query_first

class NodeCache():

    cache = {}

    def build_key_cache(key):
        if type(key) is str:
            return key
        elif type(key) is int:
            return str(key)
        elif type(key) is tuple:
            return "@".join(str(i) for i in key)
        elif type(key) is list:
            return "@".join(str(i) for i in key)
        else:
            raise Exception("Wrong key type")

    # section = RemoteNode, Node
    # keyable = id, parent_id, md5
    # key = "id", "id@other-spec"
    # value = cached value
    @classmethod
    def set(cls, section, keyable, key, value):
        key = NodeCache.build_key_cache(key)
        if not section in cls.cache: cls.cache[section] = {}
        if not keyable in cls.cache[section]: cls.cache[section][keyable] = {}
        cls.cache[section][keyable][key] = value

    @classmethod
    def is_cached(cls, section, keyable, key):
        key = NodeCache.build_key_cache(key)
        return (section in cls.cache and keyable in cls.cache[section] and key in cls.cache[section][keyable])

    @classmethod
    def get(cls, section, keyable, key):
        key = NodeCache.build_key_cache(key)
        return cls.cache[section][keyable][key] if NodeCache.is_cached(section, keyable,key) else None

    @classmethod
    def clear_key(cls, section, keyable, key_id):
        if not section in cls.cache: return 0
        if not keyable in cls.cache[section]: return 0
        regexp = re.compile(r'^' + str(key_id) + r'($|@.*)')
        keys_for_delete = []
        for key,value in cls.cache[section][keyable].items():
            if regexp.match(str(key)): keys_for_delete.append(key)
        for key in keys_for_delete:
            del cls.cache[section][keyable][key]
        return len(keys_for_delete)

    @classmethod
    def clear_section(cls,section):
        cls.cache[section] = {}

    @classmethod
    def clear(cls):
        cls.cache = {}

    @classmethod
    def print_me(cls):
        print(cls.cache)

class BaseNode(Model):
    class Meta:
        database = db

    @classmethod
    def save_decrypted_name(cls,encrypted_name, translated_name):
    	return cls.update(plain_name=translated_name).where(cls.name == encrypted_name).execute()

    @classmethod
    def find_all_unencrypted_names(cls):
        return cls.select().group_by(cls.name).where((cls.plain_name == None) | (cls.plain_name == ''))

    @classmethod
    def find_node_by_path(cls, search_path, last_seen_at = None, parent_node = None, search_by = 'name'):
        if search_path == '' and parent_node != None: return cls.get(id = parent_node)
        split_path = search_path.split(os.path.sep)
        for counter, path_part in enumerate(split_path):
            if path_part == "": path_part = "/"
            if not NodeCache.is_cached(cls.cache_section, "parent", (parent_node,path_part,last_seen_at)):
                nodes = cls.select().where(cls.node_type << ["F","D"]).where(cls.parent_id == parent_node)
                nodes = nodes.where(cls.plain_name == path_part) if search_by == 'plain' else nodes.where(cls.name == path_part)
                if last_seen_at: nodes = nodes.where(cls.last_seen_at == last_seen_at) # for local Node
                nodes = nodes.execute()
                if search_by == 'name': NodeCache.set(cls.cache_section, "parent", (parent_node,path_part,last_seen_at), nodes)
            else:
                nodes = NodeCache.get(cls.cache_section, "parent", (parent_node,path_part,last_seen_at))
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
        return nodes.execute()

    @classmethod
    def get_dir_by_name_and_parent(cls, directory_name, parent_id, last_seen_at = None):
        nodes =  cls.select().where(cls.parent_id == parent_id).where(cls.node_type == 'D').where(cls.name == directory_name)
        if last_seen_at: nodes = nodes.where(cls.last_seen_at == last_seen_at) # for local Node
        return nodes.execute()

    @classmethod
    def get_file_by_name_and_parent(cls, directory_name, parent_id, last_seen_at = None):
        nodes =  cls.select().where(cls.parent_id == parent_id).where(cls.node_type == 'F').where(cls.name == directory_name)
        if last_seen_at: nodes = nodes.where(cls.last_seen_at == last_seen_at) # for local Node
        return nodes.execute()

    @classmethod
    def clear_relevant_cache(cls, node):
        if node == None: return False
        if type(node) is str:
            node_ids = [node]
        else:
            node_ids = [node.id, node.parent_id]

        for node_id in node_ids:
            if node_id == None: continue
            NodeCache.clear_key(cls.cache_section, 'id', node_id)
            NodeCache.clear_key(cls.cache_section, 'parent', node_id)

        return True

    def clear_my_relevant_cache(self):
        type(self).clear_relevant_cache(self)

    def get_node_path(self, path_type = 'name', stop_on_node = None):
        node_id = self.id
        path_list = []
        while True:
            if not NodeCache.is_cached(self.cache_section, "id", node_id):
                node = type(self).get(type(self).id == node_id)
                NodeCache.set(self.cache_section, "id", node_id, node)
            else:
                node = NodeCache.get(self.cache_section, "id", node_id)
            if path_type == 'name':
                path_list.append(node.name)
            elif path_type == 'plain':
                path_list.append(node.plain_name)
            elif path_type == 'id':
                path_list.append(node.id)
            if node.parent_id == None or node.parent_id == stop_on_node: break
            node_id = node.parent_id
        path_list.reverse()
        if path_type == 'id': return path_list
        return (os.path.join(*path_list))

from nodes import Node
from remote_node import RemoteNode

db.connect()
db.create_tables([Node,RemoteNode], safe = True)
