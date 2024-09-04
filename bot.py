import discord
from discord.ext import commands

import config
from database import db, Profile, User, Channel

intents = discord.Intents(message_content=True, messages=True, guilds=True, emojis=True)
bot = commands.AutoShardedBot(command_prefix="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                              intents=intents,
                              help_command=None,
                              chunk_guilds_at_startup=False)

@bot.event
async def setup_hook():
    await bot.load_extension("main")

async def reload():
    try:
        await bot.unload_extension("main")
    except commands.ExtensionNotLoaded:
        pass
    await bot.load_extension("main")

bot.cat_bot_reload_hook = reload  # pyright: ignore

db.connect()
if not db.get_tables():
    db.create_tables([Profile, User, Channel])

try:
    bot.run(config.TOKEN)
finally:
    db.close()
