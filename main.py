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
import base64
import datetime
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
from typing import Literal, Optional

import aiohttp
import discord
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
import msg2img
from catpg import RawSQL
from database import Channel, Prism, Profile, Reminder, User

try:
    import exportbackup  # type: ignore
except ImportError:
    exportbackup = None

# trigger warning, base64 encoded for your convinience
NONOWORDS = [base64.b64decode(i).decode("utf-8") for i in ["bmlja2E=", "bmlja2Vy", "bmlnYQ==", "bmlnZ2E=", "bmlnZ2Vy"]]

type_dict = {
    "Fine": 1000,
    "Nice": 750,
    "Good": 500,
    "Rare": 350,
    "Wild": 275,
    "Baby": 230,
    "Epic": 200,
    "Sus": 175,
    "Brave": 150,
    "Rickroll": 125,
    "Reverse": 100,
    "Superior": 80,
    "Trash": 50,
    "Legendary": 35,
    "Mythic": 25,
    "8bit": 20,
    "Corrupt": 15,
    "Professor": 10,
    "Divine": 8,
    "Real": 5,
    "Ultimate": 3,
    "eGirl": 2,
}

# this list stores unique non-duplicate cattypes
cattypes = list(type_dict.keys())

# generate a dict with lowercase'd keys
cattype_lc_dict = {i.lower(): i for i in cattypes}

allowedemojis = []
for i in cattypes:
    allowedemojis.append(i.lower() + "cat")

pack_data = [
    {"name": "Christmas", "value": 30, "upgrade": 70, "totalvalue": 225},
    {"name": "Wooden", "value": 65, "upgrade": 30, "totalvalue": 75},
    {"name": "Stone", "value": 90, "upgrade": 30, "totalvalue": 100},
    {"name": "Bronze", "value": 100, "upgrade": 30, "totalvalue": 130},
    {"name": "Silver", "value": 115, "upgrade": 30, "totalvalue": 200},
    {"name": "Gold", "value": 230, "upgrade": 30, "totalvalue": 400},
    {"name": "Platinum", "value": 630, "upgrade": 30, "totalvalue": 800},
    {"name": "Diamond", "value": 860, "upgrade": 30, "totalvalue": 1200},
    {"name": "Celestial", "value": 2000, "upgrade": 0, "totalvalue": 2000},  # is that a madeline celeste reference????
]

prism_names_start = [
    "Alpha",
    "Bravo",
    "Charlie",
    "Delta",
    "Echo",
    "Foxtrot",
    "Golf",
    "Hotel",
    "India",
    "Juliett",
    "Kilo",
    "Lima",
    "Mike",
    "November",
    "Oscar",
    "Papa",
    "Quebec",
    "Romeo",
    "Sierra",
    "Tango",
    "Uniform",
    "Victor",
    "Whiskey",
    "X-ray",
    "Yankee",
    "Zulu",
]
prism_names_end = [
    "",
    " Two",
    " Three",
    " Four",
    " Five",
    " Six",
    " Seven",
    " Eight",
    " Nine",
    " Ten",
    " Eleven",
    " Twelve",
    " Thirteen",
    " Fourteen",
    " Fifteen",
    " Sixteen",
    " Seventeen",
    " Eighteen",
    " Nineteen",
    " Twenty",
]
prism_names = []
for i in prism_names_end:
    for j in prism_names_start:
        prism_names.append(j + i)

vote_button_texts = [
    "You havent voted today!",
    "I know you havent voted ;)",
    "If vote cat will you friend :)",
    "Vote cat for president",
    "vote = 0.01% to escape basement",
    "vote vote vote vote vote",
    "mrrp mrrow go and vote now",
    "if you vote you'll be free (no)",
    "vote. btw, i have a pipebomb",
    "No votes? :megamind:",
    "Cat says you should vote",
    "cat will be happy if you vote",
    "VOTE NOW!!!!!",
    "I voted and got 1000000$",
    "I voted and found a gf",
    "lebron james forgot to vote",
    "vote if you like cats",
    "vote if cats > dogs",
    "you should vote for cat NOW!",
    "I'd vote if I were you",
]

# various hints/fun facts
hints = [
    "Cat Bot has a wiki! <https://catbot.wiki>",
    "Cat Bot is open source! <https://github.com/milenakos/cat-bot>",
    "View all cats and rarities with /catalogue",
    "Cat Bot's birthday is on the 21st of April",
    "Unlike the normal one, Cat's /8ball isn't rigged",
    "/rate says /rate is 100% correct",
    "/casino is *surely* not rigged",
    "You probably shouldn't use a Discord bot for /remind-ers",
    "Cat /Rain is an excellent way to support development!",
    "Cat Bot was made later than its support server",
    "Cat Bot reached 100 servers 3 days after release",
    "Cat died for 2+ weeks bc the servers were flooded with water",
    "Cat Bot's top.gg page was deleted at one point",
    "Cat Bot has an official soundtrack! <https://youtu.be/Ww1opmRwYF0>",
    "4 with 832 zeros cats were deleted on September 5th, 2024",
    "Cat Bot has reached top #19 on top.gg in January 2025",
    "Cat Bot has reached top #17 on top.gg in February 2025",
    "Cat Bot has reached top #12 on top.gg in March 2025",
    "Cat Bot has reached top #9 on top.gg in April 2025",
    "Cat Bot has reached top #7 on top.gg in May 2025",
    "Cat Bot has reached top #5 on top.gg in September 2025",
    "Most Cat Bot features were made within 2 weeks",
    "Cat Bot was initially made for only one server",
    "Cat Bot is made in Python with discord.py",
    "Discord didn't verify Cat properly the first time",
    "Looking at Cat's code won't make you regret your life choices!",
    "Cats aren't shared between servers to make it more fair and fun",
    "Cat Bot can go offline! Don't panic if it does",
    "By default, cats spawn 1-10 minutes apart",
    "View the last catch as well as the next one with /last",
    "Make sure to leave Cat Bot [a review on top.gg](<https://top.gg/bot/966695034340663367#reviews>)!",
]

# laod the jsons
with open("config/aches.json", "r") as f:
    ach_list = json.load(f)

with open("config/battlepass.json", "r", encoding="utf-8") as f:
    battle = json.load(f)

with open("config/catnip.json", "r", encoding="utf-8") as f:
    catnip_list = json.load(f)

with open("facts.txt") as f:
    cat_facts_list = f.read().split("\n")

# convert achievement json to a few other things
ach_names = ach_list.keys()
ach_titles = {value["title"].lower(): key for (key, value) in ach_list.items()}

bot = commands.AutoShardedBot(
    command_prefix="this is a placebo bot which will be replaced when this will get loaded",
    intents=discord.Intents.default(),
)

funny = [
    "why did you click this this arent yours",
    "absolutely not",
    "cat bot not responding, try again later",
    "you cant",
    "can you please stop",
    "try again",
    "403 not allowed",
    "stop",
    "get a life",
    "not for you",
    "no",
    "nuh uh",
    "access denied",
    "forbidden",
    "don't do this",
    "cease",
    "wrong",
    "aw dangit",
    "why don't you press buttons from your commands",
    "you're only making me angrier",
    "why are you like this",
    "legends say you get something for clicking it 1000 times",
]


class Colors:
    brown = 0x6E593C
    gray = 0xCCCCCC
    green = 0x007F0E
    yellow = 0xFFFF00
    maroon = 0x750F0E
    demonic = 0xC12929
    rose = 0xFF81C6
    red = 0xFF0000


# rain shill message for footers
rain_shill = "☔ Get tons of cats /rain"

# timeout for views
# higher one means buttons work for longer but uses more ram to keep track of them
VIEW_TIMEOUT = 86400

# store credits usernames to prevent excessive api calls
gen_credits = {}

# due to some stupid individuals spamming the hell out of reactions, we ratelimit them
# you can do 50 reactions before they stop, limit resets on global cat loop
reactions_ratelimit = {}

# sort of the same thing but for pointlaughs and per channel instead of peruser
pointlaugh_ratelimit = {}

# cooldowns for some commands
catchcooldown = {}
fakecooldown = {}
customcatcooldown = {}

# cat bot auto-claims in the channel user last ran /vote in
# this is a failsafe to store the fact they voted until they ran that atleast once
pending_votes = []

# prevent ratelimits
casino_lock = []
slots_lock = []

# ???
rigged_users = []


# WELCOME TO THE TEMP_.._STORAGE HELL

# to prevent double catches
temp_catches_storage = []

# to prevent double spawns
temp_spawns_storage = []

# to prevent double belated battlepass progress and for "faster than 10 seconds" belated bp quest
temp_belated_storage = {}

# to prevent weird cookie things without destroying the database with load
temp_cookie_storage = {}

# docs suggest on_ready can be called multiple times
on_ready_debounce = False

about_to_stop = False

# d.py doesnt cache app emojis so we do it on our own yippe
emojis = {}

# for mentioning it in catch message, will be auto-fetched in on_ready()
RAIN_ID = 1270470307102195752

# for dev commands, this is fetched in on_ready
OWNER_ID = 553093932012011520

# for funny stats, you can probably edit background_loop to restart every X of them
loop_count = 0

# loops in dpy can randomly break, i check if is been over X minutes since last loop to restart it
last_loop_time = 0


def get_emoji(name):
    global emojis
    if name in emojis.keys():
        return emojis[name]
    elif name in emoji.EMOJI_DATA:
        return name
    else:
        return "🔳"


async def fetch_dm_channel(user: User) -> discord.PartialMessageable:
    if user.dm_channel_id:
        return bot.get_partial_messageable(user.dm_channel_id)
    else:
        person = await bot.fetch_user(user.user_id)
        if not person.dm_channel:
            await person.create_dm()
        user.dm_channel_id = person.dm_channel.id
        await user.save()
        return person.dm_channel


# news stuff
news_list = [
    {"title": "Cat Bot Survey - win rains!", "emoji": "📜"},
    {"title": "New Cat Rains perks!", "emoji": "✨"},
    {"title": "Cat Bot Christmas 2024", "emoji": "🎅"},
    {"title": "Battlepass Update", "emoji": "⬆️"},
    {"title": "Packs!", "emoji": "goldpack"},
    {"title": "Message from CEO of Cat Bot", "emoji": "finecat"},
    {"title": "Cat Bot Turns 3", "emoji": "🥳"},
    {"title": "100,000 SERVERS WHAT", "emoji": "🎉"},
    {"title": "Regarding recent instabilities", "emoji": "🗒️"},
    {"title": "cat bot reached #5 on top.gg", "emoji": "yippee"},
    {"title": "top.gg awards (outdated)", "emoji": "🏆"},
    {"title": "Welcome to the Cat Mafia", "emoji": "catnip"},
    {"title": "vote for cat bot as finalist in top.gg awards", "emoji": "❤️"},
    {"title": "Cat Bot Christmas 2025", "emoji": "christmaspack"},
]


# this is some common code which is run whether someone gets an achievement
async def achemb(message, ach_id, send_type, author_string=None):
    if not author_string:
        try:
            author_string = message.author
        except Exception:
            author_string = message.user
    author = author_string.id

    if not message.guild:
        return

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=author)

    if profile[ach_id]:
        return

    profile[ach_id] = True
    await profile.save()
    logging.debug("Achievement unlocked: %s", ach_id)
    ach_data = ach_list[ach_id]
    desc = ach_data["description"]
    if ach_id == "dataminer":
        desc = "Your head hurts -- you seem to have forgotten what you just did to get this."

    if ach_id != "thanksforplaying":
        embed = (
            discord.Embed(title=ach_data["title"], description=desc, color=Colors.green)
            .set_author(
                name="Achievement get!",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/ach.png",
            )
            .set_footer(text=f"Unlocked by {author_string.name}")
        )
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
            .set_footer(text=f"Congrats to {author_string.name}!!")
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
            .set_footer(text=f"Congrats to {author_string.name}!!")
        )

    try:
        result = None
        if send_type == "reply":
            result = await message.reply(embed=embed)
        elif send_type == "send":
            result = await message.channel.send(embed=embed)
        elif send_type == "followup":
            result = await message.followup.send(embed=embed)
        elif send_type == "ephemeral":
            result = await message.followup.send(embed=embed, ephemeral=True)
        elif send_type == "response":
            result = await message.response.send_message(embed=embed)
        await progress(message, profile, "achievement")
        await finale(message, profile)
    except Exception:
        pass

    if result and ach_id == "thanksforplaying":
        await asyncio.sleep(2)
        await result.edit(embed=embed2)
        await asyncio.sleep(2)
        await result.edit(embed=embed)
        await asyncio.sleep(2)
        await result.edit(embed=embed2)
        await asyncio.sleep(2)
        await result.edit(embed=embed)
    elif result and ach_id == "curious":
        await result.delete(delay=30)


async def generate_quest(user: Profile, quest_type: str):
    while True:
        quest = random.choice(list(battle["quests"][quest_type].keys()))
        if quest in ["slots", "reminder"]:
            # removed quests
            continue
        elif quest == "prism":
            total_count = await Prism.count("guild_id = $1", user.guild_id)
            user_count = await Prism.count("guild_id = $1 AND user_id = $2", user.guild_id, user.user_id)
            global_boost = 0.06 * math.log(2 * total_count + 1)
            prism_boost = global_boost + 0.03 * math.log(2 * user_count + 1)
            if prism_boost < 0.15:
                continue
        elif quest == "news":
            global_user = await User.get_or_create(user_id=user.user_id)
            if len(news_list) <= len(global_user.news_state.strip()) and "0" not in global_user.news_state.strip()[-4:]:
                continue
        elif quest == "achievement":
            unlocked = 0
            for k in ach_names:
                if user[k] and ach_list[k]["category"] != "Hidden":
                    unlocked += 1
            if unlocked > 30:
                continue
        break

    quest_data = battle["quests"][quest_type][quest]
    if quest_type == "vote":
        user.vote_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.vote_cooldown = 0
    elif quest_type == "catch":
        user.catch_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.catch_quest = quest
        user.catch_cooldown = 0
    elif quest_type == "misc":
        user.misc_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.misc_quest = quest
        user.misc_cooldown = 0
    await user.save()


async def refresh_quests(user):
    await user.refresh_from_db()
    start_date = datetime.datetime(2024, 12, 1)
    current_date = datetime.datetime.utcnow() + datetime.timedelta(hours=4)
    full_months_passed = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
    if current_date.day < start_date.day:
        full_months_passed -= 1
    if user.season != full_months_passed:
        user.bp_history = user.bp_history + f"{user.season},{user.battlepass},{user.progress};"
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

        user.season = full_months_passed
        await user.save()
    if 12 * 3600 < user.vote_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "vote")
    if 12 * 3600 < user.catch_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "catch")
    if 12 * 3600 < user.misc_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "misc")


async def progress(message: discord.Message | discord.Interaction, user: Profile, quest: str, is_belated: Optional[bool] = False):
    await refresh_quests(user)
    await user.refresh_from_db()

    # progress
    quest_complete = False
    if user.catch_quest == quest:
        if user.catch_cooldown != 0:
            return
        quest_data = battle["quests"]["catch"][quest]
        user.catch_progress += 1
        if user.catch_progress >= quest_data["progress"]:
            quest_complete = True
            user.catch_cooldown = int(time.time())
            current_xp = user.progress + user.catch_reward
            user.catch_progress = 0
            user.reminder_catch = 1
    elif quest == "vote":
        if user.vote_cooldown != 0:
            return
        quest_data = battle["quests"]["vote"][quest]
        global_user = await User.get_or_create(user_id=user.user_id)
        user.vote_cooldown = global_user.vote_time_topgg

        # Weekdays 0 Mon - 6 Sun
        # double vote xp rewards if Friday, Saturday or Sunday
        voted_at = datetime.datetime.utcfromtimestamp(global_user.vote_time_topgg)
        if voted_at.weekday() >= 4:
            user.vote_reward *= 2

        streak_data = get_streak_reward(global_user.vote_streak)
        if streak_data["reward"]:
            user[f"pack_{streak_data['reward']}"] += 1

        current_xp = user.progress + user.vote_reward
        quest_complete = True
    elif user.misc_quest == quest:
        if user.misc_cooldown != 0:
            return
        quest_data = battle["quests"]["misc"][quest]
        user.misc_progress += 1
        if user.misc_progress >= quest_data["progress"]:
            quest_complete = True
            user.misc_cooldown = int(time.time())
            current_xp = user.progress + user.misc_reward
            user.misc_progress = 0
            user.reminder_misc = 1
    else:
        return

    await user.save()
    if not quest_complete:
        return

    user.quests_completed += 1

    logging.debug("Quest complete: %s", quest)
    old_xp = user.progress
    level_complete_embeds = []
    if user.battlepass >= len(battle["seasons"][str(user.season)]):
        level_data = {"xp": 1500, "reward": "Stone", "amount": 1}
        level_text = "Extra Rewards"
    else:
        level_data = battle["seasons"][str(user.season)][user.battlepass]
        level_text = f"Level {user.battlepass + 1}"

    if current_xp >= level_data["xp"]:
        logging.debug("Level complete %d", user.battlepass)
        xp_progress = current_xp
        active_level_data = level_data
        while xp_progress >= active_level_data["xp"]:
            user.battlepass += 1
            xp_progress -= active_level_data["xp"]
            user.progress = xp_progress
            cat_emojis = None
            if active_level_data["reward"] in cattypes:
                user[f"cat_{active_level_data['reward']}"] += active_level_data["amount"]
            elif active_level_data["reward"] == "Rain":
                user.rain_minutes += active_level_data["amount"]
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

            if user.battlepass >= len(battle["seasons"][str(user.season)]):
                active_level_data = {"xp": 1500, "reward": "Stone", "amount": 1}
                new_level_text = "Extra Rewards"
            else:
                active_level_data = battle["seasons"][str(user.season)][user.battlepass]
                new_level_text = f"Level {user.battlepass + 1}"

        embed_progress = await progress_embed(
            message,
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
            message,
            user,
            level_data,
            current_xp,
            old_xp,
            quest_data,
            current_xp - old_xp,
            level_text,
        )

    if is_belated:
        embed_progress.set_footer(text="For catching within 3 seconds")

    if level_complete_embeds:
        await message.channel.send(f"<@{user.user_id}>", embeds=level_complete_embeds + [embed_progress])
    else:
        await message.channel.send(f"<@{user.user_id}>", embed=embed_progress)


async def progress_embed(message, user, level_data, current_xp, old_xp, quest_data, diff, level_text) -> discord.Embed:
    percentage_before = int(old_xp / level_data["xp"] * 10)
    percentage_after = int(current_xp / level_data["xp"] * 10)
    percenteage_left = 10 - percentage_after

    progress_line = get_emoji("staring_square") * percentage_before + "🟨" * (percentage_after - percentage_before) + "⬛" * percenteage_left

    title = quest_data["title"] if "top.gg" not in quest_data["title"] else "Vote on Top.gg"

    if level_data["reward"] == "Rain":
        reward_text = get_emoji(str(level_data["amount"]) + "rain")
    elif level_data["reward"] == "random cats":
        reward_text = f"{level_data['amount']}x ❓"
    elif level_data["reward"] in cattypes:
        reward_text = f"{level_data['amount']}x {get_emoji(level_data['reward'].lower() + 'cat')}"
    else:
        reward_text = get_emoji(level_data["reward"].lower() + "pack")

    global_user = await User.get_or_create(user_id=user.user_id)
    streak_data = get_streak_reward(global_user.vote_streak)
    if streak_data["reward"] and "top.gg" in quest_data["title"]:
        streak_reward = f"\n🔥 **Streak Bonus!** +1 {streak_data['emoji']} {streak_data['reward'].capitalize()} pack"
    else:
        streak_reward = ""

    return discord.Embed(
        title=f"✅ {title}",
        description=f"{progress_line} {reward_text}\n{current_xp}/{level_data['xp']} XP (+{diff}){streak_reward}",
        color=Colors.green,
    ).set_author(name="/battlepass " + level_text)


def get_streak_reward(streak):
    if streak % 5 != 0 or streak in [0, 5]:
        return {"reward": None, "emoji": "⬛", "done_emoji": "🟦"}

    pack_type = "gold"
    # these honestly don't add that much value but feel like good milestones
    if streak % 100 == 0:
        pack_type = "diamond"
    elif streak % 25 == 0:
        pack_type = "platinum"

    return {"reward": pack_type, "emoji": get_emoji(f"{pack_type}pack"), "done_emoji": get_emoji(f"{pack_type}pack_claimed")}


# handle curious people clicking buttons
async def do_funny(message):
    await message.response.send_message(random.choice(funny), ephemeral=True)
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    user.funny += 1
    await user.save()
    await achemb(message, "curious", "reply")
    if user.funny >= 50:
        await achemb(message, "its_not_working", "followup")


# not :eyes:
async def debt_cutscene(message, user):
    if user.debt_seen:
        return

    user.debt_seen = True
    await user.save()

    debt_msgs = [
        "**\\*BANG\\***",
        "Your door gets slammed open and multiple man in black suits enter your room.",
        "**???**: Hello, you have unpaid debts. You owe us money. We are here to liquidate all your assets.",
        "*(oh for fu)*",
        "**You**: pls dont",
        "**???**: oh okay then we will come back to you later.",
        "They leave the room.",
        "**You**: Oh god this is bad",
        "**You**: I know of a solution though!",
        "**You**: I heard you can gamble your debts away in the slots machine!",
    ]

    for debt_msg in debt_msgs:
        await asyncio.sleep(4)
        await message.followup.send(debt_msg, ephemeral=True)


# :eyes:
async def finale(message, user):
    if user.finale_seen:
        return

    # check ach req
    for k in ach_names:
        if not user[k] and ach_list[k]["category"] != "Hidden":
            return

    user.finale_seen = True
    await user.save()
    try:
        author_string = message.author
    except Exception:
        author_string = message.user
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
    return [discord.app_commands.Choice(name=choice, value=choice) for choice in cattypes if current.lower() in choice.lower()][:25]


# function to autocomplete /cat, it only shows the cats you have
async def cat_command_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
    choices = []
    for choice in cattypes:
        if current.lower() in choice.lower() and user[f"cat_{choice}"] > 0:
            choices.append(discord.app_commands.Choice(name=choice, value=choice))
    return choices[:25]


async def lb_type_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [
        discord.app_commands.Choice(name=choice, value=choice)
        for choice in ["All"] + await cats_in_server(interaction.guild_id)
        if current.lower() in choice.lower()
    ][:25]


async def cats_in_server(guild_id):
    return [cat_type for cat_type in cattypes if (await Profile.count(f'guild_id = $1 AND "cat_{cat_type}" > 0 LIMIT 1', guild_id))]


# function to autocomplete cat_type choices for /gift, which shows only cats user has and how many of them they have
async def gift_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
    actual_user = await User.get_or_create(user_id=interaction.user.id)
    choices = []
    for choice in cattypes:
        if current.lower() in choice.lower() and user[f"cat_{choice}"] > 0:
            choices.append(discord.app_commands.Choice(name=f"{choice} (x{user[f'cat_{choice}']})", value=choice))
    if current.lower() in "rain" and actual_user.rain_minutes > 0:
        choices.append(discord.app_commands.Choice(name=f"Rain ({actual_user.rain_minutes} minutes)", value="rain"))
    for choice in pack_data:
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


# converts string to lowercase alphanumeric characters only
def alnum(string):
    return "".join(item for item in string.lower() if item.isalnum())


async def spawn_cat(ch_id, localcat=None, force_spawn=None):
    try:
        channel = await Channel.get_or_none(channel_id=int(ch_id))
        if not channel:
            raise Exception
    except Exception:
        return False
    if channel.cat or channel.yet_to_spawn > time.time() + 10:
        return False

    if not localcat:
        localcat = random.choices(cattypes, weights=type_dict.values())[0]
    icon = get_emoji(localcat.lower() + "cat")
    file = discord.File(
        f"images/spawn/{localcat.lower()}_cat.png",
    )
    channeley = bot.get_partial_messageable(int(ch_id))

    appearstring = '{emoji} {type} cat has appeared! Type "cat" to catch it!' if not channel.appear else channel.appear

    if int(ch_id) in temp_spawns_storage:
        return False

    temp_spawns_storage.append(int(ch_id))

    try:
        message_is_sus = await channeley.send(
            appearstring.replace("{emoji}", str(icon)).replace("{type}", localcat),
            file=file,
            allowed_mentions=discord.AllowedMentions.all(),
        )
    except discord.Forbidden:
        await channel.delete()
        temp_spawns_storage.remove(int(ch_id))
        return False
    except discord.NotFound:
        await channel.delete()
        temp_spawns_storage.remove(int(ch_id))
        return False
    except Exception:
        temp_spawns_storage.remove(int(ch_id))
        return False

    channel.cat = message_is_sus.id
    channel.yet_to_spawn = 0
    channel.forcespawned = bool(force_spawn)
    channel.cattype = localcat
    await channel.save()
    temp_spawns_storage.remove(int(ch_id))
    logging.debug("Cat spawned, forced: %s", bool(force_spawn))
    return True


async def postpone_reminder(interaction):
    reminder_type = interaction.data["custom_id"]
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
    logging.debug("Reminder postponed: %s", reminder_type)
    await interaction.response.send_message(f"ok, i will remind you <t:{int(time.time()) + 30 * 60}:R>", ephemeral=True)


