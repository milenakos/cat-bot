import importlib

import discord
import winuvloop
from discord.ext import commands

import config
import database

winuvloop.install()

intents = discord.Intents(message_content=True, messages=True, guilds=True, emojis=True)
bot = commands.AutoShardedBot(
    command_prefix="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    intents=intents,
    member_cache_flags=discord.MemberCacheFlags.none(),
    help_command=None,
    chunk_guilds_at_startup=False,
    allowed_mentions=discord.AllowedMentions.none(),
)


@bot.event
async def setup_hook():
    try:
        await bot.load_extension("stats")
        config.COLLECT_STATS = True
    except commands.ExtensionNotFound:
        config.COLLECT_STATS = False
    await bot.load_extension("main")


async def reload():
    try:
        await bot.unload_extension("main")
    except commands.ExtensionNotLoaded:
        pass
    database.db.close()
    importlib.reload(database)
    database.db.connect()
    await bot.load_extension("main")


bot.cat_bot_reload_hook = reload  # pyright: ignore

database.db.connect()
if not database.db.get_tables():
    database.db.create_tables([database.Profile, database.User, database.Channel, database.Prism])
if "prism" not in database.db.get_tables():
    database.db.create_tables([database.Prism])
if "reminder" not in database.db.get_tables():
    database.db.create_tables([database.Reminder])

try:
    bot.run(config.TOKEN)
finally:
    database.db.close()
