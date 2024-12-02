import os

# discord bot token
TOKEN = os.environ['token']

# database type
# either SQLITE or POSTGRES
DB_TYPE = "POSTGRES"

# db pass if postgres (user is cat_bot), otherwise set to None
DB_PASS = os.environ["psql_password"]

# channel id for db backups, private extremely recommended
# temporarily doesnt actually backup, just sends stats.
BACKUP_ID = 1060545763194707998

# what to do when there is a crash
CRASH_MODE = "RAISE"

#
# all the following are optional (setting them to None will disable the feature)
#

# top.gg voting key
WEBHOOK_VERIFY = os.environ["webhook_verify"]

# top.gg api token because they use ancient technology and you need to post server count manually smh
TOP_GG_TOKEN = os.environ["top_gg_token"]

# this will automatically restart the bot if message in GITHUB_CHANNEL_ID is sent, you can use a github webhook for that
GITHUB_CHANNEL_ID = 1060965767044149249

# all messages in this channel will be interpreted as user ids to give premium access to
# (deprecated, all rain buyes get premium for free now)
DONOR_CHANNEL_ID = 1249343008890028144

# all messages in this channel are allowed to be cat!rain commands
RAIN_CHANNEL_ID = 1278705994536321157