# a loop for various maintenance which is ran every 5 minutes
async def background_loop():
    global pointlaugh_ratelimit, reactions_ratelimit, last_loop_time, loop_count, catchcooldown, temp_belated_storage, temp_cookie_storage, fakecooldown
    pointlaugh_ratelimit = {}
    reactions_ratelimit = {}
    catchcooldown = {}
    fakecooldown = {}
    await bot.change_presence(activity=discord.CustomActivity(name=f"Catting in {len(bot.guilds):,} servers"))

    # update cookies
    temp_temp_cookie_storage = temp_cookie_storage.copy()
    cookie_updates = []
    for cookie_id, cookies in temp_temp_cookie_storage.items():
        p = await Profile.get_or_create(guild_id=cookie_id[0], user_id=cookie_id[1])
        p.cookies = cookies
        cookie_updates.append(p)
    if cookie_updates:
        await Profile.bulk_update(cookie_updates, "cookies")
    logging.debug("Cookies updated: %d", len(cookie_updates))
    temp_cookie_storage = {}

    # temp_belated_storage cleanup
    # clean up anything older than 1 minute
    baseflake = discord.utils.time_snowflake(datetime.datetime.utcnow() - datetime.timedelta(minutes=1))
    for id in temp_belated_storage.copy().keys():
        if id < baseflake:
            del temp_belated_storage[id]

    if config.TOP_GG_TOKEN:
        async with aiohttp.ClientSession() as session:
            try:
                if not config.MIN_SERVER_SEND or len(bot.guilds) > config.MIN_SERVER_SEND:
                    # send server count to top.gg
                    r = await session.post(
                        f"https://top.gg/api/bots/{bot.user.id}/stats",
                        headers={"Authorization": config.TOP_GG_TOKEN},
                        json={"server_count": len(bot.guilds)},
                    )
                    r.close()

                # post commands to top.gg
                r = await session.post(
                    "https://top.gg/api/v1/projects/@me/commands",
                    headers={"Authorization": config.TOP_GG_TOKEN},
                    json=[command.to_dict(bot.tree) for command in bot.tree._get_all_commands(guild=None) if command.to_dict(bot.tree)["type"] == 1],
                )
                r.close()

            except Exception:
                logging.warning("Posting to top.gg failed.")

    # revive dead catch loops
    counter = 0
    async for channel in Channel.limit(["channel_id"], "yet_to_spawn < $1 AND cat = 0", time.time(), refetch=False):
        counter += 1
        await spawn_cat(str(channel.channel_id))
        await asyncio.sleep(0.1)
    logging.debug("Channels revived: %d", counter)

    # THIS IS CONSENTUAL AND TURNED OFF BY DEFAULT DONT BAN ME
    #
    # i wont go into the details of this because its a complicated mess which took me like solid 30 minutes of planning
    #
    # vote reminders
    proccessed_users = []
    async for user in User.limit(
        ["user_id", "reminder_vote", "vote_streak", "dm_channel_id"],
        "vote_time_topgg != 0 AND vote_time_topgg + 43200 < $1 AND reminder_vote != 0 AND reminder_vote < $1",
        time.time(),
    ):
        if not await Profile.count("user_id = $1 AND reminders_enabled = true LIMIT 1", user.user_id):
            continue
        await asyncio.sleep(0.1)

        view = View(timeout=VIEW_TIMEOUT)
        button = Button(
            emoji=get_emoji("topgg"),
            label=random.choice(vote_button_texts),
            url="https://top.gg/bot/966695034340663367/vote",
        )
        view.add_item(button)

        button = Button(label="Postpone", custom_id="vote")
        button.callback = postpone_reminder
        view.add_item(button)

        try:
            user_dm = await fetch_dm_channel(user)
            await user_dm.send("You can vote now!" if user.vote_streak < 10 else f"Vote now to keep your {user.vote_streak} streak going!", view=view)
        except Exception:
            pass
        # no repeat reminers for now
        user.reminder_vote = 0
        proccessed_users.append(user)

    await User.bulk_update(proccessed_users, "reminder_vote")
    logging.debug("Reminders sent: %d, type: %s", len(proccessed_users), "vote")

    # i know the next two are similiar enough to be merged but its currently dec 30 and i cant be bothered
    # catch reminders
    proccessed_users = []
    async for user in Profile.limit(
        ["id"],
        "(reminders_enabled = true AND reminder_catch != 0) AND ((catch_cooldown != 0 AND catch_cooldown + 43200 < $1) OR (reminder_catch > 1 AND reminder_catch < $1))",
        time.time(),
    ):
        await asyncio.sleep(0.1)

        await refresh_quests(user)
        await user.refresh_from_db()

        quest_data = battle["quests"]["catch"][user.catch_quest]

        embed = discord.Embed(
            title=f"{get_emoji(quest_data['emoji'])} {quest_data['title']}",
            description=f"Reward: **{user.catch_reward}** XP",
            color=Colors.green,
        )

        view = View(timeout=VIEW_TIMEOUT)
        button = Button(label="Postpone", custom_id=f"catch_{user.guild_id}")
        button.callback = postpone_reminder
        view.add_item(button)

        guild = bot.get_guild(user.guild_id)
        if not guild:
            guild_name = "a server"
        else:
            guild_name = guild.name

        try:
            user_user = await User.get_or_create(id=user.user_id)
            user_dm = await fetch_dm_channel(user_user)
            await user_dm.send(f"A new quest is available in {guild_name}!", embed=embed, view=view)
        except Exception:
            pass
        user.reminder_catch = 0
        proccessed_users.append(user)

    if proccessed_users:
        await Profile.bulk_update(proccessed_users, "reminder_catch")
    logging.debug("Reminders sent: %d, type: %s", len(proccessed_users), "catch")

    # misc reminders
    proccessed_users = []
    async for user in Profile.limit(
        ["id"],
        "(reminders_enabled = true AND reminder_misc != 0) AND ((misc_cooldown != 0 AND misc_cooldown + 43200 < $1) OR (reminder_misc > 1 AND reminder_misc < $1))",
        time.time(),
    ):
        await asyncio.sleep(0.1)

        await refresh_quests(user)
        await user.refresh_from_db()

        quest_data = battle["quests"]["misc"][user.misc_quest]

        embed = discord.Embed(
            title=f"{get_emoji(quest_data['emoji'])} {quest_data['title']}",
            description=f"Reward: **{user.misc_reward}** XP",
            color=Colors.green,
        )

        view = View(timeout=VIEW_TIMEOUT)
        button = Button(label="Postpone", custom_id=f"misc_{user.guild_id}")
        button.callback = postpone_reminder
        view.add_item(button)

        guild = bot.get_guild(user.guild_id)
        if not guild:
            guild_name = "a server"
        else:
            guild_name = guild.name

        try:
            user_user = await User.get_or_create(user_id=user.user_id)
            user_dm = await fetch_dm_channel(user_user)
            await user_dm.send(f"A new quest is available in {guild_name}!", embed=embed, view=view)
        except Exception:
            pass
        user.reminder_misc = 0
        proccessed_users.append(user)

    if proccessed_users:
        await Profile.bulk_update(proccessed_users, "reminder_misc")
    logging.debug("Reminders sent: %d, type: %s", len(proccessed_users), "misc")

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

        if loop_count % 12 == 0:
            backup_file = "/root/backup.dump"
            try:
                # delete the previous backup file
                os.remove(backup_file)
            except Exception:
                pass

            try:
                process = await asyncio.create_subprocess_shell(f"PGPASSWORD={config.DB_PASS} pg_dump -U cat_bot -Fc -Z 9 -f {backup_file} cat_bot")
                await process.wait()

                if exportbackup:
                    event_loop = asyncio.get_event_loop()
                    await event_loop.run_in_executor(None, exportbackup.export)

                    await backupchannel.send(f"In {len(bot.guilds)} servers, loop {loop_count}.\nBackup exported.")
                else:
                    await backupchannel.send(f"In {len(bot.guilds)} servers, loop {loop_count}.", file=discord.File(backup_file))
            except Exception as e:
                logging.warning(f"Error during backup: {e}")
        else:
            await backupchannel.send(f"In {len(bot.guilds)} servers, loop {loop_count}.")

    loop_count += 1


# fetch app emojis early
async def on_connect():
    global emojis
    if len(emojis) == 0:
        emojis = {emoji.name: str(emoji) for emoji in await bot.fetch_application_emojis()}


# some code which is run when bot is started
async def on_ready():
    global OWNER_ID, on_ready_debounce, gen_credits, emojis
    if on_ready_debounce:
        return
    on_ready_debounce = True
    logging.info("cat is now online")
    if len(emojis) == 0:
        emojis = {emoji.name: str(emoji) for emoji in await bot.fetch_application_emojis()}
    appinfo = bot.application
    if appinfo.team and appinfo.team.owner_id:
        OWNER_ID = appinfo.team.owner_id
    else:
        OWNER_ID = appinfo.owner.id

    testers = [
        712639066373619754,
        902862104971849769,
        709374062237057074,
        520293520418930690,
        1004128541853618197,
        839458185059500032,
    ]

    # fetch github contributors
    url = "https://api.github.com/repos/milenakos/cat-bot/contributors"
    contributors = []

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"}) as response:
            if response.status == 200:
                data = await response.json()
                for contributor in data:
                    login = contributor["login"].replace("_", r"\_")
                    if login not in ["milenakos", "ImgBotApp"]:
                        contributors.append(login)
            else:
                logging.warning(f"Error: {response.status} - {await response.text()}")

    # fetch testers
    tester_users = []
    try:
        for i in testers:
            user = await bot.fetch_user(i)
            tester_users.append(user.name.replace("_", r"\_"))
    except Exception:
        # death
        pass

    gen_credits = "\n".join(
        [
            "Made by **Lia Milenakos**",
            "With contributions from **" + ", ".join(contributors) + "**",
            "Original Cat Image: **pathologicals**",
            "APIs: **catfact.ninja, weilbyte.dev, wordnik.com, thecatapi.com**",
            "Open Source Projects: **[discord.py](https://github.com/Rapptz/discord.py), [asyncpg](https://github.com/MagicStack/asyncpg), [gateway-proxy](https://github.com/Gelbpunkt/gateway-proxy)**",
            "Art, suggestions, and a lot more: **TheTrashCell**",
            "Banner art: **2braincelledcreature**",
            "Testers: **" + ", ".join(tester_users) + "**",
            "Enjoying the bot: **You <3**",
        ]
    )


