import os

# discord bot token
TOKEN = os.environ["TOKEN"]

# db password for postgres
# user - cat_bot, database - cat_bot, ip - localhost, port - default
DB_PASS = os.environ["psql_password"]

#
# all the following are optional (setting them to None will disable the feature)
#

try:
    env_vars = [os.environ["sentry_dsn"], os.environ["webhook_verify"], os.environ["top_gg_token"], os.environ["wordnik_api_key"]]
except KeyError:
    env_vars = [None, None, None, None]

# dsn of a sentry-compatible service for error logging
SENTRY_DSN = env_vars[0]

# top.gg vote webhook verification key, setting this to None disables all voting stuff
WEBHOOK_VERIFY = env_vars[1]

# top.gg api token to occasionally post stats
TOP_GG_TOKEN = env_vars[2]

# wordnik api key for /define command
WORDNIK_API_KEY = env_vars[3]

# only post stats if server count is above this, to prevent wrong stats
MIN_SERVER_SEND = 125_000

# channel id for db backups, private extremely recommended
BACKUP_ID = 1060545763194707998

# channel to store supporter images, can also be used for moderation purposes
DONOR_CHANNEL_ID = 1249343008890028144

# cat bot will also log all rain uses/movements here
# cat!rain commands here can be used without author check and will dm reciever a thanks message
RAIN_CHANNEL_ID = 1278705994536321157

# stores channels where fake egirl command was used: {channel_id: message_id}
fake_egirl_storage = {}
