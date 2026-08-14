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
import base64
import datetime
import hashlib
import hmac
import io
import json
import logging
import math
import os
import platform
import random
import re
import subprocess
import sys
import time
import traceback
from collections.abc import Awaitable, Callable
from typing import Literal, TypedDict

import aiohttp
import anyio
import discord
import discord.gateway
import discord.http
import discord_emoji
import emoji
import psutil
import unidecode  # type: ignore
from aiohttp import web
from discord import ButtonStyle
from discord.ext import commands
from discord.ui import ActionRow, Button, LayoutView, Modal, Separator, TextDisplay, TextInput, Thumbnail, View
from PIL import Image

import config
import graph
import msg2img
from catpg import RawSQL, _get_pool, transaction
from database import Channel, Order, PortfolioHistory, PriceHistory, Prism, Profile, Reminder, Restore, Reward, Server, User

try:
    import exportbackup  # type: ignore
except ImportError:
    exportbackup = None

try:
    COMMIT = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
except subprocess.CalledProcessError:
    COMMIT = "unknown"

logger = logging.getLogger()


def plural(word: str, count: int) -> str:
    if count == 1:
        return word
    return word + "s"


# trigger warning, base64 encoded for your convinience
NONOWORDS = [base64.b64decode(i).decode("utf-8") for i in ["bmlja2E=", "bmlja2Vy", "bmlnYQ==", "bmlnZ2E=", "bmlnZ2Vy"]]


class PackEntry(TypedDict):
    name: str
    value: int
    upgrade: int
    totalvalue: int
    special: bool


class NewsEntry(TypedDict):
    title: str
    emoji: str
    active: bool


class SparkleEntry(TypedDict):
    odds: float
    emoji: str
    percent: str
    punct: str


class FishingEntry(TypedDict):
    cost: int
    value: float


class StockEntry(TypedDict):
    name: str
    ticker: str
    emoji: str
    amount: int
    init_price: int


class DataWrapper:
    type_dict: dict[str, int]
    filtered_errors: list[str]
    pack_data: list[PackEntry]
    badge_list: list[str]
    prism_names_start: list[str]
    prism_names_end: list[str]
    vote_button_texts: list[str]
    hints: list[str]
    funny: list[str]
    news_list: list[NewsEntry]
    achs: dict[str, str]
    reactions: dict[str, str]
    responses: dict[str, str]
    letter_mapping: dict[str, str]
    dark_market_followups: list[str]
    custom_cough_strings: dict[str, str]
    sparkle_messages: list[SparkleEntry]
    roulette_colors: list[str]  # mapping of colors to numbers by indexes
    cat_translations: list[str]
    wiki_lines: list[str]
    illegal: list[str]
    sentences: list[str]
    cat_fortunes: list[str]
    cat_fortune_titles: list[str]
    cat_activities: list[str]
    debt_msgs: list[str]
    family_guy_funny_moments: list[str]  # ??? (used in /roll when sides=0)
    catball_responses: list[str]
    dice_names: dict[str, str]  # loosely based on https://en.wikipedia.org/wiki/Dice
    scratch_opts: list[str]
    win_combinations: list[list[int]]
    nuke_confirmation_lines: list[str]
    fishing_upgrades: dict[str, list[FishingEntry]]
    stock_data: list[StockEntry]

    def __init__(self, data):
        self.data = data

    def __getitem__(self, key):
        return self.data[key]

    def __getattr__(self, key):
        return self.data[key]


# static data (large lists/dicts) is kept in dicts.json and loaded once here
with open("dicts.json", "r", encoding="utf-8") as f:
    data = DataWrapper(json.load(f))

# this list stores unique non-duplicate cattypes
cattypes: list[str] = list(data.type_dict.keys())

TOTAL_CAT_WEIGHT = sum(data.type_dict.values())
CAT_VALUES = {ct: TOTAL_CAT_WEIGHT / data.type_dict[ct] for ct in cattypes}
PRISM_VALUE = round(sum(CAT_VALUES.values()), 2)

cattype_lc_dict = {i.lower(): i for i in cattypes}
allowedemojis = [i.lower() + "cat" for i in cattypes]

pack_names = [i["name"] for i in data.pack_data]
prism_names = [j + i for i in data.prism_names_end for j in data.prism_names_start]

config.filtered_errors = data.filtered_errors

last_active_article = [k for k, v in enumerate(data.news_list) if v["active"]][-1]


# laod the jsons
with open("config/aches.json", "r") as f:
    ach_list = json.load(f)

with open("config/battlepass.json", "r", encoding="utf-8") as f:
    config.battle = json.load(f)

with open("config/catnip.json", "r", encoding="utf-8") as f:
    catnip_list = json.load(f)

with open("assets/lists/facts.txt") as f:
    cat_facts_list = f.read().split("\n")

with open("assets/lists/fanhalo.txt") as f:
    fanhalo_list = f.read().split("\n")

with open("assets/lists/rickroll.txt") as f:
    rickroll_list = [line for line in f.read().split("\n") if line]


# convert achievement json to a few other things
ach_names = ach_list.keys()
ach_titles = {value["title"].lower(): key for (key, value) in ach_list.items()}

bot = commands.AutoShardedBot(
    command_prefix="this is a placebo bot which will be replaced when this will get loaded",
    intents=discord.Intents.default(),
)


class TTLStore:
    def __init__(self, ttl: float) -> None:
        self.ttl = ttl
        self._data: dict = {}

    def add(self, key) -> None:
        self._data[key] = time.time()

    def discard(self, key) -> None:
        self._data.pop(key, None)

    def __contains__(self, key) -> bool:
        ts = self._data.get(key)
        return ts is not None and ts + self.ttl > time.time()

    def expire(self, now: float) -> None:
        cutoff = now - self.ttl
        self._data = {k: t for k, t in self._data.items() if t > cutoff}


class Colors:
    brown = 0x6E593C
    gray = 0xCCCCCC
    green = 0x007F0E
    yellow = 0xFFFF00
    maroon = 0x750F0E
    demonic = 0xC12929
    rose = 0xFF81C6
    red = 0xFF0000


GuildMessageable = discord.TextChannel | discord.Thread | discord.VoiceChannel | discord.StageChannel | discord.PartialMessageable


# rain shill message for footers
rain_shill = "☔ Get tons of cats /rain"

# timeout for views
# higher one means buttons work for longer but uses more ram to keep track of them
VIEW_TIMEOUT = 3600 * 24

# store credits usernames to prevent excessive api calls
gen_credits = {}

# due to some stupid individuals spamming the hell out of reactions, we ratelimit them
reactions_ratelimit = {}

# sort of the same thing but for pointlaughs and per channel instead of peruser
pointlaugh_ratelimit = {}

# cooldowns for some commands
catchcooldown = TTLStore(6)
fakecooldown = TTLStore(30)
customcatcooldown = TTLStore(300)

# prevent ratelimits/abuse
casino_lock = TTLStore(60)
slots_lock = TTLStore(60)
fish_lock = TTLStore(60)

# ???
rigged_users = []

# to prevent double catches
temp_catches_storage = TTLStore(60)

# to prevent double spawns
temp_spawns_storage = TTLStore(60)

# to avoid expensive db queries
temp_stock_prices = {}

# stocks stuff
INSTANT_SPREAD = 0.04
QUEUED_SPREAD = 0.01
PRICE_IMPACT_WARNING = 0.10
stock_reward_tasks: set[tuple[str, int]] = set()

# docs suggest on_ready can be called multiple times
on_ready_debounce = False

# fallback for fetching missing votes on background loops using top.gg replay api thing
try:
    with open("cursor.txt", "r", encoding="utf-8") as f:
        last_vote_cursor = f.read().strip() or None
except FileNotFoundError:
    last_vote_cursor = None

# d.py doesnt cache app emojis so we do it on our own yippe
emojis = {}

# for mentioning em, will be auto-fetched in on_ready()
COMMAND_IDS = {}

# for dev commands, this is fetched in on_ready
OWNER_ID = 553093932012011520

# for funny stats, you can probably edit background_loop to restart every X of them
loop_count = 0

# loops in dpy can randomly break, i check if is been over X minutes since last loop to restart it
last_loop_time = 0

server_count = 0


def get_emoji(name: str) -> str:
    if config.EMOJI and name in allowedemojis:
        themed_name = data.emoji_theme_prefixes[config.EMOJI] + name
        if themed_name in emojis:
            return emojis[themed_name]
    if name in emojis:
        return emojis[name]
    elif name in emoji.EMOJI_DATA:
        return name
    else:
        return "🔳"


def get_short_emoji(emoji: str) -> str:
    return re.sub(r":[A-Za-z0-9_]*:", ":i:", get_emoji(emoji), count=1)


def get_aura_emoji(emoji: str, auras: list[str]) -> str:
    emoji_pre = emoji.lower() + "cat"
    cattype_index = cattypes.index(emoji)
    suffix = auras[cattype_index]
    if suffix and suffix in ["r", "p", "c", "y", "a"]:
        return get_emoji(emoji_pre + f"_{suffix}")
    return get_emoji(emoji_pre)


def get_command_mention(name: str) -> str:
    return f"</{name}:{COMMAND_IDS[name]}>" if name in COMMAND_IDS else f"/{name}"


def log_stats(key: str, tags: dict[str, str] | None = None, value: float = 1) -> None:
    logger.debug("Cat Bot - %s", json.dumps({"name": str(key), "gauge": {"value": int(value)}, "tags": tags or {}}))


async def fetch_dm_channel(user: User) -> discord.abc.Messageable:
    if user.dm_channel_id:
        return bot.get_partial_messageable(user.dm_channel_id)
    else:
        person = await bot.fetch_user(user.user_id)
        if person.dm_channel is None:
            await person.create_dm()
            assert person.dm_channel is not None
        user.dm_channel_id = person.dm_channel.id
        await user.save()
        return person.dm_channel


def stock_info(ticker: str) -> StockEntry:
    for stock in data.stock_data:
        if stock["ticker"] == ticker:
            return stock
    raise ValueError(f"Unknown stock ticker: {ticker}")


def ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def market_spot_price(market) -> int:
    return max(1, ceil_div(market["virtual_coins"], market["share_reserve"] + market["virtual_shares"]))


def market_quote(market, quantity: int, buy: bool, spread: float) -> tuple[int, int, int]:
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    reserve_shares = market["share_reserve"]
    virtual_shares = market["virtual_shares"]
    virtual_coins = market["virtual_coins"]
    current_shares = reserve_shares + virtual_shares
    invariant = current_shares * virtual_coins

    if buy:
        if quantity > reserve_shares:
            raise ValueError("The market does not have that many shares available")
        next_shares = current_shares - quantity
        next_virtual_coins = ceil_div(invariant, next_shares)
        base_total = next_virtual_coins - virtual_coins
        total = ceil_div(int(base_total * 10_000), int((1 - spread) * 10_000))
    else:
        next_shares = current_shares + quantity
        next_virtual_coins = invariant // next_shares
        base_total = virtual_coins - next_virtual_coins
        total = int(base_total * (1 - spread))

    next_spot = max(1, ceil_div(next_virtual_coins, next_shares))
    return max(0, total), next_virtual_coins, next_spot


def max_buy_quantity(market, coins: int) -> int:
    low = 0
    high = market["share_reserve"]
    while low < high:
        middle = (low + high + 1) // 2
        quote, _, _ = market_quote(market, middle, True, QUEUED_SPREAD)
        if ceil_div(quote * 125, 100) <= coins:
            low = middle
        else:
            high = middle - 1
    return low


async def locked_market(ticker: str, conn):
    stock = stock_info(ticker)
    await conn.execute(
        """INSERT INTO market (ticker, share_reserve, coin_reserve, virtual_shares, virtual_coins, last_updated)
        VALUES ($1, $2, 0, $2, $3, $4) ON CONFLICT (ticker) DO NOTHING""",
        ticker,
        stock["amount"] // 5,
        stock["init_price"] * stock["amount"] * 2,
        int(time.time()),
    )
    market = await conn.fetchrow("SELECT * FROM market WHERE ticker = $1 FOR UPDATE", ticker)
    assert market is not None
    return market


async def market_snapshot(ticker: str):
    async with transaction() as conn:
        return await locked_market(ticker, conn)


async def get_stock_price(ticker: str) -> int:
    if market := await _get_pool().fetchrow("SELECT * FROM market WHERE ticker = $1", ticker):
        return market_spot_price(market)
    try:
        return (await PriceHistory.collect("ticker = $1 ORDER BY time DESC LIMIT 1", ticker))[0].price
    except IndexError:
        return stock_info(ticker)["init_price"]


async def compute_portfolio(profile) -> tuple[float, list[str]]:
    portfolio_value = 0.0
    share_strs = []
    for stock in data.stock_data:
        stock_price = await get_stock_price(stock["ticker"])
        amount_owned = profile[f"stock_{stock['ticker'].lower()}"]
        item_value = stock_price * amount_owned
        portfolio_value += item_value
        if amount_owned > 0:
            share_strs.append(f"{get_emoji(stock['emoji'])} {amount_owned:,}x (🪙 *{item_value:,}*)")
    return portfolio_value, share_strs


async def inject_market_liquidity(ticker: str, shares: int, target_price: int) -> None:
    if shares <= 0:
        return
    target_price = max(1, target_price)
    async with transaction() as conn:
        market = await locked_market(ticker, conn)
        new_share_reserve = market["share_reserve"] + shares
        new_virtual_coins = target_price * (new_share_reserve + market["virtual_shares"])
        now = int(time.time())
        await conn.execute(
            "UPDATE market SET share_reserve = $1, virtual_coins = $2, last_updated = $3 WHERE ticker = $4",
            new_share_reserve,
            new_virtual_coins,
            now,
            ticker,
        )
        await PriceHistory.create(connection=conn, ticker=ticker, price=target_price, time=now)
        temp_stock_prices[ticker] = target_price


async def execute_market_trade(conn, profile_id: int, ticker: str, quantity: int, buy: bool, spread: float, escrow: int = 0) -> tuple[int, int]:
    market = await locked_market(ticker, conn)
    profile = await conn.fetchrow("SELECT * FROM profile WHERE id = $1 FOR UPDATE", profile_id)
    if profile is None:
        raise ValueError("Profile no longer exists")

    total, next_virtual_coins, next_spot = market_quote(market, quantity, buy, spread)
    stock_column = f'"stock_{ticker.lower()}"'

    if buy:
        if escrow:
            if total > escrow:
                raise ValueError("Reserved coins do not cover the current quote")
            await conn.execute(
                f"UPDATE profile SET coins = coins + $1, {stock_column} = {stock_column} + $2 WHERE id = $3", escrow - total, quantity, profile_id
            )
        else:
            if total > profile["coins"]:
                raise ValueError("Not enough coins")
            await conn.execute(f"UPDATE profile SET coins = coins - $1, {stock_column} = {stock_column} + $2 WHERE id = $3", total, quantity, profile_id)
        await conn.execute(
            "UPDATE market SET share_reserve = share_reserve - $1, coin_reserve = coin_reserve + $2, virtual_coins = $3, last_updated = $4 WHERE ticker = $5",
            quantity,
            total,
            next_virtual_coins,
            int(time.time()),
            ticker,
        )
    else:
        if total > market["coin_reserve"]:
            raise ValueError("The market cannot currently fund that sale")
        if not escrow:
            if quantity > profile[f"stock_{ticker.lower()}"]:
                raise ValueError("Not enough shares")
            await conn.execute(f"UPDATE profile SET coins = coins + $1, {stock_column} = {stock_column} - $2 WHERE id = $3", total, quantity, profile_id)
        else:
            await conn.execute("UPDATE profile SET coins = coins + $1 WHERE id = $2", total, profile_id)
        await conn.execute(
            "UPDATE market SET share_reserve = share_reserve + $1, coin_reserve = coin_reserve - $2, virtual_coins = $3, last_updated = $4 WHERE ticker = $5",
            quantity,
            total,
            next_virtual_coins,
            int(time.time()),
            ticker,
        )

    now = int(time.time())
    await PortfolioHistory.create(
        connection=conn, user_id=profile_id, ticker=ticker, type="b" if buy else "s", quantity=quantity, price=ceil_div(total, quantity), time=now
    )
    await PriceHistory.create(connection=conn, ticker=ticker, price=next_spot, time=now)
    temp_stock_prices[ticker] = next_spot
    return total, next_spot


async def check_channel_setupped(guild: Server, channel: GuildMessageable) -> bool:
    if not guild.only_setupped_channels:
        return True
    db_channel = await Channel.get_or_none(channel_id=channel.id)
    return db_channel is not None


def count_achievements(profile) -> tuple[int, int, int]:
    """Returns (unlocked non-hidden count, unlocked hidden count, total hidden count)."""
    unlocked = 0
    minus_achs = 0
    minus_achs_count = 0
    for k in ach_names:
        if is_ach_hidden := ach_list[k]["category"] == "Hidden":
            minus_achs_count += 1
        if profile[k]:
            if is_ach_hidden:
                minus_achs += 1
            else:
                unlocked += 1
    return unlocked, minus_achs, minus_achs_count


# this is some common code which is run whether someone gets an achievement
async def achemb(
    message: discord.Message | discord.Interaction,
    ach_id: str,
    send_type: str,
    author_string: discord.abc.User | None = None,
) -> None:
    if not author_string:
        if isinstance(message, discord.Message):
            author_string = message.author
        elif isinstance(message, discord.Interaction):
            author_string = message.user
        else:
            return
    author = author_string.id

    if not message.guild:
        return

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=author)

    if profile[ach_id]:
        return

    profile[ach_id] = True
    await profile.save()
    log_stats("achievement", {"ach_id": ach_id})
    ach_data = ach_list[ach_id]
    desc = ach_data["description"]
    if ach_id == "dataminer":
        desc = "Your head hurts -- you seem to have forgotten what you just did to get this."

    username = author_string.name
    if author_string == bot.user:
        username = "Cat Bot (what)"

    if ach_id != "thanksforplaying":
        embed = (
            discord.Embed(title=ach_data["title"], description=desc, color=Colors.green)
            .set_author(
                name="Achievement get!",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/ach.png",
            )
            .set_footer(text=f"Unlocked by {username}")
        )
        embed2 = None
    else:
        embed = (
            discord.Embed(
                title="Catnip Addict",
                description="Uncover the mafia's truth\nThanks for playing! ✨",
                color=Colors.demonic,
            )
            .set_author(
                name="Demonic achievement unlocked! 🌟",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/demonic_ach.png",
            )
            .set_footer(text=f"Congrats to {username}!!")
        )

        embed2 = (
            discord.Embed(
                title="Catnip Addict",
                description="Uncover the mafia's truth\nThanks for playing! ✨",
                color=Colors.yellow,
            )
            .set_author(
                name="Demonic achievement unlocked! 🌟",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/demonic_ach.png",
            )
            .set_footer(text=f"Congrats to {username}!!")
        )

    result = None
    server = await Server.get_or_create(server_id=message.guild.id)
    assert isinstance(message.channel, GuildMessageable)
    do = not server.mute_achievements and await check_channel_setupped(server, message.channel)
    try:
        if send_type == "ephemeral":
            assert isinstance(message, discord.Interaction)
            await message.followup.send(embed=embed, ephemeral=True)
        if send_type == "reply" and do:
            assert isinstance(message, discord.Message)
            result = await message.reply(embed=embed)
        if send_type == "send" and do:
            result = await message.channel.send(embed=embed)
        if send_type == "followup":
            assert isinstance(message, discord.Interaction)
            await message.followup.send(embed=embed, ephemeral=not do)
        if send_type == "response":
            assert isinstance(message, discord.Interaction)
            await message.response.send_message(embed=embed, ephemeral=not do)
        await progress(message, profile, "achievement")
        await finale(message, profile)
    except (discord.NotFound, discord.Forbidden):
        pass

    if result:
        if embed2:
            await asyncio.sleep(2)
            await result.edit(embed=embed2)
            await asyncio.sleep(2)
            await result.edit(embed=embed)
            await asyncio.sleep(2)
            await result.edit(embed=embed2)
            await asyncio.sleep(2)
            await result.edit(embed=embed)

        if server.auto_delete_achievements:
            await result.delete(delay=10)
        elif ach_id == "curious":
            await result.delete(delay=30)


async def generate_quest(user: Profile, quest_type: str) -> None:
    while True:
        quest = random.choice(list(config.battle["quests"][quest_type].keys()))
        match quest:
            case "plush":
                # removed quests
                continue
            case "prism":
                total_count = await Prism.count("guild_id = $1", user.guild_id)
                user_count = await Prism.count("guild_id = $1 AND user_id = $2", user.guild_id, user.user_id)
                global_boost = 0.06 * math.log(2 * total_count + 1)
                prism_boost = global_boost + 0.05 * math.log(2 * user_count + 1)
                if prism_boost < 0.15:
                    continue
            case "achievement":
                unlocked, _, _ = count_achievements(user)
                if unlocked > 30:
                    continue
        break

    quest_data = config.battle["quests"][quest_type][quest]
    user[f"{quest_type}_reward"] = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
    user[f"{quest_type}_cooldown"] = 0
    if quest_type != "vote":
        user[f"{quest_type}_quest"] = quest
    await user.save()


async def refresh_quests(user: Profile) -> None:
    await user.refresh_from_db()
    start_date = datetime.datetime(2024, 12, 1, tzinfo=datetime.timezone.utc)
    current_date = discord.utils.utcnow() + datetime.timedelta(hours=4)
    full_months_passed = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
    if current_date.day < start_date.day:
        full_months_passed -= 1
    if user.season != full_months_passed:
        user.bp_history += f"{user.season},{user.battlepass},{user.progress};"
        user.battlepass = 0
        user.progress = 0

        user.catch_quest = ""
        user.catch_progress = 0
        user.catch_cooldown = 1
        user.catch_reward = 0

        user.misc_quest = ""
        user.misc_progress = 0
        user.misc_cooldown = 1
        user.misc_reward = 0

        user.weekly_quest = next(iter(config.battle["quests"]["weekly"].keys()))
        user.weekly_progress = 0
        user.weekly_cattypes = []

        user.season = full_months_passed
        await user.save()
    if 12 * 3600 < user.vote_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "vote")
    if 12 * 3600 < user.catch_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "catch")
    if 12 * 3600 < user.misc_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "misc")

    curr_weekly = config.battle["quests"]["weekly"][user.weekly_quest]
    month_start = datetime.datetime(current_date.year, current_date.month, 1, tzinfo=datetime.timezone.utc) - datetime.timedelta(hours=4)
    time_in_month = time.time() - int(month_start.timestamp())
    if curr_weekly["start_time"] < time_in_month < curr_weekly["end_time"]:
        return
    user.weekly_progress = 0
    for k, v in config.battle["quests"]["weekly"].items():
        if v["start_time"] < time_in_month < v["end_time"]:
            user.weekly_quest = k
            await user.save()
            return


async def build_catch_quests(user: Profile, cattype: str, time_seconds: float, got_prism_boost: bool) -> list[str]:
    quests = ["3cats", "catch"]
    if cattype == "Fine":
        quests.append("2fine")
    if cattype == "Good":
        quests.append("good")
    if time_seconds >= 0 and time_seconds < 10:
        quests.append("under10")
    if time_seconds >= 0:
        quests.append("even" if int(time_seconds) % 2 == 0 else "odd")
    if cattype and cattype not in ["Fine", "Nice", "Good"]:
        quests.append("rare+")
    if got_prism_boost:
        quests.append("prism")
    if user.catch_quest == "finenice":
        # 0 none
        # 1 fine
        # 2 nice
        # 3 both
        if cattype == "Fine" and user.catch_progress in [0, 2]:
            quests.append("finenice")
        elif cattype == "Nice" and user.catch_progress in [0, 1]:
            quests.append("finenice")
            quests.append("finenice")
    if cattypes.index(cattype) > 8:
        quests.append("brave+")
    if user.weekly_quest == "different":
        idx = cattypes.index(cattype)
        current = user.weekly_cattypes.copy()
        if idx not in current:
            current.append(idx)
            user.weekly_cattypes = current
            quests.append("different")
            await user.save()
    return quests


async def multi_progress(message: discord.Message | discord.Interaction, user: Profile, quests: list[str], is_belated: bool = False) -> None:
    await refresh_quests(user)
    await user.refresh_from_db()
    for quest in quests:
        if return_user := await progress(message, user, quest, is_belated, False):
            user = return_user


async def progress(message: discord.Message | discord.Interaction, user: Profile, quest: str, is_belated: bool = False, refetch: bool = True) -> Profile:
    if refetch:
        await refresh_quests(user)
        await user.refresh_from_db()

    # progress
    current_xp = None
    if user.catch_quest == quest:
        if user.catch_cooldown != 0:
            return user
        quest_data = config.battle["quests"]["catch"][quest]
        user.catch_progress += 1
        if user.catch_progress >= quest_data["progress"]:
            user.catch_cooldown = int(time.time())
            current_xp = user.progress + user.catch_reward
            user.catch_progress = 0
            user.reminder_catch = 1
    elif quest == "vote":
        if user.vote_cooldown != 0:
            return user
        quest_data = config.battle["quests"]["vote"][quest]
        global_user = await User.get_or_create(user_id=user.user_id)
        user.vote_cooldown = global_user.vote_time_topgg

        # Weekdays 0 Mon - 6 Sun
        # double vote xp rewards if Friday, Saturday or Sunday
        voted_at = datetime.datetime.fromtimestamp(global_user.vote_time_topgg, tz=datetime.timezone.utc)
        if voted_at.weekday() >= 4:
            user.vote_reward *= 2

        streak_data = get_streak_reward(global_user.vote_streak)
        if streak_data["reward"]:
            user[f"pack_{streak_data['reward']}"] += 1

        current_xp = user.progress + user.vote_reward
    elif user.misc_quest == quest:
        if user.misc_cooldown != 0:
            return user
        quest_data = config.battle["quests"]["misc"][quest]
        user.misc_progress += 1
        if user.misc_progress >= quest_data["progress"]:
            user.misc_cooldown = int(time.time())
            current_xp = user.progress + user.misc_reward
            user.misc_progress = 0
            user.reminder_misc = 1
    elif user.weekly_quest == quest:
        quest_data = config.battle["quests"]["weekly"][quest]
        if user.weekly_progress >= quest_data["progress"]:
            return user
        user.weekly_progress += 1
        if user.weekly_progress >= quest_data["progress"]:
            user.weekly_progress = quest_data["progress"]
            current_xp = user.progress + 2000
            user.scratchcards += 1
    else:
        return user

    await user.save()
    if current_xp is None:
        return user

    user.quests_completed += 1

    log_stats("quest", {"quest": quest})
    old_xp = user.progress
    level_complete_embeds = []
    if user.battlepass >= len(config.battle["seasons"][str(user.season)]):
        level_data = {"xp": 2000, "reward": "Mystery", "amount": 1}
        level_text = "Extra Rewards"
    else:
        level_data = config.battle["seasons"][str(user.season)][user.battlepass]
        level_text = f"Level {user.battlepass + 1}"

    new_level_text = None
    if current_xp >= level_data["xp"]:
        log_stats("bp_lvl_complete", {"level": user.battlepass})
        xp_progress = current_xp
        active_level_data = level_data
        while xp_progress >= active_level_data["xp"]:
            user.battlepass += 1
            xp_progress -= active_level_data["xp"]
            user.progress = xp_progress
            cat_emojis = None
            pack_chosen = None
            if active_level_data["reward"] in cattypes:
                user[f"cat_{active_level_data['reward']}"] += active_level_data["amount"]
            elif active_level_data["reward"] == "Rain":
                user.rain_minutes += active_level_data["amount"]
            elif active_level_data["reward"] == "Mystery":
                pack_options = [pack["name"] for pack in data.pack_data if not pack["special"]]
                pack_weights = [1 / pack["totalvalue"] for pack in data.pack_data if not pack["special"]]
                pack_chosen = random.choices(pack_options, weights=pack_weights, k=1)[0]
                user[f"pack_{pack_chosen.lower()}"] += 1
            else:
                user[f"pack_{active_level_data['reward'].lower()}"] += 1
            await user.save()

            if not cat_emojis:
                if active_level_data["reward"] == "Rain":
                    description = f"You got ☔ {active_level_data['amount']} rain minutes!"
                elif active_level_data["reward"] in cattypes:
                    description = (
                        f"You got {get_emoji(active_level_data['reward'].lower() + 'cat')} {active_level_data['amount']} {active_level_data['reward']}!"
                    )
                elif pack_chosen:
                    description = f"You got a {get_emoji('mysterypack')} -> {get_emoji(pack_chosen.lower() + 'pack')} {pack_chosen} pack! Do /packs to open it!"
                else:
                    description = (
                        f"You got a {get_emoji(active_level_data['reward'].lower() + 'pack')} {active_level_data['reward']} pack! Do /packs to open it!"
                    )
                title = f"Level {user.battlepass} Complete!"
            else:
                description = f"You got {cat_emojis}!"
                title = "Bonus Complete!"
            embed_level_up = discord.Embed(title=title, description=description, color=Colors.yellow)
            level_complete_embeds.append(embed_level_up)

            if user.battlepass >= len(config.battle["seasons"][str(user.season)]):
                active_level_data = {"xp": 2000, "reward": "Mystery", "amount": 1}
                new_level_text = "Extra Rewards"
            else:
                active_level_data = config.battle["seasons"][str(user.season)][user.battlepass]
                new_level_text = f"Level {user.battlepass + 1}"

        assert new_level_text is not None
        embed_progress = await progress_embed(
            user,
            active_level_data,
            xp_progress,
            0,
            quest_data,
            current_xp - old_xp,
            new_level_text,
        )

    else:
        user.progress = current_xp
        await user.save()
        embed_progress = await progress_embed(
            user,
            level_data,
            current_xp,
            old_xp,
            quest_data,
            current_xp - old_xp,
            level_text,
        )

    if is_belated:
        embed_progress.set_footer(text="For catching late")
    elif bot.user and user.user_id == bot.user.id:
        embed_progress.set_footer(text="im so good at this")

    assert message.guild is not None
    assert isinstance(message.channel, GuildMessageable)
    server = await Server.get_or_create(server_id=message.guild.id)
    if await check_channel_setupped(server, message.channel):
        if level_complete_embeds:
            await message.channel.send(f"<@{user.user_id}>", embeds=level_complete_embeds + [embed_progress])
        else:
            await message.channel.send(f"<@{user.user_id}>", embed=embed_progress)

    return user


async def progress_embed(user: Profile, level_data: dict, current_xp: int, old_xp: int, quest_data: dict, diff: int, level_text: str) -> discord.Embed:
    percentage_before = int(old_xp / level_data["xp"] * 10)
    percentage_after = int(current_xp / level_data["xp"] * 10)
    percenteage_left = 10 - percentage_after

    progress_line = get_emoji("staring_square") * percentage_before + "🟨" * (percentage_after - percentage_before) + "⬛" * percenteage_left

    title = quest_data["title"] if "top.gg" not in quest_data["title"] else "Vote on Top.gg"

    match level_data["reward"]:
        case "Rain":
            reward_text = get_emoji(str(level_data["amount"]) + "rain")
        case "Mystery":
            reward_text = get_emoji("mysterypack")
        case "random cats":
            reward_text = f"{level_data['amount']}x ❓"
        case _ if level_data["reward"] in cattypes:
            reward_text = f"{level_data['amount']}x {get_emoji(level_data['reward'].lower() + 'cat')}"
        case _:
            reward_text = get_emoji(level_data["reward"].lower() + "pack")

    global_user = await User.get_or_create(user_id=user.user_id)
    streak_data = get_streak_reward(global_user.vote_streak)
    if streak_data["reward"] and "top.gg" in quest_data["title"]:
        streak_reward = f"\n🔥 **Streak Bonus!** +1 {streak_data['emoji']} {streak_data['reward'].capitalize()} pack"
    elif quest_data in config.battle["quests"]["weekly"].values():
        streak_reward = "\n🍀 **Weekly Quest!** +1 /scratch card!"
    else:
        streak_reward = ""

    return discord.Embed(
        title=f"✅ {title}",
        description=f"{progress_line} {reward_text}\n{current_xp}/{level_data['xp']} XP (+{diff}){streak_reward}",
        color=Colors.green,
    ).set_author(name="/battlepass " + level_text)


def get_streak_reward(streak: int) -> dict:
    if streak == 0:
        return {"reward": None, "emoji": "⬛", "done_emoji": get_emoji("staring_square")}
    elif streak % 100 == 0:
        return {"reward": "diamond", "emoji": get_emoji("diamondpack"), "done_emoji": get_emoji("diamondpack_claimed")}
    elif streak % 25 == 0:
        return {"reward": "platinum", "emoji": get_emoji("platinumpack"), "done_emoji": get_emoji("platinumpack_claimed")}
    elif streak % 5 == 0 and streak != 5:
        return {"reward": "gold", "emoji": get_emoji("goldpack"), "done_emoji": get_emoji("goldpack_claimed")}
    else:
        return {"reward": None, "emoji": "⬛", "done_emoji": get_emoji("staring_square")}


# handle curious people clicking buttons
async def do_funny(message: discord.Interaction) -> None:
    assert message.guild is not None
    await message.response.send_message(random.choice(data.funny), ephemeral=True)
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    user.funny += 1
    await user.save()
    await achemb(message, "curious", "ephemeral")
    if user.funny >= 50:
        await achemb(message, "its_not_working", "followup")


# not :eyes:
async def debt_cutscene(message: discord.Interaction, user: Profile) -> None:
    if user.debt_seen:
        return

    user.debt_seen = True
    await user.save()

    for debt_msg in data.debt_msgs:
        await asyncio.sleep(4)
        await message.followup.send(debt_msg, ephemeral=True)


# :eyes:
async def finale(message: discord.Interaction | discord.Message, user: Profile) -> None:
    if user.finale_seen:
        return

    # check ach req
    unlocked, _, hidden_count = count_achievements(user)
    if unlocked < len(ach_names) - hidden_count:
        return

    if isinstance(message, discord.Message):
        author_string = message.author
    elif isinstance(message, discord.Interaction):
        author_string = message.user
    else:
        return

    user.finale_seen = True
    await user.save()

    assert isinstance(message.channel, GuildMessageable)
    await asyncio.sleep(5)
    await message.channel.send("...")
    await asyncio.sleep(3)
    await message.channel.send("You...")
    await asyncio.sleep(3)
    await message.channel.send("...actually did it.")
    await asyncio.sleep(3)
    await message.channel.send(
        embed=discord.Embed(
            title="True Ending achieved!",
            description="You are finally free.",
            color=Colors.rose,
        )
        .set_author(
            name="All achievements complete!",
            icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png",
        )
        .set_footer(text=f"Congrats to {author_string}")
    )


# function to autocomplete cat_type choices for /givecat, and /forcespawn, which also allows more than 25 options
async def cat_type_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [discord.app_commands.Choice(name=choice, value=choice) for choice in [*cattypes, "Random"] if current.lower() in choice.lower()][:25]


# function to autocomplete /cat, it only shows the cats you have
async def cat_command_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    assert interaction.guild is not None
    user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
    return [discord.app_commands.Choice(name=choice, value=choice) for choice in cattypes if current.lower() in choice.lower() and user[f"cat_{choice}"] > 0][
        :25
    ]


async def lb_type_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    assert interaction.guild is not None
    return [
        discord.app_commands.Choice(name=choice, value=choice)
        for choice in ["All"] + await cats_in_server(interaction.guild.id)
        if current.lower() in choice.lower()
    ][:25]


async def cats_in_server(guild_id: int) -> list[str]:
    cols = ", ".join(f'bool_or("cat_{t}" > 0) AS "cat_{t}"' for t in cattypes)
    row = await _get_pool().fetchrow(f"SELECT {cols} FROM profile WHERE guild_id = $1;", guild_id)
    return [t for t in cattypes if row and row[f"cat_{t}"]]


# function to autocomplete cat_type choices for /gift, which shows only cats user has and how many of them they have
async def gift_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    assert interaction.guild is not None
    user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
    actual_user = await User.get_or_create(user_id=interaction.user.id)
    choices = []
    for choice in cattypes:
        if current.lower() in choice.lower() and user[f"cat_{choice}"] > 0:
            choices.append(discord.app_commands.Choice(name=f"{choice} (x{user[f'cat_{choice}']})", value=choice))
    if current.lower() in "rain" and actual_user.rain_minutes > 0:
        choices.append(discord.app_commands.Choice(name=f"Rain ({actual_user.rain_minutes} {plural('minute', actual_user.rain_minutes)})", value="rain"))
    if current.lower() in "scratchcards" and user.scratchcards > 0:
        choices.append(discord.app_commands.Choice(name=f"Scratchcards (x{user.scratchcards})", value="scratchcards"))
    for choice in data.pack_data:
        if user[f"pack_{choice['name'].lower()}"] > 0:
            pack_name = choice["name"]
            pack_amount = user[f"pack_{pack_name.lower()}"]
            choices.append(discord.app_commands.Choice(name=f"{pack_name} pack (x{pack_amount})", value=pack_name.lower()))
    return choices[:25]


# function to autocomplete achievement choice for /giveachievement, which also allows more than 25 options
async def ach_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [
        discord.app_commands.Choice(name=val["title"], value=key)
        for (key, val) in ach_list.items()
        if (alnum(current) in alnum(key) or alnum(current) in alnum(val["title"]))
    ][:25]


# function to convert a snowflake to "X days ago"
def snow_to_rel(snowflake: int) -> str:
    delta = discord.utils.utcnow() - discord.utils.snowflake_time(snowflake)
    seconds = max(0, int(delta.total_seconds()))

    for unit, unit_seconds in (("d", 86_400), ("h", 3_600), ("m", 60)):
        if seconds >= unit_seconds:
            return f"{seconds // unit_seconds}{unit} ago"

    return f"{seconds}s ago"


# function to autocomplete operation choice for /undo, which also allows more than 25 options
async def undo_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    assert interaction.guild is not None
    time_snowflake = discord.utils.time_snowflake(discord.utils.utcnow() - datetime.timedelta(days=7))
    return [
        discord.app_commands.Choice(
            name=(f"reset - {entry.username}" if entry.username else "nuke") + f" ({snow_to_rel(entry.id)})",
            value=str(entry.id),
        )
        async for entry in Restore.filter("guild_id = $1 AND id > $2 ORDER BY id DESC", interaction.guild.id, time_snowflake)
    ][:25]


# converts string to lowercase alphanumeric characters only
def alnum(string: str) -> str:
    return "".join(item for item in string.lower() if item.isalnum())


async def spawn_cat(ch_id: int, localcat: str | None = None, force_spawn: bool = False) -> str:
    if not (channel := await Channel.get_or_none(channel_id=ch_id)):
        return "channel not setup"
    if channel.cat or channel.yet_to_spawn > time.time() + 10:
        return "cat already spawned"

    if not localcat:
        localcat = random.choices(cattypes, weights=list(data.type_dict.values()))[0]
    icon = get_emoji(localcat.lower() + "cat")
    file = discord.File(
        f"assets/images/spawn/{localcat.lower()}_cat.png",
    )
    channeley = bot.get_partial_messageable(ch_id)

    appearstring = '{emoji} {type} cat has appeared! Type "cat" to catch it!' if not channel.appear else channel.appear

    if ch_id in temp_spawns_storage:
        return "cat spawn already in progress"

    temp_spawns_storage.add(ch_id)

    try:
        message_is_sus = await channeley.send(
            appearstring.replace("{emoji}", str(icon)).replace("{type}", localcat),
            file=file,
            allowed_mentions=discord.AllowedMentions.all(),
        )
    except discord.Forbidden as e:
        await channel.delete()
        temp_spawns_storage.discard(ch_id)
        if e.text == "Access to file uploads has been limited for this guild":
            return "your server is limited by discord, cat bot cant operate here"
        return "sending message forbidden (no permissions)"
    except discord.NotFound:
        await channel.delete()
        temp_spawns_storage.discard(ch_id)
        return "not found (cant access channel)"
    except Exception as e:
        temp_spawns_storage.discard(ch_id)
        return str(e)

    config.belated_catchers.pop(ch_id, None)
    channel.cat = message_is_sus.id
    channel.yet_to_spawn = 0
    channel.forcespawned = bool(force_spawn)
    channel.cattype = localcat
    await channel.save()
    temp_spawns_storage.discard(ch_id)
    log_stats("spawn", {"forced": str(force_spawn)})
    return f"ok, now i will send cats in <#{ch_id}>"


async def wait_and_do_stock(stock):
    task_key = (stock.ticker, int(stock.end_time))
    try:
        await asyncio.sleep(max(0, stock.end_time - time.time()))
        allowed_tickers = {s["ticker"] for s in data.stock_data}
        if stock.ticker not in allowed_tickers:
            return

        async with transaction() as conn:
            claimed_reward = await conn.fetchrow(
                """UPDATE reward SET paid = true
                WHERE ticker = $1 AND end_time = $2 AND active = true AND paid = false
                RETURNING *""",
                stock.ticker,
                stock.end_time,
            )
            if claimed_reward is None:
                return

            if random.random() * 100 < claimed_reward["chance"]:
                stock_column = f'"stock_{stock.ticker.lower()}"'
                await conn.execute(
                    f"""WITH stock_holders_raw AS (
                    SELECT id AS user_id, {stock_column} AS quantity
                    FROM profile
                    WHERE {stock_column} > 0
                    UNION ALL
                    SELECT user_id, quantity
                    FROM "order"
                    WHERE ticker = $4 AND type_buy = false
                ),
                stock_holders AS (
                    SELECT user_id, SUM(quantity) AS quantity
                    FROM stock_holders_raw
                    GROUP BY user_id
                ),
                "updated" AS (
                    UPDATE profile p
                    SET coins = coins + sh.quantity * $1
                    FROM stock_holders sh
                    WHERE p.id = sh.user_id
                    RETURNING p.id AS profile_id, sh.quantity * $1 AS coin_change
                )
                INSERT INTO portfoliohistory (user_id, time, type, ticker, quantity)
                SELECT profile_id, $2, $3, $4, coin_change
                FROM "updated";""",
                    claimed_reward["amount"],
                    claimed_reward["end_time"],
                    "r",
                    claimed_reward["ticker"],
                )
        await refresh_stock_rewards(stock.ticker)
    finally:
        stock_reward_tasks.discard(task_key)


async def refresh_stock_rewards(ticker):
    stock = await Reward.get_or_create(ticker=ticker)
    hour = 3600
    current_price = await get_stock_price(ticker)
    stock.active = False
    stock.start_time = time.time() + random.randint(10 * hour, 24 * hour)
    stock.end_time = stock.start_time + hour * 24
    stock.chance = min(100, max(0, round(random.gauss(50, 10))))
    stock.amount = round(random.gauss(0, current_price / 4))
    stock.chance_hidden = random.randint(0, 100) < 50
    stock.paid = False
    await stock.save()


async def postpone_reminder(interaction: discord.Interaction) -> None:
    if not interaction.custom_id:
        return
    reminder_type = interaction.custom_id
    if reminder_type == "vote":
        user = await User.get_or_create(user_id=interaction.user.id)
        user.reminder_vote = int(time.time()) + 30 * 60
        await user.save()
    else:
        guild_id = reminder_type.split("_")[1]
        user = await Profile.get_or_create(guild_id=int(guild_id), user_id=interaction.user.id)
        if reminder_type.startswith("catch"):
            user.reminder_catch = int(time.time()) + 30 * 60
        else:
            user.reminder_misc = int(time.time()) + 30 * 60
        await user.save()
    log_stats("postpone_reminder", {"reminder_type": reminder_type})
    await interaction.response.send_message(f"ok, i will remind you <t:{int(time.time()) + 30 * 60}:R>", ephemeral=True)


async def send_quest_reminders(quest_type: str, start_time: int) -> None:
    reminder_count = 0
    while True:
        user = await Profile.collect(
            f"(reminders_enabled = true AND reminder_{quest_type} != 0) AND "
            f"(({quest_type}_cooldown != 0 AND {quest_type}_cooldown + 43200 < {start_time}) OR (reminder_{quest_type} > 1 AND reminder_{quest_type} < {start_time})) LIMIT 1",
        )
        if not user or not user[0]:
            break
        user = user[0]
        await asyncio.sleep(0.2)

        await refresh_quests(user)
        await user.refresh_from_db()

        quest_data = config.battle["quests"][quest_type][user[f"{quest_type}_quest"]]

        embed = discord.Embed(
            title=f"{get_emoji(quest_data['emoji'])} {quest_data['title']}",
            description=f"Reward: **{user[f'{quest_type}_reward']}** XP",
            color=Colors.green,
        )

        view = View(timeout=VIEW_TIMEOUT)
        button = Button(label="Postpone", custom_id=f"{quest_type}_{user.guild_id}")
        button.callback = postpone_reminder
        view.add_item(button)

        guild = await Server.get_or_create(server_id=user.guild_id)
        try:
            if not guild.name:
                guild.name = (await bot.fetch_guild(user.guild_id)).name
                await guild.save()
        except Exception:
            guild.name = "Unknown Server"
            await guild.save()

        try:
            user_user = await User.get_or_create(user_id=user.user_id)
            user_dm = await fetch_dm_channel(user_user)
            await user_dm.send(f"A new quest is available in {guild.name}!", embed=embed, view=view)
        except Exception:
            pass
        user[f"reminder_{quest_type}"] = 0
        reminder_count += 1
        await user.save()

    log_stats("reminders", {"type": quest_type}, reminder_count)


# a loop for various maintenance which is ran every minute
async def background_loop() -> None:
    global pointlaugh_ratelimit, reactions_ratelimit, loop_count, last_vote_cursor, server_count, emojis

    pointlaugh_ratelimit = {}
    reactions_ratelimit = {}

    for store in (catchcooldown, fakecooldown, customcatcooldown, casino_lock, slots_lock, fish_lock, temp_catches_storage, temp_spawns_storage):
        store.expire(time.time())

    # clean up anything older than 5 minutes
    for ch_id in list(config.belated_catchers.keys()):
        if config.belated_catchers[ch_id].get("timestamp", 0) < time.time() - 300:
            del config.belated_catchers[ch_id]

    try:
        async with await anyio.open_file("config/emojis_cache.json", "r", encoding="utf-8") as f:
            emojis = json.loads(await f.read())
    except Exception:
        pass

    if config.CLUSTERING:
        try:
            async with aiohttp.ClientSession() as session, session.get("http://localhost:7878/metrics") as response:
                metrics_data = await response.text()
                server_count = 0
                for line in metrics_data.split("\n"):
                    if line.startswith("gateway_cache_guilds{shard="):
                        if "NaN" in line:
                            continue
                        server_count += int(line.split(" ")[1])
        except Exception:
            pass
    else:
        server_count = len(bot.guilds)

    await bot.change_presence(activity=discord.CustomActivity(name=f"Catting in {server_count:,} servers"))
    if config.CLUSTERING and not config.CLUSTERING_ZERO:
        loop_count += 1
        return

    if config.TOP_GG_MODERN_TOKEN:
        try:
            async with aiohttp.ClientSession() as session:
                if not config.MIN_SERVER_SEND or server_count > config.MIN_SERVER_SEND:
                    # send server count to top.gg
                    r = await session.post(
                        "https://top.gg/api/v1/projects/@me/metrics",
                        headers={"Authorization": f"Bearer {config.TOP_GG_MODERN_TOKEN}"},
                        json={"server_count": server_count},
                    )
                    r.close()

                # post commands to top.gg
                r = await session.post(
                    "https://top.gg/api/v1/projects/@me/commands",
                    headers={"Authorization": f"Bearer {config.TOP_GG_MODERN_TOKEN}"},
                    json=[command.to_dict(bot.tree) for command in bot.tree._get_all_commands(guild=None) if command.to_dict(bot.tree)["type"] == 1],
                )
                r.close()

                # fallback fetch votes
                if last_vote_cursor:
                    suffix = "cursor=" + last_vote_cursor
                else:
                    timestamp = discord.utils.utcnow() - datetime.timedelta(minutes=1)
                    suffix = "startDate=" + timestamp.replace(tzinfo=None).isoformat()
                r = await session.get(
                    f"https://top.gg/api/v1/projects/@me/votes?{suffix}",
                    headers={"Authorization": f"Bearer {config.TOP_GG_MODERN_TOKEN}"},
                )
                response_data = await r.json()
                r.close()

                the_votes = response_data.get("data", [])
                for vote_data in the_votes:
                    if not vote_data.get("created_at", 0) or not vote_data.get("platform_id", 0):
                        continue
                    created_at = datetime.datetime.fromisoformat(vote_data["created_at"]).timestamp()
                    vote_user = await User.get_or_create(user_id=int(vote_data["platform_id"]))
                    await do_vote(vote_user, created_at)

                last_vote_cursor = response_data.get("cursor", "")
                async with await anyio.open_file("cursor.txt", "w") as f:
                    await f.write(last_vote_cursor)
                logger.info(f"Fetched {len(the_votes)} votes, cursor {last_vote_cursor}")

        except Exception:
            logger.warning("Posting to top.gg failed.")

    assert bot.user is not None

    # refresh materialized view
    await _get_pool().execute("REFRESH MATERIALIZED VIEW CONCURRENTLY profile_sums_mv;")

    # payout stock market rewards/set up future rewards
    for stock_info in data.stock_data:
        stock = await Reward.get_or_create(ticker=stock_info["ticker"])
        if stock and stock.active and stock.end_time < time.time() + 60 * 5:
            task_key = (stock.ticker, int(stock.end_time))
            if task_key not in stock_reward_tasks:
                stock_reward_tasks.add(task_key)
                bot.loop.create_task(wait_and_do_stock(stock))
            continue
        if stock.start_time == 0 or stock.end_time == 0:
            await refresh_stock_rewards(stock.ticker)
            continue
        if stock and not stock.active and stock.start_time < time.time():
            stock.active = True
            await stock.save()

            # reward events issue discounted shares so long-term hoarding cannot exhaust liquidity
            median_price = await PriceHistory.median(
                "price",
                "ticker = $1 AND time >= $2",
                stock.ticker,
                int(time.time()) - 3600 * 24,
            )
            reference_price = int(median_price) if median_price is not None else await get_stock_price(stock.ticker)
            await inject_market_liquidity(stock.ticker, 100, int(reference_price * 0.75))

    # settle waiting trades
    await settle_queued_orders()

    # auto-sell stocks of people inactive for over a week at the current market quote
    async for profile in Profile.filter("last_ran_stocks < $1 AND last_ran_stocks != 0", time.time() - 3600 * 24 * 7):
        for stock in data.stock_data:
            ticker = stock["ticker"]
            quantity = profile[f"stock_{ticker.lower()}"]
            if quantity <= 0:
                continue
            try:
                async with transaction() as conn:
                    market = await locked_market(ticker, conn)
                    if sell_quantity := max_queued_quantity(market, quantity, False, 0):
                        await execute_market_trade(conn, profile.id, ticker, sell_quantity, False, QUEUED_SPREAD)
            except ValueError:
                logger.warning("Could not auto-sell %s shares of %s for inactive profile %s", quantity, ticker, profile.id)

    # ensure every configured stock has a market-maker state from startup onward
    async with transaction() as conn:
        for stock in data.stock_data:
            await locked_market(stock["ticker"], conn)

    # revive dead catch loops
    counter = 0
    async for channel in Channel.limit(["channel_id"], "yet_to_spawn < $1 AND cat = 0", time.time(), refetch=False):
        counter += 1
        await spawn_cat(channel.channel_id)
        await asyncio.sleep(0.1)
    log_stats("revived", {}, counter)

    # THIS IS CONSENTUAL AND TURNED OFF BY DEFAULT DONT BAN ME
    #
    # i wont go into the details of this because its a complicated mess which took me like solid 30 minutes of planning
    #
    # vote reminders
    reminder_count = 0
    start_time = int(time.time())
    while True:
        user = await User.collect(
            f"vote_time_topgg != 0 AND vote_time_topgg + 43200 < {start_time} AND reminder_vote != 0 AND reminder_vote < {start_time} "
            + 'AND EXISTS(SELECT 1 FROM profile WHERE profile.user_id = "user".user_id AND reminders_enabled = true) LIMIT 1',
        )
        if not user or not user[0]:
            break
        user = user[0]
        await asyncio.sleep(0.2)

        view = View(timeout=VIEW_TIMEOUT)
        button = Button(
            emoji=get_emoji("topgg"),
            label=random.choice(data.vote_button_texts),
            url="https://top.gg/bot/966695034340663367/vote",
        )
        view.add_item(button)

        button = Button(label="Postpone", custom_id="vote")
        button.callback = postpone_reminder
        view.add_item(button)

        try:
            user_dm = await fetch_dm_channel(user)
            await user_dm.send(
                "You can vote now!" if user.vote_streak < 10 else f"Vote now to keep your {user.vote_streak} streak going!",
                view=view,
            )
        except Exception:
            pass

        # no repeat reminers for now
        user.reminder_vote = 0
        reminder_count += 1
        await user.save()

    log_stats("reminders", {"type": "vote"}, reminder_count)

    # catch and misc quest reminders
    await send_quest_reminders("catch", start_time)
    await send_quest_reminders("misc", start_time)

    # manual reminders
    async for reminder in Reminder.filter("time < $1", time.time()):
        try:
            user = await User.get_or_create(user_id=reminder.user_id)
            user_dm = await fetch_dm_channel(user)
            await user_dm.send(reminder.text)
            await asyncio.sleep(0.5)
        except Exception:
            pass
        await reminder.delete()

    # db backups
    if config.BACKUP_ID:
        backupchannel = bot.get_partial_messageable(config.BACKUP_ID)

        if loop_count % 60 == 0:
            backup_file = "./backup.dump"
            try:
                os.remove(backup_file)
            except Exception:
                pass

            try:
                process = await asyncio.create_subprocess_shell(f"PGPASSWORD={config.DB_PASS} pg_dump -U cat_bot -Fc -Z 9 -f {backup_file} cat_bot")
                await process.wait()

                if exportbackup:
                    await bot.loop.run_in_executor(None, exportbackup.export)
                    await backupchannel.send(f"In {server_count:,} servers, loop {loop_count}.\nBackup exported.")
                else:
                    await backupchannel.send(f"In {server_count:,} servers, loop {loop_count}.", file=discord.File(backup_file))
            except Exception as e:
                logger.warning(f"Error during backup: {e}")
        else:
            await backupchannel.send(f"In {server_count:,} servers, loop {loop_count}.")

    loop_count += 1


async def on_connect() -> None:
    global emojis
    if len(emojis) != 0:
        return

    try:
        async with await anyio.open_file("config/emojis_cache.json", "r", encoding="utf-8") as f:
            emojis = json.loads(await f.read())
        return
    except Exception:
        pass

    emojis = {emoji.name: str(emoji) for emoji in await bot.fetch_application_emojis()}
    try:
        async with await anyio.open_file("config/emojis_cache.json", "w", encoding="utf-8") as f:
            await f.write(json.dumps(emojis))
    except Exception:
        pass


# some code which is run when bot is started
async def on_ready() -> None:
    global OWNER_ID, on_ready_debounce, gen_credits
    if on_ready_debounce:
        return
    on_ready_debounce = True
    logger.info("cat is now online")
    appinfo = bot.application
    if appinfo is not None:
        if appinfo.team and appinfo.team.owner_id:
            OWNER_ID = appinfo.team.owner_id
        else:
            OWNER_ID = appinfo.owner.id

    # fetch github contributors
    url = "https://api.github.com/repos/milenakos/cat-bot/contributors"
    contributors = []

    async with aiohttp.ClientSession() as session, session.get(url, headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"}) as response:
        if response.status == 200:
            data = await response.json()
            for contributor in data:
                login = contributor["login"].replace("_", r"\_")
                if login not in ["milenakos", "ImgBotApp", "Neoexm"]:
                    contributors.append(login)
        else:
            logger.warning(f"Error: {response.status} - {await response.text()}")

    gen_credits = "\n".join(
        [
            "Made by **Lia Milenakos**",
            "With contributions from **" + ", ".join(contributors) + "**",
            "Original Cat Image: **pathologicals**",
            "APIs: **catfact.ninja, weilbyte.dev, wordnik.com, thecatapi.com**",
            "Open Source Projects: **[discord.py](https://github.com/Rapptz/discord.py), [asyncpg](https://github.com/MagicStack/asyncpg), [gateway-proxy](https://github.com/Gelbpunkt/gateway-proxy)**",
            "Art, suggestions, and a lot more: **TheTrashCell**",
            "Banner art: **2braincelledcreature**",
            "Testers: **aflyde, azalichia, amethystultrakill, thetrashcell, ruby404._., sior_.**",
            "Enjoying the bot: **You <3**",
        ]
    )


def to_roman_numeral(value: int) -> str:
    roman_map = {1: "I", 4: "IV", 5: "V", 9: "IX", 10: "X", 40: "XL", 50: "L", 90: "XC", 100: "C", 400: "CD", 500: "D", 900: "CM", 1000: "M"}
    result = ""
    remainder = value
    for i in sorted(roman_map.keys(), reverse=True):
        times = remainder // i
        remainder %= i
        result += roman_map[i] * times
    return result


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True


async def play_minigame(interaction: discord.Interaction) -> None:
    assert isinstance(interaction.channel, GuildMessageable)
    if interaction.channel.id not in config.belated_catchers:
        await interaction.response.send_message("No active minigame in this channel.", ephemeral=True)
        return

    belated = config.belated_catchers[interaction.channel.id]
    if interaction.user.id not in [c[0] for c in belated["late_catchers"]]:
        await interaction.response.send_message("You are not eligible to play this minigame.", ephemeral=True)
        return

    belated["late_catchers"] = [c for c in belated["late_catchers"] if c[0] != interaction.user.id]
    cattype = belated["cattype"]
    start = int(time.time())
    end = start + 45

    log_stats("minigame_start", {"cattype": cattype})

    modal = Modal(title="Bonus Cat Minigame")
    match cattype:
        case "Fine":
            random_text = random.choice(data.sentences)
            text_letters = list({i for i in random_text.upper() if i.isalpha()})
            picked = random.sample(text_letters, 3)
            answer = sum(random_text.lower().count(letter.lower()) for letter in picked)
            modal.add_item(TextDisplay(f"## Count how many letters in this sentence are any of these: {', '.join(picked)}\n\n{random_text}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=2))
        case "Nice":
            random_numbers = [random.randint(-100, 100) for _ in range(5)]
            answer = " ".join(map(str, sorted(random_numbers)))
            modal.add_item(TextDisplay(f"## Sort the numbers in ascending order\n\n{', '.join(map(str, random_numbers))}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=100))
        case "Good":
            random_text = random.choice(data.sentences)
            answer = 0
            for vowel in "AEIOU":
                answer += random_text.lower().count(vowel.lower())
            modal.add_item(TextDisplay(f"## Count the amount of vowels (AEIOU, no Y) in the sentence below\n\n{random_text}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=2))
        case "Rare":
            base = random.randint(200, 900)
            num_range = [base + (i * 100) for i in range(-2, 2)]
            random.shuffle(num_range)
            items = {
                num_range[0]: str(num_range[0]),
                num_range[1]: str(num_range[1] // 2) + " * 2",
                num_range[2]: str(num_range[2] * 3) + "/3",
                num_range[3]: str(num_range[3] - 111) + " + 111",
            }
            items = dict(random.sample(list(items.items()), len(items)))
            options = [discord.RadioGroupOption(label=value, value=str(key)) for key, value in items.items()]
            modal.add_item(discord.ui.Label(text="Choose the biggest number", component=discord.ui.RadioGroup(options=options, id=67)))
            answer = max(items.keys())
        case "Wild":
            colors = ["red", "yellow", "blue", "green"]
            options = [discord.RadioGroupOption(label=color) for color in colors]
            modal.add_item(discord.ui.Label(text="Three options are safe, and one is a fail", component=discord.ui.RadioGroup(options=options, id=67)))
            answer = random.choice(colors)
        case "Gremlin":
            expr = str(random.randint(1, 15)) + " + " + str(random.randint(1, 15)) + " * " + str(random.randint(2, 10))
            modal.add_item(
                discord.ui.Label(text=f"What's the result of {expr}?", component=discord.ui.TextInput(placeholder="Answer", id=67, min_length=1, max_length=3))
            )
            answer = eval(expr)
        case "Epic":
            random_text = random.choice(data.sentences)
            answer = random_text.upper()
            modal.add_item(TextDisplay(f"## Retype this text in UPPERCASE\n\n{random_text}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=100))
        case "Sus":
            random_text = random.choice(data.sentences)
            random_letter = ""
            while not random_letter.isalpha():
                random_letter = random.choice(random_text).upper()
            answer = random_text.replace(random_letter, "").replace(random_letter.lower(), "")
            modal.add_item(
                TextDisplay(
                    f"## Retype this text without the letter '{random_letter}/{random_letter.lower()}'\n\n{random_text}",
                )
            )
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=100))
        case "Brave":
            asc_digits = sorted(random.sample(range(1, 10), 6))
            answer = "".join(map(str, asc_digits))
            option_texts = [answer]
            while len(option_texts) < 25:
                candidate_digits = [random.randint(1, 9) for _ in range(6)]
                candidate = "".join(map(str, candidate_digits))
                if candidate in option_texts:
                    continue
                if all(candidate_digits[i] < candidate_digits[i + 1] for i in range(5)):
                    continue
                option_texts.append(candidate)
            random.shuffle(option_texts)
            options = [discord.SelectOption(label=text, value=text) for text in option_texts]
            modal.add_item(discord.ui.Label(text="Find the number whose digits only ascend", component=discord.ui.Select(options=options, id=67)))
        case "Rickroll":
            answer = random.choice(rickroll_list) + ". " + random.choice(rickroll_list)
            modal.add_item(TextDisplay(f"## Retype this text\n\n{answer}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=200))
        case "Reverse":
            line = random.choice(data.sentences)
            split_line = line.split()
            split_line.reverse()
            answer = " ".join(split_line)
            modal.add_item(TextDisplay(f"## Reverse the word order of this text\n\n{line}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=100))
        case "Superior":
            number = random.randint(10_000, 99_999)
            answer = sum(int(i) for i in str(number))
            modal.add_item(TextDisplay(f"## What is the sum of the digits of this number\n\n{number}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=2))
        case "Trash":
            inputs = ['TRO', 'JET', 'STR', 'ADJ', 'CRA', 'ISE', 'TIC', 'INT', 'MIN', 'SCA', 'INC', 'VER', 'RED', 'TRA', 'MEN', 'KIL', 'ZAP', 'LUB', 'STA', 'REF', 'LIT', 'IST', 'MIS', 'ANG', 'REV', 'LAT', 'DIS', 'BLA', 'SYR', 'DIG', 'CAT', 'INE', 'LIN', 'RAF', 'PER', 'SAV', 'ROA', 'SCH', 'LOV', 'SOF', 'CON', 'HUN', 'LAG', 'COM', 'ICA', 'INS', 'RIS', 'GAG', 'INO', 'LOW', 'RAT', 'WOR', 'BRE', 'LOG', 'ORI', 'HAN', 'ATT', 'TIN', 'DRA', 'UNP', 'PUR', 'PAL', 'MIL', 'FOR', 'GRA', 'ATE', 'PAT', 'BER', 'BET', 'WEA', 'IOD', 'RES', 'TRI', 'BRO', 'RAN', 'PRO', 'WHI', 'FLA', 'ELL', 'ENT', 'INK', 'ABS', 'CLA', 'CAL', 'OVE', 'IMI', 'ILL', 'COK', 'SHI', 'SAT', 'CRO', 'DEP', 'STI', 'MAT', 'SIN', 'IDE', 'SPL']  # fmt: skip
            answer = random.choice(inputs)
            modal.add_item(
                discord.ui.Label(
                    text=f"Type a 6+ letter word containing {answer}", component=discord.ui.TextInput(placeholder="Answer", id=67, min_length=6, max_length=50)
                )
            )
        case "Legendary":
            raw_words = random.choice(data.sentences).split()
            words = [re.sub(r"[^a-zA-Z]", "", w) for w in raw_words]
            words = [w for w in words if w][:4]
            shuffled = words.copy()
            random.shuffle(shuffled)
            answer = " ".join(sorted(words, key=str.lower))
            modal.add_item(TextDisplay(f"## Put these words in alphabetical order\n\n{' '.join(shuffled)}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=100))
        case "Mythic":
            answer = random.randint(15, 89)
            modal.add_item(TextDisplay(f"## What's the value of this roman numeral?\n\n{to_roman_numeral(answer)}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=3))
        case "8bit":
            powers = {"³": 2**3, "⁴": 2**4, "⁵": 2**5, "⁶": 2**6}
            power = random.choice(list(powers.keys()))
            answer = powers[power]
            modal.add_item(discord.ui.Label(text=f"What's 2{power}?", component=discord.ui.TextInput(placeholder="Answer", id=67, min_length=1, max_length=3)))
        case "Corrupt":
            bin_string = "".join(random.choice(["0", "1"]) for _ in range(50))
            to_count = random.choice(["0", "1"])
            answer = bin_string.count(to_count)
            modal.add_item(TextDisplay(f"## How many {to_count}s are in this binary number?\n\n{bin_string}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=2))
        case "Professor":
            answer = random.choice(cattypes)
            show = list(answer)
            random.shuffle(show)
            show = "".join(show).upper()
            modal.add_item(TextDisplay(f"## Decode this cat type\n\n{show}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=20))
        case "Divine":
            letter_mappings = dict(data.letter_mapping)
            letter_mappings.update({v: k for k, v in letter_mappings.items()})  # reverse mappings
            sentence = random.choice(data.sentences).upper()
            answer = random.randint(2, 5)
            valid_indices = [i for i, c in enumerate(sentence) if c in letter_mappings]
            random.shuffle(valid_indices)
            swap_indices = valid_indices[:answer]
            changed = list(sentence)
            for idx in swap_indices:
                changed[idx] = letter_mappings[sentence[idx]]
            changed = "".join(changed)
            modal.add_item(TextDisplay(f"## How many letters are different between the sentences?\n\n{sentence}\n\n{changed}"))
            modal.add_item(discord.ui.TextInput(label="Answer", id=67, min_length=1, max_length=2))
        case "Real":
            try:
                async with (
                    aiohttp.ClientSession() as session,
                    session.get(
                        "https://the-trivia-api.com/v2/questions?limit=1&difficulties=easy",
                        headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"},
                    ) as response,
                ):
                    stuff = await response.json()
                    question = stuff[0]
                    question_text = question["question"]["text"]
                    correct_answer = question["correctAnswer"]
                    answers = question["incorrectAnswers"] + [correct_answer]
            except Exception:
                question_text = "Are cats awesome?"
                answers = ["Yes", "No", "Meh", "IDK"]
                correct_answer = "Yes"
            random.shuffle(answers)
            options = []
            answer = correct_answer
            for answer_value in answers:
                options.append(discord.RadioGroupOption(label=answer_value[:100], value=answer_value[:100]))
            modal.add_item(TextDisplay(f"## {question_text}"))
            modal.add_item(discord.ui.Label(text="Answer", component=discord.ui.RadioGroup(options=options, id=67)))
        case "Ultimate":
            number = random.randint(10, 150)
            answer = "Yes" if is_prime(number) else "No"
            options = [discord.RadioGroupOption(label="Yes", value="Yes"), discord.RadioGroupOption(label="No", value="No")]
            modal.add_item(discord.ui.Label(text=f"Is {number} a prime number?", component=discord.ui.RadioGroup(options=options, id=67)))
        case "eGirl":
            answer = "meow"
            modal.add_item(
                discord.ui.Label(
                    text="Meow agressively.",
                    component=discord.ui.TextInput(placeholder="meow mrrrp miau nyaa~ :3", min_length=69, max_length=2000, style=discord.TextStyle.long, id=67),
                )
            )
    modal.add_item(TextDisplay(f"-# Time's up <t:{end}:R>\n-# If you don't see the question, update your Discord app."))

    async def check_minigame(interaction: discord.Interaction) -> None:
        nonlocal answer
        if time.time() > end:
            await interaction.response.send_message("❌ You weren't fast enough!", ephemeral=True)
            log_stats("minigame_timeout")
            return
        answer_item = modal.find_item(67)
        if isinstance(answer_item, (discord.ui.TextInput, discord.ui.RadioGroup)):
            answer_raw = answer_item.value
        elif isinstance(answer_item, discord.ui.Select):
            answer_raw = answer_item.values[0]
        else:
            return

        assert answer_raw is not None

        def clean_answer_input(raw: str) -> str:
            return " ".join(re.sub(r"[^0-9A-Za-z \-]+", "", raw.replace(",", " ")).split())

        answer_clean = clean_answer_input(answer_raw)  # user answer
        answer = clean_answer_input(str(answer))  # correct answer

        match cattype:
            case "Trash" if answer in answer_clean.upper():
                try:
                    async with (
                        aiohttp.ClientSession() as session,
                        session.get(
                            f"https://api.wordnik.com/v4/word.json/{answer_clean.lower()}/definitions?api_key={config.WORDNIK_API_KEY}&useCanonical=true&includeTags=false&includeRelated=false&limit=1",
                            headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"},
                        ) as response,
                    ):
                        response_text = await response.text()
                        correct = "from" in response_text
                except Exception:
                    # assume word is valid
                    correct = True
            case "Trash":
                correct = False
            case "Divine":
                correct = answer_clean.upper() in answer
            case "eGirl":
                # need atleast 10 signals
                signals = 0
                answer_clean = answer_raw.lower()
                for word in ["meow", "purr", "nya", "miau", "mrrp", "www", "ppp", "uuu", "333", ":3", "~"]:
                    signals += answer_raw.count(word)
                correct = signals >= 10
                answer = "10+ meow signals"
                answer_clean = f"{signals} meow signals"
            case "Epic":
                correct = answer_clean == str(answer)
            case "Wild":
                correct = answer_clean != str(answer)
                answer = "not " + answer
            case _:
                correct = answer_clean.lower() == str(answer).lower()

        if correct:
            assert interaction.guild is not None
            profile = await Profile.get_or_create(user_id=interaction.user.id, guild_id=interaction.guild.id)
            profile.bonus_catches += 1
            profile[f"cat_{cattype}"] += 3
            await profile.save()
            icon = get_aura_emoji(cattype, profile.cat_auras)
            await interaction.response.send_message(f"✅ {interaction.user.mention} got +3 {icon} {cattype} bonus cats.")
            await progress(interaction, profile, "bonus")
            log_stats("minigame_success", {"cattype": cattype})
            if cattype == "Rare":
                await achemb(interaction, "math_jumpscare", "followup")
        else:
            await interaction.response.send_message(f"❌ Better luck next time!\nCorrect answer: `{answer}`\nYour answer: `{answer_clean}`", ephemeral=True)
            log_stats("minigame_fail", {"cattype": cattype})

    modal.on_submit = check_minigame
    await interaction.response.send_modal(modal)


async def belated_window_task(
    msg: discord.PartialMessage,
    window: float,
    chance: float,
    catch_confirm: discord.Message | None,
    is_rain: bool = False,
) -> None:
    belated_pre = config.belated_catchers.get(msg.channel.id, {})
    if full_event := belated_pre.get("full_event"):
        try:
            await asyncio.wait_for(full_event.wait(), timeout=window)
        except asyncio.TimeoutError:
            pass
    else:
        await asyncio.sleep(window)
    if not is_rain:
        try:
            await msg.delete()
        except Exception:
            pass

    if not (belated := config.belated_catchers.get(msg.channel.id, {})):
        return
    if catchers := belated["late_catchers"].copy():
        catchers.pop(0)

    log_stats("late_catchers", {"count": str(len(catchers))})

    icon = get_emoji(belated["cattype"].lower() + "cat")
    has_bonus = random.random() < chance

    async def reply_or_send(target: discord.Message | None, text: str, **kwargs) -> discord.Message:
        try:
            assert target is not None
            return await target.reply(text, **kwargs)
        except Exception:
            return await msg.channel.send(text, **kwargs)

    # rain bonus: process rewards and combine with late-catchers message
    if has_bonus and belated["is_rain"]:
        log_stats("bonus_cat", {"rain": "true", "cattype": belated["cattype"]})
        for uid in belated["late_catchers"]:
            assert msg.guild is not None
            u = await Profile.get_or_create(user_id=uid[0], guild_id=msg.guild.id)
            u[f"cat_{belated['cattype']}"] += 1
            await u.save()
            if msg.channel.id in config.cat_cought_rain:
                if belated["cattype"] not in config.cat_cought_rain[msg.channel.id]:
                    config.cat_cought_rain[msg.channel.id][belated["cattype"]] = []
                config.cat_cought_rain[msg.channel.id][belated["cattype"]].append(f"<@{uid[0]}>")
        parts = []
        if catchers:
            parts.append(
                f"{get_emoji('pointlaugh')} Late {icon} {belated['cattype']} catchers:\n"
                + "\n".join([c[1] for c in catchers])
                + f"\n-# up to 3 late catchers within {window}s get +1 cat without boosts"
            )
        parts.append(f"🎁 Bonus {icon} {belated['cattype']} cat! Everyone who caught it gets +1 extra cat!")
        await reply_or_send(catch_confirm, "\n".join(parts))
        return

    if catchers:
        catch_confirm = await reply_or_send(
            catch_confirm,
            f"{get_emoji('pointlaugh')} Late {icon} {belated['cattype']} catchers:\n"
            + "\n".join([c[1] for c in catchers])
            + f"\n-# up to 3 late catchers within {window}s get +1 cat without boosts",
        )

    # non-rain bonus: minigame button
    if has_bonus:
        log_stats("bonus_cat", {"rain": "false", "cattype": belated["cattype"]})
        view = View(timeout=10)
        button = Button(style=discord.ButtonStyle.green, label="Go!")
        button.callback = play_minigame
        view.add_item(button)
        h = await reply_or_send(
            catch_confirm,
            f"🎁 **BONUS {icon} {belated['cattype'].upper()} CAT!**\nAnyone who cought this cat can play a minigame and potentially **get +3 more!**",
            view=view,
        )
        await h.delete(delay=10)


# this is all the code which is ran on every message sent
# a lot of it is for easter eggs or achievements
async def on_message(message: discord.Message) -> None:
    global last_loop_time
    text = message.content
    if not bot.user or message.author.id == bot.user.id:
        return

    if time.time() > last_loop_time + 60:
        last_loop_time = time.time()
        bot.loop.create_task(background_loop())

    if message.guild is None:
        if message.author.bot:
            return
        try:
            user = await User.get_or_create(user_id=message.author.id)
            if text.startswith("disable"):
                # disable reminders
                try:
                    where = text.split(" ")[1]
                    user = await Profile.get_or_create(guild_id=int(where), user_id=message.author.id)
                    user.reminders_enabled = False
                    await user.save()
                    await message.reply("reminders disabled")
                except Exception:
                    await message.reply("failed. check if your guild id is correct")
                    return
            elif text == "lol_i_have_dmed_the_cat_bot_and_got_an_ach":
                await message.reply('which part of "send in server" was unclear?')
            elif user.dms < 15:
                await message.reply('good job! please send "lol_i_have_dmed_the_cat_bot_and_got_an_ach" in server to get your ach!')
                user.dms += 1
                await user.save()
            else:
                await message.reply(random.choice(fanhalo_list))
        except Exception:
            pass
        return

    if not isinstance(message.channel, GuildMessageable):
        return

    server = None

    # here are some automation hooks for giving out purchases and similiar
    if config.RAIN_CHANNEL_ID and message.channel.id == config.RAIN_CHANNEL_ID and text.lower().startswith("cat!rain"):
        arguements = text.split(" ")
        user = await User.get_or_create(user_id=int(arguements[1]))
        rain_duration = arguements[2]
        if not user.rain_minutes:
            user.rain_minutes = 0

        user.rain_minutes += int(rain_duration)
        user.rain_minutes_bought += int(rain_duration)
        user.premium = True
        await user.save()

        await _get_pool().execute("REFRESH MATERIALIZED VIEW CONCURRENTLY user_sums_mv;")

        # try to dm the user the thanks msg
        try:
            person = await fetch_dm_channel(user)
            await person.send(
                f"**You have recieved {rain_duration} minutes of Cat Rain!** ☔\n\nThanks for your support!\nYou can start a rain with `/rain`. By buying you also get access to `/editprofile` and `/customcat` commands as well as a role in [our Discord server](<https://discord.gg/staring>)!\n\nEnjoy your goods!"
            )
        except Exception:
            pass

        return

    if message.author.bot or message.webhook_id is not None:
        return

    react_count = 0

    # :staring_cat: reaction on some system messages
    if reactions_ratelimit.get(message.guild.id, 0) < 30 and message.type in [
        discord.MessageType.channel_follow_add,
        discord.MessageType.recipient_remove,
        discord.MessageType.guild_discovery_disqualified,
        discord.MessageType.guild_discovery_grace_period_initial_warning,
        discord.MessageType.guild_discovery_grace_period_final_warning,
        discord.MessageType.role_subscription_purchase,
        discord.MessageType.stage_end,
        discord.MessageType.guild_incident_report_false_alarm,
        discord.MessageType.purchase_notification,
    ]:
        if not server:
            server = await Server.get_or_create(server_id=message.guild.id)
        if server.do_reactions and await check_channel_setupped(server, message.channel):
            await message.add_reaction(get_emoji("staring_cat"))
        react_count += 1
        reactions_ratelimit[message.guild.id] = reactions_ratelimit.get(message.guild.id, 0) + 1
        log_stats("reaction", {"reaction": "staring_cat"})
    elif message.type not in [discord.MessageType.default, discord.MessageType.reply]:
        return

    # :staring_cat: reaction on "bullshit"
    if " " not in text and len(text) > 7 and text.isalnum():
        s = text.lower()
        total_vow = 0
        total_illegal = 0
        for i in "aeuio":
            total_vow += s.count(i)
        for j in data.illegal:
            if j in s:
                total_illegal += 1
        vow_perc = total_vow / len(text)
        if (vow_perc >= 0.82) or total_illegal >= 2:
            try:
                if reactions_ratelimit.get(message.guild.id, 0) < 30:
                    if not server:
                        server = await Server.get_or_create(server_id=message.guild.id)
                    if server.do_reactions and await check_channel_setupped(server, message.channel):
                        await message.add_reaction(get_emoji("staring_cat"))
                    react_count += 1
                    reactions_ratelimit[message.guild.id] = reactions_ratelimit.get(message.guild.id, 0) + 1
                    log_stats("reaction", {"reaction": "staring_cat"})
            except Exception:
                pass

    for match_text, achievement_name in data.achs.items():
        if match_text == text.lower():
            await achemb(message, achievement_name, "reply")

    if text == "cat!n4lltvuCOKe2iuDCmc6JsU7Jmg4vmFBj8G8l5xvoDHmCoIJMcxkeXZObR6HbIV6":
        await achemb(message, "dataminer", "reply")

    if unidecode.unidecode(text).lower().strip() in data.cat_translations:
        await achemb(message, "multilingual", "reply")

    if str(bot.user.id) in message.content:
        await achemb(message, "who_ping", "reply")

    for reaction_prompt, reaction_name in data.reactions.items():
        if reaction_prompt in text.lower() and reactions_ratelimit.get(message.guild.id, 0) < 30:
            try:
                if not server:
                    server = await Server.get_or_create(server_id=message.guild.id)
                if server.do_reactions and await check_channel_setupped(server, message.channel):
                    await message.add_reaction(get_emoji(reaction_name))
                react_count += 1
                reactions_ratelimit[message.guild.id] = reactions_ratelimit.get(message.guild.id, 0) + 1
                log_stats("reaction", {"reaction": reaction_name})
            except Exception:
                pass

    for response_prompt, response_reply in data.responses.items():
        if response_prompt in text.lower():
            if not server:
                server = await Server.get_or_create(server_id=message.guild.id)
            if server.do_responses and await check_channel_setupped(server, message.channel):
                try:
                    await message.reply(response_reply)
                except Exception:
                    pass
                log_stats("response", {"type": response_reply})

    try:
        if message.author in message.mentions and message.type != discord.MessageType.poll_result and reactions_ratelimit.get(message.guild.id, 0) < 30:
            if not server:
                server = await Server.get_or_create(server_id=message.guild.id)
            if server.do_reactions and await check_channel_setupped(server, message.channel):
                await message.add_reaction(get_emoji("staring_cat"))
            react_count += 1
            reactions_ratelimit[message.guild.id] = reactions_ratelimit.get(message.guild.id, 0) + 1
            log_stats("reaction", {"reaction": "staring_cat"})
    except Exception:
        pass

    if react_count >= 3:
        await achemb(message, "silly", "reply")

    if (":place_of_worship:" in text or "🛐" in text) and (":cat:" in text or ":staring_cat:" in text or "🐱" in text):
        await achemb(message, "worship", "reply")

    if text.lower() in ["testing testing 1 2 3", "cat!ach"]:
        if not server:
            server = await Server.get_or_create(server_id=message.guild.id)
        if server.do_responses and await check_channel_setupped(server, message.channel):
            try:
                await message.reply("test success")
            except Exception:
                # test failure
                pass
            log_stats("response", {"type": "test success"})
        await achemb(message, "test_ach", "reply")

    if text.lower() == "please do not the cat":
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.author.id)
        user.cat_Fine -= 1
        await user.save()
        if not server:
            server = await Server.get_or_create(server_id=message.guild.id)
        if server.do_responses and await check_channel_setupped(server, message.channel):
            try:
                personname = message.author.name.replace("_", "\\_")
                await message.reply(f"ok then\n{personname} lost 1 fine cat!!!1!\nYou now have {user.cat_Fine:,} {plural('cat', user.cat_Fine)} of dat type!")
            except Exception:
                pass
            log_stats("response", {"type": "please do not the cat"})
        await achemb(message, "pleasedonotthecat", "reply")

    if text.lower() == "please do the cat":
        if not server:
            server = await Server.get_or_create(server_id=message.guild.id)
        if server.do_responses and await check_channel_setupped(server, message.channel):
            thing = discord.File("assets/images/socialcredit.jpg", filename="socialcredit.jpg")
            try:
                await message.reply(file=thing)
            except Exception:
                pass
            log_stats("response", {"type": "please do the cat"})
        await achemb(message, "pleasedothecat", "reply")

    if text.lower() == "car":
        if not server:
            server = await Server.get_or_create(server_id=message.guild.id)
        if server.do_responses and await check_channel_setupped(server, message.channel):
            file = discord.File("assets/images/car.png", filename="car.png")
            embed = discord.Embed(title="car!", color=Colors.brown).set_image(url="attachment://car.png")
            try:
                await message.reply(file=file, embed=embed)
            except Exception:
                pass
            log_stats("response", {"type": "car"})
        await achemb(message, "car", "reply")

    if text.lower() == "cart":
        if not server:
            server = await Server.get_or_create(server_id=message.guild.id)
        if server.do_responses and await check_channel_setupped(server, message.channel):
            file = discord.File("assets/images/cart.png", filename="cart.png")
            embed = discord.Embed(title="cart!", color=Colors.brown).set_image(url="attachment://cart.png")
            try:
                await message.reply(file=file, embed=embed)
            except Exception:
                pass
            log_stats("response", {"type": "cart"})

    try:
        if (
            ("sus" in text.lower() or "amog" in text.lower() or "among" in text.lower() or "impost" in text.lower() or "report" in text.lower())
            and (channel := await Channel.get_or_none(channel_id=message.channel.id))
            and channel.cattype == "Sus"
        ):
            await achemb(message, "sussy", "reply")
    except Exception:
        pass

    # this is run whether someone says "cat" (very complex)
    if text.lower() == "cat":
        user, channel, server = await asyncio.gather(
            Profile.get_or_create(guild_id=message.guild.id, user_id=message.author.id),
            Channel.get_or_none(channel_id=message.channel.id),
            Server.get_or_create(server_id=message.guild.id),
        )
        if not server.name_style_set:
            try:
                # set the bot display name style
                await bot.http.request(
                    discord.http.Route("PATCH", f"/guilds/{message.guild.id}/members/@me"),
                    json={"display_name_font_id": 3, "display_name_effect_id": 5, "display_name_colors": [16738816]},
                )
                server.name_style_set = True
                await server.save()
            except Exception:
                pass
        if not channel or not channel.cattype:
            return
        if (
            not channel
            or not channel.cat
            or channel.cat in temp_catches_storage
            or user.timeout > time.time()
            or (server.anti_double_catch and user.last_catch_channel != message.channel.id and user.last_catch + 300 > time.time())
        ):
            # laugh at this user
            # (except if rain is active, we dont have perms or channel isnt setupped, or we laughed way too much already)
            if channel and channel.cat_rains == 0 and pointlaugh_ratelimit.get(message.channel.id, 0) < 10:
                try:
                    if server.do_reactions and await check_channel_setupped(server, message.channel):
                        await message.add_reaction(get_emoji("pointlaugh"))
                    pointlaugh_ratelimit[message.channel.id] = pointlaugh_ratelimit.get(message.channel.id, 0) + 1
                except Exception:
                    pass

            # belated catching
            if message.channel.id in config.belated_catchers:
                current_time = message.created_at.timestamp()
                belated = config.belated_catchers[message.channel.id]
                is_rain = belated.get("is_rain", False)
                catch_window = 3 if server.legacy_catching else (1 if is_rain else 5)
                if (
                    channel
                    and "users" in belated
                    and "time" in belated
                    and belated.get("timestamp", 0) + 5 > current_time
                    and message.author.id not in belated["users"]
                ):
                    belated["users"].append(message.author.id)
                    if (
                        not server.legacy_catching
                        and channel.cattype
                        and user.timeout <= time.time()
                        and len(belated["late_catchers"]) < 4
                        and belated.get("timestamp", 0) + catch_window > current_time
                        and not (server.anti_double_catch and user.last_catch_channel != message.channel.id and user.last_catch + 300 > time.time())
                    ):
                        user[f"cat_{channel.cattype}"] += 1
                        user.total_catches += 1
                        user.last_catch = time.time()
                        user.last_catch_channel = message.channel.id
                        icon = get_emoji(channel.cattype.lower() + "cat")
                        new_count = user[f"cat_{channel.cattype}"]
                        delay = abs(current_time - belated["timestamp"])
                        delay_str = f"+{round(delay, 3) if delay < 1 else round(delay, 2)}s"
                        belated["late_catchers"].append(
                            (message.author.id, f"{message.author.name.replace('_', '\\_')} ({delay_str}, {new_count:,} total)"),
                        )
                        if len(belated["late_catchers"]) >= 4 and "full_event" in belated:
                            belated["full_event"].set()
                        if channel.channel_id in config.cat_cought_rain:
                            if channel.cattype not in config.cat_cought_rain[channel.channel_id]:
                                config.cat_cought_rain[channel.channel_id][channel.cattype] = []
                            config.cat_cought_rain[channel.channel_id][channel.cattype].append(f"<@{user.user_id}>")
                        await user.save()
                    if user.catnip_active >= time.time() or user.hibernation:
                        await bounty(message, user, channel.cattype)
                    total_count, user_count = await asyncio.gather(
                        Prism.count("guild_id = $1", message.guild.id),
                        Prism.count("guild_id = $1 AND user_id = $2", message.guild.id, message.author.id),
                    )
                    prism_boost = 0.06 * math.log(2 * total_count + 1) + 0.05 * math.log(2 * user_count + 1)
                    time_proxy = belated.get("time", 10) + current_time - belated.get("timestamp", 0)
                    quests = await build_catch_quests(user, channel.cattype, time_proxy, prism_boost > random.random())
                    await multi_progress(message, user, quests, True)
                    vote_time_user = await User.get_or_create(user_id=message.author.id)

                    if vote_time_user.tutorial_state == 0:
                        text = f"👋 Welcome to Cat Bot! Check out the {get_command_mention('tutorial')} to get started (includes a free gift!)"
                        try:
                            await message.reply(text, allowed_mentions=discord.AllowedMentions(users=True))
                        except Exception:
                            await message.channel.send(f"{message.author.mention} {text}", allowed_mentions=discord.AllowedMentions(users=True))
                        vote_time_user.tutorial_state = 1
                        await vote_time_user.save()
                    elif vote_time_user.tutorial_state == 2:
                        text = f"✅ Run {get_command_mention('tutorial')} to continue"
                        try:
                            await message.reply(text, allowed_mentions=discord.AllowedMentions(users=True))
                        except Exception:
                            await message.channel.send(f"{message.author.mention} {text}", allowed_mentions=discord.AllowedMentions(users=True))
                        vote_time_user.tutorial_state = 3
                        await vote_time_user.save()
        else:
            pls_remove_me_later_k_thanks = channel.cat
            temp_catches_storage.add(channel.cat)
            decided_time = random.uniform(channel.spawn_times_min, channel.spawn_times_max)

            cat_rain_end = False
            if channel.cat_rains > 0:
                channel.cat_rains -= 1
                if channel.cat_rains == 0:
                    cat_rain_end = True
                else:
                    decided_time = random.uniform(1, 2)
                    channel.rain_should_end = int(time.time() + decided_time)

            if channel.yet_to_spawn < time.time():
                # if there isnt already a scheduled spawn
                channel.yet_to_spawn = time.time() + decided_time + 10
            else:
                channel.yet_to_spawn = 0
                decided_time = 0
            force_rain_summary = {}

            try:
                current_time = message.created_at.timestamp()
                channel.lastcatches = current_time
                cat_temp = channel.cat
                channel.cat = 0
                le_emoji = None
                try:
                    if channel.cattype != "":
                        catchtime = discord.utils.snowflake_time(cat_temp)
                        le_emoji = str(channel.cattype)
                    else:
                        var = await message.channel.fetch_message(cat_temp)
                        catchtime = var.created_at
                        catchcontents = var.content

                        partial_type = None
                        for v in allowedemojis:
                            if v in catchcontents:
                                partial_type = v
                                break

                        if not partial_type:
                            if "thetrashcellcat" in catchcontents:
                                partial_type = "trashcat"
                                le_emoji = "Trash"
                            elif "babycat" in catchcontents:
                                partial_type = "gremlincat"
                                le_emoji = "Gremlin"
                        else:
                            for i in cattypes:
                                if i.lower() in partial_type:
                                    le_emoji = i
                                    break
                        assert le_emoji is not None
                except Exception:
                    try:
                        await message.channel.send(f"oopsie poopsie i cant access the original message but {message.author.mention} *did* catch a cat rn")
                    except Exception:
                        pass
                    return

                send_target = message.channel
                precatch_reads = asyncio.gather(
                    _get_pool().fetchval("SELECT sum_blessing_minutes FROM user_sums_mv;"),
                    Prism.count("guild_id = $1", message.guild.id),
                    Prism.count("guild_id = $1 AND user_id = $2", message.guild.id, message.author.id),
                    User.get_or_create(user_id=message.author.id),
                )
                try:
                    # some math to make time look cool
                    then = catchtime.timestamp()
                    time_caught = round(abs(current_time - then), 3)  # cry about it
                    if time_caught >= 1:
                        time_caught = round(time_caught, 2)

                    days, time_left = divmod(time_caught, 86400)
                    hours, time_left = divmod(time_left, 3600)
                    minutes, seconds = divmod(time_left, 60)

                    caught_time = ""
                    if days:
                        caught_time += str(int(days)) + " days "
                    if hours:
                        caught_time += str(int(hours)) + " hours "
                    if minutes:
                        caught_time += str(int(minutes)) + " minutes "
                    if seconds:
                        pre_time = round(seconds, 3)
                        if pre_time % 1 == 0:
                            # replace .0 with .00 basically
                            pre_time = str(int(pre_time)) + ".00"
                        caught_time += str(pre_time) + " seconds "
                    do_time = True
                    if not caught_time:
                        caught_time = "0.000 seconds (woah) "
                    if time_caught <= 0:
                        do_time = False
                except Exception:
                    # if some of the above explodes just give up
                    do_time = False
                    caught_time = "undefined amounts of time "
                    time_caught = 0

                if channel.cat_rains > 0 or cat_rain_end:
                    do_time = False

                suffix_string = ""
                silly_amount = 1

                # perky!
                double_chance = 0
                triple_chance = 0
                single_chance = 100
                none_chance = 0
                double_boost_chance = 0
                rain_chance = 0
                purr_all_triple = False
                packs = []
                double_boost = False
                double_first = 0
                timer_add_chance = 0
                packs_gained = []
                bonus_chance = 0.02 * math.log2(CAT_VALUES[channel.cattype] - 0.7)
                bonus_chance_increase = 0

                if user.perks:
                    if user.catnip_active < time.time():
                        if user.catnip_active != 1:
                            user.catnip_active = 1
                            suffix_string += f"\n{get_emoji('catnip_disabled')} Your catnip expired! Run /catnip to get more."
                        perks = []
                    else:
                        perks = user.perks
                    perks_info = catnip_list["perks"]
                    user.pack_attempts -= 1

                    if len(perks) > 0:
                        log_stats("catnip", {"perks": str(len(perks))})

                    for perk in perks:
                        h = perk.split("_")
                        rarity = int(h[0])
                        type = int(h[1])
                        id = perks_info[type - 1]["id"]

                        match id:
                            case "double":
                                double_chance += perks_info[0]["values"][rarity]
                                single_chance -= perks_info[0]["values"][rarity]
                            case "triple_none":
                                triple_chance += perks_info[1]["values"][rarity]
                                none_chance += perks_info[1]["values"][rarity] / 2
                                single_chance -= perks_info[1]["values"][rarity] * (1.5)
                            case _ if "pack" in id and user.pack_attempts > 0:
                                for num, pack in enumerate(data.pack_data):
                                    if pack["name"].lower() in id:
                                        packs.append((num, perks_info[type - 1]["values"][rarity]))
                                        break
                            case "double_boost":
                                double_boost_chance += perks_info[8]["values"][rarity]
                            case "triple_ach":
                                purr_all_triple = True
                            case "timer_add":
                                timer_add_chance += perks_info[10]["values"][rarity]
                            case "rain_boost":
                                rain_chance += perks_info[12]["values"][rarity]
                            case "double_first":
                                double_first += perks_info[13]["values"][rarity]
                            case "bonus_catcher":
                                bonus_chance_increase += perks_info[14]["values"][rarity]

                    for i in packs:
                        chance = random.random() * 100
                        if chance <= i[1]:
                            packs_gained.append(data.pack_data[i[0]]["name"])
                            user[f"pack_{data.pack_data[i[0]]['name'].lower()}"] += 1
                            suffix_string += f"\n{get_emoji(data.pack_data[i[0]]['name'].lower() + 'pack')} You got a {data.pack_data[i[0]]['name']} pack! You now have {user[f'pack_{data.pack_data[i[0]]['name'].lower()}']:,} packs of this type!"

                    chance = random.random() * 100
                    if chance <= double_boost_chance:
                        double_boost = True

                    chance = random.random() * 100
                    if chance <= timer_add_chance:
                        user.catnip_active += 300
                        suffix_string += f"\n⏰ You got +5 minutes on your catnip timer! It will now expire <t:{user.catnip_active}:R>"

                    if double_first > user.catnip_total_cats:
                        user.catnip_total_cats += 1
                        double_chance = 100 - triple_chance
                        single_chance = 0
                        none_chance = 0

                    if time_caught > 0 and time_caught == int(time_caught):
                        user.perfection_count += 1
                        if purr_all_triple:
                            triple_chance = 100
                            double_chance = 0
                            single_chance = 0
                            none_chance = 0

                    if "undefined" not in caught_time and time_caught > 0:
                        raw_digits = "".join(char for char in caught_time[:-1] if char.isdigit())
                        if len(set(raw_digits)) == 1 and purr_all_triple:
                            triple_chance = 100
                            double_chance = 0
                            single_chance = 0
                            none_chance = 0

                    if single_chance < 0:
                        single_chance = 0
                        double_chance = 100 - triple_chance - none_chance
                    if double_chance < 0:
                        double_chance = 0
                        if 100 - triple_chance < 25:
                            none_chance = 25
                            triple_chance = 75
                    none_chance = max(none_chance, 0)
                    if bonus_chance_increase > 0:
                        bonus_chance_increase = min(2, bonus_chance_increase * 0.01 + 1)
                        bonus_chance *= bonus_chance_increase

                    if random.random() * 100 < rain_chance and channel.cat_rains == 0 and server.do_rain:
                        force_rain_summary = config.cat_cought_rain.get(channel.channel_id, {}).copy()
                        channel.cat_rains = 10
                        decided_time = random.uniform(1, 2)
                        channel.rain_should_end = int(time.time() + decided_time)
                        channel.yet_to_spawn = 0
                        config.cat_cought_rain[channel.channel_id] = {}
                        config.rain_starter[channel.channel_id] = message.author.id
                        bot.loop.create_task(rain_recovery_loop(channel))
                        suffix_string += "\n☔ Catnip started a short rain! 10 cats will spawn."

                    chance = random.random() * 100
                    if chance <= triple_chance:
                        silly_amount *= 3
                        suffix_string += f"\n{get_emoji('catnip')}{get_emoji('catnip')} catnip worked! your cat was TRIPLED by catnip!1!!1!"
                        user.catnip_activations += 2
                    elif chance <= triple_chance + double_chance:
                        silly_amount *= 2
                        suffix_string += f"\n{get_emoji('catnip')} catnip worked! your cat was doubled by catnip!!1!"
                        user.catnip_activations += 1
                    elif chance <= triple_chance + double_chance + single_chance:
                        silly_amount *= 1
                    elif chance <= triple_chance + double_chance + single_chance + none_chance:
                        silly_amount *= 0
                        suffix_string += "\n🚫 catnip failed! your cat was uncought. tragic."

                blessing_minutes, total_count, user_count, vote_time_user = await precatch_reads

                # blessings
                bless_chance = blessing_minutes * 0.0001 * 0.01
                if bless_chance > random.random():
                    # woo we got blessed thats pretty cool
                    if silly_amount == 0:
                        silly_amount += 1
                    else:
                        silly_amount *= 2

                    blesser_l = await User.collect("blessings_enabled = true AND rain_minutes_bought > 0 ORDER BY -ln(random()) / rain_minutes_bought LIMIT 1")
                    blesser = blesser_l[0]
                    blesser.cats_blessed += 1
                    if not blesser.username:
                        blesser.username = (await bot.fetch_user(blesser.user_id)).name
                    bot.loop.create_task(blesser.save())

                    log_stats("bless")

                    if blesser.blessings_anonymous:
                        blesser_text = "💫 Anonymous Supporter"
                    else:
                        blesser_text = f"{blesser.emoji or '💫'} {blesser.username}"

                    if silly_amount > 1:
                        suffix_string += f"\n{blesser_text} blessed your catch and it got doubled!"
                    else:
                        suffix_string += f"\n{blesser_text} blessed your catch and it got saved!"

                # aura farming
                if random.random() < CAT_VALUES[channel.cattype] / 100000:
                    type_idx = cattypes.index(channel.cattype)
                    new_auras = user.cat_auras.copy()
                    new_auras[type_idx] = "r"
                    user.cat_auras = new_auras
                    suffix_string += f"\n{get_emoji(f'{channel.cattype.lower()}cat_r')} Rainbow aura for {channel.cattype} cat unlocked!!!"

                # calculate prism boost
                global_boost = 0.06 * math.log(2 * total_count + 1)
                user_boost = global_boost + 0.05 * math.log(2 * user_count + 1)
                did_boost = False
                le_old_emoji = le_emoji
                if user_boost > random.random():
                    # determine whodunnit
                    if random.uniform(0, user_boost) > global_boost:
                        # boost from our own prism
                        user_prisms = await Prism.collect("guild_id = $1 AND user_id = $2 ORDER BY random() LIMIT 1", message.guild.id, message.author.id)
                        prism_which_boosted = user_prisms[0]
                    else:
                        # boost from any prism
                        total_prisms = await Prism.collect("guild_id = $1 ORDER BY random() LIMIT 1", message.guild.id)
                        prism_which_boosted = total_prisms[0]

                    if prism_which_boosted.user_id == message.author.id:
                        boost_applied_prism = "Your prism " + prism_which_boosted.name
                    else:
                        boost_applied_prism = f"<@{prism_which_boosted.user_id}>'s prism " + prism_which_boosted.name

                    did_boost = True
                    rainboost = None
                    user.boosted_catches += 1
                    prism_which_boosted.catches_boosted += 1
                    bot.loop.create_task(prism_which_boosted.save())
                    log_stats("boost", {"from": le_emoji})
                    idx_shift = 0
                    try:
                        overflow = False
                        le_old_emoji = le_emoji
                        if double_boost:
                            idx_shift = cattypes.index(le_emoji) + 2
                        else:
                            idx_shift = cattypes.index(le_emoji) + 1
                        le_emoji = cattypes[idx_shift]
                    except IndexError:
                        overflow = True
                        le_emoji = cattypes[-1]
                        if not channel.forcespawned:
                            if idx_shift == len(cattypes) + 1:
                                rainboost = 1200
                            else:
                                rainboost = 600
                            log_stats("boost_to_rain", {"length": str(rainboost)})
                            channel.cat_rains += int(rainboost / 60) * 22
                            if channel.cat_rains > int(rainboost / 60) * 22:
                                await message.channel.send(f"# ‼️‼️ RAIN EXTENDED BY {int(rainboost / 60)} MINUTES ‼️‼️")
                                await message.channel.send(f"# ‼️‼️ RAIN EXTENDED BY {int(rainboost / 60)} MINUTES ‼️‼️")
                                await message.channel.send(f"# ‼️‼️ RAIN EXTENDED BY {int(rainboost / 60)} MINUTES ‼️‼️")
                            elif server.do_rain:
                                force_rain_summary = config.cat_cought_rain.get(channel.channel_id, {}).copy()
                                decided_time = random.uniform(1, 2)
                                channel.rain_should_end = int(time.time() + decided_time)
                                channel.yet_to_spawn = 0
                                config.cat_cought_rain[channel.channel_id] = {}
                                config.rain_starter[channel.channel_id] = message.author.id
                                bot.loop.create_task(rain_recovery_loop(channel))

                    boost_icon = get_aura_emoji(le_old_emoji, user.cat_auras)
                    prism_icon = get_emoji("prism")
                    if double_boost:
                        suffix_string += f"\n{prism_icon}{prism_icon} {boost_applied_prism} boosted this catch twice from a {boost_icon} {le_old_emoji} cat!"
                    elif overflow:
                        suffix_string += f"\n{prism_icon} {boost_applied_prism} tried to boost this catch, but failed!"
                    else:
                        suffix_string += f"\n{prism_icon} {boost_applied_prism} boosted this catch from a {boost_icon} {le_old_emoji} cat!"

                    if rainboost:
                        suffix_string += f" A {rainboost // 60}m rain will start!"

                icon = get_aura_emoji(le_emoji, user.cat_auras)

                if channel.channel_id in config.cat_cought_rain:
                    if le_emoji not in config.cat_cought_rain[channel.channel_id]:
                        config.cat_cought_rain[channel.channel_id][le_emoji] = []
                    for _ in range(silly_amount):
                        config.cat_cought_rain[channel.channel_id][le_emoji].append(f"<@{user.user_id}>")
                    for i in packs_gained:
                        if i not in config.cat_cought_rain[channel.channel_id]:
                            config.cat_cought_rain[channel.channel_id][i] = []
                        config.cat_cought_rain[channel.channel_id][i].append(f"<@{user.user_id}>")

                if random.randint(0, 5) == 0:
                    # shill rains
                    suffix_string += f"\n☔ get tons of cats and have fun: {get_command_mention('rain')}"
                if random.randint(1, 20) == 1:
                    # diplay a hint/fun fact
                    suffix_string += "\n💡 " + random.choice(data.hints)

                # sparkles
                sparkle_roll = random.random()
                sparkle_fired = False
                for sparkle in data.sparkle_messages:
                    if sparkle_roll < sparkle["odds"]:
                        suffix_string += f"\n{get_emoji(sparkle['emoji'])} This message appears on {sparkle['percent']} of catches{sparkle['punct']}"
                        sparkle_fired = True
                        break

                if channel.cought:
                    # custom spawn message
                    coughstring = channel.cought
                elif le_emoji in data.custom_cough_strings:
                    # custom type message
                    coughstring = data.custom_cough_strings[le_emoji]
                else:
                    # default
                    coughstring = "{username} cought {emoji} {type} cat!!!!1!\nYou now have {count} {cats} of dat type!!!\nthis fella was cought in {time}!!!!"

                view = None
                button = None

                async def dark_market_cutscene(interaction: discord.Interaction) -> None:
                    nonlocal message
                    if interaction.user != message.author:
                        await interaction.response.send_message(
                            "the shadow you saw runs away. perhaps you need to be the one to catch the cat.",
                            ephemeral=True,
                        )
                        return
                    if user.dark_market_active:
                        await interaction.response.send_message("the shadowy figure is nowhere to be found.", ephemeral=True)
                        return
                    user.dark_market_active = True
                    await user.save()
                    await interaction.response.send_message("is someone watching after you?", ephemeral=True)

                    for phrase in data.dark_market_followups:
                        await asyncio.sleep(5)
                        await interaction.followup.send(phrase, ephemeral=True)

                    await achemb(interaction, "dark_market", "followup")

                if random.randint(0, 10) == 0 and user.total_catches > 50 and not user.dark_market_active:
                    button = Button(label="You see a shadow...", style=ButtonStyle.red)
                    button.callback = dark_market_cutscene
                elif config.WEBHOOK_VERIFY and vote_time_user.vote_time_topgg + 43200 < time.time():
                    button = Button(
                        emoji=get_emoji("topgg"),
                        label=random.choice(data.vote_button_texts),
                        url="https://top.gg/bot/966695034340663367/vote",
                    )
                elif random.randint(0, 20) == 0:
                    button = Button(label="Join our Discord!", url="https://discord.gg/staring")
                elif random.randint(0, 500) == 0:
                    button = Button(label="John Discord 🤠", url="https://discord.gg/staring")
                elif random.randint(0, 50000) == 0:
                    button = Button(
                        label="DAVE DISCORD 😀💀⚠️🥺",
                        url="https://discord.gg/staring",
                    )
                elif random.randint(0, 5000000) == 0:
                    button = Button(
                        label="JOHN AND DAVE HAD A SON 💀🤠😀⚠️🥺",
                        url="https://discord.gg/staring",
                    )

                if button:
                    view = View(timeout=VIEW_TIMEOUT)
                    view.add_item(button)

                if vote_time_user.tutorial_state < 10 and vote_time_user.tutorial_state not in [0, 2]:
                    suffix_string += f"\n👋 Check out the {get_command_mention('tutorial')} (includes a free gift!)"

                user[f"cat_{le_emoji}"] += silly_amount
                new_count = user[f"cat_{le_emoji}"]

                async def delete_cat() -> None:
                    try:
                        cat_spawn = send_target.get_partial_message(cat_temp)
                        await cat_spawn.delete()
                    except Exception:
                        pass

                is_rain_catch = cat_rain_end or channel.cat_rains > 0

                async def send_confirm() -> discord.Message | None:
                    try:
                        assert le_emoji is not None
                        kwargs = {}
                        if view:
                            kwargs["view"] = view

                        catch_text = (
                            coughstring.replace("{username}", message.author.name.replace("_", "\\_"))
                            .replace("{emoji}", str(icon))
                            .replace("{type}", le_emoji)
                            .replace("{count}", f"{new_count:,}")
                            .replace("{cats}", plural("cat", new_count))
                            .replace("{time}", caught_time[:-1])
                            + suffix_string
                        )

                        if is_rain_catch:
                            cat_spawn = send_target.get_partial_message(cat_temp)
                            result = await cat_spawn.edit(content=catch_text, attachments=[], **kwargs)
                            return result

                        result = await send_target.send(catch_text, **kwargs)

                        if server.auto_delete_catches:
                            # button do stuff = button stay... for now-
                            delay = 30 if (button and button.callback) else 10
                            await result.delete(delay=delay)

                        return result

                    except Exception:
                        # Silently fail if we can't send the confirmation message (e.g. permission issues)
                        pass

                try:
                    if time_caught >= 0:
                        config.belated_catchers[message.channel.id] = {
                            "time": time_caught,
                            "users": [message.author.id],
                            "timestamp": current_time,
                            "cattype": channel.cattype,
                            "is_rain": cat_rain_end or channel.cat_rains > 0,
                            "late_catchers": [(message.author.id, None)],
                            "full_event": asyncio.Event(),
                        }
                except Exception:
                    pass

                if server.legacy_catching:
                    await asyncio.gather(delete_cat(), send_confirm())
                else:
                    result = await send_confirm()
                    bot.loop.create_task(
                        belated_window_task(
                            send_target.get_partial_message(cat_temp),
                            1 if is_rain_catch else 5,
                            bonus_chance,
                            result,
                            is_rain=is_rain_catch,
                        )
                    )

                log_stats("precatch", {"amount": "1", "cattype": channel.cattype})
                log_stats("postcatch", {"amount": str(silly_amount), "cattype": le_emoji})

                user.total_catches += 1
                user.last_catch = time.time()
                user.last_catch_channel = message.channel.id
                if do_time:
                    user.total_catch_time += time_caught

                # handle fastest and slowest catches
                if do_time and time_caught < user.time:
                    user.time = time_caught
                if do_time and time_caught > user.timeslow:
                    user.timeslow = time_caught

                if channel.cat_rains > 0:
                    user.rain_participations += 1

                await user.save()

                if sparkle_fired and not user.lucky:
                    await achemb(message, "lucky", "send")
                if message.content == "CAT" and not user.loud_cat:
                    await achemb(message, "loud_cat", "send")
                if bot.user in message.mentions and message.reference and message.reference.message_id == cat_temp and not user.ping_reply:
                    await achemb(message, "ping_reply", "send")
                if channel.cat_rains > 0 and not user.cat_rain:
                    await achemb(message, "cat_rain", "send")

                if not user.first:
                    await achemb(message, "first", "send")

                if user.time <= 5 and not user.fast_catcher:
                    await achemb(message, "fast_catcher", "send")

                if user.timeslow >= 3600 and not user.slow_catcher:
                    await achemb(message, "slow_catcher", "send")

                if time_caught in [3.14, 31.41, 31.42, 194.15, 194.16, 1901.59, 11655.92, 11655.93] and not user.pie:
                    await achemb(message, "pie", "send")

                if time_caught > 0 and time_caught == int(time_caught) and not user.perfection:
                    await achemb(message, "perfection", "send")

                if did_boost and not user.boosted:
                    await achemb(message, "boosted", "send")

                if "undefined" not in caught_time and time_caught > 0 and not user.all_the_same:
                    raw_digits = "".join(char for char in caught_time[:-1] if char.isdigit())
                    if len(set(raw_digits)) == 1:
                        await achemb(message, "all_the_same", "send")

                if suffix_string.count("\n") >= 4 and not user.certified_yapper:
                    await achemb(message, "certified_yapper", "send")

                # handle battlepass
                quests = await build_catch_quests(user, channel.cattype, time_caught, did_boost)

                # handle catnip bounties
                await bounty(message, user, channel.cattype)

                # handle quests
                await multi_progress(message, user, quests, False)

                if vote_time_user.tutorial_state == 0:
                    text = f"👋 Welcome to Cat Bot! Check out the {get_command_mention('tutorial')} to get started (includes a free gift!)"
                    try:
                        await message.reply(text, allowed_mentions=discord.AllowedMentions(users=True))
                    except Exception:
                        await message.channel.send(f"{message.author.mention} {text}", allowed_mentions=discord.AllowedMentions(users=True))
                    vote_time_user.tutorial_state = 1
                    await vote_time_user.save()
                elif vote_time_user.tutorial_state == 2:
                    text = f"✅ Run {get_command_mention('tutorial')} to continue"
                    try:
                        await message.reply(text, allowed_mentions=discord.AllowedMentions(users=True))
                    except Exception:
                        await message.channel.send(f"{message.author.mention} {text}", allowed_mentions=discord.AllowedMentions(users=True))
                    vote_time_user.tutorial_state = 3
                    await vote_time_user.save()
            finally:
                if decided_time:
                    if cat_rain_end:
                        await channel.save()
                        bot.loop.create_task(rain_end(message, channel, force_rain_summary))

                    # shift decided_time to reduce load
                    if decided_time > 10:
                        # ignore cat rains
                        start_time = channel.yet_to_spawn
                        shifts = [0] + [x for n in range(1, 11) for x in (n, -n)]
                        for shift in shifts:
                            c = await Channel.count("yet_to_spawn = $1", start_time + shift)
                            if c < 5:
                                channel.yet_to_spawn = start_time + shift
                                decided_time += shift
                                break

                    await channel.save()

                    await asyncio.sleep(decided_time)
                    temp_catches_storage.discard(pls_remove_me_later_k_thanks)
                    await spawn_cat(message.channel.id)
                else:
                    await channel.save()
                    temp_catches_storage.discard(pls_remove_me_later_k_thanks)

    # owner commands are real prefix commands now
    # (see the "owner commands" section near the end of the file, after the admin commands)
    if message.author.id == OWNER_ID:
        await bot.process_commands(message)


# the message when cat gets added to a new server
async def on_guild_join(guild: discord.Guild) -> None:
    def verify(ch: discord.TextChannel | None) -> bool:
        return bool(ch) and ch.permissions_for(guild.me).send_messages

    def find(patt: str, channels: list[discord.TextChannel]) -> discord.TextChannel | None:
        for i in channels:
            if patt in i.name:
                return i

    if not guild.self_role:
        source = "unknown"
    elif guild.self_role.permissions.use_external_emojis:
        source = "external"
    else:
        source = "discord"

    log_stats("guild_join", {"source": source})

    # first to try a good channel, then whenever we cat atleast chat
    found = False
    ch = None
    names = ["cat", "bot", "command", "welcome", "general"]
    for name in names:
        ch = find(name, guild.text_channels)
        if verify(ch):
            found = True
            break

    if not found:
        for ch in guild.text_channels:
            if verify(ch):
                found = True
                break

    # you are free to change/remove this, its just a note for general user letting them know
    unofficial_note = "**NOTE: This is an unofficial Cat Bot instance.**\n\n"
    if not bot.user or bot.user.id == 966695034340663367:
        unofficial_note = ""

    msg = f"""{unofficial_note}
Thanks for adding me!
Use `/setup` to start (creating a new channel just for Cat Bot is recommended)!
Join the support server here: https://discord.gg/staring
Have a nice day :)"""

    try:
        if found:
            assert ch is not None
            await ch.send(msg)
            log_stats("welcome_message")
    except Exception:
        pass

    try:
        async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=20):
            if bot.user and entry.target and entry.user and entry.target.id == bot.user.id:
                await entry.user.send(msg)
                log_stats("welcome_dm")
                break
    except Exception:
        pass

    server = await Server.get_or_create(server_id=guild.id)
    server.name = guild.name

    try:
        # set the bot display name style
        await bot.http.request(
            discord.http.Route("PATCH", f"/guilds/{guild.id}/members/@me"),
            json={"display_name_font_id": 3, "display_name_effect_id": 5, "display_name_colors": [16738816]},
        )
        server.name_style_set = True
    except Exception:
        pass

    await server.save()

    try:
        if config.INVITE_LOGS_CHANNEL:
            ch = bot.get_partial_messageable(config.INVITE_LOGS_CHANNEL)
            await ch.send(f"~#{server_count:,} | {guild.member_count:,} members | Invite source: {source}")
    except Exception:
        pass


# keep db server name in sync
async def on_guild_update(before: discord.Guild, after: discord.Guild) -> None:
    if before.name != after.name:
        server = await Server.get_or_create(server_id=after.id)
        server.name = after.name
        await server.save()


# 0 - not started
# 1 - seen cta message on catch, /tutorial required
# 2 - seen first tutorial page, catch required
# 3 - catch done, /tutorial refresh required
# 4 - second tutorial page shown, /inventory required
# 5 - /inventory done, third tutorial page shown, /leaderboards required
# 6 - /leaderboards done, fourth tutorial page shown, /achievements required
# 7 - /achievements done, fifth tutorial page shown, /battlepass required
# 8 - /battlepass done, sixth tutorial page shown, pack open required
# 9 - pack open done, final page shown, rain given
# 10 - tutorial complete
async def get_tutorial_view(user_id: int) -> LayoutView:
    user = await User.get_or_create(user_id=user_id)
    if user.tutorial_state == 0:
        user.tutorial_state = 1

    view = LayoutView(timeout=VIEW_TIMEOUT)
    match user.tutorial_state:
        case 1 | 2:
            user.tutorial_state = 2
            container = Container(
                f"## Welcome to {get_emoji('staring_cat')} Cat Bot!",
                "🐈 The main goal of the bot is to __catch cats__. You can do that by waiting for one to appear - it will look like on the image below (there is usually one every couple of minutes), then simply saying `cat` in the chat. Be quick - after the first person catches the cat, only the first *3 people* within *5 seconds* also get it.",
                "**Go try it!**",
                discord.ui.MediaGallery(
                    discord.MediaGalleryItem("https://cdn.discordapp.com/attachments/967080927937323138/1509316534462578838/tutorial1.png")
                ),
                "===",
                f"-# Progress: {get_emoji('staring_square') * user.tutorial_state}{'⬛' * (10 - user.tutorial_state)} {get_emoji('2rain')}",
            )
            view.add_item(container)
        case 3 | 4:
            user.tutorial_state = 4
            container = Container(
                "Well done! To see the cat you just caught, run `/inventory`!",
                "===",
                f"-# Progress: {get_emoji('staring_square') * user.tutorial_state}{'⬛' * (10 - user.tutorial_state)} {get_emoji('2rain')}",
            )
            view.add_item(container)
        case 5:
            container = Container(
                "This is your inventory. It's the place you can see your cat collection and some basic stats. You can also see anyone else's inventory by using `/inventory @username`.",
                "Lets run `/leaderboards` to see the best cat catchers in your server!",
                discord.ui.MediaGallery(
                    discord.MediaGalleryItem("https://cdn.discordapp.com/attachments/967080927937323138/1509316535108243608/tutorial2.png")
                ),
                "===",
                f"-# Progress: {get_emoji('staring_square') * user.tutorial_state}{'⬛' * (10 - user.tutorial_state)} {get_emoji('2rain')}",
            )
            view.add_item(container)
        case 6:
            container = Container(
                "Nice! Interacting with others is a big part of Cat Bot - don't be afraid to `/trade` with them or ask for advice!",
                "Speaking about important things, let's check out `/achievements`!",
                "===",
                f"-# Progress: {get_emoji('staring_square') * user.tutorial_state}{'⬛' * (10 - user.tutorial_state)} {get_emoji('2rain')}",
            )
            view.add_item(container)
        case 7:
            container = Container(
                f"Cat Bot has *a bunch* of {get_emoji('ach')} achievements, from very simple ones to {get_emoji('demonic_ach')} __ones which take months to complete__. If you ever feel unsure what to do, try completing some! You will also be able to discover a bunch of Cat Bot this way.",
                "Okay, the last important thing - run `/battlepass`.",
                "===",
                f"-# Progress: {get_emoji('staring_square') * user.tutorial_state}{'⬛' * (10 - user.tutorial_state)} {get_emoji('2rain')}",
            )
            view.add_item(container)
        case 8:
            container = Container(
                "⬆️ Cat Bot's Battlepass *(or Cattlepass)* is the main non-catching way of getting cats.",
                f"There are 3 quests which give you XP, and every couple hundred XP you will get some {get_emoji('goldpack')} __Packs__, which you can open via `/packs` to get some cats! Quests refresh 12 hours after completing them.",
                "**Try completing some quests and opening a pack!**",
                "===",
                f"-# Progress: {get_emoji('staring_square') * user.tutorial_state}{'⬛' * (10 - user.tutorial_state)} {get_emoji('2rain')}",
            )
            view.add_item(container)
        case 9:
            user.tutorial_state = 10
            if not user.claimed_free_rain:
                user.claimed_free_rain = True
                user.rain_minutes += 2
            container = Container(
                "Nice! One last thing - catching gets __a lot more fun__ if you use the various *power-ups* inside Cat Bot!",
                f"These include {get_emoji('prism')} `/Prism`s, {get_emoji('catnip')} `/Catnip`, 💫 `/Bless`ings, and ☔ `/Rain`.",
                "Speaking of the last one, for completing the tutorial you get **+2 free ☔ Rain Minutes**! You can use them via `/rain`.",
                "===",
                '-# ✅ Tutorial Complete! Go catch cats, do some achievements like saying "i read help", or discover the power-ups! Have fun!',
            )
            view.add_item(container)
        case 10:
            button = Button(label="Restart Tutorial")
            button.callback = restart_tutorial
            view.add_item(
                TextDisplay(
                    '✅ Tutorial Complete! Go catch cats, do some achievements like saying "i read help", or discover the power-ups! Have fun!',
                )
            )
            view.add_item(ActionRow(button))
    log_stats("tutorial_state_update", {"state": str(user.tutorial_state)})
    await user.save()
    return view


async def restart_tutorial(interaction: discord.Interaction) -> None:
    user = await User.get_or_create(user_id=interaction.user.id)
    user.tutorial_state = 1
    user.claimed_free_rain = True
    await user.save()
    await interaction.response.edit_message(view=await get_tutorial_view(interaction.user.id))


@bot.tree.command(description="A guide to help you get started with Cat Bot!")
async def tutorial(message: discord.Interaction):
    await message.response.send_message(view=await get_tutorial_view(message.user.id), ephemeral=True)


@bot.tree.command(description="Roll the credits")
async def credits(message: discord.Interaction):
    if not gen_credits:
        await message.response.send_message(
            "credits not yet ready! this is a very rare error, congrats.",
            ephemeral=True,
        )
        return

    embedVar = discord.Embed(title="Cat Bot", color=Colors.brown, description=gen_credits).set_thumbnail(
        url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png"
    )

    await message.response.send_message(embed=embedVar)


@bot.tree.command(description="add cat bot to your server")
async def invite(message: discord.Interaction):
    assert bot.user is not None
    view = View(timeout=1)
    invite_button = Button(label="Invite", url=discord.utils.oauth_url(bot.user.id, scopes=None))
    view.add_item(invite_button)
    await message.response.send_message("Click the button below to invite Cat Bot to your server!", view=view)


@bot.tree.command(description="View various info and stats about the bot")
async def info(message: discord.Interaction):
    assert message.guild is not None
    embed = discord.Embed(title="Cat Bot Info", color=Colors.brown)
    try:
        assert COMMIT != "unknown"
        proc = await asyncio.create_subprocess_exec("git", "show", "-s", "--format=%ct", COMMIT, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        git_timestamp = int(stdout.decode("utf-8").strip())
    except Exception:
        git_timestamp = 0

    embed.description = f"""
**__System__**
OS Version: `{platform.system()} {platform.release()}`
Python Version: `{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}`
discord.py Version: `{discord.__version__}{"-catbot" if "localhost" in str(discord.gateway.DiscordWebSocket.DEFAULT_GATEWAY) else ""}`
CPU usage: `{psutil.cpu_percent():.1f}%`
RAM usage: `{psutil.virtual_memory().percent:.1f}%`

**__Tech__**
Last hard restart: <t:{int(config.HARD_RESTART_TIME)}:R>
Last soft restart: <t:{int(config.SOFT_RESTART_TIME)}:R>
Commit: `{COMMIT[:7]}`
Commit time: {f"<t:{int(git_timestamp)}:R>" if git_timestamp else "N/A"}
Loops since soft restart: `{loop_count + 1:,}`

Guild shard: `{message.guild.shard_id:,}`
Guild cluster: `{int(message.guild.shard_id / len(bot.shards)) if config.CLUSTERING else "N/A"}`
Guilds in cluster: `{format(len(bot.guilds), ",") if config.CLUSTERING else "N/A"}`

**__Global Stats__**
Guilds: `{f"{server_count:,}" if server_count else "..."}`
DB Profiles: `{await _get_pool().fetchval("SELECT reltuples::bigint FROM pg_class WHERE oid = 'public.profile'::regclass;"):,}`
DB Users: `{await _get_pool().fetchval("SELECT reltuples::bigint FROM pg_class WHERE oid = 'public.user'::regclass;"):,}`
DB Channels: `{await _get_pool().fetchval("SELECT reltuples::bigint FROM pg_class WHERE oid = 'public.channel'::regclass;"):,}`
DB Prisms: `{await _get_pool().fetchval("SELECT reltuples::bigint FROM pg_class WHERE oid = 'public.prism'::regclass;"):,}`
DB Servers: `{await _get_pool().fetchval("SELECT reltuples::bigint FROM pg_class WHERE oid = 'public.server'::regclass;"):,}`
"""

    await message.response.send_message(embed=embed)


@bot.tree.command(description="Confused? Check out the Cat Bot Wiki!")
async def wiki(message: discord.Interaction):
    await message.response.send_message(embed=discord.Embed(title="Cat Bot Wiki", color=Colors.brown, description="\n".join(data.wiki_lines)))


@bot.tree.command(description="Consult the ancient cat oracle for a purrsonalized fortune")
async def fortune(interaction: discord.Interaction):
    rng = random.Random(interaction.user.id + discord.utils.utcnow().date().toordinal())

    embed = discord.Embed(
        title=f"🔮 {rng.choice(data.cat_fortune_titles)}",
        description=(
            f"😺 {rng.choice(data.cat_fortunes)}\n\n"
            f"**Lucky cat type:** {rng.choice(cattypes)}\n"
            f"**Lucky number:** {rng.randint(1, 9)}\n"
            f"**Lucky activity:** {rng.choice(data.cat_activities)}"
        ),
        color=Colors.brown,
    )

    embed.set_footer(text="Fortunes reset daily • Your fate is sealed (until tomorrow)")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(description="Read The Cat Bot Times™️")
async def news(message: discord.Interaction):
    user = await User.get_or_create(user_id=message.user.id)
    buttons = []
    current_state = user.news_state.strip()

    async def send_news(interaction: discord.Interaction) -> None:
        if not interaction.custom_id or interaction.user != message.user:
            await do_funny(interaction)
            return

        news_id = int(interaction.custom_id)

        async def go_back(interaction: discord.Interaction) -> None:
            if interaction.user != message.user:
                await do_funny(interaction)
                return
            await regen_buttons()
            await interaction.response.edit_message(view=generate_page(current_page))

        current_state = user.news_state.strip()
        if current_state[news_id] not in "123456789":
            user.news_state = current_state[:news_id] + "1" + current_state[news_id + 1 :]
            await user.save()

        view = LayoutView(timeout=VIEW_TIMEOUT)
        back_button = Button(emoji="⬅️", label="Back")
        back_button.callback = go_back
        back_row = ActionRow(back_button)

        log_stats("news", {"id": str(news_id)})

        match news_id:
            case 0:
                embed = Container(
                    "## 📜 Cat Bot Survey (ended)",
                    "Hello and welcome to The Cat Bot Times:tm:! I kind of want to learn more about your time with Cat Bot because I barely know about it lmao. This should only take a couple of minutes.\n\nGood high-quality responses will win FREE cat rain prizes.\n\nSurvey is closed!",
                    "-# <t:1731168230>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 1:
                embed = Container(
                    "## ✨ New Cat Rains perks!",
                    "Hey there! Buying Cat Rains now gives you access to `/editprofile` command! You can add an image, change profile color, and add an emoji next to your name. Additionally, you will now get a special role in our [discord server](https://discord.gg/staring).\nEveryone who ever bought rains and all future buyers will get it.\nAnyone who bought these abilities separately in the past (known as 'Cat Bot Supporter') have received 10 minutes of Rains as compensation.\n\nThis is a really cool perk and I hope you like it!",
                    Button(label="Cat Bot Store", url="https://catbot.shop"),
                    "-# <t:1732377932>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 2:
                embed = Container(
                    "## ☃️ Cat Bot Christmas",
                    f"⚡ **Cat Bot Wrapped 2024**\nIn 2024 Cat Bot got...\n- 🖥️ *45777* new servers!\n- 👋 *286607* new profiles!\n- {get_emoji('staring_cat')} okay so funny story due to the new 2.1 billion per cattype limit i added a few months ago 4 with 832 zeros cats were deleted... oopsie... there are currently *64105220101255* cats among the entire bot rn though\n- {get_emoji('cat_throphy')} *1518096* achievements get!\nSee last year's Wrapped [here](<https://discord.com/channels/966586000417619998/1021844042654417017/1188573593408385074>).\n\n❓ **New Year Update**\nSomething is coming...",
                    "-# <t:1734458962>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 3:
                embed = Container(
                    "## Cattlepass is getting an update!",
                    """### qhar?
- Huge stuff!
- Cattlepass will now reset every month
- You will have 3 quests, including voting
- They refresh 12 hours after completing
- Quest reward is XP which goes towards progressing
- There are 30 cattlepass levels with much better rewards (even Ultimate cats and Rain minutes!)
- Prism crafting/true ending no longer require cattlepass progress.
- More fun stuff to do each day and better rewards!

### oh no what if i hate grinding?
Don't worry, quests are very easy and to complete the cattlepass you will need to complete less than 3 easy quests a day.

### will you sell paid cattlepass? its joever
There are currently no plans to sell a paid cattlepass.""",
                    "-# <t:1735689601>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 4:
                embed = Container(
                    f"## {get_emoji('goldpack')} Packs!",
                    f"""you want more gambling? we heard you!
instead of predetermined cat rewards you now unlock Packs! packs have different rarities and have a 30% chance to upgrade a rarity when opening, then 30% for one more upgrade and so on. this means even the most common packs have a small chance to upgrade to the rarest one!
the rarities are - Wooden {get_emoji("woodenpack")}, Stone {get_emoji("stonepack")}, Bronze {get_emoji("bronzepack")}, Silver {get_emoji("silverpack")}, Gold {get_emoji("goldpack")}, Platinum {get_emoji("platinumpack")}, Diamond {get_emoji("diamondpack")} and Celestial {get_emoji("celestialpack")}!
the extra reward is now a stone pack instead of 5 random cats too!
*LETS GO GAMBLING*""",
                    "-# <t:1740787200>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 5:
                embed = Container(
                    "## Important Message from CEO of Cat Bot",
                    """(April Fools 2025)

Dear Cat Bot users,

I hope this message finds you well. I want to take a moment to address some recent developments within our organization that are crucial for our continued success.

Our latest update has had a significant impact on our financial resources, resulting in an unexpected budget shortfall. In light of this situation, we have made the difficult decision to implement advertising on our platform to help offset these costs. We believe this strategy will not only stabilize our finances but also create new opportunities for growth.

Additionally, in our efforts to manage expenses more effectively, we have replaced all cat emojis with just the "Fine Cat" branding. This change will help us save on copyright fees while maintaining an acceptable user experience.

We are committed to resolving these challenges and aim to have everything back on track by **April 2nd**. Thank you for your understanding and continued dedication during this time. Together, we will navigate these changes and emerge stronger.

Best regards,
[Your Name]""",
                    "-# <t:1743454803>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 6:
                embed = Container(
                    "## 🥳 Cat Bot Turns 3",
                    """april 21st is a special day for cat bot! on this day is its birthday, and in 2025 its turning three!
happy birthda~~
...
hold on...
im recieving some news cats are starting to get caught with puzzle pieces in their teeth!
the puzzle pieces say something about having to collect a million of them...
how interesting!

update: the puzzle piece event has concluded""",
                    "-# <t:1745242856>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 7:
                embed = Container(
                    "## 🎉 100,000 SERVERS WHAT",
                    """wow! cat bot has reached 100,000 servers! this beyond insane i never thought this would happen thanks everyone
giving away a whole bunch of rain as celebration!

1. cat stand giveaway (ENDED)
[join our discord server](<https://discord.gg/FBkXDxjqSz>) and click the first reaction under the latest newspost to join in!
there will be a total of 10 winners who will get 40 minutes each! giveaway ends july 5th.

2. art contest (ENDED)
again in our [discord server](<https://discord.gg/zrYstPe3W6>) a new channel has opened for art submissions!
top 5 people who get the most community votes will get 250, 150, 100, 50 and 50 rain minutes respectively!

3. cat bot event (ENDED)
starting june 30th, for the next 5 days you will get points randomly on every catch! if you manage to collect 1,000 points before the time runs out you will get 2 minutes of rain!!

4. sale (ENDED)
starting june 30th, [catbot.shop](<https://catbot.shop>) will have a sale for the next 5 days! if everything above wasnt enough rain for your fancy you can buy some more with a discount!

aaaaaaaaaaaaaaa""",
                    ActionRow(
                        Button(label="Join our Server", url="https://discord.gg/staring"),
                        Button(label="Cat Bot Store", url="https://catbot.shop"),
                    ),
                    "-# <t:1751252181>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 8:
                embed = Container(
                    "## Regarding recent instabilities",
                    """hello!

stuff has been kinda broken the past few days, and the past 24 hours in paricular.

it was mostly my fault, but i worked hard to fix everything and i think its mostly working now.

as a compensation i will give everyone who voted in the past 3 days 2 free gold packs! you can press the button below to claim them. (note you can only claim it in 1 server, choose wisely)

thanks for using cat bot!""",
                    Button(label="Expired!", disabled=True),
                    "-# <t:1752689941>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 9:
                # we hijack the cookie system to store the yippee count
                assert bot.user is not None
                cookie_user = await Profile.get_or_create(guild_id=9, user_id=bot.user.id)

                async def add_yippee(interaction: discord.Interaction) -> None:
                    nonlocal cookie_user
                    assert bot.user is not None
                    cookie_user = await Profile.get(["cookies"], guild_id=9, user_id=bot.user.id)
                    cookie_user.cookies += 1
                    await cookie_user.save()
                    await send_yippee(interaction)

                async def send_yippee(interaction: discord.Interaction) -> None:
                    view = LayoutView(timeout=VIEW_TIMEOUT)
                    btn = Button(label=f"yippee! ({cookie_user.cookies:,})", emoji=get_emoji("yippee"), style=ButtonStyle.primary)
                    btn.callback = add_yippee
                    embed = Container(
                        "## cat bot is now top 5 on top.gg",
                        "thanks for voting",
                        discord.ui.MediaGallery(discord.MediaGalleryItem("https://i.imgur.com/MSZF3ly.png")),
                        "also pls still [go vote](https://top.gg/bot/966695034340663367/vote) incase OwO will rebeat us!!",
                        "===",
                        btn,
                        "-# <t:1757794211>",
                    )
                    view.add_item(embed)
                    view.add_item(back_row)
                    await interaction.response.edit_message(view=view)

                await send_yippee(interaction)
            case 10:
                embed = Container(
                    "## 🏆 nominate cat bot for top.gg awards (outdated)",
                    "holy cat top.gg is doing annual awards now",
                    "you know [what to do](https://top.gg/bot/966695034340663367)...\nyou can also leave a review while you are there if you havent yet :3",
                    discord.ui.MediaGallery(discord.MediaGalleryItem("https://i.imgur.com/YgQ0flQ.png")),
                    Button(label="Vote for Cat Bot", url="https://nominations.top.gg/", emoji="🏆"),
                    "-# <t:1759513848>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 11:
                embed = Container(
                    f"## {get_emoji('catnip')} Welcome to the Cat Mafia",
                    f"""after the dog mafia got arrested, cats got inspired and started their own mafia!

- the dark market is being replaced by {get_emoji("catnip")} catnip
- the biggest update ever (probably)
- this is a new late-game complex mechanic with *leveling, bounties and perks*
- it can be accessed and managed via /catnip
- discover **10 new cats** - the members of the mafia who have tough challenges for you
- getting through all of it is a very tough challenge, **the hardest thing in cat bot**
- the old system is completely gone, all process you had in it will be reset

👉 okay now let me explain:
at each level you will have some bounties you have to complete within a time frame. if you complete the bounties and pay the price, you will be able to choose one of 3 different perks of random rarities {get_emoji("common")}{get_emoji("uncommon")}{get_emoji("rare")}{get_emoji("epic")}{get_emoji("legendary")}. the perks will stack while catnip is active! failing to complete the bounties will bring you one level down and you will lose your last perk. higher levels are harder but give you better perks!""",
                    "-# <t:1761325200>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 12:
                embed = Container(
                    "## ❤️ vote for cat bot in top.gg awards (outdated)",
                    'cat bot is finalist in "Labor of Love" category on top.gg awards!',
                    "make sure to [vote for it](https://nominations.top.gg/) and perhaps attend the awards ceremony on january 3rd",
                    discord.ui.MediaGallery(discord.MediaGalleryItem("https://i.imgur.com/7EW2I4P.png")),
                    Button(label="Vote for Cat Bot", url="https://nominations.top.gg/", emoji="🏆"),
                    "-# <t:1765747278>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 13:
                embed = Container(
                    f"## {get_emoji('christmaspack')} Cat Bot Christmas 2025 (event over)",
                    f"""Merry Christmas!

{get_emoji("christmaspack")} **Christmas Packs**
Christmas packs are a new pack type with a twist: when opening them the upgrade chances are 70% instead of 30%!
They start below Wooden with base value of 30. Their average value is ~225.
You can trade, gift, and open them as usual even after the event ends.
You will be able to collect them until <t:1767297600> using 2 methods:
- You get 1 when completing the Vote quest, or
- You get 1 for every 500 snowflakes you earn.

❄️ **Snowflakes**
You can get them by catching cats. The amount will be determined by the value of the catch (excluding all boosts), where 1 value = 1 ❄️.
This means catching an eGirl cat will give you 4 Christmas packs!

🎅 **Christmas Sale**
-20% sale starts now on the Cat Bot Store!
:point_right: **[catbot.shop](<https://catbot.shop>)**""",
                    ActionRow(
                        Button(label="Cat Bot Store", url="https://catbot.shop"),
                    ),
                    "-# <t:1766433600>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 14:
                embed = Container(
                    "## 💝 Valentine's Day!",
                    f"""💞 **Pick a Valentine** (event over)
Use `/valentine` to pick a valentine - your progress and rewards will be shared with them for the duration of the event.
You can't change this after you picked someone, so choose wisely!

{get_emoji("valentinepack")} **Valentine Packs**
Valentine packs are the new event pack type, with the upgrade chances being 70% instead of 30%!
Just like Christmas packs, they start below Wooden with base value of 30 and have average value of ~225.
You can trade, gift, and open them as usual even after the event ends.
You will be able to collect them until <t:1771437600> using 2 methods:
- You and your valentine both get 1 when either of you completes the Vote quest, and
- You and your valentine both get 1 for every 50 cats you collectively catch.

🥰 **Valentine's Sale** (over)
-20% sale starts now on the Cat Bot Store and will end on <t:1771437600>!
:point_right: **[catbot.shop](<https://catbot.shop>)**""",
                    ActionRow(
                        Button(label="Cat Bot Store", url="https://catbot.shop"),
                    ),
                    "-# <t:1771005600>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 15:
                embed = Container(
                    "## 📈 Welcome to the Stock Market",
                    """ever wanted to invest your cats into stocks? no? well now you can!
- /stocks and /portfolio
- deposit packs to get coins
- trade shares of stocks with other cat bot users globally
- earn random rewards from time to time
- withdraw coins back to packs

i understand this might be overwhelming which is why i added a ton of help buttons throughout the thing! those have much better explanations than this brief overview

ummm good luck and let the line go up!""",
                    "-# <t:1772308800>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 16:
                embed = Container(
                    "## PackOrRain Event (ended)",
                    "everyone *who votes below* will earn a prize! the prize type will be **whatever option gets most votes**, and the prize amount will be **how many millions of catches** everyone does until the event ends!",
                    "-# the prize will be given to everyone who votes, even if their vote wasn't the winning option.",
                    "===",
                    "**Final Prize**: 2 ☔ Rain Minutes",
                    "**Event ended** <t:1773856800>",
                    "===",
                    "-# <t:1773424800>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 17:
                embed = Container(
                    f"## {get_emoji('insane')} cat bot has reached 200k servers!",
                    "wow big number!!",
                    "to celebrate im ~~doing a 200 rain minute giveaway~~ ended!! in our [discord server](https://discord.com/channels/966586000417619998/1021844042654417017/1492510874458394655)",
                    ActionRow(
                        Button(label="Join the server", url="https://discord.gg/staring"),
                    ),
                    "-# <t:1775913490>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 18:
                embed = Container(
                    f"## {get_emoji('b_gremlincat')} It's Cat Bot's 4th birthday!!",
                    Section(
                        f"### {get_emoji('b_gremlincat')} Baby cat becomes an adult 🥳 [ended]",
                        "Help decide Baby cat's new name via a poll in our [Discord server](https://discord.com/channels/966586000417619998/1021844042654417017)!",
                        Button(label="Vote!", url="https://discord.com/channels/966586000417619998/1021844042654417017"),
                    ),
                    f"### {get_emoji('birthdaypack')} Birthday Packs [ended]",
                    f"For the next 5 days, you will get a {get_emoji('birthdaypack')} Birthday Pack for every {get_emoji('b_gremlincat')} Baby cat you catch!\nCollect 10 of them to get ☔ **2 free Rain Minutes**!",
                    Section(
                        "### 🎨 Birthday Art Contest [ended]",
                        "Join our [Discord server](https://discord.gg/staring) to participate in the Birthday Art Contest! 3 winners will get ☔ **100 Rain Minutes** each.",
                        Button(label="Join the server", url="https://discord.gg/staring"),
                    ),
                    Section(
                        f"### {get_emoji('insane')} -50% off Sale [ended]",
                        "This is **much higher** than normal sale amounts!!",
                        Button(label="catbot.shop", emoji="☔", url="https://catbot.shop"),
                    ),
                    "-# <t:1776778856>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 19:
                view.add_item(
                    Container(
                        "## Cat Bot Plush [ended]",
                        "~~[Pre-order now for $2!](https://www.makeship.com/petitions/cat-bot-plush)~~",
                        "Everyone who pre-ordered will also get ☔ **60 Rain Minutes** and a badge! Run `/plushbadge` to redeem.",
                        "===",
                        "-# <t:1777921200>",
                    )
                )
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 20:
                view.add_item(
                    Container(
                        "## 🎖️ Badges!",
                        "have you ever wanted to flex that *you were there* but had no proof? well now you can! here are the badges i retroactively added:",
                        f"""- {get_emoji("og_badge")} *OG Badge* - Interact with Cat Bot before it got verified (71 people)
- {get_emoji("cataine_badge")} *Cataine Badge* - Defeat the Dog Mafia prior to Oct 13 2025 (4200 people)
- {get_emoji("second_birthday_badge")} *Second Birthday Badge* - Join the Cat Bot Birthday Server on Apr 21 2024 (1708 people)
- {get_emoji("puzzle_badge")} *Puzzle Badge* - Collect at least 25 puzzle pieces during 2025 Birthday event (8893 people)
- {get_emoji("plush_badge")} *Plush Badge* - Pre-order the Cat Bot Plush and run `/plushbadge`""",
                        "we hit the petition goal! i will give everyone who pre-orders (or already did) ☔ **60 Rain Minutes** as well! so",
                        "-# june update will be hype, sry for all the shilling",
                        "===",
                        "-# <t:1778544574>",
                    )
                )
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 21:
                view.add_item(
                    Container(
                        "## 🐈 CATCHING UPDATE",
                        f"1. {get_emoji('pointlaugh')} late catching",
                        """now __the first 3 people to catch within 5 seconds__ of the original catcher will also get the cat, although **without any boosts**! "first-wins-all" was one of the most popular complaints on that one survey i did back in 2024.
here is a helpful table of what works and what doesnt when you are late:
- ✅ Progress of catnip bounties, cattlepass quests and /tutorial all trigger within 5s, even outside of 3 people limit
- ❌ Achievements; activations of catnip perks, prisms, blessings, etc (up to 3 late people will only get +1 unboosted cat)""",
                        "2. 🎁 bonus cats",
                        """there is a small chance (around 6.5% on average, *chance is higher for rarer cats*) that a cat is a __bonus cat__. such a cat will have *a minigame* after its caught, in which you can get **+3 more of it** if you succeed. only people who caught the cat can play this minigame (this includes the initial catcher + late catchers, so max of 4 people).
each of 22 cats has a unique minigame associated with it.
there is also a new catnip perk which makes these bonus cats more likely (only activates from initial catcher)""",
                        'both of the updates above can be rolled back via "Legacy Catching" toggle in /settings',
                        "3. ☔ rain",
                        """heres how these mechanics work during rain:
- the late catching window is reduced to 1 second
- bonus cats give +1 cat to everyone eligible instead of a minigame
- both are reflected in rain summaries
these changes were made to not slow down rains. like, i pinky promise they arent slower
unrelated, cat rains were also increased from ~21.818 to a nice round 22 cats per minute. this results in all rains having atleast +1 more cat, and then approx. +1 more for every 5 minute of length.""",
                        "===",
                        "-# <t:1782500400>",
                    )
                )
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)
            case 22:
                embed = Container(
                    "## 😻 250k/Cat Day Event",
                    f"-# quarter million lets go! and happy international cat day! and {get_command_mention('stocks')} are back!",
                    "A new catching event, ending <t:1786651200:R>! For every *unique cat type* you catch, you will get a pack! The pack type will be determined by *how many catches everyone globally does*. See below for current event state!",
                    f"*Final reward:* {get_emoji('silverpack')} Silver Pack",
                    "===",
                    "## 🔥 Cat Day Sale!",
                    "Also ending <t:1786651200:R>, there is a -20% sale over on [catbot.shop](https://catbot.shop)! Yippee!",
                    ActionRow(
                        Button(label="Cat Bot Shop", url="https://catbot.shop"),
                    ),
                    "-# <t:1786132800>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.response.edit_message(view=view)

    async def regen_buttons() -> None:
        nonlocal buttons
        await user.refresh_from_db()
        buttons = []
        active_buttons = []
        current_state = user.news_state.strip()
        for num, article in enumerate(data.news_list[::-1]):
            num = len(data.news_list) - num - 1
            try:
                have_read_this = current_state[num] != "0"
            except Exception:
                have_read_this = False
            button = Button(
                label=article["title"],
                emoji=get_emoji(article["emoji"]),
                custom_id=str(num),
                style=ButtonStyle.green if not have_read_this else ButtonStyle.gray,
            )
            button.callback = send_news
            if article["active"] and len(active_buttons) <= 3:
                active_buttons.append(button)
            else:
                buttons.append(button)
        active_buttons.extend(buttons)
        buttons = active_buttons.copy()

    await regen_buttons()

    if len(data.news_list) > len(current_state):
        user.news_state = current_state + "0" * (len(data.news_list) - len(current_state))
        await user.save()

    current_page = 0

    async def prev_page(interaction: discord.Interaction) -> None:
        nonlocal current_page
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        current_page -= 1
        await interaction.response.edit_message(view=generate_page(current_page))

    async def next_page(interaction: discord.Interaction) -> None:
        nonlocal current_page
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        current_page += 1
        await interaction.response.edit_message(view=generate_page(current_page))

    async def mark_all_as_read(interaction: discord.Interaction) -> None:
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        user.news_state = "1" * len(data.news_list)
        await user.save()
        await regen_buttons()
        await interaction.response.edit_message(view=generate_page(current_page))

    def generate_page(number: int) -> LayoutView:
        view = LayoutView(timeout=VIEW_TIMEOUT)
        view.add_item(TextDisplay("Choose an article:"))

        # article buttons
        if current_page == 0:
            end = (number + 1) * 4
            row = None
        else:
            end = len(buttons)
            row = ActionRow()
        for num, button in enumerate(buttons[number * 4 : end]):
            if not row:
                view.add_item(ActionRow(button))
            else:
                if len(row.children) == 5:
                    view.add_item(row)
                    row = ActionRow()
                row.add_item(button)

        if row and len(row.children) > 0:
            view.add_item(row)

        last_row = ActionRow()

        # pages buttons
        if current_page != 0:
            button = Button(label="Back")
            button.callback = prev_page
            last_row.add_item(button)

        button = Button(label="Mark all as read")
        button.callback = mark_all_as_read
        last_row.add_item(button)

        if current_page == 0:
            button = Button(label="Archive")
            button.callback = next_page
            last_row.add_item(button)

        view.add_item(last_row)

        return view

    await message.response.send_message(view=generate_page(current_page))
    await achemb(message, "news", "followup")


@bot.tree.command(description="Read text as TikTok TTS woman")
@discord.app_commands.describe(text="The text to be read! (300 characters max)")
async def tiktok(message: discord.Interaction, text: str):
    # detect n-words
    for i in NONOWORDS:
        if i in text.lower():
            await message.response.send_message("Do not.", ephemeral=True)
            return

    if text == "bwomp":
        file = discord.File("assets/bwomp.mp3", filename="bwomp.mp3")
        await message.response.send_message(file=file)
        await achemb(message, "bwomp", "followup")
        return

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                "https://tiktok-tts.weilnet.workers.dev/api/generation",
                json={"text": text, "voice": "en_us_001"},
                headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"},
            ) as response,
        ):
            stuff = await response.json()
            with io.BytesIO() as f:
                ba = "data:audio/mpeg;base64," + stuff["data"]
                f.write(base64.b64decode(ba))
                f.seek(0)
                await message.response.send_message(file=discord.File(fp=f, filename="output.mp3"))
    except Exception:
        await message.response.send_message("i dont speak guacamole (remove non-english characters, make sure the message is below 300 characters)")


@bot.tree.command(description="(ADMIN) Prevent someone from catching cats for a certain time period")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(person="A person to timeout!", timeout="How many seconds? (0 to reset, -1 for infinity)")
async def preventcatch(message: discord.Interaction, person: discord.User, timeout: int):
    assert message.guild is not None
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=person.id)
    if person == bot.user:
        await message.response.send_message("i hate you")
        return
    if timeout == 0:
        timestamp = 0
        suffix = " can now catch cats again."
    elif timeout == -1:
        timestamp = 9223372036854775806  # :wyphsmall:
        suffix = " can't catch cats until the year 292277026596"
        # You finally wake up from your coma. It's the year 292,277,026,596.
        # After the events of the World War 239, 99% of the humanity was wiped.
        # Only a few people are preserved in cryogenic sleep.
        # The AIs are waking them up to let them know of a high likelihood of a catastrophic failure
        # caused by the 64 bit integer limit for unix timestamps.
        # You realize it is out of your control, and decide to spend your last moments in a fun way.
        # You open a completely random app using your brainchip - it lands on Discord.
        # Due to the technological breakthroughs of the 22nd century all computers can run without electricity,
        # and the internet connection can't break due to quantum entanglement, which means abandoned apps can work forever.
        # No one has touched this app in thousands of milleniums, and it was abandoned by the developers back in 2126.
        # You open a random server your account happens to be in.
        # "A Fine cat has appeared. Type "cat" to catch it!". You do as instructed.
        # The catch fails, but seconds later you get a notification that your /preventcatch expired.
        # All the memories come back. You break down crying.
        # "this fella was caught in 292277024570 years 69 days 21 hours 42 minutes 6.7 seconds"
        # This gotta be a record.
    else:
        timestamp = round(time.time()) + timeout
        suffix = f" can't catch cats until <t:{timestamp}:R>"
    user.timeout = timestamp
    await user.save()
    await message.response.send_message(person.name.replace("_", r"\_") + suffix)


@bot.tree.command(description="(ADMIN) Change Cat Bot avatar")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(avatar="The avatar to use (leave empty to reset)")
async def changeavatar(message: discord.Interaction, avatar: discord.Attachment | None = None):
    if avatar and avatar.content_type not in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
        await message.response.send_message("Invalid file type! Please upload a PNG, JPEG, GIF, or WebP image.", ephemeral=True)
        return

    if avatar:
        try:
            avatar_value = await avatar.read()
        except Exception:
            await message.response.send_message("your image is too weird", ephemeral=True)
            return
    else:
        avatar_value = None

    try:
        assert message.guild is not None
        await message.guild.me.edit(avatar=avatar_value)
        await message.response.send_message("Avatar changed successfully!")
    except Exception:
        await message.response.send_message("Failed to change avatar! Your image is too big or you are changing avatars too quickly.", ephemeral=True)
        return


@bot.tree.command(description="(ADMIN) Change the cat spawn/appear times")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(
    minimum_time="In seconds, minimum possible time between spawns (leave both empty to reset)",
    maximum_time="In seconds, maximum possible time between spawns (leave both empty to reset)",
)
async def changetimings(
    message: discord.Interaction,
    minimum_time: int | None = None,
    maximum_time: int | None = None,
):
    assert isinstance(message.channel, GuildMessageable)
    if not (channel := await Channel.get_or_none(channel_id=message.channel.id)):
        await message.response.send_message("This channel isnt setupped. Please select a valid channel.", ephemeral=True)
        return

    if not minimum_time and not maximum_time:
        # reset
        channel.spawn_times_min = 60
        channel.spawn_times_max = 600
        await channel.save()
        await message.response.send_message("Success! This channel is now reset back to usual spawning intervals.")
    elif minimum_time and maximum_time:
        if minimum_time < 20:
            await message.response.send_message("Sorry, but minimum time must be above 20 seconds.", ephemeral=True)
            return
        if maximum_time < minimum_time:
            await message.response.send_message(
                "Sorry, but maximum time must not be less than minimum time.",
                ephemeral=True,
            )
            return

        channel.spawn_times_min = minimum_time
        channel.spawn_times_max = maximum_time
        await channel.save()

        await message.response.send_message(
            f"Success! The spawn times are now {minimum_time} to {maximum_time} seconds. Please note the changes will only apply after the next spawn."
        )
    else:
        await message.response.send_message("Please input all times.", ephemeral=True)


@bot.tree.command(description="(ADMIN) Change the cat appear and cought message texts")
@discord.app_commands.default_permissions(manage_guild=True)
async def changemessage(message: discord.Interaction):
    assert isinstance(message.channel, GuildMessageable)
    caller = message.user
    if not (channel := await Channel.get_or_none(channel_id=message.channel.id)):
        await message.response.send_message("pls setup this channel first", ephemeral=True)
        return

    # this is the silly popup when you click the button
    class InputModal(Modal):
        def __init__(self, type: str):
            super().__init__(
                title=f"Change {type} Message",
                timeout=VIEW_TIMEOUT,
            )

            self.type = type

            if self.type == "Appear":
                default = channel.appear if channel.appear else '{emoji} {type} cat has appeared! Type "cat" to catch it!'
            else:
                default = (
                    channel.cought
                    if channel.cought
                    else "{username} cought {emoji} {type} cat!!!!1!\nYou now have {count} {cats} of dat type!!!\nthis fella was cought in {time}!!!!"
                )

            self.input = TextInput(
                min_length=0,
                max_length=1000,
                label="Input",
                style=discord.TextStyle.long,
                required=False,
                default=default,
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction) -> None:
            await channel.refresh_from_db()
            if not channel:
                await message.response.send_message("this channel is not /setup-ed", ephemeral=True)
                return
            input_value = self.input.value

            # check if all placeholders are there
            if input_value != "":
                check = ["{emoji}", "{type}"] + (["{username}", "{count}", "{time}"] if self.type == "Cought" else [])

                for i in check:
                    if i not in input_value:
                        await interaction.response.send_message(
                            f"nuh uh! you are missing `{i}`.\nyou must include the placeholders exactly like they are shown, the values will be replaced by cat bot when it uses them.",
                            ephemeral=True,
                        )
                        return
                    elif input_value.count(i) > 10:
                        await interaction.response.send_message(f"nuh uh! you are using too much of `{i}`.", ephemeral=True)
                        return

                # check there are no emojis as to not break catching
                for i in allowedemojis:
                    if i in input_value:
                        await interaction.response.send_message(f"nuh uh! you cant use `{i}`. sorry!", ephemeral=True)
                        return

                icon = get_emoji("finecat")
                await interaction.response.send_message(
                    "Success! Here is a preview:\n"
                    + input_value.replace("{emoji}", str(icon))
                    .replace("{type}", "Fine")
                    .replace("{username}", "Cat Bot")
                    .replace("{count}", "1")
                    .replace("{cats}", plural("cat", 1))
                    .replace("{time}", "69 years 420 days")
                )
            else:
                await interaction.response.send_message("Reset to defaults.")

            if self.type == "Appear":
                channel.appear = input_value
            else:
                channel.cought = input_value

            await channel.save()

    # helper to make the above popup appear
    async def ask_appear(interaction: discord.Interaction) -> None:
        nonlocal caller

        if interaction.user != caller:
            await do_funny(interaction)
            return

        modal = InputModal("Appear")
        await interaction.response.send_modal(modal)

    async def ask_catch(interaction: discord.Interaction) -> None:
        nonlocal caller

        if interaction.user != caller:
            await do_funny(interaction)
            return

        modal = InputModal("Cought")
        await interaction.response.send_modal(modal)

    embed = discord.Embed(
        title="Change appear and cought messages",
        description="""below are buttons to change them.
they are required to have all placeholders somewhere in them.
you must include the placeholders exactly like they are shown below, the values will be replaced by cat bot when it uses them.
that being:

for appear:
`{emoji}`, `{type}`

for cought:
`{emoji}`, `{type}`, `{username}`, `{count}`, `{time}`

optionally, you can also use `{cats}` for cought, which will say "cat" or "cats" depending on the count.

missing any of the required ones will result in a failure.
how to do mentions: `@everyone`, `@here`, `<@userid>`, `<@&roleid>`
to get ids, run `/getid` with the thing you want to mention.
if it doesnt work make sure the bot has mention permissions.
leave blank to reset.""",
        color=Colors.brown,
    )

    button1 = Button(label="Appear Message", style=ButtonStyle.blurple)
    button1.callback = ask_appear

    button2 = Button(label="Catch Message", style=ButtonStyle.blurple)
    button2.callback = ask_catch

    view = View(timeout=VIEW_TIMEOUT)
    view.add_item(button1)
    view.add_item(button2)

    await message.response.send_message(embed=embed, view=view)


@bot.tree.command(description="Get ID of a thing")
async def getid(message: discord.Interaction, thing: discord.User | discord.Role):
    await message.response.send_message(f"The ID of {thing.mention} is {thing.id}\nyou can use it in /changemessage like this: `{thing.mention}`")


@bot.tree.command(description="(ADMIN) tune various cat bot things")
@discord.app_commands.default_permissions(manage_guild=True)
async def settings(message: discord.Interaction):
    assert message.guild is not None
    server = await Server.get_or_create(server_id=message.guild.id)

    async def toggle_parameter(interaction: discord.Interaction) -> None:
        if not interaction.custom_id or interaction.user != message.user:
            await do_funny(interaction)
            return
        parameter = interaction.custom_id
        server[parameter] = not server[parameter]
        await server.save()
        await interaction.response.edit_message(view=await settings_view())

    async def settings_view() -> LayoutView:
        assert message.guild is not None
        await server.refresh_from_db()

        def make_section(key, title, description):
            if server[key]:
                suffix = "(✅ On)"
                button = Button(label="Disable", style=ButtonStyle.red, custom_id=key)
            else:
                suffix = "(❌ Off)"
                button = Button(label="Enable", style=ButtonStyle.green, custom_id=key)
            button.callback = toggle_parameter
            return Section(f"### {title} {suffix}\n{description}", button)

        view = LayoutView(timeout=VIEW_TIMEOUT)
        view.add_item(
            Container(
                f"## Cat Bot Settings for {message.guild.name}",
                make_section(
                    "only_setupped_channels",
                    "Only in Setupped Channels",
                    "If enabled, mutes reactions, responses, achievements and cattlepass progress outside of setupped channels",
                ),
                make_section("do_reactions", "Reactions", "Controls all Cat Bot reactions"),
                make_section("do_responses", "Responses", "Controls Cat Bot easter egg responses to specific messages sent"),
                make_section("mute_achievements", "Mute Achievements", "If enabled, will hide all Cat Bot 'achievement get' messages"),
                make_section("auto_delete_achievements", "Auto-Delete Achievements", "If enabled, will delete all 'achievement get' messages after 10 seconds"),
                make_section("auto_delete_catches", "Auto-Delete Catches", "If enabled, will delete all 'user caught' messages after ~10 seconds"),
                make_section("do_rain", "Cat Rains", "Controls whether Cat Rains can happen"),
                make_section("do_catnip", "Catnip", "Controls whether catnip is accessible"),
                make_section(
                    "anti_double_catch", "Anti-Double Catch", "If enabled, users must wait 5 minutes after catching in one channel to catch in another"
                ),
                make_section("legacy_catching", "Legacy Catching", "If enabled, reverts to old catching (first catcher only, no bonus cats)"),
            )
        )
        return view

    await message.response.send_message(view=await settings_view())


@bot.tree.command(description="Get Daily cats")
async def daily(message: discord.Interaction):
    await message.response.send_message("there is no daily cats why did you even try this")
    await achemb(message, "daily", "followup")


@bot.tree.command(description="View when the last cat was caught in this channel, and when the next one might spawn")
async def last(message: discord.Interaction):
    assert isinstance(message.channel, GuildMessageable)
    channel = await Channel.get_or_none(channel_id=message.channel.id)
    nextpossible = ""

    try:
        assert channel is not None
        lasttime = channel.lastcatches
        if int(lasttime) == 0:
            displayedtime = "forever ago"
        else:
            displayedtime = f"<t:{int(lasttime)}:R>"

        if not channel.cat:
            times = [channel.spawn_times_min, channel.spawn_times_max]
            nextpossible = f"\nthe next cat will spawn between <t:{int(lasttime) + times[0]}:R> and <t:{int(lasttime) + times[1]}:R>"
    except Exception:
        displayedtime = "forever ago"

    if channel and channel.cat_rains:
        nextpossible += f"\ncat rain! {channel.cat_rains} {plural('cat', channel.cat_rains)} remaining..."

    await message.response.send_message(f"the last cat in this channel was caught {displayedtime}.{nextpossible}")


@bot.tree.command(description="View all the juicy numbers and info behind cat types")
async def catalogue(message: discord.Interaction):
    assert message.guild is not None
    embed = discord.Embed(title=f"{get_emoji('staring_cat')} The Catalogue", color=Colors.brown)
    for cat_type in cattypes:
        in_server = await Profile.sum(f"cat_{cat_type}", f'guild_id = $1 AND "cat_{cat_type}" > 0', message.guild.id)
        title = f"{get_emoji(cat_type.lower() + 'cat')} {cat_type}"
        if in_server == 0 or not in_server:
            in_server = 0
            title = f"{get_emoji('mysterycat')} ???"

        title += f" ({round((data.type_dict[cat_type] / TOTAL_CAT_WEIGHT) * 100, 2)}%)"

        embed.add_field(
            name=title,
            value=f"{round(CAT_VALUES[cat_type], 2)} value\n{in_server:,} in this server",
        )

    await message.response.send_message(embed=embed)


async def gen_stats(profile: Profile, star: str) -> list[list[str]]:
    stats = []
    user = await User.get_or_create(user_id=profile.user_id)

    # catching
    stats.append([get_emoji("staring_cat"), "Catching"])
    stats.append(["catches", "🐈", f"Catches: {profile.total_catches:,}{star}"])
    catch_time = "---" if profile.time >= 99999999999999 else round(profile.time, 3)
    slow_time = "---" if profile.timeslow == 0 else round(profile.timeslow / 3600, 2)
    stats.append(["time_records", "⏱️", f"Fastest: {catch_time}s, Slowest: {slow_time}h"])
    if profile.total_catches - profile.rain_participations != 0:
        stats.append(
            ["average_time", "⏱️", f"Average catch time: {profile.total_catch_time / (profile.total_catches - profile.rain_participations):,.2f}s{star}"]
        )
    else:
        stats.append(["average_time", "⏱️", f"Average catch time: N/A{star}"])
    stats.append(["purrfect_catches", "✨", f"Purrfect catches: {profile.perfection_count:,}{star}"])
    stats.append(["bonus_catches", "🎁", f"Successful bonus catches: {profile.bonus_catches:,}{star}"])

    # catching boosts
    stats.append([get_emoji("prism"), "Prisms & Catnip"])
    prisms_crafted = await Prism.count("guild_id = $1 AND user_id = $2", profile.guild_id, profile.user_id)
    boosts_done = await Prism.sum("catches_boosted", "guild_id = $1 AND user_id = $2", profile.guild_id, profile.user_id)
    stats.append(["prism_crafted", get_emoji("prism"), f"Prisms crafted: {prisms_crafted:,}"])
    stats.append(["boosts_done", get_emoji("prism"), f"Boosts by owned prisms: {boosts_done:,}{star}"])
    stats.append(["boosted_catches", get_emoji("prism"), f"Prism-boosted catches: {profile.boosted_catches:,}{star}"])
    stats.append(["catnip_activations", get_emoji("catnip"), f"Cats gained from catnip: {profile.catnip_activations:,}"])
    stats.append(["catnip_bought", get_emoji("catnip"), f"Catnip levels reached: {profile.catnip_bought:,}"])
    stats.append(["highest_catnip_level", "⬆️", f"Highest catnip level: {profile.highest_catnip_level:,}"])
    stats.append(["bounties_complete", "🎯", f"Mafia bounties completed: {profile.bounties_complete:,}"])

    # battlepass
    stats.append(["⬆️", "Cattlepass & Voting"])
    stats.append(["total_votes", get_emoji("topgg"), f"Total votes: {user.total_votes:,}{star}"])
    stats.append(["current_vote_streak", "🔥", f"Current vote streak: {user.vote_streak} (max {max(user.vote_streak, user.max_vote_streak):,}){star}"])
    seasons_complete = 0
    levels_complete = 0
    max_level = 0
    total_xp = 0
    # past seasons
    for season in profile.bp_history.split(";"):
        if not season:
            break
        season_num, season_lvl, season_progress = map(int, season.split(","))
        if season_num == 0:
            continue
        levels_complete += season_lvl
        total_xp += season_progress
        if season_lvl > 30:
            seasons_complete += 1
            extra_xp = 1500 if season_num <= 18 else 2000
            total_xp += extra_xp * (season_lvl - 31)
        max_level = max(max_level, season_lvl)

        for num, level in enumerate(config.battle["seasons"][str(season_num)]):
            if num >= season_lvl:
                break
            total_xp += level["xp"]
    # current season
    if profile.season != 0:
        levels_complete += profile.battlepass
        total_xp += profile.progress
        if profile.battlepass > 30:
            seasons_complete += 1
            extra_xp = 1500 if profile.season <= 18 else 2000
            total_xp += extra_xp * (profile.battlepass - 31)
        max_level = max(max_level, profile.battlepass)

        for num, level in enumerate(config.battle["seasons"][str(profile.season)]):
            if num >= profile.battlepass:
                break
            total_xp += level["xp"]
    current_packs = 0
    for pack in data.pack_data:
        current_packs += profile[f"pack_{pack['name'].lower()}"]
    stats.append(["quests_completed", "✅", f"Quests completed: {profile.quests_completed:,}{star}"])
    stats.append(["seasons_completed", "🏅", f"Cattlepass seasons completed: {seasons_complete:,}"])
    stats.append(["levels_completed", "✅", f"Cattlepass levels completed: {levels_complete:,}"])
    stats.append(["packs_in_inventory", get_emoji("woodenpack"), f"Packs in inventory: {current_packs:,}"])
    stats.append(["packs_opened", get_emoji("goldpack"), f"Packs opened: {profile.packs_opened:,}"])
    stats.append(["pack_upgrades", get_emoji("diamondpack"), f"Pack upgrades: {profile.pack_upgrades:,}"])
    stats.append(["highest_ever_level", "🏆", f"Highest ever Cattlepass level: {max_level:,}"])
    stats.append(["total_xp_earned", "🧮", f"Total Cattlepass XP earned: {total_xp:,}"])

    # rains & supporter
    stats.append(["☔", "Rains & Blessings"])
    stats.append(["current_rain_minutes", "☔", f"Current rain minutes: {user.rain_minutes:,}"])
    stats.append(["rain_minutes_bought", "☔", f"Rain minutes bought: {user.rain_minutes_bought:,}"])
    stats.append(["cats_caught_during_rains", "☔", f"Cats caught during rains: {profile.rain_participations:,}{star}"])
    stats.append(["rain_minutes_started", "☔", f"Rain minutes started: {profile.rain_minutes_started:,}{star}"])
    stats.append(["cats_blessed", "🌠", f"Cats blessed: {user.cats_blessed:,}"])

    # misc
    if profile.rarest_fish.strip():
        rarest_fish = f"{get_emoji(profile.rarest_fish.lower() + 'fish')} {profile.rarest_fish}"
    else:
        rarest_fish = "N/A"
    stats.append(["❓", "Misc"])
    portfolio_value, _ = await compute_portfolio(profile)
    if profile.ttt_played != 0:
        stats.append(
            ["ttc_win_rate", "⭕", f"Tic Tac Toe wins: {profile.ttt_won:,} (winrate: {(profile.ttt_won + profile.ttt_draws) / profile.ttt_played * 100:.2f}%)"]
        )
    else:
        stats.append(["ttc_win_rate", "⭕", "Tic Tac Toe wins: 0 (winrate: 0%)"])
    stats.append(["casino_spins", "🎰", f"Casino spins: {profile.gambles:,}"])
    stats.append(["slot_spins", "🎰", f"Slot spins: {profile.slot_spins:,}, wins: {profile.slot_wins:,}, big wins: {profile.slot_big_wins:,}"])
    stats.append(["roulette_spins", "💰", f"Roulette spins: {profile.roulette_spins:,}, wins: {profile.roulette_wins:,}"])
    stats.append(["portfolio_value", "🪙", f"Portfolio value: {int(portfolio_value):,}"])
    stats.append(["cookies", "🍪", f"Cookies clicked: {profile.cookies:,}"])
    stats.append(["catfishing", "🎣", f"Fish caught: {profile.fish_caught:,}, rarest: {rarest_fish}"])
    stats.append(["pig_high_score", "🎲", f"Pig high score: {profile.best_pig_score:,}"])
    stats.append(["cats_gifted", "🎁", f"Cats gifted: {profile.cats_gifted:,}{star}"])
    stats.append(["cats_received_as_gift", "🎁", f"Cats received as gift: {profile.cat_gifts_recieved:,}{star}"])
    stats.append(["trades_completed", "💱", f"Trades completed: {profile.trades_completed}{star}"])
    stats.append(["cats_traded", "💱", f"Cats traded: {profile.cats_traded:,}{star}"])
    if profile.user_id == 553093932012011520:
        stats.append(["owner", get_emoji("neocat"), "a cute catgirl :3"])
    return stats


@bot.tree.command(name="stats", description="View some advanced stats")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="Person to view the stats of!")
async def stats_command(message: discord.Interaction, person_id: discord.User | discord.Member | None = None):
    if not person_id:
        person_id = message.user
    assert message.guild is not None
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    star = "*" if not profile.new_user else ""

    stats = await gen_stats(profile, star)
    embedVar = discord.Embed(
        title=f"{person_id.name}'s Stats",
        color=Colors.brown,
    )

    current_category = None
    current_lines = []

    for stat in stats:
        if len(stat) == 2:
            # remove prev cat
            if current_category:
                embedVar.add_field(name=current_category, value="\n".join(current_lines), inline=True)

            # start new cat
            current_category = f"{stat[0]} {stat[1]}"
            current_lines = []

        elif len(stat) == 3:
            current_lines.append(stat[2])

    # add last cat
    if current_category:
        embedVar.add_field(name=current_category, value="\n".join(current_lines), inline=True)

    if star:
        embedVar.set_footer(text="* this stat is only tracked since February 2025")
    if person_id == bot.user:
        embedVar.set_footer(text="dont believe the lies i every stat maxxed")

    await message.response.send_message(embed=embedVar)


async def gen_inventory(
    guild_id: int, inv_user: discord.abc.User | discord.Object, me_msg: discord.Interaction | None = None
) -> tuple[discord.ui.Container, list[str]]:
    person = await Profile.get_or_create(guild_id=guild_id, user_id=inv_user.id)
    user = await User.get_or_create(user_id=inv_user.id)

    # around here we count aches
    unlocked, minus_achs, minus_achs_count = count_achievements(person)
    total_achs = len(ach_list) - minus_achs_count
    minus_achs = "" if minus_achs == 0 else f" + {minus_achs}"

    def prism_short_name(name):
        if " " not in name:
            return name
        parts = name.split(" ")
        second_part = data.prism_names_end.index(" " + parts[-1]) + 1
        return f"{parts[0]} {second_part}"

    # count prism stuff
    prisms = await Prism.collect_limit(["name"], "guild_id = $1 AND user_id = $2", guild_id, inv_user.id)
    total_count = await Prism.count("guild_id = $1", guild_id)
    user_count = len(prisms)
    global_boost = 0.06 * math.log(2 * total_count + 1)
    prism_boost = round((global_boost + 0.05 * math.log(2 * user_count + 1)) * 100, 3)
    if len(prisms) == 0:
        prism_list = "No Prisms"
    elif len(prisms) == 1:
        prism_list = f"1 Prism: {prisms[0].name}"
    else:
        prism_list = f"{len(prisms)} Prisms: {prism_short_name(prisms[0].name)}, {prism_short_name(prisms[1].name)}" + ("..." if len(prisms) > 2 else "")

    emoji_prefix = str(user.emoji) + " " if user.emoji else ""

    if user.color:
        color = user.color
    else:
        color = "#6E593C"

    await refresh_quests(person)
    try:
        needed_xp = config.battle["seasons"][str(person.season)][person.battlepass]["xp"]
    except Exception:
        needed_xp = 2000

    stats = await gen_stats(person, "")
    highlighted_stat = None
    for stat in stats:
        if stat[0] == person.highlighted_stat:
            highlighted_stat = stat
            break
    if not highlighted_stat:
        for stat in stats:
            if stat[0] == "time_records":
                highlighted_stat = stat
                break
    if inv_user == bot.user:
        highlighted_stat = ["style_points", "😎", "Style points: 1000"]
    assert highlighted_stat is not None

    debt = False
    give_collector = True
    total = 0
    valuenum = 0

    # for every cat
    cat_elements = []
    for i in cattypes:
        icon = get_aura_emoji(i, person.cat_auras)
        cat_num = person[f"cat_{i}"]
        if cat_num <= 0:
            give_collector = False
            if cat_num < 0:
                debt = True
        else:
            total += cat_num
            valuenum += CAT_VALUES[i] * cat_num
            cat_elements.append(f"{icon} **{i}** {cat_num:,}")

    if user.custom and hasattr(inv_user, "name"):
        icon = get_emoji(str(user.user_id) + "cat")
        cat_elements.append(f"{icon} **{user.custom}** {user.custom_num:,}")

    if len(cat_elements) == 0:
        cat_desc = f"u hav no cats {get_emoji('cat_cry')}"
    elif len(cat_elements) <= 10 or not person.compact_inventory:
        cat_desc = "\n".join(cat_elements)
    else:
        cat_desc = ""
        mid = (len(cat_elements) + 1) // 2
        odds, evens = cat_elements[:mid], cat_elements[mid:]

        def closest_sum(increase):
            shift_values = {"　": 32, " ": 18, " ": 16, " ": 10, " ": 8, " ": 7, " ": 6, " ": 5, " ": 2}
            nums = list(shift_values.values())
            num_to_key = {v: k for k, v in shift_values.items()}

            dp: dict[int, tuple[int, int | None, int | None]] = {0: (0, None, None)}

            for s in range(1, 1000):
                best = None
                for n in nums:
                    prev = s - n
                    if prev in dp:
                        count = dp[prev][0] + 1
                        if best is None or count < best[0]:
                            best = (count, prev, n)
                if best is not None:
                    dp[s] = best

            best_sum = None
            best_dist = None
            best_count = None

            for s, (count, _, _) in dp.items():
                dist = abs(s - increase)
                if best_sum is None or dist < best_dist or (dist == best_dist and best_count is not None and count < best_count):
                    best_sum = s
                    best_dist = dist
                    best_count = count

            used_keys = []
            s = best_sum
            while s != 0 and s is not None:
                _, prev, n = dp[s]
                assert n is not None
                used_keys.append(num_to_key[n])
                s = prev

            return "".join(used_keys)

        def markdown_width(text: str) -> int:
            return sum(msg2img._measure(chunk, msg2img.body_fonts[style]) for style, chunk in msg2img._parse_markdown(text))

        lens = {i: markdown_width(i) for i in odds}
        goal = max(lens.values()) + 50
        for idx, elem in enumerate(odds):
            try:
                even = evens[idx]
            except IndexError:
                cat_desc += "\n" + elem
                break
            cat_desc += "\n" + elem + closest_sum(goal - lens[elem]) + even

    if me_msg and (len(data.news_list) > len(user.news_state.strip()) or user.news_state.strip()[last_active_article] == "0"):
        has_news = "You have unread news! /news"
    else:
        has_news = None

    things = f"""{highlighted_stat[1]} {highlighted_stat[2]}
{get_emoji("ach")} Achievements: {unlocked}/{total_achs}{minus_achs}
⬆️ Cattlepass Level {person.battlepass} ({person.progress}/{needed_xp} XP)
{get_emoji("staring_cat")} Cats: {total:,}, Value: {round(valuenum):,}
{get_emoji("prism")} {prism_list} ({prism_boost}%)"""

    if isinstance(inv_user, discord.abc.User):
        uname = inv_user.name
    else:
        uname = "Cat Bot User"
    username = f"## {emoji_prefix}{uname.replace('_', r'\_')}"

    badges = ""
    for badge in data.badge_list:
        if user[badge]:
            badges += f"{get_emoji(badge)} "

    if not badges:
        badges = None
    else:
        badges = f"### {badges}"

    if user.image.startswith("https://cdn.discordapp.com/attachments/") and isinstance(inv_user, discord.abc.User):
        embedVar = Container(
            has_news,
            Section(username, badges, things, Thumbnail(user.image)),
            cat_desc,
            accent_color=discord.Colour.from_str(color),
        )
    else:
        embedVar = Container(
            has_news,
            username,
            badges,
            things,
            cat_desc,
            accent_color=discord.Colour.from_str(color),
        )

    give_achs: list[str] = []
    if me_msg:
        # give some aches if we are vieweing our own inventory
        if give_collector:
            give_achs.append("collecter")

        if person.time <= 5:
            give_achs.append("fast_catcher")
        if person.timeslow >= 3600:
            give_achs.append("slow_catcher")

        if total >= 100:
            give_achs.append("second")
        if total >= 1000:
            give_achs.append("third")
        if total >= 10000:
            give_achs.append("fourth")

        if unlocked >= 15:
            give_achs.append("achiever")

        if debt:
            bot.loop.create_task(debt_cutscene(me_msg, person))

    return embedVar, give_achs


@bot.tree.command(description="View your inventory")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="Person to view the inventory of!")
async def inventory(message: discord.Interaction, person_id: discord.User | discord.Member | None = None):
    assert message.guild is not None
    if not person_id:
        person_id = message.user
    person = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    user = await User.get_or_create(user_id=message.user.id)
    view_user = await User.get_or_create(user_id=person_id.id)
    stats = await gen_stats(person, "")

    async def confirm_report(interaction: discord.Interaction) -> None:
        try:
            ch = bot.get_partial_messageable(config.REPORT_CHANNEL_ID)
            await ch.send(f"⚠️ {person_id.id} has been reported.")
        except Exception:
            pass
        await interaction.response.edit_message(content="Thanks for your report.", view=None)

    async def report_profile(interaction: discord.Interaction) -> None:
        assert bot.user is not None
        if person_id.id == bot.user.id:
            await interaction.response.send_message("do you really hate me that much", ephemeral=True)
            return
        view = View(timeout=VIEW_TIMEOUT)
        btn = Button(label="Confirm Report")
        btn.callback = confirm_report
        view.add_item(btn)
        await interaction.response.send_message(
            f"⚠️ Are you sure you want to report {person_id} for having an inappropriate inventory image / custom cat?", view=view, ephemeral=True
        )

    async def edit_profile(interaction: discord.Interaction) -> None:
        if interaction.user.id != person_id.id:
            await do_funny(interaction)
            return

        def stat_select(category) -> discord.ui.Select:
            options = [discord.SelectOption(emoji="⬅️", label="Back", value="back")]
            track = False
            for stat in stats:
                if len(stat) == 2:
                    track = bool(stat[1] == category)
                if len(stat) == 3 and track:
                    options.append(discord.SelectOption(value=stat[0], emoji=stat[1], label=stat[2]))

            select = discord.ui.Select(placeholder="Edit highlighted stat... (2/2)", options=options)

            async def select_callback(interaction: discord.Interaction) -> None:
                if select.values[0] == "back":
                    view = View(timeout=VIEW_TIMEOUT)
                    view.add_item(category_select())
                    await interaction.response.edit_message(view=view)
                else:
                    # update the stat
                    person.highlighted_stat = select.values[0]
                    await person.save()
                    await interaction.response.edit_message(content="Highlighted stat updated!", embed=None, view=None)

            select.callback = select_callback
            return select

        def category_select() -> discord.ui.Select:
            options = []
            for stat in stats:
                if len(stat) != 2:
                    continue
                options.append(discord.SelectOption(emoji=stat[0], label=stat[1], value=stat[1]))

            select = discord.ui.Select(placeholder="Edit highlighted stat... (1/2)", options=options)

            async def select_callback(interaction: discord.Interaction) -> None:
                view = View(timeout=VIEW_TIMEOUT)
                view.add_item(stat_select(select.values[0]))
                await interaction.response.edit_message(view=view)

            select.callback = select_callback
            return select

        async def toggle_compact_inventory(interaction: discord.Interaction) -> None:
            person.compact_inventory = not person.compact_inventory
            await person.save()
            await interaction.response.edit_message(
                content=f"Compact inventory is now {'enabled' if person.compact_inventory else 'disabled'}.", embed=None, view=None
            )

        highlighted_stat = None
        for stat in stats:
            if stat[0] == person.highlighted_stat:
                highlighted_stat = stat
                break
        if not highlighted_stat:
            for stat in stats:
                if stat[0] == "time_records":
                    highlighted_stat = stat
                    break
        assert highlighted_stat is not None

        view = View(timeout=VIEW_TIMEOUT)
        button = Button(style=discord.ButtonStyle.blurple, label="Toggle Compact Inventory")
        button.callback = toggle_compact_inventory
        view.add_item(button)
        view.add_item(category_select())

        if user.premium:
            if not user.color:
                user.color = "#6E593C"
            description = f"""👑 __Supporter Settings__
Global, change with `/editprofile`.
**Color**: {user.color.lower() if user.color.upper() not in ["", "#6E593C"] else "Default"}
**Emoji**: {user.emoji if user.emoji else "None"}
**Image**: {"Yes" if user.image.startswith("https://cdn.discordapp.com/attachments/") else "No"}

__Highlighted Stat__
{highlighted_stat[1]} {highlighted_stat[2]}

__Compact Inventory__
{"✅ True" if person.compact_inventory else "❌ False"}"""

            embed = discord.Embed(
                title=f"{(user.emoji + ' ') if user.emoji else ''}Edit Profile", description=description, color=discord.Colour.from_str(user.color)
            )
            if user.image.startswith("https://cdn.discordapp.com/attachments/"):
                embed.set_thumbnail(url=user.image)

        else:
            description = f"""👑 __Supporter Settings__
Global, buy anything from [the store](https://catbot.shop) to unlock.
👑 **Color**
👑 **Emoji**
👑 **Image**

__Highlighted Stat__
{highlighted_stat[1]} {highlighted_stat[2]}"""

            embed = discord.Embed(title="Edit Profile", description=description, color=Colors.brown)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    view = LayoutView(timeout=VIEW_TIMEOUT)

    embedVar, give_achs = await gen_inventory(message.guild.id, person_id, message if person_id == message.user else None)
    embedVar.add_item(TextDisplay(f"-# {rain_shill}"))
    view.add_item(embedVar)

    if person_id == message.user:
        btn = Button(emoji="📝", label="Edit", style=ButtonStyle.blurple)
        btn.callback = edit_profile
        view.add_item(ActionRow(btn))
    elif config.REPORT_CHANNEL_ID and (view_user.image.startswith("https://cdn.discordapp.com/attachments/") or view_user.custom):
        btn = Button(emoji="⚠️", label="Report")
        btn.callback = report_profile
        view.add_item(ActionRow(btn))

    await message.response.send_message(view=view)

    for ach in give_achs:
        await achemb(message, ach, "followup")

    if user.tutorial_state == 4:
        user.tutorial_state = 5
        await user.save()
        await message.followup.send(view=await get_tutorial_view(message.user.id), ephemeral=True)


@bot.tree.command(description="Browse inventories of completely random Cat Bot users")
async def randomizer(message: discord.Interaction):
    async def gen_random_inventory(interaction: discord.Interaction, first: bool = False) -> None:
        view = LayoutView(timeout=VIEW_TIMEOUT)

        if result := await _get_pool().fetchrow("SELECT user_id, guild_id FROM profile TABLESAMPLE BERNOULLI (1) LIMIT 1;"):
            embedVar, _ = await gen_inventory(
                result["guild_id"],
                discord.Object(result["user_id"], type=discord.User),
                None,
            )
            view.add_item(embedVar)
        else:
            view.add_item(TextDisplay("uhhh"))

        button = Button(label="Reroll", emoji="🔄", style=discord.ButtonStyle.primary)
        button.callback = gen_random_inventory
        view.add_item(ActionRow(button))

        if first:
            await interaction.response.send_message(view=view)
        else:
            await interaction.response.edit_message(view=view)

    await gen_random_inventory(message, first=True)
    await achemb(message, "randomizer2", "followup")


async def rain_recovery_loop(channel: Channel) -> None:
    log_stats("rain_start", {"cats": str(channel.cat_rains)})
    while True:
        await asyncio.sleep(5)
        await channel.refresh_from_db()
        if channel.cat_rains <= 0:
            break
        if channel.cat_rains and not channel.cat and time.time() - channel.rain_should_end > 5:
            await spawn_cat(channel.channel_id)
            channel.cat_rains -= 1
            await channel.save()


async def rain_end(message: discord.Message, channel: Channel, force_summary: dict) -> None:
    assert isinstance(message.channel, GuildMessageable)
    assert message.guild is not None
    try:
        for _ in range(3):
            await message.channel.send("# :bangbang: cat rain has ended")
            await asyncio.sleep(0.3)
    except Exception:
        pass

    lock_success = False
    unlock_info = None
    if not isinstance(message.channel, discord.Thread):
        try:
            guild = await bot.fetch_guild(message.guild.id)
            api_channel = await guild.fetch_channel(message.channel.id)

            assert not isinstance(api_channel, discord.Thread)
            me_overwrites = api_channel.overwrites_for(message.guild.me)
            me_overwrites.send_messages = True

            everyone_overwrites = api_channel.overwrites_for(guild.default_role)
            current_perm = everyone_overwrites.send_messages
            everyone_overwrites.send_messages = False

            await asyncio.gather(
                api_channel.set_permissions(guild.default_role, overwrite=everyone_overwrites),
                api_channel.set_permissions(message.guild.me, overwrite=me_overwrites),
            )

            lock_success = True
            unlock_info = (api_channel, guild.default_role, everyone_overwrites, current_perm)
        except Exception:
            pass

    def schedule_unlock(delay: float) -> None:
        if unlock_info is None:
            return
        api_channel, default_role, everyone_overwrites, current_perm = unlock_info

        async def wait_and_unlock():
            await asyncio.sleep(delay)
            everyone_overwrites.send_messages = current_perm
            await api_channel.set_permissions(default_role, overwrite=everyone_overwrites)

        bot.loop.create_task(wait_and_unlock())

    # rain summary
    try:
        if not (rain_server := force_summary):
            if channel.channel_id not in config.rain_starter or channel.channel_id not in config.cat_cought_rain:
                schedule_unlock(10)
                return
            rain_server = config.cat_cought_rain[channel.channel_id]

        pack_names = ["Wooden", "Stone", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Celestial"]
        pack_yeah = {"Wooden": 1, "Stone": 0.9, "Bronze": 0.8, "Silver": 0.7, "Gold": 0.6, "Platinum": 0.5, "Diamond": 0.4, "Celestial": 0.3}
        rain_packs = []
        rain_cats = []

        for key in rain_server:
            if key in cattypes:
                rain_cats.append(key)
            if key in pack_names:
                rain_packs.append(key)

        funny_cat_emojis = {k: get_short_emoji(k.lower() + "cat") for k in rain_cats}
        funny_pack_emojis = {k: get_short_emoji(k.lower() + "pack") for k in rain_packs}
        funny_aura_emojis = (
            {k: get_short_emoji(k.lower() + "cat_y") for k in rain_cats}
            | {k: get_short_emoji(k.lower() + "cat_c") for k in rain_packs}
            | {k: get_short_emoji(k.lower() + "cat_p") for k in rain_packs}
            | {k: get_short_emoji(k.lower() + "cat_r") for k in rain_cats}
            | {k: get_short_emoji(k.lower() + "cat_a") for k in rain_packs}
        )

        funny_emojis = funny_cat_emojis | funny_pack_emojis | funny_aura_emojis

        reverse_mapping = {}

        for thing_type, user_ids in rain_server.items():
            for user_id in user_ids:
                if user_id not in reverse_mapping:
                    reverse_mapping[user_id] = []
                reverse_mapping[user_id].append(thing_type)

        schedule_unlock(max(10, len(reverse_mapping) * 2))

        evil_types = []
        epic_fail = False
        thingtypes = cattypes + pack_names
        for cat_type in thingtypes:
            part_one = "## Rain Summary\n"

            for user_id, cat_types in sorted(reverse_mapping.items(), key=lambda item: len(item[1]), reverse=True):
                profile = await Profile.get_or_create(user_id=user_id, guild_id=message.guild.id)
                aura_suffixes = {cattypes[k]: f"_{v}" if v != " " else "" for k, v in enumerate(profile.cat_auras)}
                show_cats = ""
                shortened_types = False
                dictdict = data.type_dict | pack_yeah
                cat_types.sort(reverse=True, key=lambda x: dictdict[x])
                pack_amount = 0
                for cat_type_two in cat_types:
                    if cat_type_two in evil_types:
                        shortened_types = True
                        continue
                    if cat_type_two in pack_names:
                        pack_amount += 1
                    show_cats += funny_emojis[cat_type_two] + (aura_suffixes.get(cat_type_two, ""))
                if show_cats != "":
                    if shortened_types:
                        show_cats = ": ..." + show_cats
                    else:
                        show_cats = ": " + show_cats
                if str(config.rain_starter[channel.channel_id]) in str(user_id):
                    part_one += "☔ "
                disambig = f"({len(cat_types)})"
                if pack_amount:
                    disambig = f"({len(cat_types) - pack_amount} {get_emoji('finecat')}, {pack_amount} {get_emoji('woodenpack')})"
                part_one += f"{user_id} {disambig}{show_cats}\n"

            if not lock_success and not epic_fail:
                part_one += "-# 💡 Cat Bot will automatically lock the channel for a few seconds after a rain if you give it `Manage Permissions`"

            if len(part_one) > 4000:
                evil_types.append(cat_type)
                epic_fail = True
                continue

            parts = [part_one]

            if epic_fail:
                part_two = ""
                for cat_type in thingtypes:
                    if cat_type not in rain_server:
                        continue
                    if len(rain_server[cat_type]) > 5:
                        part_two += f"{funny_emojis[cat_type]} *{len(rain_server[cat_type])} catches*\n"
                    else:
                        part_two += f"{funny_emojis[cat_type]} {' '.join(rain_server[cat_type])}\n"

                if not lock_success:
                    part_two += "-# 💡 Cat Bot will automatically lock the channel for a few seconds after a rain if you give it `Manage Permissions`"

                parts.append(part_two)

            for rain_msg in parts:
                if ":i:" not in rain_msg:
                    continue
                # this is to bypass character limit up to 4k
                v = LayoutView()
                v.add_item(TextDisplay(rain_msg))
                try:
                    await message.channel.send(view=v)
                except Exception:
                    pass

            break

        del config.cat_cought_rain[channel.channel_id]
        del config.rain_starter[channel.channel_id]
    except discord.Forbidden:
        pass


@bot.tree.command(description="redeem plush badge")
@discord.app_commands.describe(proof="screenshot of purchase confirmation email (dont include any personal info)")
async def plushbadge(message: discord.Interaction, proof: discord.Attachment):
    if proof and proof.content_type in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
        file = await proof.to_file()
        ch = bot.get_partial_messageable(1503550891670634758)
        await ch.send(str(message.user.id), file=file)
        await message.response.send_message(
            "✅ ok. you will get the badge after the purchase is confirmed. (usually under 5 mins, up to 12 hours)", ephemeral=True
        )
    else:
        await message.response.send_message("❌ invalid image. please upload a png, jpeg, gif, or webp image.", ephemeral=True)
        return


@bot.tree.command(description="its raining cats")
async def rain(message: discord.Interaction):
    assert message.guild is not None
    user = await User.get_or_create(user_id=message.user.id)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    server = await Server.get_or_create(server_id=message.guild.id)

    if not user.rain_minutes:
        user.rain_minutes = 0
        await user.save()

    # this is the silly popup when you click the button
    class RainModal(Modal):
        def __init__(self):
            super().__init__(
                title="Start a Cat Rain!",
                timeout=VIEW_TIMEOUT,
            )

            self.input = TextInput(
                min_length=1,
                max_length=5,
                label="Duration in minutes",
                style=discord.TextStyle.short,
                required=True,
                placeholder="2",
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction) -> None:
            try:
                duration = int(self.input.value)
            except Exception:
                await interaction.response.send_message("number pls", ephemeral=True)
                return
            await do_rain(interaction, duration)

    async def do_rain(interaction: discord.Interaction, rain_length: int) -> None:
        # i LOOOOVE checks
        assert interaction.guild is not None
        assert isinstance(interaction.channel, GuildMessageable)
        user = await User.get_or_create(user_id=interaction.user.id)
        profile = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
        channel = await Channel.get_or_none(channel_id=interaction.channel.id)
        await server.refresh_from_db()

        if not user.rain_minutes:
            user.rain_minutes = 0
            await user.save()

        if not server.do_rain:
            await interaction.response.send_message("rain is disabled in this server.", ephemeral=True)
            return

        if rain_length < 1:
            await interaction.response.send_message("last time i checked weather can not change for a negative amount of time", ephemeral=True)
            return

        if rain_length > user.rain_minutes + profile.rain_minutes or user.rain_minutes < 0:
            await interaction.response.send_message(
                "you dont have enough rain! buy some more [here](<https://catbot.shop>)",
                ephemeral=True,
            )
            return

        if not channel:
            await interaction.response.send_message("please run this in a setupped channel.", ephemeral=True)
            return

        if channel.cat:
            await interaction.response.send_message("please catch the cat in this channel first.", ephemeral=True)
            return

        if channel.cat_rains > 0:
            await interaction.response.send_message("there is already a rain running!", ephemeral=True)
            return

        profile.rain_minutes_started += rain_length
        channel.cat_rains = rain_length * 22
        channel.yet_to_spawn = 0
        await channel.save()
        if profile.rain_minutes:
            if rain_length > profile.rain_minutes:
                user.rain_minutes -= rain_length - profile.rain_minutes
                profile.rain_minutes = 0
            else:
                profile.rain_minutes -= rain_length
        else:
            user.rain_minutes -= rain_length
        await user.save()
        await profile.save()
        try:
            await interaction.response.send_message(f"{rain_length:,}m cat rain was started by {interaction.user.mention}!")
            ch = bot.get_partial_messageable(config.RAIN_CHANNEL_ID)
            await ch.send(f"{interaction.user.id} started {rain_length}m rain in {interaction.channel.id} ({user.rain_minutes} left)")
        except Exception:
            pass

        config.cat_cought_rain[channel.channel_id] = {}
        config.rain_starter[channel.channel_id] = interaction.user.id
        await spawn_cat(interaction.channel.id)
        await rain_recovery_loop(channel)

    async def rain_modal(interaction: discord.Interaction) -> None:
        modal = RainModal()
        await interaction.response.send_modal(modal)

    button = Button(
        emoji="☔",
        label="Rain!" + (" (disabled by server)" if not server.do_rain else ""),
        style=ButtonStyle.blurple,
        disabled=not server.do_rain,
    )
    button.callback = rain_modal

    shopbutton = Button(emoji="🛒", label="Store", url="https://catbot.shop")

    view = View(timeout=VIEW_TIMEOUT)

    server_rains = ""
    server_minutes = profile.rain_minutes
    if server_minutes > 0:
        server_rains = f" (+**{server_minutes}** bonus {plural('minute', server_minutes)})"

    view = LayoutView(timeout=VIEW_TIMEOUT)

    embed = Container(
        "## ☔ Cat Rains",
        "Cat Rains are power-ups which spawn cats super fast for a limited amounts of time in a channel of your choice.",
        f"""You can get those by buying them at our [store](<https://catbot.shop>) or by winning them in an event.
This bot is developed by a single person so buying one would be very appreciated.
As a bonus, you will get access to {get_command_mention("editprofile")} and {get_command_mention("customcat")} commands!
- 1 Rain Minute = 22 cats
- Fastest times are not saved during rains.
- Late catching time is reduced to 1 second.
- Bonus cats are +1 instead of minigame.""",
        "===",
        f"You currently have **{user.rain_minutes:,}** {plural('minute', user.rain_minutes)} of rains!{server_rains}",
        ActionRow(button, shopbutton),
    )

    view.add_item(embed)

    await message.response.send_message(view=view)


@bot.tree.command(description="Buy Cat Rains!")
async def store(message: discord.Interaction):
    await message.response.send_message("☔ Cat rains make cats spawn instantly! Make your server active, get more cats and have fun!\n<https://catbot.shop>")


if config.DONOR_CHANNEL_ID:

    @bot.tree.command(description="(SUPPORTER) Get a cosmetic custom cat! (non-tradeable, doesn't count towards anything)")
    @discord.app_commands.describe(
        name='The name of your custom cat. ("None" to remove)',
        image="Static/animated GIF, PNG, JPEG, WEBP, AVIF below 256 KB. Static images will be auto-compressed.",
        amount="The amount of your custom cat you want.",
    )
    async def customcat(message: discord.Interaction, name: str, image: discord.Attachment | None = None, amount: int | None = None):
        global emojis
        assert message.guild is not None
        user = await User.get_or_create(user_id=message.user.id)
        if not user.premium:
            await message.response.send_message(
                "👑 This feature is supporter-only!\nBuy anything from Cat Bot Store to unlock custom cats!\n<https://catbot.shop>",
                ephemeral=True,
            )
            return

        if image and image.content_type not in ["image/png", "image/jpeg", "image/gif", "image/webp", "image/avif"]:
            await message.response.send_message("Invalid file type! Please upload a PNG, JPEG, GIF, WebP, or AVIF image.", ephemeral=True)
            return

        if name and len(name) > 20:
            await message.response.send_message("Name must be 20 characters or less.", ephemeral=True)
            return

        log_stats("custom_cat_change")

        em_name = str(user.user_id) + "cat"

        if name:
            user.custom = name if name.lower() != "none" else ""
        if amount:
            user.custom_num = amount
        if image:
            if message.user.id in customcatcooldown:
                await message.response.send_message("You can only upload a new custom cat image every 5 minutes.", ephemeral=True)
                return
            customcatcooldown.add(message.user.id)
            try:
                emojiss = {emoji.name: emoji for emoji in await bot.fetch_application_emojis()}
                if em_name in emojiss:
                    await emojiss[em_name].delete()
                data = await image.read()
                if image.content_type == "image/gif":
                    new_em = await bot.create_application_emoji(name=em_name, image=data)
                else:
                    img = Image.open(io.BytesIO(data))
                    img.thumbnail((128, 128))
                    with io.BytesIO() as image_binary:
                        img.save(image_binary, format="PNG")
                        image_binary.seek(0)
                        new_em = await bot.create_application_emoji(name=em_name, image=image_binary.getvalue())
                emojiss[em_name] = new_em
                emojis = {k: str(v) for k, v in emojiss.items()}
                try:
                    async with await anyio.open_file("config/emojis_cache.json", "w", encoding="utf-8") as f:
                        await f.write(json.dumps(emojis))
                except Exception:
                    pass
            except Exception:
                await message.response.send_message("Error creating emoji. Make sure your image is valid and below 256KB.", ephemeral=True)
                return
        await user.save()
        embedVar, _ = await gen_inventory(message.guild.id, message.user, None)
        view = LayoutView(timeout=1)
        view.add_item(TextDisplay("Success! Here is a preview:"))
        view.add_item(embedVar)
        await message.response.send_message(view=view, ephemeral=True)

    @bot.tree.command(description="(SUPPORTER) Bless random Cat Bot users with doubled cats!")
    async def bless(message: discord.Interaction):
        user = await User.get_or_create(user_id=message.user.id)
        do_edit = False

        if user.blessings_enabled and user.username != message.user.name:
            user.username = message.user.name
            await user.save()

        async def toggle_bless(interaction: discord.Interaction) -> None:
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            nonlocal do_edit, user
            do_edit = True
            await user.refresh_from_db()
            if not user.premium:
                return
            user.blessings_enabled = not user.blessings_enabled
            user.username = message.user.name
            await user.save()
            await _get_pool().execute("REFRESH MATERIALIZED VIEW CONCURRENTLY user_sums_mv;")
            await regen(interaction)

        async def toggle_anon(interaction: discord.Interaction) -> None:
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            nonlocal do_edit, user
            do_edit = True
            await user.refresh_from_db()
            user.blessings_anonymous = not user.blessings_anonymous
            await user.save()
            await regen(interaction)

        async def regen(interaction: discord.Interaction) -> None:
            if user.blessings_anonymous:
                blesser = "💫 Anonymous Supporter"
            else:
                blesser = f"{user.emoji or '💫'} {message.user.name}"

            user_bless_chance = user.rain_minutes_bought * 0.0001
            global_bless_chance = await _get_pool().fetchval("SELECT sum_blessing_minutes FROM user_sums_mv;") * 0.0001

            view = View(timeout=VIEW_TIMEOUT)
            if not user.premium:
                bbutton = Button(label="Supporter Required!", url="https://catbot.shop", emoji="👑")
            else:
                bbutton = Button(
                    emoji="🌟",
                    label=f"{'Disable' if user.blessings_enabled else 'Enable'} Blessings",
                    style=ButtonStyle.red if user.blessings_enabled else ButtonStyle.green,
                )
                bbutton.callback = toggle_bless

            view = LayoutView(timeout=VIEW_TIMEOUT)
            container = Container(
                "## :stars: Cat Blessings",
                "When enabled, random Cat Bot users will have their cats blessed by you - and their catches will be doubled! Your bless chance increases by *0.0001%* per minute of rain bought.",
                "===",
                f"Cats you blessed: **{user.cats_blessed:,}**\nYour bless chance is **{user_bless_chance:.4f}%**\nGlobal bless chance is **{global_bless_chance:.4f}%**",
                "===",
                Section(bbutton, f"Your blessings are currently **{'enabled' if user.blessings_enabled else 'disabled'}**."),
            )

            if user.premium:
                abutton = Button(
                    emoji="🕵️",
                    label=f"{'Disable' if user.blessings_anonymous else 'Enable'} Anonymity",
                    style=ButtonStyle.red if user.blessings_anonymous else ButtonStyle.green,
                )
                abutton.callback = toggle_anon

                container.add_item(Section(abutton, f"{'' if user.blessings_enabled else '*(disabled)* '}{blesser} blessed your catch and it got doubled!"))

            view.add_item(container)

            if do_edit:
                await interaction.response.edit_message(view=view)
            else:
                await interaction.response.send_message(view=view)

        await regen(message)

    @bot.tree.command(description="(SUPPORTER) Customize your profile!")
    @discord.app_commands.rename(provided_emoji="emoji")
    @discord.app_commands.describe(
        color="Color for your profile in hex form (e.g. #6E593C)",
        provided_emoji="A default Discord emoji to show near your username.",
        image="A square image to show in top-right corner of your profile.",
    )
    async def editprofile(
        message: discord.Interaction,
        color: str | None = None,
        provided_emoji: str | None = None,
        image: discord.Attachment | None = None,
    ):
        assert message.guild is not None
        if not config.DONOR_CHANNEL_ID:
            return

        user = await User.get_or_create(user_id=message.user.id)
        if not user.premium:
            await message.response.send_message(
                "👑 This feature is supporter-only!\nBuy anything from Cat Bot Store to unlock profile customization!\n<https://catbot.shop>"
            )
            return

        if provided_emoji and discord_emoji.to_discord(provided_emoji.strip(), get_all=False, put_colons=False):
            user.emoji = provided_emoji.strip()

        if color and (match := re.search(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color)):
            user.color = match.group(0)
        if image and image.content_type in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
            # reupload image
            channeley = bot.get_partial_messageable(config.DONOR_CHANNEL_ID)
            file = await image.to_file()
            if "." in file.filename:
                ext = file.filename[file.filename.rfind(".") :]
                file.filename = "i" + ext
            else:
                file.filename = "i"
            msg = await channeley.send(file=file)
            user.image = msg.attachments[0].url
        await user.save()
        embedVar, _ = await gen_inventory(message.guild.id, message.user, None)
        view = LayoutView(timeout=1)
        view.add_item(TextDisplay("Success! Here is a preview:"))
        view.add_item(embedVar)
        await message.response.send_message(view=view)


@bot.tree.command(description="bumbum's scratch off game")
async def scratch(message: discord.Interaction):
    assert message.guild is not None
    user = await Profile.get_or_create(user_id=message.user.id, guild_id=message.guild.id)

    async def scratch_callback(interaction: discord.Interaction) -> None:
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        await user.refresh_from_db()
        if user.scratchcards == 0:
            await interaction.response.send_message("You have no scratch cards!", ephemeral=True)
            return

        log_stats("scratchcard")

        opts = data.scratch_opts.copy()
        random.shuffle(opts)

        # the entire minigame is actually a lie whoopsie daisy!!!
        # this is solely so people who fall asleep midgame wont lose on rewards
        picks = opts[:10]
        winnings = ["Winnings:"]
        user.scratchcards -= 1
        for opt in set(opts):
            amount = picks.count(opt) // 2
            if amount == 0:
                continue
            emoji = get_emoji("1rain" if opt == "1m Rain" else f"{opt.lower()}pack")
            winnings.append(f"{emoji} x{amount}")
            if opt == "1m Rain":
                user.rain_minutes += amount
            else:
                user[f"pack_{opt.lower()}"] += amount
        await user.save()

        # each key has a list of indices where that item appears in picks
        positions = {}
        for i, x in enumerate(picks):
            if x not in positions:
                positions[x] = []
            positions[x].append(i)

        # this is used during minigame to determine when to reveal the pair
        pairs = {}
        for idxs in positions.values():
            for i in range(0, len(idxs) - 1, 2):
                a, b = idxs[i], idxs[i + 1]
                pairs[a] = b
                pairs[b] = a

        move_spaces = []

        async def scratch_spot(interaction: discord.Interaction) -> None:
            if not interaction.custom_id or interaction.user != message.user:
                await do_funny(interaction)
                return
            spot = int(interaction.custom_id)
            if len(move_spaces) < 10 and spot not in move_spaces:
                move_spaces.append(spot)
            await refresh_board(interaction)

        async def refresh_board(interaction: discord.Interaction) -> None:
            nonlocal move_spaces
            view = LayoutView(timeout=VIEW_TIMEOUT)
            buttons = []
            empty_idx = 10
            if len(move_spaces) > 10:
                move_spaces = move_spaces[:10]
            for i in range(25):
                if i not in move_spaces:
                    if len(move_spaces) != 10:
                        button = Button(emoji=get_emoji("empty"), custom_id=str(i), style=ButtonStyle.gray)
                        button.callback = scratch_spot
                    else:
                        item = opts[empty_idx]
                        empty_idx += 1
                        button = Button(
                            emoji=get_emoji("1rain" if item == "1m Rain" else f"{item.lower()}pack"),
                            disabled=True,
                            style=ButtonStyle.gray,
                        )
                    buttons.append(button)
                    continue
                move_number = move_spaces.index(i)
                button = Button(
                    emoji=get_emoji("1rain" if picks[move_number] == "1m Rain" else f"{picks[move_number].lower()}pack"),
                    style=ButtonStyle.green if move_number in pairs and len(move_spaces) > pairs[move_number] else ButtonStyle.blurple,
                    disabled=True,
                )
                buttons.append(button)

            view.add_item(TextDisplay(f"Clicks remaining: {10 - len(move_spaces)}" if len(move_spaces) != 10 else "\n".join(winnings)))
            for i in range(0, 25, 5):
                view.add_item(ActionRow(*buttons[i : i + 5]))

            if len(move_spaces) == 10:
                await user.refresh_from_db()
                button = Button(label=f"Scratch! ({user.scratchcards})", style=ButtonStyle.green, disabled=user.scratchcards == 0)
                button.callback = scratch_callback
                view.add_item(ActionRow(button))
            await interaction.response.edit_message(view=view)

        await refresh_board(interaction)

    view = LayoutView(timeout=VIEW_TIMEOUT)
    button = Button(label=f"Scratch! ({user.scratchcards})", style=ButtonStyle.green, disabled=user.scratchcards == 0)
    button.callback = scratch_callback
    view.add_item(
        Container(
            "## 🍀 Scratch Off",
            f"You will be able to select **10 out of 25 spots**. Finding a __pair__ will give you it's respective prize. (example: finding 2x {get_emoji('diamondpack')} will give you a Diamond pack)",
            "Get scratch cards by completing *Weekly Quests*.",
            "===",
            ActionRow(button),
        )
    )
    await message.response.send_message(view=view)


@bot.tree.command(description="View and open packs")
async def packs(message: discord.Interaction):
    assert message.guild is not None

    async def process_pack_opening(limit: int | None = None) -> discord.Embed | None:
        await user.refresh_from_db()

        pack_names = [pack["name"] for pack in data.pack_data]
        total_pack_count = sum(user[f"pack_{pack_id.lower()}"] for pack_id in pack_names)

        if total_pack_count < 1:
            return None

        real_to_open = total_pack_count
        if limit:
            real_to_open = min(limit, total_pack_count)

        display_cats = real_to_open >= 50
        results_header = []
        results_detail = []
        results_percat = {cat: 0 for cat in cattypes}
        total_upgrades = 0
        opened_so_far = 0

        for level, pack in enumerate(pack_names):
            if opened_so_far >= real_to_open:
                break
            log_stats("pack_open", {"pack": pack})
            pack_id = f"pack_{pack.lower()}"
            this_packs_count = user[pack_id]
            if this_packs_count < 1:
                continue

            opening_this = min(this_packs_count, real_to_open - opened_so_far)

            results_header.append(f"{opening_this:,}x {get_emoji(pack.lower() + 'pack')}")
            for _ in range(opening_this):
                chosen_type, cat_amount, upgrades, rewards = get_pack_rewards(level, is_single=False)
                total_upgrades += upgrades
                if not display_cats:
                    results_detail.append(rewards)
                results_percat[chosen_type] += cat_amount

            user[pack_id] -= opening_this
            opened_so_far += opening_this

        user.packs_opened += opened_so_far
        user.pack_upgrades += total_upgrades
        for cat_type, cat_amount in results_percat.items():
            user[f"cat_{cat_type}"] += cat_amount
        await user.save()

        final_header = f"Opened {opened_so_far:,} {plural('pack', opened_so_far)}!"
        pack_list = "**" + ", ".join(results_header) + "**"
        final_result = "\n".join(results_detail)

        if display_cats or len(final_result) > 4000 - len(pack_list):
            cat_summary = []
            for cat in cattypes:
                if results_percat[cat] > 0:
                    cat_summary.append(f"{get_emoji(cat.lower() + 'cat')} x{results_percat[cat]:,}")
            final_result = "\n".join(cat_summary)

        if len(final_result) > 0:
            final_result = "\n\n" + final_result

        return discord.Embed(title=final_header, description=f"{pack_list}{final_result}", color=Colors.brown)

    async def confirm_open_all(interaction: discord.Interaction) -> None:
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        async def do_it(interaction: discord.Interaction) -> None:
            await interaction.response.defer()
            await interaction.delete_original_response()
            await open_all_packs(interaction)

        confirm_view = View(timeout=VIEW_TIMEOUT)
        yes_btn = Button(label="Yes, Open All", style=ButtonStyle.green)
        yes_btn.callback = do_it
        confirm_view.add_item(yes_btn)

        await interaction.response.send_message("Are you sure you want to open ALL your packs?", view=confirm_view, ephemeral=True)

    def gen_view(user: Profile) -> tuple[View, bool]:
        view = View(timeout=VIEW_TIMEOUT)
        empty = True
        has_special = False
        total_amount = 0
        for pack in data.pack_data:
            if user[f"pack_{pack['name'].lower()}"] < 1:
                continue
            empty = False
            amount = user[f"pack_{pack['name'].lower()}"]
            total_amount += amount
            button = Button(
                emoji=get_emoji(pack["name"].lower() + "pack"),
                label=f"{pack['name']} ({amount:,})",
                style=ButtonStyle.blurple if not pack["special"] else ButtonStyle.green,
                custom_id=pack["name"],
            )
            button.callback = open_pack
            view.add_item(button)
            if pack["special"]:
                has_special = True
        if empty:
            view.add_item(Button(label="No packs left!", disabled=True))
        if total_amount > 5:
            button = Button(label=f"Open all! ({total_amount:,})", style=ButtonStyle.gray)
            button.callback = confirm_open_all
            view.add_item(button)
        return view, has_special

    def get_pack_rewards(level: int, is_single: bool = True) -> tuple[str, int, int, str | list[str]]:
        # returns cat_type, cat_amount, upgrades, verbal_output
        reward_texts: list[str] = []
        build_string = ""
        upgrades = 0
        if not is_single:
            build_string = get_emoji(data.pack_data[level]["name"].lower() + "pack")

        is_special = data.pack_data[level]["special"]
        first_boost = 1
        if is_special:
            # find first non-special level
            while data.pack_data[level + first_boost]["special"]:
                first_boost += 1

        # bump rarity
        while random.uniform(1, 100) <= data.pack_data[level]["upgrade"]:
            if is_single:
                reward_texts.append(f"{get_emoji(data.pack_data[level]['name'].lower() + 'pack')} {data.pack_data[level]['name']}\n" + build_string)
                build_string = f"Upgraded from {get_emoji(data.pack_data[level]['name'].lower() + 'pack')} {data.pack_data[level]['name']}!\n" + build_string
            else:
                build_string += f" -> {get_emoji(data.pack_data[level + first_boost]['name'].lower() + 'pack')}"
            level += first_boost
            first_boost = 1
            upgrades += 1
        final_level = data.pack_data[level]
        if is_single:
            reward_texts.append(f"{get_emoji(final_level['name'].lower() + 'pack')} {final_level['name']}\n" + build_string)

        # select cat type
        goal_value = final_level["value"]
        chosen_type = random.choice(cattypes)
        cat_emoji = get_emoji(chosen_type.lower() + "cat")
        pre_cat_amount: float = goal_value / CAT_VALUES[chosen_type]
        if pre_cat_amount % 1 > random.random():
            cat_amount = math.ceil(pre_cat_amount)
        else:
            cat_amount = math.floor(pre_cat_amount)
        if pre_cat_amount < 1:
            if is_single:
                reward_texts.append(
                    reward_texts[-1] + f"\n{round(pre_cat_amount * 100, 2)}% chance for a {get_emoji(chosen_type.lower() + 'cat')} {chosen_type} cat"
                )
                reward_texts.append(reward_texts[-1] + ".")
                reward_texts.append(reward_texts[-1] + ".")
                reward_texts.append(reward_texts[-1] + ".")
            else:
                build_string += f" {round(pre_cat_amount * 100, 2)}% {cat_emoji}? "
            if cat_amount == 1:
                # success
                if is_single:
                    reward_texts.append(reward_texts[-1] + "\n✅ Success!")
                else:
                    build_string += f"✅ -> {cat_emoji} 1"
            else:
                # fail
                if is_single:
                    reward_texts.append(reward_texts[-1] + "\n❌ Fail!")
                else:
                    build_string += f"❌ -> {get_emoji('finecat')} 1"
                chosen_type = "Fine"
                cat_amount = 1
        elif not is_single:
            build_string += f" {cat_emoji} {cat_amount:,}"
        if is_single:
            reward_texts.append(
                reward_texts[-1] + f"\nYou got {get_emoji(chosen_type.lower() + 'cat')} {cat_amount:,} {chosen_type} {plural('cat', cat_amount)}!"
            )
            return chosen_type, cat_amount, upgrades, reward_texts
        return chosen_type, cat_amount, upgrades, build_string

    async def open_pack(interaction: discord.Interaction) -> None:
        if not interaction.custom_id or interaction.user != message.user:
            await do_funny(interaction)
            return

        pack = interaction.custom_id
        await user.refresh_from_db()
        if user[f"pack_{pack.lower()}"] < 1:
            return
        level = next((i for i, p in enumerate(data.pack_data) if p["name"] == pack), 0)

        chosen_type, cat_amount, upgrades, reward_texts = get_pack_rewards(level)
        user[f"cat_{chosen_type}"] += cat_amount
        user.pack_upgrades += upgrades
        user.packs_opened += 1
        user[f"pack_{pack.lower()}"] -= 1
        await user.save()

        log_stats("pack_open", {"pack": pack})

        embed = discord.Embed(title=reward_texts[0], color=Colors.brown)
        await interaction.response.edit_message(embed=embed, view=None)
        for reward_text in reward_texts[1:]:
            await asyncio.sleep(1)
            things = reward_text.split("\n", 1)
            embed = discord.Embed(title=things[0], description=things[1], color=Colors.brown)
            await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(1)
        view, _ = gen_view(user)
        await interaction.edit_original_response(view=view)

        await global_user.refresh_from_db()
        if global_user.tutorial_state == 8:
            global_user.tutorial_state = 9
            await global_user.save()
            await interaction.followup.send(view=await get_tutorial_view(message.user.id), ephemeral=True)

    async def open_all_packs(interaction: discord.Interaction) -> None:
        if not (embed := await process_pack_opening(10000)):
            return

        await message.edit_original_response(embed=embed, view=None)
        await asyncio.sleep(1)
        view, _ = gen_view(user)
        await message.edit_original_response(view=view)

        await global_user.refresh_from_db()
        if global_user.tutorial_state == 8:
            global_user.tutorial_state = 9
            await global_user.save()
            await interaction.followup.send(view=await get_tutorial_view(message.user.id), ephemeral=True)

    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    global_user = await User.get_or_create(user_id=message.user.id)
    view, has_special = gen_view(user)
    description = "Each pack starts at one of eight tiers of increasing value - Wooden, Stone, Bronze, Silver, Gold, Platinum, Diamond, or Celestial - and can repeatedly move up tiers with a 30% chance per upgrade. This means that even a pack starting at Wooden, through successive upgrades, can reach the Celestial tier.\n[Chance Info](<https://catbot.minkos.lol/packs>)"
    if has_special:
        description += "\n\n**Special Packs** are packs highlighted in green. Their upgrade chance is 70% instead of 30% and they start below Wooden."
    description += "\n\nClick the buttons below to start opening packs!"
    embed = discord.Embed(title=f"{get_emoji('goldpack')} Packs", description=description, color=Colors.brown)
    await message.response.send_message(embed=embed, view=view)


def make_refresh_and_reminder_buttons(user, gen_main_cb, toggle_reminders_cb) -> tuple[Button, Button]:
    refresh_button = Button(emoji="🔄", label="Refresh", style=ButtonStyle.blurple)
    refresh_button.callback = gen_main_cb

    if user.reminders_enabled:
        reminder_button = Button(emoji="🔕", style=ButtonStyle.blurple)
    else:
        reminder_button = Button(label="Enable Reminders", emoji="🔔", style=ButtonStyle.green)
    reminder_button.callback = toggle_reminders_cb

    return refresh_button, reminder_button


@bot.tree.command(description="why would anyone think a cattlepass would be a good idea (bp)")
async def battlepass(message: discord.Interaction):
    assert message.guild is not None
    current_mode = ""
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    global_user = await User.get_or_create(user_id=message.user.id)

    async def toggle_reminders(interaction: discord.Interaction) -> None:
        nonlocal current_mode
        assert interaction.guild is not None
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        await user.refresh_from_db()
        if not user.reminders_enabled:
            try:
                dm_channel = await fetch_dm_channel(global_user)
                await dm_channel.send(
                    f"You have enabled reminders in {interaction.guild.name}. You can disable them in the /battlepass command in that server or by saying `disable {interaction.guild.id}` here any time."
                )
            except Exception:
                await interaction.response.send_message(
                    "Failed. Ensure you have DMs open by going to Server > Privacy Settings > Allow direct messages from server members."
                )
                return

        user.reminders_enabled = not user.reminders_enabled
        await user.save()

        view = View(timeout=VIEW_TIMEOUT)
        for button in make_refresh_and_reminder_buttons(user, gen_main, toggle_reminders):
            view.add_item(button)

        await interaction.response.edit_message(view=view)
        await interaction.followup.send(
            f"Reminders are now {'enabled' if user.reminders_enabled else 'disabled'}.",
            ephemeral=True,
        )

    async def gen_main(interaction: discord.Interaction, first: bool = False) -> None:
        nonlocal current_mode
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        current_mode = "Main"

        await refresh_quests(user)

        await global_user.refresh_from_db()
        if global_user.vote_time_topgg + 12 * 3600 > time.time():
            await progress(message, user, "vote")
            await global_user.refresh_from_db()

        await user.refresh_from_db()

        # season end
        now = discord.utils.utcnow() + datetime.timedelta(hours=4)

        if now.month == 12:
            next_month = datetime.datetime(now.year + 1, 1, 1, tzinfo=datetime.timezone.utc)
        else:
            next_month = datetime.datetime(now.year, now.month + 1, 1, tzinfo=datetime.timezone.utc)

        next_month -= datetime.timedelta(hours=4)

        timestamp = int(next_month.timestamp())

        description = f"Season ends <t:{timestamp}:R>\n\n"

        # weekly
        if user.weekly_quest:
            weekly_quest = config.battle["quests"]["weekly"][user.weekly_quest]
            month_start = datetime.datetime(now.year, now.month, 1, tzinfo=datetime.timezone.utc) - datetime.timedelta(hours=4)
            description += f"__Weekly Quest__ (refreshes <t:{weekly_quest['end_time'] + int(month_start.timestamp())}:R>)\n"
            if weekly_quest["progress"] > user.weekly_progress:
                title = weekly_quest["title"]
                if user.weekly_quest == "bonus":
                    title = "Complete 4 [bonus minigames](https://catbot.wiki/cat-types#bonus-cats)"
                description += f"{get_emoji(weekly_quest['emoji'])} {title} ({user.weekly_progress}/{weekly_quest['progress']})\n"
                if user.weekly_quest != "different":
                    colored = int(user.weekly_progress / weekly_quest["progress"] * 10)
                    description += get_emoji("staring_square") * colored + "⬛" * (10 - colored)
                else:
                    for cat_index in user.weekly_cattypes:
                        description += get_emoji(cattypes[cat_index].lower() + "cat")
                    description += "⬛" * (weekly_quest["progress"] - user.weekly_progress)
                description += "\n- Reward: 2000 XP + 1 Scratchcard\n\n"
            else:
                description += f"✅ ~~{weekly_quest['title']}~~\n\n"

        # vote
        streak_string = ""
        if global_user.vote_streak >= 5:
            streak_string = f" (🔥 {global_user.vote_streak}x streak)"
        if user.vote_cooldown != 0:
            description += f"✅ ~~Vote on Top.gg~~\n- Refreshes <t:{int(user.vote_cooldown + 12 * 3600)}:R>{streak_string}\n"
        else:
            # inform double vote xp during weekends
            is_weekend = (now - datetime.timedelta(hours=4)).weekday() >= 4

            if is_weekend:
                description += "-# *Double Vote XP During Weekends*\n"

            description += f"{get_emoji('topgg')} [Vote on Top.gg](https://top.gg/bot/966695034340663367/vote)\n"

            if is_weekend:
                description += f"- Reward: ~~{user.vote_reward}~~ **{user.vote_reward * 2}** XP"
            else:
                description += f"- Reward: {user.vote_reward} XP"

            next_streak_data = get_streak_reward(global_user.vote_streak + 1)
            if next_streak_data["reward"] and global_user.vote_time_topgg + 24 * 3600 > time.time():
                description += f" + {next_streak_data['emoji']} 1 {next_streak_data['reward'].capitalize()} pack"

            description += f"{streak_string}\n"

        # catch
        catch_quest = config.battle["quests"]["catch"][user.catch_quest]
        if user.catch_cooldown != 0:
            description += f"✅ ~~{catch_quest['title']}~~\n- Refreshes <t:{int(min(timestamp, user.catch_cooldown + 12 * 3600))}:R>\n"
        else:
            progress_string = ""
            if catch_quest["progress"] != 1:
                if user.catch_quest == "finenice":
                    try:
                        real_progress = ["need both", "need Nice", "need Fine", "done"][user.catch_progress]
                    except IndexError:
                        real_progress = "error"
                    progress_string = f" ({real_progress})"
                else:
                    progress_string = f" ({user.catch_progress}/{catch_quest['progress']})"
            description += f"{get_emoji(catch_quest['emoji'])} {catch_quest['title']}{progress_string}\n- Reward: {user.catch_reward} XP\n"

        # misc
        misc_quest = config.battle["quests"]["misc"][user.misc_quest]
        if user.misc_cooldown != 0:
            description += f"✅ ~~{misc_quest['title']}~~\n- Refreshes <t:{int(min(timestamp, user.misc_cooldown + 12 * 3600))}:R>\n\n"
        else:
            progress_string = ""
            if misc_quest["progress"] != 1:
                progress_string = f" ({user.misc_progress}/{misc_quest['progress']})"
            description += f"{get_emoji(misc_quest['emoji'])} {misc_quest['title']}{progress_string}\n- Reward: {user.misc_reward} XP\n\n"

        if user.battlepass >= len(config.battle["seasons"][str(user.season)]):
            description += f"**Extra Rewards** [{user.progress}/2000 XP]\n"
            colored = min(10, int(user.progress / 2000 * 10))
            description += get_emoji("staring_square") * colored + "⬛" * (10 - colored) + " " + get_emoji("mysterypack") + "\n\n"
        else:
            level_data = config.battle["seasons"][str(user.season)][user.battlepass]
            description += f"**Level {user.battlepass + 1}/30** [{user.progress}/{level_data['xp']} XP]\n"
            colored = int(user.progress / level_data["xp"] * 10)
            description += get_emoji("staring_square") * colored + "⬛" * (10 - colored)

            if level_data["reward"] == "Rain":
                description += f" {get_emoji(str(level_data['amount']) + 'rain')}\n\n"
            elif level_data["reward"] in cattypes:
                description += f" {level_data['amount']}x {get_emoji(level_data['reward'].lower() + 'cat')}\n\n"
            else:
                description += f" {get_emoji(level_data['reward'].lower() + 'pack')}\n\n"

        # season overview
        levels = config.battle["seasons"][str(user.season)]
        for num, level_data in enumerate(levels):
            claimed_suffix = "_claimed" if num < user.battlepass else ""
            if level_data["reward"] == "Rain":
                description += get_emoji(str(level_data["amount"]) + "rain" + claimed_suffix)
            elif level_data["reward"] in cattypes:
                description += get_emoji(level_data["reward"].lower() + "cat" + claimed_suffix)
            else:
                description += get_emoji(level_data["reward"].lower() + "pack" + claimed_suffix)
            if num % 10 == 9:
                description += "\n"
        description += f"*Then:* {get_emoji('mysterypack')} Mystery per 2000 XP"

        embedVar = discord.Embed(
            title=f"Cattlepass Season {user.season}",
            description=description,
            color=Colors.brown,
        ).set_footer(text=rain_shill)
        view = View(timeout=VIEW_TIMEOUT)
        for button in make_refresh_and_reminder_buttons(user, gen_main, toggle_reminders):
            view.add_item(button)

        if len(data.news_list) > len(global_user.news_state.strip()) or global_user.news_state.strip()[last_active_article] == "0":
            embedVar.set_author(name="You have unread news! /news")

        if first:
            await interaction.response.send_message(embed=embedVar, view=view)
        else:
            await interaction.response.edit_message(embed=embedVar, view=view)

    await gen_main(message, True)

    if global_user.tutorial_state == 7:
        global_user.tutorial_state = 8
        await global_user.save()
        await message.followup.send(view=await get_tutorial_view(message.user.id), ephemeral=True)


@bot.tree.command(description="vote for cat bot")
async def vote(message: discord.Interaction):
    view = View(timeout=1)
    button = Button(label="Vote!", url="https://top.gg/bot/966695034340663367/vote", emoji=get_emoji("topgg"))
    view.add_item(button)
    await message.response.send_message(view=view)


async def stock_help(interaction: discord.Interaction):
    text = """Let's break this down!

At the top is the name of the stock. Each stock has a 4 letter "ticker" its identified by.
This is also where the reward will be displayed if there is one upcoming, more on them a bit later.

Below that is the price graph over the last 3 days.

When you choose Buy or Sell, enter the quantity and pick an execution method:

- **Instant** executes immediately, but costs a bit more.
- **Wait** reserves your coins or shares and finishes after about 30 minutes. It's possible there won't be enough liquity, in which case unused assets are refunded.
- Queued trades can be cancelled any time before they finish.

The displayed graph records the market price after completed trades."""

    view = View(timeout=VIEW_TIMEOUT)
    button = Button(label="Continue")
    button.callback = rewards_help
    view.add_item(button)
    await interaction.response.send_message(text, view=view, ephemeral=True)


async def rewards_help(interaction: discord.Interaction):
    text = """Rewards are random events which happen every days or two. You will know of when an award is about to be given out **24 hours** in advance to prepare and buy the stock if you want it.
Rewards have a *random* chance to give you a *random* amount of :coin: **coins** per *stock* you own.
For example, if the reward is "50% chance to earn :coin: 10/stock" and you have 5 of that stock, then when the time comes you will either get +50 or +0 coins added to your balance.

These rewards are global and equal for everyone, and whether you get the reward or not is also the same for everyone (if your chance failed, everyone else's did as well!)
To spice it up, sometimes the chance percentage will be randomly hidden. Be more careful when trading such a stock.
The reward can also sometimes be negative but I'm sure you don't have to worry about that :)"""
    await interaction.response.send_message(text, ephemeral=True)


async def portfolio_help(interaction: discord.Interaction):
    text = """Welcome to your portfolio!

First of all comes your combined portfolio value. This is a sum of all of your stocks priced at their current **stock price**, plus your current coin balance. You can also see your lifetime portfolio growth percentage and cancel queued trades.

Next, the portfolio value from before is broken down. You can see how much of each stock you have, how much they are worth, and how many :coin: **coins** you have left.

Queued trades are waiting for around 30 minutes. Their coins or shares are reserved and cannot be used until the trade finishes or you cancel it.

Lastly, there is your portfolio history. This is a history of completed trades, rewards, deposits, withdrawals, and cancelled queued trades."""
    await interaction.response.send_message(text, ephemeral=True)


async def view_portfolio(interaction: discord.Interaction, person: discord.Member | discord.User, refresh: bool = False, hidden: bool | None = None):
    assert interaction.guild is not None
    if hidden is None:
        hidden = False
    profile = await Profile.get_or_create(user_id=person.id, guild_id=interaction.guild.id)
    user = await User.get_or_create(user_id=person.id)

    view = LayoutView(timeout=VIEW_TIMEOUT)

    stock_value, share_strs = await compute_portfolio(profile)
    portfolio_value = profile.coins + stock_value
    share_strs = [f"🪙 {profile.coins:,}"] + share_strs

    shares_display = "\n".join(share_strs)

    open_orders = []
    async for order in Order.filter("user_id = $1", profile.id):
        reserved = f", up to 🪙 {order.price:,} reserved" if order.type_buy else ", shares reserved"
        open_orders.append(
            f"WAITING TO {'BUY' if order.type_buy else 'SELL'} {order.quantity:,}x **{order.ticker}**{reserved}, finishes <t:{order.time + 1800}:R>"
        )

    portfolio_history = []
    async for history in PortfolioHistory.filter("user_id = $1 ORDER BY time DESC LIMIT 13", profile.id):
        match history.type:
            case "d":
                portfolio_history.append(f"📥 Deposited 🪙 {history.price:,} coins <t:{history.time}:R>")
            case "w":
                portfolio_history.append(f"📤 Withdrew 🪙 {history.price:,} coins <t:{history.time}:R>")
            case "s":
                portfolio_history.append(f"🔴 Sold {history.quantity:,}x {history.ticker} at 🪙 {history.price:,}/share <t:{history.time}:R>")
            case "b":
                portfolio_history.append(f"🟢 Bought {history.quantity:,}x {history.ticker} at 🪙 {history.price:,}/share <t:{history.time}:R>")
            case "r":
                portfolio_history.append(f"⭐ Got rewarded 🪙 {history.quantity:,} by {history.ticker} <t:{history.time}:R>")
            case "c":
                portfolio_history.append(f":x: Cancelled BUY, refunded 🪙 {history.quantity:,} <t:{history.time}:R>")
            case "C":
                portfolio_history.append(f":x: Cancelled SELL, refunded {history.quantity:,}x {history.ticker} shares <t:{history.time}:R>")

    deposits = await PortfolioHistory.sum("price", "user_id = $1 AND type = $2", profile.id, "d")
    deposits -= await PortfolioHistory.sum("price", "user_id = $1 AND type = $2", profile.id, "w")

    try:
        value_diff = (portfolio_value / deposits - 1) * 100
    except ZeroDivisionError:
        value_diff = 0
    growth_emoji = "📈" if value_diff >= 0 else "📉"
    emoji_prefix = (user.emoji + " ") if user.emoji else ""

    first_lines = (f"## {emoji_prefix}{person}", f"### 🪙 {int(portfolio_value):,}", f"{growth_emoji} {value_diff:+.2f}% *(Lifetime)*")

    async def refresh_portfolio(interaction):
        await view_portfolio(interaction, person, refresh=True, hidden=False)

    help_button = Button(label="Help", style=ButtonStyle.gray, emoji="💡")
    help_button.callback = portfolio_help

    cancel_button = Button(label="Cancel orders...", style=ButtonStyle.red)
    cancel_button.callback = cancel_orders

    refresh_button = Button(label="Refresh", style=ButtonStyle.gray, emoji="🔄")
    refresh_button.callback = refresh_portfolio

    container = Container(
        Section(*first_lines, Thumbnail(user.image)) if user.image else first_lines,
        "===",
        shares_display or "No portfolio",
        "===",
        "### Queued Trades",
        "\n".join(open_orders) or "No queued trades",
        "===",
        "### Portfolio History",
        "\n".join(portfolio_history) or "No portfolio history",
        "===",
        ActionRow(refresh_button, cancel_button, help_button),
        accent_color=Colors.brown if not user.color else discord.Colour.from_str(user.color),
    )

    view.add_item(container)
    if not refresh:
        await interaction.response.send_message(view=view, ephemeral=hidden)
    else:
        await interaction.response.edit_message(view=view)

    if not profile.rugpulled and await PortfolioHistory.count("user_id = $1 AND type = $2 AND quantity < 0", profile.id, "r") > 0:
        await achemb(interaction, "rugpulled", "followup", person)


@bot.tree.command(description="View your stock portfolio")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="Person to view the inventory of!", hidden="Whether the response will only be seen by you.")
async def portfolio(message: discord.Interaction, person_id: discord.User | discord.Member | None, hidden: bool | None):
    if not person_id:
        person_id = message.user
    if not hidden:
        hidden = False
    await view_portfolio(message, person_id, refresh=False, hidden=hidden)


async def cancel_orders(interaction):
    profile = await Profile.get_or_create(user_id=interaction.user.id, guild_id=interaction.guild.id)
    view = View(timeout=VIEW_TIMEOUT)
    queued_orders = []
    async for order in Order.filter("user_id = $1", profile.id):
        queued_orders.append(discord.SelectOption(label=f"WAITING TO {'BUY' if order.type_buy else 'SELL'} {order.quantity:,}x {order.ticker}", value=order.id))
    if not queued_orders:
        await interaction.response.send_message("No queued orders", ephemeral=True)
        return
    view.add_item(Select("cancel_order_dd", placeholder="Select queued orders to cancel", options=queued_orders, on_select=the_order_canceller))
    await interaction.response.send_message("Select queued orders to cancel...", view=view, ephemeral=True)


async def the_order_canceller(interaction, choices):
    if not choices:
        await interaction.response.send_message("No orders selected", ephemeral=True)
        return
    profile = await Profile.get_or_create(user_id=interaction.user.id, guild_id=interaction.guild.id)
    if not isinstance(choices, list):
        choices = [choices]
    for choice in choices:
        async with transaction() as conn:
            order = await conn.fetchrow('SELECT * FROM "order" WHERE id = $1 FOR UPDATE', int(choice))
            if not order or order["user_id"] != profile.id:
                continue
            stock_column = f'"stock_{order["ticker"].lower()}"'
            if order["type_buy"]:
                await conn.execute("UPDATE profile SET coins = coins + $1 WHERE id = $2", order["price"], profile.id)
                await PortfolioHistory.create(connection=conn, user_id=profile.id, type="c", quantity=order["price"], time=int(time.time()))
            else:
                await conn.execute(f"UPDATE profile SET {stock_column} = {stock_column} + $1 WHERE id = $2", order["quantity"], profile.id)
                await PortfolioHistory.create(
                    connection=conn, user_id=profile.id, type="C", quantity=order["quantity"], time=int(time.time()), ticker=order["ticker"]
                )
            await conn.execute('DELETE FROM "order" WHERE id = $1', order["id"])
    await interaction.response.edit_message(content="Queued orders cancelled and reserved assets refunded!", view=None)


def max_queued_quantity(market, quantity: int, buy: bool, escrow: int) -> int:
    upper = min(quantity, market["share_reserve"]) if buy else quantity
    if not buy:
        upper = min(upper, quantity)
    low = 0
    while low < upper:
        middle = (low + upper + 1) // 2
        total, _, _ = market_quote(market, middle, buy, QUEUED_SPREAD)
        affordable = total <= escrow if buy else total <= market["coin_reserve"]
        if affordable:
            low = middle
        else:
            upper = middle - 1
    return low


async def settle_queued_orders() -> None:
    cutoff = int(time.time()) - 1800
    order_ids = await _get_pool().fetch('SELECT id FROM "order" WHERE time <= $1 ORDER BY time ASC LIMIT 250', cutoff)
    for id_row in order_ids:
        async with transaction() as conn:
            order = await conn.fetchrow('SELECT * FROM "order" WHERE id = $1 FOR UPDATE', id_row["id"])
            if order is None:
                continue
            market = await locked_market(order["ticker"], conn)
            if quantity := max_queued_quantity(market, order["quantity"], order["type_buy"], order["price"]):
                try:
                    await execute_market_trade(
                        conn, order["user_id"], order["ticker"], quantity, order["type_buy"], QUEUED_SPREAD, order["price"] if order["type_buy"] else 1
                    )
                except ValueError:
                    quantity = 0
            if order["type_buy"] and quantity == 0:
                await conn.execute("UPDATE profile SET coins = coins + $1 WHERE id = $2", order["price"], order["user_id"])
            elif not order["type_buy"] and quantity < order["quantity"]:
                stock_column = f'"stock_{order["ticker"].lower()}"'
                await conn.execute(f"UPDATE profile SET {stock_column} = {stock_column} + $1 WHERE id = $2", order["quantity"] - quantity, order["user_id"])
            await conn.execute('DELETE FROM "order" WHERE id = $1', order["id"])


@bot.tree.command(description="the stonk market")
async def stocks(message: discord.Interaction):
    assert message.guild is not None
    profile = await Profile.get_or_create(user_id=message.user.id, guild_id=message.guild.id)
    profile.last_ran_stocks = int(time.time())
    await profile.save()

    if not profile.bp_history.strip().replace("0,0,0;", ""):
        await message.response.send_message("your profile needs to be older than 1 cattlepass season to use this feature.", ephemeral=True)
        return

    async def deposit_pack(interaction):
        await profile.refresh_from_db()
        pack_name = interaction.custom_id
        assert pack_name is not None
        if pack_name not in ["Wooden", "Stone", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Celestial"]:
            return
        if profile[f"pack_{pack_name.lower()}"] < 1:
            await interaction.response.send_message("u dont have any packs of such type", ephemeral=True)
            return
        profile[f"pack_{pack_name.lower()}"] -= 1
        og = profile.coins
        for pack in data.pack_data:
            if pack["name"].lower() == pack_name.lower():
                profile.coins += pack["totalvalue"]
                break
        await profile.save()
        embedVar = discord.Embed(title="📥 Deposit Packs", description=f"You currently have 🪙 **{profile.coins:,}** coins.", color=Colors.brown)
        await interaction.response.edit_message(embed=embedVar, view=deposit_msg(profile))
        await PortfolioHistory.create(user_id=profile.id, time=int(time.time()), type="d", price=profile.coins - og)

    async def deposit(interaction):
        await profile.refresh_from_db()
        profile.seen_deposit = True
        embedVar = discord.Embed(title="📥 Deposit Packs", description=f"You currently have 🪙 **{profile.coins:,}** coins.", color=Colors.brown)
        await interaction.response.send_message(embed=embedVar, view=deposit_msg(profile), ephemeral=True)
        await profile.save()

    def deposit_msg(profile):
        view = View(timeout=VIEW_TIMEOUT)
        empty = True
        for pack in data.pack_data:
            if pack["name"] not in ["Wooden", "Stone", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Celestial"]:
                continue
            if profile[f"pack_{pack['name'].lower()}"] < 1:
                continue
            empty = False
            amount = profile[f"pack_{pack['name'].lower()}"]
            button = Button(
                emoji=get_emoji(pack["name"].lower() + "pack"),
                label=f"{pack['name']} ({amount:,})",
                style=ButtonStyle.blurple,
                custom_id=pack["name"],
            )
            button.callback = deposit_pack
            view.add_item(button)
        if empty:
            view.add_item(Button(label="No packs left!", disabled=True))
        return view

    async def withdraw(interaction):
        await profile.refresh_from_db()
        embedVar = discord.Embed(
            title="📤 Withdraw Coins",
            description=f"You currently have 🪙 **{profile.coins:,}** coins.\n\nYou will get {get_emoji('stonepack')} **1 Stone Pack** for every 🪙 **100** coins you withdraw.",
            color=Colors.brown,
        )
        view = View(timeout=VIEW_TIMEOUT)
        button = Button(label="Continue")
        button.callback = send_withdrawal_modal
        view.add_item(button)
        await interaction.response.send_message(embed=embedVar, view=view, ephemeral=True)

    async def send_withdrawal_modal(interaction):
        await profile.refresh_from_db()
        max_packs = max(profile.coins // 100, 0)
        await interaction.response.send_modal(WithdrawalModal(max_packs))

    class WithdrawalModal(Modal):
        def __init__(self, max_packs):
            super().__init__(
                title="Withdraw...",
                timeout=VIEW_TIMEOUT,
            )

            self.input = TextInput(
                min_length=1,
                max_length=5,
                label=f"Stone packs to withdraw (max {max_packs})",
                style=discord.TextStyle.short,
                required=True,
                placeholder="2",
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
            try:
                packs = int(self.input.value)
                if packs <= 0:
                    raise ValueError
            except Exception:
                await interaction.response.send_message("number pls", ephemeral=True)
                return

            await profile.refresh_from_db()
            max_packs = profile.coins // 100
            max_packs = max(max_packs, 0)
            if packs > max_packs:
                await interaction.response.send_message("u dont have enough coins", ephemeral=True)
                return

            profile.coins -= packs * 100
            profile.pack_stone += packs
            await profile.save()
            await PortfolioHistory.create(user_id=profile.id, time=int(time.time()), type="w", price=packs * 100)
            await interaction.response.send_message(f"📤 You withdrew {packs} stone {plural('pack', packs)}! 🪙 -{packs * 100} coins.", ephemeral=True)

    class OrderModal(Modal):
        def __init__(
            self, ticker: str, trade_type: Literal["buy", "sell"], balance: int, max_quantity: int, instant_price: int | None, queued_price: int | None
        ):
            super().__init__(title=f"{trade_type.capitalize()}ing {ticker}")
            self.ticker = ticker
            self.trade_type = trade_type
            self.quantity = TextInput(
                label="Quantity",
                placeholder=(
                    f"Shares to sell (max {max_quantity:,})" if trade_type == "sell" else f"Shares to buy (balance: {balance:,}; max: {max_quantity:,})"
                ),
                min_length=1,
                max_length=6,
                required=True,
                style=discord.TextStyle.short,
            )
            self.execution = discord.ui.RadioGroup(
                options=[
                    discord.RadioGroupOption(
                        label=f"Instant - 🪙 ~{instant_price:,}/share" if instant_price is not None else "Instant - unavailable",
                        value="instant",
                        default=True,
                    ),
                    discord.RadioGroupOption(
                        label=f"Wait (~30 min) - 🪙 ~{queued_price:,}/share" if queued_price is not None else "Wait - unavailable",
                        value="queued",
                    ),
                ],
                id=1,
            )
            self.add_item(self.quantity)
            self.add_item(discord.ui.Label(text="Execution", description="Final prices may differ from these estimates.", component=self.execution))

        async def execute_order(self, interaction: discord.Interaction, quantity: int, mode: str):
            buy = self.trade_type == "buy"
            try:
                if mode == "instant":
                    async with transaction() as conn:
                        total, spot = await execute_market_trade(conn, profile.id, self.ticker, quantity, buy, INSTANT_SPREAD)
                    await interaction.response.send_message(
                        f"✅ Instantly {'bought' if buy else 'sold'} **{quantity:,}x {self.ticker}** for 🪙 **{total:,}** "
                        f"(average 🪙 {ceil_div(total, quantity):,}/share; new price 🪙 {spot:,}).",
                        ephemeral=True,
                    )
                elif mode == "queued":
                    if await Order.count("user_id = $1", profile.id) >= 25:
                        await interaction.response.send_message("you have too many queued orders. cancel some before placing another.", ephemeral=True)
                        return
                    async with transaction() as conn:
                        market = await locked_market(self.ticker, conn)
                        quote, _, _ = market_quote(market, quantity, buy, QUEUED_SPREAD)
                        reserved_coins = ceil_div(quote * 125, 100) if buy else 0
                        db_profile = await conn.fetchrow("SELECT * FROM profile WHERE id = $1 FOR UPDATE", profile.id)
                        assert db_profile is not None
                        stock_column = f'"stock_{self.ticker.lower()}"'
                        if buy:
                            if reserved_coins > db_profile["coins"]:
                                raise ValueError(f"Not enough coins to reserve up to {reserved_coins:,} coins")
                            await conn.execute("UPDATE profile SET coins = coins - $1 WHERE id = $2", reserved_coins, profile.id)
                        else:
                            if quantity > db_profile[f"stock_{self.ticker.lower()}"]:
                                raise ValueError("Not enough shares")
                            await conn.execute(f"UPDATE profile SET {stock_column} = {stock_column} - $1 WHERE id = $2", quantity, profile.id)
                        await Order.create(
                            connection=conn,
                            user_id=profile.id,
                            ticker=self.ticker,
                            type_buy=buy,
                            quantity=quantity,
                            price=reserved_coins,
                            time=int(time.time()),
                        )
                    reserve_text = f" Up to 🪙 **{reserved_coins:,}** has been reserved." if buy else " Your shares have been reserved."
                    await interaction.response.send_message(
                        f"⏳ Queued {'buy' if buy else 'sell'} for **{quantity:,}x {self.ticker}**. It will finish in about 30 minutes.{reserve_text}",
                        ephemeral=True,
                    )
                else:
                    raise ValueError("Choose Instant or Wait")
                await achemb(interaction, "buy_stock" if buy else "sell_stock", "followup")
            except ValueError as error:
                await interaction.response.send_message(str(error), ephemeral=True)

        async def on_submit(self, interaction: discord.Interaction):
            try:
                quantity = int(self.quantity.value)
                if quantity <= 0:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message("quantity must be a positive integer", ephemeral=True)
                return

            mode = self.execution.value
            if mode not in ("instant", "queued"):
                await interaction.response.send_message("Choose Instant or Wait", ephemeral=True)
                return

            try:
                market = await market_snapshot(self.ticker)
                quote, _, _ = market_quote(market, quantity, self.trade_type == "buy", INSTANT_SPREAD if mode == "instant" else QUEUED_SPREAD)
            except ValueError as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return

            spot = market_spot_price(market)
            average = ceil_div(quote, quantity)
            impact = abs(average / spot - 1)
            if impact < PRICE_IMPACT_WARNING:
                await self.execute_order(interaction, quantity, mode)
                return

            direction = "higher" if average > spot else "lower"
            view = View(timeout=VIEW_TIMEOUT)
            confirm = Button(label="Confirm trade", style=ButtonStyle.red)
            cancel = Button(label="Cancel", style=ButtonStyle.gray)

            async def confirm_trade(interaction: discord.Interaction):
                await self.execute_order(interaction, quantity, mode)
                await interaction.delete_original_response()

            async def cancel_trade(interaction: discord.Interaction):
                await interaction.response.edit_message(content="Trade cancelled.", view=None)

            confirm.callback = confirm_trade
            cancel.callback = cancel_trade
            view.add_item(confirm)
            view.add_item(cancel)
            await interaction.response.send_message(
                f"⚠️ **Large price impact:** current price is 🪙 **{spot:,}**/share, but this order is so large that the estimated average is 🪙 **{average:,}**/share "
                f"(**{impact:.1%} {direction}**). The final price can still change before execution. Continue?",
                view=view,
                ephemeral=True,
            )

    async def buy_stock(interaction: discord.Interaction):
        assert interaction.guild is not None
        ticker = interaction.custom_id
        assert ticker is not None
        ticker = ticker.split("_")[0]
        current_profile = await Profile.get_or_create(user_id=interaction.user.id, guild_id=interaction.guild.id)
        market = await market_snapshot(ticker)
        instant_price = market_quote(market, 1, True, INSTANT_SPREAD)[0] if market["share_reserve"] else None
        queued_price = market_quote(market, 1, True, QUEUED_SPREAD)[0] if market["share_reserve"] else None
        await interaction.response.send_modal(
            OrderModal(ticker, "buy", current_profile.coins, max_buy_quantity(market, current_profile.coins), instant_price, queued_price)
        )

    async def sell_stock(interaction: discord.Interaction):
        assert interaction.guild is not None
        ticker = interaction.custom_id
        assert ticker is not None
        ticker = ticker.split("_")[0]
        current_profile = await Profile.get_or_create(user_id=interaction.user.id, guild_id=interaction.guild.id)
        market = await market_snapshot(ticker)
        instant_price = market_quote(market, 1, False, INSTANT_SPREAD)[0]
        queued_price = market_quote(market, 1, False, QUEUED_SPREAD)[0]
        await interaction.response.send_modal(OrderModal(ticker, "sell", 0, current_profile[f"stock_{ticker.lower()}"], instant_price, queued_price))

    async def view_stock(interaction):
        view = LayoutView(timeout=VIEW_TIMEOUT)

        stock_ticker = interaction.custom_id
        stock = None
        for i in data.stock_data:
            if i["ticker"] == stock_ticker:
                stock = i
                break

        assert stock is not None

        stock_data = []
        async for i in PriceHistory.filter("ticker = $1 AND time > $2", stock_ticker, int(time.time() - 3600 * 49)):
            stock_data.append((i.time, i.price))

        buffer = await bot.loop.run_in_executor(None, graph.make_graph, stock_data, 10, 3)
        file = discord.File(fp=buffer, filename="output.png")

        reward = await Reward.get_or_create(ticker=stock["ticker"])
        reward_suffix = ""
        if reward and reward.active:
            reward_suffix = f"\n⭐ {reward.chance if not reward.chance_hidden else '???'}% to earn 🪙 {reward.amount}/stock <t:{reward.end_time}:R>"

        market = await market_snapshot(stock_ticker)

        buy_button = Button(label="Buy", style=ButtonStyle.green, custom_id=stock_ticker + "_buy")
        buy_button.callback = buy_stock
        sell_button = Button(label="Sell", style=ButtonStyle.red, custom_id=stock_ticker + "_sell")
        sell_button.callback = sell_stock

        back_button = Button(style=ButtonStyle.gray, emoji="⬅️")
        back_button.callback = go_back
        refresh_button = Button(label="Refresh", style=ButtonStyle.gray, emoji="🔄", custom_id=stock_ticker)
        refresh_button.callback = view_stock
        help_button = Button(label="Help", style=ButtonStyle.gray, emoji="💡")
        help_button.callback = stock_help

        container = Container(
            f"## {get_emoji(stock['emoji'])} {stock['name']} ({stock['ticker']}){reward_suffix}",
            "===",
            f"### Current price: 🪙 **{market_spot_price(market):,}**/share",
            discord.ui.MediaGallery(discord.MediaGalleryItem(file)),
            ActionRow(buy_button, sell_button),
            f"Reserve: {market['share_reserve']:,} shares, 🪙 {market['coin_reserve']:,}",
            "===",
            ActionRow(back_button, refresh_button, help_button),
        )

        view.add_item(container)

        await interaction.response.edit_message(view=view, attachments=[file])

    async def main_page():
        await profile.refresh_from_db()

        view = LayoutView(timeout=VIEW_TIMEOUT)

        _, share_strs = await compute_portfolio(profile)
        share_strs = [f"🪙 {profile.coins:,}"] + share_strs

        deposits = await PortfolioHistory.sum("price", "user_id = $1 AND type = $2", profile.id, "d")
        deposits -= await PortfolioHistory.sum("price", "user_id = $1 AND type = $2", profile.id, "w")

        container = Container(
            "## 📈 Stock Market",
            "Buy stocks representing Cat Bot mechanics.\nEarn rewards if they perform well!",
            "===",
        )

        for item in data.stock_data:
            button = Button(label="View", style=ButtonStyle.blurple, custom_id=item["ticker"])

            button.callback = view_stock

            price = await get_stock_price(item["ticker"])

            market = await market_snapshot(item["ticker"])

            reward = await Reward.get_or_create(ticker=item["ticker"])
            reward_suffix = ""
            if reward and reward.active:
                reward_suffix = f"\n⭐ {reward.chance if not reward.chance_hidden else '???'}% to earn 🪙 {reward.amount}/stock <t:{reward.end_time}:R>"

            container.add_item(
                Section(
                    f"### {get_emoji(item['emoji'])} {item['ticker']} - 🪙 {price:,}",
                    f"Reserve: {market['share_reserve']:,} shares, 🪙 {market['coin_reserve']:,}{reward_suffix}",
                    button,
                )
            )

        row = ActionRow()

        button = Button(label="Deposit", style=ButtonStyle.green)
        button.callback = deposit
        row.add_item(button)

        button = Button(label="Withdraw", style=ButtonStyle.red)
        button.callback = withdraw
        row.add_item(button)

        button = Button(label="Your Portfolio", style=ButtonStyle.blurple)
        button.callback = view_user_portfolio
        row.add_item(button)

        container.add_item(Separator())
        container.add_item(row)
        view.add_item(container)
        return view

    async def view_user_portfolio(interaction):
        await view_portfolio(interaction, interaction.user, refresh=False, hidden=True)

    async def go_back(interaction):
        await interaction.response.edit_message(view=await main_page(), attachments=[])

    await message.response.send_message(view=await main_page(), ephemeral=True)

    if not profile.seen_deposit:
        text = f"""Welcome!

**Cat Bot Stock Market** is a recreation of real-life stock market made to be as simple as possible while still being functional. There are 5 stocks you can trade with other Cat Bot users *globally*. To sell and buy stocks you use :coin: **coins**, which you can get by depositing {get_emoji("goldpack")} __Packs__. You can withdraw :coin: **coins** back into __Packs__.

Select any stock and click `💡 Help` to learn more, or click `Deposit` to start."""
        await message.followup.send(text, ephemeral=True)


@bot.tree.command(description="cat prisms are a special power up")
@discord.app_commands.describe(person="Person to view the prisms of")
async def prism(message: discord.Interaction, person: discord.User | discord.Member | None = None):
    assert message.guild is not None

    icon = get_emoji("prism")
    page_number = 0

    if not person:
        person_id = message.user
    else:
        person_id = person

    async def regen_texts() -> tuple[int, int, float, float, list[str]]:
        assert message.guild is not None
        user_prisms = await Prism.collect("guild_id = $1 AND user_id = $2", message.guild.id, person_id.id)
        all_prisms = await Prism.collect("guild_id = $1", message.guild.id)
        total_count = len(all_prisms)
        user_count = len(user_prisms)
        global_boost = 0.06 * math.log(2 * total_count + 1)
        user_boost = round((global_boost + 0.05 * math.log(2 * user_count + 1)) * 100, 3)
        prism_texts = []

        if person_id == message.user and user_count != 0:
            await achemb(message, "prism", "followup")

        order_map = {name: index for index, name in enumerate(prism_names)}
        prisms = all_prisms if not person else user_prisms
        prisms.sort(key=lambda p: order_map.get(p.name, float("inf")))

        for prism in prisms:
            owner = f" <@{prism.user_id}>'s" if not person else ""
            crafter = f"<@{prism.creator}> " if prism.creator and prism.creator != prism.user_id else ""
            prism_texts.append(f"{icon}{owner} **{prism.name}** ({crafter}crafted <t:{prism.time}:d>)")

        if len(prisms) == 0:
            prism_texts.append("No prisms found!")

        if person == bot.user:
            prism_texts = ["dont i technically own every prism ever bc yknow"]

        return total_count, user_count, global_boost, user_boost, prism_texts

    async def confirm_craft(interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        assert message.guild is not None

        if await Prism.count("guild_id = $1", interaction.guild.id) >= len(prism_names):
            await interaction.response.send_message("This server has reached the prism limit.", ephemeral=True)
            return

        # determine the next name
        selected_name = None
        for selected_name in prism_names:
            if not await Prism.get_or_none(guild_id=message.guild.id, name=selected_name):
                break

        if (
            not selected_name
            or await Prism.get_or_none(guild_id=message.guild.id, name=selected_name)
            or await Prism.count("guild_id = $1", message.guild.id) >= len(prism_names)
        ):
            await interaction.response.send_message("This server has reached the prism limit.", ephemeral=True)
            return

        if youngest_prism := await Prism.collect("guild_id = $1 ORDER BY time DESC LIMIT 1", message.guild.id):
            selected_time = max(round(time.time()), youngest_prism[0].time + 1)
        else:
            selected_time = round(time.time())

        # actually take away cats
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
        for i in cattypes:
            if user["cat_" + i] < 1:
                await interaction.response.send_message("You don't have enough cats. Nice try though.", ephemeral=True)
                return
            user["cat_" + i] -= 1

        # create the prism
        await Prism.create(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            creator=interaction.user.id,
            time=selected_time,
            name=selected_name,
        )
        await user.save()

        log_stats("prism_craft", {"name": selected_name})

        await interaction.response.send_message(f"{icon} {interaction.user.mention} has created prism {selected_name}!")
        await achemb(interaction, "prism", "followup")
        await achemb(interaction, "collecter", "followup")

    async def craft_prism(interaction: discord.Interaction) -> None:
        assert interaction.guild is not None

        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)

        found_cats = await cats_in_server(interaction.guild.id)
        missing_cats = []
        unknowns = 0
        for i in cattypes:
            if user[f"cat_{i}"] > 0:
                continue
            if i in found_cats:
                missing_cats.append(get_emoji(i.lower() + "cat"))
            else:
                unknowns += 1

        unknown_suffix = ""
        if unknowns:
            unknown_suffix = f" + {unknowns} unknown cat {plural('type', unknowns)} (see /catalogue)"

        if len(missing_cats) == 0:
            view = View(timeout=VIEW_TIMEOUT)
            confirm_button = Button(label="Craft!", style=ButtonStyle.blurple, emoji=icon)
            confirm_button.callback = confirm_craft
            description = "The crafting recipe is __ONE of EVERY cat type__.\nContinue crafting?"
        else:
            view = View(timeout=VIEW_TIMEOUT)
            confirm_button = Button(label="Not enough cats!", style=ButtonStyle.red, disabled=True)
            description = "The crafting recipe is __ONE of EVERY cat type__.\nYou are missing " + "".join(missing_cats) + unknown_suffix

        view.add_item(confirm_button)
        await interaction.response.send_message(description, view=view, ephemeral=True)

    async def change_page(interaction: discord.Interaction) -> None:
        nonlocal page_number
        wanted_page = interaction.custom_id
        if wanted_page == "first":
            page_number = 0
        elif wanted_page == "last":
            page_number = max(0, (len(prism_texts) - 1) // 26)
        else:
            assert wanted_page is not None
            page_number = int(wanted_page)
        await interaction.response.edit_message(view=gen_page())

    def gen_page() -> LayoutView:
        target = "" if not person else f" {person_id.name}'s"

        view = LayoutView(timeout=VIEW_TIMEOUT)

        last_page = max(0, (len(prism_texts) - 1) // 26)
        buttons = [
            Button(emoji="⏪", disabled=bool(page_number == 0), custom_id="first"),
            Button(emoji="⬅️", disabled=bool(page_number == 0), custom_id=str(page_number - 1)),
            Button(emoji="➡️", disabled=bool(page_number >= last_page), custom_id=str(page_number + 1)),
            Button(emoji="⏩", disabled=bool(page_number >= last_page), custom_id="last"),
        ]
        for button in buttons:
            button.callback = change_page

        async def filter_by_owner(interaction: discord.Interaction) -> None:
            nonlocal page_number, person, person_id, total_count, user_count, global_boost, user_boost, prism_texts
            page_number = 0
            if not user_select.values:
                person = None
                person_id = message.user
            else:
                person = user_select.values[0]
                person_id = person
            assert person_id is not None
            total_count, user_count, global_boost, user_boost, prism_texts = await regen_texts()
            await interaction.response.edit_message(view=gen_page())

        if person:
            user_select = discord.ui.UserSelect(placeholder="Filter by owner...", min_values=0, max_values=1, default_values=[person])
        else:
            user_select = discord.ui.UserSelect(placeholder="Filter by owner...", min_values=0, max_values=1)
        user_select.callback = filter_by_owner

        craft_button = Button(label="Craft!", style=ButtonStyle.blurple, emoji=icon)
        craft_button.callback = craft_prism

        embed = Container(
            Section(f"## {icon}{target} Cat Prisms", craft_button),
            "Prisms are a tradeable power-up which occasionally bumps cat rarity up by one. Each prism crafted gives the entire server an increased chance to get upgraded, plus additional chance for prism owner.",
            "\n".join(prism_texts[page_number * 26 : (page_number + 1) * 26]),
            f"-# Server Prisms: {total_count} | Boost Chance: {round(global_boost * 100, 3)}%\n-# {person_id.name}'s Prisms: {user_count} | Boost Chance: {user_boost}%",
            "===",
            ActionRow(*buttons),
            ActionRow(user_select),
        )

        view.add_item(embed)

        return view

    total_count, user_count, global_boost, user_boost, prism_texts = await regen_texts()
    await message.response.send_message(view=gen_page())


@bot.tree.command(description="Pong")
async def ping(message: discord.Interaction):
    assert message.guild is not None

    try:
        latency = round(bot.latency * 1000)
    except Exception:
        latency = "infinite"
    if latency == 0:
        # probably using gateway proxy, try fetching latency from metrics
        shard_latency = 0
        try:
            async with aiohttp.ClientSession() as session, session.get("http://localhost:7878/metrics") as response:
                data = await response.text()
                total_latencies = 0
                total_shards = 0
                for line in data.split("\n"):
                    if line.startswith("gateway_shard_latency{shard="):
                        if "NaN" in line:
                            continue
                        if f'shard="{message.guild.shard_id}"' in line:
                            shard_latency = int(float(line.split(" ")[1]) * 1000)
                        try:
                            total_latencies += float(line.split(" ")[1])
                            total_shards += 1
                        except Exception:
                            pass
                latency = round((total_latencies / total_shards) * 1000)
        except Exception:
            pass
        postfix = ""
        if shard_latency:
            postfix = f"\nthe neuron for this server has a delay of {shard_latency} ms {get_emoji('staring_cat')}{get_emoji('staring_cat')}"
        await message.response.send_message(f"🏓 cat has global brain delay of {latency} ms {get_emoji('staring_cat')}{postfix}")
    else:
        await message.response.send_message(f"🏓 cat has brain delay of {latency} ms {get_emoji('staring_cat')}")


@bot.tree.command(description="the most useful command ever")
async def bruh(message: discord.Interaction):
    await message.response.defer()
    await message.delete_original_response()


@bot.tree.command(description="play a relaxing game of tic tac toe (ttt)")
@discord.app_commands.describe(person="who do you want to play with? (choose Cat Bot for ai)")
async def tictactoe(message: discord.Interaction, person: discord.Member):
    do_edit = False
    board: list[Literal["❌", "⭕"] | None] = [None, None, None, None, None, None, None, None, None]

    players = [message.user, person]
    random.shuffle(players)
    bot_is_playing = person == bot.user
    current_turn = 0

    def check_win(board: list[Literal["❌", "⭕"] | None]) -> list[int]:
        for combination in data.win_combinations:
            if board[combination[0]] == board[combination[1]] == board[combination[2]] and board[combination[0]] is not None:
                return combination

        return [-1]

    def minimax(
        board: list[Literal["❌", "⭕"] | None],
        depth: int,
        is_maximizing: bool,
        alpha: float,
        beta: float,
        bot_symbol: Literal["❌", "⭕"],
        human_symbol: Literal["❌", "⭕"],
    ) -> float:
        wins = check_win(board)
        if wins != [-1]:
            if board[wins[0]] == bot_symbol:
                return 10 - depth  # Bot wins (good for bot)
            elif board[wins[0]] == human_symbol:
                return -10 + depth  # Human wins (bad for bot)

        if all(cell is not None for cell in board):
            return 0

        if is_maximizing:
            max_eval = float("-inf")
            for i in range(9):
                if board[i] is None:
                    board[i] = bot_symbol
                    eval = minimax(board, depth + 1, False, alpha, beta, bot_symbol, human_symbol)
                    board[i] = None
                    max_eval = max(max_eval, eval)
                    alpha = max(alpha, eval)
                    if beta <= alpha:
                        break
            return max_eval
        else:
            min_eval = float("inf")
            for i in range(9):
                if board[i] is None:
                    board[i] = human_symbol
                    eval = minimax(board, depth + 1, True, alpha, beta, bot_symbol, human_symbol)
                    board[i] = None
                    min_eval = min(min_eval, eval)
                    beta = min(beta, eval)
                    if beta <= alpha:
                        break
            return min_eval

    def get_best_move(board: list[Literal["❌", "⭕"] | None]) -> int | None:
        best_score = float("-inf")
        best_move = None

        bot_turn = None
        human_turn = None
        for i, player in enumerate(players):
            if player.bot:
                bot_turn = i
            else:
                human_turn = i

        bot_symbol: Literal["❌", "⭕"] = "❌" if bot_turn == 0 else "⭕"
        human_symbol: Literal["❌", "⭕"] = "❌" if human_turn == 0 else "⭕"

        for i in range(9):
            if board[i] is None:
                board[i] = bot_symbol
                score = minimax(board, 0, False, float("-inf"), float("inf"), bot_symbol, human_symbol)
                board[i] = None

                if score > best_score:
                    best_score = score
                    best_move = i

        return best_move

    async def finish_turn(interaction: discord.Interaction) -> None:
        nonlocal do_edit, current_turn

        view = LayoutView(timeout=VIEW_TIMEOUT)
        wins = check_win(board)
        tie = True
        rows = [ActionRow(), ActionRow(), ActionRow()]
        for cell_num, cell in enumerate(board):
            if cell is None:
                tie = False
                button = Button(emoji=get_emoji("empty"), custom_id=str(cell_num), disabled=wins != [-1])
            else:
                button = Button(emoji=cell, disabled=True, style=ButtonStyle.green if cell_num in wins else ButtonStyle.gray)
            button.callback = play
            rows[cell_num // 3].add_item(button)

        game_over = wins != [-1] or tie

        second_line = ""
        if wins != [-1]:
            if board[wins[0]] == "❌":
                second_line = f"{players[0].mention} (X) won!"
                await end_game(0)
            elif board[wins[0]] == "⭕":
                second_line = f"{players[1].mention} (O) won!"
                await end_game(1)
        elif tie:
            second_line = "its a tie!"
            await end_game(-1)
        else:
            second_line = f"{players[current_turn].mention}'s turn ({'X' if current_turn == 0 else 'O'})"

        restart_row = None
        if game_over and bot_is_playing:

            async def restart(interaction):
                nonlocal current_turn
                if interaction.user != message.user:
                    return await do_funny(interaction)
                board[:] = [None] * 9
                current_turn = 0
                random.shuffle(players)
                await finish_turn(interaction)

            restart_btn = Button(label="Play Again", emoji="🔄", style=ButtonStyle.blurple)
            restart_btn.callback = restart
            restart_row = ActionRow(restart_btn)

        container = Container(f"## {players[0].mention} (X) vs {players[1].mention} (O)", second_line, rows[0], rows[1], rows[2], restart_row)
        view.add_item(container)

        if do_edit:
            if not interaction.response.is_done():
                await interaction.response.edit_message(view=view)
            else:
                await interaction.edit_original_response(view=view)
        else:
            await interaction.response.send_message(view=view)
            do_edit = True

        if bot_is_playing and players[current_turn].bot and wins == [-1] and not tie:
            await asyncio.sleep(1)
            best_move = get_best_move(board)
            if best_move is not None:
                board[best_move] = "❌" if current_turn == 0 else "⭕"
                current_turn = 1 - current_turn
                await finish_turn(interaction)

    async def play(interaction: discord.Interaction) -> None:
        nonlocal current_turn
        assert interaction.custom_id is not None
        cell_num = int(interaction.custom_id)
        if board[cell_num] is not None:
            await interaction.response.send_message("That spot is already taken!", ephemeral=True)
            return
        if players[current_turn] != interaction.user:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        board[cell_num] = "❌" if current_turn == 0 else "⭕"
        current_turn = 1 - current_turn
        await finish_turn(interaction)

    async def end_game(winner: int) -> None:
        assert message.guild is not None

        if players[0] == players[1]:
            # self-play
            return
        users = [
            await Profile.get_or_create(guild_id=message.guild.id, user_id=players[0].id),
            await Profile.get_or_create(guild_id=message.guild.id, user_id=players[1].id),
        ]
        users[0].ttt_played += 1
        users[1].ttt_played += 1
        if winner != -1:
            users[winner].ttt_won += 1
            await achemb(message, "ttt_win", "followup", players[winner])
        else:
            users[0].ttt_draws += 1
            users[1].ttt_draws += 1
            if players[0] == bot.user:
                await progress(message, users[1], "ttc")
            if players[1] == bot.user:
                await progress(message, users[0], "ttc")
        await users[0].save()
        await users[1].save()

    await finish_turn(message)


@bot.tree.command(description="dont select a person to make an everyone vs you game")
@discord.app_commands.describe(person="Who do you want to play with?")
async def rps(message: discord.Interaction, person: discord.Member | None = None):
    clean_name = message.user.name.replace("_", "\\_")
    picks = {"Rock": [], "Paper": [], "Scissors": []}
    mappings = {"Rock": ["Paper", "Rock", "Scissors"], "Paper": ["Scissors", "Paper", "Rock"], "Scissors": ["Rock", "Scissors", "Paper"]}
    vs_picks = {}
    players = []

    async def pick(interaction: discord.Interaction) -> None:
        nonlocal players
        assert bot.user is not None

        if person and interaction.user.id not in [message.user.id, person.id]:
            await do_funny(interaction)
            return

        assert interaction.custom_id is not None
        thing = interaction.custom_id
        if person or interaction.user != message.user:
            if interaction.user.id in players:
                return
            if person:
                vs_picks[interaction.user.name.replace("_", "\\_")] = thing
            else:
                picks[thing].append(interaction.user.name.replace("_", "\\_"))
            players.append(interaction.user.id)
            if person and person.id == bot.user.id:
                players.append(bot.user.id)
                vs_picks[bot.user.name.replace("_", "\\_")] = mappings[thing][0]
            if not person or len(players) == 1:
                await interaction.response.edit_message(content=f"Players picked: {len(players)}")
                return

        result = mappings[thing]

        if not person:
            description = f"{clean_name} picked: __{thing}__\n\n"
            for num, i in enumerate(["Winners", "Tie", "Losers"]):
                if picks[result[num]]:
                    peoples = "\n".join(picks[result[num]])
                else:
                    peoples = "No one"
                description += f"**{i}** ({result[num]})\n{peoples}\n\n"
        else:
            description = f"{clean_name} picked: __{vs_picks[clean_name]}__\n\n{clean_name_2} picked: __{vs_picks[clean_name_2]}__\n\n"
            result = mappings[vs_picks[clean_name]].index(vs_picks[clean_name_2])
            if result == 0:
                description += f"**Winner**: {clean_name_2}!"
            elif result == 1:
                description += "It's a **Tie**!"
            else:
                description += f"**Winner**: {clean_name}!"

        embed = discord.Embed(
            title=f"{clean_name_2} vs {clean_name}",
            description=description,
            color=Colors.brown,
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    if person:
        clean_name_2 = person.name.replace("_", "\\_")
    else:
        clean_name_2 = "Rock Paper Scissors"

    if person:
        description = "Pick what to play!"
    else:
        description = "Any amount of users can play. The game ends when the person who ran the command picks. Max time is 24 hours."
    embed = discord.Embed(
        title=f"{clean_name_2} vs {clean_name}",
        description=description,
        color=Colors.brown,
    )
    view = View(timeout=24 * 3600)
    for i in ["Rock", "Paper", "Scissors"]:
        button = Button(label=i, custom_id=i)
        button.callback = pick
        view.add_item(button)
    await message.response.send_message("Players picked: 0", embed=embed, view=view)


@bot.tree.command(description="you feel like making cookies")
async def cookie(message: discord.Interaction):
    assert message.guild is not None
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    async def bake(interaction: discord.Interaction) -> None:
        nonlocal user
        assert message.guild is not None
        if interaction.user != message.user:
            await do_funny(interaction)
            return
        try:
            user = await Profile.get(["cookies", "misc_quest"], guild_id=message.guild.id, user_id=message.user.id)
            user.cookies += 1
            await user.save()
        except (AttributeError, LookupError):
            await interaction.response.edit_message(content="...", view=None)
            return
        btn = view.children[0]
        assert isinstance(btn, Button)
        btn.label = f"{user.cookies:,}"
        await interaction.response.edit_message(view=view)
        if user.cookies < 5:
            await achemb(interaction, "cookieclicker", "followup")
        if 5100 > user.cookies >= 5000:
            await achemb(interaction, "cookiesclicked", "followup")
        if user.misc_quest.strip() == "cookie":
            await progress(message, user, "cookie")

    view = View(timeout=VIEW_TIMEOUT)
    button = Button(emoji="🍪", label=f"{user.cookies:,}", style=ButtonStyle.blurple)
    button.callback = bake
    view.add_item(button)
    await message.response.send_message(view=view)


@bot.tree.command(description="yeah i made this solely so i could name it catfishing")
async def fish(message: discord.Interaction):
    assert message.guild is not None
    profile = await Profile.get_or_create(user_id=message.user.id, guild_id=message.guild.id)

    async def go_fishing(interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        if (interaction.guild.id, interaction.user.id) in fish_lock:
            await interaction.response.send_message("You're already fishing!", ephemeral=True)
            return

        fish_lock.add((interaction.guild.id, interaction.user.id))

        view = LayoutView(timeout=VIEW_TIMEOUT)
        view.add_item(TextDisplay("Fishing... (wait a bit)"))
        await interaction.response.edit_message(view=view)
        await profile.refresh_from_db()

        attempts = 1
        used_bait = False
        if profile.fish_bait_durability > 0:
            attempts = int(data.fishing_upgrades["bait"][profile.fish_bait_level]["value"])
            used_bait = True
        max_index = 0
        for _ in range(attempts):
            fishtype = random.choices(cattypes, weights=list(data.type_dict.values()))[0]
            max_index = max(max_index, cattypes.index(fishtype))
        fishtype = cattypes[max_index]

        mult = 1
        used_rod = False
        if profile.fish_rod_durability > 0:
            mult = data.fishing_upgrades["rod"][profile.fish_rod_level]["value"]
            used_rod = True
        for _ in range(random.randint(int(1000 * mult), int(3000 * mult))):
            if (interaction.guild.id, interaction.user.id) not in fish_lock:
                fish_lock.add((interaction.guild.id, interaction.user.id))
            await asyncio.sleep(0.01)

        fish_caught = False

        async def pull_fish(interaction: discord.Interaction) -> None:
            nonlocal fish_caught
            assert interaction.guild is not None
            if fish_caught:
                return
            if interaction.user != message.user:
                await do_funny(interaction)
                return
            fish_caught = True
            await profile.refresh_from_db()

            used_clover = False
            coin_mult = 1
            if profile.fish_clover_durability > 0:
                used_clover = True
                coin_mult = data.fishing_upgrades["clover"][profile.fish_clover_level]["value"]

            coins_gained = round(coin_mult * CAT_VALUES[fishtype])

            profile.fish_caught += 1
            profile.fish_coins += coins_gained
            if used_bait:
                profile.fish_bait_durability -= 1
            if used_rod:
                profile.fish_rod_durability -= 1
            if used_clover:
                profile.fish_clover_durability -= 1
            if not profile.rarest_fish.strip() or cattypes.index(fishtype) > cattypes.index(profile.rarest_fish.strip()):
                profile.rarest_fish = fishtype

            view = LayoutView(timeout=VIEW_TIMEOUT)
            button = Button(emoji="🎣", label="Cast", style=ButtonStyle.blurple)
            button.callback = go_fishing
            main_button = Button(emoji="⬅️", label="Main")
            main_button.callback = show_main
            usage_suffix = ", ".join(
                [
                    k
                    for k, v in {
                        f"🎣 ({profile.fish_rod_durability:,} left)": used_rod,
                        f"🍥 ({profile.fish_bait_durability:,} left)": used_bait,
                        f"🍀 ({profile.fish_clover_durability:,} left)": used_clover,
                    }.items()
                    if v
                ]
            )
            if usage_suffix:
                usage_suffix = "\n-# Used: " + usage_suffix
            view.add_item(
                TextDisplay(
                    f"You caught a {get_emoji(fishtype.lower() + 'fish')} {fishtype} fish and got 🪙 {coins_gained:,} coins (now {profile.fish_coins:,})!{usage_suffix}"
                )
            )
            view.add_item(ActionRow(button, main_button))
            await interaction.response.edit_message(view=view)

            await profile.save()
            await achemb(interaction, "fisherman", "followup")
            if cattypes.index(fishtype) >= 13:
                await achemb(interaction, "pro_fisher", "followup")
            if (
                used_bait
                and used_rod
                and used_clover
                and all(profile[f"fish_{u}_level"] + 1 >= len(data.fishing_upgrades[u]) for u in ["rod", "bait", "clover"])
            ):
                await achemb(interaction, "master_baiter", "followup")

            fish_lock.discard((interaction.guild.id, interaction.user.id))

            await progress(message, profile, "fish")

        view = LayoutView(timeout=VIEW_TIMEOUT)
        button = Button(label="Pull!", style=ButtonStyle.blurple)
        button.callback = pull_fish

        view.add_item(TextDisplay(f"A {get_emoji(fishtype.lower() + 'fish')} {fishtype} is on the line! Pull!"))
        view.add_item(ActionRow(button))

        await interaction.edit_original_response(view=view)

        await asyncio.sleep(5)

        if not fish_caught:
            await profile.refresh_from_db()
            used_clover = False
            if used_bait:
                profile.fish_bait_durability -= 1
            if used_rod:
                profile.fish_rod_durability -= 1
            if profile.fish_clover_durability > 0:
                used_clover = True
                profile.fish_clover_durability -= 1
            await profile.save()
            usage_suffix = ", ".join(
                [
                    k
                    for k, v in {
                        f"🎣 ({profile.fish_rod_durability:,} left)": used_rod,
                        f"🍥 ({profile.fish_bait_durability:,} left)": used_bait,
                        f"🍀 ({profile.fish_clover_durability:,} left)": used_clover,
                    }.items()
                    if v
                ]
            )
            if usage_suffix:
                usage_suffix = "\n-# Used: " + usage_suffix
            view = LayoutView(timeout=VIEW_TIMEOUT)
            button = Button(emoji="🎣", label="Cast", style=ButtonStyle.blurple)
            button.callback = go_fishing
            main_button = Button(emoji="⬅️", label="Main")
            main_button.callback = show_main
            view.add_item(TextDisplay("You weren't fast enough..." + usage_suffix))
            view.add_item(ActionRow(button, main_button))
            await interaction.edit_original_response(view=view)
            fish_lock.discard((interaction.guild.id, interaction.user.id))

    async def show_main(interaction: discord.Interaction) -> None:
        if interaction.user != message.user:
            return await do_funny(interaction)
        await interaction.response.edit_message(view=main_view())

    async def upgrade_upgrade(interaction: discord.Interaction) -> None:
        if interaction.user != message.user:
            return await do_funny(interaction)
        upgrade = interaction.custom_id
        assert upgrade is not None
        upgrade = upgrade.removesuffix("_upgrade")
        await profile.refresh_from_db()

        cost = data.fishing_upgrades[upgrade][profile[f"fish_{upgrade}_level"] + 1]["cost"]
        if profile.fish_coins < cost:
            await interaction.response.send_message("LMAOOOO your too broke", ephemeral=True)
            return
        profile[f"fish_{upgrade}_level"] += 1
        profile.fish_coins -= cost
        await profile.save()

        await show_main(interaction)

    async def durability_upgrade(interaction: discord.Interaction) -> None:
        if interaction.user != message.user:
            return await do_funny(interaction)
        upgrade = interaction.custom_id
        assert upgrade is not None
        upgrade = upgrade.removesuffix("_durability")
        await profile.refresh_from_db()

        async def durability_callback(interaction: discord.Interaction) -> None:
            await profile.refresh_from_db()
            try:
                item = modal.find_item(69)
                assert isinstance(item, discord.ui.TextInput)
                wanted = int(item.value)
                if wanted <= 0:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message("??? number pls", ephemeral=True)
                return

            if wanted * 25 > profile.fish_coins:
                await interaction.response.send_message("LMAOOOO your too broke", ephemeral=True)
                return

            profile.fish_coins -= wanted * 25
            profile[f"fish_{upgrade}_durability"] += wanted
            await profile.save()
            await show_main(interaction)

        modal = Modal(title="add durability...")
        modal.add_item(
            discord.ui.Label(
                text="durability to add (1 dura = 25 🪙)",
                component=discord.ui.TextInput(placeholder=f"max: {(profile.fish_coins // 25):,}", min_length=1, id=69),
            )
        )
        modal.on_submit = durability_callback
        await interaction.response.send_modal(modal)

    def main_view() -> LayoutView:
        view = LayoutView(timeout=VIEW_TIMEOUT)

        button = Button(emoji="🎣", label="Cast", style=ButtonStyle.blurple)
        button.callback = go_fishing

        if profile.rarest_fish.strip():
            rarest_fish = f"{get_emoji(profile.rarest_fish.lower() + 'fish')} {profile.rarest_fish}"
        else:
            rarest_fish = "none"

        buttons = []
        for upgrade in ["rod", "bait", "clover"]:
            if profile[f"fish_{upgrade}_level"] + 1 >= len(data.fishing_upgrades[upgrade]):
                btn = Button(label="maxxed out!", style=ButtonStyle.green, disabled=True)
                buttons.append(btn)
            else:
                cost = data.fishing_upgrades[upgrade][profile[f"fish_{upgrade}_level"] + 1]["cost"]
                btn = Button(label=f"upgrade (🪙 {cost:,})", style=ButtonStyle.green, custom_id=upgrade + "_upgrade")
                btn.callback = upgrade_upgrade
                buttons.append(btn)

            btn = Button(label="add...", style=ButtonStyle.blurple, custom_id=upgrade + "_durability")
            btn.callback = durability_upgrade
            buttons.append(btn)

        view.add_item(
            Container(
                "## 🐟 catfishing",
                f"🪙 fish coins: {profile.fish_coins:,}\ntotal fish caught: {profile.fish_caught:,}\nyour rarest fish: {rarest_fish}",
                "===",
                "### 🎣 fishing rod (speed)",
                Section(
                    f"level: **{profile.fish_rod_level:,}** ({data.fishing_upgrades['rod'][profile.fish_rod_level]['value']}x fishing duration)", buttons[0]
                ),
                Section(f"durability: **{profile.fish_rod_durability:,}**", buttons[1]),
                "===",
                "### 🍥 bait (rarity)",
                Section(
                    f"level: **{profile.fish_bait_level:,}** (best of {data.fishing_upgrades['bait'][profile.fish_bait_level]['value']} rarities)",
                    buttons[2],
                ),
                Section(f"durability: **{profile.fish_bait_durability:,}**", buttons[3]),
                "===",
                "### 🍀 clover (money)",
                Section(
                    f"level: **{profile.fish_clover_level:,}** ({data.fishing_upgrades['clover'][profile.fish_clover_level]['value']}x coins on sell)",
                    buttons[4],
                ),
                Section(f"durability: **{profile.fish_clover_durability:,}**", buttons[5]),
                "===",
                "-# upgrades temporarily deactivate (act as lvl 0) if they run out of durability",
            )
        )
        view.add_item(ActionRow(button))
        return view

    await message.response.send_message(view=main_view())


@bot.tree.command(description="donate (give) cats now")
@discord.app_commands.rename(gift_type="type", raw_amount="amount")
@discord.app_commands.describe(
    person="Whom to gift?",
    gift_type="im gonna airstrike your house from orbit",
    raw_amount='And how much? (default: 1, "all" for max)',
)
@discord.app_commands.autocomplete(gift_type=gift_autocomplete)
async def gift(
    message: discord.Interaction,
    person: discord.User,
    gift_type: str,
    raw_amount: str | None = None,
):
    assert message.guild is not None
    assert bot.user is not None
    person_id = person.id
    if not raw_amount:
        raw_amount = "1"

    if raw_amount.lower() in ["all", "max"]:
        amount = "all"
    else:
        if not raw_amount.isdigit() or not raw_amount.isascii() or (raw_amount.isdigit() and int(raw_amount) >= 2147483647):
            await message.response.send_message("no", ephemeral=True)
            return
        amount = int(raw_amount)

    if message.user.id == person_id:
        # haha skill issue
        await message.response.send_message("no", ephemeral=True)
        await achemb(message, "lonely", "followup")
        return

    async with transaction() as conn:
        if gift_type.lower() == "rain":
            if person_id == bot.user.id:
                await message.response.send_message("you can't sacrifice rains", ephemeral=True)
                return
            user = await User.get_or_create(conn, user_id=message.user.id)
            reciever = await User.get_or_create(conn, user_id=person_id)
        else:
            user = await Profile.get_or_create(conn, guild_id=message.guild.id, user_id=message.user.id)
            reciever = await Profile.get_or_create(conn, guild_id=message.guild.id, user_id=person_id)

        if gift_type.lower() == "rain":
            key = "rain_minutes"
            thing = "Rain Minute"
        elif gift_type.lower() in [cattype.lower() for cattype in cattypes]:
            gift_type = cattype_lc_dict[gift_type.lower()]
            key = f"cat_{gift_type}"
            thing = f"{gift_type} cat"
        elif gift_type.lower() in [i["name"].lower() for i in data.pack_data]:
            key = f"pack_{gift_type.lower()}"
            thing = f"{gift_type.capitalize()} pack"
            if not user.bp_history.strip().replace("0,0,0;", ""):
                await message.response.send_message("your profile needs to be older than 1 cattlepass season to gift packs.", ephemeral=True)
                return
        elif gift_type.lower() == "scratchcards":
            key = "scratchcards"
            thing = "Scratchcard"
        else:
            await message.response.send_message("bro what", ephemeral=True)
            return

        # if enough
        if amount == "all":
            amount = user[key]
        if amount <= 0:
            await message.response.send_message("no", ephemeral=True)
            return
        if user[key] >= amount:
            user[key] -= amount
            reciever[key] += amount
            if key.startswith("cat_"):
                user.cats_gifted += amount
                reciever.cat_gifts_recieved += amount
            await user.save()
            await reciever.save()
        else:
            await message.response.send_message("no", ephemeral=True)
            return

    content = f"Successfully transfered {amount:,} {plural(thing, amount)} from {message.user.mention} to {person.mention}!"

    if person == bot.user:
        content += " wow thank you"

    # handle tax
    if key.startswith("cat_") and amount >= 5:
        tax_amount = round(amount * 0.2)
        tax_debounce = False

        async def pay(interaction: discord.Interaction) -> None:
            nonlocal tax_debounce
            assert message.guild is not None
            if tax_debounce:
                return
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return

            tax_debounce = True

            user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
            user[f"cat_{gift_type}"] -= tax_amount
            await user.save()

            await interaction.response.edit_message(view=None)
            await interaction.followup.send(f"You paid the tax of {tax_amount:,} {gift_type} {plural('cat', tax_amount)}!")
            await achemb(message, "good_citizen", "followup")
            if user[f"cat_{gift_type}"] < 0:
                bot.loop.create_task(debt_cutscene(interaction, user))

        async def evade(interaction: discord.Interaction) -> None:
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return

            await interaction.response.edit_message(view=None)
            await interaction.followup.send(f"You evaded the tax of {tax_amount:,} {gift_type} {plural('cat', tax_amount)}.")
            await achemb(message, "secret", "followup")

        button = Button(label="Pay 20% tax", style=ButtonStyle.green)
        button.callback = pay

        button2 = Button(label="Evade the tax", style=ButtonStyle.red)
        button2.callback = evade

        myview = View(timeout=VIEW_TIMEOUT)

        myview.add_item(button)
        myview.add_item(button2)

        await message.response.send_message(content, view=myview, allowed_mentions=discord.AllowedMentions(users=True))
    else:
        await message.response.send_message(content, allowed_mentions=discord.AllowedMentions(users=True))

    # handle aches
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await achemb(message, "donator", "followup")
    await achemb(message, "anti_donator", "followup", person)
    if person_id == bot.user.id and gift_type == "Ultimate":
        user.ultimates_gifted = min(32766, user.ultimates_gifted + int(amount))
        await user.save()
        if user.ultimates_gifted >= 5:
            await achemb(message, "rich", "followup")
    if person_id == bot.user.id:
        await achemb(message, "sacrifice", "followup")
    if gift_type == "Nice" and int(amount) == 69:
        await achemb(message, "nice", "followup")

    if key == "rain_minutes":
        try:
            ch = bot.get_partial_messageable(config.RAIN_CHANNEL_ID)
            await ch.send(f"{message.user.id} gave {amount}m to {person_id}")
        except Exception:
            pass


def parse_trade_amount(raw: str) -> int | Literal["all"] | None:
    if raw.lower() in ["max", "all"]:
        return "all"
    try:
        return int(raw)
    except ValueError:
        return None


async def resolve_trade_delta(current: int, available: int, requested: int | Literal["all"], item_label: str, interaction: discord.Interaction) -> int | None:
    """Resolves 'all' against what's available and validates bounds. Returns the delta to apply, or None if invalid (a response has already been sent)."""
    if requested == "all":
        requested = available - current
    if available < requested + current or current + requested < 0:
        await interaction.response.send_message(f"You don't have enough {item_label}!", ephemeral=True)
        return None
    return requested


@bot.tree.command(description="Trade stuff!")
@discord.app_commands.rename(other_user="user")
@discord.app_commands.describe(other_user="why would you need description")
async def trade(message: discord.Interaction, other_user: discord.User):
    assert message.guild is not None

    class TradeUser:
        def __init__(self, user: discord.abc.User, profile: Profile, global_user: User) -> None:
            assert bot.user is not None
            self.user = user
            self.profile = profile
            self.global_user = global_user
            self.accept = False
            self.value = 0

            self.gives_cats = {}
            self.gives_packs = {}
            self.gives_rain = 0
            self.gives_prisms = []
            self.gives_scratchcards = 0

            if user.id == bot.user.id:
                self.gives_cats["eGirl"] = 9999999
                self.value += CAT_VALUES["eGirl"] * 9999999

    blackhole: bool = False
    person1: TradeUser = TradeUser(
        message.user,
        await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id),
        await User.get_or_create(user_id=message.user.id),
    )
    person2: TradeUser = TradeUser(
        other_user,
        await Profile.get_or_create(guild_id=message.guild.id, user_id=other_user.id),
        await User.get_or_create(user_id=other_user.id),
    )

    async def denyb(interaction: discord.Interaction) -> None:
        nonlocal blackhole
        if interaction.user not in [person1.user, person2.user]:
            await do_funny(interaction)
            return

        blackhole = True
        person1.accept = False
        person2.accept = False
        try:
            await interaction.response.edit_message(content=f"{interaction.user.mention} has cancelled the trade.", embed=None, view=None)
        except Exception:
            pass

    async def acceptb(interaction: discord.Interaction) -> None:
        nonlocal blackhole
        if interaction.user not in [person1.user, person2.user]:
            await do_funny(interaction)
            return

        active_user = person1 if interaction.user == person1.user else person2
        active_user.accept = not active_user.accept

        embed, view = await gen_embed()
        await interaction.response.edit_message(embed=embed, view=view)

        if active_user == person1 and active_user.accept and person2.user == bot.user:
            await achemb(message, "desperate", "followup")

        if person1.accept and person2.accept and not blackhole:
            # accepted!!
            blackhole = True

            # verify
            fail = False

            async def fetch_all_prisms() -> dict[str, Prism]:
                assert interaction.guild is not None
                if not (prism_names := person1.gives_prisms + person2.gives_prisms):
                    return {}
                return {
                    p.name: p
                    async for p in Prism.filter(
                        "guild_id = $1 AND name = ANY($2)",
                        interaction.guild.id,
                        prism_names,
                        refetch=False,
                    )
                }

            tasks: list[Awaitable[object]] = [
                person1.profile.refresh_from_db(),
                person2.profile.refresh_from_db(),
                person1.global_user.refresh_from_db(),
                person2.global_user.refresh_from_db(),
            ]
            fetch_prisms_task = None
            if person1.gives_prisms or person2.gives_prisms:
                fetch_prisms_task = bot.loop.create_task(fetch_all_prisms())
                tasks.append(fetch_prisms_task)

            await asyncio.gather(*tasks)

            temp_prisms = fetch_prisms_task.result() if fetch_prisms_task else {}

            for user in [person1, person2]:
                for item, amount in user.gives_cats.items():
                    if user.profile[f"cat_{item}"] < amount:
                        fail = f"You don't have enough {item} cats!"
                for item, amount in user.gives_packs.items():
                    if user.profile[f"pack_{item.lower()}"] < amount:
                        fail = f"You don't have enough {item} packs!"
                if user.global_user.rain_minutes < user.gives_rain:
                    fail = "You don't have enough rain!"
                if user.profile.scratchcards < user.gives_scratchcards:
                    fail = "You don't have enough scratchcards!"
                for prism in user.gives_prisms:
                    if prism not in temp_prisms:
                        fail = f"Prism {prism} not found!"
                    elif temp_prisms[prism].user_id != user.user.id:
                        fail = f"You don't own prism {prism}!"

            if fail:
                await interaction.edit_original_response(content=fail, embed=None, view=None)
                return

            # exchange
            cat_count = 0
            for giver in [person1, person2]:
                getter = person2 if giver == person1 else person1
                for item, amount in giver.gives_cats.items():
                    giver.profile[f"cat_{item}"] -= amount
                    getter.profile[f"cat_{item}"] += amount
                    cat_count += amount
                for item, amount in giver.gives_packs.items():
                    giver.profile[f"pack_{item.lower()}"] -= amount
                    getter.profile[f"pack_{item.lower()}"] += amount
                if giver.gives_rain:
                    giver.global_user.rain_minutes -= giver.gives_rain
                    getter.global_user.rain_minutes += giver.gives_rain
                    try:
                        ch = bot.get_partial_messageable(config.RAIN_CHANNEL_ID)
                        bot.loop.create_task(ch.send(f"{giver.user.id} traded {giver.gives_rain}m to {getter.user.id}"))
                    except Exception:
                        pass
                if giver.gives_scratchcards:
                    giver.profile.scratchcards -= giver.gives_scratchcards
                    getter.profile.scratchcards += giver.gives_scratchcards
                for prism in giver.gives_prisms:
                    temp_prisms[prism].user_id = getter.user.id

            person1.profile.cats_traded += cat_count
            person2.profile.cats_traded += cat_count
            person1.profile.trades_completed += 1
            person2.profile.trades_completed += 1

            async def save_prisms() -> None:
                if temp_prisms:
                    await Prism.bulk_update(list(temp_prisms.values()), "user_id")

            await asyncio.gather(
                person1.profile.save(),
                person2.profile.save(),
                person1.global_user.save(),
                person2.global_user.save(),
                save_prisms(),
            )

            await interaction.edit_original_response(content="Trade finished!", view=None)

            await achemb(message, "extrovert", "followup")
            await achemb(message, "extrovert", "followup", other_user)

            if cat_count >= 1000:
                await achemb(message, "capitalism", "followup")
                await achemb(message, "capitalism", "followup", other_user)

            if person1.value + person2.value == 0:
                await achemb(message, "absolutely_nothing", "followup")
                await achemb(message, "absolutely_nothing", "followup", other_user)

            if person2.value - person1.value >= 100:
                await achemb(message, "profit", "followup")
            if person1.value - person2.value >= 100:
                await achemb(message, "profit", "followup", other_user)

            if person1.value > person2.value:
                await achemb(message, "scammed", "followup")
            if person2.value > person1.value:
                await achemb(message, "scammed", "followup", other_user)

            if person1.value == person2.value and (
                person1.gives_cats != person2.gives_cats or person1.gives_packs != person2.gives_packs or person1.gives_rain != person2.gives_rain
            ):
                await achemb(message, "perfectly_balanced", "followup")
                await achemb(message, "perfectly_balanced", "followup", other_user)

            await progress(message, person1.profile, "trade")
            await progress(message, person2.profile, "trade")

    async def gen_embed() -> tuple[discord.Embed, View | None]:
        if blackhole:
            # no way thats fun
            await achemb(message, "blackhole", "followup")
            await achemb(message, "blackhole", "followup", other_user)
            return discord.Embed(color=Colors.brown, title="Blackhole", description="How Did We Get Here?"), None

        async def selectb(interaction: discord.Interaction) -> None:
            async def submitb(interaction2: discord.Interaction) -> None:
                assert modal is not None
                item1 = modal.find_item(67)
                item2 = modal.find_item(69)
                match selection:
                    case "cats":
                        assert isinstance(item1, discord.ui.Select)
                        assert isinstance(item2, discord.ui.TextInput)
                        pre_cattype = item1.values[0].lower()
                        amount = parse_trade_amount(item2.value)
                        if amount is None:
                            await interaction2.response.send_message("Amount must be an integer!", ephemeral=True)
                            return

                        cattype = {t.lower(): t for t in cattypes}.get(pre_cattype, None)
                        if cattype is None:
                            await interaction2.response.send_message("Invalid cat type!", ephemeral=True)
                            return

                        await active_user.profile.refresh_from_db()

                        current = active_user.gives_cats.get(cattype, 0)
                        amount = await resolve_trade_delta(current, active_user.profile[f"cat_{cattype}"], amount, f"{cattype} cats", interaction2)
                        if amount is None:
                            return

                        if current + amount == 0:
                            active_user.gives_cats.pop(cattype, None)
                        else:
                            active_user.gives_cats[cattype] = amount + current
                            active_user.gives_cats = {k: active_user.gives_cats[k] for k in cattypes if k in active_user.gives_cats}
                        active_user.value += CAT_VALUES[cattype] * amount
                    case "packs":
                        assert isinstance(item1, discord.ui.Select)
                        assert isinstance(item2, discord.ui.TextInput)
                        packtype = item1.values[0].title()
                        amount = parse_trade_amount(item2.value)
                        if amount is None:
                            await interaction2.response.send_message("Amount must be an integer!", ephemeral=True)
                            return

                        if packtype not in pack_names:
                            await interaction2.response.send_message(f"Pack {packtype} not found!", ephemeral=True)
                            return

                        await active_user.profile.refresh_from_db()

                        current = active_user.gives_packs.get(packtype, 0)
                        amount = await resolve_trade_delta(current, active_user.profile[f"pack_{packtype.lower()}"], amount, f"{packtype} packs", interaction2)
                        if amount is None:
                            return

                        if current + amount == 0:
                            active_user.gives_packs.pop(packtype, None)
                        else:
                            active_user.gives_packs[packtype] = amount + current
                            active_user.gives_packs = {k: active_user.gives_packs[k] for k in pack_names if k in active_user.gives_packs}
                        active_user.value += sum([i["totalvalue"] if i["name"] == packtype else 0 for i in data.pack_data]) * amount
                    case "scratchcards":
                        assert isinstance(item2, discord.ui.TextInput)
                        amount = parse_trade_amount(item2.value)
                        if amount is None:
                            await interaction2.response.send_message("Amount must be an integer!", ephemeral=True)
                            return

                        await active_user.profile.refresh_from_db()

                        current = active_user.gives_scratchcards
                        amount = await resolve_trade_delta(current, active_user.profile.scratchcards, amount, "scratchcards", interaction2)
                        if amount is None:
                            return

                        active_user.gives_scratchcards += amount
                        active_user.value += amount * 1085
                    case "rain":
                        assert isinstance(item2, discord.ui.TextInput)
                        amount = parse_trade_amount(item2.value)
                        if amount is None:
                            await interaction2.response.send_message("Amount must be an integer!", ephemeral=True)
                            return

                        await active_user.global_user.refresh_from_db()

                        current = active_user.gives_rain
                        amount = await resolve_trade_delta(current, active_user.global_user.rain_minutes, amount, "rain", interaction2)
                        if amount is None:
                            return

                        active_user.gives_rain += amount
                    case "prisms":
                        if isinstance(item1, discord.ui.Select):
                            prism_name = item1.values[0].title()
                        elif isinstance(item1, discord.ui.TextInput):
                            prism_name = item1.value.title()
                        else:
                            raise TypeError(f"Expected Select or TextInput, got {type(item1)}")

                        prism_name = prism_name.replace("X-Ray", "X-ray")

                        if prism_name in active_user.gives_prisms:
                            active_user.gives_prisms.remove(prism_name)
                            active_user.value -= PRISM_VALUE
                        else:
                            assert interaction2.guild is not None
                            prism = await Prism.get_or_none(guild_id=interaction2.guild.id, name=prism_name)

                            if prism is None:
                                await interaction2.response.send_message(f"Prism {prism_name} not found!", ephemeral=True)
                                return
                            if prism.user_id != active_user.user.id:
                                await interaction2.response.send_message(f"You don't own the {prism_name} prism!", ephemeral=True)
                                return

                            active_user.gives_prisms.append(prism_name)
                            order_index = {k: i for i, k in enumerate(prism_names)}
                            active_user.gives_prisms.sort(key=lambda x: order_index.get(x, float("inf")))
                            active_user.value += PRISM_VALUE

                person1.accept = False
                person2.accept = False

                embed, view = await gen_embed()
                await interaction2.response.defer()
                await interaction.edit_original_response(embed=embed, view=view)

            if interaction.user not in [person1.user, person2.user]:
                await do_funny(interaction)
                return

            active_user = person1 if interaction.user == person1.user else person2
            selection = select.values[0]
            modal = None
            match selection:
                case "cats":
                    modal = Modal(title="Offer cats...")
                    options = []
                    await active_user.profile.refresh_from_db()
                    for cattype in cattypes:
                        if (ca := active_user.profile[f"cat_{cattype}"]) > 0:
                            value = CAT_VALUES[cattype]
                            options.append(
                                discord.SelectOption(
                                    value=cattype,
                                    label=f"{cattype} ({ca})",
                                    emoji=get_emoji(f"{cattype.lower()}cat"),
                                    description=f"{round(value, 2)} value",
                                )
                            )
                    if len(options) == 0:
                        await interaction.response.send_message("You don't have any cats to offer!", ephemeral=True)
                        return
                    modal.add_item(discord.ui.Label(text="Cat Type", component=discord.ui.Select(options=options, id=67)))
                    modal.add_item(discord.ui.Label(text="Amount", component=discord.ui.TextInput(placeholder="1", min_length=1, id=69)))
                case "packs":
                    if not active_user.profile.bp_history.strip().replace("0,0,0;", ""):
                        await interaction.response.send_message("your profile needs to be older than 1 cattlepass season to trade packs.", ephemeral=True)
                        return
                    modal = Modal(title="Offer packs...")
                    options = []
                    await active_user.profile.refresh_from_db()
                    for pack in pack_names:
                        if (pa := active_user.profile[f"pack_{pack.lower()}"]) > 0:
                            value = sum([i["totalvalue"] if i["name"] == pack else 0 for i in data.pack_data])
                            options.append(
                                discord.SelectOption(
                                    value=pack,
                                    label=f"{pack} ({pa})",
                                    emoji=get_emoji(f"{pack.lower()}pack"),
                                    description=f"{round(value, 2)} value",
                                )
                            )
                    if len(options) == 0:
                        await interaction.response.send_message("You don't have any packs to offer!", ephemeral=True)
                        return
                    modal.add_item(discord.ui.Label(text="Pack Type", component=discord.ui.Select(options=options, id=67)))
                    modal.add_item(discord.ui.Label(text="Amount", component=discord.ui.TextInput(placeholder="1", min_length=1, id=69)))
                case "scratchcards":
                    modal = Modal(title="Offer scratchcards...")
                    await active_user.profile.refresh_from_db()
                    if active_user.profile.scratchcards == 0:
                        await interaction.response.send_message("You don't have any scratchcards to offer!", ephemeral=True)
                        return

                    modal.add_item(
                        discord.ui.Label(
                            text="Amount (1085 value each)",
                            component=discord.ui.TextInput(placeholder=f"Max: {active_user.profile.scratchcards:,}", min_length=1, id=69),
                        )
                    )
                case "rain":
                    modal = Modal(title="Offer rain...")
                    await active_user.global_user.refresh_from_db()
                    if active_user.global_user.rain_minutes == 0:
                        await interaction.response.send_message("You don't have any rain to offer!", ephemeral=True)
                        return

                    modal.add_item(
                        discord.ui.Label(
                            text="Rain Minutes", component=discord.ui.TextInput(placeholder=f"Max: {active_user.global_user.rain_minutes}", min_length=1, id=69)
                        )
                    )
                case "prisms":
                    modal = Modal(title="Offer prisms...")
                    assert message.guild is not None
                    names = [
                        prism.name async for prism in Prism.filter("user_id = $1 AND guild_id = $2 ORDER BY time ASC", active_user.user.id, message.guild.id)
                    ]
                    names = list(dict.fromkeys(names))
                    if len(names) == 0:
                        await interaction.response.send_message("You don't have any prisms to offer!", ephemeral=True)
                        return
                    if len(names) <= 25:
                        options = [discord.SelectOption(label=name, emoji=get_emoji("prism")) for name in names]
                        modal.add_item(discord.ui.Label(text=f"Prism Type ({PRISM_VALUE} value each)", component=discord.ui.Select(options=options, id=67)))
                    else:
                        modal.add_item(
                            discord.ui.Label(text=f"Prism Type ({PRISM_VALUE} value each)", component=discord.ui.TextInput(placeholder="Alpha", id=67))
                        )
            assert modal is not None
            modal.on_submit = submitb
            await interaction.response.send_modal(modal)

        view = View(timeout=VIEW_TIMEOUT)

        accept = Button(label="Accept", style=ButtonStyle.green)
        accept.callback = acceptb

        deny = Button(label="Deny", style=ButtonStyle.red)
        deny.callback = denyb

        options = [
            discord.SelectOption(label="Cats", emoji=get_emoji("finecat"), value="cats"),
            discord.SelectOption(label="Packs", emoji=get_emoji("goldpack"), value="packs"),
            discord.SelectOption(label="Prisms", emoji=get_emoji("prism"), value="prisms"),
            discord.SelectOption(label="Scratchcards", emoji="🍀", value="scratchcards"),
            discord.SelectOption(label="Rain", emoji="☔", value="rain"),
        ]

        select = discord.ui.Select(placeholder="Offer...", options=options)
        select.callback = selectb

        view.add_item(accept)
        view.add_item(deny)
        view.add_item(select)

        coolembed = discord.Embed(color=Colors.brown, title="Trade")
        rain_suffix = False

        # a single field for one person
        for tradeuser in [person1, person2]:
            icon = "✅" if tradeuser.accept else "⬜"
            offer_string = ""
            local_rain_suffix = ""

            total = 0
            for cattype, amount in tradeuser.gives_cats.items():
                total += amount
                offer_string += f"{get_short_emoji(cattype.lower() + 'cat')} {cattype} {amount:,}\n"

            for packtype, amount in tradeuser.gives_packs.items():
                offer_string += f"{get_short_emoji(packtype.lower() + 'pack')} {packtype} {amount:,}\n"

            for prism in tradeuser.gives_prisms:
                offer_string += f"{get_short_emoji('prism')} {prism}\n"

            if tradeuser.gives_scratchcards:
                offer_string += f"🍀 {tradeuser.gives_scratchcards:,} scratchcards\n"

            if tradeuser.gives_rain:
                offer_string += f"☔ {tradeuser.gives_rain:,}m of Cat Rains\\*\n"
                rain_suffix = True
                local_rain_suffix = "\\*"

            if not offer_string:
                offer_string = "Nothing offered!"
            else:
                offer_string += f"*Total value: {round(tradeuser.value):,}{local_rain_suffix}\nTotal cats: {round(total):,}*"

            personname = tradeuser.user.name.replace("_", "\\_")
            if len(offer_string) > 1024:
                offer_string = re.sub(r"<:[^:]+:[^>]+> ", "", offer_string)
            coolembed.add_field(name=f"{icon} {personname}", inline=True, value=offer_string)

        if rain_suffix:
            coolembed.set_footer(text="*rains not included in value")

        return coolembed, view

    embed, view = await gen_embed()
    assert view is not None
    await message.response.send_message(other_user.mention, embed=embed, view=view, allowed_mentions=discord.AllowedMentions(users=True))

    if message.user == other_user:
        await achemb(message, "introvert", "followup")


@bot.tree.command(description="Get Cat Image, does not add a cat to your inventory")
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(cat_type="select a cat type ok")
@discord.app_commands.autocomplete(cat_type=cat_command_autocomplete)
async def cat(message: discord.Interaction, cat_type: str | None = None):
    assert message.guild is not None

    if cat_type and cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    # check the user has the cat if required
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    if cat_type and user[f"cat_{cat_type}"] <= 0:
        await message.response.send_message("you dont have that cat", ephemeral=True)
        return

    image = f"assets/images/spawn/{cat_type.lower()}_cat.png" if cat_type else "assets/images/cat.png"
    file = discord.File(image, filename=image)
    await message.response.send_message(file=file)


@bot.tree.command(description="Get Cursed Cat")
async def cursed(message: discord.Interaction):
    file = discord.File("assets/images/cursed.jpg", filename="cursed.jpg")
    await message.response.send_message(file=file)


@bot.tree.command(description="Get Your balance")
async def bal(message: discord.Interaction):
    file = discord.File("assets/images/money.png", filename="money.png")
    embed = discord.Embed(title="cat coins", color=Colors.brown).set_image(url="attachment://money.png")
    await message.response.send_message(file=file, embed=embed)


@bot.tree.command(description="Brew some coffee to catch cats more efficiently")
async def brew(message: discord.Interaction):
    async def brew_coffee(interaction: discord.Interaction) -> None:
        nonlocal view
        assert message.guild is not None
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        try:
            user = await Profile.get(["coffees", "misc_quest"], guild_id=message.guild.id, user_id=message.user.id)
            user.coffees += 1
            await user.save()
        except (AttributeError, LookupError):
            await interaction.response.edit_message(content="...", view=None)
            return

        btn = view.children[0]
        assert isinstance(btn, Button)
        btn.label = f"{user.coffees:,}"
        await interaction.response.edit_message(content="ugh fine", view=view)

        if user.misc_quest.strip() == "coffee":
            await progress(message, user, "coffee")

    view = View(timeout=VIEW_TIMEOUT)
    button = Button(emoji="☕", label="Retry", style=ButtonStyle.blurple)
    button.callback = brew_coffee
    view.add_item(button)
    await message.response.send_message("HTTP 418: I'm a teapot. <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/418>", view=view)
    await achemb(message, "coffee", "followup")


def get_current_week() -> int:
    epoch_monday = datetime.datetime(1970, 1, 5, tzinfo=datetime.timezone.utc).date()
    today = discord.utils.utcnow().date()
    return (today - epoch_monday).days // 7


def get_timestamp_of_next_week() -> int:
    today = discord.utils.utcnow().date()
    days_until_next_monday = (7 - today.weekday()) % 7
    if days_until_next_monday == 0:
        days_until_next_monday = 7
    next_monday_date = today + datetime.timedelta(days=days_until_next_monday)
    next_monday_dt = datetime.datetime(next_monday_date.year, next_monday_date.month, next_monday_date.day, tzinfo=datetime.timezone.utc)
    return int(next_monday_dt.timestamp())


@bot.tree.command(description="Deliver orders from your bakery to get Cat Eggs and Packs!")
async def bakery(message: discord.Interaction):
    async def refresh(interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(view=await gen_bakery())

    async def gen_bakery() -> LayoutView:
        assert message.guild is not None
        assert isinstance(message.channel, GuildMessageable)
        user = await User.get_or_create(user_id=message.user.id)
        profile = await Profile.get_or_create(user_id=message.user.id, guild_id=message.guild.id)
        if user.queued_chef_pack:
            profile.pack_chef += 1
            user.queued_chef_pack = False
            await user.save()
            await profile.save()
            log_stats("chef_pack_get")
            try:
                await message.channel.send(f"{message.user.mention} got +1 {get_emoji('chefpack')} Chef Pack from Bake.gg!")
            except Exception:
                pass

        refresh_button = Button(label="Refresh", emoji="🔄")
        refresh_button.callback = refresh

        if user.last_bakegg_send == get_current_week():
            # order already delivered for this week
            view = LayoutView(timeout=VIEW_TIMEOUT)
            view.add_item(
                Container(
                    "## ✅ Order Delivered!",
                    f"+1 {get_emoji('silverpack')} Silver pack, +1 {get_emoji('bakegg_egg')} Bake.gg Cat Egg",
                    f"Next order <t:{get_timestamp_of_next_week()}:R>",
                    "===",
                    f"➡️ Opening any {get_emoji('bakegg_egg')} Cat Egg in Bake.gg will give you an **exclusive {get_emoji('chefpack')} Chef Pack** in Cat Bot, so head over to not miss out!",
                    "-# 1 Chef Pack per user per week",
                    "===",
                    ActionRow(Button(label="Bake.gg", url="https://bake.gg/"), refresh_button),
                )
            )
            return view

        async def deliver(interaction: discord.Interaction) -> None:
            if interaction.user != message.user:
                await do_funny(interaction)
                return

            await profile.refresh_from_db()
            await user.refresh_from_db()
            if profile.cookies < 120 or profile.coffees < 140 or profile.cat_Nice < 2:
                await interaction.response.send_message("Your order is not ready yet.", ephemeral=True)
                return
            if user.last_bakegg_send == get_current_week():
                await interaction.response.send_message("You've already delivered this order.", ephemeral=True)
                return

            success = False
            try:
                async with (
                    aiohttp.ClientSession() as session,
                    session.post(
                        "https://auth.bake.gg:2053/reward/catbot",
                        headers={"Authorization": os.environ.get("BAKE_GG_TOKEN", "")},  # i dont believe anyone would ever need to change this
                        json={"user": str(interaction.user.id)},
                    ) as response,
                ):
                    if response.status != 200:
                        logger.warning("Bake.gg reward failed: status=%s body=%s", response.status, await response.text())
                        raise ValueError

                    profile.cookies -= 120
                    profile.coffees -= 140
                    profile.cat_Nice -= 2
                    profile.pack_silver += 1
                    await profile.save()

                    user.last_bakegg_send = get_current_week()
                    await user.save()

                    log_stats("bakery_delivered")

                    await interaction.response.edit_message(view=await gen_bakery())
                    success = True
            except Exception:
                await interaction.response.send_message("Failed! Try again later.", ephemeral=True)
                raise

            if success:
                await achemb(message, "baker", "followup")

        view = LayoutView(timeout=VIEW_TIMEOUT)
        order_complete = profile.cookies >= 120 and profile.coffees >= 140 and profile.cat_Nice >= 2
        button = Button(label="Deliver!", style=ButtonStyle.green, disabled=not order_complete)
        button.callback = deliver
        embed = Container(
            "## 📝 Bakery Order",
            "In collaboration with [Bake.gg](https://bake.gg)",
            "__Order Details__",
            f"""{get_emoji("bakegg_cookie")} {min(profile.cookies, 120)}/120 {"✅" if profile.cookies >= 120 else "(`/cookie`)"}
{get_emoji("bakegg_coffee")} {min(profile.coffees, 140)}/140 {"✅" if profile.coffees >= 140 else "(`/brew`)"}
{get_emoji("nicecat")} {min(profile.cat_Nice, 2)}/2 {"✅" if profile.cat_Nice >= 2 else ""}""",
            "===",
            "__Order Reward__",
            f"""{get_emoji("bakegg_egg")} 1 Bake.gg Cat Egg\n{get_emoji("silverpack")} 1 Silver Pack""",
            "-# orders can only be done once a week per user",
            "===",
            ActionRow(button, refresh_button),
        )
        view.add_item(embed)
        return view

    await message.response.send_message(view=await gen_bakery())


@bot.tree.command(description="Gamble your life savings away in our totally-not-rigged catsino!")
async def casino(message: discord.Interaction):
    assert message.guild is not None
    if (message.guild.id, message.user.id) in casino_lock:
        await message.response.send_message(
            "you get kicked out of the catsino because you are already there, and two of you playing at once would cause a glitch in the universe",
            ephemeral=True,
        )
        await achemb(message, "paradoxical_gambler", "followup")
        return

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    # funny global gamble counter cus funny
    total_sum = await _get_pool().fetchval("SELECT sum_gambles FROM profile_sums_mv;")
    embed = discord.Embed(
        title="🎲 The Catsino",
        description=f"One spin costs 5 {get_emoji('finecat')} Fine cats\nSo far you gambled {profile.gambles} times.\nAll Cat Bot users gambled {total_sum:,} times.",
        color=Colors.maroon,
    )

    async def spin(interaction: discord.Interaction) -> None:
        nonlocal message
        assert message.guild is not None
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        if (message.guild.id, message.user.id) in casino_lock:
            await interaction.response.send_message(
                "you get kicked out of the catsino because you are already there, and two of you playing at once would cause a glitch in the universe",
                ephemeral=True,
            )
            return

        await profile.refresh_from_db()
        if profile.cat_Fine < 5:
            await interaction.response.send_message("you are too broke now", ephemeral=True)
            await achemb(interaction, "broke", "followup")
            return

        await interaction.response.defer()
        amount = random.randint(1, 5)
        casino_lock.add((message.guild.id, message.user.id))
        profile.cat_Fine += amount - 5
        profile.gambles += 1
        await profile.save()

        if profile.gambles >= 10:
            await achemb(message, "gambling_one", "followup")
        if profile.gambles >= 50:
            await achemb(message, "gambling_two", "followup")

        variants = [
            f"{get_emoji('egirlcat')} 1 eGirl cat",
            f"{get_emoji('egirlcat')} 3 eGirl cats",
            f"{get_emoji('ultimatecat')} 2 Ultimate cats",
            f"{get_emoji('corruptcat')} 7 Corrupt cats",
            f"{get_emoji('divinecat')} 4 Divine cats",
            f"{get_emoji('epiccat')} 10 Epic cats",
            f"{get_emoji('professorcat')} 5 Professor cats",
            f"{get_emoji('realcat')} 2 Real cats",
            f"{get_emoji('legendarycat')} 5 Legendary cats",
            f"{get_emoji('mythiccat')} 2 Mythic cats",
            f"{get_emoji('8bitcat')} 7 8bit cats",
        ]

        random.shuffle(variants)

        for i in variants:
            embed = discord.Embed(title="🎲 The Catsino", description=f"**{i}**", color=Colors.maroon)
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass
            await asyncio.sleep(1)

        embed = discord.Embed(
            title="🎲 The Catsino",
            description=f"You won:\n**{get_emoji('finecat')} {amount} Fine {plural('cat', amount)}**",
            color=Colors.maroon,
        )

        button = Button(label="Spin", style=ButtonStyle.blurple)
        button.callback = spin

        myview = View(timeout=VIEW_TIMEOUT)
        myview.add_item(button)

        casino_lock.discard((message.guild.id, message.user.id))

        await interaction.edit_original_response(embed=embed, view=myview)

    button = Button(label="Spin", style=ButtonStyle.blurple)
    button.callback = spin

    myview = View(timeout=VIEW_TIMEOUT)
    myview.add_item(button)

    await message.response.send_message(embed=embed, view=myview)


@bot.tree.command(description="oh no")
async def slots(message: discord.Interaction):
    assert message.guild is not None
    if (message.guild.id, message.user.id) in slots_lock:
        await message.response.send_message(
            "you get kicked from the slot machine because you are already there, and two of you playing at once would cause a glitch in the universe",
            ephemeral=True,
        )
        await achemb(message, "paradoxical_gambler", "followup")
        return

    debt_debounce = False

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    totals = await _get_pool().fetchrow("SELECT sum_spins, sum_wins, sum_big_wins FROM profile_sums_mv;")
    total_spins, total_wins, total_big_wins = totals["sum_spins"], totals["sum_wins"], totals["sum_big_wins"]
    embed = discord.Embed(
        title=":slot_machine: The Slot Machine",
        description=f"__Your stats__\n{profile.slot_spins:,} spins\n{profile.slot_wins:,} wins\n{profile.slot_big_wins:,} big wins\n\n__Global stats__\n{total_spins:,} spins\n{total_wins:,} wins\n{total_big_wins:,} big wins",
        color=Colors.maroon,
    )

    async def remove_debt(interaction: discord.Interaction) -> None:
        nonlocal message, debt_debounce
        if interaction.user.id != message.user.id or debt_debounce:
            await do_funny(interaction)
            return
        debt_debounce = True
        await profile.refresh_from_db()

        # remove debt
        for i in cattypes:
            profile[f"cat_{i}"] = max(0, profile[f"cat_{i}"])

        await profile.save()
        await interaction.response.send_message("You have removed your debts! Life is wonderful!", ephemeral=True)
        await achemb(interaction, "debt", "followup")

    async def spin(interaction: discord.Interaction) -> None:
        nonlocal message, debt_debounce
        assert message.guild is not None
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        if (message.guild.id, message.user.id) in slots_lock:
            await interaction.response.send_message(
                "you get kicked from the slot machine because you are already there, and two of you playing at once would cause a glitch in the universe",
                ephemeral=True,
            )
            return
        await profile.refresh_from_db()

        await interaction.response.defer()
        slots_lock.add((message.guild.id, message.user.id))
        profile.slot_spins += 1
        await profile.save()

        try:
            await achemb(interaction, "slots", "followup")
            await progress(message, profile, "slots2")
        except Exception:
            pass

        variants = ["🍒", "🍋", "🍇", "🔔", "⭐", ":seven:"]
        reel_durations = [random.randint(9, 12), random.randint(15, 22), random.randint(25, 28)]
        random.shuffle(reel_durations)

        # the k number is much cycles it will go before stopping + 1
        col1 = random.choices(variants, k=reel_durations[0])
        col2 = random.choices(variants, k=reel_durations[1])
        col3 = random.choices(variants, k=reel_durations[2])

        if message.user.id in rigged_users:
            col1[len(col1) - 2] = ":seven:"
            col2[len(col2) - 2] = ":seven:"
            col3[len(col3) - 2] = ":seven:"

        blank_emoji = get_emoji("empty")
        current1, current2, current3 = 0, 0, 0
        desc = ""
        for slot_loop_ind in range(1, max(reel_durations) - 1):
            current1 = min(len(col1) - 2, slot_loop_ind)
            current2 = min(len(col2) - 2, slot_loop_ind)
            current3 = min(len(col3) - 2, slot_loop_ind)
            desc = ""
            for offset in [-1, 0, 1]:
                if offset == 0:
                    desc += f"➡️ {col1[current1 + offset]} {col2[current2 + offset]} {col3[current3 + offset]} ⬅️\n"
                else:
                    desc += f"{blank_emoji} {col1[current1 + offset]} {col2[current2 + offset]} {col3[current3 + offset]} {blank_emoji}\n"
            embed = discord.Embed(
                title=":slot_machine: The Slot Machine",
                description=desc,
                color=Colors.maroon,
            )
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass
            await asyncio.sleep(0.5)

        await profile.refresh_from_db()
        big_win = False
        if col1[current1] == col2[current2] == col3[current3]:
            profile.slot_wins += 1
            if col1[current1] == ":seven:":
                desc = "**BIG WIN!**\n\n" + desc
                profile.slot_big_wins += 1
                big_win = True
                await profile.save()
                await achemb(interaction, "big_win_slots", "followup")
            else:
                desc = "**You win!**\n\n" + desc
                await profile.save()
            await achemb(interaction, "win_slots", "followup")
        else:
            desc = "**You lose!**\n\n" + desc

        button = Button(label="Spin", style=ButtonStyle.blurple)
        button.callback = spin

        myview = View(timeout=VIEW_TIMEOUT)
        myview.add_item(button)

        if big_win:
            # check if user has debt in any cat type
            has_debt = False
            for i in cattypes:
                if profile[f"cat_{i}"] < 0:
                    has_debt = True
                    break
            if has_debt:
                debt_debounce = False
                desc += "\n\n**You can remove your debt!**"
                button = Button(label="Remove Debt", style=ButtonStyle.blurple)
                button.callback = remove_debt
                myview.add_item(button)

        slots_lock.discard((message.guild.id, message.user.id))

        embed = discord.Embed(title=":slot_machine: The Slot Machine", description=desc, color=Colors.maroon)

        try:
            await interaction.edit_original_response(embed=embed, view=myview)
        except Exception:
            await interaction.followup.send(embed=embed, view=myview)

    button = Button(label="Spin", style=ButtonStyle.blurple)
    button.callback = spin

    myview = View(timeout=VIEW_TIMEOUT)
    myview.add_item(button)

    await message.response.send_message(embed=embed, view=myview)


@bot.tree.command(description="what")
async def roulette(message: discord.Interaction):
    assert message.guild is not None
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    # this is the silly popup when you click the button
    class RouletteModel(Modal):
        def __init__(self) -> None:
            super().__init__(
                title="place a bet idfk",
                timeout=VIEW_TIMEOUT,
            )

            self.bettype = TextInput(
                min_length=1,
                max_length=5,
                label="choose a bet",
                style=discord.TextStyle.short,
                required=True,
                placeholder="red / black / green / 0 / 1 / 2 / 3 / ... / 36",
            )
            self.add_item(self.bettype)

            self.betamount = TextInput(
                min_length=1,
                label="bet amount (in cat dollars)",
                style=discord.TextStyle.short,
                required=True,
                placeholder="69",
            )
            self.add_item(self.betamount)

        async def on_submit(self, interaction: discord.Interaction) -> None:
            await user.refresh_from_db()

            valids = ["red", "black", "green"] + [str(i) for i in range(37)]
            if self.bettype.value.lower() not in valids:
                await interaction.response.send_message("invalid bet", ephemeral=True)
                return

            try:
                bet_amount = int(self.betamount.value)
                if bet_amount <= 0:
                    await interaction.response.send_message("bet amount must be greater than 0", ephemeral=True)
                    return
                if bet_amount > max(user.roulette_balance, 100):
                    await interaction.response.send_message(f"your max bet is {max(user.roulette_balance, 100)}", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("invalid bet amount", ephemeral=True)
                return

            await interaction.response.defer()

            colors = data.roulette_colors

            emoji_map = {
                "red": "🔴",
                "black": "⚫",
                "green": "🟢",
            }

            final_choice = random.randint(0, 36)
            user.roulette_balance -= bet_amount
            user.roulette_spins += 1
            win = False
            funny_win = False
            if str(final_choice) == self.bettype.value or colors[final_choice] == self.bettype.value.lower():
                if self.bettype.value in [str(i) for i in range(37)] or self.bettype.value.lower() == "green":
                    user.roulette_balance += bet_amount * 36
                    funny_win = True
                else:
                    user.roulette_balance += bet_amount * 2
                user.roulette_wins += 1
                win = True
            user.roulette_balance = round(user.roulette_balance)
            await user.save()

            for wait_time in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.5]:
                choice = random.randint(0, 36)
                color = colors[choice]
                embed = discord.Embed(
                    color=Colors.maroon,
                    title="woo its spinnin",
                    description=f"your bet is {bet_amount:,} {plural('cat dollar', bet_amount)} on {self.bettype.value.capitalize()}\n\n{emoji_map[color]} **{choice}**",
                )
                await interaction.edit_original_response(embed=embed, view=None)
                await asyncio.sleep(wait_time)

            color = colors[final_choice]

            broke_suffix = ""
            if user.roulette_balance <= 0:
                broke_suffix = "\ndebt is allowed - you can still gamble up to **100** cat dollars"

            embed = discord.Embed(
                color=Colors.maroon,
                title="winner!!!" if win else "womp womp",
                description=f"your bet was {bet_amount:,} {plural('cat dollar', bet_amount)} on {self.bettype.value.capitalize()}\n\n{emoji_map[color]} **{final_choice}**\n\nyour new balance is **{user.roulette_balance:,}** {plural('cat dollar', user.roulette_balance)}{broke_suffix}",
            )
            view = View(timeout=VIEW_TIMEOUT)
            b = Button(label="spin", style=ButtonStyle.blurple)
            b.callback = modal_select
            view.add_item(b)
            await interaction.edit_original_response(embed=embed, view=view)

            if win:
                await progress(message, user, "roulette")
                await achemb(interaction, "roulette_winner", "followup")
            if funny_win:
                await achemb(interaction, "roulette_prodigy", "followup")
            if user.roulette_balance < 0:
                await achemb(interaction, "failed_gambler", "followup")

    async def modal_select(interaction: discord.Interaction) -> None:
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        await interaction.response.send_modal(RouletteModel())

    broke_suffix = ""
    if user.roulette_balance <= 0:
        broke_suffix = "\n\ndebt is allowed - you can still gamble up to **100** cat dollars"

    embed = discord.Embed(
        color=Colors.maroon,
        title="hecking roulette table",
        description=f"your balance is **{user.roulette_balance:,}** {plural('cat dollar', user.roulette_balance)}{broke_suffix}",
    )

    view = View(timeout=VIEW_TIMEOUT)
    b = Button(label="spin", style=ButtonStyle.blurple)
    b.callback = modal_select
    view.add_item(b)

    await message.response.send_message(embed=embed, view=view)

    if user.roulette_balance < 0:
        await achemb(message, "failed_gambler", "followup")


@bot.tree.command(description="absolute CHAOS")
async def chaos(message: discord.Interaction):
    assert message.guild is not None

    async def click(interaction: discord.Interaction, first: bool = False) -> None:
        assert bot.user is not None
        assert message.guild is not None
        cookies = await _get_pool().fetchrow(
            """INSERT INTO profile (guild_id, user_id, cookies)
            VALUES (666, $1, 1)
            ON CONFLICT (guild_id, user_id)
            DO UPDATE SET cookies = profile.cookies + $2
            RETURNING cookies;""",
            bot.user.id,
            random.randint(0, 1000),
        )
        cookies = cookies["cookies"]

        view = LayoutView(timeout=VIEW_TIMEOUT)
        b = Button(label="Chaos!", style=ButtonStyle.red, emoji="💥")
        b.callback = click
        view.add_item(
            Container(
                f"## {cookies:,}",
                "the number above is global for everyone. click the button to add a random number to it.",
                b,
            )
        )

        if first:
            await interaction.response.send_message(view=view)
        else:
            await interaction.response.edit_message(view=view)

        profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=interaction.user.id)
        if profile.misc_quest.strip() == "chaos":
            await progress(message, profile, "chaos")

    await click(message, True)


@bot.tree.command(description="roll a dice")
async def roll(message: discord.Interaction, sides: int | None = None):
    if sides is None:
        sides = 6

    if sides < 0:
        await message.response.send_message("???", ephemeral=True)
        return

    assert message.guild is not None
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    if sides == 0:
        if user.sphere_easter_egg < len(data.family_guy_funny_moments):
            await message.response.send_message(data.family_guy_funny_moments[user.sphere_easter_egg], ephemeral=True)
            user.sphere_easter_egg += 1
            await user.save()

            if user.sphere_easter_egg == len(data.family_guy_funny_moments):
                await achemb(message, "sphere_ach", "followup")
        else:
            await message.response.send_message(random.choice(data.family_guy_funny_moments), ephemeral=True)

        return

    dice = data.dice_names.get(str(sides), f"d{sides}")

    view = View(timeout=VIEW_TIMEOUT)
    button = Button(label="Reroll", emoji="🎲", style=ButtonStyle.blurple)
    view.add_item(button)

    roll_number = 0

    async def roll_and_respond(interaction: discord.Interaction, is_first: bool = False) -> None:
        nonlocal roll_number
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        roll_number += 1
        roll = random.randint(1, sides)
        if sides == 2:
            side = "heads" if roll == 1 else "tails"
            text = f"🪙 your coin lands on **{side}** ({roll})"
        else:
            text = f"🎲 your {dice} lands on **{roll}**"

        if is_first:
            await interaction.response.send_message(text, view=view)
        else:
            button.label = f"Reroll ({roll_number})"
            await interaction.response.edit_message(content=text, view=view)

        if sides == 6 and roll == 6:
            await progress(message, user, "roll")

    button.callback = roll_and_respond
    await roll_and_respond(message, is_first=True)


@bot.tree.command(description="get a super accurate rating of something")
@discord.app_commands.describe(thing="The thing or person to check", stat="The stat to check")
async def rate(message: discord.Interaction, thing: str, stat: str):
    if len(thing) > 100 or len(stat) > 100:
        await message.response.send_message("thats kinda long", ephemeral=True)
        return
    if thing.lower() == "/rate" and stat.lower() == "correct":
        await message.response.send_message("/rate is 100% correct")
    else:
        await message.response.send_message(f"{thing} is {random.randint(0, 100)}% {stat}")


@bot.tree.command(name="8ball", description="ask the magic catball")
@discord.app_commands.describe(question="your question to the catball")
async def eightball(message: discord.Interaction, question: str):
    if len(question) > 300:
        await message.response.send_message("thats kinda long", ephemeral=True)
        return

    await message.response.send_message(f"{question}\n:8ball: **{random.choice(data.catball_responses)}**")

    await achemb(message, "balling", "followup")


@bot.tree.command(description="The best Artificial Catelligence on the Planet")
@discord.app_commands.describe(query="Your query to CatGPT")
async def catgpt(message: discord.Interaction, query: str):
    await message.response.defer(thinking=True)

    # initial random noise
    a = [random.gauss(0, 1.0) for _ in range(128)]
    b = math.fsum(a)
    for _ in range(11):
        b = math.tanh(b) + math.atan(math.sin(b))
    c = [[(i * j + b) % 1.0 for j in range(6)] for i in range(6)]
    d = sum(c[i][i] for i in range(6))

    # sentiment analysis
    e = 0.0
    for n in range(1, 73):
        e += math.sin(n * b) / (n * n) + ord(query[n % len(query)])
    f = math.sin(d) ** 2 + math.cos(d) ** 2 - 1
    e = int(e)
    g = ((e & ~e) - (e & ~e)) + f

    # main loop
    h = 0xC0FFEE
    for _ in range(13):
        h = (((h << 5) ^ (h >> 3)) + 0x5A5A5A5A) & 0xFFFFFFFF
        h ^= (h >> 11) & 0xDEADBEEF
        await asyncio.sleep(0.5)  # make sure the beef is dead

    # convert the values back to text
    i = ((h ^ h) | (h & 0)) >> 4
    j = (i << 17) ^ ((i + 1) - 1)
    k = (j | (j << 3) | (j >> 2)) & 0xFF
    L = ((k << 5) ^ (k >> 2)) & 0xFF
    p = int(math.pi**4 + g) ^ k
    q = int(math.e + abs(g)) | (L << 1)
    r = int(math.factorial(5) - int(math.pi + math.cos(g))) ^ (k | L)
    s = [
        ((p + q) | k) ^ L,
        (p | (k << 4)) & (~L & 0xFF),
        (r ^ (k & 0xF0)) | (L >> 3),
    ]
    t = sum(random.randint(0, 9) for _ in range(32)) & 0
    u = ((t << 9) ^ (t >> 1)) & 0
    result = "".join(chr(((x ^ t) & 0x7F) | u) for x in s)

    await message.followup.send(f"{result}\n-# ℹ️ CatGPT can't make mistakes.")
    await achemb(message, "catgpt", "followup")


@bot.tree.command(description="the most engaging boring game")
async def pig(message: discord.Interaction):
    assert message.guild is not None
    score = 0
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    async def roll(interaction: discord.Interaction) -> None:
        nonlocal score
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        if score == 0:
            # dont roll 1 on first roll
            roll_result = random.randint(2, 6)
        else:
            roll_result = random.randint(1, 6)

        if roll_result == 1:
            # gg
            last_score = score
            score = 0
            view = View(timeout=VIEW_TIMEOUT)
            button = Button(label="Play Again", emoji="🎲", style=ButtonStyle.blurple)
            button.callback = roll
            view.add_item(button)
            await interaction.response.edit_message(
                content=f"*Oops!* You rolled a **1** and lost your {last_score} score...\nFinal score: 0\nBetter luck next time!", view=view
            )
        else:
            score += roll_result
            view = View(timeout=VIEW_TIMEOUT)
            button = Button(label="Roll", emoji="🎲", style=ButtonStyle.blurple)
            button.callback = roll
            button2 = Button(label="Save & Finish")
            button2.callback = finish
            view.add_item(button)
            view.add_item(button2)
            await interaction.response.edit_message(content=f"🎲 +{roll_result}\nCurrent score: {score:,}", view=view)

    async def finish(interaction: discord.Interaction):
        nonlocal score
        if interaction.user != message.user:
            await do_funny(interaction)
            return
        await profile.refresh_from_db()

        if score > profile.best_pig_score:
            profile.best_pig_score = score
            await profile.save()

        last_score = score
        score = 0
        view = View(timeout=VIEW_TIMEOUT)
        button = Button(label="Play Again", emoji="🎲", style=ButtonStyle.blurple)
        button.callback = roll
        view.add_item(button)
        await interaction.response.edit_message(content=f"*Congrats!*\nYou finished with {last_score} score!", view=view)

        if last_score >= 50:
            await progress(message, profile, "pig")
            await achemb(interaction, "pig50", "followup")
        if last_score >= 100:
            await achemb(interaction, "pig100", "followup")

    view = View(timeout=VIEW_TIMEOUT)
    button = Button(label="Play!", emoji="🎲", style=ButtonStyle.blurple)
    button.callback = roll
    view.add_item(button)
    await message.response.send_message(
        f"🎲 Pig is a simple dice game. You repeatedly roll a die. The number it lands on gets added to your score, then you can either roll the die again, or finish and save your current score. However, if you roll a 1, you lose and your score gets voided.\n\nYour current best score is **{profile.best_pig_score:,}**.",
        view=view,
    )


@bot.tree.command(description="get a reminder in the future (+- 1 minute)")
@discord.app_commands.describe(
    days="in how many days",
    hours="in how many hours",
    minutes="in how many minutes (+- 1 minute)",
    text="what to remind",
)
async def remind(
    message: discord.Interaction,
    days: int | None = None,
    hours: int | None = None,
    minutes: int | None = None,
    text: str | None = None,
):
    assert message.guild is not None
    if not days:
        days = 0
    if not hours:
        hours = 0
    if not minutes:
        minutes = 0
    if not text:
        text = "Reminder!"

    goal_time = int(time.time() + (days * 86400) + (hours * 3600) + (minutes * 60))
    if goal_time > time.time() + (86400 * 365 * 20):
        await message.response.send_message("cats do not live for that long", ephemeral=True)
        return
    if len(text) > 1900:
        await message.response.send_message("thats too long", ephemeral=True)
        return
    if goal_time < 0:
        await message.response.send_message("cat cant time travel (yet)", ephemeral=True)
        return
    msg = await message.response.send_message(f"🔔 ok, <t:{goal_time}:R> (+- 1 min) ill remind you of:\n{text}")
    assert isinstance(msg.resource, discord.InteractionMessage)
    message_link = msg.resource.jump_url
    text += f"\n\n*This is a [reminder](<{message_link}>) you set.*"
    await Reminder.create(user_id=message.user.id, text=text, time=goal_time)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    profile.reminders_set += 1
    await profile.save()
    await achemb(message, "reminder", "followup")  # the ai autocomplete thing suggested this and its actually a cool ach


@bot.tree.command(name="random", description="Get a random cat")
async def random_cat(message: discord.Interaction):
    try:
        async with (
            aiohttp.ClientSession() as session,
            session.get("https://api.thecatapi.com/v1/images/search", headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"}) as response,
        ):
            data = await response.json()
            await message.response.send_message(data[0]["url"])
    except Exception:
        await message.response.send_message("no cats :(")

    await achemb(message, "randomizer", "followup")


if config.WORDNIK_API_KEY:

    @bot.tree.command(description="define a word")
    async def define(message: discord.Interaction, word: str):
        word = word.lower()
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    f"https://api.wordnik.com/v4/word.json/{word}/definitions?api_key={config.WORDNIK_API_KEY}&useCanonical=true&includeTags=false&includeRelated=false&limit=69",
                    headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"},
                ) as response,
            ):
                data = await response.json()

                # lazily filter some things
                text = (await response.text()).lower()

                # sometimes the api returns results without definitions, so we search for the first one which has a definition
                for i in data:
                    if "text" in i:
                        clean_data = re.sub(re.compile("<.*?>"), "", i["text"])
                        await message.response.send_message(
                            f"__{word}__\n{clean_data}\n-# [{i['attributionText']}](<{i['attributionUrl']}>) Powered by [Wordnik](<{i['wordnikUrl']}>)",
                            ephemeral=any(test in text for test in ["vulgar", "slur", "offensive", "profane", "insult", "abusive", "derogatory"]),
                        )
                        await achemb(message, "define", "followup")
                        return

                raise LookupError
        except Exception:
            await message.response.send_message("no definition found", ephemeral=True)


@bot.tree.command(name="fact", description="get a random cat fact")
async def cat_fact(message: discord.Interaction):
    assert message.guild is not None
    assert isinstance(message.channel, GuildMessageable)
    facts = [
        "you love cats",
        f"cat bot is in {f'{server_count:,}' if server_count else '...'} servers",
        "cat",
        "cats are the best",
    ]

    # give a fact from the list or the file
    if random.randint(0, 10) == 0:
        await message.response.send_message(random.choice(facts))
    else:
        await message.response.send_message(random.choice(cat_facts_list))

    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    user.facts += 1
    await user.save()
    if user.facts >= 10:
        await achemb(message, "fact_enjoyer", "followup")

    try:
        channel = await Channel.get_or_none(channel_id=message.channel.id)
        if channel and channel.cattype == "Professor":
            await achemb(message, "nerd_battle", "followup")
    except Exception:
        pass


BOUNTY_SLOTS = ("one", "two", "three")


def _bounty_title(bid: int, total: int, btype: str) -> str:
    if bid == 0:
        return f"Catch {total} {plural('cat', total)}"
    elif bid == 1:
        return f"Catch {total} {btype} {plural('cat', total)}"
    else:
        return f"Catch {total} {btype} or rarer {plural('cat', total)}"


def _bounty_matches(bid: int, btype: str, cattype: str) -> bool:
    if bid == 0:
        return True
    elif bid == 1:
        return cattype == btype
    else:
        return cattypes.index(cattype) >= cattypes.index(btype)


def _bounties_are_complete(user: Profile) -> bool:
    return all(user[f"bounty_progress_{slot}"] >= user[f"bounty_total_{slot}"] for slot in BOUNTY_SLOTS[: user.bounties])


def _bounty_progress_segments(user: Profile, segments: int = 10) -> int:
    if not (slots := BOUNTY_SLOTS[: user.bounties]):
        return segments

    average_progress = sum(user[f"bounty_progress_{slot}"] / user[f"bounty_total_{slot}"] for slot in slots) / len(slots)
    return max(0, min(segments, int(average_progress * segments)))


async def bounty(message: discord.Message, user: Profile, cattype: str) -> None:
    if user.hibernation or user.catnip_active < time.time():
        return

    newly_completed_titles = []
    completed_count = 0

    for slot in BOUNTY_SLOTS[: user.bounties]:
        bid = user[f"bounty_id_{slot}"]
        progress = user[f"bounty_progress_{slot}"]
        total = user[f"bounty_total_{slot}"]
        btype = user[f"bounty_type_{slot}"]

        if progress < total and _bounty_matches(bid, btype, cattype):
            progress = min(progress + 1, total)
            user[f"bounty_progress_{slot}"] = progress
            if progress >= total:
                newly_completed_titles.append(_bounty_title(bid, total, btype))

        if progress >= total:
            completed_count += 1

    await user.save()

    if catnip_list["levels"][user.catnip_level]["bonus"]:
        b_progress = user.bounty_progress_bonus
        b_total = user.bounty_total_bonus
        if b_progress < b_total:
            bid = user.bounty_id_bonus
            btype = user.bounty_type_bonus
            bonus_title = _bounty_title(bid, b_total, btype)
            if _bounty_matches(bid, btype, cattype):
                user.bounty_progress_bonus = min(b_progress + 1, b_total)
            if user.bounty_progress_bonus >= b_total:
                description = "Bonus Bounty Complete!\nGo to `/catnip` to reroll a perk!"
                embed = discord.Embed(title=f"✅ {bonus_title}", color=Colors.green, description=description).set_author(
                    name="Mafia Level " + str(user.catnip_level)
                )
                await message.channel.send(f"<@{user.user_id}>", embed=embed)
                user.reroll = False
                user.reroll_level = 0
            await user.save()

    for title in newly_completed_titles:
        log_stats("bounty_complete", {"title": title})
        level = user.catnip_level
        colored = _bounty_progress_segments(user)
        progress_line = f"\n{level} " + get_emoji("staring_square") * colored + "⬛" * (10 - colored) + f" {level + 1}"
        if completed_count == user.bounties:
            description = f"{progress_line}\nAll Bounties Complete!\nGo to `/catnip` to pay up and pick a perk!"
        else:
            description = f"{progress_line}\n{completed_count}/{user.bounties} Bounties Complete"
        embed = discord.Embed(title=f"✅ {title}", color=Colors.green, description=description).set_author(name="Mafia Level " + str(level))
        user.bounties_complete += 1
        if user.bounties_complete >= 5:
            await achemb(message, "bounty_novice", "reply")
        if user.bounties_complete >= 20:
            await achemb(message, "bounty_hunter", "reply")
        if user.bounties_complete >= 100:
            await achemb(message, "bounty_lord", "reply")
        await message.channel.send(f"<@{user.user_id}>", embed=embed)
        await user.save()


async def set_mafia_offer(level: int, user: Profile) -> None:
    if user.catnip_level == 0:
        user.catnip_amount = 0
        return
    level_data = catnip_list["levels"][level]
    vt = level_data["cost"]
    cattype = "Fine"
    value = None
    for _ in range(100):
        cattype = random.choice(cattypes)
        value = CAT_VALUES[cattype]
        if value <= vt:
            break
    assert value is not None
    amount = max(1, round(vt / value))
    user.catnip_price = cattype
    user.catnip_amount = amount
    await user.save()


async def set_bounties(level: int, user: Profile) -> None:
    if user.catnip_level == 0:
        user.bounties = 0
        return
    bounties = await get_bounties(level)
    bonus_check = catnip_list["levels"][level + 1]["bonus"]
    if level == 10 and user.bounty_progress_bonus != user.bounty_total_bonus and user.catnip_active > 86400:
        bonus_check = False
    if bonus_check:
        bonus = bounties.pop()
        user.bounty_id_bonus = bonus["id"]
        user.bounty_type_bonus = bonus["cat_type"]
        user.bounty_total_bonus = bonus["amount"]
        user.bounty_progress_bonus = bonus["progress"]
    else:
        bounties = bounties[:-1]
    user.bounties = len(bounties)

    for index, slot in enumerate(BOUNTY_SLOTS):
        bounty = bounties[index] if index < len(bounties) else None
        user[f"bounty_id_{slot}"] = bounty["id"] if bounty else None
        user[f"bounty_type_{slot}"] = bounty["cat_type"] if bounty else None
        user[f"bounty_total_{slot}"] = bounty["amount"] if bounty else 1
        user[f"bounty_progress_{slot}"] = bounty["progress"] if bounty else 0

    await user.save()


async def get_bounties(level: int) -> list[dict]:
    level_data = catnip_list["levels"][level + 1]
    bounties = []
    num_bounties = level_data["bounty_amount"]
    avg_cats_needed = level_data["bounty_difficulty"]
    num_max = level_data["max_amount"]

    used_types = set()
    used_rarities = set()
    tries = 0
    max_tries = 1000 * num_bounties
    while len(bounties) < num_bounties + 1 and tries < max_tries:
        tries += 1
        bounty_type = random.choice(["rarity", "specific", "any"])

        # to add a bit of randomness
        variation = random.uniform(0.85, 1.15)
        if len(bounties) == num_bounties:
            variation *= 1.5
            if level == 10:
                variation *= 10
        if bounty_type == "rarity":
            margin = 0.2
            rarity_i = random.randint(2, len(cattypes) - 2)

            while True:
                rarity = cattypes[rarity_i]
                eligible_types = cattypes[rarity_i:]

                prob = sum(data.type_dict[t] for t in eligible_types) / TOTAL_CAT_WEIGHT
                base_amount = max(1, round(avg_cats_needed * prob))
                expected_total = base_amount / prob if prob > 0 else float("inf")

                if abs(expected_total - avg_cats_needed) / avg_cats_needed <= margin or rarity_i == 0:
                    break
                rarity_i -= 1

            if rarity_i in used_rarities:
                continue

            used_rarities.add(rarity_i)
            amount = max(1, round(base_amount * variation))

            if amount > num_max:
                continue

            bounties.append(
                {"id": 2, "progress": 0, "cat_type": rarity, "amount": amount, "desc": f"Catch {amount} {plural('cat', amount)} of {rarity} rarity and above"}
            )
        elif bounty_type == "any":
            if any(b["id"] == 0 for b in bounties):
                continue

            amount = max(1, round(avg_cats_needed * variation / 2))

            if amount > num_max:
                continue

            bounties.append({"id": 0, "progress": 0, "cat_type": "", "amount": amount, "desc": f"Catch {amount} {plural('cat', amount)} of any kind"})
        else:
            # pick a specific cat type not already used
            if not (available_types := [cat for cat in cattypes if cat not in used_types]):
                continue

            available_types1 = available_types.copy()
            base_amount = None
            cat_type = None
            for _ in available_types:
                cat_type = random.choices(available_types1)[0]
                prob = data.type_dict[cat_type] / TOTAL_CAT_WEIGHT
                base_amount = avg_cats_needed * prob
                available_types1.remove(cat_type)
                if base_amount > 0.8:
                    break

            if base_amount is None or cat_type is None:
                continue

            amount = max(1, round(base_amount * variation))

            if amount > num_max:
                continue

            if level > 4 and amount < 4:
                # prevent too "luck based" bounties
                continue

            used_types.add(cat_type)
            bounties.append(
                {
                    "id": 1,
                    "progress": 0,
                    "cat_type": cat_type,
                    "amount": amount,
                    "desc": f"Catch {amount} {get_emoji(cat_type.lower() + 'cat')} {plural('cat', amount)}",
                }
            )

    return bounties


async def get_perks(level: int, user: Profile) -> list[dict]:
    level_data = catnip_list["levels"][level]
    rarities = [r for r in level_data["weights"]]
    weights = {rarity: level_data["weights"][rarity] for rarity in rarities}
    perks = catnip_list["perks"]

    current_perks = []
    used_ids = set()
    thelist = []
    if user.perks:
        for perk in user.perks:
            p = perk.split("_")
            thelist.append(perks[int(p[1]) - 1]["id"])

    for _ in range(3):
        luck = random.randint(1, 1000) / 10
        total_weight = 0
        current_rarity = "common"
        for rarity, weight in weights.items():
            total_weight += weight
            if luck <= total_weight:
                current_rarity = rarity
                break

        tries = 0
        selected_perk = None

        while tries < 100:
            luck = random.randint(1, 100)
            total_weight = 0
            i = 0
            for perk in perks:
                i += 1
                total_weight += perk["weight"]

                if perk["id"] in used_ids or (perk["exclusive"] == 1 and perk["id"] in thelist):  # me when im in thelist
                    continue

                if all("pack" in p["id"] for p in current_perks) and "pack" in perk["id"]:
                    continue

                if luck <= total_weight:
                    effect = perk["values"][list(weights.keys()).index(current_rarity)]
                    if effect == 0:
                        continue

                    selected_perk = {
                        "id": perk["id"],
                        "name": perk["name"],
                        "values": perk["values"],
                        "rarity": current_rarity,
                        "uuid": f"{list(weights.keys()).index(current_rarity)}_{i}",
                        "effect": effect,
                    }

                    break
            if selected_perk:
                break
            tries += 1

        if selected_perk:
            used_ids.add(selected_perk["id"])
            current_perks.append(selected_perk)

    return current_perks


async def level_down(user: Profile, message: discord.Interaction, ephemeral: bool = False) -> discord.Embed | None:
    if user.catnip_level == 0:
        return

    user.catnip_level -= 1
    user.catnip_active = 0

    user.hibernation = True

    for number in BOUNTY_SLOTS:
        user[f"bounty_id_{number}"] = 0
        user[f"bounty_type_{number}"] = ""
        user[f"bounty_total_{number}"] = 1
        user[f"bounty_progress_{number}"] = 0

    user.catnip_total_cats = 0

    user.first_quote_seen = False

    removed_perk = None
    if user.perks:
        h = list(user.perks)
        removed_perk = h.pop()
        user.perks = h[:]

    await set_bounties(user.catnip_level, user)
    await set_mafia_offer(user.catnip_level, user)
    await user.save()

    name = catnip_list["quotes"][user.catnip_level]["name"]
    quote = catnip_list["quotes"][user.catnip_level]["quotes"]["leveldown"].replace("jeremysus", get_emoji("jeremysus"))
    removed_line = ""

    if user.perks and removed_perk:
        rarities = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
        perk_rarity = int(removed_perk.split("_")[0])
        perk_type = int(removed_perk.split("_")[1])
        perk_data = catnip_list["perks"][perk_type - 1]

        removed_line = f"\nYou lost your **{perk_data['name']} ({rarities[perk_rarity]})** perk."

    embed = discord.Embed(
        title="❌ Mafia Level Failed",
        color=Colors.red,
        description=f"**{name}**: *{quote}*\n\nLevel {user.catnip_level + 1} bounties failed!\nYou're now on level {user.catnip_level}.{removed_line}",
    )

    log_stats("level_down", {"to": str(user.catnip_level)})

    if ephemeral:
        return embed

    assert isinstance(message.channel, GuildMessageable)
    await message.channel.send(f"<@{user.user_id}>", embed=embed)


async def mafia_cutscene(interaction: discord.Interaction, user: Profile) -> None:
    # YAPPATRON
    text1 = """You feel satisfied with yourself. I just defeated the Godfather, Bailey! I'm on top of the world now!
Little did you know, it was foolish to believe it was over just yet.
You stare Bailey down, and realize just how bizarre he is. He's very large for a cat… he wags his tail… he just feels wrong. But then, you hear it.
*Bark! Bark!*
Oh no."""
    text2 = """You immediately run. You know that he will probably be able to outpace you, but you do have a bit of a head start.
There's a split in the alley.
Left would lead to the hideout, but you'll never get there in time.
Right, however, leads to a dead end.
Which way do you go?"""
    text3a = """You dash to the left. You can see the cat door ahead, but you'll never make it out in time.
You call out for help, and think back to all of those people you defeated.
Whiskers, the Lucians, Jinx, Jeremy, Sofia.
Would any of them be willing to save you?"""
    text3b = """You dash to the right. As you turn the corner and approach the dead end, you realize that while he may go faster, you can jump higher.
You back up against the wall, wait for him to approach… and jump.
You get over him, and run the other way. With a head start, you can get into the hideout.
But Bailey isn't done yet.
He's trying to break in. You think back to all of those people you defeated.
Whiskers, the Lucians, Jinx, Jeremy, Sofia.
Would any of them be willing to save you?"""
    text4 = """You see Jinx come out first. Whiskers is just behind him.
Jeremy doesn't take much longer. The Lucians come out too, though reluctantly.
Finally, Sofia scowls and approaches.
Bailey knew he could take down one cat. Two wouldn't be that hard. But seven..?
\"This isn't the end of this...\"
Bailey puts his head down, and scampers off. But you aren't done.
You and your crew chase after him. He runs, until you corner him. He goes into the building behind him… but it's the Cat Police Station.
As you return to your hideout, you hear a howl in the distance."""

    async def button3_callback(interaction: discord.Interaction):
        await interaction.response.edit_message(content=text4, view=None)
        user.thanksforplaying = False
        user.cutscene = 1
        await user.save()
        await achemb(interaction, "thanksforplaying", "followup")

    async def button2a_callback(interaction: discord.Interaction):
        myview3 = View(timeout=VIEW_TIMEOUT)
        button3 = Button(label="Next", style=ButtonStyle.blurple)
        button3.callback = button3_callback
        myview3.add_item(button3)
        await interaction.response.edit_message(content=text3a, view=myview3)

    async def button2b_callback(interaction: discord.Interaction):
        myview3 = View(timeout=VIEW_TIMEOUT)
        button3 = Button(label="Next", style=ButtonStyle.blurple)
        button3.callback = button3_callback
        myview3.add_item(button3)
        await interaction.response.edit_message(content=text3b, view=myview3)

    async def button1_callback(interaction: discord.Interaction):
        myview2 = View(timeout=VIEW_TIMEOUT)
        button2a = Button(label="Left", style=ButtonStyle.red)
        button2b = Button(label="Right", style=ButtonStyle.green)
        button2a.callback = button2a_callback
        button2b.callback = button2b_callback
        myview2.add_item(button2a)
        myview2.add_item(button2b)
        await interaction.response.edit_message(content=text2, view=myview2)

    user.thanksforplaying = True
    await user.save()

    myview1 = View(timeout=VIEW_TIMEOUT)
    button1 = Button(label="RUN!", style=ButtonStyle.blurple)
    button1.callback = button1_callback
    myview1.add_item(button1)
    await interaction.response.send_message(content=text1, view=myview1, ephemeral=True)


async def mafia_cutscene2(interaction: discord.Interaction, user: Profile) -> None:
    text1 = """Why? What do you gain from this? What's the point?
You've gone too far. You defeated Bailey, and I was proud of you for that.
But you kept going. Just for slightly more cats.
You never cared about the people. It was all for you."""
    text2 = """I got too greedy myself. I took over the mafia far too young.
I wanted more, and more, and more. But I never went as far as you did.
I took over catnip production, and took so much for myself.
Eventually, though, someone took away my catnip.
And I realized how I had taken so much catnip, that the whole world was limited to about 4 doses a week."""
    text3 = """But you. You've left nothing for the others. You've made the most powerful catnip, but at what cost?
I can't stop you. No one can. I guess the only question is: will you stay here to torment us? Or fight on, against the world itself?
[More content coming soon! Congrats on actually making it to level 10, that's quite a feat.]"""
    text4a = """...Really? I thought you would continue your path of destruction.
So fine. Continue to torment us. You've won. Are you happy now?"""
    text4b = """woa you looked at the code! crazy. btw stella is cute"""

    async def button3a_callback(interaction: discord.Interaction):
        await interaction.response.edit_message(content=text4a, view=None)
        user.mafia_win = False
        user.cutscene = 2
        await user.save()
        await achemb(interaction, "mafia_win", "followup")

    async def button3b_callback(interaction: discord.Interaction):
        await interaction.response.edit_message(content=text4b, view=None)

    async def button2_callback(interaction: discord.Interaction):
        myview3 = View(timeout=VIEW_TIMEOUT)
        button3a = Button(label="Stay", style=ButtonStyle.green)
        button3b = Button(label="Continue", style=ButtonStyle.red, disabled=True)
        button3a.callback = button3a_callback
        button3b.callback = button3b_callback
        myview3.add_item(button3a)
        myview3.add_item(button3b)
        await interaction.response.edit_message(content=text3, view=myview3)

    async def button1_callback(interaction: discord.Interaction):
        myview2 = View(timeout=VIEW_TIMEOUT)
        button2 = Button(label="Next", style=ButtonStyle.blurple)
        button2.callback = button2_callback
        myview2.add_item(button2)
        await interaction.response.edit_message(content=text2, view=myview2)

    user.mafia_win = True
    await user.save()

    myview1 = View(timeout=VIEW_TIMEOUT)
    button1 = Button(label="'uhhhh'", style=ButtonStyle.blurple)
    button1.callback = button1_callback
    myview1.add_item(button1)
    await interaction.response.send_message(content=text1, view=myview1, ephemeral=True)


def describe_perk(perk: str, perks: list, global_user: User) -> tuple[int, dict, str]:
    perk_rarity = int(perk.split("_")[0])
    perk_data = perks[int(perk.split("_")[1]) - 1]
    effect = perk_data["values"][perk_rarity]
    desc = (
        perk_data.get("desc", "")
        .replace("percent", f"{effect:,}")
        .replace("triple_none", f"{effect / 2:g}")
        .replace("timer_add_streak", f"{global_user.vote_streak:,}")
    )
    return perk_rarity, perk_data, desc


@bot.tree.command(description="..?")
async def catnip(message: discord.Interaction):
    assert message.guild is not None
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    server = await Server.get_or_create(server_id=message.guild.id)

    if not server.do_catnip:
        await message.response.send_message("catnip is disabled in this server.", ephemeral=True)
        return

    if not user.dark_market_active:
        await message.response.send_message("You don't have access to the catnip yet. Catch more cats to unlock it!", ephemeral=True)
        return

    level_down_embed = None
    if user.catnip_active < time.time() and not user.hibernation and user.catnip_level > 0:
        level_down_embed = await level_down(user, message, True)
        assert level_down_embed is not None

    if user.catnip_amount == 0:
        await set_mafia_offer(user.catnip_level, user)

    if user.bounties == 0:
        await set_bounties(user.catnip_level, user)

    if len(user.perks) + 1 < user.catnip_level:
        user.perk_selected = False
        await user.save()

    if len(user.perks) + 1 > user.catnip_level:
        user.perks = user.perks[:-1]
        await user.save()

    level = user.catnip_level

    async def pay_catnip(interaction: discord.Interaction) -> None:
        await user.refresh_from_db()
        if level != user.catnip_level:
            await interaction.response.send_message("nice try", ephemeral=True)
            return
        if not _bounties_are_complete(user):
            await interaction.response.send_message("You haven't completed your bounties yet!", ephemeral=True)
            return
        if not user.perk_selected:
            await interaction.response.send_message("You haven't selected a perk from your previous level yet!", ephemeral=True)
            return
        if user.catnip_price:
            if user[f"cat_{user.catnip_price}"] < user.catnip_amount:
                need_more = user.catnip_amount - user[f"cat_{user.catnip_price}"]
                await interaction.response.send_message(
                    f"You don't have enough cats to pay up!\nYou need {need_more} more {user.catnip_price} {plural('cat', need_more)}.", ephemeral=True
                )
                return
            user[f"cat_{user.catnip_price}"] -= user.catnip_amount

        trigger_cutscene = False
        if user.catnip_level != 10:
            user.catnip_level += 1
            user.hibernation = True
            if user.catnip_level == 1:
                user.catnip_active = int(time.time()) + 3600
                user.perk_selected = True  # we do a bit of lying
            else:
                user.perk_selected = False
        else:
            user.catnip_active += 86400
            trigger_cutscene = True
        user.catnip_bought += 1
        user.first_quote_seen = False
        user.reroll = True

        user.highest_catnip_level = max(user.highest_catnip_level, user.catnip_level)

        await user.save()
        await set_bounties(user.catnip_level, user)
        await set_mafia_offer(user.catnip_level, user)

        log_stats("level_down", {"to": str(user.catnip_level)})

        if user.catnip_level == 8 and user.cutscene == 0:
            await mafia_cutscene(interaction, user)
        elif user.catnip_level == 10 and not trigger_cutscene:
            text = """The point of catnip IS NOT TO KEEP LEVELLING UP FOREVER.
You are meant to go up and down levels.
You get absolutely no benefit from completing level 10.
You can stop. That's okay. Seriously."""
            await interaction.response.send_message(content=text, ephemeral=True)
        elif trigger_cutscene and user.cutscene <= 1:
            await mafia_cutscene2(interaction, user)
        elif user.catnip_level > 1:
            await perk_screen(interaction)
        else:
            await interaction.response.edit_message(view=await gen_main())

    async def reroll(interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        global_user = await User.get_or_create(user_id=interaction.user.id)
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
        await user.refresh_from_db()
        perks = catnip_list["perks"]
        rarities = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
        rarity_colors = [get_emoji("common"), get_emoji("uncommon"), get_emoji("rare"), get_emoji("epic"), get_emoji("legendary")]
        emojied_options = {}
        user_perks = user.perks
        full_desc = ""

        for index, perk in enumerate(user_perks):
            perk_rarity, perk_data, desc = describe_perk(perk, perks, global_user)
            full_desc += f"{rarity_colors[perk_rarity]} {perk_data.get('name', '')} ({rarities[perk_rarity]})\n{desc}\n\n"
            emojied_options[index + 1] = (f"{perk_data.get('name', '')} ({rarities[perk_rarity]})", rarity_colors[perk_rarity], desc.replace("**", ""))

        myview = LayoutView(timeout=VIEW_TIMEOUT)
        options = [discord.SelectOption(label=f"Lv{k}: {t}", emoji=e, description=d, value=str(k)) for k, (t, e, d) in emojied_options.items()]
        perk_select = Select(
            "rr_type",
            placeholder="Select a perk to reroll",
            options=options,
            on_select=lambda interaction, level: perk_screen(interaction, int(level), True),
        )
        perk_embed = Container("# Your Perks", full_desc)
        myview.add_item(perk_embed)
        action_row = ActionRow(perk_select)
        myview.add_item(action_row)
        await interaction.response.edit_message(view=myview)

    async def view_perks(interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        global_user = await User.get_or_create(user_id=interaction.user.id)
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
        await user.refresh_from_db()
        perks = catnip_list["perks"]
        rarities = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
        rarity_colors = [get_emoji("common"), get_emoji("uncommon"), get_emoji("rare"), get_emoji("epic"), get_emoji("legendary")]
        user_perks = user.perks
        full_desc = ""

        for perk in user_perks:
            perk_rarity, perk_data, desc = describe_perk(perk, perks, global_user)
            full_desc += f"{rarity_colors[perk_rarity]} {perk_data.get('name', '')} ({rarities[perk_rarity]})\n{desc}\n\n"

        if not user_perks:
            full_desc = "You have no perks!"
        myview = LayoutView(timeout=VIEW_TIMEOUT)
        perk_embed = Container("# Your Perks", full_desc)
        myview.add_item(perk_embed)
        await interaction.response.send_message(view=myview, ephemeral=True)

    async def perk_screen(interaction: discord.Interaction, level: int = 0, reroll: bool = False) -> None:
        assert interaction.guild is not None
        global_user = await User.get_or_create(user_id=interaction.user.id)
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)

        async def select_perk(interaction: discord.Interaction) -> None:
            await user.refresh_from_db()

            if user.perk_selected and not reroll:
                await interaction.response.send_message("You have already selected a perk.", ephemeral=True)
                return
            if reroll and user.reroll:
                await interaction.response.send_message("your die rerolls through the floor", ephemeral=True)
                return
            if reroll and user.reroll_level and user.reroll_level != level:
                await interaction.response.send_message(f"you already chose to reroll level {user.reroll_level}", ephemeral=True)
                return

            h = list(user.perks) if user.perks else []
            if reroll:
                # We use level-1 because level is 1-based (Lv1, Lv2, etc) defined in the UI
                if 0 <= level - 1 < len(h):
                    h[level - 1] = interaction.custom_id
                else:
                    await interaction.response.send_message(f"Failed to reroll! Perk slot {level} not found. (Count: {len(h)})", ephemeral=True)
                    return
                # Mark reroll as consumed
                user.reroll = True
            else:
                user.perk_selected = True
                h.append(interaction.custom_id)
            user.perks = h[:]  # black magic

            user.perk1 = ""
            user.perk2 = ""
            user.perk3 = ""
            await user.save()

            log_stats("perk_select", {"level": str(user.catnip_level)})

            await interaction.response.edit_message(view=await gen_main())

        if user.perk_selected and not reroll:
            await interaction.response.send_message("You have already selected a perk.", ephemeral=True)
            return
        if reroll and user.reroll:
            await interaction.response.send_message("your die rerolls through the floor", ephemeral=True)
            return

        perks_data = catnip_list["perks"]
        rarities = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
        rarity_colors = [get_emoji("common"), get_emoji("uncommon"), get_emoji("rare"), get_emoji("epic"), get_emoji("legendary")]

        myview = LayoutView(timeout=VIEW_TIMEOUT)

        perk_embed = Container("# Select one of these perks!")

        if user.perk1 and user.perk2 and user.perk3:
            perks = [user.perk1, user.perk2, user.perk3]
        elif level:
            perks = [p["uuid"] for p in await get_perks(level, user)]
        else:
            perks = [p["uuid"] for p in await get_perks(user.catnip_level, user)]

        for i, perk in enumerate(perks):
            perk_data = perks_data[int(perk.split("_")[1]) - 1]
            effect = perk_data["values"][int(perk.split("_")[0])]

            button = Button(label="Select", style=ButtonStyle.blurple, custom_id=perk)
            button.callback = select_perk

            perk_embed.add_item(
                Section(
                    f"## {rarity_colors[int(perk.split('_')[0])]} {perk_data.get('name', '')} ({rarities[int(perk.split('_')[0])]})",
                    f"{perk_data.get('desc', '')}".replace("percent", str(effect))
                    .replace("triple_none", str(effect / 2))
                    .replace("timer_add_streak", str(global_user.vote_streak)),
                    button,
                )
            )
            perks[i] = {
                "uuid": perk,
                "name": perk_data.get("name", ""),
                "desc": perk_data.get("desc", ""),
                "rarity": perk_data.get("rarity", ""),
                "effect": effect,
            }

        user.perk1 = perks[0]["uuid"] if len(perks) > 0 else None
        user.perk2 = perks[1]["uuid"] if len(perks) > 1 else None
        user.perk3 = perks[2]["uuid"] if len(perks) > 2 else None
        if reroll:
            user.reroll_level = level
        await user.save()

        perk_embed.add_item(TextDisplay("-# The catnip timer will not start until you begin your bounties."))
        myview.add_item(perk_embed)
        await interaction.response.edit_message(view=myview)

    async def help_screen(interaction: discord.Interaction) -> None:
        desc = "Catnip is a prestige system where you pay cats to join your mafia and get perks and bounties!"
        desc += "\n\n❓ **How it works:**"
        desc += '\n- Press the "Begin" button to join the mafia and get your first perk and bounties.'
        desc += "\n- Complete your bounties and pay the fee again to level up and get more perks and better bounties!"
        desc += "\n- If you fail to pay in time, you will level down and lose your most recent perk."
        desc += "\n- The timer only starts after you press 'Begin Bounties'."
        desc += "\n\n⭐ **Perks:**"
        desc += "\nPerks give you various bonuses like a chance to double cats cought, a chance of getting packs, etc. You can view your current perks with the 'View Perks' button."
        desc += "\n\n⬆️ **Bounties:**"
        desc += "\nBounties are tasks you need to complete before you can level up. They involve catching a certain number of cats of specific types or rarities. You can view your current bounties in the catnip menu."
        help_embed = discord.Embed(title="Catnip Help", color=Colors.brown, description=desc)
        await interaction.response.send_message(embed=help_embed, ephemeral=True)

    async def start_bounties(user_id: int) -> None:
        duration = catnip_list["levels"][user.catnip_level]["duration"]
        duration_bonus = 0

        for perk in user.perks or []:
            perk_data = catnip_list["perks"][int(perk.split("_")[1]) - 1]
            if perk_data["id"] != "timer_add_streak":
                continue

            global_user = await User.get_or_create(user_id=user_id)
            hundreds, remainder = divmod(global_user.vote_streak, 100)
            duration_bonus = sum(6000 / level for level in range(1, hundreds + 1))
            duration_bonus += 60 * remainder / (hundreds + 1)
            break

        user.hibernation = False
        user.catnip_total_cats = 0
        user.catnip_active = int(time.time()) + 3600 * duration + duration_bonus
        user.pack_attempts = (3600 * duration + duration_bonus) // 60
        await user.save()
        log_stats("bounties_start", {"level": str(user.catnip_level)})

    async def begin_bounties(interaction: discord.Interaction) -> None:
        if not user.hibernation:
            await interaction.response.send_message("nice try", ephemeral=True)
            return

        async def confirm_begin(interaction: discord.Interaction) -> None:
            await start_bounties(interaction.user.id)
            await interaction.response.edit_message(content="Bounties started!", view=None)
            await main_message.edit(view=await gen_main())

        should_confirm = user.catnip_active > time.time() and user.catnip_level >= 2
        if should_confirm:
            confirmation_view = View(timeout=VIEW_TIMEOUT)
            button = Button(label="Begin Anyway", style=ButtonStyle.red)
            button.callback = confirm_begin
            confirmation_view.add_item(button)
            await interaction.response.send_message(
                f"Your catnip expires <t:{user.catnip_active}:R>.\nAre you sure you want to start your bounties now?\nThis will remove the remaining catnip time you have.",
                view=confirmation_view,
                ephemeral=True,
            )
            return

        await start_bounties(interaction.user.id)
        await interaction.response.edit_message(view=await gen_main())

    async def gen_main() -> LayoutView:
        await user.refresh_from_db()
        level = user.catnip_level
        level_data = catnip_list["levels"][level]
        rank = level_data["name"]
        change = level_data["change"]
        duration = level_data["duration"]
        bonus = level_data["bonus"]
        bounty_data = catnip_list["bounties"]
        cat_type = user.catnip_price
        amount = user.catnip_amount
        quote_list = catnip_list["quotes"][level - 1]["quotes"]
        all_complete = True
        bounties_complete = 0
        bonus_complete = False
        name = ""

        desc = "\n"
        if user.hibernation:
            desc += "\nThe timer for leveling up will **not start** until you begin your bounties.\n"

        if user.catnip_level > 0 and user.catnip_level < 11:

            def format_bounty(bounty_numstr: str) -> None:
                nonlocal desc, all_complete, bonus_complete, bounties_complete
                bounty_id = user[f"bounty_id_{bounty_numstr}"]
                bounty_type = user[f"bounty_type_{bounty_numstr}"]
                bounty_total = user[f"bounty_total_{bounty_numstr}"]
                bounty_progress = user[f"bounty_progress_{bounty_numstr}"]

                desc += "\n- "
                if bounty_progress == bounty_total:
                    desc += "✅ "
                    if bounty_numstr == "bonus":
                        bonus_complete = True
                    else:
                        bounties_complete += 1
                elif bounty_numstr != "bonus":
                    all_complete = False

                if bounty_progress == 0:
                    desc += f"{bounty_data[bounty_id]['desc']}".replace("X", str(bounty_total))
                else:
                    desc += f"{bounty_data[bounty_id]['desc']}".replace("X", str(bounty_total - bounty_progress) + " more")

                desc = desc.replace("type", f"{get_emoji(bounty_type.lower() + 'cat')} {bounty_type}")

            if not user.hibernation:
                if user.bounties == 1:
                    desc += "\n**__Bounty:__**"
                else:
                    desc += "\n**__Bounties:__**"
                for slot in BOUNTY_SLOTS[: user.bounties]:
                    format_bounty(slot)
                if bonus:
                    desc += "\n**__Bonus Bounty:__**"
                    format_bounty("bonus")
                desc += "\n"
                if not all_complete:
                    desc += f"\n**Pay Up!** {amount} {get_emoji(cat_type.lower() + 'cat')} {cat_type} after completing your bounties"
                else:
                    desc += f"\n**Pay Up!** {amount} {get_emoji(cat_type.lower() + 'cat')} {cat_type} to proceed"
            else:
                desc += "\nPress **Begin Bounties** to view your bounties and cost!"
                if user.catnip_active > time.time():
                    desc += f"\nPerks expire <t:{user.catnip_active}:R>"
                all_complete = False

            colored = _bounty_progress_segments(user)
            desc += f"\n\n**Level {level}** - {change}"
            desc += f"\n{level} " + get_emoji("staring_square") * colored + "⬛" * (10 - colored) + f" {min(10, level + 1)}"
        if level != 0 and not user.hibernation:
            if user.catnip_active - int(time.time()) < 1800:
                desc += f"\n\n**Hurry!** Levels down <t:{user.catnip_active}:R> ({duration}h total)"
            elif user.catnip_active > time.time():
                desc += f"\n\nLevels down <t:{user.catnip_active}:R> ({duration}h total)"

        if user.catnip_level:
            if not user.first_quote_seen:
                quote = quote_list["first"]
                user.first_quote_seen = True
                await user.save()
            elif all_complete:
                quote = random.choice(quote_list["levelup"])
            else:
                quote = random.choice(quote_list["normal"])
            name = catnip_list["quotes"][level - 1]["name"]
            desc = f"**{name}**: *{quote}*" + desc

        myview = LayoutView(timeout=VIEW_TIMEOUT)

        if name == "Lucian Jr":
            name = "LucianJr"  # i hate file name conventions
        filename = f"assets/images/mafia/{name}.png"

        if name == "Whiskers" and user.catnip_level == 10:
            filename = "assets/images/mafia/WhiskersII.png"
        if name == "Jeremy" and random.randint(1, 100) == 69:
            filename = "assets/images/mafia/sus.png"

        filename = "https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/refs/heads/main/" + filename

        if not desc or desc == "\n":
            embed = Container(f"# Mafia - {rank} (Lv{level})")
        else:
            embed = Container(Section(f"# Mafia - {rank} (Lv{level})", desc, Thumbnail(filename)))
        action_row = ActionRow()

        if not user.perk_selected:
            button3 = Button(label="Select Perk", style=ButtonStyle.red)
            button3.callback = perk_screen
            action_row.add_item(button3)

        if bonus_complete and not user.reroll:
            button4 = Button(label="Reroll Perk!", style=ButtonStyle.green)
            button4.callback = reroll
            action_row.add_item(button4)
        if user.catnip_level == 0:
            button = Button(label="Begin.", style=ButtonStyle.blurple)
            button.callback = pay_catnip
            action_row.add_item(button)
        elif user.hibernation:
            button = Button(label="Begin Bounties", style=ButtonStyle.blurple)
            button.callback = begin_bounties
            action_row.add_item(button)
        elif user.catnip_level < 11:

            async def reroll_warning(interaction: discord.Interaction):
                async def abandon_ship(interaction: discord.Interaction):
                    await interaction.response.edit_message(view=await gen_main())

                view2 = LayoutView(timeout=VIEW_TIMEOUT)
                button = Button(label="Continue", style=ButtonStyle.red)
                button.callback = pay_catnip
                cancel_button = Button(label="Hold on...")
                cancel_button.callback = abandon_ship
                view2.add_item(TextDisplay("Warning: You will lose your reroll if you level up now. Use it first.\nStill continue?"))
                view2.add_item(ActionRow(button, cancel_button))
                await interaction.response.edit_message(view=view2)

            button = Button(label="Pay Up!", style=ButtonStyle.blurple)
            if user.bounty_progress_bonus == user.bounty_total_bonus and user.catnip_level >= 7 and not user.reroll:
                button.callback = reroll_warning
            else:
                button.callback = pay_catnip
            button.disabled = not all_complete
            action_row.add_item(button)

        if user.catnip_level > 0:
            button1 = Button(label="View Perks", style=ButtonStyle.gray)
            button1.callback = view_perks
            action_row.add_item(button1)

        button2 = Button(emoji="💡", label="Help", style=ButtonStyle.gray)
        button2.callback = help_screen
        action_row.add_item(button2)

        embed.add_item(action_row)
        myview.add_item(embed)
        return myview

    await message.response.send_message(view=await gen_main(), ephemeral=True)
    main_message = await message.original_response()

    if level_down_embed:
        await message.followup.send(f"<@{user.user_id}>", embed=level_down_embed, ephemeral=True)
    await achemb(message, "dark_market", "followup")
    if user.cutscene >= 1:
        await achemb(message, "thanksforplaying", "followup")
    if user.cutscene == 2:
        await achemb(message, "mafia_win", "followup")


@bot.tree.command(description="View your achievements (achs)")
async def achievements(message: discord.Interaction):
    # this is very close to /inv's ach counter
    assert message.guild is not None
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    global_user = await User.get_or_create(user_id=message.user.id)

    if user.funny >= 50:
        await achemb(message, "its_not_working", "followup")

    unlocked, minus_achs, minus_achs_count = count_achievements(user)
    total_achs = len(ach_list) - minus_achs_count
    minus_achs = "" if minus_achs == 0 else f" + {minus_achs}"

    hidden_counter = 0

    # this is a single page of the achievement list
    async def gen_new(category: str) -> discord.Embed:
        nonlocal message, unlocked, total_achs, hidden_counter

        unlocked, minus_achs, minus_achs_count = count_achievements(user)
        total_achs = len(ach_list) - minus_achs_count

        if minus_achs != 0:
            minus_achs = f" + {minus_achs}"
        else:
            minus_achs = ""

        hidden_suffix = ""

        if category == "Hidden":
            hidden_suffix = '\n\nThis is a "Hidden" category. Achievements here only show up after you complete them.'
            hidden_counter += 1
        else:
            hidden_counter = 0

        newembed = discord.Embed(
            title=category,
            description=f"Achievements unlocked (total): {unlocked}/{total_achs}{minus_achs}{hidden_suffix}",
            color=Colors.brown,
        ).set_footer(text=rain_shill)

        global_user = await User.get_or_create(user_id=message.user.id)
        if len(data.news_list) > len(global_user.news_state.strip()) or global_user.news_state.strip()[last_active_article] == "0":
            newembed.set_author(name="You have unread news! /news")

        for k, v in ach_list.items():
            if v["category"] == category:
                if k == "thanksforplaying":
                    if user[k]:
                        newembed.add_field(
                            name=str(get_emoji("demonic_ach")) + " Catnip Addict",
                            value="uncover the mafia's truth",
                            inline=True,
                        )
                    else:
                        newembed.add_field(
                            name=str(get_emoji("no_demonic_ach")) + " Thanks For Playing",
                            value="complete the story",
                            inline=True,
                        )
                    continue

                icon = str(get_emoji("no_ach")) + " "
                if user[k]:
                    newembed.add_field(
                        name=str(get_emoji("ach")) + " " + v["title"],
                        value=v["description"],
                        inline=True,
                    )
                elif category != "Hidden":
                    newembed.add_field(
                        name=icon + v["title"],
                        value="???" if v["is_hidden"] else v["description"],
                        inline=True,
                    )

        return newembed

    # creates buttons at the bottom of the full view
    def insane_view_generator(category: str) -> View:
        myview = View(timeout=VIEW_TIMEOUT)

        options = [
            discord.SelectOption(label="Cat Hunt", emoji=get_emoji("staring_cat")),
            discord.SelectOption(label="Commands", emoji="🤖"),
            discord.SelectOption(label="Random", emoji="🙃"),
            discord.SelectOption(label="Silly", emoji=get_emoji("sillycat")),
            discord.SelectOption(label="Hard", emoji=get_emoji("demonic_ach")),
            discord.SelectOption(label="Hidden", emoji="❓", description="Hidden achievements only show up after you complete them."),
        ]
        select = discord.ui.Select(placeholder=category, options=options)

        async def callback_hell(interaction: discord.Interaction) -> None:
            thing = select.values[0]
            try:
                await interaction.response.edit_message(embed=await gen_new(thing), view=insane_view_generator(thing))
            except Exception:
                pass

            if hidden_counter == 3:
                await interaction.followup.send("catnip is now located in /catnip.", ephemeral=True)
            if hidden_counter == 5:
                await interaction.followup.send("catnip is now located in /catnip.", ephemeral=True)
            if hidden_counter == 10:
                await interaction.followup.send("catnip is now located in /catnip.", ephemeral=True)
            if hidden_counter == 15:
                await interaction.followup.send("I meant it. catnip is now located in /catnip.", ephemeral=True)
            if hidden_counter == 20:
                await interaction.followup.send("I really meant it. catnip is now located in /catnip.\nOh wait, did you want that achievement?", ephemeral=True)
                await achemb(message, "darkest_market", "followup")
            if hidden_counter == 50:
                await interaction.followup.send("I really, really meant it. catnip is now located in /catnip.", ephemeral=True)
            if hidden_counter == 100:
                await interaction.followup.send("Just go away.", ephemeral=True)
            if hidden_counter == 1000:
                await interaction.followup.send("911 theres a person who knocked on my door 1000 times get them out please", ephemeral=True)

        select.callback = callback_hell
        myview.add_item(select)
        return myview

    await message.response.send_message(
        embed=await gen_new("Cat Hunt"),
        ephemeral=True,
        view=insane_view_generator("Cat Hunt"),
    )

    if unlocked >= 15:
        await achemb(message, "achiever", "followup")

    if global_user.tutorial_state == 6:
        global_user.tutorial_state = 7
        await global_user.save()
        await message.followup.send(view=await get_tutorial_view(message.user.id), ephemeral=True)

    await finale(message, user)


@bot.tree.command(name="catch", description="Catch someone in 4k")
async def catch_tip(message: discord.Interaction):
    await message.response.send_message(
        f'Nope, that\'s the wrong way to do this.\nRight Click/Long Hold a message you want to catch > Select `Apps` in the popup > "{get_emoji("staring_cat")} catch"',
        ephemeral=True,
    )


async def catch(message: discord.Interaction, msg: discord.Message):
    assert message.guild is not None
    assert isinstance(message.channel, GuildMessageable)
    assert bot.user is not None
    if message.user.id in catchcooldown:
        await message.response.send_message("your phone is overheating bro chill", ephemeral=True)
        return

    try:
        member = await message.guild.fetch_member(msg.author.id)
    except Exception:
        member = msg.author
    result = await bot.loop.run_in_executor(None, msg2img.msg2img, msg, member)

    try:
        await message.response.send_message("cought in 4k", file=result)
    except Exception:
        try:
            await message.response.send_message("failed")
        except Exception:
            pass

    catchcooldown.add(message.user.id)

    await achemb(message, "4k", "followup")

    if msg.author.id == bot.user.id and "cought in 4k" in msg.content:
        await achemb(message, "8k", "followup")

    try:
        is_cat = (await Channel.get(channel_id=message.channel.id)).cat
    except Exception:
        is_cat = False

    if int(is_cat) == int(msg.id):
        await achemb(message, "not_like_that", "followup")


async def refresh_auras(message: discord.Interaction, specific_cat: str) -> None:
    assert message.guild is not None
    idx = cattypes.index(specific_cat) + 1  # psql array index starts at 1
    guild_count = await Profile.sum(f"cat_{specific_cat}", "guild_id = $1", message.guild.id)
    column = f'"cat_{specific_cat}"'
    # remove old auras
    await _get_pool().execute(
        "UPDATE profile SET cat_auras[$1] = ' ' WHERE cat_auras[$1] IN ('y', 'c', 'p', 'a') AND guild_id = $2",
        idx,
        message.guild.id,
    )

    # new auras
    aura_vals = {"y": 0.02 * guild_count, "c": 0.04 * guild_count, "p": 0.07 * guild_count}
    for aura, val in aura_vals.items():
        await _get_pool().execute(
            f"UPDATE profile SET cat_auras[$1] = $2 WHERE guild_id = $3 AND cat_auras[$1] != 'r' AND {column} > $4",
            idx,
            aura,
            message.guild.id,
            val,
        )

    # top 1 aura
    await _get_pool().execute(
        f"UPDATE profile SET cat_auras[$1] = 'a' WHERE guild_id = $2 AND {column} = (SELECT MAX({column}) FROM profile WHERE guild_id = $2) AND cat_auras[$1] != 'r'",
        idx,
        message.guild.id,
    )


@bot.tree.command(description="View the leaderboards (lbs)")
@discord.app_commands.rename(leaderboard_type="type")
@discord.app_commands.describe(
    leaderboard_type="The leaderboard type to view!",
    cat_type="The cat type to view (only for the Cats leaderboard)",
    locked="Whether to remove page switch buttons to prevent tampering",
)
@discord.app_commands.autocomplete(cat_type=lb_type_autocomplete)
async def leaderboards(
    message: discord.Interaction,
    leaderboard_type: Literal["Cats", "Value", "Fast", "Slow", "Cattlepass", "Cookies", "Fish", "Pig", "Roulette Dollars", "Prisms"] | None = None,
    cat_type: str | None = None,
    locked: bool | None = None,
):
    if not leaderboard_type:
        leaderboard_type = "Cats"
    if not locked:
        locked = False
    if cat_type and cat_type not in cattypes + ["All"]:
        await message.response.send_message("invalid cattype", ephemeral=True)
        return

    # this fat function handles a single page
    async def lb_handler(interaction: discord.Interaction, type: str, do_edit: bool = True, specific_cat: str | None = "All") -> None:
        nonlocal message
        assert message.guild is not None
        if not specific_cat:
            specific_cat = "All"

        messager = None
        interactor = None

        # leaderboard top amount
        show_amount = 15

        # refresh auras
        if type == "Cats" and specific_cat != "All":
            await refresh_auras(interaction, specific_cat)

        string = ""
        bp_season = None
        unit = None
        match type:
            case "Cats":
                unit = "cats"

                if specific_cat != "All":
                    result = await Profile.collect_limit(
                        ["user_id", f"cat_{specific_cat}", "cat_auras"],
                        f'guild_id = $1 AND "cat_{specific_cat}" > 0 ORDER BY "cat_{specific_cat}" DESC',
                        message.guild.id,
                    )
                    final_value = f"cat_{specific_cat}"
                else:
                    # dynamically generate sum expression, cast each value to bigint first to handle large totals
                    cat_columns = [f'CAST("cat_{c}" AS BIGINT)' for c in cattypes]
                    sum_expression = RawSQL("(" + " + ".join(cat_columns) + ") AS final_value")
                    result = await Profile.collect_limit(["user_id", sum_expression], "guild_id = $1 ORDER BY final_value DESC", message.guild.id)
                    final_value = "final_value"

                    # find rarest
                    rarest = None
                    rarest_holder = None
                    for i in cattypes[::-1]:
                        non_zero_count = await Profile.collect_limit("user_id", f'guild_id = $1 AND "cat_{i}" > 0', message.guild.id)
                        if len(non_zero_count) != 0:
                            rarest = i
                            rarest_holder = non_zero_count
                            break

                    if rarest and rarest_holder and specific_cat != rarest:
                        catmoji = get_emoji(rarest.lower() + "cat")
                        rarest_holder = [f"<@{i.user_id}>" for i in rarest_holder]
                        joined = ", ".join(rarest_holder)
                        if len(rarest_holder) > 10:
                            joined = f"{len(rarest_holder)} people"
                        string = f"Rarest cat: {catmoji} ({joined}'s)\n\n"
            case "Value":
                unit = "value"
                sums = []
                for i in cattypes:
                    if not i:
                        continue
                    weight = CAT_VALUES[i]
                    sums.append(f'({weight}) * "cat_{i}"')
                total_sum_expr = RawSQL("(" + " + ".join(sums) + ") AS final_value")
                result = await Profile.collect_limit(["user_id", total_sum_expr], "guild_id = $1 ORDER BY final_value DESC", message.guild.id)
                final_value = "final_value"
            case "Fast":
                unit = "sec"
                result = await Profile.collect_limit(["user_id", "time"], "guild_id = $1 AND time < 99999999999999 ORDER BY time ASC", message.guild.id)
                final_value = "time"
            case "Slow":
                unit = "h"
                result = await Profile.collect_limit(["user_id", "timeslow"], "guild_id = $1 AND timeslow > 0 ORDER BY timeslow DESC", message.guild.id)
                final_value = "timeslow"
            case "Cattlepass":
                start_date = datetime.datetime(2024, 12, 1, tzinfo=datetime.timezone.utc)
                current_date = discord.utils.utcnow() + datetime.timedelta(hours=4)
                full_months_passed = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
                bp_season = config.battle["seasons"][str(full_months_passed)]
                if current_date.day < start_date.day:
                    full_months_passed -= 1
                result = await Profile.collect_limit(
                    ["user_id", "battlepass", "progress"],
                    "guild_id = $1 AND season = $2 AND (battlepass > 0 OR progress > 0) ORDER BY battlepass DESC, progress DESC",
                    message.guild.id,
                    full_months_passed,
                )
                final_value = "battlepass"
            case "Cookies":
                unit = "cookies"
                result = await Profile.collect_limit(["user_id", "cookies"], "guild_id = $1 AND cookies > 0 ORDER BY cookies DESC", message.guild.id)
                final_value = "cookies"
            case "Pig":
                unit = "score"
                result = await Profile.collect_limit(
                    ["user_id", "best_pig_score"], "guild_id = $1 AND best_pig_score > 0 ORDER BY best_pig_score DESC", message.guild.id
                )
                final_value = "best_pig_score"
            case "Roulette Dollars":
                unit = "cat dollars"
                result = await Profile.collect_limit(
                    ["user_id", "roulette_balance"], "guild_id = $1 AND roulette_balance != 100 ORDER BY roulette_balance DESC", message.guild.id
                )
                final_value = "roulette_balance"
            case "Prisms":
                unit = "prisms"
                result = await Prism.collect_limit(
                    ["user_id", RawSQL("COUNT(*) as prism_count")],
                    "guild_id = $1 GROUP BY user_id ORDER BY prism_count DESC",
                    message.guild.id,
                    add_primary_key=False,
                )
                final_value = "prism_count"
            case "Fish":
                unit = "fishes"
                result = await Profile.collect_limit(
                    ["user_id", "fish_caught"], "guild_id = $1 AND fish_caught != 0 ORDER BY fish_caught DESC", message.guild.id
                )
                final_value = "fish_caught"
            case _:
                # qhar
                raise ValueError("Invalid leaderboard type")

        # find the placement of the person who ran the command and optionally the person who pressed the button
        interactor_placement = 0
        messager_placement = 0
        interactor_perc = None
        messager_perc = None
        for index, position in enumerate(result):
            if position["user_id"] == interaction.user.id:
                interactor_placement = index + 1
                interactor = position[final_value]
                if type == "Cattlepass":
                    assert bp_season is not None
                    if position[final_value] >= len(bp_season):
                        lv_xp_req = 2000
                    else:
                        lv_xp_req = bp_season[int(position[final_value]) - 1]["xp"]
                    interactor_perc = math.floor((100 / lv_xp_req) * position["progress"])
            if interaction.user != message.user and position["user_id"] == message.user.id:
                messager_placement = index + 1
                messager = position[final_value]
                if type == "Cattlepass":
                    assert bp_season is not None
                    if position[final_value] >= len(bp_season):
                        lv_xp_req = 2000
                    else:
                        lv_xp_req = bp_season[int(position[final_value]) - 1]["xp"]
                    messager_perc = math.floor((100 / lv_xp_req) * position["progress"])

        if type == "Slow":
            if interactor:
                interactor = round(interactor / 3600, 2)
            if messager:
                messager = round(messager / 3600, 2)

        if type == "Fast":
            if interactor:
                interactor = round(interactor, 3)
            if messager:
                messager = round(messager, 3)

        # dont show placements if they arent defined
        if interactor and type != "Fast":
            if interactor <= 0 and type != "Roulette Dollars":
                interactor_placement = 0
            if type != "Slow":
                interactor = round(interactor)
        elif interactor and type == "Fast" and interactor >= 99999999999999:
            interactor_placement = 0

        if messager and type != "Fast":
            if messager <= 0 and type != "Roulette Dollars":
                messager_placement = 0
            if type != "Slow":
                messager = round(messager)
        elif messager and type == "Fast" and messager >= 99999999999999:
            messager_placement = 0

        emoji = ""

        # the little place counter
        current = 1
        leader = False
        for i in result[:show_amount]:
            num = i[final_value]

            if type == "Cattlepass":
                assert bp_season is not None
                if i[final_value] >= len(bp_season):
                    lv_xp_req = 2000
                else:
                    lv_xp_req = bp_season[int(i[final_value]) - 1]["xp"]
                prog_perc = math.floor((100 / lv_xp_req) * i["progress"])
                string += f"{current}. Level **{num}** *({prog_perc}%)*: <@{i['user_id']}>\n"
            else:
                if type == "Value":
                    if num <= 0:
                        break
                    num = round(num)
                elif type == "Fast" or type == "Slow":
                    if num >= 99999999999999 or num <= 0:
                        break
                    if num >= 31536000:
                        num = round(num / 31536000, 2)
                        unit = "yrs"
                    elif num >= 86400:
                        num = round(num / 86400, 2)
                        unit = "days"
                    elif num >= 3600:
                        num = round(num / 3600, 2)
                        unit = "hrs"
                    elif num >= 60:
                        num = round(num / 60, 2)
                        unit = "mins"
                    elif num >= 1:
                        num = round(num, 2)
                        unit = "sec"
                    else:
                        num = round(num, 3)
                        unit = "sec"
                elif type in ["Cookies", "Cats", "Pig", "Prisms", "Fish"] and num <= 0 or type == "Roulette Dollars" and num == 100:
                    break
                if type == "Cats" and specific_cat != "All":
                    emoji = get_aura_emoji(specific_cat, i["cat_auras"])
                assert unit is not None
                string += f"{current}. {emoji} **{num:,}** {unit}: <@{i['user_id']}>\n"

            if message.user.id == i["user_id"] and current <= 5:
                leader = True
            current += 1

        if type == "Cats" and specific_cat != "All":
            emoji = get_emoji(f"{specific_cat.lower()}cat")
        # add the messager and interactor
        if messager_placement > show_amount or interactor_placement > show_amount:
            string += "...\n"

            # setting up names
            include_interactor = interactor_placement > show_amount and str(interaction.user.id) not in string
            include_messager = messager_placement > show_amount and str(message.user.id) not in string
            interactor_line = ""
            messager_line = ""
            if include_interactor:
                if type == "Cattlepass":
                    assert interactor_perc is not None
                    interactor_line = f"{interactor_placement}\\. Level **{interactor}** *({interactor_perc}%)*: {interaction.user.mention}\n"
                else:
                    interactor_line = f"{interactor_placement}\\. {emoji} **{interactor:,}** {unit}: {interaction.user.mention}\n"
            if include_messager:
                if type == "Cattlepass":
                    assert messager_perc is not None
                    messager_line = f"{messager_placement}\\. Level **{messager}** *({messager_perc}%)*: {message.user.mention}\n"
                else:
                    messager_line = f"{messager_placement}\\. {emoji} **{messager:,}** {unit}: {message.user.mention}\n"

            # sort them correctly!
            if messager_placement > interactor_placement:
                # interactor should go first
                string += interactor_line
                string += messager_line
            else:
                # messager should go first
                string += messager_line
                string += interactor_line

        title = type + " Leaderboard"
        if type == "Cats":
            title = f"{specific_cat} {title}"
        title = "🏅 " + title

        embedVar = discord.Embed(title=title, description=string.rstrip(), color=Colors.brown).set_footer(text=rain_shill)

        global_user = await User.get_or_create(user_id=message.user.id)

        if len(data.news_list) > len(global_user.news_state.strip()) or global_user.news_state.strip()[last_active_article] == "0":
            embedVar.set_author(name=f"{message.user} has unread news! /news")

        # handle funny buttons
        myview = View(timeout=VIEW_TIMEOUT)

        dropdown = None
        if type == "Cats":
            dd_opts = [discord.SelectOption(label="All", emoji=get_emoji("staring_cat"), value="All", default=specific_cat == "All")]

            for i in await cats_in_server(message.guild.id):
                dd_opts.append(discord.SelectOption(label=i, emoji=get_emoji(i.lower() + "cat"), value=i, default=specific_cat == i))

            dropdown = Select(
                "cat_type_dd",
                placeholder="Select a cat type",
                options=dd_opts,
                on_select=lambda interaction, option: lb_handler(interaction, type, True, option),
                disabled=locked,
            )

        emojied_options = {
            "Cats": "🐈",
            "Value": "🧮",
            "Fast": "⏱️",
            "Slow": "💤",
            "Cattlepass": "⬆️",
            "Cookies": "🍪",
            "Fish": "🐟",
            "Pig": "🎲",
            "Roulette Dollars": "💰",
            "Prisms": get_emoji("prism"),
        }
        options = [discord.SelectOption(label=k, emoji=v) for k, v in emojied_options.items()]
        lb_select = Select(
            "lb_type",
            placeholder=type,
            options=options,
            on_select=lambda interaction, type: lb_handler(interaction, type, True),
        )

        if not locked:
            myview.add_item(lb_select)
            if type == "Cats":
                assert dropdown is not None
                myview.add_item(dropdown)

        # just send if first time, otherwise edit existing
        try:
            if not do_edit:
                raise ValueError
            await interaction.response.edit_message(embed=embedVar, view=myview)
        except Exception:
            await interaction.response.send_message(embed=embedVar, view=myview)

        if leader:
            await achemb(message, "leader", "followup")

        if global_user.tutorial_state == 5:
            global_user.tutorial_state = 6
            await global_user.save()
            await interaction.followup.send(view=await get_tutorial_view(message.user.id), ephemeral=True)

        for cat in cattypes:
            await refresh_auras(interaction, cat)

    await lb_handler(message, leaderboard_type, False, cat_type)


@bot.tree.command(description="(ADMIN) Give cats to people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="who", amount="how many (negatives to remove)", cat_type="what")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def givecat(message: discord.Interaction, person_id: discord.User, cat_type: str, amount: int | None = None):
    if amount is None:
        amount = 1
    if cat_type not in [*cattypes, "Random"] or (cat_type == "Random" and amount < 0):
        await message.response.send_message("bro what", ephemeral=True)
        return

    assert message.guild is not None
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    if cat_type == "Random":
        weights = list(data.type_dict.values())
        remaining_amount = amount
        remaining_weight = sum(weights)
        for rolled_type, weight in zip(cattypes, weights):
            if remaining_amount <= 0 or remaining_weight <= 0:
                break
            if count := random.binomialvariate(remaining_amount, weight / remaining_weight):
                user[f"cat_{rolled_type}"] += count
            remaining_amount -= count
            remaining_weight -= weight
    else:
        user[f"cat_{cat_type}"] += amount
    await user.save()
    text = f"gave {person_id.mention} {amount:,} {cat_type} {plural('cat', amount)}"
    if person_id == bot.user:
        text += ". you really didnt have to"
    await message.response.send_message(text, allowed_mentions=discord.AllowedMentions(users=True))


@bot.tree.command(name="setup", description="(ADMIN) Setup cat in current channel")
@discord.app_commands.default_permissions(manage_guild=True)
async def setup_channel(message: discord.Interaction):
    try:
        assert message.guild is not None
        assert isinstance(message.channel, GuildMessageable)
        guild = await bot.fetch_guild(message.guild.id)
        if isinstance(message.channel, discord.Thread):
            channel = await guild.fetch_channel(message.channel.parent_id)
        else:
            channel = await guild.fetch_channel(message.channel.id)
        channel_permissions = channel.permissions_for(message.guild.me)
        needed_perms = {
            "View Channel": channel_permissions.view_channel,
            "Send Messages": channel_permissions.send_messages,
            "Attach Files": channel_permissions.attach_files,
        }
        if isinstance(message.channel, discord.Thread):
            needed_perms["Send Messages in Threads"] = channel_permissions.send_messages_in_threads

        for name, value in needed_perms.copy().items():
            if value:
                needed_perms.pop(name)

        missing_perms = list(needed_perms.keys())
        if len(missing_perms) != 0:
            needed_perms = "\n- ".join(missing_perms)
            await message.response.send_message(
                f":x: Missing Permissions! Please give me the following:\n- {needed_perms}\nHint: try setting channel permissions if server ones don't work."
            )
            return

        if await Channel.get_or_none(channel_id=message.channel.id):
            await message.response.send_message(
                "bruh you already setup cat here are you dumb\n\nthere might already be a cat sitting in chat. type `cat` to catch it."
            )
            return

        await Channel.create(channel_id=message.channel.id)
    except Exception:
        await message.response.send_message("error. check if i have permissions to access this channel")
        return

    await message.response.send_message(await spawn_cat(message.channel.id))


@bot.tree.command(description="(ADMIN) Undo the setup/unsetup")
@discord.app_commands.default_permissions(manage_guild=True)
async def forget(message: discord.Interaction):
    assert isinstance(message.channel, GuildMessageable)
    if channel := await Channel.get_or_none(channel_id=message.channel.id):
        await channel.delete()
        await message.response.send_message(f"ok, now i wont send cats in <#{message.channel.id}>")
    else:
        await message.response.send_message("your an idiot there is literally no cat setupped in this channel you stupid")


@bot.tree.command(description="LMAO TROLLED SO HARD :JOY:")
async def fake(message: discord.Interaction):
    if message.user.id in fakecooldown:
        await message.response.send_message("your phone is overheating bro chill", ephemeral=True)
        return
    file = discord.File("assets/images/australian cat.png", filename="australian cat.png")
    icon = get_emoji("egirlcat")
    fakecooldown.add(message.user.id)
    try:
        await message.response.send_message(
            str(icon) + ' eGirl cat hasn\'t appeared! Type "cat" to catch ratio!',
            file=file,
        )
    except Exception:
        await message.response.send_message("i dont have perms lmao here is the ach anyways", ephemeral=True)
    await achemb(message, "trolled", "ephemeral")


@bot.tree.command(description="(ADMIN) Force cats to appear/spawn")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(cat_type="select a cat type ok")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def forcespawn(message: discord.Interaction, cat_type: str | None = None):
    assert isinstance(message.channel, GuildMessageable)
    if cat_type == "Random":
        cat_type = None
    elif cat_type and cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    ch = await Channel.get_or_none(channel_id=message.channel.id)
    if ch is None:
        await message.response.send_message("this channel is not /setup-ed", ephemeral=True)
        return
    if ch.cat:
        await message.response.send_message("there is already a cat", ephemeral=True)
        return
    ch.yet_to_spawn = 0
    await ch.save()
    await spawn_cat(message.channel.id, cat_type, True)
    await message.response.send_message("done!\n**Note:** you can use `/givecat` to give yourself cats, there is no need to spam this")


@bot.tree.command(description="(ADMIN) Give achievements to people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user", ach_id="name")
@discord.app_commands.describe(person_id="who", ach_id="name or id of the achievement")
@discord.app_commands.autocomplete(ach_id=ach_autocomplete)
async def giveachievement(message: discord.Interaction, person_id: discord.User, ach_id: str):
    # check if ach is real
    try:
        valid = ach_id in ach_names
    except KeyError:
        valid = False

    if not valid and ach_id.lower() in ach_titles:
        ach_id = ach_titles[ach_id.lower()]
        valid = True

    assert message.guild is not None
    person = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)

    if valid and ach_id == "thanksforplaying":
        await message.response.send_message("HAHAHHAHAH\nno", ephemeral=True)
        return

    if valid:
        # if it is, do the thing
        reverse = person[ach_id]
        person[ach_id] = not reverse
        await person.save()
        color, title, icon = (
            Colors.green,
            "Achievement forced!",
            "https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/ach.png",
        )
        if reverse:
            color, title, icon = (
                Colors.red,
                "Achievement removed!",
                "https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/no_ach.png",
            )
        ach_data = ach_list[ach_id]
        embed = (
            discord.Embed(
                title=ach_data["title"],
                description=ach_data["description"],
                color=color,
            )
            .set_author(name=title, icon_url=icon)
            .set_footer(text=f"for {person_id.name}" if person_id != bot.user else "for the coolest bot ever")
        )
        await message.response.send_message(person_id.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
    else:
        await message.response.send_message("i cant find that achievement! try harder next time.", ephemeral=True)


@bot.tree.command(description="(ADMIN) Reset people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="who")
async def reset(message: discord.Interaction, person_id: discord.User):
    async def confirmed(interaction: discord.Interaction) -> None:
        assert message.guild is not None
        if interaction.user.id != message.user.id:
            return await do_funny(interaction)

        try:
            profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
            profile.guild_id = the_id
            await profile.save()
            async for p in Prism.filter("guild_id = $1 AND user_id = $2", message.guild.id, person_id.id):
                p.guild_id = the_id
                await p.save()
            await Restore.create(guild_id=message.guild.id, user_id=person_id.id, username=person_id.name, id=the_id)
            await interaction.response.edit_message(
                content=f"Done! rip {person_id.mention}. f's in chat.\nyou can revert this in the next 7 days via `/undo`. contact us for older reverts: <https://discord.gg/staring>",
                view=None,
            )
        except Exception:
            await interaction.response.edit_message(
                content="ummm? this person isnt even registered in cat bot wtf are you wiping?????",
                view=None,
            )

    view = View(timeout=VIEW_TIMEOUT)
    button = Button(style=ButtonStyle.red, label="Confirm")
    button.callback = confirmed
    view.add_item(button)
    thing = f"Are you sure you want to reset {person_id.mention}?"
    if person_id == bot.user:
        thing += " (this will make me sad)"
    res = await message.response.send_message(thing, view=view, allowed_mentions=discord.AllowedMentions(users=True))
    the_id = res.message_id


@bot.tree.command(description="(HIGH ADMIN) [VERY DANGEROUS] Reset/wipe all Cat Bot data of this server")
@discord.app_commands.default_permissions(administrator=True)
async def nuke(message: discord.Interaction):
    warning_text = "⚠️ This will completely reset **all** Cat Bot progress of **everyone** in this server. Spawn channels and their settings *will not be affected*.\nPress the button 5 times to continue."
    counter = 5

    async def gen(counter: int) -> View:
        view = View(timeout=VIEW_TIMEOUT)
        button = Button(label=data.nuke_confirmation_lines[max(1, counter)], style=ButtonStyle.red)
        button.callback = count
        view.add_item(button)
        return view

    async def count(interaction: discord.Interaction) -> None:
        nonlocal message, counter
        assert message.guild is not None
        assert interaction.message is not None
        if interaction.user.id != message.user.id:
            return await do_funny(interaction)

        counter -= 1
        if counter == 0:
            # ~~Scary!~~ Not anymore!
            # how this works is we basically change the server id to the message id and then add user with id of 0 to mark it as deleted
            # this can be rolled back decently easily by asking user for the id of nuking message

            changed_profiles = []
            changed_prisms = []

            async for i in Profile.filter("guild_id = $1", message.guild.id):
                i.guild_id = interaction.message.id
                changed_profiles.append(i)

            async for i in Prism.filter("guild_id = $1", message.guild.id):
                i.guild_id = interaction.message.id
                changed_prisms.append(i)

            if changed_profiles:
                await Profile.bulk_update(changed_profiles, "guild_id")
            if changed_prisms:
                await Prism.bulk_update(changed_prisms, "guild_id")
            await Profile.create(guild_id=interaction.message.id, user_id=0)

            await Restore.create(guild_id=message.guild.id, id=interaction.message.id)
            await interaction.response.edit_message(
                content="done!\nyou can revert this in the next 7 days via `/undo`. contact us for older reverts: <https://discord.gg/staring>",
                view=None,
            )
        else:
            view = await gen(counter)
            try:
                await interaction.response.edit_message(content=warning_text, view=view)
            except Exception:
                pass

    view = await gen(counter)
    await message.response.send_message(warning_text, view=view)


@bot.tree.command(description="(HIGH ADMIN) Undo/revert/restore nukes and resets")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.autocomplete(operation=undo_autocomplete)
@discord.app_commands.describe(operation="pick the lowest/oldest operation if there are multiple")
async def undo(message: discord.Interaction, operation: str):
    assert message.guild is not None
    try:
        entry = await Restore.get_or_none(id=int(operation))
        if entry is None or entry.guild_id != message.guild.id:
            raise ValueError
    except Exception:
        await message.response.send_message("invalid operation", ephemeral=True)
        return

    async def confirm(interaction: discord.Interaction) -> None:
        if interaction.user.id != message.user.id:
            return await do_funny(interaction)

        await entry.refresh_from_db()
        if not entry:
            await interaction.response.send_message("operation not found", ephemeral=True)
            return

        try:
            if entry.user_id:
                # reset
                reset_id, user_id, guild_id = entry.id, entry.user_id, entry.guild_id
                if not (from_profile := await Profile.get_or_none(guild_id=reset_id, user_id=user_id)):
                    await interaction.response.send_message("invalid operation", ephemeral=True)
                    return

                if to_profile := await Profile.get_or_none(guild_id=guild_id, user_id=user_id):
                    await to_profile.delete()

                from_profile.guild_id = guild_id

                prism_count = 0
                async for p in Prism.filter("guild_id = $1 AND user_id = $2", reset_id, user_id):
                    # check if prism exists in destination
                    if await Prism.get_or_none(guild_id=guild_id, name=p.name):
                        await p.delete()
                        prism_count += 1
                    else:
                        p.guild_id = guild_id
                        await p.save()

                for c in cattypes:
                    # refund prisms as cats
                    from_profile[f"cat_{c}"] += prism_count

                await from_profile.save()
            else:
                # nuke
                from_id, to_id = entry.id, entry.guild_id

                async for i in Profile.filter("guild_id = $1", to_id):
                    await i.delete()
                async for i in Prism.filter("guild_id = $1", to_id):
                    await i.delete()

                changed_profiles = []
                changed_prisms = []

                async for profile in Profile.filter("guild_id = $1", from_id):
                    profile.guild_id = to_id
                    changed_profiles.append(profile)

                async for prism in Prism.filter("guild_id = $1", from_id):
                    prism.guild_id = to_id
                    changed_prisms.append(prism)

                if changed_profiles:
                    await Profile.bulk_update(changed_profiles, "guild_id")
                if changed_prisms:
                    await Prism.bulk_update(changed_prisms, "guild_id")

                if p := await Profile.get_or_none(guild_id=to_id, user_id=0):
                    await p.delete()

            await entry.delete()
            await interaction.response.edit_message(content="success", view=None)
        except Exception as e:
            await interaction.response.edit_message(content=f"error: {e}", view=None)

    view = View(timeout=VIEW_TIMEOUT)
    button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.red)
    button.callback = confirm
    view.add_item(button)
    await message.response.send_message(
        "⚠️ Running this operation will restore to the state at the time of the reset. All progress made since will be lost with no way to revert. Still continue?",
        view=view,
    )


def is_bot_owner():
    async def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id == OWNER_ID

    return commands.check(predicate)


# those are "owner" commands which are not really interesting
# each is named owner_* internally to avoid shadowing existing names (e.g. rain, news, emojis)
# but is exposed to Discord under its short name via @bot.command(name=...)


@bot.command(name="rain")
@is_bot_owner()
async def owner_rain(ctx: commands.Context, user_id: int, duration: int) -> None:
    # syntax: cat!rain 553093932012011520 20
    async with transaction() as conn:
        user = await User.get_or_create(conn, user_id=user_id)
        if not user.rain_minutes:
            user.rain_minutes = 0
        user.rain_minutes += duration
        user.premium = True
        await user.save()
    await ctx.reply(f"granted {duration} rain minutes to {user_id} (now {user.rain_minutes:,})")


@bot.command(name="restartall")
@is_bot_owner()
async def owner_restartall(ctx: commands.Context) -> None:
    try:
        await ctx.reply("restarting all clusters!")
        await anyio.run_process(["git", "pull"])
    except Exception:
        pass
    if vote_server:
        await vote_server.cleanup()
    await _get_pool().execute("SELECT pg_notify('restarts', $1)", ctx.message.content)


@bot.command(name="restart")
@is_bot_owner()
async def owner_restart(ctx: commands.Context) -> None:
    try:
        await ctx.reply("restarting this cluster!")
        await anyio.run_process(["git", "pull"])
    except Exception:
        pass
    if vote_server:
        await vote_server.cleanup()
    await bot.cat_bot_reload_hook("db" in ctx.message.content)  # pyright: ignore


@bot.command(name="sync")
@is_bot_owner()
async def owner_sync(ctx: commands.Context) -> None:
    if len(list(bot.tree.walk_commands())) <= 5:
        return
    try:
        await ctx.reply("syncing commands!")
        await bot.tree.sync()
    except Exception:
        pass


@bot.command(name="emojis")
@is_bot_owner()
async def owner_emojis(ctx: commands.Context) -> None:
    global emojis
    emojis = {emoji.name: str(emoji) for emoji in await bot.fetch_application_emojis()}
    try:
        async with await anyio.open_file("config/emojis_cache.json", "w", encoding="utf-8") as f:
            await f.write(json.dumps(emojis))
        await ctx.reply("emojis refreshed!")
    except Exception as e:
        await ctx.reply(f"emojis refreshed in memory, but cache write failed: {e}")


@bot.command(name="print")
@is_bot_owner()
async def owner_print(ctx: commands.Context, *, expr: str) -> None:
    # just a simple one-line with no async (e.g. 2+3)
    try:
        await ctx.reply(eval(expr))
    except Exception:
        try:
            await ctx.reply(str(traceback.format_exc())[-1900:])
        except Exception:
            pass


@bot.command(name="eval")
@is_bot_owner()
async def owner_eval(ctx: commands.Context, *, code: str) -> None:
    # complex eval, multi-line + async support
    message = ctx.message  # noqa: F841 (referenced by the exec'd template below)

    spaced = ""
    for i in code.split("\n"):
        spaced += "  " + i + "\n"

    wrapped = f"""async def go(message, bot):
 try:
{spaced}
 except Exception:
  await message.reply(str(traceback.format_exc())[-1900:])
bot.loop.create_task(go(message, bot))
    """

    try:
        exec(wrapped)  # noqa: S102
    except Exception:
        await ctx.reply(str(traceback.format_exc())[-1900:])


@bot.command(name="sql")
@is_bot_owner()
async def owner_sql(ctx: commands.Context, *, query: str) -> None:
    try:
        result = await _get_pool().fetch(query)
    except Exception as e:
        await ctx.reply(f"ERROR: {e}")
        return
    result = "\n".join(str(i).replace("<Record ", "").replace(">", "") for i in result)
    if not result:
        await ctx.reply("no rows returned")
    elif len(result) < 1900:
        await ctx.reply(result)
    else:
        await ctx.reply(file=discord.File(io.StringIO(result), filename="result.txt"))  # pyright: ignore[reportArgumentType]


@bot.command(name="transfer")
@is_bot_owner()
async def owner_transfer(ctx: commands.Context, *, args: str = "") -> None:
    parts = args.split()
    if len(parts) != 2:
        await ctx.reply("usage: cat!transfer <from_guild_id> <to_guild_id>")
        return
    from_id, to_id = int(parts[0]), int(parts[1])

    async for i in Profile.filter("guild_id = $1", to_id):
        await i.delete()
    async for i in Prism.filter("guild_id = $1", to_id):
        await i.delete()

    changed_profiles = []
    changed_prisms = []

    async for profile in Profile.filter("guild_id = $1", from_id):
        profile.guild_id = to_id
        changed_profiles.append(profile)

    async for prism in Prism.filter("guild_id = $1", from_id):
        prism.guild_id = to_id
        changed_prisms.append(prism)

    if changed_profiles:
        await Profile.bulk_update(changed_profiles, "guild_id")
    if changed_prisms:
        await Prism.bulk_update(changed_prisms, "guild_id")

    if p := await Profile.get_or_none(guild_id=to_id, user_id=0):
        await p.delete()

    await ctx.reply(
        f"transferred {len(changed_profiles)} {plural('profile', len(changed_profiles))} and {len(changed_prisms)} {plural('prism', len(changed_prisms))}"
    )


@bot.command(name="undoreset")
@is_bot_owner()
async def owner_undoreset(ctx: commands.Context, *, args: str = "") -> None:
    parts = args.split()
    if len(parts) != 3:
        await ctx.reply("usage: cat!undoreset <guild_id> <user_id> <reset_id>")
        return
    guild_id, user_id, reset_id = int(parts[0]), int(parts[1]), int(parts[2])

    if not (from_profile := await Profile.get_or_none(guild_id=reset_id, user_id=user_id)):
        await ctx.reply(f"no profile found for {user_id} in {reset_id}")
        return

    if to_profile := await Profile.get_or_none(guild_id=guild_id, user_id=user_id):
        await to_profile.delete()

    from_profile.guild_id = guild_id

    prism_count = 0
    async for p in Prism.filter("guild_id = $1 AND user_id = $2", reset_id, user_id):
        await p.delete()
        prism_count += 1

    for c in cattypes:
        # refund prisms as cats
        from_profile[f"cat_{c}"] += prism_count

    await from_profile.save()
    await ctx.reply(f"successfully undone reset for {user_id} in {guild_id}")


@bot.command(name="merge")
@is_bot_owner()
async def owner_merge(ctx: commands.Context, *, args: str = "") -> None:
    parts = args.split()
    if len(parts) != 3:
        await ctx.reply("usage: cat!merge <guild_id> <from_user_id> <to_user_id>")
        return
    guild_id, from_user_id, to_user_id = int(parts[0]), int(parts[1]), int(parts[2])

    from_profile = await Profile.get_or_create(guild_id=guild_id, user_id=from_user_id)
    to_profile = await Profile.get_or_create(guild_id=guild_id, user_id=to_user_id)

    # prisms
    prism_count = 0
    async for p in Prism.filter("guild_id = $1 AND user_id = $2", guild_id, from_user_id):
        p.user_id = to_user_id
        await p.save()
        prism_count += 1

    # cats
    cat_count = 0
    for i in cattypes:
        to_profile[f"cat_{i}"] += from_profile[f"cat_{i}"]
        cat_count += from_profile[f"cat_{i}"]
        from_profile[f"cat_{i}"] = 0

    # achs
    ach_count = 0
    for ach in ach_list:
        if not from_profile[ach] or to_profile[ach]:
            continue
        to_profile[ach] = True
        from_profile[ach] = False
        ach_count += 1

    await to_profile.save()
    await from_profile.save()

    await ctx.reply(f"successfully merged {from_user_id} into {to_user_id} in {guild_id} ({prism_count:,} prisms, {cat_count:,} cats, {ach_count:,} achs)")


@bot.command(name="news")
@is_bot_owner()
async def owner_news(ctx: commands.Context, *, announcement: str) -> None:
    async for i in Channel.all():
        try:
            channeley = bot.get_partial_messageable(int(i.channel_id))
            await channeley.send(announcement)
        except Exception:
            pass


async def recieve_vote(request: web.Request) -> web.Response:
    signature = request.headers.get("x-topgg-signature", "")
    try:
        assert config.WEBHOOK_VERIFY is not None
        signature_parts = {i.split("=")[0]: i.split("=")[1] for i in signature.split(",")}
        raw_body = await request.read()
        body = f"{signature_parts['t']}.{raw_body.decode()}".encode()
        key = config.WEBHOOK_VERIFY.encode("utf-8")
        if hmac.new(key, body, hashlib.sha256).hexdigest() != signature_parts["v1"]:
            raise ValueError
    except Exception:
        return web.Response(text="bad", status=403)
    request_data = json.loads(raw_body)["data"]

    user = await User.get_or_create(user_id=int(request_data["user"]["platform_id"]))
    created_at = datetime.datetime.fromisoformat(request_data["created_at"]).timestamp()

    await do_vote(user, created_at)

    return web.Response(text="ok", status=200)


async def do_vote(user: User, created_at: float) -> None:
    if user.vote_streak < 10:
        extend_time = 24
    elif user.vote_streak < 20:
        extend_time = 36
    elif user.vote_streak < 50:
        extend_time = 48
    elif user.vote_streak < 100:
        extend_time = 60
    else:
        extend_time = 72

    if created_at - user.vote_time_topgg < 3600:
        return

    user.reminder_vote = 1
    user.total_votes += 1
    freeze_note = ""
    if user.vote_time_topgg + extend_time * 3600 <= created_at:
        # streak end
        if user.streak_freezes < 1:
            user.max_vote_streak = max(user.max_vote_streak, user.vote_streak)
            user.vote_streak = 1
        else:
            # i initially wanted streak freezes to not increase up
            # but that could result in unexpected repeated milestone rewards
            user.vote_streak += 1

            user.streak_freezes -= 1
            freeze_note = "\n🧊 Streak Freeze Used!"
    else:
        user.vote_streak += 1

    user.vote_time_topgg = created_at

    channeley = await fetch_dm_channel(user)

    if user.vote_streak == 1:
        streak_progress = f"{get_emoji('staring_square')}⬛⬛⬛⬛⬛⬛⬛⬛⬛\n⬆️"
    else:
        streak_progress = ""
        if user.vote_streak > 0:
            streak_progress += get_streak_reward(user.vote_streak - 1)["done_emoji"]
        streak_progress += get_streak_reward(user.vote_streak)["done_emoji"]

        for i in range(user.vote_streak + 1, user.vote_streak + 9):
            streak_progress += get_streak_reward(i)["emoji"]

        streak_progress += f"\n{get_emoji('empty')}⬆️"

    special_reward = math.ceil(user.vote_streak / 25) * 25
    if special_reward not in range(user.vote_streak, user.vote_streak + 9):
        streak_progress += f"\nNext Special Reward: {get_streak_reward(special_reward)['emoji']} at {special_reward} streak"

    top_text = ""
    if user.vote_streak >= 100:
        streak_top_position = await User.count("vote_streak > $1", user.vote_streak) + 1
        top_text = f" (top #{streak_top_position}!)" if streak_top_position < 1000 else ""

    await user.save()

    try:
        await channeley.send(
            "\n".join(
                [
                    "Thanks for voting! To claim your rewards, run `/battlepass` in every server you want.",
                    f"You can vote again <t:{int(created_at) + 43200}:R>.",
                    "",
                    f":fire: **Streak:** {user.vote_streak:,}{top_text} expires <t:{int(created_at) + extend_time * 3600}:R>{freeze_note}",
                    f"{streak_progress}",
                ]
            ),
        )

        log_stats("vote", {"streak": str(user.vote_streak)})
    except discord.Forbidden:
        pass


async def check_supporter(request: web.Request) -> web.Response:
    if request.headers.get("authorization", "") != config.WEBHOOK_VERIFY:
        return web.Response(text="bad", status=403)
    request_json = await request.json()

    user = await User.get_or_create(user_id=int(request_json["user"]))
    return web.Response(text="1" if user.premium else "0", status=200)


async def bake_gg_reward(request: web.Request) -> web.Response:
    if request.headers.get("Authorization", "") != os.environ.get("BAKE_GG_WEBHOOK_TOKEN", ""):
        return web.Response(text="Invalid or missing authorization token", status=401)

    try:
        request_json = await request.json()
        user_id = int(request_json["user"])
    except (KeyError, ValueError):
        return web.Response(text="Invalid user ID", status=400)
    user = await User.get_or_create(user_id=user_id)

    if user.last_bakegg_get == get_current_week():
        return web.Response(text="User already claimed this week", status=429)

    user.last_bakegg_get = get_current_week()
    user.queued_chef_pack = True
    await user.save()
    try:
        channeley = await fetch_dm_channel(user)
        await channeley.send(f"You have received a {get_emoji('chefpack')} Chef Pack from Bake.gg! You can claim it in a single server by running `/bakery`.")
    except Exception:
        pass
    return web.Response(text="Success", status=200)


# cat bot uses glitchtip (sentry alternative) for errors, here u can instead implement some other logic like dming the owner
async def on_error(*args, **kwargs):
    raise  # noqa: PLE0704


async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    # CommandNotFound/CheckFailure/UserInputError are expected noise (typos, non-owner cat!x attempts,
    # missing args on owner commands) - anything else is a real bug, let on_error/sentry see it
    if isinstance(error, (commands.CommandNotFound, commands.CheckFailure, commands.UserInputError)):
        return
    raise error


async def on_interaction(ctx: discord.Interaction) -> None:
    try:
        if ctx.command:
            log_stats("command_use", {"name": ctx.command.name})
            bot.loop.create_task(start_tutorial(ctx))
    except Exception:
        pass


async def start_tutorial(ctx: discord.Interaction) -> None:
    await asyncio.sleep(5)
    global_user = await User.get_or_create(user_id=ctx.user.id)
    if global_user.tutorial_state == 0:
        await ctx.followup.send(view=await get_tutorial_view(ctx.user.id), ephemeral=True)


async def setup(bot2: commands.AutoShardedBot) -> None:
    global bot, COMMAND_IDS, vote_server

    # remove old commands
    bot2.tree.clear_commands(guild=None)
    for command in bot2.walk_commands():
        bot2.remove_command(command.name)

    for command in bot.tree.walk_commands():
        # copy all the commands
        command.guild_only = True
        bot2.tree.add_command(command)

    for command in bot.commands:
        # copy the owner prefix commands too
        bot2.add_command(command)

    context_menu_command = discord.app_commands.ContextMenu(name="catch", callback=catch)
    context_menu_command.guild_only = True
    bot2.tree.add_command(context_menu_command)

    # copy all the events
    bot2.on_message = on_message
    bot2.on_command_error = on_command_error  # type: ignore
    bot2.on_error = on_error  # type: ignore
    bot2.on_ready = on_ready  # type: ignore
    bot2.on_guild_join = on_guild_join  # type: ignore
    bot2.on_guild_update = on_guild_update  # type: ignore
    bot2.on_connect = on_connect  # type: ignore
    bot2.on_interaction = on_interaction  # type: ignore

    # finally replace the fake bot with the real one
    bot = bot2

    config.SOFT_RESTART_TIME = time.time()

    vote_server = None
    if config.WEBHOOK_VERIFY and (not config.CLUSTERING or config.CLUSTERING_ZERO):
        app = web.Application()
        app.add_routes(
            [
                web.post("/", recieve_vote),
                web.get("/supporter", check_supporter),
                web.post("/bakegg", bake_gg_reward),
            ]
        )
        vote_server = web.AppRunner(app)
        await vote_server.setup()
        site = web.TCPSite(vote_server, "0.0.0.0", 8069)
        await site.start()

    app_commands = await bot.tree.fetch_commands()
    COMMAND_IDS = {i.name: i.id for i in app_commands}

    if bot.is_ready() and not on_ready_debounce:
        await on_ready()


async def teardown(bot: commands.AutoShardedBot) -> None:
    if vote_server:
        await vote_server.cleanup()


# Reusable UI components
class Select(discord.ui.Select):
    on_select = None

    def __init__(
        self,
        id: str,
        placeholder: str,
        options: list[discord.SelectOption],
        on_select: Callable | None = None,
        disabled: bool = False,
    ):
        if on_select is not None:
            self.on_select = on_select

        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id=id,
            max_values=1,
            min_values=1,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.on_select is not None and callable(self.on_select):
            await self.on_select(interaction, self.values[0] if len(self.values) == 1 else self.values)


class Container(discord.ui.Container):
    def __init__(self, *pre_children, **kwargs):
        if "accent_color" not in kwargs:
            kwargs["accent_color"] = Colors.brown

        children = []
        new_children = []

        for chil in pre_children:
            if isinstance(chil, tuple):
                children.extend(chil)
            else:
                children.append(chil)

        for child in children:
            if not child:
                continue
            elif isinstance(child, str):
                if child == "===":
                    new_children.append(Separator())
                else:
                    new_children.append(TextDisplay(child))
            elif isinstance(child, Button):
                new_children.append(ActionRow(child))
            else:
                new_children.append(child)

        super().__init__(*new_children, **kwargs)


class Section(discord.ui.Section):
    def __init__(self, *children, **kwargs):
        if "accessory" not in kwargs:
            new_children = []

            for child in children:
                if not child:
                    continue
                if isinstance(child, (Button, Thumbnail)):
                    kwargs["accessory"] = child
                else:
                    new_children.append(child)

            super().__init__(*new_children, **kwargs)
        else:
            super().__init__(*children, **kwargs)