# this is all the code which is ran on every message sent
# a lot of it is for easter eggs or achievements
async def on_message(message: discord.Message):
    global emojis, last_loop_time
    text = message.content
    if not bot.user or message.author.id == bot.user.id:
        return

    if time.time() > last_loop_time + 300:
        last_loop_time = time.time()
        bot.loop.create_task(background_loop())

    if message.guild is None and not message.author.bot:
        if text.startswith("disable"):
            # disable reminders
            try:
                where = text.split(" ")[1]
                user = await Profile.get_or_create(guild_id=int(where), user_id=message.author.id)
                user.reminders_enabled = False
                await user.save()
                await message.channel.send("reminders disabled")
            except Exception:
                await message.channel.send("failed. check if your guild id is correct")
                return
        elif text == "lol_i_have_dmed_the_cat_bot_and_got_an_ach":
            await message.channel.send('which part of "send in server" was unclear?')
        else:
            await message.channel.send('good job! please send "lol_i_have_dmed_the_cat_bot_and_got_an_ach" in server to get your ach!')
        return

    achs = [
        ["cat?", "startswith", "???"],
        ["catn", "exact", "catn"],
        ["cat!coupon jr0f-pzka", "exact", "coupon_user"],
        ["pineapple", "exact", "pineapple"],
        ["cat!i_like_cat_website", "exact", "website_user"],
        ["cat!i_clicked_there", "exact", "click_here"],
        ["cat!lia_is_cute", "exact", "nerd"],
        ["i read help", "exact", "patient_reader"],
        [str(bot.user.id), "in", "who_ping"],
        ["lol_i_have_dmed_the_cat_bot_and_got_an_ach", "exact", "dm"],
        ["dog", "exact", "not_quite"],
        ["egril", "exact", "egril"],
        ["-.-. .- -", "exact", "morse_cat"],
        ["tac", "exact", "reverse"],
        ["cat!n4lltvuCOKe2iuDCmc6JsU7Jmg4vmFBj8G8l5xvoDHmCoIJMcxkeXZObR6HbIV6", "veryexact", "dataminer"],
    ]

    reactions = [
        ["v1;", "custom", "why_v1"],
        ["proglet", "custom", "professor_cat"],
        ["xnopyt", "custom", "vanish"],
        ["silly", "custom", "sillycat"],
        ["indev", "vanilla", "🐸"],
        ["bleh", "custom", "blepcat"],
        ["blep", "custom", "blepcat"],
    ]

    responses = [
        [
            "cellua good",
            "in",
            ".".join([str(random.randint(2, 254)) for _ in range(4)]),
        ],
        [
            "https://tenor.com/view/this-cat-i-have-hired-this-cat-to-stare-at-you-hired-cat-cat-stare-gif-26392360",
            "exact",
            "https://tenor.com/view/cat-staring-cat-gif-16983064494644320763",
        ],
    ]

    # here are some automation hooks for giving out purchases and similiar
    if config.RAIN_CHANNEL_ID and message.channel.id == config.RAIN_CHANNEL_ID and text.lower().startswith("cat!rain"):
        arguements = text.split(" ")
        user = await User.get_or_create(user_id=int(arguements[1]))
        rain_duration = arguements[2]
        if not user.rain_minutes:
            user.rain_minutes = 0

        if rain_duration == "short":
            user.rain_minutes += 2
        elif rain_duration == "medium":
            user.rain_minutes += 10
        elif rain_duration == "long":
            user.rain_minutes += 20
        else:
            user.rain_minutes += int(rain_duration)
            user.rain_minutes_bought += int(rain_duration)
        user.premium = True
        await user.save()

        # try to dm the user the thanks msg
        try:
            person = await fetch_dm_channel(user)
            await person.send(
                f"**You have recieved {rain_duration} minutes of Cat Rain!** ☔\n\nThanks for your support!\nYou can start a rain with `/rain`. By buying you also get access to `/editprofile` and `/customcat` commands as well as a role in [our Discord server](<https://discord.gg/staring>)!\n\nEnjoy your goods!"
            )
        except Exception:
            pass

        return

    react_count = 0

    # :staring_cat: reaction on "bullshit"
    if " " not in text and len(text) > 7 and text.isalnum():
        s = text.lower()
        total_vow = 0
        total_illegal = 0
        for i in "aeuio":
            total_vow += s.count(i)
        illegal = [
            "bk",
            "fq",
            "jc",
            "jt",
            "mj",
            "qh",
            "qx",
            "vj",
            "wz",
            "zh",
            "bq",
            "fv",
            "jd",
            "jv",
            "mq",
            "qj",
            "qy",
            "vk",
            "xb",
            "zj",
            "bx",
            "fx",
            "jf",
            "jw",
            "mx",
            "qk",
            "qz",
            "vm",
            "xg",
            "zn",
            "cb",
            "fz",
            "jg",
            "jx",
            "mz",
            "ql",
            "sx",
            "vn",
            "xj",
            "zq",
            "cf",
            "gq",
            "jh",
            "jy",
            "pq",
            "qm",
            "sz",
            "vp",
            "xk",
            "zr",
            "cg",
            "gv",
            "jk",
            "jz",
            "pv",
            "qn",
            "tq",
            "vq",
            "xv",
            "zs",
            "cj",
            "gx",
            "jl",
            "kq",
            "px",
            "qo",
            "tx",
            "vt",
            "xz",
            "zx",
            "cp",
            "hk",
            "jm",
            "kv",
            "qb",
            "qp",
            "vb",
            "vw",
            "yq",
            "cv",
            "hv",
            "jn",
            "kx",
            "qc",
            "qr",
            "vc",
            "vx",
            "yv",
            "cw",
            "hx",
            "jp",
            "kz",
            "qd",
            "qs",
            "vd",
            "vz",
            "yz",
            "cx",
            "hz",
            "jq",
            "lq",
            "qe",
            "qt",
            "vf",
            "wq",
            "zb",
            "dx",
            "iy",
            "jr",
            "lx",
            "qf",
            "qv",
            "vg",
            "wv",
            "zc",
            "fk",
            "jb",
            "js",
            "mg",
            "qg",
            "qw",
            "vh",
            "wx",
            "zg",
        ]
        for j in illegal:
            if j in s:
                total_illegal += 1
        vow_perc = 0
        const_perc = len(text)
        if total_vow != 0:
            vow_perc = len(text) / total_vow
        if total_vow != len(text):
            const_perc = len(text) / (len(text) - total_vow)
        if (vow_perc <= 3 and const_perc >= 6) or total_illegal >= 2:
            try:
                if reactions_ratelimit.get(message.guild.id, 0) < 100:
                    await message.add_reaction(get_emoji("staring_cat"))
                    react_count += 1
                    reactions_ratelimit[message.guild.id] = reactions_ratelimit.get(message.guild.id, 0) + 1
                    logging.debug("Reaction added: %s", "staring_cat")
            except Exception:
                pass

    try:
        if "robotop" in message.author.name.lower() and "i rate **cat" in message.content.lower():
            icon = str(get_emoji("no_ach"))
            await message.reply("**RoboTop**, I rate **you** 0 cats " + icon * 5)

        if "leafbot" in message.author.name.lower() and "hmm... i would rate cat" in message.content.lower():
            icon = str(get_emoji("no_ach")) + " "
            await message.reply("Hmm... I would rate you **0 cats**! " + icon * 5)
    except Exception:
        pass

    if message.author.bot or message.webhook_id is not None:
        return

    for achievement in achs:
        match_text, match_method, achievement_name = achievement
        text_lowered = text.lower()
        if any(
            [
                match_method == "startswith" and text_lowered.startswith(match_text),
                match_method == "re" and re.search(match_text, text_lowered),
                match_method == "exact" and match_text == text_lowered,
                match_method == "veryexact" and match_text == text,
                match_method == "in" and match_text in text_lowered,
            ]
        ):
            await achemb(message, achievement_name, "reply")

    if unidecode.unidecode(text).lower().strip() in [
        "mace",
        "katu",
        "kot",
        "koshka",
        "macka",
        "gat",
        "gata",
        "kocka",
        "kat",
        "poes",
        "kass",
        "kissa",
        "chat",
        "chatte",
        "gato",
        "katze",
        "gata",
        "macska",
        "kottur",
        "gatto",
        "getta",
        "kakis",
        "kate",
        "qattus",
        "qattusa",
        "katt",
        "kit",
        "kishka",
        "cath",
        "qitta",
        "katu",
        "pisik",
        "biral",
        "kyaung",
        "mao",
        "pusa",
        "kata",
        "billi",
        "kucing",
        "neko",
        "bekku",
        "mysyq",
        "chhma",
        "goyangi",
        "pucha",
        "manjar",
        "muur",
        "biralo",
        "gorbeh",
        "punai",
        "pilli",
        "kedi",
        "mushuk",
        "meo",
        "demat",
        "nwamba",
        "jangwe",
        "adure",
        "katsi",
        "bisad,",
        "paka",
        "ikati",
        "ologbo",
        "wesa",
        "popoki",
        "piqtuq",
        "negeru",
        "poti",
        "mosi",
        "michi",
        "pusi",
        "oratii",
    ]:
        await achemb(message, "multilingual", "reply")

    for reaction in reactions:
        reaction_prompt, reaction_type, reaction_name = reaction
        if reaction_prompt in text.lower() and reactions_ratelimit.get(message.guild.id, 0) < 100:
            if reaction_type == "custom":
                resolved_emoji = get_emoji(reaction_name)
            elif reaction_type == "vanilla":
                resolved_emoji = reaction_name

            try:
                await message.add_reaction(resolved_emoji)
                react_count += 1
                reactions_ratelimit[message.guild.id] = reactions_ratelimit.get(message.guild.id, 0) + 1
                logging.debug("Reaction added: %s", reaction_name)
            except Exception:
                pass

    for response in responses:
        match_method, match_text, response_reply = response
        text_lowered = text.lower()
        if any(
            [
                match_method == "startswith" and text_lowered.startswith(match_text),
                match_method == "re" and re.search(match_text, text_lowered),
                match_method == "exact" and match_text == text_lowered,
                match_method == "in" and match_text in text_lowered,
            ]
        ):
            try:
                await message.reply(response_reply)
            except Exception:
                pass
            logging.debug("Response sent: %s", response_reply)

    try:
        if message.author in message.mentions and reactions_ratelimit.get(message.guild.id, 0) < 100:
            await message.add_reaction(get_emoji("staring_cat"))
            react_count += 1
            reactions_ratelimit[message.guild.id] = reactions_ratelimit.get(message.guild.id, 0) + 1
            logging.debug("Reaction added: %s", "staring_cat")
    except Exception:
        pass

    if react_count >= 3:
        await achemb(message, "silly", "reply")

    if (":place_of_worship:" in text or "🛐" in text) and (":cat:" in text or ":staring_cat:" in text or "🐱" in text):
        await achemb(message, "worship", "reply")

    if text.lower() in ["testing testing 1 2 3", "cat!ach"]:
        try:
            await message.reply("test success")
        except Exception:
            # test failure
            pass
        logging.debug("Response sent: %s", "test success")
        await achemb(message, "test_ach", "reply")

    if text.lower() == "please do not the cat":
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.author.id)
        user.cat_Fine -= 1
        await user.save()
        try:
            personname = message.author.name.replace("_", "\\_")
            await message.reply(f"ok then\n{personname} lost 1 fine cat!!!1!\nYou now have {user.cat_Fine:,} cats of dat type!")
        except Exception:
            pass
        await achemb(message, "pleasedonotthecat", "reply")
        logging.debug("Response sent: %s", "please do not the cat")

    if text.lower() == "please do the cat":
        thing = discord.File("images/socialcredit.jpg", filename="socialcredit.jpg")
        try:
            await message.reply(file=thing)
        except Exception:
            pass
        await achemb(message, "pleasedothecat", "reply")
        logging.debug("Response sent: %s", "please do the cat")

    if text.lower() == "car":
        file = discord.File("images/car.png", filename="car.png")
        embed = discord.Embed(title="car!", color=Colors.brown).set_image(url="attachment://car.png")
        try:
            await message.reply(file=file, embed=embed)
        except Exception:
            pass
        await achemb(message, "car", "reply")
        logging.debug("Response sent: %s", "car")

    if text.lower() == "cart":
        file = discord.File("images/cart.png", filename="cart.png")
        embed = discord.Embed(title="cart!", color=Colors.brown).set_image(url="attachment://cart.png")
        try:
            await message.reply(file=file, embed=embed)
        except Exception:
            pass
        logging.debug("Response sent: %s", "cart")

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
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.author.id)
        channel = await Channel.get_or_none(channel_id=message.channel.id)
        if not channel or not channel.cat or channel.cat in temp_catches_storage or user.timeout > time.time():
            # laugh at this user
            # (except if rain is active, we dont have perms or channel isnt setupped, or we laughed way too much already)
            if channel and channel.cat_rains == 0 and pointlaugh_ratelimit.get(message.channel.id, 0) < 10:
                try:
                    await message.add_reaction(get_emoji("pointlaugh"))
                    pointlaugh_ratelimit[message.channel.id] = pointlaugh_ratelimit.get(message.channel.id, 0) + 1
                except Exception:
                    pass

            # belated battlepass
            if message.channel.id in temp_belated_storage:
                current_time = message.created_at.timestamp()
                belated = temp_belated_storage[message.channel.id]
                if (
                    channel
                    and "users" in belated
                    and "time" in belated
                    and belated.get("timestamp", 0) + 3 > current_time
                    and message.author.id not in belated["users"]
                ):
                    belated["users"].append(message.author.id)
                    temp_belated_storage[message.channel.id] = belated
                    await progress(message, user, "3cats", True)
                    if channel.cattype == "Fine":
                        await progress(message, user, "2fine", True)
                    if channel.cattype == "Good":
                        await progress(message, user, "good", True)
                    if belated.get("time", 10) + current_time - belated.get("timestamp", 0) < 10:
                        await progress(message, user, "under10", True)
                    if random.randint(0, 1) == 0:
                        await progress(message, user, "even", True)
                    else:
                        await progress(message, user, "odd", True)
                    if channel.cattype and channel.cattype not in ["Fine", "Nice", "Good"]:
                        await progress(message, user, "rare+", True)
                    if user.catnip_active >= time.time() or user.hibernation:
                        await bounty(message, user, channel.cattype)
                    total_count = await Prism.count("guild_id = $1", message.guild.id)
                    user_count = await Prism.count("guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
                    global_boost = 0.06 * math.log(2 * total_count + 1)
                    prism_boost = global_boost + 0.03 * math.log(2 * user_count + 1)
                    if prism_boost > random.random():
                        await progress(message, user, "prism", True)
                    if user.catch_quest == "finenice":
                        # 0 none
                        # 1 fine
                        # 2 nice
                        # 3 both
                        if channel.cattype == "Fine" and user.catch_progress in [0, 2]:
                            await progress(message, user, "finenice", True)
                        elif channel.cattype == "Nice" and user.catch_progress in [0, 1]:
                            await progress(message, user, "finenice", True)
                            await progress(message, user, "finenice", True)
        else:
            pls_remove_me_later_k_thanks = channel.cat
            temp_catches_storage.append(channel.cat)
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
            force_rain_summary = None

            try:
                current_time = message.created_at.timestamp()
                channel.lastcatches = current_time
                cat_temp = channel.cat
                channel.cat = 0
                try:
                    if channel.cattype != "":
                        catchtime = discord.utils.snowflake_time(cat_temp)
                        le_emoji = channel.cattype
                    else:
                        var = await message.channel.fetch_message(cat_temp)
                        catchtime = var.created_at
                        catchcontents = var.content

                        partial_type = None
                        for v in allowedemojis:
                            if v in catchcontents:
                                partial_type = v
                                break

                        if not partial_type and "thetrashcellcat" in catchcontents:
                            partial_type = "trashcat"
                            le_emoji = "Trash"
                        else:
                            if not partial_type:
                                return

                            for i in cattypes:
                                if i.lower() in partial_type:
                                    le_emoji = i
                                    break
                except Exception:
                    try:
                        await message.channel.send(f"oopsie poopsie i cant access the original message but {message.author.mention} *did* catch a cat rn")
                    except Exception:
                        pass
                    return

                send_target = message.channel
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
                        caught_time = caught_time + str(int(days)) + " days "
                    if hours:
                        caught_time = caught_time + str(int(hours)) + " hours "
                    if minutes:
                        caught_time = caught_time + str(int(minutes)) + " minutes "
                    if seconds:
                        pre_time = round(seconds, 3)
                        if pre_time % 1 == 0:
                            # replace .0 with .00 basically
                            pre_time = str(int(pre_time)) + ".00"
                        caught_time = caught_time + str(pre_time) + " seconds "
                    do_time = True
                    if not caught_time:
                        caught_time = "0.000 seconds (woah) "
                    if time_caught <= 0:
                        do_time = False
                except Exception:
                    # if some of the above explodes just give up
                    do_time = False
                    caught_time = "undefined amounts of time "

                try:
                    if time_caught >= 0:
                        temp_belated_storage[message.channel.id] = {"time": time_caught, "users": [message.author.id], "timestamp": current_time}
                except Exception:
                    pass

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

                if user.perks:
                    if user.catnip_active < time.time():
                        if user.catnip_active != 1:
                            user.catnip_active = 1
                            suffix_string += f"\n{get_emoji('catnip_disabled')} Your catnip expired! Run /catnip to get more."
                        perks = []
                    else:
                        perks = user.perks
                    perks_info = catnip_list["perks"]

                    if len(perks) > 0:
                        logging.debug("Catnip active with %d perks", len(perks))

                    for perk in perks:
                        h = perk.split("_")
                        rarity = int(h[0])
                        type = int(h[1])
                        id = perks_info[type - 1]["id"]

                        if id == "double":
                            double_chance += perks_info[0]["values"][rarity]
                            single_chance -= perks_info[0]["values"][rarity]
                        elif id == "triple_none":
                            triple_chance += perks_info[1]["values"][rarity]
                            none_chance += perks_info[1]["values"][rarity] / 2
                            single_chance -= perks_info[1]["values"][rarity] * (1.5)
                        elif "pack" in id:
                            for num, pack in enumerate(pack_data):
                                if pack["name"].lower() in id:
                                    packs.append((num, perks_info[type - 1]["values"][rarity]))
                                    break
                        elif id == "double_boost":
                            double_boost_chance += perks_info[8]["values"][rarity]
                        elif id == "triple_ach":
                            purr_all_triple = True
                        elif id == "timer_add":
                            timer_add_chance += perks_info[10]["values"][rarity]
                        elif id == "rain_boost":
                            rain_chance += perks_info[12]["values"][rarity]
                        elif id == "double_first":
                            double_first += perks_info[13]["values"][rarity]

                    for i in packs:
                        chance = random.random() * 100
                        if chance <= i[1]:
                            packs_gained.append(pack_data[i[0]]["name"])
                            user[f"pack_{pack_data[i[0]]['name'].lower()}"] += 1
                            suffix_string += f"\n{get_emoji(pack_data[i[0]]['name'].lower() + 'pack')} You got a {pack_data[i[0]]['name']} pack! You now have {user[f'pack_{pack_data[i[0]]["name"].lower()}']:,} packs of this type!"

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
                    if none_chance < 0:
                        none_chance = 0

                    if random.random() * 100 < rain_chance:
                        if channel.cat_rains == 0:
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
                        suffix_string += f"\n{get_emoji('catnip')} catnip worked! your cat was TRIPLED by catnip!1!!1!"
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

                # blessings
                bless_chance = await User.sum("rain_minutes_bought", "blessings_enabled = true") * 0.0001 * 0.01
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
                    asyncio.create_task(blesser.save())

                    logging.debug("Catch blessed")

                    if blesser.blessings_anonymous:
                        blesser_text = "💫 Anonymous Supporter"
                    else:
                        blesser_text = f"{blesser.emoji or '💫'} {blesser.username}"

                    if silly_amount > 1:
                        suffix_string += f"\n{blesser_text} blessed your catch and it got doubled!"
                    else:
                        suffix_string += f"\n{blesser_text} blessed your catch and it got saved!"

                # calculate prism boost
                total_prisms = await Prism.collect("guild_id = $1", message.guild.id)
                user_prisms = await Prism.collect("guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
                global_boost = 0.06 * math.log(2 * len(total_prisms) + 1)
                user_boost = global_boost + 0.03 * math.log(2 * len(user_prisms) + 1)
                did_boost = False
                if user_boost > random.random():
                    # determine whodunnit
                    if random.uniform(0, user_boost) > global_boost:
                        # boost from our own prism
                        prism_which_boosted = random.choice(user_prisms)
                    else:
                        # boost from any prism
                        prism_which_boosted = random.choice(total_prisms)

                    if prism_which_boosted.user_id == message.author.id:
                        boost_applied_prism = "Your prism " + prism_which_boosted.name
                    else:
                        boost_applied_prism = f"<@{prism_which_boosted.user_id}>'s prism " + prism_which_boosted.name

                    did_boost = True
                    user.boosted_catches += 1
                    prism_which_boosted.catches_boosted += 1
                    asyncio.create_task(prism_which_boosted.save())
                    logging.debug("Boosted from %s", le_emoji)
                    try:
                        le_old_emoji = le_emoji
                        if double_boost:
                            le_emoji = cattypes[cattypes.index(le_emoji) + 2]
                        else:
                            le_emoji = cattypes[cattypes.index(le_emoji) + 1]
                        normal_bump = True
                    except IndexError:
                        # :SILENCE:
                        # This block handles cases where boosting goes beyond the maximum cat rarity (eGirl).
                        # Previously, a check `if double_boost and le_emoji == 'eGirl'` ensured only eGirl triggered the mega-rain.
                        # This was removed so that ANY double boost that fails (e.g., Ultimate -> Index+2) also triggers the 1200 boost.
                        normal_bump = False
                        if not channel.forcespawned:
                            if double_boost:
                                # rainboost is the duration of the rain in seconds.
                                # 1200 seconds = 20 minutes of rain.
                                # This rewards the player for a "failed" double boost on a high-tier cat (Ultimate or eGirl).
                                rainboost = 1200
                            else:
                                # 600 seconds = 10 minutes of rain.
                                rainboost = 600
                            logging.debug("Boosted to rain: %d", rainboost)
                            channel.cat_rains += math.ceil(rainboost / 2.75)
                            if channel.cat_rains > math.ceil(rainboost / 2.75):
                                await message.channel.send(f"# ‼️‼️ RAIN EXTENDED BY {int(rainboost / 60)} MINUTES ‼️‼️")
                                await message.channel.send(f"# ‼️‼️ RAIN EXTENDED BY {int(rainboost / 60)} MINUTES ‼️‼️")
                                await message.channel.send(f"# ‼️‼️ RAIN EXTENDED BY {int(rainboost / 60)} MINUTES ‼️‼️")
                            else:
                                force_rain_summary = config.cat_cought_rain.get(channel.channel_id, {}).copy()
                                decided_time = random.uniform(1, 2)
                                channel.rain_should_end = int(time.time() + decided_time)
                                channel.yet_to_spawn = 0
                                config.cat_cought_rain[channel.channel_id] = {}
                                config.rain_starter[channel.channel_id] = message.author.id
                                bot.loop.create_task(rain_recovery_loop(channel))

                    if normal_bump:
                        if double_boost:
                            suffix_string += f"\n{get_emoji('prism')} {boost_applied_prism} boosted this catch twice from a {get_emoji(le_old_emoji.lower() + 'cat')} {le_old_emoji} cat to a {get_emoji(le_emoji.lower() + 'cat')} {le_emoji} cat!"
                        else:
                            suffix_string += f"\n{get_emoji('prism')} {boost_applied_prism} boosted this catch from a {get_emoji(le_old_emoji.lower() + 'cat')} {le_old_emoji} cat!"
                    elif not channel.forcespawned:
                        if double_boost:
                            suffix_string += f"\n{get_emoji('prism')} {boost_applied_prism} tried to boost this catch, but failed! A 20m rain will start!"
                        else:
                            suffix_string += f"\n{get_emoji('prism')} {boost_applied_prism} tried to boost this catch, but failed! A 10m rain will start!"

                icon = get_emoji(le_emoji.lower() + "cat")

                if channel.channel_id in config.cat_cought_rain:
                    if le_emoji not in config.cat_cought_rain[channel.channel_id]:
                        config.cat_cought_rain[channel.channel_id][le_emoji] = []
                    for _ in range(silly_amount):
                        config.cat_cought_rain[channel.channel_id][le_emoji].append(f"<@{user.user_id}>")
                    for i in packs_gained:
                        if i not in config.cat_cought_rain[channel.channel_id]:
                            config.cat_cought_rain[channel.channel_id][i] = []
                        config.cat_cought_rain[channel.channel_id][i].append(f"<@{user.user_id}>")

                if random.randint(0, 7) == 0:
                    # shill rains
                    suffix_string += f"\n☔ get tons of cats and have fun: </rain:{RAIN_ID}>"
                if random.randint(0, 19) == 0:
                    # diplay a hint/fun fact
                    suffix_string += "\n💡 " + random.choice(hints)

                custom_cough_strings = {
                    "Corrupt": "{username} coought{type} c{emoji}at!!!!404!\nYou now BEEP {count} cats of dCORRUPTED!!\nthis fella wa- {time}!!!!",
                    "eGirl": "{username} cowought {emoji} {type} cat~~ ^^\nYou-u now *blushes* hawe {count} cats of dat tywe~!!!\nthis fella was <3 cought in {time}!!!!",
                    "Rickroll": "{username} cought {emoji} {type} cat!!!!1!\nYou will never give up {count} cats of dat type!!!\nYou wouldn't let them down even after {time}!!!!",
                    "Sus": "{username} cought {emoji} {type} cat!!!!1!\nYou have vented infront of {count} cats of dat type!!!\nthis sussy baka was cought in {time}!!!!",
                    "Professor": "{username} caught {emoji} {type} cat!\nThou now hast {count} cats of that type!\nThis fellow was caught 'i {time}!",
                    "8bit": "{username} c0ught {emoji} {type} cat!!!!1!\nY0u n0w h0ve {count} cats 0f dat type!!!\nth1s fe11a was c0ught 1n {time}!!!!",
                    "Reverse": "!!!!{time} in cought was fella this\n!!!type dat of cats {count} have now You\n!1!!!!cat {type} {emoji} cought {username}",
                }

                if channel.cought:
                    # custom spawn message
                    coughstring = channel.cought
                elif le_emoji in custom_cough_strings:
                    # custom type message
                    coughstring = custom_cough_strings[le_emoji]
                else:
                    # default
                    coughstring = "{username} cought {emoji} {type} cat!!!!1!\nYou now have {count} cats of dat type!!!\nthis fella was cought in {time}!!!!"

                view = None
                button = None

                async def dark_market_cutscene(interaction):
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

                    dark_market_followups = [
                        "you walk up to them. the dark voice says:",
                        "**???**: Hello. We have a unique deal for you.",
                        "**???**: To access our services, run /catnip.",
                        "**???**: You won't be disappointed.",
                        "before you manage to process that, the figure disappears. will you figure out whats going on?",
                        "the only choice is to go to that place.",
                    ]

                    for phrase in dark_market_followups:
                        await asyncio.sleep(5)
                        await interaction.followup.send(phrase, ephemeral=True)

                    await achemb(message, "dark_market", "followup")

                vote_time_user = await User.get_or_create(user_id=message.author.id)
                if random.randint(0, 10) == 0 and user.total_catches > 50 and not user.dark_market_active:
                    button = Button(label="You see a shadow...", style=ButtonStyle.red)
                    button.callback = dark_market_cutscene
                elif config.WEBHOOK_VERIFY and vote_time_user.vote_time_topgg + 43200 < time.time():
                    button = Button(
                        emoji=get_emoji("topgg"),
                        label=random.choice(vote_button_texts),
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

                user[f"cat_{le_emoji}"] += silly_amount
                new_count = user[f"cat_{le_emoji}"]

                async def delete_cat():
                    try:
                        cat_spawn = send_target.get_partial_message(cat_temp)
                        await cat_spawn.delete()
                    except Exception:
                        pass

                async def send_confirm():
                    try:
                        kwargs = {}
                        if view:
                            kwargs["view"] = view

                        await send_target.send(
                            coughstring.replace("{username}", message.author.name.replace("_", "\\_"))
                            .replace("{emoji}", str(icon))
                            .replace("{type}", le_emoji)
                            .replace("{count}", f"{new_count:,}")
                            .replace("{time}", caught_time[:-1])
                            + suffix_string,
                            **kwargs,
                        )
                    except Exception:
                        # Silently fail if we can't send the confirmation message (e.g. permission issues)
                        pass

                await asyncio.gather(delete_cat(), send_confirm())

                logging.debug("Caught (pre-boost) %d %s", 1, channel.cattype)
                logging.debug("Caught (post-boost) %d %s", silly_amount, le_emoji)

                user.total_catches += 1
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

                if random.randint(0, 1000) == 69:
                    await achemb(message, "lucky", "send")
                if message.content == "CAT":
                    await achemb(message, "loud_cat", "send")
                if bot.user in message.mentions and message.reference.message_id == cat_temp:
                    await achemb(message, "ping_reply", "send")
                if channel.cat_rains > 0:
                    await achemb(message, "cat_rain", "send")

                await achemb(message, "first", "send")

                if user.time <= 5:
                    await achemb(message, "fast_catcher", "send")

                if user.timeslow >= 3600:
                    await achemb(message, "slow_catcher", "send")

                if time_caught in [3.14, 31.41, 31.42, 194.15, 194.16, 1901.59, 11655.92, 11655.93]:
                    await achemb(message, "pie", "send")

                if time_caught > 0 and time_caught == int(time_caught):
                    await achemb(message, "perfection", "send")

                if did_boost:
                    await achemb(message, "boosted", "send")

                if "undefined" not in caught_time and time_caught > 0:
                    raw_digits = "".join(char for char in caught_time[:-1] if char.isdigit())
                    if len(set(raw_digits)) == 1:
                        await achemb(message, "all_the_same", "send")

                if suffix_string.count("\n") >= 4:
                    await achemb(message, "certified_yapper", "send")

                # handle battlepass
                await progress(message, user, "3cats")
                if channel.cattype == "Fine":
                    await progress(message, user, "2fine")
                if channel.cattype == "Good":
                    await progress(message, user, "good")
                if time_caught >= 0 and time_caught < 10:
                    await progress(message, user, "under10")
                if time_caught >= 0 and int(time_caught) % 2 == 0:
                    await progress(message, user, "even")
                if time_caught >= 0 and int(time_caught) % 2 == 1:
                    await progress(message, user, "odd")
                if channel.cattype and channel.cattype not in ["Fine", "Nice", "Good"]:
                    await progress(message, user, "rare+")
                if did_boost:
                    await progress(message, user, "prism")
                if user.catch_quest == "finenice":
                    # 0 none
                    # 1 fine
                    # 2 nice
                    # 3 both
                    if channel.cattype == "Fine" and user.catch_progress in [0, 2]:
                        await progress(message, user, "finenice")
                    elif channel.cattype == "Nice" and user.catch_progress in [0, 1]:
                        await progress(message, user, "finenice")
                        await progress(message, user, "finenice")

                # handle catnip bounties
                await bounty(message, user, channel.cattype)
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
                    try:
                        temp_catches_storage.remove(pls_remove_me_later_k_thanks)
                    except Exception:
                        pass
                    await spawn_cat(str(message.channel.id))
                else:
                    await channel.save()
                    try:
                        temp_catches_storage.remove(pls_remove_me_later_k_thanks)
                    except Exception:
                        pass

    # only letting the owner of the bot access anything past this point
    if message.author.id != OWNER_ID:
        return

    # those are "owner" commands which are not really interesting
    if text.lower().startswith("cat!sweep"):
        try:
            channel = await Channel.get_or_none(channel_id=message.channel.id)
            channel.cat = 0
            await channel.save()
            await message.reply("success")
        except Exception:
            pass
    if text.lower().startswith("cat!rain"):
        # syntax: cat!rain 553093932012011520 short
        things = text.split(" ")
        user = await User.get_or_create(user_id=int(things[1]))
        if not user.rain_minutes:
            user.rain_minutes = 0
        if things[2] == "short":
            user.rain_minutes += 2
        elif things[2] == "medium":
            user.rain_minutes += 10
        elif things[2] == "long":
            user.rain_minutes += 20
        else:
            user.rain_minutes += int(things[2])
        user.premium = True
        await user.save()
    if text.lower().startswith("cat!restart"):
        try:
            await message.reply("restarting!")
        except Exception:
            pass
        os.system("git pull")
        if config.WEBHOOK_VERIFY:
            await vote_server.cleanup()
        await bot.cat_bot_reload_hook("db" in text)  # pyright: ignore
    if text.lower().startswith("cat!print"):
        # just a simple one-line with no async (e.g. 2+3)
        try:
            await message.reply(eval(text[9:]))
        except Exception:
            try:
                await message.reply(traceback.format_exc())
            except Exception:
                pass
    if text.lower().startswith("cat!eval"):
        # complex eval, multi-line + async support
        # requires the full `await message.channel.send(2+3)` to get the result

        # async def go():
        #  <stuff goes here>
        #
        # try:
        #  bot.loop.create_task(go())
        # except Exception:
        #  await message.reply(traceback.format_exc())

        silly_billy = text[9:]

        spaced = ""
        for i in silly_billy.split("\n"):
            spaced += "  " + i + "\n"

        intro = "async def go(message, bot):\n try:\n"
        ending = "\n except Exception:\n  await message.reply(traceback.format_exc())\nbot.loop.create_task(go(message, bot))"

        complete = intro + spaced + ending
        exec(complete)
    if text.lower().startswith("cat!news"):
        async for i in Channel.all():
            try:
                channeley = bot.get_partial_messageable(int(i.channel_id))
                await channeley.send(text[8:])
            except Exception:
                pass
    if text.lower().startswith("cat!custom"):
        stuff = text.split(" ")
        if stuff[1][0] not in "1234567890":
            stuff.insert(1, message.channel.owner_id)
        user = await User.get_or_create(user_id=int(stuff[1]))
        cat_name = " ".join(stuff[2:])
        if stuff[2] != "None" and message.reference and message.reference.message_id:
            emoji_name = str(user.user_id) + "cat"
            if emoji_name in emojis.keys():
                await message.reply("emoji already exists")
                return
            og_msg = await message.channel.fetch_message(message.reference.message_id)
            if not og_msg or len(og_msg.attachments) == 0:
                await message.reply("no image found")
                return
            img_data = await og_msg.attachments[0].read()

            if og_msg.attachments[0].content_type.startswith("image/gif"):
                await bot.create_application_emoji(name=emoji_name, image=img_data)
            else:
                img = Image.open(io.BytesIO(img_data))
                img.thumbnail((128, 128))
                with io.BytesIO() as image_binary:
                    img.save(image_binary, format="PNG")
                    image_binary.seek(0)
                    await bot.create_application_emoji(name=emoji_name, image=image_binary.getvalue())
        user.custom = cat_name if cat_name != "None" else ""
        emojis = {emoji.name: str(emoji) for emoji in await bot.fetch_application_emojis()}
        await user.save()
        await message.reply("success")


# the message when cat gets added to a new server
async def on_guild_join(guild):
    def verify(ch):
        return ch and ch.permissions_for(guild.me).send_messages

    def find(patt, channels):
        for i in channels:
            if patt in i.name:
                return i

    logging.debug("Guild joined, member count %d", guild.member_count)

    # first to try a good channel, then whenever we cat atleast chat
    ch = find("cat", guild.text_channels)
    if not verify(ch):
        ch = find("bot", guild.text_channels)
    if not verify(ch):
        ch = find("commands", guild.text_channels)
    if not verify(ch):
        ch = find("general", guild.text_channels)

    found = False
    if not verify(ch):
        for ch in guild.text_channels:
            if verify(ch):
                found = True
                break
        if not found:
            ch = guild.owner

    # you are free to change/remove this, its just a note for general user letting them know
    unofficial_note = "**NOTE: This is an unofficial Cat Bot instance.**\n\n"
    if not bot.user or bot.user.id == 966695034340663367:
        unofficial_note = ""
    try:
        if ch.permissions_for(guild.me).send_messages:
            await ch.send(
                unofficial_note
                + "Thanks for adding me!\nTo start, use `/setup` and `/help` to learn more!\nJoin the support server here: https://discord.gg/staring\nHave a nice day :)"
            )
    except Exception:
        pass


@bot.tree.command(description="Learn to use the bot")
async def help(message):
    embed1 = discord.Embed(
        title="How to Setup",
        description="Server moderator (anyone with *Manage Server* permission) needs to run `/setup` in any channel. After that, cats will start to spawn in 1-10 minute intervals inside of that channel.\nYou can customize those intervals with `/changetimings` and change the spawn message with `/changemessage`.\nCat spawns can also be forced by moderators using `/forcespawn` command.\nYou can have unlimited amounts of setupped channels at once.\nYou can stop the spawning in a channel by running `/forget`.",
        color=Colors.brown,
    ).set_thumbnail(url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png")

    embed2 = (
        discord.Embed(title="How to Play", color=Colors.brown)
        .add_field(
            name="Catch Cats",
            value='Whenever a cat spawns you will see a message along the lines of "a cat has appeared", which will also display it\'s type.\nCat types can have varying rarities from 25% for Fine to hundredths of percent for rarest types.\nSo, after saying "cat" the cat will be added to your inventory.',
            inline=False,
        )
        .add_field(
            name="Viewing Your Inventory",
            value="You can view your (or anyone elses!) inventory using `/inventory` command. It will display all the cats, along with other stats.\nIt is important to note that you have a separate inventory in each server and nothing carries over, to make the experience more fair and fun.\nCheck out the leaderboards for your server by using `/leaderboards` command.\nIf you want to transfer cats, you can use the simple `/gift` or more complex `/trade` commands.",
            inline=False,
        )
        .add_field(
            name="Let's get funky!",
            value='Cat Bot has various other mechanics to make fun funnier. You can collect various `/achievements`, for example saying "i read help", progress in the `/battlepass`, or have beef with the mafia over catnip addiction. The amount you worship is the limit!',
            inline=False,
        )
        .add_field(
            name="Other features",
            value="Cat Bot has extra fun commands which you will discover along the way.\nAnything unclear? Check out [our wiki](https://catbot.wiki) or drop us a line at our [Discord server](https://discord.gg/staring).",
            inline=False,
        )
        .set_footer(
            text=f"Cat Bot by Milenakos, {datetime.datetime.utcnow().year}",
            icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png",
        )
    )

    await message.response.send_message(embeds=[embed1, embed2])


@bot.tree.command(description="Roll the credits")
async def credits(message: discord.Interaction):
    global gen_credits

    if not gen_credits:
        await message.response.send_message(
            "credits not yet ready! this is a very rare error, congrats.",
            ephemeral=True,
        )
        return

    await message.response.defer()

    embedVar = discord.Embed(title="Cat Bot", color=Colors.brown, description=gen_credits).set_thumbnail(
        url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png"
    )

    await message.followup.send(embed=embedVar)


def format_timedelta(start_timestamp, end_timestamp):
    delta = datetime.timedelta(seconds=end_timestamp - start_timestamp)
    days = delta.days
    seconds = delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{days}d {hours}h {minutes}m {seconds}s"


@bot.tree.command(description="View various bot information and stats")
async def info(message: discord.Interaction):
    embed = discord.Embed(title="Cat Bot Info", color=Colors.brown)
    try:
        git_timestamp = int(subprocess.check_output(["git", "show", "-s", "--format=%ct"]).decode("utf-8"))
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
Hard uptime: `{format_timedelta(config.HARD_RESTART_TIME, time.time())}`
Soft uptime: `{format_timedelta(config.SOFT_RESTART_TIME, time.time())}`
Last code update: `{format_timedelta(git_timestamp, time.time()) if git_timestamp else "N/A"}`
Loops since soft restart: `{loop_count + 1:,}`
Shards: `{len(bot.shards):,}`
Guild shard: `{message.guild.shard_id:,}`

**__Global Stats__**
Guilds: `{len(bot.guilds):,}`
DB Profiles: `{await Profile.count():,}`
DB Users: `{await User.count():,}`
DB Channels: `{await Channel.count():,}`
"""

    await message.response.send_message(embed=embed)


@bot.tree.command(description="Confused? Check out the Cat Bot Wiki!")
async def wiki(message: discord.Interaction):
    embed = discord.Embed(title="Cat Bot Wiki", color=Colors.brown)
    embed.description = "\n".join(
        [
            "Main Page: https://catbot.wiki/",
            "",
            "[Cat Bot](https://catbot.wiki/cat-bot)",
            "[Cat Spawning](https://catbot.wiki/spawning)",
            "[Commands](https://catbot.wiki/commands)",
            "[Cat Types](https://catbot.wiki/cat-types)",
            "[Cattlepass](https://catbot.wiki/cattlepass)",
            "[Achievements](https://catbot.wiki/achievements)",
            "[Packs](https://catbot.wiki/packs)",
            "[Trading](https://catbot.wiki/trading)",
            "[Gambling](https://catbot.wiki/gambling)",
            "[Catnip](https://catbot.wiki/catnip)",
            "[Prisms](https://catbot.wiki/prisms)",
        ]
    )
    await message.response.send_message(embed=embed)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, profile, "wiki")


@bot.tree.command(description="Read The Cat Bot Times™️")
async def news(message: discord.Interaction):
    user = await User.get_or_create(user_id=message.user.id)
    buttons = []
    current_state = user.news_state.strip()

    async def send_news(interaction: discord.Interaction):
        news_id = int(interaction.data["custom_id"])
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        async def go_back(back_interaction: discord.Interaction):
            if back_interaction.user != message.user:
                await do_funny(back_interaction)
                return
            await back_interaction.response.defer()
            await regen_buttons()
            await back_interaction.edit_original_response(view=generate_page(current_page))

        await interaction.response.defer()

        current_state = user.news_state.strip()
        if current_state[news_id] not in "123456789":
            user.news_state = current_state[:news_id] + "1" + current_state[news_id + 1 :]
            await user.save()

        profile = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
        await progress(interaction, profile, "news")

        view = LayoutView(timeout=VIEW_TIMEOUT)
        back_button = Button(emoji="⬅️", label="Back")
        back_button.callback = go_back
        back_row = ActionRow(back_button)

        logging.debug("Read news #%d", news_id)

        if news_id == 0:
            embed = Container(
                "## 📜 Cat Bot Survey",
                "Hello and welcome to The Cat Bot Times:tm:! I kind of want to learn more about your time with Cat Bot because I barely know about it lmao. This should only take a couple of minutes.\n\nGood high-quality responses will win FREE cat rain prizes.\n\nSurvey is closed!",
                "-# <t:1731168230>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)
        elif news_id == 1:
            embed = Container(
                "## ✨ New Cat Rains perks!",
                "Hey there! Buying Cat Rains now gives you access to `/editprofile` command! You can add an image, change profile color, and add an emoji next to your name. Additionally, you will now get a special role in our [discord server](https://discord.gg/staring).\nEveryone who ever bought rains and all future buyers will get it.\nAnyone who bought these abilities separately in the past (known as 'Cat Bot Supporter') have received 10 minutes of Rains as compensation.\n\nThis is a really cool perk and I hope you like it!",
                Button(label="Cat Bot Store", url="https://catbot.shop"),
                "-# <t:1732377932>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)
        elif news_id == 2:
            embed = Container(
                "## ☃️ Cat Bot Christmas",
                f"⚡ **Cat Bot Wrapped 2024**\nIn 2024 Cat Bot got...\n- 🖥️ *45777* new servers!\n- 👋 *286607* new profiles!\n- {get_emoji('staring_cat')} okay so funny story due to the new 2.1 billion per cattype limit i added a few months ago 4 with 832 zeros cats were deleted... oopsie... there are currently *64105220101255* cats among the entire bot rn though\n- {get_emoji('cat_throphy')} *1518096* achievements get!\nSee last year's Wrapped [here](<https://discord.com/channels/966586000417619998/1021844042654417017/1188573593408385074>).\n\n❓ **New Year Update**\nSomething is coming...",
                "-# <t:1734458962>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)
        elif news_id == 3:
            embed = Container(
                "## Battlepass is getting an update!",
                """### qhar?
- Huge stuff!
- Battlepass will now reset every month
- You will have 3 quests, including voting
- They refresh 12 hours after completing
- Quest reward is XP which goes towards progressing
- There are 30 battlepass levels with much better rewards (even Ultimate cats and Rain minutes!)
- Prism crafting/true ending no longer require battlepass progress.
- More fun stuff to do each day and better rewards!

### oh no what if i hate grinding?
Don't worry, quests are very easy and to complete the battlepass you will need to complete less than 3 easy quests a day.

### will you sell paid battlepass? its joever
There are currently no plans to sell a paid battlepass.""",
                "-# <t:1735689601>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)
        elif news_id == 4:
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
            await interaction.edit_original_response(view=view)
        elif news_id == 5:
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
            await interaction.edit_original_response(view=view)
        elif news_id == 6:
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
            await interaction.edit_original_response(view=view)
        elif news_id == 7:
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
            await interaction.edit_original_response(view=view)

        elif news_id == 8:
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
            await interaction.edit_original_response(view=view)
        elif news_id == 9:
            # we hijack the cookie system to store the yippee count
            cookie_id = (9, bot.user.id)
            if cookie_id not in temp_cookie_storage.keys():
                cookie_user = await Profile.get_or_create(guild_id=9, user_id=bot.user.id)
                temp_cookie_storage[cookie_id] = cookie_user.cookies

            async def add_yippee(interaction):
                await interaction.response.defer()
                try:
                    temp_cookie_storage[cookie_id] += 1
                except KeyError:
                    cookie_user = await Profile.get_or_create(guild_id=9, user_id=bot.user.id)
                    temp_cookie_storage[cookie_id] = cookie_user.cookies
                await send_yippee(interaction)

            async def send_yippee(interaction):
                view = LayoutView(timeout=VIEW_TIMEOUT)
                btn = Button(label=f"yippee! ({temp_cookie_storage[cookie_id]:,})", emoji=get_emoji("yippee"), style=ButtonStyle.primary)
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
                await interaction.edit_original_response(view=view)

            await send_yippee(interaction)
        elif news_id == 10:
            embed = Container(
                "## 🏆 nominate cat bot for top.gg awards",
                "(this is outdated, nominations are over. you can [vote for cat bot as finalist in Labor of Love category](https://nominations.top.gg/))"
                "holy cat top.gg is doing annual awards now",
                "you know [what to do](https://top.gg/bot/966695034340663367)...\nyou can also leave a review while you are there if you havent yet :3",
                discord.ui.MediaGallery(discord.MediaGalleryItem("https://i.imgur.com/YgQ0flQ.png")),
                Button(label="Vote for Cat Bot", url="https://nominations.top.gg/", emoji="🏆"),
                "-# <t:1759513848>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)
        elif news_id == 11:
            embed = Container(
                f"## {get_emoji('catnip')} Welcome to the Cat Mafia",
                f"""after the dog mafia got arrested for selling cataine, cats got inspired and started their own mafia!

- cataine is replaced by {get_emoji("catnip")} catnip
- the biggest update ever (probably)
- this is a new late-game complex mechanic with *leveling, bounties and perks*
- it can be accessed and managed via /catnip
- discover **10 new cats** - the members of the mafia who have tough challenges for you
- getting through all of it is a very tough challenge, **the hardest thing in cat bot**
- old cataine is completely gone, all process you had in it will be reset

👉 okay now let me explain:
at each level you will have some bounties you have to complete within a time frame. if you complete the bounties and pay the price, you will be able to choose one of 3 different perks of random rarities {get_emoji("common")}{get_emoji("uncommon")}{get_emoji("rare")}{get_emoji("epic")}{get_emoji("legendary")}. the perks will stack while catnip is active! failing to complete the bounties will bring you one level down and you will lose your last perk. higher levels are harder but give you better perks!""",
                "-# <t:1761325200>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)
        elif news_id == 12:
            embed = Container(
                "## ❤️ vote for cat bot in top.gg awards",
                'cat bot is finalist in "Labor of Love" category on top.gg awards!',
                "make sure to [vote for it](https://nominations.top.gg/) and perhaps attend the awards ceremony on january 3rd",
                discord.ui.MediaGallery(discord.MediaGalleryItem("https://i.imgur.com/7EW2I4P.png")),
                Button(label="Vote for Cat Bot", url="https://nominations.top.gg/", emoji="🏆"),
                "-# <t:1765747278>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)
        elif news_id == 13:
            embed = Container(
                f"## {get_emoji('christmaspack')} Cat Bot Christmas 2025",
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
            await interaction.edit_original_response(view=view)

    async def regen_buttons():
        nonlocal buttons
        await user.refresh_from_db()
        buttons = []
        current_state = user.news_state.strip()
        for num, article in enumerate(news_list):
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
            buttons.append(button)
        buttons = buttons[::-1]  # reverse the list so the first button is the most recent article

    await regen_buttons()

    if len(news_list) > len(current_state):
        user.news_state = current_state + "0" * (len(news_list) - len(current_state))
        await user.save()

    current_page = 0

    async def prev_page(interaction):
        nonlocal current_page
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        current_page -= 1
        await interaction.response.edit_message(view=generate_page(current_page))

    async def next_page(interaction):
        nonlocal current_page
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        current_page += 1
        await interaction.response.edit_message(view=generate_page(current_page))

    async def mark_all_as_read(interaction):
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        user.news_state = "1" * len(news_list)
        await user.save()
        await regen_buttons()
        await interaction.response.edit_message(view=generate_page(current_page))

    def generate_page(number):
        view = LayoutView(timeout=VIEW_TIMEOUT)
        view.add_item(TextDisplay("Choose an article:"))

        # article buttons
        if current_page == 0:
            end = (number + 1) * 4
        else:
            end = len(buttons)
            row = ActionRow()
        for num, button in enumerate(buttons[number * 4 : end]):
            if current_page == 0:
                view.add_item(ActionRow(button))
            else:
                if len(row.children) == 5:
                    view.add_item(row)
                    row = ActionRow()
                row.add_item(button)

        if current_page != 0 and len(row.children) > 0:
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

    await message.response.defer()
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    if text == "bwomp":
        file = discord.File("bwomp.mp3", filename="bwomp.mp3")
        await message.followup.send(file=file)
        await achemb(message, "bwomp", "followup")
        await progress(message, profile, "tiktok")
        return

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://tiktok-tts.weilnet.workers.dev/api/generation",
                json={"text": text, "voice": "en_us_001"},
                headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"},
            ) as response:
                stuff = await response.json()
                with io.BytesIO() as f:
                    ba = "data:audio/mpeg;base64," + stuff["data"]
                    f.write(base64.b64decode(ba))
                    f.seek(0)
                    await message.followup.send(file=discord.File(fp=f, filename="output.mp3"))
        except discord.NotFound:
            pass
        except Exception:
            await message.followup.send("i dont speak guacamole (remove non-english characters, make sure the message is below 300 characters)")

    await progress(message, profile, "tiktok")


@bot.tree.command(description="(ADMIN) Prevent someone from catching cats for a certain time period")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(person="A person to timeout!", timeout="How many seconds? (0 to reset)")
async def preventcatch(message: discord.Interaction, person: discord.User, timeout: int):
    if timeout < 0:
        await message.response.send_message("uhh i think time is supposed to be a number", ephemeral=True)
        return
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=person.id)
    timestamp = round(time.time()) + timeout
    user.timeout = timestamp
    await user.save()
    await message.response.send_message(
        person.name.replace("_", r"\_") + (f" can't catch cats until <t:{timestamp}:R>" if timeout > 0 else " can now catch cats again.")
    )


@bot.tree.command(description="(ADMIN) Change Cat Bot avatar")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(avatar="The avatar to use (leave empty to reset)")
async def changeavatar(message: discord.Interaction, avatar: Optional[discord.Attachment]):
    await message.response.defer()

    if avatar and avatar.content_type not in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
        await message.followup.send("Invalid file type! Please upload a PNG, JPEG, GIF, or WebP image.", ephemeral=True)
        return

    if avatar:
        avatar_value = discord.utils._bytes_to_base64_data(await avatar.read())
    else:
        avatar_value = None

    try:
        # this isnt supported by discord.py yet
        await bot.http.request(discord.http.Route("PATCH", f"/guilds/{message.guild.id}/members/@me"), json={"avatar": avatar_value})
        await message.followup.send("Avatar changed successfully!")
    except Exception:
        await message.followup.send("Failed to change avatar! Your image is too big or you are changing avatars too quickly.", ephemeral=True)
        return


@bot.tree.command(description="(ADMIN) Change the cat appear timings")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(
    minimum_time="In seconds, minimum possible time between spawns (leave both empty to reset)",
    maximum_time="In seconds, maximum possible time between spawns (leave both empty to reset)",
)
async def changetimings(
    message: discord.Interaction,
    minimum_time: Optional[int],
    maximum_time: Optional[int],
):
    channel = await Channel.get_or_none(channel_id=message.channel.id)
    if not channel:
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


@bot.tree.command(description="(ADMIN) Change the cat appear and cought messages")
@discord.app_commands.default_permissions(manage_guild=True)
async def changemessage(message: discord.Interaction):
    caller = message.user
    channel = await Channel.get_or_none(channel_id=message.channel.id)
    if not channel:
        await message.response.send_message("pls setup this channel first", ephemeral=True)
        return

    # this is the silly popup when you click the button
    class InputModal(Modal):
        def __init__(self, type):
            super().__init__(
                title=f"Change {type} Message",
                timeout=3600,
            )

            self.type = type

            self.input = TextInput(
                min_length=0,
                max_length=1000,
                label="Input",
                style=discord.TextStyle.long,
                required=False,
                placeholder='{emoji} {type} has appeared! Type "cat" to catch it!',
                default=channel.appear if self.type == "Appear" else channel.cought,
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
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
                        await interaction.response.send_message(f"nuh uh! you are missing `{i}`.", ephemeral=True)
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
    async def ask_appear(interaction):
        nonlocal caller

        if interaction.user != caller:
            await do_funny(interaction)
            return

        modal = InputModal("Appear")
        await interaction.response.send_modal(modal)

    async def ask_catch(interaction):
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

missing any of these will result in a failure.
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


@bot.tree.command(description="Get Daily cats")
async def daily(message: discord.Interaction):
    await message.response.send_message("there is no daily cats why did you even try this")
    await achemb(message, "daily", "followup")


@bot.tree.command(description="View when the last cat was caught in this channel, and when the next one might spawn")
async def last(message: discord.Interaction):
    channel = await Channel.get_or_none(channel_id=message.channel.id)
    nextpossible = ""

    try:
        lasttime = channel.lastcatches
        if int(lasttime) == 0:  # unix epoch check
            displayedtime = "forever ago"
        else:
            displayedtime = f"<t:{int(lasttime)}:R>"
    except Exception:
        displayedtime = "forever ago"

    if channel and not channel.cat:
        times = [channel.spawn_times_min, channel.spawn_times_max]
        nextpossible = f"\nthe next cat will spawn between <t:{int(lasttime) + times[0]}:R> and <t:{int(lasttime) + times[1]}:R>"

    if channel and channel.cat_rains:
        nextpossible += f"\ncat rain! {channel.cat_rains} cats remaining..."

    await message.response.send_message(f"the last cat in this channel was caught {displayedtime}.{nextpossible}")


@bot.tree.command(description="View all the juicy numbers behind cat types")
async def catalogue(message: discord.Interaction):
    embed = discord.Embed(title=f"{get_emoji('staring_cat')} The Catalogue", color=Colors.brown)
    for cat_type in cattypes:
        in_server = await Profile.sum(f"cat_{cat_type}", f'guild_id = $1 AND "cat_{cat_type}" > 0', message.guild.id)
        title = f"{get_emoji(cat_type.lower() + 'cat')} {cat_type}"
        if in_server == 0 or not in_server:
            in_server = 0
            title = f"{get_emoji('mysterycat')} ???"

        title += f" ({round((type_dict[cat_type] / sum(type_dict.values())) * 100, 2)}%)"

        embed.add_field(
            name=title,
            value=f"{round(sum(type_dict.values()) / type_dict[cat_type], 2)} value\n{in_server:,} in this server",
        )

    await message.response.send_message(embed=embed)


async def gen_stats(profile, star):
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

    # catching boosts
    stats.append([get_emoji("prism"), "Boosts"])
    prisms_crafted = await Prism.count("guild_id = $1 AND user_id = $2", profile.guild_id, profile.user_id)
    boosts_done = await Prism.sum("catches_boosted", "guild_id = $1 AND user_id = $2", profile.guild_id, profile.user_id)
    stats.append(["prism_crafted", get_emoji("prism"), f"Prisms crafted: {prisms_crafted:,}"])
    stats.append(["boosts_done", get_emoji("prism"), f"Boosts by owned prisms: {boosts_done:,}{star}"])
    stats.append(["boosted_catches", get_emoji("prism"), f"Prism-boosted catches: {profile.boosted_catches:,}{star}"])

    # catnip
    stats.append([get_emoji("catnip"), "Catnip"])
    stats.append(["catnip_activations", get_emoji("catnip"), f"Cats gained from catnip: {profile.catnip_activations:,}"])
    stats.append(["catnip_bought", get_emoji("catnip"), f"Catnip levels reached: {profile.catnip_bought:,}"])
    stats.append(["highest_catnip_level", "⬆️", f"Highest catnip level: {profile.highest_catnip_level:,}"])
    stats.append(["bounties_complete", "🎯", f"Bounties completed: {profile.bounties_complete:,}"])

    # voting
    stats.append([get_emoji("topgg"), "Voting"])
    stats.append(["total_votes", get_emoji("topgg"), f"Total votes: {user.total_votes:,}{star}"])
    stats.append(["current_vote_streak", "🔥", f"Current vote streak: {user.vote_streak} (max {max(user.vote_streak, user.max_vote_streak):,}){star}"])
    if user.vote_time_topgg + 43200 > time.time():
        stats.append(["can_vote", get_emoji("topgg"), f"Can vote <t:{user.vote_time_topgg + 43200}:R>"])
    else:
        stats.append(["can_vote", get_emoji("topgg"), "Can vote!"])

    # battlepass
    stats.append(["⬆️", "Cattlepass"])
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
            total_xp += 1500 * (season_lvl - 31)
        if season_lvl > max_level:
            max_level = season_lvl

        for num, level in enumerate(battle["seasons"][str(season_num)]):
            if num >= season_lvl:
                break
            total_xp += level["xp"]
    # current season
    if profile.season != 0:
        levels_complete += profile.battlepass
        total_xp += profile.progress
        if profile.battlepass > 30:
            seasons_complete += 1
            total_xp += 1500 * (profile.battlepass - 31)
        if profile.battlepass > max_level:
            max_level = profile.battlepass

        for num, level in enumerate(battle["seasons"][str(profile.season)]):
            if num >= profile.battlepass:
                break
            total_xp += level["xp"]
    current_packs = 0
    for pack in pack_data:
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
    stats.append(["☔", "Rains"])
    stats.append(["current_rain_minutes", "☔", f"Current rain minutes: {user.rain_minutes:,}"])
    stats.append(["supporter", "👑", "Ever bought rains: " + ("Yes" if user.premium else "No")])
    stats.append(["rain_minutes_bought", "☔", f"Rain minutes bought: {user.rain_minutes_bought:,}"])
    stats.append(["cats_caught_during_rains", "☔", f"Cats caught during rains: {profile.rain_participations:,}{star}"])
    stats.append(["rain_minutes_started", "☔", f"Rain minutes started: {profile.rain_minutes_started:,}{star}"])
    stats.append(["cats_blessed", "🌠", f"Cats blessed: {user.cats_blessed:,}"])

    # gambling
    stats.append(["🎰", "Gambling"])
    stats.append(["casino_spins", "🎰", f"Casino spins: {profile.gambles:,}"])
    stats.append(["slot_spins", "🎰", f"Slot spins: {profile.slot_spins:,}"])
    stats.append(["slot_wins", "🎰", f"Slot wins: {profile.slot_wins:,}"])
    stats.append(["slot_big_wins", "🎰", f"Slot big wins: {profile.slot_big_wins:,}"])
    stats.append(["roulette_spins", "💰", f"Roulette spins: {profile.roulette_spins:,}"])
    stats.append(["roulette_wins", "💰", f"Roulette wins: {profile.roulette_wins:,}"])

    # tic tac toe
    stats.append(["⭕", "Tic Tac Toe"])
    stats.append(["ttc_games", "⭕", f"Tic Tac Toe games played: {profile.ttt_played:,}"])
    stats.append(["ttc_wins", "⭕", f"Tic Tac Toe wins: {profile.ttt_won:,}"])
    stats.append(["ttc_draws", "⭕", f"Tic Tac Toe draws: {profile.ttt_draws:,}"])
    if profile.ttt_played != 0:
        stats.append(["ttc_win_rate", "⭕", f"Tic Tac Toe win rate: {(profile.ttt_won + profile.ttt_draws) / profile.ttt_played * 100:.2f}%"])
    else:
        stats.append(["ttc_win_rate", "⭕", "Tic Tac Toe win rate: 0%"])

    if (profile.guild_id, profile.user_id) not in temp_cookie_storage.keys():
        cookies = profile.cookies
    else:
        cookies = temp_cookie_storage[(profile.guild_id, profile.user_id)]
    # misc
    stats.append(["❓", "Misc"])
    stats.append(["facts_read", "🧐", f"Facts read: {profile.facts:,}"])
    stats.append(["cookies", "🍪", f"Cookies clicked: {cookies:,}"])
    stats.append(["pig_high_score", "🎲", f"Pig high score: {profile.best_pig_score:,}"])
    stats.append(["private_embed_clicks", get_emoji("pointlaugh"), f"Private embed clicks: {profile.funny:,}"])
    stats.append(["reminders_set", "⏰", f"Reminders set: {profile.reminders_set:,}{star}"])
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
async def stats_command(message: discord.Interaction, person_id: Optional[discord.User]):
    await message.response.defer()
    if not person_id:
        person_id = message.user
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    star = "*" if not profile.new_user else ""

    stats = await gen_stats(profile, star)
    stats_string = ""
    for stat in stats:
        if len(stat) == 2:
            # category
            stats_string += f"\n{stat[0]} __{stat[1]}__\n"
        elif len(stat) == 3:
            # stat
            stats_string += f"{stat[2]}\n"
    if star:
        stats_string += "\n\\*this stat is only tracked since February 2025"

    embedVar = discord.Embed(title=f"{person_id.name}'s Stats", color=Colors.brown, description=stats_string)
    await message.followup.send(embed=embedVar)


async def gen_inventory(message, person_id):
    # check if we are viewing our own inv or some other person
    if person_id is None:
        person_id = message.user
    me = bool(person_id == message.user)
    person = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    user = await User.get_or_create(user_id=person_id.id)

    # around here we count aches
    unlocked = 0
    minus_achs = 0
    minus_achs_count = 0
    for k in ach_names:
        is_ach_hidden = ach_list[k]["category"] == "Hidden"
        if is_ach_hidden:
            minus_achs_count += 1
        if person[k]:
            if is_ach_hidden:
                minus_achs += 1
            else:
                unlocked += 1
    total_achs = len(ach_list) - minus_achs_count
    minus_achs = "" if minus_achs == 0 else f" + {minus_achs}"

    # count prism stuff
    prisms = await Prism.collect_limit(["name"], "guild_id = $1 AND user_id = $2", message.guild.id, person_id.id)
    total_count = await Prism.count("guild_id = $1", message.guild.id)
    user_count = len(prisms)
    global_boost = 0.06 * math.log(2 * total_count + 1)
    prism_boost = round((global_boost + 0.03 * math.log(2 * user_count + 1)) * 100, 3)
    if len(prisms) == 0:
        prism_list = "None"
    elif len(prisms) <= 3:
        prism_list = ", ".join([i.name for i in prisms])
    else:
        prism_list = f"{prisms[0].name}, {prisms[1].name}, {len(prisms) - 2} more..."

    emoji_prefix = str(user.emoji) + " " if user.emoji else ""

    if user.color:
        color = user.color
    else:
        color = "#6E593C"

    await refresh_quests(person)
    try:
        needed_xp = battle["seasons"][str(person.season)][person.battlepass]["xp"]
    except Exception:
        needed_xp = 1500

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

    embedVar = discord.Embed(
        title=f"{emoji_prefix}{person_id.name.replace('_', r'\_')}",
        description=f"{highlighted_stat[1]} {highlighted_stat[2]}\n{get_emoji('ach')} Achievements: {unlocked}/{total_achs}{minus_achs}\n⬆️ Battlepass Level {person.battlepass} ({person.progress}/{needed_xp} XP)",
        color=discord.Colour.from_str(color),
    )

    debt = False
    give_collector = True
    total = 0
    valuenum = 0

    # for every cat
    cat_desc = ""
    for i in cattypes:
        icon = get_emoji(i.lower() + "cat")
        cat_num = person[f"cat_{i}"]
        if cat_num < 0:
            debt = True
        if cat_num != 0:
            total += cat_num
            valuenum += (sum(type_dict.values()) / type_dict[i]) * cat_num
            cat_desc += f"{icon} **{i}** {cat_num:,}\n"
        else:
            give_collector = False

    if user.custom:
        icon = get_emoji(str(user.user_id) + "cat")
        cat_desc += f"{icon} **{user.custom}** {user.custom_num:,}"

    if len(cat_desc) == 0:
        cat_desc = f"u hav no cats {get_emoji('cat_cry')}"

    if embedVar.description:
        embedVar.description += f"\n{get_emoji('staring_cat')} Cats: {total:,}, Value: {round(valuenum):,}\n{get_emoji('prism')} Prisms: {prism_list} ({prism_boost}%)\n\n{cat_desc}"

    if user.image.startswith("https://cdn.discordapp.com/attachments/"):
        embedVar.set_thumbnail(url=user.image)

    give_achs = []
    if me:
        # give some aches if we are vieweing our own inventory
        if len(news_list) > len(user.news_state.strip()) or "0" in user.news_state.strip()[-4:]:
            embedVar.set_author(name="You have unread news! /news")

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
            bot.loop.create_task(debt_cutscene(message, person))

    return embedVar, give_achs


@bot.tree.command(description="View your inventory")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="Person to view the inventory of!")
async def inventory(message: discord.Interaction, person_id: Optional[discord.User]):
    await message.response.defer()
    if not person_id:
        person_id = message.user
    person = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    user = await User.get_or_create(user_id=message.user.id)
    stats = await gen_stats(person, "")

    async def edit_profile(interaction: discord.Interaction):
        if interaction.user.id != person_id.id:
            await do_funny(interaction)
            return

        def stat_select(category):
            options = [discord.SelectOption(emoji="⬅️", label="Back", value="back")]
            track = False
            for stat in stats:
                if len(stat) == 2:
                    track = bool(stat[1] == category)
                if len(stat) == 3 and track:
                    options.append(discord.SelectOption(value=stat[0], emoji=stat[1], label=stat[2]))

            select = discord.ui.Select(placeholder="Edit highlighted stat... (2/2)", options=options)

            async def select_callback(interaction: discord.Interaction):
                await interaction.response.defer()
                if select.values[0] == "back":
                    view = View(timeout=VIEW_TIMEOUT)
                    view.add_item(category_select())
                    await interaction.edit_original_response(view=view)
                else:
                    # update the stat
                    person.highlighted_stat = select.values[0]
                    await person.save()
                    await interaction.edit_original_response(content="Highlighted stat updated!", embed=None, view=None)

            select.callback = select_callback
            return select

        def category_select():
            options = []
            for stat in stats:
                if len(stat) != 2:
                    continue
                options.append(discord.SelectOption(emoji=stat[0], label=stat[1], value=stat[1]))

            select = discord.ui.Select(placeholder="Edit highlighted stat... (1/2)", options=options)

            async def select_callback(interaction: discord.Interaction):
                # im 13 and this is deep (nesting)
                # and also please dont think about the fact this is async inside of sync :3
                await interaction.response.defer()
                view = View(timeout=VIEW_TIMEOUT)
                view.add_item(stat_select(select.values[0]))
                await interaction.edit_original_response(view=view)

            select.callback = select_callback
            return select

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

        view = View(timeout=VIEW_TIMEOUT)
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
{highlighted_stat[1]} {highlighted_stat[2]}"""

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

    embedVar, give_achs = await gen_inventory(message, person_id)

    embedVar.set_footer(text=rain_shill)

    if person_id.id == message.user.id:
        view = View(timeout=VIEW_TIMEOUT)
        btn = Button(emoji="📝", label="Edit", style=ButtonStyle.blurple)
        btn.callback = edit_profile
        view.add_item(btn)
        await message.followup.send(embed=embedVar, view=view)
    else:
        await message.followup.send(embed=embedVar)

    for ach in give_achs:
        await achemb(message, ach, "followup")


async def rain_recovery_loop(channel):
    logging.debug("Rain started, cats %d", channel.cat_rains)
    while True:
        await asyncio.sleep(5)
        await channel.refresh_from_db()
        if channel.cat_rains <= 0:
            break
        if channel.cat_rains and not channel.cat and time.time() - channel.rain_should_end > 5:
            await spawn_cat(str(channel.channel_id))
            channel.cat_rains -= 1
            await channel.save()


async def rain_end(message, channel, force_summary=None):
    try:
        for _ in range(3):
            await message.channel.send("# :bangbang: cat rain has ended")
            await asyncio.sleep(0.4)
    except Exception:
        pass

    lock_success = False
    try:
        me_overwrites = message.channel.overwrites_for(message.guild.me)
        me_overwrites.send_messages = True

        everyone_overwrites = message.channel.overwrites_for(message.guild.default_role)
        current_perm = everyone_overwrites.send_messages
        everyone_overwrites.send_messages = False

        await asyncio.gather(
            message.channel.set_permissions(message.guild.default_role, overwrite=everyone_overwrites),
            message.channel.set_permissions(message.guild.me, overwrite=me_overwrites),
        )
        lock_success = True
    except Exception:
        pass

    await asyncio.sleep(1)

    # rain summary
    try:
        rain_server = force_summary
        if not rain_server:
            if channel.channel_id not in config.rain_starter or channel.channel_id not in config.cat_cought_rain:
                return
            rain_server = config.cat_cought_rain[channel.channel_id]

        # you can throw out the name of the emoji to save on characters
        pack_names = ["Christmas", "Wooden", "Stone", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Celestial"]
        pack_yeah = {"Christmas": 1.2, "Wooden": 1, "Stone": 0.9, "Bronze": 0.8, "Silver": 0.7, "Gold": 0.6, "Platinum": 0.5, "Diamond": 0.4, "Celestial": 0.3}
        rain_packs = []
        rain_cats = []

        for key in rain_server.keys():
            if key in cattypes:
                rain_cats.append(key)
            if key in pack_names:
                rain_packs.append(key)

        funny_cat_emojis = {k: re.sub(r":[A-Za-z0-9_]*:", ":i:", get_emoji(k.lower() + "cat"), count=1) for k in rain_cats}
        funny_pack_emojis = {k: re.sub(r":[A-Za-z0-9_]*:", ":i:", get_emoji(k.lower() + "pack"), count=1) for k in rain_packs}

        funny_emojis = funny_cat_emojis | funny_pack_emojis

        reverse_mapping = {}

        for thing_type, user_ids in rain_server.items():
            for user_id in user_ids:
                if user_id not in reverse_mapping:
                    reverse_mapping[user_id] = []
                reverse_mapping[user_id].append(thing_type)

        evil_types = []
        epic_fail = False
        thingtypes = cattypes + pack_names
        for cat_type in thingtypes:
            part_one = "## Rain Summary\n"

            for user_id, cat_types in sorted(reverse_mapping.items(), key=lambda item: len(item[1]), reverse=True):
                show_cats = ""
                shortened_types = False
                dictdict = type_dict | pack_yeah
                cat_types.sort(reverse=True, key=lambda x: dictdict[x])
                pack_amount = 0
                for cat_type_two in cat_types:
                    if cat_type_two in evil_types:
                        shortened_types = True
                        continue
                    if cat_type_two in pack_names:
                        pack_amount += 1
                    show_cats += funny_emojis[cat_type_two]
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
                    if cat_type not in rain_server.keys():
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

        await asyncio.sleep(2)
    except discord.Forbidden:
        pass
    finally:
        if lock_success:
            everyone_overwrites = message.channel.overwrites_for(message.guild.default_role)
            everyone_overwrites.send_messages = current_perm
            await message.channel.set_permissions(message.guild.default_role, overwrite=everyone_overwrites)


@bot.tree.command(description="its raining cats")
async def rain(message: discord.Interaction):
    user = await User.get_or_create(user_id=message.user.id)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    if not user.rain_minutes:
        user.rain_minutes = 0
        await user.save()

    if not user.claimed_free_rain:
        user.rain_minutes += 2
        user.claimed_free_rain = True
        await user.save()

    server_rains = ""
    server_minutes = profile.rain_minutes
    if server_minutes > 0:
        server_rains = f" (+**{server_minutes}** bonus minutes)"

    embed = discord.Embed(
        title="☔ Cat Rains",
        description=f"""Cat Rains are power-ups which spawn cats super fast for a limited amounts of time in a channel of your choice.

You can get those by buying them at our [store](<https://catbot.shop>) or by winning them in an event.
This bot is developed by a single person so buying one would be very appreciated.
As a bonus, you will get access to /editprofile command!
Fastest times are not saved during rains.

You currently have **{user.rain_minutes}** minutes of rains{server_rains}.""",
        color=Colors.brown,
    )

    # this is the silly popup when you click the button
    class RainModal(Modal):
        def __init__(self, type):
            super().__init__(
                title="Start a Cat Rain!",
                timeout=3600,
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

        async def on_submit(self, interaction: discord.Interaction):
            try:
                duration = int(self.input.value)
            except Exception:
                await interaction.response.send_message("number pls", ephemeral=True)
                return
            await do_rain(interaction, duration)

    async def do_rain(interaction, rain_length):
        # i LOOOOVE checks
        user = await User.get_or_create(user_id=interaction.user.id)
        profile = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
        channel = await Channel.get_or_none(channel_id=interaction.channel.id)

        if not user.rain_minutes:
            user.rain_minutes = 0
            await user.save()

        if not user.claimed_free_rain:
            user.rain_minutes += 2
            user.claimed_free_rain = True
            await user.save()

        if about_to_stop:
            await interaction.response.send_message("the bot is about to stop. please try again later.", ephemeral=True)
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
        channel.cat_rains = math.ceil(rain_length * 60 / 2.75)
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
        await interaction.response.send_message(f"{rain_length}m cat rain was started by {interaction.user.mention}!")
        try:
            ch = bot.get_partial_messageable(config.RAIN_CHANNEL_ID)
            await ch.send(f"{interaction.user.id} started {rain_length}m rain in {interaction.channel.id} ({user.rain_minutes} left)")
        except Exception:
            pass

        config.cat_cought_rain[channel.channel_id] = {}
        config.rain_starter[channel.channel_id] = interaction.user.id
        await spawn_cat(str(interaction.channel.id))
        await rain_recovery_loop(channel)

    async def rain_modal(interaction):
        modal = RainModal(interaction.user)
        await interaction.response.send_modal(modal)

    button = Button(label="Rain!", style=ButtonStyle.blurple)
    button.callback = rain_modal

    shopbutton = Button(
        emoji="🛒",
        label="Store",
        url="https://catbot.shop",
    )

    view = View(timeout=VIEW_TIMEOUT)
    view.add_item(button)
    view.add_item(shopbutton)

    await message.response.send_message(embed=embed, view=view)


@bot.tree.command(description="Buy Cat Rains!")
async def store(message: discord.Interaction):
    await message.response.send_message("☔ Cat rains make cats spawn instantly! Make your server active, get more cats and have fun!\n<https://catbot.shop>")


if config.DONOR_CHANNEL_ID:

    @bot.tree.command(description="(SUPPORTER) Get a cosmetic custom cat! (non-tradeable, doesn't count towards anything)")
    @discord.app_commands.describe(
        name="The name of your custom cat.",
        image="Static/animated GIF, PNG, JPEG, WEBP, AVIF below 256 KB. Static images will be auto-compressed.",
        amount="The amount of your custom cat you want.",
    )
    async def customcat(message: discord.Interaction, name: Optional[str], image: Optional[discord.Attachment], amount: Optional[int]):
        global emojis
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

        await message.response.defer(ephemeral=True)

        em_name = str(user.user_id) + "cat"

        if name:
            user.custom = name
        if amount:
            user.custom_num = amount
        if image:
            if customcatcooldown.get(message.user.id, 0) + 300 > time.time():
                await message.followup.send("You can only upload a new custom cat image every 5 minutes.", ephemeral=True)
                return
            customcatcooldown[message.user.id] = time.time()
            try:
                emojiss = {emoji.name: emoji for emoji in await bot.fetch_application_emojis()}
                if em_name in emojiss:
                    await emojiss[em_name].delete()
                data = await image.read()
                if image.content_type.startswith("image/gif"):
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
            except Exception:
                await message.followup.send("Error creating emoji. Make sure your image is a valid and below 256KB.", ephemeral=True)
                return
        await user.save()
        embedVar, _ = await gen_inventory(message, message.user)
        await message.followup.send("Success! Here is a preview:", embed=embedVar, ephemeral=True)

    @bot.tree.command(description="(SUPPORTER) Bless random Cat Bot users with doubled cats!")
    async def bless(message: discord.Interaction):
        user = await User.get_or_create(user_id=message.user.id)
        do_edit = False

        if user.blessings_enabled and user.username != message.user.name:
            user.username = message.user.name
            await user.save()

        async def toggle_bless(interaction):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            nonlocal do_edit, user
            do_edit = True
            await interaction.response.defer()
            await user.refresh_from_db()
            if not user.premium:
                return
            user.blessings_enabled = not user.blessings_enabled
            user.username = message.user.name
            await user.save()
            await regen(interaction)

        async def toggle_anon(interaction):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            nonlocal do_edit, user
            do_edit = True
            await interaction.response.defer()
            await user.refresh_from_db()
            user.blessings_anonymous = not user.blessings_anonymous
            await user.save()
            await regen(interaction)

        async def regen(interaction):
            if user.blessings_anonymous:
                blesser = "💫 Anonymous Supporter"
            else:
                blesser = f"{user.emoji or '💫'} {message.user.name}"

            user_bless_chance = user.rain_minutes_bought * 0.0001
            global_bless_chance = await User.sum("rain_minutes_bought", "blessings_enabled = true") * 0.0001

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
                await message.edit_original_response(view=view)
            else:
                await message.response.send_message(view=view)

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
        color: Optional[str],
        provided_emoji: Optional[str],
        image: Optional[discord.Attachment],
    ):
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

        if color:
            match = re.search(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color)
            if match:
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
        embedVar, _ = await gen_inventory(message, message.user)
        await message.response.send_message("Success! Here is a preview:", embed=embedVar)


@bot.tree.command(description="View and open packs")
async def packs(message: discord.Interaction):
    async def process_pack_opening(limit=None):
        await user.refresh_from_db()

        pack_names = [pack["name"] for pack in pack_data]
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
            logging.debug("Opened pack %s", pack)
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

        final_header = f"Opened {opened_so_far:,} packs!"
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

    async def open_custom_amount(interaction: discord.Interaction):
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        async def on_submit(interaction: discord.Interaction):
            try:
                amount = int(amount_input.value)
                if amount < 1:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message("Please enter a valid positive number!", ephemeral=True)
                return

            await interaction.response.defer()
            embed = await process_pack_opening(amount)
            if not embed:
                await interaction.followup.send("You have no packs!", ephemeral=True)
                return

            await message.edit_original_response(embed=embed, view=None)
            await asyncio.sleep(1)
            await message.edit_original_response(view=gen_view(user))

        modal = Modal(title="Open Custom Amount")
        amount_input = TextInput(label="Amount", placeholder="How many packs to open?", min_length=1, max_length=10)
        modal.add_item(amount_input)
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    async def confirm_open_all(interaction: discord.Interaction):
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        async def do_it(interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()
            await open_all_packs(interaction)

        confirm_view = View(timeout=VIEW_TIMEOUT)
        yes_btn = Button(label="Yes, Open All", style=ButtonStyle.green)
        yes_btn.callback = do_it
        confirm_view.add_item(yes_btn)

        await interaction.response.send_message("Are you sure you want to open ALL your packs?", view=confirm_view, ephemeral=True)

    def gen_view(user):
        view = View(timeout=VIEW_TIMEOUT)
        empty = True
        total_amount = 0
        for pack in pack_data:
            if user[f"pack_{pack['name'].lower()}"] < 1:
                continue
            empty = False
            amount = user[f"pack_{pack['name'].lower()}"]
            total_amount += amount
            button = Button(
                emoji=get_emoji(pack["name"].lower() + "pack"),
                label=f"{pack['name']} ({amount:,})",
                style=ButtonStyle.blurple,
                custom_id=pack["name"],
            )
            button.callback = open_pack
            view.add_item(button)
        if empty:
            view.add_item(Button(label="No packs left!", disabled=True))
        if total_amount > 5:
            button = Button(label=f"Open all! ({total_amount:,})", style=ButtonStyle.gray)
            button.callback = confirm_open_all
            view.add_item(button)

            custom_btn = Button(label="Open Custom Amount...", style=ButtonStyle.gray)
            custom_btn.callback = open_custom_amount
            view.add_item(custom_btn)
        return view

    def get_pack_rewards(level: int, is_single=True):
        # returns cat_type, cat_amount, upgrades, verbal_output
        reward_texts = []
        build_string = ""
        upgrades = 0
        if not is_single:
            build_string = get_emoji(pack_data[level]["name"].lower() + "pack")

        bump_boost = 7 / 3 if level == 0 else 1

        # bump rarity
        while random.uniform(1, 100) <= pack_data[level]["upgrade"] * bump_boost:
            if is_single:
                reward_texts.append(f"{get_emoji(pack_data[level]['name'].lower() + 'pack')} {pack_data[level]['name']}\n" + build_string)
                build_string = f"Upgraded from {get_emoji(pack_data[level]['name'].lower() + 'pack')} {pack_data[level]['name']}!\n" + build_string
            else:
                build_string += f" -> {get_emoji(pack_data[level + 1]['name'].lower() + 'pack')}"
            level += 1
            upgrades += 1
        final_level = pack_data[level]
        if is_single:
            reward_texts.append(f"{get_emoji(final_level['name'].lower() + 'pack')} {final_level['name']}\n" + build_string)

        # select cat type
        goal_value = final_level["value"]
        chosen_type = random.choice(cattypes)
        cat_emoji = get_emoji(chosen_type.lower() + "cat")
        pre_cat_amount = goal_value / (sum(type_dict.values()) / type_dict[chosen_type])
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
            reward_texts.append(reward_texts[-1] + f"\nYou got {get_emoji(chosen_type.lower() + 'cat')} {cat_amount:,} {chosen_type} cats!")
            return chosen_type, cat_amount, upgrades, reward_texts
        return chosen_type, cat_amount, upgrades, build_string

    async def open_pack(interaction: discord.Interaction):
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        await interaction.response.defer()
        pack = interaction.data["custom_id"]
        await user.refresh_from_db()
        if user[f"pack_{pack.lower()}"] < 1:
            return
        level = next((i for i, p in enumerate(pack_data) if p["name"] == pack), 0)

        chosen_type, cat_amount, upgrades, reward_texts = get_pack_rewards(level)
        user[f"cat_{chosen_type}"] += cat_amount
        user.pack_upgrades += upgrades
        user.packs_opened += 1
        user[f"pack_{pack.lower()}"] -= 1
        await user.save()

        logging.debug("Opened pack %s", pack)

        embed = discord.Embed(title=reward_texts[0], color=Colors.brown)
        await interaction.edit_original_response(embed=embed, view=None)
        for reward_text in reward_texts[1:]:
            await asyncio.sleep(1)
            things = reward_text.split("\n", 1)
            embed = discord.Embed(title=things[0], description=things[1], color=Colors.brown)
            await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(1)
        await interaction.edit_original_response(view=gen_view(user))

    async def open_all_packs(interaction: discord.Interaction):
        embed = await process_pack_opening()
        if not embed:
            return

        await message.edit_original_response(embed=embed, view=None)
        await asyncio.sleep(1)
        await message.edit_original_response(view=gen_view(user))

    description = "Each pack starts at one of eight tiers of increasing value - Wooden, Stone, Bronze, Silver, Gold, Platinum, Diamond, or Celestial - and can repeatedly move up tiers with a 30% chance per upgrade. This means that even a pack starting at Wooden, through successive upgrades, can reach the Celestial tier.\n[Chance Info](<https://catbot.minkos.lol/packs>)\n\nClick the buttons below to start opening packs!"
    embed = discord.Embed(title=f"{get_emoji('bronzepack')} Packs", description=description, color=Colors.brown)
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await message.response.send_message(embed=embed, view=gen_view(user))


@bot.tree.command(description="why would anyone think a cattlepass would be a good idea")
async def battlepass(message: discord.Interaction):
    current_mode = ""
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    global_user = await User.get_or_create(user_id=message.user.id)

    async def toggle_reminders(interaction: discord.Interaction):
        nonlocal current_mode
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        await interaction.response.defer()
        await user.refresh_from_db()
        if not user.reminders_enabled:
            try:
                dm_channel = await fetch_dm_channel(global_user)
                await dm_channel.send(
                    f"You have enabled reminders in {interaction.guild.name}. You can disable them in the /battlepass command in that server or by saying `disable {interaction.guild.id}` here any time."
                )
            except Exception:
                await interaction.followup.send(
                    "Failed. Ensure you have DMs open by going to Server > Privacy Settings > Allow direct messages from server members."
                )
                return

        user.reminders_enabled = not user.reminders_enabled
        await user.save()

        view = View(timeout=VIEW_TIMEOUT)
        button = Button(emoji="🔄", label="Refresh", style=ButtonStyle.blurple)
        button.callback = gen_main
        view.add_item(button)

        if user.reminders_enabled:
            button = Button(emoji="🔕", style=ButtonStyle.blurple)
        else:
            button = Button(label="Enable Reminders", emoji="🔔", style=ButtonStyle.green)
        button.callback = toggle_reminders
        view.add_item(button)

        await interaction.followup.send(
            f"Reminders are now {'enabled' if user.reminders_enabled else 'disabled'}.",
            ephemeral=True,
        )
        await interaction.edit_original_response(view=view)

    async def gen_main(interaction, first=False):
        nonlocal current_mode
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        await interaction.response.defer()
        current_mode = "Main"

        await refresh_quests(user)

        await global_user.refresh_from_db()
        if global_user.vote_time_topgg + 12 * 3600 > time.time():
            await progress(message, user, "vote")
            await global_user.refresh_from_db()

        await user.refresh_from_db()

        # season end
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=4)

        if now.month == 12:
            next_month = datetime.datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime.datetime(now.year, now.month + 1, 1)

        next_month -= datetime.timedelta(hours=4)

        timestamp = int(time.mktime(next_month.timetuple()))

        description = f"Season ends <t:{timestamp}:R>\n\n"

        # vote
        streak_string = ""
        if global_user.vote_streak >= 5:
            streak_string = f" (🔥 {global_user.vote_streak}x streak)"
        if user.vote_cooldown != 0:
            description += f"✅ ~~Vote on Top.gg~~\n- Refreshes <t:{int(user.vote_cooldown + 12 * 3600)}:R>{streak_string}\n"
        else:
            # inform double vote xp during weekends
            is_weekend = now.weekday() >= 4

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
        catch_quest = battle["quests"]["catch"][user.catch_quest]
        if user.catch_cooldown != 0:
            description += f"✅ ~~{catch_quest['title']}~~\n- Refreshes <t:{int(user.catch_cooldown + 12 * 3600 if user.catch_cooldown + 12 * 3600 < timestamp else timestamp)}:R>\n"
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
        misc_quest = battle["quests"]["misc"][user.misc_quest]
        if user.misc_cooldown != 0:
            description += f"✅ ~~{misc_quest['title']}~~\n- Refreshes <t:{int(user.misc_cooldown + 12 * 3600 if user.misc_cooldown + 12 * 3600 < timestamp else timestamp)}:R>\n\n"
        else:
            progress_string = ""
            if misc_quest["progress"] != 1:
                progress_string = f" ({user.misc_progress}/{misc_quest['progress']})"
            description += f"{get_emoji(misc_quest['emoji'])} {misc_quest['title']}{progress_string}\n- Reward: {user.misc_reward} XP\n\n"

        if user.battlepass >= len(battle["seasons"][str(user.season)]):
            description += f"**Extra Rewards** [{user.progress}/1500 XP]\n"
            colored = int(user.progress / 150)
            description += get_emoji("staring_square") * colored + "⬛" * (10 - colored) + "\nReward: " + get_emoji("stonepack") + " Stone pack\n\n"
        else:
            level_data = battle["seasons"][str(user.season)][user.battlepass]
            description += f"**Level {user.battlepass + 1}/30** [{user.progress}/{level_data['xp']} XP]\n"
            colored = int(user.progress / level_data["xp"] * 10)
            description += f"**{user.battlepass}** " + get_emoji("staring_square") * colored + "⬛" * (10 - colored) + f" **{user.battlepass + 1}**\n"

            if level_data["reward"] == "Rain":
                description += f"Reward: ☔ {level_data['amount']} minutes of rain\n\n"
            elif level_data["reward"] in cattypes:
                description += f"Reward: {get_emoji(level_data['reward'].lower() + 'cat')} {level_data['amount']} {level_data['reward']} cats\n\n"
            else:
                description += f"Reward: {get_emoji(level_data['reward'].lower() + 'pack')} {level_data['reward']} pack\n\n"

        # next reward
        levels = battle["seasons"][str(user.season)]
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
        if user.battlepass >= len(battle["seasons"][str(user.season)]) - 1:
            description += f"*Extra:* {get_emoji('stonepack')} per 1500 XP"

        embedVar = discord.Embed(
            title=f"Cattlepass Season {user.season}",
            description=description,
            color=Colors.brown,
        ).set_footer(text=rain_shill)
        view = View(timeout=VIEW_TIMEOUT)

        button = Button(emoji="🔄", label="Refresh", style=ButtonStyle.blurple)
        button.callback = gen_main
        view.add_item(button)

        if user.reminders_enabled:
            button = Button(emoji="🔕", style=ButtonStyle.blurple)
        else:
            button = Button(label="Enable Reminders", emoji="🔔", style=ButtonStyle.green)
        button.callback = toggle_reminders
        view.add_item(button)

        if len(news_list) > len(global_user.news_state.strip()) or "0" in global_user.news_state.strip()[-4:]:
            embedVar.set_author(name="You have unread news! /news")

        if first:
            await interaction.followup.send(embed=embedVar, view=view)
        else:
            await interaction.edit_original_response(embed=embedVar, view=view)

    await gen_main(message, True)


@bot.tree.command(description="vote for cat bot")
async def vote(message: discord.Interaction):
    view = View(timeout=1)
    button = Button(label="Vote!", url="https://top.gg/bot/966695034340663367/vote", emoji=get_emoji("topgg"))
    view.add_item(button)
    await message.response.send_message(view=view)


@bot.tree.command(description="cat prisms are a special power up")
@discord.app_commands.describe(person="Person to view the prisms of")
async def prism(message: discord.Interaction, person: Optional[discord.User]):
    icon = get_emoji("prism")
    page_number = 0

    if not person:
        person_id = message.user
    else:
        person_id = person

    user_prisms = await Prism.collect("guild_id = $1 AND user_id = $2", message.guild.id, person_id.id)
    all_prisms = await Prism.collect("guild_id = $1", message.guild.id)
    total_count = len(all_prisms)
    user_count = len(user_prisms)
    global_boost = 0.06 * math.log(2 * total_count + 1)
    user_boost = round((global_boost + 0.03 * math.log(2 * user_count + 1)) * 100, 3)
    prism_texts = []

    if person_id == message.user and user_count != 0:
        await achemb(message, "prism", "followup")

    order_map = {name: index for index, name in enumerate(prism_names)}
    prisms = all_prisms if not person else user_prisms
    prisms.sort(key=lambda p: order_map.get(p.name, float("inf")))

    for prism in prisms:
        prism_texts.append(f"{icon} **{prism.name}** {f'Owner: <@{prism.user_id}>' if not person else ''}\n<@{prism.creator}> crafted <t:{prism.time}:D>")

    if len(prisms) == 0:
        prism_texts.append("No prisms found!")

    async def confirm_craft(interaction: discord.Interaction):
        await interaction.response.defer()
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)

        # check we still can craft
        for i in cattypes:
            if user["cat_" + i] < 1:
                await interaction.followup.send("You don't have enough cats. Nice try though.", ephemeral=True)
                return

        if await Prism.count("guild_id = $1", interaction.guild.id) >= len(prism_names):
            await interaction.followup.send("This server has reached the prism limit.", ephemeral=True)
            return

        # determine the next name
        for selected_name in prism_names:
            if not await Prism.get_or_none(guild_id=message.guild.id, name=selected_name):
                break

        youngest_prism = await Prism.collect("guild_id = $1 ORDER BY time DESC LIMIT 1", message.guild.id)
        if youngest_prism:
            selected_time = max(round(time.time()), youngest_prism[0].time + 1)
        else:
            selected_time = round(time.time())

        # actually take away cats
        for i in cattypes:
            user["cat_" + i] -= 1
        await user.save()

        # create the prism
        await Prism.create(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            creator=interaction.user.id,
            time=selected_time,
            name=selected_name,
        )

        logging.debug("Created prism")

        await message.followup.send(f"{icon} {interaction.user.mention} has created prism {selected_name}!")
        await achemb(interaction, "prism", "followup")
        await achemb(interaction, "collecter", "followup")

    async def craft_prism(interaction: discord.Interaction):
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)

        found_cats = await cats_in_server(interaction.guild.id)
        missing_cats = []
        for i in cattypes:
            if user[f"cat_{i}"] > 0:
                continue
            if i in found_cats:
                missing_cats.append(get_emoji(i.lower() + "cat"))
            else:
                missing_cats.append(get_emoji("mysterycat"))

        if len(missing_cats) == 0:
            view = View(timeout=VIEW_TIMEOUT)
            confirm_button = Button(label="Craft!", style=ButtonStyle.blurple, emoji=icon)
            confirm_button.callback = confirm_craft
            description = "The crafting recipe is __ONE of EVERY cat type__.\nContinue crafting?"
        else:
            view = View(timeout=VIEW_TIMEOUT)
            confirm_button = Button(label="Not enough cats!", style=ButtonStyle.red, disabled=True)
            description = "The crafting recipe is __ONE of EVERY cat type__.\nYou are missing " + "".join(missing_cats)

        view.add_item(confirm_button)
        await interaction.response.send_message(description, view=view, ephemeral=True)

    async def prev_page(interaction):
        nonlocal page_number
        page_number -= 1
        embed, view = gen_page()
        await interaction.response.edit_message(embed=embed, view=view)

    async def next_page(interaction):
        nonlocal page_number
        page_number += 1
        embed, view = gen_page()
        await interaction.response.edit_message(embed=embed, view=view)

    def gen_page():
        target = "" if not person else f"{person_id.name}'s"

        embed = discord.Embed(
            title=f"{icon} {target} Cat Prisms",
            color=Colors.brown,
            description="Prisms are a tradeable power-up which occasionally bumps cat rarity up by one. Each prism crafted gives the entire server an increased chance to get upgraded, plus additional chance for prism owner.\n\n",
        ).set_footer(
            text=f"{total_count} Total Prisms | Server boost: {round(global_boost * 100, 3)}%\n{person_id.name}'s prisms | Owned: {user_count} | Personal boost: {user_boost}%"
        )

        embed.description += "\n".join(prism_texts[page_number * 26 : (page_number + 1) * 26])

        view = View(timeout=VIEW_TIMEOUT)

        craft_button = Button(label="Craft!", style=ButtonStyle.blurple, emoji=icon)
        craft_button.callback = craft_prism
        view.add_item(craft_button)

        prev_button = Button(label="<-", disabled=bool(page_number == 0))
        prev_button.callback = prev_page
        view.add_item(prev_button)

        next_button = Button(label="->", disabled=bool(page_number == (len(prism_texts) + 1) // 26))
        next_button.callback = next_page
        view.add_item(next_button)

        return embed, view

    embed, view = gen_page()
    await message.response.send_message(embed=embed, view=view)


@bot.tree.command(description="Pong")
async def ping(message: discord.Interaction):
    try:
        latency = round(bot.latency * 1000)
    except Exception:
        latency = "infinite"
    if latency == 0:
        # probably using gateway proxy, try fetching latency from metrics
        async with aiohttp.ClientSession() as session:
            shard_latency = 0
            try:
                async with session.get("http://localhost:7878/metrics") as response:
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
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, user, "ping")


@bot.tree.command(description="play a relaxing game of tic tac toe")
@discord.app_commands.describe(person="who do you want to play with? (choose Cat Bot for ai)")
async def tictactoe(message: discord.Interaction, person: discord.Member):
    do_edit = False
    board = [None, None, None, None, None, None, None, None, None]

    players = [message.user, person]
    random.shuffle(players)
    bot_is_playing = person == bot.user
    current_turn = 0

    def check_win(board):
        combinations = [
            # rows
            [0, 1, 2],
            [3, 4, 5],
            [6, 7, 8],
            # columns
            [0, 3, 6],
            [1, 4, 7],
            [2, 5, 8],
            # diagonals
            [0, 4, 8],
            [2, 4, 6],
        ]

        for combination in combinations:
            if board[combination[0]] == board[combination[1]] == board[combination[2]] and board[combination[0]] is not None:
                return combination

        return [-1]

    def minimax(board, depth, is_maximizing, alpha, beta, bot_symbol, human_symbol):
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

    def get_best_move(board):
        best_score = float("-inf")
        best_move = None

        bot_turn = None
        human_turn = None
        for i, player in enumerate(players):
            if player.bot:
                bot_turn = i
            else:
                human_turn = i

        bot_symbol = "❌" if bot_turn == 0 else "⭕"
        human_symbol = "❌" if human_turn == 0 else "⭕"

        for i in range(9):
            if board[i] is None:
                board[i] = bot_symbol
                score = minimax(board, 0, False, float("-inf"), float("inf"), bot_symbol, human_symbol)
                board[i] = None

                if score > best_score:
                    best_score = score
                    best_move = i

        return best_move

    async def finish_turn():
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

        container = Container(f"## {players[0].mention} (X) vs {players[1].mention} (O)", second_line, rows[0], rows[1], rows[2])
        view.add_item(container)

        if do_edit:
            await message.edit_original_response(view=view)
        else:
            await message.response.send_message(view=view)
            do_edit = True

        if bot_is_playing and players[current_turn].bot and wins == [-1] and not tie:
            await asyncio.sleep(1)
            best_move = get_best_move(board)
            if best_move is not None:
                board[best_move] = "❌" if current_turn == 0 else "⭕"
                current_turn = 1 - current_turn
                await finish_turn()

    async def play(interaction):
        nonlocal current_turn
        cell_num = int(interaction.data["custom_id"])
        if board[cell_num] is not None:
            await interaction.response.send_message("That spot is already taken!", ephemeral=True)
            return
        if players[current_turn] != interaction.user:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        await interaction.response.defer()
        board[cell_num] = "❌" if current_turn == 0 else "⭕"
        current_turn = 1 - current_turn
        await finish_turn()

    async def end_game(winner):
        if players[0] == players[1]:
            # self-play
            user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
            await progress(message, user, "ttc")
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
        await users[0].save()
        await users[1].save()
        await progress(message, users[0], "ttc")
        await progress(message, users[1], "ttc")

    await finish_turn()


@bot.tree.command(description="dont select a person to make an everyone vs you game")
@discord.app_commands.describe(person="Who do you want to play with?")
async def rps(message: discord.Interaction, person: Optional[discord.Member]):
    clean_name = message.user.name.replace("_", "\\_")
    picks = {"Rock": [], "Paper": [], "Scissors": []}
    mappings = {"Rock": ["Paper", "Rock", "Scissors"], "Paper": ["Scissors", "Paper", "Rock"], "Scissors": ["Rock", "Scissors", "Paper"]}
    vs_picks = {}
    players = []

    async def pick(interaction):
        nonlocal players
        if person and interaction.user.id not in [message.user.id, person.id]:
            await do_funny(interaction)
            return

        await interaction.response.defer()

        thing = interaction.data["custom_id"]
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
                await interaction.edit_original_response(content=f"Players picked: {len(players)}")
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
        await interaction.edit_original_response(content=None, embed=embed, view=None)

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
    cookie_id = (message.guild.id, message.user.id)
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    if cookie_id not in temp_cookie_storage.keys():
        temp_cookie_storage[cookie_id] = user.cookies

    async def bake(interaction):
        if interaction.user != message.user:
            await do_funny(interaction)
            return
        await interaction.response.defer()
        if cookie_id in temp_cookie_storage:
            curr = temp_cookie_storage[cookie_id]
        else:
            await user.refresh_from_db()
            curr = user.cookies
        curr += 1
        temp_cookie_storage[cookie_id] = curr
        view.children[0].label = f"{curr:,}"
        await interaction.edit_original_response(view=view)
        if curr < 5:
            await achemb(interaction, "cookieclicker", "followup")
        if 5100 > curr >= 5000:
            await achemb(interaction, "cookiesclicked", "followup")

    view = View(timeout=VIEW_TIMEOUT)
    button = Button(emoji="🍪", label=f"{temp_cookie_storage[cookie_id]:,}", style=ButtonStyle.blurple)
    button.callback = bake
    view.add_item(button)
    await message.response.send_message(view=view)


@bot.tree.command(description="give cats now")
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(
    person="Whom to gift?",
    cat_type="im gonna airstrike your house from orbit",
    amount="And how much?",
)
@discord.app_commands.autocomplete(cat_type=gift_autocomplete)
async def gift(
    message: discord.Interaction,
    person: discord.User,
    cat_type: str,
    amount: Optional[int],
):
    if amount is None:
        # default the amount to 1
        amount = 1
    person_id = person.id

    if amount <= 0 or message.user.id == person_id:
        # haha skill issue
        await message.response.send_message("no", ephemeral=True)
        if message.user.id == person_id:
            await achemb(message, "lonely", "followup")
        return

    if cat_type in cattypes:
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
        # if we even have enough cats
        if user[f"cat_{cat_type}"] >= amount:
            reciever = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id)
            user[f"cat_{cat_type}"] -= amount
            reciever[f"cat_{cat_type}"] += amount
            try:
                user.cats_gifted += amount
                reciever.cat_gifts_recieved += amount
            except Exception:
                pass
            await user.save()
            await reciever.save()
            content = f"Successfully transfered {amount:,} {cat_type} cats from {message.user.mention} to <@{person_id}>!"

            # handle tax
            if amount >= 5:
                tax_amount = round(amount * 0.2)
                tax_debounce = False

                async def pay(interaction):
                    nonlocal tax_debounce
                    if interaction.user.id == message.user.id and not tax_debounce:
                        tax_debounce = True
                        await interaction.response.defer()
                        await user.refresh_from_db()
                        try:
                            # transfer tax
                            user[f"cat_{cat_type}"] -= tax_amount

                            try:
                                await interaction.edit_original_response(view=None)
                            except Exception:
                                pass
                            await interaction.followup.send(f"Tax of {tax_amount:,} {cat_type} cats was withdrawn from your account!")
                        finally:
                            # always save to prevent issue with exceptions leaving bugged state
                            await user.save()
                        await achemb(message, "good_citizen", "followup")
                        if user[f"cat_{cat_type}"] < 0:
                            bot.loop.create_task(debt_cutscene(interaction, user))
                    else:
                        await do_funny(interaction)

                async def evade(interaction):
                    if interaction.user.id == message.user.id:
                        await interaction.response.defer()
                        try:
                            await interaction.edit_original_response(view=None)
                        except Exception:
                            pass
                        await interaction.followup.send(f"You evaded the tax of {tax_amount:,} {cat_type} cats.")
                        await achemb(message, "secret", "followup")
                    else:
                        await do_funny(interaction)

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
            await achemb(message, "donator", "followup")
            await achemb(message, "anti_donator", "followup", person)
            if person_id == bot.user.id and cat_type == "Ultimate" and int(amount) >= 5:
                await achemb(message, "rich", "followup")
            if person_id == bot.user.id:
                await achemb(message, "sacrifice", "followup")
            if cat_type == "Nice" and int(amount) == 69:
                await achemb(message, "nice", "followup")

            await progress(message, user, "gift")
        else:
            await message.response.send_message("no", ephemeral=True)
    elif cat_type.lower() == "rain":
        if person_id == bot.user.id:
            await message.response.send_message("you can't sacrifice rains", ephemeral=True)
            return

        actual_user = await User.get_or_create(user_id=message.user.id)
        actual_receiver = await User.get_or_create(user_id=person_id)
        if actual_user.rain_minutes >= amount:
            actual_user.rain_minutes -= amount
            actual_receiver.rain_minutes += amount
            await actual_user.save()
            await actual_receiver.save()
            content = f"Successfully transfered {amount:,} minutes of rain from {message.user.mention} to <@{person_id}>!"

            await message.response.send_message(content, allowed_mentions=discord.AllowedMentions(users=True))

            # handle aches
            await achemb(message, "donator", "followup")
            await achemb(message, "anti_donator", "followup", person)
            user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
            await progress(message, user, "gift")
        else:
            await message.response.send_message("no", ephemeral=True)

        try:
            ch = bot.get_partial_messageable(config.RAIN_CHANNEL_ID)
            await ch.send(f"{message.user.id} gave {amount}m to {person_id}")
        except Exception:
            pass
    elif cat_type.lower() in [i["name"].lower() for i in pack_data]:
        cat_type = cat_type.lower()
        # packs um also this seems to be repetetive uh
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
        # if we even have enough packs
        if user[f"pack_{cat_type}"] >= amount:
            reciever = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id)
            user[f"pack_{cat_type}"] -= amount
            reciever[f"pack_{cat_type}"] += amount
            await user.save()
            await reciever.save()
            content = f"Successfully transfered {amount:,} {cat_type} packs from {message.user.mention} to <@{person_id}>!"

            await message.response.send_message(content, allowed_mentions=discord.AllowedMentions(users=True))

            # handle aches
            await achemb(message, "donator", "followup")
            await achemb(message, "anti_donator", "followup", person)
            if person_id == bot.user.id:
                await achemb(message, "sacrifice", "followup")

            await progress(message, user, "gift")
        else:
            await message.response.send_message("no", ephemeral=True)
    else:
        await message.response.send_message("bro what", ephemeral=True)


@bot.tree.command(description="Trade stuff!")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="why would you need description")
async def trade(message: discord.Interaction, person_id: discord.User):
    person1 = message.user
    person2 = person_id

    blackhole = False

    person1accept = False
    person2accept = False

    person1value = 0
    person2value = 0

    person1gives = {}
    person2gives = {}

    user1 = await Profile.get_or_create(guild_id=message.guild.id, user_id=person1.id)
    user2 = await Profile.get_or_create(guild_id=message.guild.id, user_id=person2.id)

    if not bot.user:
        return

    # do the funny
    if person2.id == bot.user.id:
        person2gives["eGirl"] = 9999999

    # this is the deny button code
    async def denyb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole
        if interaction.user != person1 and interaction.user != person2:
            await do_funny(interaction)
            return

        await interaction.response.defer()
        blackhole = True
        person1gives = {}
        person2gives = {}
        try:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention} has cancelled the trade.",
                embed=None,
                view=None,
            )
        except Exception:
            pass

    # this is the accept button code
    async def acceptb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, person1value, person2value, user1, user2, blackhole
        if interaction.user != person1 and interaction.user != person2:
            await do_funny(interaction)
            return

        # clicking accept again would make you un-accept
        if interaction.user == person1:
            person1accept = not person1accept
        elif interaction.user == person2:
            person2accept = not person2accept

        await interaction.response.defer()
        await update_trade_embed(interaction)

        if person1accept and person2 == bot.user:
            await achemb(message, "desperate", "followup")

        if blackhole:
            await update_trade_embed(interaction)
            return

        if person1accept and person2accept:
            blackhole = True
            await user1.refresh_from_db()
            await user2.refresh_from_db()
            actual_user1 = await User.get_or_create(user_id=person1.id)
            actual_user2 = await User.get_or_create(user_id=person2.id)

            # check if we have enough things (person could have moved them during the trade)
            error = False
            person1prismgive = 0
            person2prismgive = 0
            for k, v in person1gives.items():
                if k in prism_names:
                    person1prismgive += 1
                    prism = await Prism.get_or_none(guild_id=interaction.guild.id, name=k)
                    if not prism or prism.user_id != person1.id:
                        error = True
                        break
                    continue
                elif k == "rains":
                    if actual_user1.rain_minutes < v:
                        error = True
                        break
                elif k in cattypes:
                    if user1[f"cat_{k}"] < v:
                        error = True
                        break
                elif user1[f"pack_{k.lower()}"] < v:
                    error = True
                    break

            for k, v in person2gives.items():
                if k in prism_names:
                    person2prismgive += 1
                    prism = await Prism.get_or_none(guild_id=interaction.guild.id, name=k)
                    if not prism or prism.user_id != person2.id:
                        error = True
                        break
                    continue
                elif k == "rains":
                    if actual_user2.rain_minutes < v:
                        error = True
                        break
                elif k in cattypes:
                    if user2[f"cat_{k}"] < v:
                        error = True
                        break
                elif user2[f"pack_{k.lower()}"] < v:
                    error = True
                    break

            if error:
                try:
                    await interaction.edit_original_response(
                        content="Uh oh - some of the cats/prisms/packs/rains disappeared while trade was happening",
                        embed=None,
                        view=None,
                    )
                except Exception:
                    await interaction.followup.send("Uh oh - some of the cats/prisms/packs/rains disappeared while trade was happening")
                return

            # exchange
            cat_count = 0
            for k, v in person1gives.items():
                if k in prism_names:
                    move_prism = await Prism.get_or_none(guild_id=message.guild.id, name=k)
                    move_prism.user_id = person2.id
                    await move_prism.save()
                elif k == "rains":
                    actual_user1.rain_minutes -= v
                    actual_user2.rain_minutes += v
                    try:
                        ch = bot.get_partial_messageable(config.RAIN_CHANNEL_ID)
                        await ch.send(f"{actual_user1.user_id} traded {v}m to {actual_user2.user_id}")
                    except Exception:
                        pass
                elif k in cattypes:
                    cat_count += v
                    user1[f"cat_{k}"] -= v
                    user2[f"cat_{k}"] += v
                else:
                    user1[f"pack_{k.lower()}"] -= v
                    user2[f"pack_{k.lower()}"] += v

            for k, v in person2gives.items():
                if k in prism_names:
                    move_prism = await Prism.get_or_none(guild_id=message.guild.id, name=k)
                    move_prism.user_id = person1.id
                    await move_prism.save()
                elif k == "rains":
                    actual_user2.rain_minutes -= v
                    actual_user1.rain_minutes += v
                    try:
                        ch = bot.get_partial_messageable(config.RAIN_CHANNEL_ID)
                        await ch.send(f"{actual_user2.user_id} traded {v}m to {actual_user1.user_id}")
                    except Exception:
                        pass
                elif k in cattypes:
                    cat_count += v
                    user1[f"cat_{k}"] += v
                    user2[f"cat_{k}"] -= v
                else:
                    user1[f"pack_{k.lower()}"] += v
                    user2[f"pack_{k.lower()}"] -= v

            user1.cats_traded += cat_count
            user2.cats_traded += cat_count
            user1.trades_completed += 1
            user2.trades_completed += 1

            await user1.save()
            await user2.save()
            await actual_user1.save()
            await actual_user2.save()

            try:
                await interaction.edit_original_response(content="Trade finished!", view=None)
            except Exception:
                await interaction.followup.send()

            await achemb(message, "extrovert", "followup")
            await achemb(message, "extrovert", "followup", person2)

            if cat_count >= 1000:
                await achemb(message, "capitalism", "followup")
                await achemb(message, "capitalism", "followup", person2)

            if person2value + person1value == 0:
                await achemb(message, "absolutely_nothing", "followup")
                await achemb(message, "absolutely_nothing", "followup", person2)

            if person2value - person1value >= 100:
                await achemb(message, "profit", "followup")
            if person1value - person2value >= 100:
                await achemb(message, "profit", "followup", person2)

            if person1value > person2value:
                await achemb(message, "scammed", "followup")
            if person2value > person1value:
                await achemb(message, "scammed", "followup", person2)

            if person1value == person2value and person1gives != person2gives:
                await achemb(message, "perfectly_balanced", "followup")
                await achemb(message, "perfectly_balanced", "followup", person2)

            await progress(message, user1, "trade")
            await progress(message, user2, "trade")

    # add cat code
    async def addb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
        if interaction.user != person1 and interaction.user != person2:
            await do_funny(interaction)
            return

        currentuser = 1 if interaction.user == person1 else 2

        # all we really do is spawn the modal
        modal = TradeModal(currentuser)
        await interaction.response.send_modal(modal)

    # this is ran like everywhere when you do anything
    # it updates the embed
    async def gen_embed():
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole, person1value, person2value

        if blackhole:
            # no way thats fun
            await achemb(message, "blackhole", "followup")
            await achemb(message, "blackhole", "followup", person2)
            return discord.Embed(color=Colors.brown, title="Blackhole", description="How Did We Get Here?"), None

        view = View(timeout=VIEW_TIMEOUT)

        accept = Button(label="Accept", style=ButtonStyle.green)
        accept.callback = acceptb

        deny = Button(label="Deny", style=ButtonStyle.red)
        deny.callback = denyb

        add = Button(label="Offer...", style=ButtonStyle.blurple)
        add.callback = addb

        view.add_item(accept)
        view.add_item(deny)
        view.add_item(add)

        person1name = person1.name.replace("_", "\\_")
        person2name = person2.name.replace("_", "\\_")
        coolembed = discord.Embed(
            color=Colors.brown,
            title=f"{person1name} and {person2name} trade",
            description="no way",
        )

        # a single field for one person
        def field(personaccept, persongives, person, number):
            nonlocal coolembed, person1value, person2value
            icon = "⬜"
            if personaccept:
                icon = "✅"
            valuestr = ""
            valuenum = 0
            total = 0
            for k, v in persongives.items():
                if v == 0:
                    continue
                if k in prism_names:
                    # prisms
                    valuestr += f"{get_emoji('prism')} {k}\n"
                    for v2 in type_dict.values():
                        valuenum += sum(type_dict.values()) / v2
                elif k == "rains":
                    # rains
                    valuestr += f"☔ {v:,}m of Cat Rains\n"
                    valuenum += 900 * v
                elif k in cattypes:
                    # cats
                    valuenum += (sum(type_dict.values()) / type_dict[k]) * v
                    total += v
                    aicon = get_emoji(k.lower() + "cat")
                    valuestr += f"{aicon} {k} {v:,}\n"
                else:
                    # packs
                    valuenum += sum([i["totalvalue"] if i["name"] == k else 0 for i in pack_data]) * v
                    aicon = get_emoji(k.lower() + "pack")
                    valuestr += f"{aicon} {k} {v:,}\n"
            if not valuestr:
                valuestr = "Nothing offered!"
            else:
                valuestr += f"*Total value: {round(valuenum):,}\nTotal cats: {round(total):,}*"
                if number == 1:
                    person1value = round(valuenum)
                else:
                    person2value = round(valuenum)
            personname = person.name.replace("_", "\\_")
            coolembed.add_field(name=f"{icon} {personname}", inline=True, value=valuestr)

        field(person1accept, person1gives, person1, 1)
        field(person2accept, person2gives, person2, 2)

        return coolembed, view

    # this is wrapper around gen_embed() to edit the mesage automatically
    async def update_trade_embed(interaction):
        embed, view = await gen_embed()
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            await achemb(message, "blackhole", "followup")
            await achemb(message, "blackhole", "followup", person2)

    # lets go add cats modal thats fun
    class TradeModal(Modal):
        def __init__(self, currentuser):
            super().__init__(
                title="Add to the trade",
                timeout=3600,
            )
            self.currentuser = currentuser

            self.cattype = TextInput(
                label='Cat or Pack Type, Prism Name or "Rain"',
                placeholder="Fine / Wooden / Alpha / Rain",
            )
            self.add_item(self.cattype)

            self.amount = TextInput(label="Amount to offer", placeholder="1", required=False)
            self.add_item(self.amount)

        # this is ran when user submits
        async def on_submit(self, interaction: discord.Interaction):
            nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
            value = self.amount.value if self.amount.value else 1
            await user1.refresh_from_db()
            await user2.refresh_from_db()

            try:
                if int(value) < 0:
                    person1accept = False
                    person2accept = False
            except Exception:
                await interaction.response.send_message("invalid amount", ephemeral=True)
                return

            # handle prisms
            if (pname := " ".join(i.capitalize() for i in self.cattype.value.split())) in prism_names:
                try:
                    prism = await Prism.get_or_none(guild_id=interaction.guild.id, name=pname)
                    if not prism:
                        raise Exception
                except Exception:
                    await interaction.response.send_message("this prism doesnt exist", ephemeral=True)
                    return
                if prism.user_id != interaction.user.id:
                    await interaction.response.send_message("this is not your prism", ephemeral=True)
                    return
                if (self.currentuser == 1 and pname in person1gives.keys()) or (self.currentuser == 2 and pname in person2gives.keys()):
                    await interaction.response.send_message("you already added this prism", ephemeral=True)
                    return

                if self.currentuser == 1:
                    person1gives[pname] = 1
                else:
                    person2gives[pname] = 1
                await interaction.response.defer()
                await update_trade_embed(interaction)
                return

            # handle packs
            if self.cattype.value.capitalize() in [i["name"] for i in pack_data]:
                pname = self.cattype.value.capitalize()
                if self.currentuser == 1:
                    if user1[f"pack_{pname.lower()}"] < int(value):
                        await interaction.response.send_message("you dont have enough packs", ephemeral=True)
                        return
                    new_val = person1gives.get(pname, 0) + int(value)
                    if new_val >= 0:
                        person1gives[pname] = new_val
                    else:
                        await interaction.response.send_message("skibidi toilet", ephemeral=True)
                        return
                else:
                    if user2[f"pack_{pname.lower()}"] < int(value):
                        await interaction.response.send_message("you dont have enough packs", ephemeral=True)
                        return
                    new_val = person2gives.get(pname, 0) + int(value)
                    if new_val >= 0:
                        person2gives[pname] = new_val
                    else:
                        await interaction.response.send_message("skibidi toilet", ephemeral=True)
                        return
                await interaction.response.defer()
                await update_trade_embed(interaction)
                return

            # handle rains
            if "rain" in self.cattype.value.lower():
                user = await User.get_or_create(user_id=interaction.user.id)
                try:
                    if user.rain_minutes < int(value) or int(value) < 1:
                        await interaction.response.send_message("you dont have enough rains", ephemeral=True)
                        return
                except Exception:
                    await interaction.response.send_message("please enter a number for amount", ephemeral=True)
                    return

                if self.currentuser == 1:
                    try:
                        person1gives["rains"] += int(value)
                    except Exception:
                        person1gives["rains"] = int(value)
                else:
                    try:
                        person2gives["rains"] += int(value)
                    except Exception:
                        person2gives["rains"] = int(value)
                await interaction.response.defer()
                await update_trade_embed(interaction)
                return

            lc_input = self.cattype.value.lower()

            # loop through the cat types and find the correct one using lowercased user input.
            cname = cattype_lc_dict.get(lc_input, None)

            # if no cat type was found, the user input was invalid. as cname is still `None`
            if cname is None:
                await interaction.response.send_message("add a valid cat/pack/prism name 💀💀💀", ephemeral=True)
                return

            try:
                if self.currentuser == 1:
                    currset = person1gives[cname]
                else:
                    currset = person2gives[cname]
            except Exception:
                currset = 0

            try:
                if int(value) + currset < 0 or int(value) == 0:
                    raise Exception
            except Exception:
                await interaction.response.send_message("plz number?", ephemeral=True)
                return

            if (self.currentuser == 1 and user1[f"cat_{cname}"] < int(value) + currset) or (
                self.currentuser == 2 and user2[f"cat_{cname}"] < int(value) + currset
            ):
                await interaction.response.send_message(
                    "hell naww dude you dont even have that many cats 💀💀💀",
                    ephemeral=True,
                )
                return

            # OKE SEEMS GOOD LETS ADD CATS TO THE TRADE
            if self.currentuser == 1:
                try:
                    person1gives[cname] += int(value)
                    if person1gives[cname] == 0:
                        person1gives.pop(cname)
                except Exception:
                    person1gives[cname] = int(value)
            else:
                try:
                    person2gives[cname] += int(value)
                    if person2gives[cname] == 0:
                        person2gives.pop(cname)
                except Exception:
                    person2gives[cname] = int(value)

            await interaction.response.defer()
            await update_trade_embed(interaction)

    embed, view = await gen_embed()
    if not view:
        await message.response.send_message(embed=embed)
    else:
        await message.response.send_message(person2.mention, embed=embed, view=view, allowed_mentions=discord.AllowedMentions(users=True))

    if person1 == person2:
        await achemb(message, "introvert", "followup")


