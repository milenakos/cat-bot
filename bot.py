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
import sys
import time

import asyncpg
import discord
import sentry_sdk
import sentry_sdk.types
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
    import stats  # type: ignore  # noqa: F401

    log_level = logging.DEBUG
except ImportError:
    pass


winuvloop.install()


def before_send(event: sentry_sdk.types.Event, hint: sentry_sdk.types.Hint) -> sentry_sdk.types.Event | None:
    if "exc_info" not in hint:
        return event

    for i in config.filtered_errors:
        if i.lower() in str(hint["exc_info"][0]).lower() + str(hint["exc_info"][1]).lower():
            return None

    commit = None
    tb = hint["exc_info"][2]
    while tb is not None:
        c = tb.tb_frame.f_globals.get("COMMIT")
        if c:
            commit = c
        tb = tb.tb_next
    if commit is None:
        commit = getattr(sys.modules.get("main"), "COMMIT", None)
    if commit:
        event["release"] = commit

    return event


if config.SENTRY_DSN:
    sentry_sdk.init(dsn=config.SENTRY_DSN, before_send=before_send)


if len(sys.argv) == 4:
    start = int(sys.argv[1])
    end = int(sys.argv[2])
    total = int(sys.argv[3])
    shard_ids = list(range(start, end))
    shard_count = total
    config.CLUSTERING = True
    config.CLUSTERING_ZERO = start == 0
else:
    shard_ids = None
    shard_count = None


bot = commands.AutoShardedBot(
    command_prefix="cat!",
    case_insensitive=True,
    help_command=None,
    chunk_guilds_at_startup=False,
    allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False),
    intents=discord.Intents(message_content=True, messages=True, guilds=True),
    member_cache_flags=discord.MemberCacheFlags.none(),
    allowed_mentions=discord.AllowedMentions.none(),
    shard_ids=shard_ids,  # type: ignore
    shard_count=shard_count,
)


@bot.event
async def setup_hook() -> None:
    global listener_conn

    await database.connect()
    if config.CLUSTERING:
        listener_conn = await catpg._get_pool().acquire()
        await listener_conn.add_listener("restarts", reload_call)
    await bot.load_extension("main")


async def reload(reload_db: bool) -> None:
    global listener_conn

    try:
        await bot.unload_extension("main")
    except commands.ExtensionNotLoaded:
        pass
    if reload_db:
        if config.CLUSTERING:
            await listener_conn.remove_listener("restarts", reload_call)
            await catpg._get_pool().release(listener_conn)
        await database.close()
        importlib.reload(database)
        importlib.reload(catpg)
        await database.connect()
        if config.CLUSTERING:
            listener_conn = await catpg._get_pool().acquire()
            await listener_conn.add_listener("restarts", reload_call)
    await bot.load_extension("main")


async def reload_call(conn: asyncpg.Connection, pid: int, channel: str, payload: str) -> None:
    if "config" in payload:
        importlib.reload(config)
    if "msg2img" in payload:
        importlib.reload(__import__("msg2img"))
    await reload("db" in payload)


async def shutdown() -> None:
    if config.CLUSTERING:
        await listener_conn.remove_listener("restarts", reload_call)
        await catpg._get_pool().release(listener_conn)
    await database.close()


bot.cat_bot_reload_hook = reload  # pyright: ignore


try:
    config.HARD_RESTART_TIME = time.time()
    bot.run(config.TOKEN, log_handler=handler, log_level=log_level)
except KeyboardInterrupt:
    pass
finally:
    asyncio.run(shutdown())
