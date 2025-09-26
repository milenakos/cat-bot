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

import asyncio
import importlib
import time

import discord
import sentry_sdk
import winuvloop
from discord.ext import commands

import catpg
import config
import database

winuvloop.install()

filtered_errors = [
    # inactionable/junk discord api errors
    "Too Many Requests",
    "You are being rate limited",
    "Invalid Webhook Token",
    "Unknown Interaction",
    "Unknown Webhook",
    "Failed to convert",
    "CommandNotFound",
    "CommandAlreadyRegistered",
    "Cannot send an empty message",
    # connection errors and warnings
    "ClientConnectorError",
    "DiscordServerError",
    "WSServerHandshakeError",
    "ConnectionClosed",
    "ConnectionResetError",
    "TimeoutError",
    "ServerDisconnectedError",
    "ClientOSError",
    "TransferEncodingError",
    "Request Timeout",
    "Session is closed",
    "Unclosed connection",
    "unable to perform operation on",
    "503 Service Unavailable",
]


def before_send(event, hint):
    if "exc_info" not in hint:
        return event
    for i in filtered_errors:
        if i in str(hint["exc_info"][0]) + str(hint["exc_info"][1]):
            return None
    return event


if config.SENTRY_DSN:
    sentry_sdk.init(dsn=config.SENTRY_DSN, before_send=before_send)


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
    await database.connect()
    await bot.load_extension("main")


async def reload(reload_db):
    try:
        await bot.unload_extension("main")
    except commands.ExtensionNotLoaded:
        pass
    if reload_db:
        await database.close()
        importlib.reload(database)
        importlib.reload(catpg)
        await database.connect()
    await bot.load_extension("main")


bot.cat_bot_reload_hook = reload  # pyright: ignore

try:
    config.HARD_RESTART_TIME = time.time()
    bot.run(config.TOKEN)
finally:
    asyncio.run(database.close())