@bot.tree.command(description="Get Cat Image, does not add a cat to your inventory")
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(cat_type="select a cat type ok")
@discord.app_commands.autocomplete(cat_type=cat_command_autocomplete)
async def cat(message: discord.Interaction, cat_type: Optional[str]):
    if cat_type and cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    # check the user has the cat if required
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    if cat_type and user[f"cat_{cat_type}"] <= 0:
        await message.response.send_message("you dont have that cat", ephemeral=True)
        return

    image = f"images/spawn/{cat_type.lower()}_cat.png" if cat_type else "images/cat.png"
    file = discord.File(image, filename=image)
    await message.response.send_message(file=file)


@bot.tree.command(description="Get Cursed Cat")
async def cursed(message: discord.Interaction):
    file = discord.File("images/cursed.jpg", filename="cursed.jpg")
    await message.response.send_message(file=file)


@bot.tree.command(description="Get Your balance")
async def bal(message: discord.Interaction):
    file = discord.File("images/money.png", filename="money.png")
    embed = discord.Embed(title="cat coins", color=Colors.brown).set_image(url="attachment://money.png")
    await message.response.send_message(file=file, embed=embed)


@bot.tree.command(description="Brew some coffee to catch cats more efficiently")
async def brew(message: discord.Interaction):
    await message.response.send_message("HTTP 418: I'm a teapot. <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/418>")
    await achemb(message, "coffee", "followup")


