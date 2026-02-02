# Cat Bot - A Discord bot about catching cats.
# Copyright (C) 2026 Lia Milenakos & Cat Bot Contributors
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
import logging
import time

import discord
import sentry_sdk
import winuvloop
from discord.ext import commands

import catpg
import config
import database

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
logger.addHandler(handler)
log_level = logging.INFO

try:
    # this is a messy closed source script which injects into logging module to do statistics
    # inside discord.py, it only intercepts the amount of status codes and ratelimits
    # everything else is from main.py logging.debug() statements
    import stats  # noqa: F401

    log_level = logging.DEBUG
except ImportError:
    pass


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
    "Event loop is closed",
    "503 Service Unavailable",
]


def before_send(event, hint):
    if "exc_info" not in hint:
        return event
    for i in filtered_errors:
        if i.lower() in str(hint["exc_info"][0]).lower() + str(hint["exc_info"][1]).lower():
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


config.cat_cought_rain = {}
config.rain_starter = {}

bot.cat_bot_reload_hook = reload  # pyright: ignore

try:
    config.HARD_RESTART_TIME = time.time()
    bot.run(config.TOKEN, log_handler=handler, log_level=log_level)
finally:
    asyncio.run(database.close())
