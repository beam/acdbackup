ENCFS_PASS="--encfs--password--here--"
ENCFS6_CONFIG="/root/.encfs6.xml"

TMP_DIR = "/tmp"

ACD_CACHE_PATH = "/root/.cache/acd_cli"
ACD_SETTINGS_PATH = "/root/.config/acd_cli"

BACKUP_DIR = "/backup"

REMOTE_BACKUP_DESTINATION = "/Backup"

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

BACKUP_EXCLUDE = [
	'HDD2/DO/NOT/COPY/THIS'
]

LOG_FILE = "acdbackup.log"
