import asyncio
import os

import discord
from discord.ext import commands

# discord bot token, use os.environ for more security
TOKEN = os.environ['token']
# TOKEN = "token goes here"

intents = discord.Intents(message_content=True, messages=True, guilds=True, emojis=True)
bot = commands.AutoShardedBot(command_prefix="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                              intents=intents,
                              help_command=None,
                              chunk_guilds_at_startup=False)

@bot.event
async def setup_hook():
    await bot.load_extension("main")

async def reload():
    await bot.unload_extension("main")
    await asyncio.sleep(3)
    await bot.load_extension("main")

bot.cat_bot_reload_hook = reload  # pyright: ignore
bot.run(TOKEN)
