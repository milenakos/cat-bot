# Cat Bot - A Discord bot about catching cats.
# Copyright (C) 2025 Lia Milenakos & Cat Bot Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import importlib

import discord
import winuvloop
from discord.ext import commands

import config
import database

winuvloop.install()

bot = commands.AutoShardedBot(
    command_prefix="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    help_command=None,
    chunk_guilds_at_startup=False,
    allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False),
    intents=discord.Intents(message_content=True, messages=True, guilds=True),
    member_cache_flags=discord.MemberCacheFlags.none(),
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


async def reload(reload_db):
    try:
        await bot.unload_extension("main")
    except commands.ExtensionNotLoaded:
        pass
    if reload_db:
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