@bot.tree.command(description="Gamble your life savings away in our totally-not-rigged catsino!")
async def casino(message: discord.Interaction):
    if message.user.id + message.guild.id in casino_lock:
        await message.response.send_message(
            "you get kicked out of the catsino because you are already there, and two of you playing at once would cause a glitch in the universe",
            ephemeral=True,
        )
        await achemb(message, "paradoxical_gambler", "followup")
        return

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    # funny global gamble counter cus funny
    total_sum = await Profile.sum("gambles", "gambles > 0")
    embed = discord.Embed(
        title="🎲 The Catsino",
        description=f"One spin costs 5 {get_emoji('finecat')} Fine cats\nSo far you gambled {profile.gambles} times.\nAll Cat Bot users gambled {total_sum:,} times.",
        color=Colors.maroon,
    )

    async def spin(interaction):
        nonlocal message
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        if message.user.id + message.guild.id in casino_lock:
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
        casino_lock.append(message.user.id + message.guild.id)
        profile.cat_Fine += amount - 5
        profile.gambles += 1
        await profile.save()

        if profile.gambles >= 10:
            await achemb(message, "gambling_one", "followup")
        if profile.gambles >= 50:
            await achemb(message, "gambling_two", "followup")

        variants = [
            f"{get_emoji('egirlcat')} 1 eGirl cats",
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
        icon = "🎲"

        for i in variants:
            embed = discord.Embed(title=f"{icon} The Catsino", description=f"**{i}**", color=Colors.maroon)
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass
            await asyncio.sleep(1)

        embed = discord.Embed(
            title=f"{icon} The Catsino",
            description=f"You won:\n**{get_emoji('finecat')} {amount} Fine cats**",
            color=Colors.maroon,
        )

        button = Button(label="Spin", style=ButtonStyle.blurple)
        button.callback = spin

        myview = View(timeout=VIEW_TIMEOUT)
        myview.add_item(button)

        casino_lock.remove(message.user.id + message.guild.id)

        try:
            await interaction.edit_original_response(embed=embed, view=myview)
        except Exception:
            await interaction.followup.send(embed=embed, view=myview)

    button = Button(label="Spin", style=ButtonStyle.blurple)
    button.callback = spin

    myview = View(timeout=VIEW_TIMEOUT)
    myview.add_item(button)

    await message.response.send_message(embed=embed, view=myview)


@bot.tree.command(description="oh no")
async def slots(message: discord.Interaction):
    if message.user.id + message.guild.id in slots_lock:
        await message.response.send_message(
            "you get kicked from the slot machine because you are already there, and two of you playing at once would cause a glitch in the universe",
            ephemeral=True,
        )
        await achemb(message, "paradoxical_gambler", "followup")
        return

    await message.response.defer()

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    total_spins, total_wins, total_big_wins = (
        await Profile.sum("slot_spins", "slot_spins > 0"),
        await Profile.sum("slot_wins", "slot_wins > 0"),
        await Profile.sum("slot_big_wins", "slot_big_wins > 0"),
    )
    embed = discord.Embed(
        title=":slot_machine: The Slot Machine",
        description=f"__Your stats__\n{profile.slot_spins:,} spins\n{profile.slot_wins:,} wins\n{profile.slot_big_wins:,} big wins\n\n__Global stats__\n{total_spins:,} spins\n{total_wins:,} wins\n{total_big_wins:,} big wins",
        color=Colors.maroon,
    )

    async def remove_debt(interaction):
        nonlocal message
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        await profile.refresh_from_db()

        # remove debt
        for i in cattypes:
            profile[f"cat_{i}"] = max(0, profile[f"cat_{i}"])

        await profile.save()
        await interaction.response.send_message("You have removed your debts! Life is wonderful!", ephemeral=True)
        await achemb(interaction, "debt", "followup")

    async def spin(interaction):
        nonlocal message
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        if message.user.id + message.guild.id in slots_lock:
            await interaction.response.send_message(
                "you get kicked from the slot machine because you are already there, and two of you playing at once would cause a glitch in the universe",
                ephemeral=True,
            )
            return
        await profile.refresh_from_db()

        await interaction.response.defer()
        slots_lock.append(message.user.id + message.guild.id)
        profile.slot_spins += 1
        await profile.save()

        try:
            await achemb(interaction, "slots", "followup")
            await progress(message, profile, "slots")
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
                desc += "\n\n**You can remove your debt!**"
                button = Button(label="Remove Debt", style=ButtonStyle.blurple)
                button.callback = remove_debt
                myview.add_item(button)

        slots_lock.remove(message.user.id + message.guild.id)

        embed = discord.Embed(title=":slot_machine: The Slot Machine", description=desc, color=Colors.maroon)

        try:
            await interaction.edit_original_response(embed=embed, view=myview)
        except Exception:
            await interaction.followup.send(embed=embed, view=myview)

    button = Button(label="Spin", style=ButtonStyle.blurple)
    button.callback = spin

    myview = View(timeout=VIEW_TIMEOUT)
    myview.add_item(button)

    await message.followup.send(embed=embed, view=myview)


@bot.tree.command(description="what")
async def roulette(message: discord.Interaction):
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    # this is the silly popup when you click the button
    class RouletteModel(Modal):
        def __init__(self):
            super().__init__(
                title="place a bet idfk",
                timeout=3600,
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

        async def on_submit(self, interaction: discord.Interaction):
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

            # mapping of colors to numbers by indexes
            colors = [
                "green",
                "red",
                "black",
                "red",
                "black",
                "red",
                "black",
                "red",
                "black",
                "red",
                "black",
                "black",
                "red",
                "black",
                "red",
                "black",
                "red",
                "black",
                "red",
                "red",
                "black",
                "red",
                "black",
                "red",
                "black",
                "red",
                "black",
                "red",
                "black",
                "black",
                "red",
                "black",
                "red",
                "black",
                "red",
                "black",
                "red",
            ]

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
            user.roulette_balance = int(round(user.roulette_balance))
            await user.save()

            for wait_time in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.5]:
                choice = random.randint(0, 36)
                color = colors[choice]
                embed = discord.Embed(
                    color=Colors.maroon,
                    title="woo its spinnin",
                    description=f"your bet is {int(self.betamount.value):,} cat dollars on {self.bettype.value.capitalize()}\n\n{emoji_map[color]} **{choice}**",
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
                description=f"your bet was {int(self.betamount.value):,} cat dollars on {self.bettype.value.capitalize()}\n\n{emoji_map[color]} **{final_choice}**\n\nyour new balance is **{user.roulette_balance:,}** cat dollars{broke_suffix}",
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

    async def modal_select(interaction: discord.Interaction):
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
        description=f"your balance is **{user.roulette_balance:,}** cat dollars{broke_suffix}",
    )

    view = View(timeout=VIEW_TIMEOUT)
    b = Button(label="spin", style=ButtonStyle.blurple)
    b.callback = modal_select
    view.add_item(b)

    await message.response.send_message(embed=embed, view=view)

    if user.roulette_balance < 0:
        await achemb(message, "failed_gambler", "followup")


@bot.tree.command(description="roll a dice")
async def roll(message: discord.Interaction, sides: Optional[int]):
    if sides is None:
        sides = 6

    if sides < 0:
        await message.response.send_message("???", ephemeral=True)
        return

    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    if sides == 0:
        # ???
        family_guy_funny_moments = [
            "your sphere doesn't land",
            "your sphere floats in air",
            "your sphere lands and bounces forever",
            "your sphere breaks",
            "your sphere gets turned inside out",
            "your sphere lands in a dumpster",
            "your sphere gets eaten",
            "your sphere lands in an active volcano",
            "your house gets striked down from orbit before your sphere lands",
            "your sphere lands on the bottom of the Mariana trench",
            "your sphere lands inside of a frying pan and burns",
            "your sphere breaks into 0 pieces and the universe throws a runtime error",
            "your sphere is getting married",
            "your sphere turns into a pentagonal bipyramid because it's bored",
            "your sphere defies gravity and floats into the space never to be seen again",
            "your sphere lands in honey and gets sticky",
            "your sphere gets compressed into a blackhole",
            "your sphere became sentient and refused to land",
            "your sphere lands a pretty good job",
            "your sphere lands on a 7 somehow",
            "you try to pick up your sphere but its just a hallucination",
            'your sphere lands on "WAKE UP"',
            "your sphere is in a superposition of having landed on 0 and not landed",
            "your sphere lands on pi (get it?)",
            "your sphere fell into sulfuric acid and dissolved",
            "your sphere used slightly a wrong pi and therefore is just barely not a sphere",
            "your sphere is too fast to be seen",
            "your sphere's landing is delayed because of poor visibility at the airport",
            "your sphere turns into a tesseract",
            "your sphere opens a macdonalds franchise",
            "your sphere lands in crippling debt",
            "your sphere lands in court",
            "your sphere lands in prison",
            "your sphere has been sentenced to lifetime slavery",
            "your sphere is a sphere trying its best to become a cube with no avail because of the discrimination of society",
            "your mom is a sphere",
            "everything in the world is sphere its a matter of perspective",
            "did you notice most emojis are spheres?",
            "why are you still here",
            "your sphere ran out of jokes",
            "your sphere finally peacefully lands on the table. you shed a (spherical) tear of happiness.",
        ]

        if user.sphere_easter_egg < len(family_guy_funny_moments):
            await message.response.send_message(family_guy_funny_moments[user.sphere_easter_egg], ephemeral=True)
            user.sphere_easter_egg += 1
            await user.save()

            if user.sphere_easter_egg == len(family_guy_funny_moments):
                await achemb(message, "sphere_ach", "followup")
        else:
            await message.response.send_message(random.choice(family_guy_funny_moments), ephemeral=True)

        return

    # loosely based on this wikipedia article
    # https://en.wikipedia.org/wiki/Dice
    dice_names = {
        1: '"dice"',
        2: "coin",
        4: "tetrahedron",
        5: "triangular prism",
        6: "cube",
        7: "pentagonal prism",
        8: "octahedron",
        9: "hexagonal prism",
        10: "pentagonal trapezohedron",
        12: "dodecahedron",
        14: "heptagonal trapezohedron",
        16: "octagonal bipyramid",
        18: "rounded rhombicuboctahedron",
        20: "icosahedron",
        24: "triakis octahedron",
        30: "rhombic triacontahedron",
        34: "heptadecagonal trapezohedron",
        48: "disdyakis dodecahedron",
        50: "icosipentagonal trapezohedron",
        60: "deltoidal hexecontahedron",
        100: "zocchihedron",
        120: "disdyakis triacontahedron",
    }

    if sides in dice_names.keys():
        dice = dice_names[sides]
    else:
        dice = f"d{sides}"

    if sides == 2:
        coinflipresult = random.randint(1, 2)
        if coinflipresult == 2:
            side = "tails"
        else:
            side = "heads"
        await message.response.send_message(f"🪙 your coin lands on **{side}** ({coinflipresult})")
    else:
        await message.response.send_message(f"🎲 your {dice} lands on **{random.randint(1, sides)}**")
    await progress(message, user, "roll")


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
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, user, "rate")


