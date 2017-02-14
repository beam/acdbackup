ENCFS_PASS="--encfs--password--here--"
ENCFS6_CONFIG="/root/.encfs6.xml"

TMP_DIR = "/tmp"

CACHE_PATH = "/root/.cache/acd_cli"
SETTINGS_PATH = "/root/.config/acd_cli"

BACKUP_DIR = "/backup"

BACKUP = [
	{
		'source'	:	'/nas/HDD1', # real path 
		'dest'		:	BACKUP_DIR + '/HDD1' # encrypted fs
	},
	{
		'source'	:	'/nas/HDD2',
		'dest'		:	BACKUP_DIR + '/HDD2'
	},
]