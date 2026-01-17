import os

# discord bot token
TOKEN = os.environ["TOKEN"]

# db password for postgres
# user - cat_bot, database - cat_bot, ip - localhost, port - default
DB_PASS = os.environ["psql_password"]

#
# all the following are optional (If not set they will default to None, disabling the feature)
#

# dsn of a sentry-compatible service for error logging
SENTRY_DSN = os.environ.get("sentry_dsn")

# top.gg vote webhook verification key, setting this to None disables all voting stuff
WEBHOOK_VERIFY = os.environ.get("webhook_verify")

# top.gg api token to occasionally post stats
TOP_GG_TOKEN = os.environ.get("top_gg_token")

# wordnik api key for /define command
WORDNIK_API_KEY = os.environ.get("wordnik_api_key")

# only post stats if server count is above this, to prevent wrong stats
MIN_SERVER_SEND = 125_000

# channel id for db backups, private extremely recommended
BACKUP_ID = 1060545763194707998

# channel to store supporter images, can also be used for moderation purposes
DONOR_CHANNEL_ID = 1249343008890028144

# cat bot will also log all rain uses/movements here
# cat!rain commands here can be used without author check and will dm reciever a thanks message
RAIN_CHANNEL_ID = 1278705994536321157