@bot.tree.command(name="8ball", description="ask the magic catball")
@discord.app_commands.describe(question="your question to the catball")
async def eightball(message: discord.Interaction, question: str):
    if len(question) > 300:
        await message.response.send_message("thats kinda long", ephemeral=True)
        return

    catball_responses = [
        # positive
        "it is certain",
        "it is decidedly so",
        "without a doubt",
        "yes definitely",
        "you may rely on it",
        "as i see it, yes",
        "most likely",
        "outlook good",
        "yes",
        "signs point to yes",
        # negative
        "dont count on it",
        "my reply is no",
        "my sources say no",
        "outlook not so good",
        "very doubtful",
        "most likely not",
        "unlikely",
        "no definitely",
        "no",
        "signs point to no",
        # neutral
        "reply hazy, try again",
        "ask again later",
        "better not tell you now",
        "cannot predict now",
        "concetrate and ask again",
    ]

    await message.response.send_message(f"{question}\n:8ball: **{random.choice(catball_responses)}**")
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, user, "catball")
    await achemb(message, "balling", "followup")


@bot.tree.command(description="the most engaging boring game")
async def pig(message: discord.Interaction):
    score = 0

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    async def roll(interaction: discord.Interaction):
        nonlocal score
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        await interaction.response.defer()

        if score == 0:
            # dont roll 1 on first roll
            roll_result = random.randint(2, 6)
        else:
            roll_result = random.randint(1, 6)

        if roll_result == 1:
            # gg
            last_score = score
            score = 0
            view = View(timeout=3600)
            button = Button(label="Play Again", emoji="🎲", style=ButtonStyle.blurple)
            button.callback = roll
            view.add_item(button)
            await interaction.edit_original_response(
                content=f"*Oops!* You rolled a **1** and lost your {last_score} score...\nFinal score: 0\nBetter luck next time!", view=view
            )
        else:
            score += roll_result
            view = View(timeout=3600)
            button = Button(label="Roll", emoji="🎲", style=ButtonStyle.blurple)
            button.callback = roll
            button2 = Button(label="Save & Finish")
            button2.callback = finish
            view.add_item(button)
            view.add_item(button2)
            await interaction.edit_original_response(content=f"🎲 +{roll_result}\nCurrent score: {score:,}", view=view)

    async def finish(interaction: discord.Interaction):
        nonlocal score
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        await interaction.response.defer()

        await profile.refresh_from_db()

        if score > profile.best_pig_score:
            profile.best_pig_score = score
            await profile.save()

        if score >= 20:
            await progress(message, profile, "pig")
        if score >= 50:
            await achemb(interaction, "pig50", "followup")
        if score >= 100:
            await achemb(interaction, "pig100", "followup")

        last_score = score
        score = 0
        view = View(timeout=3600)
        button = Button(label="Play Again", emoji="🎲", style=ButtonStyle.blurple)
        button.callback = roll
        view.add_item(button)
        await interaction.edit_original_response(content=f"*Congrats!*\nYou finished with {last_score} score!", view=view)

    view = View(timeout=3600)
    button = Button(label="Play!", emoji="🎲", style=ButtonStyle.blurple)
    button.callback = roll
    view.add_item(button)
    await message.response.send_message(
        f"🎲 Pig is a simple dice game. You repeatedly roll a die. The number it lands on gets added to your score, then you can either roll the die again, or finish and save your current score. However, if you roll a 1, you lose and your score gets voided.\n\nYour current best score is **{profile.best_pig_score:,}**.",
        view=view,
    )


