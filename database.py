import json
import config
import peewee
import playhouse.sqlite_ext

if config.DB_TYPE == "SQLITE":
    db = playhouse.sqlite_ext.SqliteExtDatabase("catbot.db", pragmas=(
        ('cache_size', -1024 * 64),
        ('journal_mode', 'wal')
    ))
elif config.DB_TYPE == "POSTGRES":
    db = peewee.PostgresqlDatabase(
        'cat_bot',
        user='cat_bot',
        password=config.DB_PASS,
        host='localhost',
        port=5432
    )

cattypes = ['Fine', 'Nice', 'Good', 'Rare', 'Wild', 'Baby', 'Epic', 'Sus', 'Brave', 'Rickroll', 'Reverse', 'Superior', 'TheTrashCell', 'Legendary', 'Mythic', '8bit', 'Corrupt', 'Professor', 'Divine', 'Real', 'Ultimate', 'eGirl']

class CappedIntegerField(peewee.IntegerField):
    MAX_VALUE = 2147483647
    MIN_VALUE = -2147483648

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def db_value(self, value):
        if value is not None:
            return max(self.MIN_VALUE, min(self.MAX_VALUE, value))
        return value

class Profile(peewee.Model):
    user_id = peewee.BigIntegerField()
    guild_id = peewee.BigIntegerField(index=True)

    time = peewee.FloatField(default=99999999999999)  # fastest catch time
    timeslow = peewee.FloatField(default=0)  # slowest catch time

    timeout = peewee.BigIntegerField(default=0)  # /preventcatch timestamp
    cataine_active = peewee.BigIntegerField(default=0)  # cataine timestamp

    battlepass = peewee.SmallIntegerField(default=0)  # battlepass level
    progress = peewee.SmallIntegerField(default=0)  # battlepass progress (for do X times levels)

    dark_market_level = peewee.SmallIntegerField(default=0)  # dark market level
    dark_market_active = peewee.BooleanField(default=False)  # dark market unlocked bool
    story_complete = peewee.BooleanField(default=False)  # whether story is complete

    cataine_week = peewee.SmallIntegerField(default=0)  # light market purcashes this week
    recent_week = peewee.SmallIntegerField(default=0)  # the week

    funny = peewee.SmallIntegerField(default=0)  # private embed click amount
    facts = peewee.SmallIntegerField(default=0)  # /fact amount
    gambles = peewee.SmallIntegerField(default=0)  # casino spins amount

    # thanks chatgpt
    # cat types
    for cattype in cattypes:
        locals()[f'cat_{cattype}'] = CappedIntegerField(default=0)

    # aches
    with open("config/aches.json", "r") as f:
        ach_list = json.load(f)
    for ach in ach_list.keys():
        locals()[ach] = peewee.BooleanField(default=False)

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, item, value):
        setattr(self, item, value)

    class Meta:
        # haha facebook meta reference
        database = db
        only_save_dirty = True
        indexes = (
            (('user_id', 'guild_id'), True),
        )


class User(peewee.Model):
    user_id = peewee.BigIntegerField(unique=True, index=True, primary_key=True)

    vote_remind = peewee.BigIntegerField(default=0)  # channel id for vote reminders
    vote_channel = peewee.BigIntegerField(default=0)  # channel id for vote claims
    vote_time_topgg = peewee.BigIntegerField(default=0)  # timestamp of last vote
    reminder_topgg_exists = peewee.BigIntegerField(default=0)  # timestamp of last reminder

    custom = peewee.CharField(default="")  # custom cat name
    emoji = peewee.CharField(default="")  # /editprofile emoji
    color = peewee.CharField(default="")  # /editprofile color
    image = peewee.CharField(default="")  # /editprofile image

    rain_minutes = peewee.SmallIntegerField(default=0) # rain minute balance
    premium = peewee.BooleanField(default=False)  # whether the user has premium
    claimed_free_rain = peewee.BooleanField(default=False)  # whether the user has claimed their free rain

    news_state = peewee.CharField(default="", max_length=2000)

    class Meta:
        database = db
        only_save_dirty = True


class Channel(peewee.Model):
    channel_id = peewee.BigIntegerField(unique=True, index=True, primary_key=True)

    cat = peewee.BigIntegerField(default=0)  # cat message id

    thread_mappings = peewee.BooleanField(default=False)  # whether the channel is a thread

    spawn_times_min = peewee.BigIntegerField(default=120)  # spawn times minimum
    spawn_times_max = peewee.BigIntegerField(default=1200)  # spawn times maximum

    lastcatches = peewee.BigIntegerField(default=0)  # timestamp of last catch
    yet_to_spawn = peewee.BigIntegerField(default=0)  # timestamp of the next catch, if any

    appear = peewee.CharField(default="", max_length=4000)
    cought = peewee.CharField(default="", max_length=4000)

    webhook = peewee.CharField(default="")  # webhook url

    class Meta:
        database = db
        only_save_dirty = True


class Prism(peewee.Model):
    user_id = peewee.BigIntegerField()
    guild_id = peewee.BigIntegerField(index=True)

    time = peewee.BigIntegerField()  # creation time
    creator = peewee.BigIntegerField()  # original crafter
    name = peewee.CharField(max_length=20)  # name (duh)

    for cattype in cattypes: # enabled boosts
        locals()[f'enabled_{cattype.lower()}'] = peewee.BooleanField(default=True)

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, item, value):
        setattr(self, item, value)

    class Meta:
        database = db
        only_save_dirty = True
        indexes = (
            (('user_id', 'guild_id'), False),
        )


class Reminder(peewee.Model):
    user_id = peewee.BigIntegerField()
    time = peewee.BigIntegerField(index=True)
    text = peewee.CharField(max_length=2000)

    class Meta:
        database = db
        only_save_dirty = True