@bot.tree.command(description="get a reminder in the future (+- 5 minutes)")
@discord.app_commands.describe(
    days="in how many days",
    hours="in how many hours",
    minutes="in how many minutes (+- 5 minutes)",
    text="what to remind",
)
async def remind(
    message: discord.Interaction,
    days: Optional[int],
    hours: Optional[int],
    minutes: Optional[int],
    text: Optional[str],
):
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
    await message.response.send_message(f"🔔 ok, <t:{goal_time}:R> (+- 5 min) ill remind you of:\n{text}")
    msg = await message.original_response()
    message_link = msg.jump_url
    text += f"\n\n*This is a [reminder](<{message_link}>) you set.*"
    await Reminder.create(user_id=message.user.id, text=text, time=goal_time)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    profile.reminders_set += 1
    await profile.save()
    await achemb(message, "reminder", "followup")  # the ai autocomplete thing suggested this and its actually a cool ach
    await progress(message, profile, "reminder")  # the ai autocomplete thing also suggested this though profile wasnt defined


@bot.tree.command(name="random", description="Get a random cat")
async def random_cat(message: discord.Interaction):
    await message.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "https://api.thecatapi.com/v1/images/search", headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"}
            ) as response:
                data = await response.json()
                await message.followup.send(data[0]["url"])
                await achemb(message, "randomizer", "followup")
        except Exception:
            await message.followup.send("no cats :(")


if config.WORDNIK_API_KEY:

    @bot.tree.command(description="define a word")
    async def define(message: discord.Interaction, word: str):
        word = word.lower()
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"https://api.wordnik.com/v4/word.json/{word}/definitions?api_key={config.WORDNIK_API_KEY}&useCanonical=true&includeTags=false&includeRelated=false&limit=69",
                    headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"},
                ) as response:
                    data = await response.json()

                    # lazily filter some things
                    text = (await response.text()).lower()

                    # sometimes the api returns results without definitions, so we search for the first one which has a definition
                    for i in data:
                        if "text" in i.keys():
                            clean_data = re.sub(re.compile("<.*?>"), "", i["text"])
                            await message.response.send_message(
                                f"__{word}__\n{clean_data}\n-# [{i['attributionText']}](<{i['attributionUrl']}>) Powered by [Wordnik](<{i['wordnikUrl']}>)",
                                ephemeral=any([test in text for test in ["vulgar", "slur", "offensive", "profane", "insult", "abusive", "derogatory"]]),
                            )
                            await achemb(message, "define", "followup")
                            return

                    raise Exception
            except Exception:
                await message.response.send_message("no definition found", ephemeral=True)


@bot.tree.command(name="fact", description="get a random cat fact")
async def cat_fact(message: discord.Interaction):
    facts = [
        "you love cats",
        f"cat bot is in {len(bot.guilds):,} servers",
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


async def bounty(message, user, cattype):
    if user.hibernation:
        return
    complete = 0
    completed = 0
    title = []
    colored = 0
    for i in range(user.bounties):
        if i == 0:
            id = user.bounty_id_one
            progress = user.bounty_progress_one
            total = user.bounty_total_one
            type = user.bounty_type_one
        if i == 1:
            id = user.bounty_id_two
            progress = user.bounty_progress_two
            total = user.bounty_total_two
            type = user.bounty_type_two
        if i == 2:
            id = user.bounty_id_three
            progress = user.bounty_progress_three
            total = user.bounty_total_three
            type = user.bounty_type_three
        if progress < total:
            if id == 0:
                progress += 1
                if progress == total:
                    complete += 1
                    title.append(f"Catch {total} cats")
            if id == 1:
                if cattype == type:
                    progress += 1
                    if progress == total:
                        complete += 1
                        title.append(f"Catch {total} {type} cats")
            if id == 2:
                if cattypes.index(cattype) >= cattypes.index(type):
                    progress += 1
                    if progress == total:
                        complete += 1
                        title.append(f"Catch {total} {type} or rarer cats")
        if i == 0:
            user.bounty_progress_one = progress
            if progress == total:
                completed += 1
        if i == 1:
            user.bounty_progress_two = progress
            if progress == total:
                completed += 1
        if i == 2:
            user.bounty_progress_three = progress
            if progress == total:
                completed += 1
        colored += (progress / total) * 10 / user.bounties
        await user.save()
    if catnip_list["levels"][user.catnip_level]["bonus"]:
        bonus_title = ""
        if user.bounty_progress_bonus < user.bounty_total_bonus:
            if user.bounty_id_bonus == 0:
                user.bounty_progress_bonus += 1
                bonus_title = f"Catch {user.bounty_total_bonus} cats"
            elif user.bounty_id_bonus == 1:
                if cattype == user.bounty_type_bonus:
                    user.bounty_progress_bonus += 1
                bonus_title = f"Catch {user.bounty_total_bonus} {cattype} cats"
            else:
                if cattypes.index(cattype) >= cattypes.index(user.bounty_type_bonus):
                    user.bounty_progress_bonus += 1
                bonus_title = f"Catch {user.bounty_total_bonus} {user.bounty_type_bonus} or rarer cats"
            if user.bounty_progress_bonus == user.bounty_total_bonus:
                description = "Bonus Bounty Complete!\nGo to `/catnip` to reroll a perk!"
                embed = discord.Embed(title=f"✅ {bonus_title}", color=Colors.green, description=description).set_author(
                    name="Mafia Level " + str(user.catnip_level)
                )
                await message.channel.send(f"<@{user.user_id}>", embed=embed)
                user.reroll = False
                user.reroll_level = 0
            await user.save()
    for i in range(complete):
        logging.debug("Completed bounties %d", completed)
        level = user.catnip_level
        progress_line = f"\n{level} " + get_emoji("staring_square") * int(colored) + "⬛" * int(10 - colored) + f" {level + 1}"
        if completed == user.bounties:
            description = f"{progress_line}\nAll Bounties Complete!\nGo to `/catnip` to pay up and pick a perk!"
        else:
            description = f"{progress_line}\n{completed}/{user.bounties} Bounties Complete"
        embed = discord.Embed(title=f"✅ {title[i]}", color=Colors.green, description=description).set_author(name="Mafia Level " + str(level))
        user.bounties_complete += 1
        if user.bounties_complete >= 5:
            await achemb(message, "bounty_novice", "followup")
        if user.bounties_complete >= 19:  # we do a little trolling (???)
            await achemb(message, "bounty_hunter", "followup")
        if user.bounties_complete >= 100:
            await achemb(message, "bounty_lord", "followup")
        await message.channel.send(f"<@{user.user_id}>", embed=embed)
        await user.save()


async def set_mafia_offer(level, user):
    if user.catnip_level == 0:
        user.catnip_amount = 0
        return
    level_data = catnip_list["levels"][level]
    vt = level_data["cost"]
    cattype = "Fine"
    for _ in range(100):
        cattype = random.choice(cattypes)
        value = sum(type_dict.values()) / type_dict[cattype]
        if value <= vt:
            break
    amount = max(1, round(vt / value))
    user.catnip_price = cattype
    user.catnip_amount = amount
    await user.save()


async def set_bounties(level, user):
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

    user.bounty_id_one = bounties[0]["id"] if bounties else None
    user.bounty_id_two = bounties[1]["id"] if len(bounties) > 1 else None
    user.bounty_id_three = bounties[2]["id"] if len(bounties) > 2 else None

    user.bounty_type_one = bounties[0]["cat_type"] if bounties else None
    user.bounty_type_two = bounties[1]["cat_type"] if len(bounties) > 1 else None
    user.bounty_type_three = bounties[2]["cat_type"] if len(bounties) > 2 else None

    user.bounty_total_one = bounties[0]["amount"] if bounties else 1
    user.bounty_total_two = bounties[1]["amount"] if len(bounties) > 1 else 1
    user.bounty_total_three = bounties[2]["amount"] if len(bounties) > 2 else 1

    user.bounty_progress_one = bounties[0]["progress"] if bounties else 0
    user.bounty_progress_two = bounties[1]["progress"] if len(bounties) > 1 else 0
    user.bounty_progress_three = bounties[2]["progress"] if len(bounties) > 2 else 0

    await user.save()


async def get_bounties(level):
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

                prob = sum(type_dict[t] for t in eligible_types) / sum(type_dict.values())
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

            bounties.append({"id": 2, "progress": 0, "cat_type": rarity, "amount": amount, "desc": f"Catch {amount} cats of {rarity} rarity and above"})
        elif bounty_type == "any":
            if any(b["id"] == 0 for b in bounties):
                continue

            amount = max(1, round(avg_cats_needed * variation / 2))

            if amount > num_max:
                continue

            bounties.append({"id": 0, "progress": 0, "cat_type": "", "amount": amount, "desc": f"Catch {amount} cats of any kind"})
        else:
            # pick a specific cat type not already used
            available_types = [cat for cat in cattypes if cat not in used_types]
            if not available_types:
                continue

            available_types1 = available_types.copy()
            for i in available_types:
                cat_type = random.choices(available_types1)[0]
                prob = type_dict[cat_type] / sum(type_dict.values())
                base_amount = avg_cats_needed * prob
                available_types1.remove(cat_type)
                if base_amount > 0.8:
                    break

            amount = max(1, round(base_amount * variation))

            if amount > num_max:
                continue

            used_types.add(cat_type)
            bounties.append(
                {
                    "id": 1,
                    "progress": 0,
                    "cat_type": cat_type,
                    "amount": amount,
                    "desc": f"Catch {amount} {get_emoji(cat_type.lower() + 'cat')} cat{'s' if amount > 1 else ''}",
                }
            )

    return bounties


async def get_perks(level, user):
    level_data = catnip_list["levels"][level]
    rarities = [r for r in level_data["weights"].keys()]
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


async def level_down(user, message, ephemeral=False):
    if user.catnip_level == 0:
        return

    user.catnip_level -= 1
    user.catnip_active = 0

    user.hibernation = True

    for number in ["one", "two", "three"]:
        user[f"bounty_id_{number}"] = 0
        user[f"bounty_type_{number}"] = ""
        user[f"bounty_total_{number}"] = 1
        user[f"bounty_progress_{number}"] = 0

    user.catnip_total_cats = 0

    user.bounty_active = False
    user.first_quote_seen = False

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

    logging.debug("Levelled down to %d", user.catnip_level)

    if ephemeral:
        return embed

    await message.channel.send(f"<@{user.user_id}>", embed=embed)


async def mafia_cutscene(interaction: discord.Interaction, user):
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
        await interaction.response.defer()
        await interaction.edit_original_response(content=text4, view=None)
        user.thanksforplaying = False
        user.cutscene = 1
        await user.save()
        await achemb(interaction, "thanksforplaying", "followup")

    async def button2a_callback(interaction: discord.Interaction):
        myview3 = View(timeout=VIEW_TIMEOUT)
        button3 = Button(label="Next", style=ButtonStyle.blurple)
        button3.callback = button3_callback
        myview3.add_item(button3)
        await interaction.response.defer()
        await interaction.edit_original_response(content=text3a, view=myview3)

    async def button2b_callback(interaction: discord.Interaction):
        myview3 = View(timeout=VIEW_TIMEOUT)
        button3 = Button(label="Next", style=ButtonStyle.blurple)
        button3.callback = button3_callback
        myview3.add_item(button3)
        await interaction.response.defer()
        await interaction.edit_original_response(content=text3b, view=myview3)

    async def button1_callback(interaction: discord.Interaction):
        myview2 = View(timeout=VIEW_TIMEOUT)
        button2a = Button(label="Left", style=ButtonStyle.red)
        button2b = Button(label="Right", style=ButtonStyle.green)
        button2a.callback = button2a_callback
        button2b.callback = button2b_callback
        myview2.add_item(button2a)
        myview2.add_item(button2b)
        await interaction.response.defer()
        await interaction.edit_original_response(content=text2, view=myview2)

    user.thanksforplaying = True
    await user.save()

    myview1 = View(timeout=VIEW_TIMEOUT)
    button1 = Button(label="RUN!", style=ButtonStyle.blurple)
    button1.callback = button1_callback
    myview1.add_item(button1)
    await interaction.followup.send(content=text1, view=myview1, ephemeral=True)


async def mafia_cutscene2(interaction: discord.Interaction, user):
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
        await interaction.response.defer()
        await interaction.edit_original_response(content=text4a, view=None)
        user.mafia_win = False
        user.cutscene = 2
        await user.save()
        await achemb(interaction, "mafia_win", "followup")

    async def button3b_callback(interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(content=text4b, view=None)

    async def button2_callback(interaction: discord.Interaction):
        myview3 = View(timeout=VIEW_TIMEOUT)
        button3a = Button(label="Stay", style=ButtonStyle.green)
        button3b = Button(label="Continue", style=ButtonStyle.red, disabled=True)
        button3a.callback = button3a_callback
        button3b.callback = button3b_callback
        myview3.add_item(button3a)
        myview3.add_item(button3b)
        await interaction.response.defer()
        await interaction.edit_original_response(content=text3, view=myview3)

    async def button1_callback(interaction: discord.Interaction):
        myview2 = View(timeout=VIEW_TIMEOUT)
        button2 = Button(label="Next", style=ButtonStyle.blurple)
        button2.callback = button2_callback
        myview2.add_item(button2)
        await interaction.response.defer()
        await interaction.edit_original_response(content=text2, view=myview2)

    user.mafia_win = True
    await user.save()

    myview1 = View(timeout=VIEW_TIMEOUT)
    button1 = Button(label="'uhhhh'", style=ButtonStyle.blurple)
    button1.callback = button1_callback
    myview1.add_item(button1)
    await interaction.followup.send(content=text1, view=myview1, ephemeral=True)


@bot.tree.command(description="..?")
async def catnip(message: discord.Interaction):
    await message.response.defer(ephemeral=True)
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    if not user.dark_market_active:
        await message.followup.send("You don't have access to the catnip yet. Catch more cats to unlock it!")
        return

    if user.catnip_active < time.time() and not user.hibernation and user.catnip_level > 0:
        embed = await level_down(user, message, True)
        await message.followup.send(f"<@{user.user_id}>", embed=embed, ephemeral=True)

    if user.catnip_amount == 0:
        await set_mafia_offer(user.catnip_level, user)

    if user.bounties == 0:
        await set_bounties(user.catnip_level, user)

    await achemb(message, "dark_market", "followup")

    if user.cutscene >= 1:
        await achemb(message, "thanksforplaying", "followup")
    if user.cutscene == 2:
        await achemb(message, "mafia_win", "followup")

    if len(user.perks) + 1 < user.catnip_level:
        user.perk_selected = False
        await user.save()

    if len(user.perks) + 1 > user.catnip_level:
        user.perks = user.perks[:-1]
        await user.save()

    level = user.catnip_level
    cat_type = user.catnip_price
    amount = user.catnip_amount

    async def pay_catnip(interaction):
        nonlocal user, cat_type, amount
        await user.refresh_from_db()
        if not interaction.response.is_done():
            await interaction.response.defer()
        if level != user.catnip_level:
            await interaction.followup.send("nice try", ephemeral=True)
            return
        for i in range(user.bounties):
            if (
                (i == 0 and user.bounty_progress_one < user.bounty_total_one)
                or (i == 1 and user.bounty_progress_two < user.bounty_total_two)
                or (i == 2 and user.bounty_progress_three < user.bounty_total_three)
            ):
                await interaction.followup.send("You haven't completed your bounties yet!", ephemeral=True)
                return
        if user.catnip_price:
            if user[f"cat_{user.catnip_price}"] < user.catnip_amount:
                need_more = user.catnip_amount - user[f"cat_{user.catnip_price}"]
                await interaction.followup.send(f"You don't have enough cats to pay up!\nYou need {need_more} more {user.catnip_price} cats.", ephemeral=True)
                return
            user[f"cat_{user.catnip_price}"] -= user.catnip_amount
        if not user.perk_selected:
            await interaction.followup.send("You haven't selected a perk from your previous level yet!", ephemeral=True)
            return

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
        user.catnip_total_cats = 0
        user.first_quote_seen = False
        user.reroll = True

        if user.catnip_level > user.highest_catnip_level:
            user.highest_catnip_level = user.catnip_level

        await user.save()
        await set_bounties(user.catnip_level, user)
        await set_mafia_offer(user.catnip_level, user)

        logging.debug("Levelled up to %d", user.catnip_level)

        if user.catnip_level == 8 and user.cutscene == 0:
            await mafia_cutscene(interaction, user)
        elif user.catnip_level == 10 and not trigger_cutscene:
            text = """The point of catnip IS NOT TO KEEP LEVELLING UP FOREVER.
You are meant to go up and down levels.
You get absolutely no benefit from completing level 10.
You can stop. That's okay. Seriously.
"""
            await interaction.followup.send(content=text, ephemeral=True)
        elif trigger_cutscene and user.cutscene <= 1:
            await mafia_cutscene2(interaction, user)
        elif user.catnip_level > 1:
            await perk_screen(interaction)
        else:
            await interaction.followup.send("Catnip started!", ephemeral=True)
            await main_message.edit(view=await gen_main())

    async def reroll(interaction):
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
            perk_rarity = int(perk.split("_")[0])
            perk_data = perks[int(perk.split("_")[1]) - 1]
            effect = perk_data["values"][int(perk.split("_")[0])]
            desc = (
                perk_data.get("desc", "")
                .replace("percent", f"{effect:,}")
                .replace("triple_none", f"{effect / 2:g}")
                .replace("timer_add_streak", f"{global_user.vote_streak:,}")
            )
            full_desc += f"{rarity_colors[perk_rarity]} {perk_data.get('name', '')} ({rarities[perk_rarity]})\n{desc}\n\n"
            emojied_options[index + 1] = (f"{perk_data.get('name', '')} ({rarities[perk_rarity]})", rarity_colors[perk_rarity], desc.replace("**", ""))

        myview = LayoutView(timeout=VIEW_TIMEOUT)
        options = [Option(label=f"Lv{k}: {t}", emoji=e, description=d, value=str(k)) for k, (t, e, d) in emojied_options.items()]
        perk_select = Select(
            "rr_type",
            placeholder="Select a perk to reroll",
            opts=options,
            on_select=lambda interaction, level: perk_screen(interaction, int(level), True),
        )
        perk_embed = Container("# Your Perks", full_desc)
        myview.add_item(perk_embed)
        action_row = ActionRow(perk_select)
        myview.add_item(action_row)
        await main_message.edit(view=myview)

    async def view_perks(interaction):
        global_user = await User.get_or_create(user_id=interaction.user.id)
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
        await user.refresh_from_db()
        perks = catnip_list["perks"]
        rarities = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
        rarity_colors = [get_emoji("common"), get_emoji("uncommon"), get_emoji("rare"), get_emoji("epic"), get_emoji("legendary")]
        user_perks = user.perks
        full_desc = ""

        for perk in user_perks:
            perk_rarity = int(perk.split("_")[0])
            perk_data = perks[int(perk.split("_")[1]) - 1]
            effect = perk_data["values"][int(perk.split("_")[0])]
            desc = (
                perk_data.get("desc", "")
                .replace("percent", f"{effect:,}")
                .replace("triple_none", f"{effect / 2:g}")
                .replace("timer_add_streak", f"{global_user.vote_streak:,}")
            )
            full_desc += f"{rarity_colors[perk_rarity]} {perk_data.get('name', '')} ({rarities[perk_rarity]})\n{desc}\n\n"

        if not user_perks:
            full_desc = "You have no perks!"
        myview = LayoutView(timeout=VIEW_TIMEOUT)
        perk_embed = Container("# Your Perks", full_desc)
        myview.add_item(perk_embed)
        await interaction.response.send_message(view=myview, ephemeral=True)

    async def perk_screen(interaction, level=0, reroll=False):
        if not interaction.response.is_done():
            await interaction.response.defer()
        global_user = await User.get_or_create(user_id=interaction.user.id)
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)

        async def select_perk(interaction):
            await user.refresh_from_db()
            await interaction.response.defer()

            if user.perk_selected and not reroll:
                await interaction.followup.send("You have already selected a perk.", ephemeral=True)
                return
            if reroll and user.reroll:
                await interaction.followup.send("your die rerolls through the floor", ephemeral=True)
                return
            if reroll and user.reroll_level and user.reroll_level != level:
                await interaction.followup.send(f"you already chose to reroll level {user.reroll_level}", ephemeral=True)
                return

            h = list(user.perks) if user.perks else []
            if reroll:
                # We use level-1 because level is 1-based (Lv1, Lv2, etc) defined in the UI
                if 0 <= level - 1 < len(h):
                    h[level - 1] = interaction.data["custom_id"]
                else:
                    await interaction.followup.send(f"Failed to reroll! Perk slot {level} not found. (Count: {len(h)})", ephemeral=True)
                    return
                # Mark reroll as consumed
                user.reroll = True
            else:
                user.perk_selected = True
                h.append(interaction.data["custom_id"])
            user.perks = h[:]  # black magic

            user.perk1 = ""
            user.perk2 = ""
            user.perk3 = ""
            await user.save()

            logging.debug("Selected perk on level %d", user.catnip_level)

            await main_message.edit(view=await gen_main())

        if user.perk_selected and not reroll:
            await interaction.followup.send("You have already selected a perk.", ephemeral=True)
            return
        if reroll and user.reroll:
            await interaction.followup.send("your die rerolls through the floor", ephemeral=True)
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
        await main_message.edit(view=myview)

    async def help_screen(interaction):
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

    async def begin_bounties(interaction, override=False):
        if not override:
            await interaction.response.defer()

        if not user.hibernation:
            await interaction.followup.send("nice try", ephemeral=True)
            return

        async def callbacks_are_so_fun(interaction2):
            nonlocal interaction
            await interaction2.response.defer()
            await begin_bounties(interaction, override=True)
            await interaction2.delete_original_response()

        if user.catnip_active > time.time() and user.catnip_level >= 2 and not override:
            myview = View(timeout=VIEW_TIMEOUT)
            button = Button(label="Begin Anyway", style=ButtonStyle.red)
            button.callback = callbacks_are_so_fun
            myview.add_item(button)
            await interaction.followup.send(
                f"Your catnip expires <t:{user.catnip_active}:R>.\nAre you sure you want to start your bounties now?\nThis will remove the remaining catnip time you have.",
                view=myview,
                ephemeral=True,
            )
            return

        level_data = catnip_list["levels"][user.catnip_level]
        duration = level_data["duration"]
        user.hibernation = False
        duration_bonus = 0
        perks = catnip_list["perks"]

        if user.perks:
            for perk in user.perks:
                perk_data = perks[int(perk.split("_")[1]) - 1]
                if perk_data["id"] == "timer_add_streak":
                    global_user = await User.get_or_create(user_id=interaction.user.id)
                    duration_bonus = 0
                    for i in range(int(global_user.vote_streak / 100)):
                        i = i + 1
                        duration_bonus += 6000 / i
                    duration_bonus += 60 * (global_user.vote_streak % 100) / (int(global_user.vote_streak / 100) + 1)

        user.catnip_active = int(time.time()) + 3600 * duration + duration_bonus
        await user.save()

        logging.debug("Started bounties on level %d", user.catnip_level)

        await main_message.edit(view=await gen_main())

    async def gen_main():
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
        bonus_complete = False
        name = ""

        desc = "\n"
        if user.hibernation:
            desc += "\nThe timer for leveling up will **not start** until you begin your bounties.\n"

        if user.catnip_level > 0 and user.catnip_level < 11:
            colored = 0

            def format_bounty(bounty_numstr, single=False):
                nonlocal desc, all_complete, colored, bonus_complete
                bounty_id = user[f"bounty_id_{bounty_numstr}"]
                bounty_type = user[f"bounty_type_{bounty_numstr}"]
                bounty_total = user[f"bounty_total_{bounty_numstr}"]
                bounty_progress = user[f"bounty_progress_{bounty_numstr}"]

                desc += "\n- "
                if bounty_progress == bounty_total:
                    desc += "✅ "
                    if bounty_numstr == "bonus":
                        bonus_complete = True
                elif bounty_numstr != "bonus":
                    all_complete = False

                if bounty_progress == 0:
                    desc += f"{bounty_data[bounty_id]['desc']}".replace("X", str(bounty_total))
                else:
                    desc += f"{bounty_data[bounty_id]['desc']}".replace("X", str(bounty_total - bounty_progress) + " more")

                if bounty_total - bounty_progress == 1:
                    desc = desc.replace("cats", "cat")

                desc = desc.replace("type", f"{get_emoji(bounty_type.lower() + 'cat')} {bounty_type}")
                if bounty_numstr != "bonus":
                    colored += (bounty_progress / bounty_total) * 10 / user.bounties

            if not user.hibernation:
                if user.bounties == 1:
                    desc += "\n**__Bounty:__**"
                else:
                    desc += "\n**__Bounties:__**"
                for i in range(user.bounties):
                    if i == 0:
                        format_bounty("one")
                    if i == 1:
                        format_bounty("two")
                    if i == 2:
                        format_bounty("three")
                if bonus:
                    desc += "\n**__Bonus Bounty:__**"
                    format_bounty("bonus")

                colored = int(colored)
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

            desc += f"\n\n**Level {level}** - {change}"
            desc += f"\n{level} " + get_emoji("staring_square") * colored + "⬛" * (10 - colored) + f" {level + 1}"
        if not level == 0 and not user.hibernation:
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
        filename = f"images/mafia/{name}.png"

        if name == "Whiskers" and user.catnip_level == 10:
            filename = "images/mafia/WhiskersII.png"
        if name == "Jeremy" and random.randint(1, 100) == 69:
            filename = "images/mafia/sus.png"

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

            async def reroll_warning(interaction2):
                async def continue_pay_catnip(interaction3):
                    await interaction3.response.defer()
                    await interaction3.delete_original_response()
                    await pay_catnip(interaction2)

                view2 = View(timeout=VIEW_TIMEOUT)
                button = Button(label="Yes")
                button.callback = continue_pay_catnip
                view2.add_item(button)
                await interaction2.response.send_message(
                    "Warning: You will lose your reroll if you level up now. Use it first.\nStill continue?", view=view2, ephemeral=True
                )

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

    main_message = await message.followup.send(view=await gen_main(), ephemeral=True, wait=True)


@bot.tree.command(description="View your achievements")
async def achievements(message: discord.Interaction):
    # this is very close to /inv's ach counter
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    if user.funny >= 50:
        await achemb(message, "its_not_working", "followup")

    unlocked = 0
    minus_achs = 0
    minus_achs_count = 0
    for k in ach_names:
        is_ach_hidden = ach_list[k]["category"] == "Hidden"
        if is_ach_hidden:
            minus_achs_count += 1
        if user[k]:
            if is_ach_hidden:
                minus_achs += 1
            else:
                unlocked += 1
    total_achs = len(ach_list) - minus_achs_count
    minus_achs = "" if minus_achs == 0 else f" + {minus_achs}"

    hidden_counter = 0

    # this is a single page of the achievement list
    async def gen_new(category):
        nonlocal message, unlocked, total_achs, hidden_counter

        unlocked = 0
        minus_achs = 0
        minus_achs_count = 0

        for k in ach_names:
            is_ach_hidden = ach_list[k]["category"] == "Hidden"
            if is_ach_hidden:
                minus_achs_count += 1
            if user[k]:
                if is_ach_hidden:
                    minus_achs += 1
                else:
                    unlocked += 1

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
        if len(news_list) > len(global_user.news_state.strip()) or "0" in global_user.news_state.strip()[-4:]:
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
    def insane_view_generator(category):
        myview = View(timeout=VIEW_TIMEOUT)
        buttons_list = []

        async def callback_hell(interaction):
            thing = interaction.data["custom_id"]
            await interaction.response.defer()
            try:
                await interaction.edit_original_response(embed=await gen_new(thing), view=insane_view_generator(thing))
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

        for num, i in enumerate(["Cat Hunt", "Commands", "Random", "Silly", "Hard", "Hidden"]):
            if category == i:
                buttons_list.append(Button(label=i, custom_id=i, style=ButtonStyle.green, row=num // 3))
            else:
                buttons_list.append(Button(label=i, custom_id=i, style=ButtonStyle.blurple, row=num // 3))
            buttons_list[-1].callback = callback_hell

        for j in buttons_list:
            myview.add_item(j)
        return myview

    await message.response.send_message(
        embed=await gen_new("Cat Hunt"),
        ephemeral=True,
        view=insane_view_generator("Cat Hunt"),
    )

    if unlocked >= 15:
        await achemb(message, "achiever", "followup")


@bot.tree.command(name="catch", description="Catch someone in 4k")
async def catch_tip(message: discord.Interaction):
    await message.response.send_message(
        f'Nope, that\'s the wrong way to do this.\nRight Click/Long Hold a message you want to catch > Select `Apps` in the popup > "{get_emoji("staring_cat")} catch"',
        ephemeral=True,
    )


async def catch(message: discord.Interaction, msg: discord.Message):
    if message.user.id in catchcooldown and catchcooldown[message.user.id] + 6 > time.time():
        await message.response.send_message("your phone is overheating bro chill", ephemeral=True)
        return
    await message.response.defer()

    event_loop = asyncio.get_event_loop()
    try:
        member = await message.guild.fetch_member(msg.author.id)
    except Exception:
        member = msg.author
    result = await event_loop.run_in_executor(None, msg2img.msg2img, msg, member)

    try:
        await message.followup.send("cought in 4k", file=result)
    except Exception:
        try:
            await message.followup.send("failed")
        except Exception:
            pass

    catchcooldown[message.user.id] = time.time()

    await achemb(message, "4k", "followup")

    if msg.author.id == bot.user.id and "cought in 4k" in msg.content:
        await achemb(message, "8k", "followup")

    try:
        is_cat = (await Channel.get_or_none(channel_id=message.channel.id)).cat
    except Exception:
        is_cat = False

    if int(is_cat) == int(msg.id):
        await achemb(message, "not_like_that", "followup")


@bot.tree.command(description="View the leaderboards")
@discord.app_commands.rename(leaderboard_type="type")
@discord.app_commands.describe(
    leaderboard_type="The leaderboard type to view!",
    cat_type="The cat type to view (only for the Cats leaderboard)",
    locked="Whether to remove page switch buttons to prevent tampering",
)
@discord.app_commands.autocomplete(cat_type=lb_type_autocomplete)
async def leaderboards(
    message: discord.Interaction,
    leaderboard_type: Optional[Literal["Cats", "Value", "Fast", "Slow", "Battlepass", "Cookies", "Pig", "Roulette Dollars", "Prisms"]],
    cat_type: Optional[str],
    locked: Optional[bool],
):
    if not leaderboard_type:
        leaderboard_type = "Cats"
    if not locked:
        locked = False
    if cat_type and cat_type not in cattypes + ["All"]:
        await message.response.send_message("invalid cattype", ephemeral=True)
        return

    # this fat function handles a single page
    async def lb_handler(interaction, type, do_edit=None, specific_cat="All"):
        if specific_cat is None:
            specific_cat = "All"

        nonlocal message
        if do_edit is None:
            do_edit = True
        await interaction.response.defer()

        messager = None
        interactor = None

        # leaderboard top amount
        show_amount = 15

        string = ""
        if type == "Cats":
            unit = "cats"

            if specific_cat != "All":
                result = await Profile.collect_limit(
                    ["user_id", f"cat_{specific_cat}"], f'guild_id = $1 AND "cat_{specific_cat}" > 0 ORDER BY "cat_{specific_cat}" DESC', message.guild.id
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
                for i in cattypes[::-1]:
                    non_zero_count = await Profile.collect_limit("user_id", f'guild_id = $1 AND "cat_{i}" > 0', message.guild.id)
                    if len(non_zero_count) != 0:
                        rarest = i
                        rarest_holder = non_zero_count
                        break

                if rarest and specific_cat != rarest:
                    catmoji = get_emoji(rarest.lower() + "cat")
                    rarest_holder = [f"<@{i.user_id}>" for i in rarest_holder]
                    joined = ", ".join(rarest_holder)
                    if len(rarest_holder) > 10:
                        joined = f"{len(rarest_holder)} people"
                    string = f"Rarest cat: {catmoji} ({joined}'s)\n\n"
        elif type == "Value":
            unit = "value"
            sums = []
            for cat_type in cattypes:
                if not cat_type:
                    continue
                weight = sum(type_dict.values()) / type_dict[cat_type]
                sums.append(f'({weight}) * "cat_{cat_type}"')
            total_sum_expr = RawSQL("(" + " + ".join(sums) + ") AS final_value")
            result = await Profile.collect_limit(["user_id", total_sum_expr], "guild_id = $1 ORDER BY final_value DESC", message.guild.id)
            final_value = "final_value"
        elif type == "Fast":
            unit = "sec"
            result = await Profile.collect_limit(["user_id", "time"], "guild_id = $1 AND time < 99999999999999 ORDER BY time ASC", message.guild.id)
            final_value = "time"
        elif type == "Slow":
            unit = "h"
            result = await Profile.collect_limit(["user_id", "timeslow"], "guild_id = $1 AND timeslow > 0 ORDER BY timeslow DESC", message.guild.id)
            final_value = "timeslow"
        elif type == "Battlepass":
            start_date = datetime.datetime(2024, 12, 1)
            current_date = datetime.datetime.utcnow() + datetime.timedelta(hours=4)
            full_months_passed = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
            bp_season = battle["seasons"][str(full_months_passed)]
            if current_date.day < start_date.day:
                full_months_passed -= 1
            result = await Profile.collect_limit(
                ["user_id", "battlepass", "progress"],
                "guild_id = $1 AND season = $2 AND (battlepass > 0 OR progress > 0) ORDER BY battlepass DESC, progress DESC",
                message.guild.id,
                full_months_passed,
            )
            final_value = "battlepass"
        elif type == "Cookies":
            unit = "cookies"
            result = await Profile.collect_limit(["user_id", "cookies"], "guild_id = $1 AND cookies > 0 ORDER BY cookies DESC", message.guild.id)
            string = "Cookie leaderboard updates every 5 min\n\n"
            final_value = "cookies"
        elif type == "Pig":
            unit = "score"
            result = await Profile.collect_limit(
                ["user_id", "best_pig_score"], "guild_id = $1 AND best_pig_score > 0 ORDER BY best_pig_score DESC", message.guild.id
            )
            final_value = "best_pig_score"
        elif type == "Roulette Dollars":
            unit = "cat dollars"
            result = await Profile.collect_limit(
                ["user_id", "roulette_balance"], "guild_id = $1 AND roulette_balance != 100 ORDER BY roulette_balance DESC", message.guild.id
            )
            final_value = "roulette_balance"
        elif type == "Prisms":
            unit = "prisms"
            result = await Prism.collect_limit(
                ["user_id", RawSQL("COUNT(*) as prism_count")],
                "guild_id = $1 GROUP BY user_id ORDER BY prism_count DESC",
                message.guild.id,
                add_primary_key=False,
            )
            final_value = "prism_count"
        else:
            # qhar
            raise ValueError("Invalid leaderboard type")

        # find the placement of the person who ran the command and optionally the person who pressed the button
        interactor_placement = 0
        messager_placement = 0
        for index, position in enumerate(result):
            if position["user_id"] == interaction.user.id:
                interactor_placement = index + 1
                interactor = position[final_value]
                if type == "Battlepass":
                    if position[final_value] >= len(bp_season):
                        lv_xp_req = 1500
                    else:
                        lv_xp_req = bp_season[int(position[final_value]) - 1]["xp"]
                    interactor_perc = math.floor((100 / lv_xp_req) * position["progress"])
            if interaction.user != message.user and position["user_id"] == message.user.id:
                messager_placement = index + 1
                messager = position[final_value]
                if type == "Battlepass":
                    if position[final_value] >= len(bp_season):
                        lv_xp_req = 1500
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
            interactor = round(interactor)
        elif interactor and type == "Fast" and interactor >= 99999999999999:
            interactor_placement = 0

        if messager and type != "Fast":
            if messager <= 0 and type != "Roulette Dollars":
                messager_placement = 0
            messager = round(messager)
        elif messager and type == "Fast" and messager >= 99999999999999:
            messager_placement = 0

        emoji = ""
        if type == "Cats" and specific_cat != "All":
            emoji = get_emoji(specific_cat.lower() + "cat")

        # the little place counter
        current = 1
        leader = False
        for i in result[:show_amount]:
            num = i[final_value]

            if type == "Battlepass":
                if i[final_value] >= len(bp_season):
                    lv_xp_req = 1500
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
                elif type in ["Cookies", "Cats", "Pig", "Prisms"] and num <= 0:
                    break
                elif type == "Roulette Dollars" and num == 100:
                    break
                string = string + f"{current}. {emoji} **{num:,}** {unit}: <@{i['user_id']}>\n"

            if message.user.id == i["user_id"] and current <= 5:
                leader = True
            current += 1

        # add the messager and interactor
        if messager_placement > show_amount or interactor_placement > show_amount:
            string = string + "...\n"

            # setting up names
            include_interactor = interactor_placement > show_amount and str(interaction.user.id) not in string
            include_messager = messager_placement > show_amount and str(message.user.id) not in string
            interactor_line = ""
            messager_line = ""
            if include_interactor:
                if type == "Battlepass":
                    interactor_line = f"{interactor_placement}\\. Level **{interactor}** *({interactor_perc}%)*: {interaction.user.mention}\n"
                else:
                    interactor_line = f"{interactor_placement}\\. {emoji} **{interactor:,}** {unit}: {interaction.user.mention}\n"
            if include_messager:
                if type == "Battlepass":
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

        if len(news_list) > len(global_user.news_state.strip()) or "0" in global_user.news_state.strip()[-4:]:
            embedVar.set_author(name=f"{message.user} has unread news! /news")

        # handle funny buttons
        myview = View(timeout=VIEW_TIMEOUT)

        if type == "Cats":
            dd_opts = [Option(label="All", emoji=get_emoji("staring_cat"), value="All")]

            for i in await cats_in_server(message.guild.id):
                dd_opts.append(Option(label=i, emoji=get_emoji(i.lower() + "cat"), value=i))

            dropdown = Select(
                "cat_type_dd",
                placeholder="Select a cat type",
                opts=dd_opts,
                selected=specific_cat,
                on_select=lambda interaction, option: lb_handler(interaction, type, True, option),
                disabled=locked,
            )

        emojied_options = {
            "Cats": "🐈",
            "Value": "🧮",
            "Fast": "⏱️",
            "Slow": "💤",
            "Battlepass": "⬆️",
            "Cookies": "🍪",
            "Pig": "🎲",
            "Roulette Dollars": "💰",
            "Prisms": get_emoji("prism"),
        }
        options = [Option(label=k, emoji=v) for k, v in emojied_options.items()]
        lb_select = Select(
            "lb_type",
            placeholder=type,
            opts=options,
            on_select=lambda interaction, type: lb_handler(interaction, type, True),
        )

        if not locked:
            myview.add_item(lb_select)
            if type == "Cats":
                myview.add_item(dropdown)

        # just send if first time, otherwise edit existing
        try:
            if not do_edit:
                raise Exception
            await interaction.edit_original_response(embed=embedVar, view=myview)
        except Exception:
            await interaction.followup.send(embed=embedVar, view=myview)

        if leader:
            await achemb(message, "leader", "followup")

    await lb_handler(message, leaderboard_type, False, cat_type)


@bot.tree.command(description="(ADMIN) Give cats to people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="who", amount="how many (negatives to remove)", cat_type="what")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def givecat(message: discord.Interaction, person_id: discord.User, cat_type: str, amount: Optional[int]):
    if amount is None:
        amount = 1
    if cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    user[f"cat_{cat_type}"] += amount
    await user.save()
    await message.response.send_message(f"gave {person_id.mention} {amount:,} {cat_type} cats", allowed_mentions=discord.AllowedMentions(users=True))


@bot.tree.command(name="setup", description="(ADMIN) Setup cat in current channel")
@discord.app_commands.default_permissions(manage_guild=True)
async def setup_channel(message: discord.Interaction):
    try:
        if isinstance(message.channel, discord.Thread) and not message.channel.parent:
            parent = message.guild.get_channel(message.channel.parent_id) or await message.guild.fetch_channel(message.channel.parent_id)
            channel_permissions = parent.permissions_for(message.guild.me)
        else:
            channel_permissions = message.channel.permissions_for(message.guild.me)
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
        await message.response.send_message("this channel gives me bad vibes.")
        return

    await spawn_cat(str(message.channel.id))
    await message.response.send_message(f"ok, now i will also send cats in <#{message.channel.id}>")


@bot.tree.command(description="(ADMIN) Undo the setup")
@discord.app_commands.default_permissions(manage_guild=True)
async def forget(message: discord.Interaction):
    if channel := await Channel.get_or_none(channel_id=message.channel.id):
        await channel.delete()
        await message.response.send_message(f"ok, now i wont send cats in <#{message.channel.id}>")
    else:
        await message.response.send_message("your an idiot there is literally no cat setupped in this channel you stupid")


@bot.tree.command(description="LMAO TROLLED SO HARD :JOY:")
async def fake(message: discord.Interaction):
    if message.user.id in fakecooldown and fakecooldown[message.user.id] + 60 > time.time():
        await message.response.send_message("your phone is overheating bro chill", ephemeral=True)
        return
    file = discord.File("images/australian cat.png", filename="australian cat.png")
    icon = get_emoji("egirlcat")
    fakecooldown[message.user.id] = time.time()
    try:
        await message.response.send_message(
            str(icon) + ' eGirl cat hasn\'t appeared! Type "cat" to catch ratio!',
            file=file,
        )
    except Exception:
        await message.response.send_message("i dont have perms lmao here is the ach anyways", ephemeral=True)
        pass
    await achemb(message, "trolled", "ephemeral")


@bot.tree.command(description="(ADMIN) Force cats to appear")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(cat_type="select a cat type ok")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def forcespawn(message: discord.Interaction, cat_type: Optional[str]):
    if cat_type and cat_type not in cattypes:
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
    await spawn_cat(str(message.channel.id), cat_type, True)
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

    if not valid and ach_id.lower() in ach_titles.keys():
        ach_id = ach_titles[ach_id.lower()]
        valid = True

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
            .set_footer(text=f"for {person_id.name}")
        )
        await message.response.send_message(person_id.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
    else:
        await message.response.send_message("i cant find that achievement! try harder next time.", ephemeral=True)


@bot.tree.command(description="(ADMIN) Reset people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="who")
async def reset(message: discord.Interaction, person_id: discord.User):
    async def confirmed(interaction):
        if interaction.user.id == message.user.id:
            await interaction.response.defer()
            try:
                og = await interaction.original_response()
                profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
                profile.guild_id = og.id
                await profile.save()
                async for p in Prism.filter("guild_id = $1 AND user_id = $2", message.guild.id, person_id.id):
                    p.guild_id = og.id
                    await p.save()
                await interaction.edit_original_response(
                    content=f"Done! rip {person_id.mention}. f's in chat.\njoin our discord to rollback: <https://discord.gg/staring>", view=None
                )
            except Exception:
                await interaction.edit_original_response(
                    content="ummm? this person isnt even registered in cat bot wtf are you wiping?????",
                    view=None,
                )
        else:
            await do_funny(interaction)

    view = View(timeout=VIEW_TIMEOUT)
    button = Button(style=ButtonStyle.red, label="Confirm")
    button.callback = confirmed
    view.add_item(button)
    await message.response.send_message(f"Are you sure you want to reset {person_id.mention}?", view=view, allowed_mentions=discord.AllowedMentions(users=True))


@bot.tree.command(description="(HIGH ADMIN) [VERY DANGEROUS] Reset all Cat Bot data of this server")
@discord.app_commands.default_permissions(administrator=True)
async def nuke(message: discord.Interaction):
    warning_text = "⚠️ This will completely reset **all** Cat Bot progress of **everyone** in this server. Spawn channels and their settings *will not be affected*.\nPress the button 5 times to continue."
    counter = 5

    async def gen(counter):
        lines = [
            "",
            "I'm absolutely sure! (1)",
            "I understand! (2)",
            "You can't undo this! (3)",
            "This is dangerous! (4)",
            "Reset everything! (5)",
        ]
        view = View(timeout=VIEW_TIMEOUT)
        button = Button(label=lines[max(1, counter)], style=ButtonStyle.red)
        button.callback = count
        view.add_item(button)
        return view

    async def count(interaction: discord.Interaction):
        nonlocal message, counter
        if interaction.user.id == message.user.id:
            await interaction.response.defer()
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

                try:
                    await interaction.edit_original_response(
                        content="Done. If you want to roll this back, please contact us in our discord: <https://discord.gg/staring>.",
                        view=None,
                    )
                except Exception:
                    await interaction.followup.send("Done. If you want to roll this back, please contact us in our discord: <https://discord.gg/staring>.")
            else:
                view = await gen(counter)
                try:
                    await interaction.edit_original_response(content=warning_text, view=view)
                except Exception:
                    pass
        else:
            await do_funny(interaction)

    view = await gen(counter)
    await message.response.send_message(warning_text, view=view)


async def recieve_vote(request):
    if request.headers.get("authorization", "") != config.WEBHOOK_VERIFY:
        return web.Response(text="bad", status=403)
    request_json = await request.json()

    user = await User.get_or_create(user_id=int(request_json["user"]))
    if user.vote_time_topgg + 43100 > time.time():
        # top.gg is NOT realiable with their webhooks, but we politely pretend they are
        return web.Response(text="you fucking dumb idiot", status=200)

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

    user.reminder_vote = 1
    user.total_votes += 1
    freeze_note = ""
    if user.vote_time_topgg + extend_time * 3600 <= time.time():
        # streak end
        if user.streak_freezes < 1:
            if user.max_vote_streak < user.vote_streak:
                user.max_vote_streak = user.vote_streak
            user.vote_streak = 1
        else:
            # i initially wanted streak freezes to not increase up
            # but that could result in unexpected repeated milestone rewards
            user.vote_streak += 1

            user.streak_freezes -= 1
            freeze_note = "\n🧊 Streak Freeze Used!"
    else:
        user.vote_streak += 1
    user.vote_time_topgg = time.time()

    try:
        channeley = await fetch_dm_channel(user)

        if user.vote_streak == 1:
            streak_progress = "🟦⬛⬛⬛⬛⬛⬛⬛⬛⬛\n⬆️"
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

        await channeley.send(
            "\n".join(
                [
                    "Thanks for voting! To claim your rewards, run `/battlepass` in every server you want.",
                    f"You can vote again <t:{int(time.time()) + 43200}:R>.",
                    "",
                    f":fire: **Streak:** {user.vote_streak:,} (expires <t:{int(time.time()) + extend_time * 3600}:R>){freeze_note}",
                    f"{streak_progress}",
                ]
            )
        )

        logging.debug("User voted, streak %d", user.vote_streak)
    except Exception:
        # Ignore errors when DMing the user (e.g. if they have DMs closed)
        pass

    await user.save()

    return web.Response(text="ok", status=200)


async def check_supporter(request):
    if request.headers.get("authorization", "") != config.WEBHOOK_VERIFY:
        return web.Response(text="bad", status=403)
    request_json = await request.json()

    user = await User.get_or_create(user_id=int(request_json["user"]))
    return web.Response(text="1" if user.premium else "0", status=200)


# cat bot uses glitchtip (sentry alternative) for errors, here u can instead implement some other logic like dming the owner
async def on_error(*args, **kwargs):
    raise


# this is for stats, useless otherwise
async def on_interaction(ctx):
    if ctx.command:
        logging.debug("Command %s was used", ctx.command.name)


async def setup(bot2):
    global bot, RAIN_ID, vote_server

    for command in bot.tree.walk_commands():
        # copy all the commands
        command.guild_only = True
        bot2.tree.add_command(command)

    context_menu_command = discord.app_commands.ContextMenu(name="catch", callback=catch)
    context_menu_command.guild_only = True
    bot2.tree.add_command(context_menu_command)

    # copy all the events
    bot2.on_ready = on_ready
    bot2.on_guild_join = on_guild_join
    bot2.on_message = on_message
    bot2.on_connect = on_connect
    bot2.on_error = on_error
    bot2.on_interaction = on_interaction

    if config.WEBHOOK_VERIFY:
        app = web.Application()
        app.add_routes([web.post("/", recieve_vote), web.get("/supporter", check_supporter)])
        vote_server = web.AppRunner(app)
        await vote_server.setup()
        site = web.TCPSite(vote_server, "0.0.0.0", 8069)
        await site.start()

    # finally replace the fake bot with the real one
    bot = bot2

    config.SOFT_RESTART_TIME = time.time()

    app_commands = await bot.tree.sync()
    for i in app_commands:
        if i.name == "rain":
            RAIN_ID = i.id

    if bot.is_ready() and not on_ready_debounce:
        await on_ready()


async def teardown(bot):
    cookie_updates = []
    for cookie_id, cookies in temp_cookie_storage.items():
        p = await Profile.get_or_create(guild_id=cookie_id[0], user_id=cookie_id[1])
        p.cookies = cookies
        cookie_updates.append(p)

    if cookie_updates:
        await Profile.bulk_update(cookie_updates, "cookies")

    if config.WEBHOOK_VERIFY:
        await vote_server.cleanup()


# Reusable UI components
class Option:
    def __init__(self, label, emoji, description=None, value=None):
        self.label = label
        self.emoji = emoji
        self.value = value if value is not None else label
        self.description = description


class Select(discord.ui.Select):
    on_select = None

    def __init__(
        self,
        id: str,
        placeholder: str,
        opts: list[Option],
        selected: str = None,
        on_select: callable = None,
        disabled: bool = False,
    ):
        options = []
        if on_select is not None:
            self.on_select = on_select

        for opt in opts:
            options.append(discord.SelectOption(label=opt.label, description=opt.description, value=opt.value, emoji=opt.emoji, default=opt.value == selected))

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
            await self.on_select(interaction, self.values[0])


class Container(discord.ui.Container):
    def __init__(self, *children, **kwargs):
        if "accent_color" not in kwargs:
            kwargs["accent_color"] = Colors.brown

        new_children = []

        for child in children:
            if isinstance(child, str):
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
                if isinstance(child, Button) or isinstance(child, Thumbnail):
                    kwargs["accessory"] = child
                else:
                    new_children.append(child)

            super().__init__(*new_children, **kwargs)
        else:
            super().__init__(*children, **kwargs)
