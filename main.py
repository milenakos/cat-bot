import asyncio
import base64
import datetime
import io
import json
import logging
import os
import random
import re
import subprocess
import time
import traceback
from typing import Literal, Optional, Union

import aiohttp
import discord
import discord_emoji
import peewee
from aiohttp import web
from discord import ButtonStyle
from discord.ext import commands
from discord.ui import Button, View
from PIL import Image

import config
import msg2img
from database import Channel, Prism, Profile, Reminder, User, db

logging.basicConfig(level=logging.INFO)

# trigger warning, base64 encoded for your convinience
NONOWORDS = [base64.b64decode(i).decode('utf-8') for i in ["bmlja2E=", "bmlja2Vy", "bmlnYQ==", "bmlnZ2E=", "bmlnZ2Vy"]]

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
    "TheTrashCell": 50,
    "Legendary": 35,
    "Mythic": 25,
    "8bit": 20,
    "Corrupt": 15,
    "Professor": 10,
    "Divine": 8,
    "Real": 5,
    "Ultimate": 3,
    "eGirl": 2
}

# create a huge list where each cat type is multipled the needed amount of times
CAT_TYPES = []
for k, v in type_dict.items():
    CAT_TYPES.extend([k] * v)

# this list stores unique non-duplicate cattypes
cattypes = list(type_dict.keys())

allowedemojis = []
for i in type_dict.keys():
    allowedemojis.append(i.lower() + "cat")

prism_names = [
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliett", "Kilo", "Lima", "Mike", "November",
    "Oscar", "Papa", "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey", "X-ray", "Yankee"
]

vote_button_texts = [
    "You havent voted today!",
    "I know you havent voted ;)",
    "If vote cat will you friend :)",
    "Vote cat for president",
    "vote = 0.01% to escape basement",
    "vote vote vote vote vote",
    "mrrp mrrow go and vote now",
    "if you vote you'll be free (no)",
    "Like gambling? Vote!",
    "vote. btw, i have a pipebomb",
    "No votes? :megamind:",
    "Cat says you should vote",
    "vote = random cats. lets gamble?",
    "cat will be happy if you vote",
    "VOTE NOW!!!!!",
    "Vote on top.gg for free cats",
    "Vote for free cats",
    "No vote = no free cats :(",
    "0.04% to get egirl on voting",
    "I voted and got 1000000$",
    "I voted and found a gf",
    "lebron james forgot to vote",
    "vote if you like cats",
    "vote if cats > dogs",
    "you should vote for cat NOW!"
]

# laod the jsons
with open("config/aches.json", "r") as f:
    ach_list = json.load(f)

with open("config/battlepass.json", "r") as f:
    battle = json.load(f)

# convert achievement json to a few other things
ach_names = ach_list.keys()
ach_titles = {value["title"].lower(): key for (key, value) in ach_list.items()}

bot = commands.AutoShardedBot(command_prefix="this is a placebo bot which will be replaced when this will get loaded", intents=discord.Intents.default())

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
    "you're only making me angrier"
]

milenakoos = None

# store credits usernames to prevent excessive api calls
gen_credits = {}

# due to some stupid individuals spamming the hell out of reactions, we ratelimit them
# you can do 50 reactions before they stop, limit resets on global cat loop
reactions_ratelimit = {}

# sort of the same thing but for pointlaughs and per channel instead of peruser
pointlaugh_ratelimit = {}

# cooldowns for /fake cat /catch
catchcooldown = {}
fakecooldown = {}

# cat bot auto-claims in the channel user last ran /vote in
# this is a failsafe to store the fact they voted until they ran that atleast once
pending_votes = []

# prevent ratelimits
casino_lock = []
slots_lock = []

# ???
rigged_users = []

# cat rains
cat_rains = {}

# to prevent double catches
temp_catches_storage = []

# to prevent weird behaviour shortly after a rain
temp_rains_storage = []

# prevent timetravel
in_the_past = False
about_to_stop = False

# manual restarts
queue_restart: Optional[discord.Message] = None

# docs suggest on_ready can be called multiple times
on_ready_debounce = False

# d.py doesnt cache app emojis so we do it on our own yippe
emojis = {}

# for mentioning it in catch message, will be auto-fetched in on_ready()
DONATE_ID = 1249368737824374896
RAIN_ID = 1270470307102195752

# for funny starts, you can probably edit maintaince_loop to restart every X of them
loop_count = 0

# loops in dpy can randomly break, i check if is been over X minutes since last loop to restart it
last_loop_time = 0


def get_profile(guild_id, user_id):
    try:
        return Profile.get(
            (Profile.guild_id == int(guild_id)) &
            (Profile.user_id == int(user_id))
        )
    except Exception:
        return Profile.create(
            guild_id=guild_id,
            user_id=user_id
        )


def get_emoji(name):
    global emojis
    if name in emojis.keys():
        return emojis[name]
    else:
        return "🔳"


# news stuff
news_list = [
    {"title": "Cat Bot Survey - win rains!", "emoji": "📜"},
    {"title": "New Cat Rains perks!", "emoji": "✨"}
]
async def send_news(interaction: discord.Interaction):
    news_id, original_caller = interaction.data["custom_id"].split(" ")  # pyright: ignore
    if str(interaction.user.id) != original_caller:
        await do_funny(interaction)
        return

    await interaction.response.defer()

    news_id = int(news_id)

    user, _ = User.get_or_create(user_id=interaction.user.id)
    current_state = user.news_state.strip()
    user.news_state = current_state[:news_id] + "1" + current_state[news_id + 1:]
    user.save()

    if news_id == 0:
        embed = discord.Embed(
            title="📜 Cat Bot Survey",
            description="Hello and welcome to The Cat Bot Times:tm:! I kind of want to learn more about your time with Cat Bot because I barely know about it lmao. This should only take a couple of minutes.\n\nGood high-quality responses will win FREE cat rain prizes.\n\nSurvey is closed!",
            color=0x6E593C
        )
        await interaction.edit_original_response(content=None, view=None, embed=embed)
    elif news_id == 1:
        embed = discord.Embed(
            title="✨ New Cat Rains perks!",
            description="Hey there! Buying Cat Rains now gives you access to `/editprofile` command! You can add an image, change profile color, and add an emoji next to your name. Additionally, you will now get a special role in our [discord server](https://discord.gg/staring).\nEveryone who ever bought rains and all future buyers will get it.\nAnyone who bought these abilities separately in the past (known as 'Cat Bot Supporter') have received 10 minutes of Rains as compensation.\n\nThis is a really cool perk and I hope you like it!",
            color=0x6E593C
        )
        await interaction.edit_original_response(content=None, view=None, embed=embed)

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

    profile = get_profile(message.guild.id, author)

    if not profile[ach_id]:
        profile[ach_id] = True
        profile.save()
        ach_data = ach_list[ach_id]
        desc = ach_data["description"]
        if ach_id == "dataminer":
            desc = "Your head hurts -- you seem to have forgotten what you just did to get this."

        if ach_id != "thanksforplaying":
            embed = discord.Embed(
                title=ach_data["title"],
                description=desc,
                color=0x007F0E
            ).set_author(
                name="Achievement get!",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/cat_throphy.png"
            ).set_footer(text=f"Unlocked by {author_string.name}")
        else:
            embed = discord.Embed(
                title="Cataine Addict",
                description="Defeat the dog mafia\nThanks for playing! ✨",
                color=0xC12929
            ).set_author(
                name="Demonic achievement unlocked! 🌟",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/demonic.png"
            ).set_footer(text=f"Congrats to {author_string.name}!!")

            embed2 = discord.Embed(
                title="Cataine Addict",
                description="Defeat the dog mafia\nThanks for playing! ✨",
                color=0xFFFF00
            ).set_author(
                name="Demonic achievement unlocked! 🌟",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/demonic.png"
            ).set_footer(text=f"Congrats to {author_string.name}!!")

        try:
            result = None
            perms: discord.Permissions = message.channel.permissions_for(message.guild.me)
            correct_perms = perms.send_messages and (not isinstance(message.channel, discord.Thread) or perms.send_messages_in_threads)
            if send_type == "reply" and correct_perms:
                result = await message.reply(embed=embed)
            elif send_type == "send" and correct_perms:
                result = await message.channel.send(embed=embed)
            elif send_type == "followup":
                result = await message.followup.send(embed=embed, ephemeral=True)
            elif send_type == "response":
                result = await message.response.send_message(embed=embed)
            await battlepass_finale(message, profile)
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


# handle curious people clicking buttons
async def do_funny(message):
    await message.response.send_message(random.choice(funny), ephemeral=True)
    await achemb(message, "curious", "send")
    user = get_profile(message.guild.id, message.user.id)
    user.funny += 1
    user.save()
    if user.funny >= 50:
        await achemb(message, "its_not_working", "send")


# :eyes:
async def battlepass_finale(message, user):
    # check ach req
    for k in ach_names:
        if not user[k] and ach_list[k]["category"] != "Hidden":
            return

    # check battlepass req
    if user.battlepass != len(battle["levels"]) - 2:
        return

    user.battlepass += 2
    user.save()
    perms: discord.Permissions = message.channel.permissions_for(message.guild.me)
    if perms.send_messages and (not isinstance(message.channel, discord.Thread) or perms.send_messages_in_threads):
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
        await message.channel.send(embed=discord.Embed(
                title="True Ending achieved!",
                description="You are finally free.",
                color=0xFF81C6
            ).set_author(
                name="Cattlepass complete!",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png"
            ).set_footer(
                text=f"Congrats to {author_string}"
            )
        )


# function to autocomplete cat_type choices for /givecat, and /forcespawn, which also allows more than 25 options
async def cat_type_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [discord.app_commands.Choice(name=choice, value=choice) for choice in cattypes if current.lower() in choice.lower()][:25]


# function to autocomplete cat_type choices for /gift, which shows only cats user has and how many of them they have
async def gift_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    user = get_profile(interaction.guild.id, interaction.user.id)
    actual_user, _ = User.get_or_create(user_id=interaction.user.id)
    choices = []
    for choice in cattypes:
        if current.lower() in choice.lower() and user[f"cat_{choice}"] != 0:
            choices.append(discord.app_commands.Choice(name=f"{choice} (x{user[f'cat_{choice}']})", value=choice))
    if current.lower() in "rain" and actual_user.rain_minutes != 0:
        choices.append(discord.app_commands.Choice(name=f"Rain ({actual_user.rain_minutes} minutes)", value="rain"))
    return choices[:25]


# function to autocomplete achievement choice for /giveachievement, which also allows more than 25 options
async def ach_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [discord.app_commands.Choice(name=val["title"], value=key) for (key, val) in ach_list.items() if (alnum(current) in alnum(key) or alnum(current) in alnum(val["title"]))][:25]


# converts string to lowercase alphanumeric characters only
def alnum(string):
    return "".join(item for item in string.lower() if item.isalnum())


async def unsetup(channel):
    try:
        wh = discord.Webhook.from_url(channel.webhook, client=bot)
        await wh.delete(prefer_auth=False)
    except Exception:
        pass
    channel.delete_instance()

async def spawn_cat(ch_id, localcat=None):
    try:
        channel = Channel.get(channel_id=ch_id)
    except Exception:
        return
    if channel.cat or in_the_past:
        return

    if not localcat:
        localcat = random.choice(CAT_TYPES)
    icon = get_emoji(localcat.lower() + "cat")
    file = discord.File(f"images/spawn/{localcat.lower()}_cat.png")
    try:
        channeley = discord.Webhook.from_url(channel.webhook, client=bot)
        thread_id = channel.thread_mappings
    except Exception:
        try:
            temp_channel = bot.get_channel(int(ch_id))
            if not temp_channel \
            or not isinstance(temp_channel, Union[discord.TextChannel, discord.StageChannel, discord.VoiceChannel]) \
            or not temp_channel.permissions_for(temp_channel.guild.me).manage_webhooks:
                raise Exception
            with open("images/cat.png", "rb") as f:
                wh = await temp_channel.create_webhook(name="Cat Bot", avatar=f.read())
                channel.webhook = wh.url
                channel.save()
                await spawn_cat(ch_id, localcat) # respawn
        except Exception:
            await unsetup(channel)
            return

    appearstring = "{emoji} {type} cat has appeared! Type \"cat\" to catch it!" if not channel.appear else channel.appear

    if channel.cat or in_the_past:
        # its never too late to return
        return

    try:
        if thread_id:
            message_is_sus = await channeley.send(appearstring.replace("{emoji}", str(icon)).replace("{type}", localcat), file=file, wait=True, thread=discord.Object(int(ch_id)))
        else:
            message_is_sus = await channeley.send(appearstring.replace("{emoji}", str(icon)).replace("{type}", localcat), file=file, wait=True)
    except discord.Forbidden:
        await unsetup(channel)
        return
    except discord.NotFound:
        await unsetup(channel)
        return
    except Exception:
        return

    if message_is_sus.channel.id != int(ch_id):
        # user changed the webhook destination, panic mode
        if thread_id:
            await channeley.send("uh oh spaghettio you changed webhook destination and idk what to do with that so i will now self destruct do /setup to fix it", thread=discord.Object(int(ch_id)))
        else:
            await channeley.send("uh oh spaghettio you changed webhook destination and idk what to do with that so i will now self destruct do /setup to fix it")
        await unsetup(channel)
        return

    channel.cat = message_is_sus.id
    channel.yet_to_spawn = 0
    channel.save()


# a loop for various maintaince which is ran every 5 minutes
async def maintaince_loop():
    global pointlaugh_ratelimit, reactions_ratelimit, last_loop_time, loop_count, in_the_past, about_to_stop
    last_loop_time = time.time()
    pointlaugh_ratelimit = {}
    reactions_ratelimit = {}
    await bot.change_presence(
        activity=discord.CustomActivity(name=f"Catting in {len(bot.guilds):,} servers")
    )

    async with aiohttp.ClientSession() as session:
        if config.TOP_GG_TOKEN:
            # send server count to top.gg
            try:
                await session.post(f'https://top.gg/api/bots/{bot.user.id}/stats',
                                    headers={"Authorization": config.TOP_GG_TOKEN},
                                    json={"server_count": len(bot.guilds), "shard_count": len(bot.shards)},
                                    timeout=15)
            except Exception:
                print("Posting to top.gg failed.")

    for channel in Channel.select().where((Channel.yet_to_spawn < time.time()) & (Channel.cat == 0)):
        await spawn_cat(str(channel.channel_id))
        await asyncio.sleep(0.1)

    notified_users = []
    errored_users = []
    processed_users = []
    # THIS IS CONSENTUAL AND TURNED OFF BY DEFAULT DONT BAN ME
    for user in User.select().where((User.vote_remind != 0) & (User.vote_time_topgg + 43200 < time.time()) & (User.reminder_topgg_exists == 0)):
        if user.user_id in processed_users:
            # prevent double notifis
            continue
        await asyncio.sleep(0.1)
        processed_users.append(user.user_id)

        channeley = bot.get_channel(user.vote_remind)
        if not isinstance(channeley, discord.TextChannel):
            user.vote_remind = 0
            errored_users.append(user)
            continue

        view = View(timeout=1)
        button = Button(emoji=get_emoji("topgg"), label=random.choice(vote_button_texts), style=ButtonStyle.gray, url="https://top.gg/bot/966695034340663367/vote")
        view.add_item(button)

        try:
            await channeley.send(f"<@{user.user_id}> You can vote now!", view=view)
            user.reminder_topgg_exists = time.time()
            notified_users.append(user)
        except Exception:
            user.vote_remind = 0
            errored_users.append(user)

    with db.atomic():
        User.bulk_update(notified_users, fields=[User.reminder_topgg_exists], batch_size=50)
        User.bulk_update(errored_users, fields=[User.vote_remind], batch_size=50)

    for reminder in Reminder.select().where(Reminder.time < time.time()):
        try:
            user = await bot.fetch_user(reminder.user_id)
            await user.send(reminder.text)
            await asyncio.sleep(0.5)
        except Exception:
            pass
        reminder.delete_instance()


    backupchannel = bot.get_channel(config.BACKUP_ID)
    if not isinstance(backupchannel, Union[discord.TextChannel, discord.StageChannel, discord.VoiceChannel, discord.Thread]):
        raise ValueError
    await backupchannel.send(f"In {len(bot.guilds)} servers, loop {loop_count}.")

    loop_count += 1


# some code which is run when bot is started
async def on_ready():
    global milenakoos, OWNER_ID, on_ready_debounce, gen_credits, emojis
    if on_ready_debounce:
        return
    on_ready_debounce = True
    print("cat is now online")
    emojis = {emoji.name: str(emoji) for emoji in await bot.fetch_application_emojis()}
    appinfo = bot.application
    if appinfo.team and appinfo.team.owner_id:
        milenakoos = await bot.fetch_user(appinfo.team.owner_id)
    else:
        milenakoos = appinfo.owner
    OWNER_ID = milenakoos.id

    credits = {
        "author": [553093932012011520],
        "contrib": [576065759185338371, 819980535639572500, 432966085025857536, 646401965596868628, 696806601771974707, 804762486946660353, 931342092121280543, 695359046928171118],
        "tester": [712639066373619754, 902862104971849769, 709374062237057074, 520293520418930690, 689345298686148732, 1004128541853618197, 839458185059500032],
        "trash": [520293520418930690]
    }

    # fetch discord usernames by user ids
    for key in credits.keys():
        peoples = []
        try:
            for i in credits[key]:
                user = await bot.fetch_user(i)
                peoples.append(user.name.replace("_", r"\_"))
        except Exception:
            # death
            pass
        gen_credits[key] = ", ".join(peoples)


# this is all the code which is ran on every message sent
# a lot of it is for easter eggs or achievements
async def on_message(message: discord.Message):
    global in_the_past, emojis, queue_restart, about_to_stop
    text = message.content
    if not bot.user or message.author.id == bot.user.id:
        return

    if time.time() > last_loop_time + 300:
        await maintaince_loop()

    if text == "lol_i_have_dmed_the_cat_bot_and_got_an_ach" and not message.guild:
        await message.channel.send("which part of \"send in server\" was unclear?")
        return
    elif message.guild is None:
        await message.channel.send("good job! please send \"lol_i_have_dmed_the_cat_bot_and_got_an_ach\" in server to get your ach!")
        return

    perms: discord.Permissions = message.channel.permissions_for(message.guild.me)

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
        ["tac", "exact", "reverse"]
    ]

    reactions = [
        ["v1;", "custom", "why_v1"],
        ["proglet", "custom", "professor_cat"],
        ["xnopyt", "custom", "vanish"],
        ["silly", "custom", "sillycat"],
        ["indev", "vanilla", "🐸"],
        ["bleh", "custom", "blepcat"],
        ["blep", "custom", "blepcat"]
    ]

    responses = [
        ["cat!sex", "exact", "..."],
        ["cellua good", "in", ".".join([str(random.randint(2, 254)) for _ in range(4)])],
        ["https://tenor.com/view/this-cat-i-have-hired-this-cat-to-stare-at-you-hired-cat-cat-stare-gif-26392360", "exact", "https://tenor.com/view/cat-staring-cat-gif-16983064494644320763"]
    ]

    # here are some automation hooks for giving out purchases and autoupdating
    if config.GITHUB_CHANNEL_ID and message.channel.id == config.GITHUB_CHANNEL_ID:
        about_to_stop = True
        os.system("git pull")
        await vote_server.cleanup()
        in_the_past = True
        await bot.cat_bot_reload_hook()  # pyright: ignore

    if config.DONOR_CHANNEL_ID and message.channel.id == config.DONOR_CHANNEL_ID:
        user, _ = User.get_or_create(user_id=message.content)
        user.premium = True
        user.save()

    if config.RAIN_CHANNEL_ID and message.channel.id == config.RAIN_CHANNEL_ID and text.lower().startswith("cat!rain"):
        things = text.split(" ")
        user, _ = User.get_or_create(user_id=things[1])
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
        user.save()

    react_count = 0

    # :staring_cat: reaction on "bullshit"
    if " " not in text and len(text) > 7 and text.isalnum():
        s = text.lower()
        total_vow = 0
        total_illegal = 0
        for i in "aeuio":
            total_vow += s.count(i)
        illegal = ["bk", "fq", "jc", "jt", "mj", "qh", "qx", "vj",  "wz",  "zh",
                        "bq", "fv", "jd", "jv", "mq", "qj", "qy", "vk",  "xb",  "zj",
                        "bx", "fx", "jf", "jw", "mx", "qk", "qz", "vm",  "xg",  "zn",
                        "cb", "fz", "jg", "jx", "mz", "ql", "sx", "vn",  "xj",  "zq",
                        "cf", "gq", "jh", "jy", "pq", "qm", "sz", "vp",  "xk",  "zr",
                        "cg", "gv", "jk", "jz", "pv", "qn", "tq", "vq",  "xv",  "zs",
                        "cj", "gx", "jl", "kq", "px", "qo", "tx", "vt",  "xz",  "zx",
                        "cp", "hk", "jm", "kv", "qb", "qp", "vb", "vw",  "yq",
                        "cv", "hv", "jn", "kx", "qc", "qr", "vc", "vx",  "yv",
                        "cw", "hx", "jp", "kz", "qd", "qs", "vd", "vz",  "yz",
                        "cx", "hz", "jq", "lq", "qe", "qt", "vf", "wq",  "zb",
                        "dx", "iy", "jr", "lx", "qf", "qv", "vg", "wv",  "zc",
                        "fk", "jb", "js", "mg", "qg", "qw", "vh", "wx",  "zg"]
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
                if message.channel.permissions_for(message.guild.me).add_reactions:
                    await message.add_reaction(get_emoji("staring_cat"))
                    react_count += 1
            except Exception:
                pass

    try:
        if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
            if "robotop" in message.author.name.lower() and "i rate **cat" in message.content.lower():
                icon = str(get_emoji("no_cat_throphy")) + " "
                await message.reply("**RoboTop**, I rate **you** 0 cats " + icon * 5)

            if "leafbot" in message.author.name.lower() and "hmm... i would rate cat" in message.content.lower():
                icon = str(get_emoji("no_cat_throphy")) + " "
                await message.reply("Hmm... I would rate you **0 cats**! " + icon * 5)
    except Exception:
        pass

    if message.author.bot or message.webhook_id is not None:
        return

    if "cat!n4lltvuCOKe2iuDCmc6JsU7Jmg4vmFBj8G8l5xvoDHmCoIJMcxkeXZObR6HbIV6" in text:
        msg = message
        try:
            if perms.manage_messages:
                await message.delete()
        except Exception:
            pass
        await achemb(msg, "dataminer", "send")

    for ach in achs:
        if (ach[1] == "startswith" and text.lower().startswith(ach[0])) or \
        (ach[1] == "re" and re.search(ach[0], text.lower())) or \
        (ach[1] == "exact" and ach[0] == text.lower()) or \
        (ach[1] == "in" and ach[0] in text.lower()):
            await achemb(message, ach[2], "reply")

    if perms.add_reactions:
        for r in reactions:
            if r[0] in text.lower() and reactions_ratelimit.get(message.author.id, 0) < 20:
                if r[1] == "custom":
                    em = get_emoji(r[2])
                elif r[1] == "vanilla":
                    em = r[2]

                try:
                    await message.add_reaction(em)
                    react_count += 1
                    reactions_ratelimit[message.author.id] = reactions_ratelimit.get(message.author.id, 0) + 1
                except Exception:
                    pass

    if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
        for resp in responses:
            if (resp[1] == "startswith" and text.lower().startswith(resp[0])) or \
            (resp[1] == "re" and re.search(resp[0], text.lower())) or \
            (resp[1] == "exact" and resp[0] == text.lower()) or \
            (resp[1] == "in" and resp[0] in text.lower()):
                try:
                    await message.reply(resp[2])
                except Exception:
                    pass

    try:
        if message.author in message.mentions and perms.add_reactions:
            await message.add_reaction(get_emoji("staring_cat"))
            react_count += 1
    except Exception:
        pass

    if react_count >= 3 and perms.add_reactions:
        await achemb(message, "silly", "send")

    if (":place_of_worship:" in text or "🛐" in text) and (":cat:" in text or ":staring_cat:" in text or "🐱" in text):
        await achemb(message, "worship", "reply")

    if text.lower() in ["testing testing 1 2 3", "cat!ach"]:
        try:
            if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                await message.reply("test success")
        except Exception:
            # test failure
            pass
        await achemb(message, "test_ach", "reply")

    if text.lower() == "please do not the cat":
        user = get_profile(message.guild.id, message.author.id)
        user.cat_Fine -= 1
        user.save()
        try:
            if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                await message.reply(f"ok then\n{message.author.name.replace("_", r"\_")} lost 1 fine cat!!!1!\nYou now have {user.cat_Fine:,} cats of dat type!")
        except Exception:
            pass
        await achemb(message, "pleasedonotthecat", "reply")

    if text.lower() == "please do the cat":
        thing = discord.File("images/socialcredit.jpg", filename="socialcredit.jpg")
        try:
            if perms.send_messages and perms.attach_files and (not message.thread or perms.send_messages_in_threads):
                await message.reply(file=thing)
        except Exception:
            pass
        await achemb(message, "pleasedothecat", "reply")

    if text.lower() == "car":
        file = discord.File("images/car.png", filename="car.png")
        embed = discord.Embed(title="car!", color=0x6E593C).set_image(url="attachment://car.png")
        try:
            if perms.send_messages and perms.attach_files and (not message.thread or perms.send_messages_in_threads):
                await message.reply(file=file, embed=embed)
        except Exception:
            pass
        await achemb(message, "car", "reply")

    if text.lower() == "cart":
        file = discord.File("images/cart.png", filename="cart.png")
        embed = discord.Embed(title="cart!", color=0x6E593C).set_image(url="attachment://cart.png")
        try:
            if perms.send_messages and perms.attach_files and (not message.thread or perms.send_messages_in_threads):
                await message.reply(file=file, embed=embed)
        except Exception:
            pass

    try:
        if ("sus" in text.lower() or "amog" in text.lower() or "among" in text.lower() or "impost" in text.lower() or "report" in text.lower()) and \
        (channel := Channel.get_or_none(channel_id=message.channel.id)) and channel.cat and perms.read_message_history:
            catchmsg = await message.channel.fetch_message(channel.cat)
            if get_emoji("suscat") in catchmsg.content:
                await achemb(message, "sussy", "send")
    except Exception:
        pass

    # this is run whether someone says "cat" (very complex)
    if text.lower() == "cat":
        user = get_profile(message.guild.id, message.author.id)
        channel = Channel.get_or_none(channel_id=message.channel.id)
        if not channel or not channel.cat or channel.cat in temp_catches_storage or user.timeout > time.time():
            # laugh at this user
            # (except if rain is active, we dont have perms or channel isnt setupped, or we laughed way too much already)
            if channel and cat_rains.get(str(message.channel.id), 0) < time.time() and perms.add_reactions and pointlaugh_ratelimit.get(message.channel.id, 0) < 10:
                try:
                    await message.add_reaction(get_emoji("pointlaugh"))
                    pointlaugh_ratelimit[message.channel.id] = pointlaugh_ratelimit.get(message.channel.id, 0) + 1
                except Exception:
                    pass
        else:
            pls_remove_me_later_k_thanks = channel.cat
            temp_catches_storage.append(channel.cat)
            times = [channel.spawn_times_min, channel.spawn_times_max]
            if cat_rains.get(str(message.channel.id), 0) != 0:
                if cat_rains.get(str(message.channel.id), 0) > time.time():
                    times = [1, 2]
                else:
                    temp_rains_storage.append(message.channel.id)
                    del cat_rains[str(message.channel.id)]
                    try:
                        if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                            await message.channel.send("# :bangbang: this concludes the cat rain.")
                            await message.channel.send("# :bangbang: this concludes the cat rain.")
                            await message.channel.send("# :bangbang: this concludes the cat rain.")
                    except Exception:
                        pass
                    if queue_restart and (len(cat_rains) == 0 or int(max(cat_rains.values())) < time.time()):
                        about_to_stop = True
                        await queue_restart.reply("restarting now!")
                        os.system("git pull")
                        await vote_server.cleanup()
                        in_the_past = True
                        await bot.cat_bot_reload_hook()  # pyright: ignore
            decided_time = random.uniform(times[0], times[1])
            if channel.yet_to_spawn < time.time():
                channel.yet_to_spawn = time.time() + decided_time + 10
            else:
                decided_time = 0
            try:
                current_time = message.created_at.timestamp()
                channel.lastcatches = current_time
                cat_temp = channel.cat
                channel.cat = 0
                try:
                    if perms.read_message_history:
                        var = await message.channel.fetch_message(cat_temp)
                    else:
                        raise Exception
                except Exception:
                    try:
                        if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                            await message.channel.send(f"oopsie poopsie i cant access the original message but {message.author.mention} *did* catch a cat rn")
                    except Exception:
                        pass
                    return
                catchtime = var.created_at
                catchcontents = var.content
                try:
                    send_target = discord.Webhook.from_url(channel.webhook, client=bot)
                    try:
                        if channel.thread_mappings:
                            await send_target.delete_message(cat_temp, thread=discord.Object(int(message.channel.id)))
                        else:
                            await send_target.delete_message(cat_temp)
                    except Exception:
                        if perms.manage_messages:
                            await cat_temp.delete()
                except Exception:
                    send_target = message.channel
                try:
                    # some math to make time look cool
                    then = catchtime.timestamp()
                    time_caught = round(abs(current_time - then), 3) # cry about it
                    if time_caught >= 1:
                        time_caught = round(time_caught, 2)
                    days = time_caught // 86400
                    time_left = time_caught - (days * 86400)
                    hours = time_left // 3600
                    time_left = time_left - (hours * 3600)
                    minutes = time_left // 60
                    seconds = time_left - (minutes * 60)
                    caught_time = ""
                    if days:
                        caught_time = caught_time + str(int(days)) + " days "
                    if hours:
                        caught_time = caught_time + str(int(hours)) + " hours "
                    if minutes:
                        caught_time = caught_time + str(int(minutes)) + " minutes "
                    if seconds:
                        pre_time = round(seconds, 3)
                        if int(pre_time) == float(pre_time):
                            # replace .0 with .00 basically
                            pre_time = str(int(pre_time)) + ".00"
                        caught_time = caught_time + str(pre_time) + " seconds "
                    do_time = True
                    if time_caught <= 0:
                        do_time = False
                except Exception:
                    # if some of the above explodes just give up
                    do_time = False
                    caught_time = "undefined amounts of time "

                if cat_rains.get(str(message.channel.id), 0) + 10 > time.time() or message.channel.id in temp_rains_storage:
                    do_time = False

                icon = None
                partial_type = None
                for v in allowedemojis:
                    if v in catchcontents:
                        partial_type = v
                        break

                if not partial_type:
                    return

                for i in cattypes:
                    if i.lower() in partial_type:
                        le_emoji = i
                        break

                suffix_string = ""

                # calculate prism boost
                boost_chance = 0
                disabled_chance = 0
                boost_prisms = []
                disabled_prisms = []
                for prism in Prism.select().where(Prism.guild_id == message.guild.id):
                    if prism.user_id == message.author.id:
                        if prism[f"enabled_{le_emoji.lower()}"]:
                            boost_chance += 5
                            boost_prisms.extend([["Your", prism.name]] * 5)
                        else:
                            disabled_chance += 5
                            disabled_prisms.extend([["Your", prism.name]] * 5)
                    else:
                        if prism[f"enabled_{le_emoji.lower()}"]:
                            boost_chance += 1
                            boost_prisms.append([prism.user_id, prism.name])
                        else:
                            disabled_chance += 1
                            disabled_prisms.append([prism.user_id, prism.name])
                all_prisms = boost_prisms + disabled_prisms

                # apply prism boost
                if random.randint(1, 100) <= boost_chance + disabled_chance:
                    boost_prism = random.choice(all_prisms)
                    if boost_prism[0] != "Your":
                        prism_user = await bot.fetch_user(boost_prism[0])
                        boost_applied_prism = str(prism_user) + "'s prism " + boost_prism[1]
                    else:
                        boost_applied_prism = "Your prism " + boost_prism[1]

                    if boost_prism in boost_prisms:
                        await achemb(message, "boosted", "send")
                        try:
                            le_old_emoji = le_emoji
                            le_emoji = cattypes[cattypes.index(le_emoji) + 1]
                            normal_bump = True
                        except IndexError:
                            # :SILENCE:
                            if cat_rains.get(str(message.channel.id), 0) > time.time():
                                await message.channel.send("# ‼️‼️ RAIN EXTENDED BY 10 MINUTES ‼️‼️")
                                await message.channel.send("# ‼️‼️ RAIN EXTENDED BY 10 MINUTES ‼️‼️")
                                await message.channel.send("# ‼️‼️ RAIN EXTENDED BY 10 MINUTES ‼️‼️")
                            cat_rains[str(message.channel.id)] = cat_rains.get(str(message.channel.id), time.time()) + 606
                            decided_time = 6
                            normal_bump = False
                            pass

                        if normal_bump:
                            suffix_string += f"\n{get_emoji('prism')} {boost_applied_prism} boosted this catch from a {get_emoji(le_old_emoji.lower() + 'cat')} {le_old_emoji} cat!"
                        else:
                            suffix_string += f"\n{get_emoji('prism')} {boost_applied_prism} tried to boost this catch, but failed! A 10m rain will start!"
                    else:
                        suffix_string += f"\n{get_emoji('prism')} {boost_applied_prism} would have boosted this catch, but this boost was disabled by its owner."

                icon = get_emoji(le_emoji.lower() + "cat")

                silly_amount = 1
                if user.cataine_active > time.time():
                    # cataine is active
                    silly_amount = 2
                    suffix_string += "\n🧂 cataine worked! you got 2 cats instead!"

                elif user.cataine_active != 0:
                    # cataine ran out
                    user.cataine_active = 0
                    suffix_string += "\nyour cataine buff has expired. you know where to get a new one 😏"

                if random.randint(0, 7) == 0:
                    # shill rains
                    suffix_string += f"\n☔ get tons of cats and have fun: </rain:{RAIN_ID}>"

                if channel.cought:
                    coughstring = channel.cought
                elif le_emoji == "Corrupt":
                    coughstring = "{username} coought{type} c{emoji}at!!!!404!\nYou now BEEP {count} cats of dCORRUPTED!!\nthis fella wa- {time}!!!!"
                elif le_emoji == "eGirl":
                    coughstring = "{username} cowought {emoji} {type} cat~~ ^^\nYou-u now *blushes* hawe {count} cats of dat tywe~!!!\nthis fella was <3 cought in {time}!!!!"
                elif le_emoji == "Rickroll":
                    coughstring = "{username} cought {emoji} {type} cat!!!!1!\nYou will never give up {count} cats of dat type!!!\nYou wouldn't let them down even after {time}!!!!"
                elif le_emoji == "Sus":
                    coughstring = "{username} cought {emoji} {type} cat!!!!1!\nYou have vented infront of {count} cats of dat type!!!\nthis sussy baka was cought in {time}!!!!"
                elif le_emoji == "Professor":
                    coughstring = "{username} caught {emoji} {type} cat!\nThou now hast {count} cats of that type!\nThis fellow was caught 'i {time}!"
                elif le_emoji == "8bit":
                    coughstring = "{username} c0ught {emoji} {type} cat!!!!1!\nY0u n0w h0ve {count} cats 0f dat type!!!\nth1s fe11a was c0ught 1n {time}!!!!"
                elif le_emoji == "Reverse":
                    coughstring = "!!!!{time} in cought was fella this\n!!!type dat of cats {count} have now You\n!1!!!!cat {type} {emoji} cought {username}"
                else:
                    coughstring = "{username} cought {emoji} {type} cat!!!!1!\nYou now have {count} cats of dat type!!!\nthis fella was cought in {time}!!!!"
                view = None
                button = None

                async def dark_market_cutscene(interaction):
                    nonlocal message
                    if interaction.user != message.author:
                        await interaction.response.send_message("the shadow you saw runs away. perhaps you need to be the one to catch the cat.", ephemeral=True)
                        return
                    if user.dark_market_active:
                        await interaction.response.send_message("the shadowy figure is nowhere to be found.", ephemeral=True)
                        return
                    user.dark_market_active = True
                    user.save()
                    await interaction.response.send_message("is someone watching after you?", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction.followup.send("you walk up to them. the dark voice says:", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction.followup.send("**???**: Hello. We have a unique deal for you.", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction.followup.send("**???**: To access our services, press \"Hidden\" `/achievements` tab 3 times in a row.", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction.followup.send("**???**: You won't be disappointed.", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction.followup.send("before you manage to process that, the figure disappears. will you figure out whats going on?", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction.followup.send("the only choice is to go to that place.", ephemeral=True)

                vote_time_user, _ = User.get_or_create(user_id=message.author.id)
                if random.randint(0, 10) == 0 and user.cat_Fine >= 20 and not user.dark_market_active:
                    button = Button(label="You see a shadow...", style=ButtonStyle.blurple)
                    button.callback = dark_market_cutscene
                elif config.WEBHOOK_VERIFY and vote_time_user.vote_time_topgg + 43200 < time.time():
                    button = Button(emoji=get_emoji("topgg"), label=random.choice(vote_button_texts), url="https://top.gg/bot/966695034340663367/vote")
                elif random.randint(0, 20) == 0:
                    button = Button(label="Join our Discord!", url="https://discord.gg/staring")
                elif random.randint(0, 500) == 0:
                    button = Button(label="John Discord 🤠", url="https://discord.gg/staring")
                elif random.randint(0, 50000) == 0:
                    button = Button(label="DAVE DISCORD 😀💀⚠️🥺", url="https://discord.gg/staring", style=ButtonStyle.danger)
                elif random.randint(0, 5000000) == 0:
                    button = Button(label="JOHN AND DAVE HAD A SON 💀🤠😀⚠️🥺", url="https://discord.gg/staring", style=ButtonStyle.green)

                if button:
                    view = View(timeout=3600)
                    view.add_item(button)

                user[f"cat_{le_emoji}"] += silly_amount
                new_count = user[f"cat_{le_emoji}"]

                if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                    try:
                        kwargs = {}
                        if channel.thread_mappings:
                            kwargs["thread"] = discord.Object(message.channel.id)
                        if view:
                            kwargs["view"] = view

                        await send_target.send(coughstring.replace("{username}", message.author.name.replace("_", "\\_"))
                                                            .replace("{emoji}", str(icon))
                                                            .replace("{type}", le_emoji)
                                                            .replace("{count}", f"{new_count:,}")
                                                            .replace("{time}", caught_time[:-1]) + suffix_string,
                                                **kwargs)
                    except Exception:
                        pass

                if random.randint(0, 1000) == 69:
                    await achemb(message, "lucky", "send")
                if message.content == "CAT":
                    await achemb(message, "loud_cat", "send")
                if cat_rains.get(str(message.channel.id), 0) != 0:
                    await achemb(message, "cat_rain", "send")

                # handle fastest and slowest catches
                if do_time and time_caught < user.time:
                    user.time = time_caught
                if do_time and time_caught > user.timeslow:
                    user.timeslow = time_caught

                if message.channel.id in temp_rains_storage:
                    temp_rains_storage.remove(message.channel.id)

                await achemb(message, "first", "send")

                if user.time <= 5:
                    await achemb(message, "fast_catcher", "send")

                if user.timeslow >= 3600:
                    await achemb(message, "slow_catcher", "send")

                if do_time and time_caught == 3.14:
                    await achemb(message, "pie", "send")

                if do_time and time_caught == int(time_caught):
                    await achemb(message, "perfection", "send")

                if do_time:
                    raw_digits = ''.join(char for char in caught_time[:-1] if char.isdigit())
                    if len(set(raw_digits)) == 1:
                        await achemb(message, "all_the_same", "send")

                # handle battlepass
                def do_reward(level):
                    user.progress = 0
                    reward = level["reward"]
                    if reward == "Prisms":
                        user.battlepass += 1
                        icon = get_emoji("prism")
                        reward_text = f"You have unlocked {icon} Prism Crafting Recipe!\nCheck out `/prism`!"
                    else:
                        user.battlepass += 1
                        reward_amount = level["reward_amount"]
                        user[f"cat_{reward}"] += reward_amount
                        icon = get_emoji(reward.lower() + "cat")
                        reward_text = f"You have received {icon} {reward_amount} {reward} cats!"

                    return discord.Embed(
                        title=f"Level {user.battlepass} complete!",
                        description=reward_text,
                        color=0x007F0E
                    ).set_author(name="Cattlepass level!", icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png")

                if user.battlepass != len(battle["levels"]):
                    battlelevel = battle["levels"][user.battlepass]
                    if battlelevel["req"] == "catch_fast" and do_time and time_caught < battlelevel["req_data"]:
                        embed = do_reward(battlelevel)
                    if battlelevel["req"] == "catch":
                        user.progress += 1
                        if user.progress == battlelevel["req_data"]:
                            embed = do_reward(battlelevel)
                    if battlelevel["req"] == "catch_type" and le_emoji == battlelevel["req_data"]:
                        embed = do_reward(battlelevel)

                    try:
                        if embed and perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                            await message.channel.send(embed=embed)
                    except Exception:
                        pass
            finally:
                user.save()
                channel.save()
                bot.loop.create_task(battlepass_finale(message, user))
                if decided_time:
                    await asyncio.sleep(decided_time)
                    try:
                        temp_catches_storage.remove(pls_remove_me_later_k_thanks)
                    except Exception:
                        pass
                    await spawn_cat(str(message.channel.id))
                else:
                    try:
                        temp_catches_storage.remove(pls_remove_me_later_k_thanks)
                    except Exception:
                        pass

    # those are "owner" commands which are not really interesting
    if text.lower().startswith("cat!sweep") and message.author.id == OWNER_ID:
        try:
            channel = Channel.get(channel_id=message.channel.id)
            channel.cat = 0
            channel.save()
            await message.reply("success")
        except Exception:
            pass
    if text.lower().startswith("cat!rain") and message.author.id == OWNER_ID:
        # syntax: cat!rain 553093932012011520 short
        things = text.split(" ")
        user, _ = User.get_or_create(user_id=things[1])
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
        user.save()
    if text.lower().startswith("cat!restart") and message.author.id == OWNER_ID:
        if not cat_rains or int(max(cat_rains.values())) < time.time():
            about_to_stop = True
            await message.reply("restarting now!")
            os.system("git pull")
            await vote_server.cleanup()
            in_the_past = True
            await bot.cat_bot_reload_hook()  # pyright: ignore
        else:
            queue_restart = message
            await message.reply("restarting soon...")
    if text.lower().startswith("cat!print") and message.author.id == OWNER_ID:
        # just a simple one-line with no async (e.g. 2+3)
        try:
            await message.reply(eval(text[9:]))
        except Exception:
            try:
                await message.reply(traceback.format_exc())
            except Exception:
                pass
    if text.lower().startswith("cat!eval") and message.author.id == OWNER_ID:
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
    if text.lower().startswith("cat!news") and message.author.id == OWNER_ID:
        for i in Channel.select():
            try:
                channeley = bot.get_channel(int(i.channel_id))
                if not isinstance(channeley, Union[discord.TextChannel, discord.StageChannel, discord.VoiceChannel, discord.Thread]):
                    continue
                if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                    await channeley.send(text[8:])
            except Exception:
                pass
    if text.lower().startswith("cat!custom") and message.author.id == OWNER_ID:
        stuff = text.split(" ")
        user, _ = User.get_or_create(user_id=stuff[1])
        if stuff[2] != "None" and message.reference and message.reference.message_id:
            emoji_name = "".join(stuff[2:]).lower() + "cat"
            if emoji_name in emojis.keys():
                await message.reply("emoji already exists")
                return
            og_msg = await message.channel.fetch_message(message.reference.message_id)
            if not og_msg or len(og_msg.attachments) == 0:
                await message.reply("no image found")
                return
            img_data = await og_msg.attachments[0].read()

            img = Image.open(io.BytesIO(img_data))
            img.thumbnail((128, 128))
            with io.BytesIO() as image_binary:
                img.save(image_binary, format="PNG")
                image_binary.seek(0)
                await bot.create_application_emoji(name=emoji_name, image=image_binary.getvalue())

        user.custom = " ".join(stuff[2:]) if stuff[2] != "None" else ""
        emojis = {emoji.name: str(emoji) for emoji in await bot.fetch_application_emojis()}
        user.save()
        await message.reply("success")



# the message when cat gets added to a new server
async def on_guild_join(guild):
    def verify(ch):
        return ch and ch.permissions_for(guild.me).send_messages

    def find(patt, channels):
        for i in channels:
            if patt in i.name:
                return i

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
            await ch.send(unofficial_note + "Thanks for adding me!\nTo start, use `/help`!\nJoin the support server here: https://discord.gg/staring\nHave a nice day :)")
    except Exception:
        pass


@bot.tree.command(description="Learn to use the bot")
async def help(message):
    embed1 = discord.Embed(
        title = "How to Setup",
        description = "Server moderator (anyone with *Manage Server* permission) needs to run `/setup` in any channel. After that, cats will start to spawn in 2-20 minute intervals inside of that channel.\nYou can customize those intervals with `/changetimings` and change the spawn message with `/changemessage`.\nCat spawns can also be forced by moderators using `/forcespawn` command.\nYou can have unlimited amounts of setupped channels at once.\nYou can stop the spawning in a channel by running `/forget`.",
        color = 0x6E593C
    ).set_thumbnail(url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png")

    embed2 = discord.Embed(
        title="How to Play",
        color=0x6E593C
    ).add_field(
        name="Catch Cats",
        value="Whenever a cat spawns you will see a message along the lines of \"a cat has appeared\", which will also display it's type.\nCat types can have varying rarities from 25% for Fine to hundredths of percent for rarest types.\nSo, after saying \"cat\" the cat will be added to your inventory.",
        inline=False
    ).add_field(
        name="Viewing Your Inventory",
        value="You can view your (or anyone elses!) inventory using `/inventory` command. It will display all the cats, along with other stats.\nIt is important to note that you have a separate inventory in each server and nothing carries over, to make the experience more fair and fun.\nCheck out the leaderboards for your server by using `/leaderboards` command.\nIf you want to transfer cats, you can use the simple `/gift` or more complex `/trade` commands.",
        inline=False
    ).add_field(
        name="Let's get funky!",
        value="Cat Bot has various other mechanics to make fun funnier. You can collect various `/achievements`, for example saying \"i read help\", progress in the `/battlepass`, or have beef with the mafia over cataine addiction. The amount you worship is the limit!",
        inline=False
    ).add_field(
        name="Other features",
        value="Cat Bot has extra fun commands which you will discover along the way.\nAnything unclear? Drop us a line at our [Discord server](https://discord.gg/staring).",
        inline=False
    ).set_footer(
        text=f"Cat Bot by Milenakos, {datetime.datetime.now().year}",
        icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png"
    )

    await message.response.send_message(embeds=[embed1, embed2])


@bot.tree.command(description="View information about the bot")
async def info(message: discord.Interaction):
    global gen_credits

    if not gen_credits:
        await message.response.send_message("credits not yet ready! this is a very rare error, congrats.", ephemeral=True)
        return

    await message.response.defer()

    embedVar = discord.Embed(title="Cat Bot", color=0x6E593C, description="[Join support server](https://discord.gg/staring)\n[GitHub Page](https://github.com/milenakos/cat-bot)\n\n" + \
                             f"by {gen_credits['author']}\nWith contributions from {gen_credits['contrib']}.\n\nThis bot adds Cat Hunt to your server with many different types of cats for people to discover! People can see leaderboards and give cats to each other.\n\n" + \
                             f"Thanks to:\n**pathologicals** for the cat image\n**thecatapi.com** for random cats API\n**catfact.ninja** for cat facts API\n**countik** for TikTok TTS API\n**{gen_credits['trash']}** for making cat, suggestions, and a lot more.\n\n**{gen_credits['tester']}** for being test monkeys\n\n**And everyone for the support!**"
                            ).set_thumbnail(url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png")

    # add "last update" to footer if we are using git
    if config.GITHUB_CHANNEL_ID:
        embedVar.timestamp = datetime.datetime.fromtimestamp(int(subprocess.check_output(["git", "show", "-s", "--format=%ct"]).decode("utf-8")))
        embedVar.set_footer(text="Last code update:")
    await message.followup.send(embed=embedVar)


@bot.tree.command(description="Read The Cat Bot Times™️")
async def news(message: discord.Interaction):
    user, _ = User.get_or_create(user_id=message.user.id)
    buttons = []
    current_state = user.news_state.strip()

    for num, article in enumerate(news_list):
        try:
            have_read_this = False if current_state[num] == "0" else True
        except Exception:
            have_read_this = False
        button = Button(label=article["title"], emoji=article["emoji"], custom_id=f"{num} {message.user.id}", style=ButtonStyle.green if not have_read_this else ButtonStyle.gray)
        button.callback = send_news
        buttons.append(button)

    buttons = buttons[::-1]  # reverse the list so the first button is the most recent article

    if len(news_list) > len(current_state):
        user.news_state = current_state + "0" * (len(news_list) - len(current_state))
        user.save()

    current_page = 0

    async def prev_page(interaction):
        nonlocal current_page
        if interaction.user.id == message.user.id:
            current_page -= 1
            await interaction.response.edit_message(view=generate_page(current_page))
        else:
            await do_funny(interaction)

    async def next_page(interaction):
        nonlocal current_page
        if interaction.user.id == message.user.id:
            current_page += 1
            await interaction.response.edit_message(view=generate_page(current_page))
        else:
            await do_funny(interaction)

    def generate_page(number):
        view = View(timeout=3600)

        # article buttons
        for num, button in enumerate(buttons[number * 4:(number + 1) * 4]):
            button.row = num
            view.add_item(button)

        # pages buttons
        button = Button(label="<-", style=ButtonStyle.gray, disabled=bool(current_page == 0), row=4)
        button.callback = prev_page
        view.add_item(button)

        button = Button(label=f"Page {current_page + 1}", style=ButtonStyle.gray, disabled=True, row=4)
        view.add_item(button)

        button = Button(label="->", style=ButtonStyle.gray, disabled=bool(current_page * 4 + 4 >= len(buttons)), row=4)
        button.callback = next_page
        view.add_item(button)

        return view


    await message.response.send_message("Choose an article:", view=generate_page(current_page))
    await achemb(message, "news", "send")


@bot.tree.command(description="Read text as TikTok's TTS woman")
@discord.app_commands.describe(text="The text to be read! (300 characters max)")
async def tiktok(message: discord.Interaction, text: str):
    if not message.channel.permissions_for(message.guild.me).attach_files:
        await message.response.send_message("i cant attach files here!", ephemeral=True)
        return

    # detect n-words
    for i in NONOWORDS:
        if i in text.lower():
            await message.response.send_message("Do not.", ephemeral=True)
            return

    await message.response.defer()

    if text == "bwomp":
        file = discord.File("bwomp.mp3", filename="bwomp.mp3")
        await message.followup.send(file=file)
        await achemb(message, "bwomp", "send")
        return

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post("https://countik.com/api/text/speech",
                                json={"text":text, "voice":"en_us_001"}) as response:
                stuff = await response.json()
                data = "" + stuff["v_data"]
                with io.BytesIO() as f:
                    ba = "data:audio/mpeg;base64," + data
                    f.write(base64.b64decode(ba))
                    f.seek(0)
                    await message.followup.send(file=discord.File(fp=f, filename='output.mp3'))
        except discord.NotFound:
            pass
        except Exception:
            await message.followup.send("i dont speak your language (remove non-english characters, make sure the message is below 300 chars)")


@bot.tree.command(description="(ADMIN) Prevent someone from catching cats for a certain time period")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(person="A person to timeout!", timeout="How many seconds? (0 to reset)")
async def preventcatch(message: discord.Interaction, person: discord.User, timeout: int):
    if timeout < 0:
        await message.response.send_message("uhh i think time is supposed to be a number", ephemeral=True)
        return
    user = get_profile(message.guild.id, person.id)
    timestamp = round(time.time()) + timeout
    user.timeout = timestamp
    user.save()
    await message.response.send_message(person.name.replace("_", r"\_") + (f" can't catch cats until <t:{timestamp}:R>" if timeout > 0 else " can now catch cats again."))


@bot.tree.command(description="(ADMIN) Change the cat appear timings")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(minimum_time="In seconds, minimum possible time between spawns (leave both empty to reset)",
                               maximum_time="In seconds, maximum possible time between spawns (leave both empty to reset)")
async def changetimings(message: discord.Interaction, minimum_time: Optional[int], maximum_time: Optional[int]):
    channel = Channel.get_or_none(channel_id=message.channel.id)
    if not channel:
        await message.response.send_message("This channel isnt setupped. Please select a valid channel.", ephemeral=True)
        return

    if not minimum_time and not maximum_time:
        # reset
        channel.spawn_times_min = 120
        channel.spawn_times_max = 1200
        channel.save()
        await message.response.send_message("Success! This channel is now reset back to usual spawning intervals.")
    elif minimum_time and maximum_time:
        if minimum_time < 20:
            await message.response.send_message("Sorry, but minimum time must be above 20 seconds.", ephemeral=True)
            return
        if maximum_time < minimum_time:
            await message.response.send_message("Sorry, but minimum time must be less than maximum time.", ephemeral=True)
            return

        channel.spawn_times_min = minimum_time
        channel.spawn_times_max = maximum_time
        channel.save()

        await message.response.send_message(f"Success! The next spawn will be {minimum_time} to {maximum_time} seconds from now.")
    else:
        await message.response.send_message("Please input all times.", ephemeral=True)


@bot.tree.command(description="(ADMIN) Change the cat appear and cought messages")
@discord.app_commands.default_permissions(manage_guild=True)
async def changemessage(message: discord.Interaction):
    caller = message.user
    channel = Channel.get_or_none(channel_id=message.channel.id)
    if not channel:
        await message.response.send_message("pls setup this channel first", ephemeral=True)
        return

    # this is the silly popup when you click the button
    class InputModal(discord.ui.Modal):
        def __init__(self, type):
            super().__init__(
                title=f"Change {type} Message",
                timeout=3600,
            )

            self.type = type

            self.input = discord.ui.TextInput(
                min_length=0,
                max_length=1000,
                label="Input",
                style=discord.TextStyle.long,
                required=False,
                placeholder="{emoji} {type} has appeared! Type \"cat\" to catch it!",
                default=channel.appear if self.type == "Appear" else channel.cought
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
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
                await interaction.response.send_message("Success! Here is a preview:\n" + \
                    input_value.replace("{emoji}", str(icon)).replace("{type}", "Fine").replace("{username}", "Cat Bot").replace("{count}", "1").replace("{time}", "69 years 420 days"))
            else:
                await interaction.response.send_message("Reset to defaults.")

            if self.type == "Appear":
                channel.appear = input_value
            else:
                channel.cought = input_value

            channel.save()

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

    embed = discord.Embed(title="Change appear and cought messages", description="""below are buttons to change them.
they are required to have all placeholders somewhere in them.
that being:

for appear:
`{emoji}`, `{type}`

for cought:
`{emoji}`, `{type}`, `{username}`, `{count}`, `{time}`

missing any of these will result in a failure.
leave blank to reset.""", color=0x6E593C)

    button1 = Button(label="Appear Message", style=ButtonStyle.blurple)
    button1.callback = ask_appear

    button2 = Button(label="Catch Message", style=ButtonStyle.blurple)
    button2.callback = ask_catch

    view = View(timeout=3600)
    view.add_item(button1)
    view.add_item(button2)

    await message.response.send_message(embed=embed, view=view)


@bot.tree.command(description="Get Daily cats")
async def daily(message: discord.Interaction):
    suffix = "\nthere ARE cats for voting tho, check out `/vote`" if config.WEBHOOK_VERIFY else ""
    await message.response.send_message("there is no daily cats why did you even try this" + suffix)
    await achemb(message, "daily", "send")


@bot.tree.command(description="View when the last cat was caught in this channel, and when the next one might spawn")
async def last(message: discord.Interaction):
    channel = Channel.get_or_none(channel_id=message.channel.id)
    nextpossible = ""

    try:
        lasttime = channel.lastcatches
        displayedtime = f"<t:{int(lasttime)}:R>"
    except Exception:
        displayedtime = "forever ago"

    if channel and not channel.cat:
        nextpossible = f"\nthe next cat will spawn between <t:{int(lasttime) + channel.spawn_times_min}:R> and <t:{int(lasttime) + channel.spawn_times_max}:R>"

    await message.response.send_message(f"the last cat in this channel was caught {displayedtime}.{nextpossible}")


async def gen_inventory(message, person_id):
    # check if we are viewing our own inv or some other person
    if person_id is None:
        me = True
        person_id = message.user
    else:
        me = False
    person = get_profile(message.guild.id, person_id.id)
    user, _ = User.get_or_create(user_id=person_id.id)

    # around here we count aches
    unlocked = 0
    minus_achs = 0
    minus_achs_count = 0
    for k in ach_names:
        if ach_list[k]["category"] == "Hidden":
            minus_achs_count += 1
        if person[k]:
            if ach_list[k]["category"] == "Hidden":
                minus_achs += 1
            else:
                unlocked += 1
    total_achs = len(ach_list) - minus_achs_count
    minus_achs = "" if minus_achs == 0 else f" + {minus_achs}"

    # now we count time i think
    catch_time = person.time
    is_empty = True

    catch_time = "---" if catch_time >= 99999999999999 else str(round(catch_time, 3))

    slow_time = person.timeslow

    if str(int(slow_time)) == "0":
        slow_time = "---"
    else:
        slow_time = float(slow_time) / 3600
        slow_time = str(round(slow_time, 2))

    # count prism stuff
    prisms = []
    prism_boost = 0
    for prism in Prism.select().where(Prism.guild_id == message.guild.id):
        if prism.user_id == person_id.id:
            prisms.append(prism.name)
            prism_boost += 5
        else:
            prism_boost += 1
    if len(prisms) == 0:
        prism_list = "None"
    elif len(prisms) <= 3:
        prism_list = ", ".join(prisms)
    else:
        prism_list = f"{prisms[0]}, {prisms[1]}, {len(prisms) - 2} more..."

    emoji_prefix = str(user.emoji) + " " if user.emoji else ""

    if user.color:
        color = user.color
    else:
        color = "#6E593C"

    embedVar = discord.Embed(
        title=f"{emoji_prefix}{person_id.name}",
        description=f"⏱️ Fastest: {catch_time}s, Slowest: {slow_time}h\n{get_emoji('cat_throphy')} Achievements: {unlocked}/{total_achs}{minus_achs}",
        color=discord.Colour.from_str(color)
    )

    give_collector = True
    total = 0
    valuenum = 0

    # for every cat
    for i in cattypes:
        icon = get_emoji(i.lower() + "cat")
        cat_num = person[f"cat_{i}"]
        if cat_num != 0:
            total += cat_num
            valuenum += (len(CAT_TYPES) / type_dict[i]) * cat_num
            embedVar.add_field(name=f"{icon} {i}", value=f"{cat_num:,}", inline=True)
            is_empty = False
        else:
            give_collector = False

    if user.custom:
        icon = get_emoji(user.custom.lower().replace(" ", "") + "cat")
        embedVar.add_field(name=f"{icon} {user.custom}", value=1, inline=True)

    if is_empty and not user.custom:
        embedVar.add_field(name="None", value=f"u hav no cats {get_emoji('cat_cry')}", inline=True)

    if embedVar.description:
        embedVar.description += f"\n{get_emoji('staring_cat')} Cats: {total:,}, Value: {round(valuenum):,}\n{get_emoji('prism')} Prisms: {prism_list} ({prism_boost}%)"

    if user.image.startswith("https://cdn.discordapp.com/attachments/"):
        embedVar.set_thumbnail(url=user.image)

    if me:
        # give some aches if we are vieweing our own inventory
        global_user, _ = User.get_or_create(user_id=message.user.id)
        if len(news_list) > len(global_user.news_state.strip()) or "0" in global_user.news_state:
            embedVar.set_author(name="You have unread news! /news")

        if give_collector:
            await achemb(message, "collecter", "send")

        if person.time <= 5:
            await achemb(message, "fast_catcher", "send")
        if person.timeslow >= 3600:
            await achemb(message, "slow_catcher", "send")

        if total >= 100:
            await achemb(message, "second", "send")
        if total >= 1000:
            await achemb(message, "third", "send")
        if total >= 10000:
            await achemb(message, "fourth", "send")

        if unlocked >= 15:
            await achemb(message, "achiever", "send")

    return embedVar


@bot.tree.command(description="View your inventory")
@discord.app_commands.rename(person_id='user')
@discord.app_commands.describe(person_id="Person to view the inventory of!")
async def inventory(message: discord.Interaction, person_id: Optional[discord.User]):
    await message.response.defer()
    embedVar = await gen_inventory(message, person_id)
    embedVar.set_footer(text="☔ Get tons of cats /rain")
    await message.followup.send(embed=embedVar)


@bot.tree.command(description="its raining cats")
async def rain(message: discord.Interaction):
    user, _ = User.get_or_create(user_id=message.user.id)

    if not user.rain_minutes:
        user.rain_minutes = 0
        user.save()

    if not user.claimed_free_rain:
        user.rain_minutes += 2
        user.claimed_free_rain = True
        user.save()

    # this is the silly popup when you click the button
    class RainModal(discord.ui.Modal):
        def __init__(self, type):
            super().__init__(
                title="Start a Cat Rain!",
                timeout=3600,
            )

            self.input = discord.ui.TextInput(
                min_length=1,
                max_length=2,
                label="Duration in minutes",
                style=discord.TextStyle.short,
                required=True,
                placeholder="2"
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
            try:
                duration = int(self.input.value)
            except Exception:
                await interaction.response.send_message("number pls", ephemeral=True)
                return
            await do_rain(interaction, duration)


    embed = discord.Embed(title="Cat Rains", description=f"""Cat Rains are power-ups which spawn cats instantly for a limited amounts of time in channel of your choice.

You can get those by buying them at our [store](<https://catbot.minkos.lol/store>) or by winning them in an event.
This bot is developed by a single person so buying one would be very appreciated.
As a bonus, you will get access to /editprofile command!
Fastest times are not saved during rains.

You currently have **{user.rain_minutes}** minutes of rains.""", color=0x6E593C)

    async def do_rain(interaction, rain_length):
        # i LOOOOVE checks
        user, _ = User.get_or_create(user_id=interaction.user.id)

        if not user.rain_minutes:
            user.rain_minutes = 0
            user.save()

        if not user.claimed_free_rain:
            user.rain_minutes += 2
            user.claimed_free_rain = True
            user.save()

        if rain_length < 1 or rain_length > 60:
            await interaction.response.send_message("pls input a number 1-60", ephemeral=True)
            return

        if rain_length > user.rain_minutes:
            await interaction.response.send_message("you dont have enough rain! buy some more [here](<https://catbot.minkos.lol/store>)", ephemeral=True)
            return

        if about_to_stop:
            await interaction.response.send_message("cat bot is currently restarting. please try again in a few seconds.", ephemeral=True)
            return

        channel = Channel.get_or_none(channel_id=message.channel.id)
        if not channel:
            await interaction.response.send_message("please run this in a setupped channel.", ephemeral=True)
            return

        if channel.cat:
            await interaction.response.send_message("please catch the cat in this channel first.", ephemeral=True)
            return

        if cat_rains.get(str(message.channel.id), 0) != 0 or message.channel.id in temp_rains_storage:
            await interaction.response.send_message("there is already a rain running!", ephemeral=True)
            return

        channel_permissions = message.channel.permissions_for(message.guild.me)
        needed_perms = {
            "View Channel": channel_permissions.view_channel,
            "Manage Webhooks": channel_permissions.manage_webhooks,
            "Send Messages": channel_permissions.send_messages,
            "Attach Files": channel_permissions.attach_files,
            "Use External Emojis": channel_permissions.use_external_emojis,
            "Read Message History": channel_permissions.read_message_history
        }
        if isinstance(message.channel, discord.Thread):
            needed_perms["Send Messages in Threads"] = channel_permissions.send_messages_in_threads

        for name, value in needed_perms.copy().items():
            if value:
                needed_perms.pop(name)

        missing_perms = list(needed_perms.keys())
        if len(missing_perms) != 0:
            await interaction.response.send_message(f":x: Missing Permissions! Please give me the following:\n- {'\n- '.join(missing_perms)}\nHint: try setting channel permissions if server ones don't work.")
            return

        if not isinstance(message.channel, Union[discord.TextChannel, discord.StageChannel, discord.VoiceChannel, discord.Thread]):
            return

        cat_rains[str(message.channel.id)] = time.time() + (rain_length * 60)
        await spawn_cat(str(message.channel.id))
        user.rain_minutes -= rain_length
        user.save()
        await interaction.response.send_message(f"{rain_length}m cat rain was started by <@{interaction.user.id}>!")

    async def rain_modal(interaction):
        modal = RainModal(interaction.user)
        await interaction.response.send_modal(modal)

    button = Button(label="Rain!", style=ButtonStyle.blurple)
    button.callback = rain_modal

    shopbutton = Button(emoji="🛒", label="Store", style=ButtonStyle.gray, url="https://catbot.minkos.lol/store")

    view = View(timeout=3600)
    view.add_item(button)
    view.add_item(shopbutton)

    await message.response.send_message(embed=embed, view=view)


@bot.tree.command(description="Buy Cat Rains!")
async def store(message: discord.Interaction):
    await message.response.send_message("☔ Cat rains make cats spawn instantly! Make your server active, get more cats and have fun!\n<https://catbot.minkos.lol/store>")


if config.DONOR_CHANNEL_ID:
    @bot.tree.command(description="[SUPPORTER] Customize your profile!")
    @discord.app_commands.rename(provided_emoji='emoji')
    @discord.app_commands.describe(color="Color for your profile in hex form (e.g. #6E593C)",
                                provided_emoji="A default Discord emoji to show near your username.",
                                image="A square image to show in top-right corner of your profile.")
    async def editprofile(message: discord.Interaction, color: Optional[str], provided_emoji: Optional[str], image: Optional[discord.Attachment]):
        if not config.DONOR_CHANNEL_ID:
            return

        user, _ = User.get_or_create(user_id=message.user.id)
        if not user.premium:
            await message.response.send_message("👑 This feature is supporter-only!\nBuy anything from Cat Bot Store to unlock profile customization!\n<https://catbot.minkos.lol/store>")
            return

        if provided_emoji and discord_emoji.to_discord(provided_emoji.strip(), get_all=False, put_colons=False):
            user.emoji = provided_emoji.strip()

        if color:
            match = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color)
            if match:
                user.color = match.group(0)
        if image:
            # reupload image
            channeley = bot.get_channel(config.DONOR_CHANNEL_ID)
            file = await image.to_file()
            if not isinstance(channeley, Union[discord.TextChannel, discord.StageChannel, discord.VoiceChannel, discord.Thread]):
                raise ValueError
            msg = await channeley.send(file=file)
            user.image = msg.attachments[0].url
        user.save()
        embedVar = await gen_inventory(message, message.user)
        await message.response.send_message("Success! Here is a preview:", embed=embedVar)


@bot.tree.command(description="I like fortnite")
async def battlepass(message: discord.Interaction):
    await message.response.defer()

    user = get_profile(message.guild.id, message.user.id)

    current_level = user.battlepass
    embedVar = discord.Embed(title="Cattlepass™", description="who thought this was a good idea", color=0x6E593C)

    # this basically generates a single level text (we have 3 of these)
    def battlelevel(levels, id, home=False):
        nonlocal message
        searching = levels["levels"][id]
        req = searching["req"]
        num = searching["req_data"]
        thetype = searching["reward"]
        amount = searching["reward_amount"]

        if thetype == "Prisms":
            icon = get_emoji("prism")
        else:
            icon = get_emoji(thetype.lower() + "cat")

        if req == "catch":
            num_str = num
            if home:
                progress = int(user.progress)
                num_str = f"{num - progress} more"
            return f"Catch {num_str} cats\nReward: {amount} {icon} {thetype} cats"
        elif req == "catch_fast":
            if thetype == "Prisms":
                return f"Catch a cat in under {num} seconds\nReward: {icon} Prism Crafting Recipe"
            else:
                return f"Catch a cat in under {num} seconds\nReward: {amount} {icon} {thetype} cats"
        elif req == "catch_type":
            an = ""
            if num[0].lower() in "aieuo":
                an = "n"
            return f"Catch a{an} {num} cat\nReward: {amount} {icon} {thetype} cats"
        elif req == "nothing":
            return "Touch grass\nReward: 1 ~~e~~Girl~~cats~~friend"
        else:
            return "Complete a battlepass level\nReward: freedom"

    if current_level == len(battle["levels"]):
        embedVar.add_field(name=f"✅ Level {current_level - 2} (complete)", value=battlelevel(battle, current_level - 3), inline=False)
        embedVar.add_field(name=f"✅ Level {current_level - 1} (complete)", value=battlelevel(battle, current_level - 2), inline=False)
        embedVar.add_field(name=f"✅ Level {current_level} (complete)", value=battlelevel(battle, current_level - 1), inline=False)
    else:
        current = "🟨"
        if battle["levels"][current_level]["req"] == "nothing":
            current = "⬛"
        if current_level != 0:
            embedVar.add_field(name=f"✅ Level {current_level} (complete)", value=battlelevel(battle, current_level - 1), inline=False)
        embedVar.add_field(name=f"{current} Level {current_level + 1}", value=battlelevel(battle, current_level, True), inline=False)
        embedVar.add_field(name=f"Level {current_level + 2}", value=battlelevel(battle, current_level + 1), inline=False)

    await message.followup.send(embed=embedVar)


@bot.tree.command(description="cat prisms are a special power up")
async def prism(message: discord.Interaction):
    user = get_profile(message.guild.id, message.user.id)

    icon = get_emoji("prism")

    embed = discord.Embed(
        title=f"{icon} Cat Prisms",
        color=0x6E593C,
        description="are a tradeable power-up which occasionally bumps cat rarity up by one. For each prism in the server you get 1% chance of activation, or 5% if you are the owner of that prism. There is a limit of 25 prisms per server and 5 per person."
    )

    global_boost = 0
    user_boost = 0
    user_count = 0
    owned_prisms = []
    owned_prisms_name = [] # i sleepy and dunno any better
    selected_prism = None

    for prism in Prism.select().where(Prism.guild_id == message.guild.id).order_by(Prism.name):
        global_boost += 1
        if prism.user_id == message.user.id:
            owned_prisms.append(prism)
            owned_prisms_name.append(prism.name)
            user_boost += 5
            user_count += 1
        else:
            user_boost += 1
        embed.add_field(
            name=f"{icon} {prism.name}",
            value=f"Owner: <@{prism.user_id}>\nCrafted by <@{prism.creator}>\non <t:{prism.time}:D>",
            inline=True
        )

    embed.set_footer(text=f"Boost for everyone: {global_boost}% | {message.user}'s total boost: {user_boost}%")

    async def confirm_craft(interaction: discord.Interaction):
        await interaction.response.defer()
        user = get_profile(message.guild.id, message.user.id)

        # check we still can craft
        for i in cattypes:
            if user["cat_" + i] < 1:
                await interaction.followup.send("You don't have enough cats. Nice try though.", ephemeral=True)
                return

        # couunt how many prisms we have
        prism_count = 0
        for prism in Prism.select().where((Prism.guild_id == message.guild.id) & (Prism.user_id == message.user.id)):
            prism_count += 1
        if prism_count >= 5:
            await interaction.followup.send("You already have 5 prisms. Nice try though.", ephemeral=True)
            return

        if not isinstance(message.channel, Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.Thread]):
            return

        # determine the next name
        youngest_prism = Prism.select().where(Prism.guild_id == message.guild.id).order_by(Prism.time.desc()).limit(1)
        if youngest_prism.exists():
            try:
                selected_name = prism_names[prism_names.index(youngest_prism.get().name) + 1]
            except IndexError:
                await interaction.followup.send("This server has reached the prism limit.", ephemeral=True)
                return
        else:
            selected_name = prism_names[0]

        # actually take away cats
        for i in cattypes:
            user["cat_" + i] -= 1
        user.save()

        # create the prism
        Prism.create(
            guild_id=message.guild.id,
            user_id=message.user.id,
            creator=message.user.id,
            time=round(time.time()),
            name=selected_name
        )
        await message.followup.send(f"{icon} <@{message.user.id}> has created prism {selected_name}!")
        await achemb(message, "prism", "send")


    async def craft_prism(interaction: discord.Interaction):
        if interaction.user.id == message.user.id:
            user = get_profile(message.guild.id, message.user.id)

            missing_cats = []
            for i in cattypes:
                if user["cat_" + i] < 1:
                    missing_cats.append(get_emoji(i.lower() + "cat"))

            if len(missing_cats) == 0:
                view = View(timeout=3600)
                confirm_button = Button(label="Craft!", style=ButtonStyle.green, emoji=icon)
                confirm_button.callback = confirm_craft
                description = "The crafting recipe is __ONE of EVERY cat type__.\nContinue crafting?"
            else:
                view = View(timeout=1)
                confirm_button = Button(label="Not enough cats!", style=ButtonStyle.red, disabled=True)
                description = "The crafting recipe is __ONE of EVERY cat type__.\nYou are missing " + "".join(missing_cats)

            view.add_item(confirm_button)
            await interaction.response.send_message(description, view=view, ephemeral=True)
        else:
            await do_funny(interaction)


    def prism_config_embed(selected_prism):
        embedVar = discord.Embed(title=f"Configure {selected_prism.name}", color=0x6E593C)
        embedVar.description = "Turn off any boosts from your prism that you don't want\n\n__Upgrades from:__\n"
        for i in cattypes:
            icon1 = get_emoji(i.lower() + "cat")
            enabled = "✅" if selected_prism[f"enabled_{i.lower()}"] else "❌"
            embedVar.description += f"{enabled} {icon1} {i}\n"

        view = View(timeout=3600)
        edit_button = Button(label="Edit", style=ButtonStyle.blurple)
        edit_button.callback = editb
        view.add_item(edit_button)
        return embedVar, view

    async def configb(interaction):
        if interaction.user.id == message.user.id:
            modal = PrismModal()
            await interaction.response.send_modal(modal)
        else:
            await do_funny(interaction)

    class PrismModal(discord.ui.Modal):
        def __init__(self):
            super().__init__(
                title="Configure a Prism",
                timeout=3600,
            )

            self.prismname = discord.ui.TextInput(
                label="Prism to configure:",
                placeholder="Alpha"
            )
            self.add_item(self.prismname)

        async def on_submit(self, interaction: discord.Interaction):
            nonlocal owned_prisms, owned_prisms_name, selected_prism
            if self.prismname.value not in owned_prisms_name:
                await interaction.response.send_message("you dont even have that prism what", ephemeral=True)
                return

            # i ask for forgiveness
            for prism in owned_prisms:
                if prism.name == self.prismname.value:
                    selected_prism = prism

            if not selected_prism:
                await interaction.response.send_message("you dont even have that prism what", ephemeral=True)
                return

            embedVar, view = prism_config_embed(selected_prism)
            await interaction.response.send_message(embed=embedVar, view=view)

    async def editb(interaction):
        if interaction.user.id == message.user.id:
            modal = EditModal()
            await interaction.response.send_modal(modal)
        else:
            await do_funny(interaction)

    class EditModal(discord.ui.Modal):
        def __init__(self):
            super().__init__(
                title="Toggle a Boost",
                timeout=3600,
            )

            self.toggletype = discord.ui.TextInput(
                label="Boost to toggle:",
                placeholder="Fine"
            )
            self.add_item(self.toggletype)

        async def on_submit(self, interaction: discord.Interaction):
            nonlocal owned_prisms, owned_prisms_name, selected_prism
            await interaction.response.defer(ephemeral=True)
            if not selected_prism or selected_prism.user_id != interaction.user.id:
                await interaction.followup.send("you dont even have that prism what", ephemeral=True)
                return
            if self.toggletype.value not in cattypes:
                await interaction.followup.send("you cant toggle that", ephemeral=True)
                return
            selected_prism[f"enabled_{self.toggletype.value.lower()}"] = not selected_prism[f"enabled_{self.toggletype.value.lower()}"]
            selected_prism.save()

            embedVar, view = prism_config_embed(selected_prism)
            await interaction.edit_original_response(embed=embedVar, view=view)

    view = View(timeout=3600)
    if global_boost >= 25 or user_count >= 5:
        craft_button = Button(label="Prism limit reached!", style=ButtonStyle.gray, disabled=True)
    elif user.battlepass >= 30:
        craft_button = Button(label="Craft!", style=ButtonStyle.blurple, emoji=icon)
        craft_button.callback = craft_prism
    else:
        craft_button = Button(label="Battlepass 30 needed to craft!", style=ButtonStyle.blurple, disabled=True)

    if len(owned_prisms) == 0:
        config_button = Button(label="No prisms to configure!", style=ButtonStyle.gray, disabled=True)
    else:
        await achemb(message, "prism", "send")
        config_button = Button(label="Configure", style=ButtonStyle.blurple)
        config_button.callback = configb

    view.add_item(craft_button)
    view.add_item(config_button)
    await message.response.send_message(embed=embed, view=view)


@bot.tree.command(description="Pong")
async def ping(message: discord.Interaction):
    try:
        latency = round(bot.latency * 1000)
    except Exception:
        latency = "infinite"
    await message.response.send_message(f"cat has brain delay of {latency} ms " + str(get_emoji("staring_cat")))

    if latency == "infinite" or latency >= 100:
        await achemb(message, "infinite", "send")


@bot.tree.command(description="give cats now")
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(person="Whom to gift?", cat_type="im gonna airstrike your house from orbit", amount="And how much?")
@discord.app_commands.autocomplete(cat_type=gift_autocomplete)
async def gift(message: discord.Interaction, person: discord.User, cat_type: str, amount: Optional[int]):
    if amount is None:
        # default the amount to 1
        amount = 1
    person_id = person.id

    if amount <= 0 or message.user.id == person_id:
        # haha skill issue
        await message.response.send_message("no", ephemeral=True)
        if message.user.id == person_id:
            await achemb(message, "lonely", "send")
        return

    if cat_type in cattypes:
        user = get_profile(message.guild.id, message.user.id)
        # if we even have enough cats
        if user[f"cat_{cat_type}"] >= amount:
            reciever = get_profile(message.guild.id, person_id)
            user[f"cat_{cat_type}"] -= amount
            reciever[f"cat_{cat_type}"] += amount
            user.save()
            reciever.save()
            embed = discord.Embed(title="Success!", description=f"Successfully transfered {amount:,} {cat_type} cats from <@{message.user.id}> to <@{person_id}>!", color=0x6E593C)

            # handle tax
            if amount >= 5:
                tax_amount = round(amount * 0.2)

                async def pay(interaction):
                    if interaction.user.id == message.user.id:
                        try:
                            await interaction.response.defer()
                            user = get_profile(message.guild.id, message.user.id)
                            catbot = get_profile(message.guild.id, bot.user.id)

                            # transfer tax
                            user[f"cat_{cat_type}"] -= tax_amount
                            catbot[f"cat_{cat_type}"] += tax_amount

                            try:
                                await interaction.edit_original_response(view=None)
                            except Exception:
                                pass
                            await interaction.followup.send(f"Tax of {tax_amount:,} {cat_type} cats was withdrawn from your account!")
                            await achemb(message, "good_citizen", "send")
                        finally:
                            # always save to prevent issue with exceptions leaving bugged state
                            user.save()
                            catbot.save()
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
                        await achemb(message, "secret", "send")
                    else:
                        await do_funny(interaction)

                button = Button(label="Pay 20% tax", style=ButtonStyle.green)
                button.callback = pay

                button2 = Button(label="Evade the tax", style=ButtonStyle.red)
                button2.callback = evade

                myview = View(timeout=3600)

                myview.add_item(button)
                myview.add_item(button2)

                await message.response.send_message(embed=embed, view=myview)
            else:
                await message.response.send_message(embed=embed)

            # handle aches
            await achemb(message, "donator", "send")
            await achemb(message, "anti_donator", "send", person)
            if person_id == bot.user.id and cat_type == "Ultimate" and int(amount) >= 5:
                await achemb(message, "rich", "send")
            if person_id == bot.user.id:
                await achemb(message, "sacrifice", "send")
            if cat_type == "Nice" and int(amount) == 69:
                await achemb(message, "nice", "send")
        else:
            await message.response.send_message("no", ephemeral=True)
    elif cat_type.lower() == "rain":
        if person_id == bot.user.id:
            await message.response.send_message("you can't sacrifice rains", ephemeral=True)
            return

        actual_user, _ = User.get_or_create(user_id=message.user.id)
        actual_receiver, _ = User.get_or_create(user_id=person_id)
        if actual_user.rain_minutes >= amount:
            actual_user.rain_minutes -= amount
            actual_receiver.rain_minutes += amount
            actual_user.save()
            actual_receiver.save()
            embed = discord.Embed(title="Success!", description=f"Successfully transfered {amount:,} minutes of rain from <@{message.user.id}> to <@{person_id}>!", color=0x6E593C)

            # handle tax
            if amount >= 5:
                tax_amount = round(amount * 0.2)

                async def confirm_pay(interaction):
                    if interaction.user.id == message.user.id:
                        await interaction.response.defer()

                        confirm = Button(label="Yes, pay the tax")
                        confirm.callback = pay
                        confirm_view = View(timeout=3600)
                        confirm_view.add_item(confirm)

                        await interaction.followup.send(f"Are you really sure you want to pay the tax? {tax_amount:,} minutes of rain will be lost forever...", view=confirm_view)
                    else:
                        await do_funny(interaction)

                async def pay(interaction):
                    if interaction.user.id == message.user.id:
                        try:
                            await interaction.response.defer()
                            actual_user = User.get(user_id=message.user.id)

                            # remove tax, don't transfer rain to cat bot because it makes no sense
                            actual_user.rain_minutes -= tax_amount
                            if actual_user.rain_minutes < 0:
                                # negative rain could cause other bugs
                                actual_user.rain_minutes = 0

                            try:
                                await interaction.edit_original_response(view=None)
                            except Exception:
                                pass
                            await interaction.followup.send(f"Tax of {tax_amount:,} rain minutes was withdrawn from your account!")
                            await achemb(message, "good_citizen", "send")
                        finally:
                            # always save to prevent issue with exceptions leaving bugged state
                            actual_user.save()
                    else:
                        await do_funny(interaction)

                async def evade(interaction):
                    if interaction.user.id == message.user.id:
                        await interaction.response.defer()
                        try:
                            await interaction.edit_original_response(view=None)
                        except Exception:
                            pass
                        await interaction.followup.send(f"You evaded the tax of {tax_amount:,} rain minutes.")
                        await achemb(message, "secret", "send")
                    else:
                        await do_funny(interaction)

                button = Button(label="Pay 20% tax", style=ButtonStyle.green)
                button.callback = confirm_pay

                button2 = Button(label="Evade the tax", style=ButtonStyle.red)
                button2.callback = evade

                myview = View(timeout=3600)

                myview.add_item(button)
                myview.add_item(button2)

                await message.response.send_message(embed=embed, view=myview)
            else:
                await message.response.send_message(embed=embed)

            # handle aches
            await achemb(message, "donator", "send")
            await achemb(message, "anti_donator", "send", person)
        else:
            await message.response.send_message("no", ephemeral=True)
    else:
        await message.response.send_message("bro what", ephemeral=True)


@bot.tree.command(description="Trade cats!")
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

    user1 = get_profile(message.guild.id, person1.id)
    user2 = get_profile(message.guild.id, person2.id)

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
            await interaction.edit_original_response(content=f"<@{interaction.user.id}> has cancelled the trade.", embed=None, view=None)
        except Exception:
            pass

    # this is the accept button code
    async def acceptb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, person1value, person2value, user1, user2
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
            await achemb(message, "desperate", "send")

        if person1accept and person2accept:
            user1 = get_profile(message.guild.id, person1.id)
            user2 = get_profile(message.guild.id, person2.id)
            actual_user1, _ = User.get_or_create(user_id=person1.id)
            actual_user2, _ = User.get_or_create(user_id=person2.id)

            # check if we have enough things (person could have moved them during the trade)
            error = False
            person1prismgive = 0
            person2prismgive = 0
            for k, v in person1gives.items():
                if k in prism_names:
                    person1prismgive += 1
                    prism = Prism.get(guild_id=interaction.guild.id, name=k)
                    if prism.user_id != person1.id:
                        error = True
                        break
                    continue
                elif k == "rains":
                    if actual_user1.rain_minutes < v:
                        error = True
                        break
                elif user1[f"cat_{k}"] < v:
                    error = True
                    break

            for k, v in person2gives.items():
                if k in prism_names:
                    person2prismgive += 1
                    prism = Prism.get(guild_id=interaction.guild.id, name=k)
                    if prism.user_id != person2.id:
                        error = True
                        break
                    continue
                elif k == "rains":
                    if actual_user2.rain_minutes < v:
                        error = True
                        break
                elif user2[f"cat_{k}"] < v:
                    error = True
                    break

            person1prismcount = len(Prism.select().where(Prism.guild_id == message.guild.id, Prism.user_id == person1.id))
            person2prismcount = len(Prism.select().where(Prism.guild_id == message.guild.id, Prism.user_id == person2.id))

            if person1prismcount + person2prismgive > 5:
                await interaction.edit_original_response(content=f"<@{person1.id}> reached the prism limit. trade cancelled.", embed=None, view=None)
                return
            if person2prismcount + person1prismgive > 5:
                await interaction.edit_original_response(content=f"<@{person2.id}> reached the prism limit. trade cancelled.", embed=None, view=None)
                return

            if error:
                try:
                    await interaction.edit_original_response(content="Uh oh - some of the cats/prisms/rains disappeared while trade was happening", embed=None, view=None)
                except Exception:
                    await interaction.followup.send("Uh oh - some of the cats/prisms/rains disappeared while trade was happening")
                return

            # exchange
            cat_count = 0
            for k, v in person1gives.items():
                if k in prism_names:
                    Prism.update(user_id=person2.id).where(Prism.guild_id == message.guild.id, Prism.name == k).execute()
                    cat_count += 1
                    continue
                if k == "rains":
                    actual_user1.rain_minutes -= v
                    actual_user2.rain_minutes += v
                    continue
                cat_count += v
                user1[f"cat_{k}"] -= v
                user2[f"cat_{k}"] += v

            for k, v in person2gives.items():
                if k in prism_names:
                    Prism.update(user_id=person1.id).where(Prism.guild_id == message.guild.id, Prism.name == k).execute()
                    cat_count += 1
                    continue
                if k == "rains":
                    actual_user2.rain_minutes -= v
                    actual_user1.rain_minutes += v
                    continue
                cat_count += v
                user1[f"cat_{k}"] += v
                user2[f"cat_{k}"] -= v

            user1.save()
            user2.save()
            actual_user1.save()
            actual_user2.save()

            try:
                await interaction.edit_original_response(content="Trade finished!", view=None)
            except Exception:
                await interaction.followup.send()

            await achemb(message, "extrovert", "send")
            await achemb(message, "extrovert", "send", person2)

            if cat_count >= 1000:
                await achemb(message, "capitalism", "send")
                await achemb(message, "capitalism", "send", person2)

            if cat_count == 0:
                await achemb(message, "absolutely_nothing", "send")
                await achemb(message, "absolutely_nothing", "send", person2)

            if person2value - person1value >= 100:
                await achemb(message, "profit", "send")
            if person1value - person2value >= 100:
                await achemb(message, "profit", "send", person2)

            if person1value > person2value:
                await achemb(message, "scammed", "send")
            if person2value > person1value:
                await achemb(message, "scammed", "send", person2)

            if person1value == person2value and person1gives != person2gives:
                await achemb(message, "perfectly_balanced", "send")
                await achemb(message, "perfectly_balanced", "send", person2)

    # add cat code
    async def addb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
        if interaction.user != person1 and interaction.user != person2:
            await do_funny(interaction)
            return

        if interaction.user == person1:
            currentuser = 1
            if person1accept:
                person1accept = False
                await update_trade_embed(interaction)
        elif interaction.user == person2:
            currentuser = 2
            if person2accept:
                person2accept = False
                await update_trade_embed(interaction)

        # all we really do is spawn the modal
        modal = TradeModal(currentuser)
        await interaction.response.send_modal(modal)

    # this is ran like everywhere when you do anything
    # it updates the embed
    async def gen_embed():
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole, person1value, person2value

        if blackhole:
            # no way thats fun
            await achemb(message, "blackhole", "send")
            await achemb(message, "blackhole", "send", person2)
            return discord.Embed(color=0x6E593C, title="Blackhole", description="How Did We Get Here?"), None

        view = View(timeout=3600)

        accept = Button(label="Accept", style=ButtonStyle.green)
        accept.callback = acceptb

        deny = Button(label="Deny", style=ButtonStyle.red)
        deny.callback = denyb

        add = Button(label="Offer...", style=ButtonStyle.blurple)
        add.callback = addb

        view.add_item(accept)
        view.add_item(deny)
        view.add_item(add)

        coolembed = discord.Embed(color=0x6E593C, title=f"{person1.name.replace("_", r"\_")} and {person2.name.replace("_", r"\_")} trade", description="no way")

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
                if k in prism_names:
                    valuestr += f"{get_emoji('prism')} {k}\n"
                    for v2 in type_dict.values():
                        valuenum += len(CAT_TYPES) / v2
                    continue
                if k == "rains":
                    valuestr += f"☔ {v:,}m of Cat Rains\n"
                    valuenum += 22 * 50 * v
                    continue
                valuenum += (len(CAT_TYPES) / type_dict[k]) * v
                total += v
                aicon = get_emoji(k.lower() + "cat")
                valuestr += f"{aicon} {k} {v:,}\n"
            if not valuestr:
                valuestr = "No cats offered!"
            else:
                valuestr += f"*Total value: {round(valuenum):,}\nTotal cats: {round(total):,}*"
                if number == 1:
                    person1value = round(valuenum)
                else:
                    person2value = round(valuenum)
            coolembed.add_field(name=f"{icon} {person.name.replace("_", r"\_")}", inline=True, value=valuestr)

        field(person1accept, person1gives, person1, 1)
        field(person2accept, person2gives, person2, 2)

        return coolembed, view

    # this is wrapper around gen_embed() to edit the mesage automatically
    async def update_trade_embed(interaction):
        embed, view = await gen_embed()
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            await achemb(message, "blackhole", "send")
            await achemb(message, "blackhole", "send", person2)

    # lets go add cats modal thats fun
    class TradeModal(discord.ui.Modal):
        def __init__(self, currentuser):
            super().__init__(
                title="Add cats to the trade",
                timeout=3600,
            )
            self.currentuser = currentuser

            self.cattype = discord.ui.TextInput(
                label="Cat Type, Prism Name or \"Rain\"",
                placeholder="Fine / Alpha / Rain"
            )
            self.add_item(self.cattype)

            self.amount = discord.ui.TextInput(
                label="Amount of cats to offer",
                placeholder="1",
                required=False
            )
            self.add_item(self.amount)

        # this is ran when user submits
        async def on_submit(self, interaction: discord.Interaction):
            nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
            value = self.amount.value if self.amount.value else 1
            user1 = get_profile(message.guild.id, person1.id)
            user2 = get_profile(message.guild.id, person2.id)

            # handle prisms
            if self.cattype.value in prism_names:
                try:
                    prism = Prism.get(guild_id=interaction.guild.id, name=self.cattype.value)
                except Exception:
                    await interaction.response.send_message("this prism doesnt exist", ephemeral=True)
                    return
                if prism.user_id != interaction.user.id:
                    await interaction.response.send_message("this is not your prism", ephemeral=True)
                    return
                if (self.currentuser == 1 and self.cattype.value in person1gives.keys()) or \
                    (self.currentuser == 2 and self.cattype.value in person2gives.keys()):
                    await interaction.response.send_message("you already added this prism", ephemeral=True)
                    return

                if self.currentuser == 1:
                    person1gives[self.cattype.value] = 1
                else:
                    person2gives[self.cattype.value] = 1
                await interaction.response.defer()
                await update_trade_embed(interaction)
                return

            # hella ton of checks
            try:
                if int(value) <= 0:
                    raise Exception
            except Exception:
                await interaction.response.send_message("plz number?", ephemeral=True)
                return

            # handle rains
            if "rain" in self.cattype.value.lower():
                user, _ = User.get_or_create(user_id=interaction.user.id)
                if user.rain_minutes < int(value):
                    await interaction.response.send_message("you dont have enough rains", ephemeral=True)
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

            if self.cattype.value not in cattypes:
                await interaction.response.send_message("add a valid cat type/prism name 💀💀💀", ephemeral=True)
                return

            try:
                if self.currentuser == 1:
                    currset = person1gives[self.cattype.value]
                else:
                    currset = person2gives[self.cattype.value]
            except Exception:
                currset = 0

            if (self.currentuser == 1 and user1[f"cat_{self.cattype.value}"] < int(value) + currset) or \
                (self.currentuser == 2 and user2[f"cat_{self.cattype.value}"] < int(value) + currset):
                await interaction.response.send_message("hell naww dude you dont even have that many cats 💀💀💀", ephemeral=True)
                return

            # OKE SEEMS GOOD LETS ADD CATS TO THE TRADE
            if self.currentuser == 1:
                try:
                    person1gives[self.cattype.value] += int(value)
                except Exception:
                    person1gives[self.cattype.value] = int(value)
            else:
                try:
                    person2gives[self.cattype.value] += int(value)
                except Exception:
                    person2gives[self.cattype.value] = int(value)

            await interaction.response.defer()
            await update_trade_embed(interaction)

    embed, view = await gen_embed()
    if not view:
        await message.response.send_message(embed=embed)
    else:
        await message.response.send_message(embed=embed, view=view)

    if person1 == person2:
        await achemb(message, "introvert", "send")


@bot.tree.command(description="Get Cat Image, does not add a cat to your inventory")
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(cat_type="select a cat type ok")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def cat(message: discord.Interaction, cat_type: Optional[str]):
    if cat_type and cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    if not message.channel.permissions_for(message.guild.me).attach_files:
        await message.response.send_message("i cant attach files here!", ephemeral=True)
        return

    image = f"images/spawn/{cat_type.lower()}_cat.png" if cat_type else "images/cat.png"
    file = discord.File(image, filename=image)
    await message.response.send_message(file=file)


@bot.tree.command(description="Get Cursed Cat")
async def cursed(message: discord.Interaction):
    if not message.channel.permissions_for(message.guild.me).attach_files:
        await message.response.send_message("i cant attach files here!", ephemeral=True)
        return
    file = discord.File("images/cursed.jpg", filename="cursed.jpg")
    await message.response.send_message(file=file)


@bot.tree.command(description="Get Your balance")
async def bal(message: discord.Interaction):
    if not message.channel.permissions_for(message.guild.me).attach_files:
        await message.response.send_message("i cant attach files here!", ephemeral=True)
        return
    file = discord.File("images/money.png", filename="money.png")
    embed = discord.Embed(title="cat coins", color=0x6E593C).set_image(url="attachment://money.png")
    await message.response.send_message(file=file, embed=embed)


@bot.tree.command(description="Brew some coffee to catch cats more efficiently")
async def brew(message: discord.Interaction):
   await message.response.send_message("HTTP 418: I'm a teapot. <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/418>")
   await achemb(message, "coffee", "send")


@bot.tree.command(description="Gamble your life savings away in our totally-not-rigged catsino!")
async def casino(message: discord.Interaction):
    if message.user.id in casino_lock:
        await message.response.send_message("you get kicked out of the catsino because you are already there, and two of you playing at once would cause a glitch in the universe", ephemeral=True)
        await achemb(message, "paradoxical_gambler", "send")
        return

    profile = get_profile(message.guild.id, message.user.id)
    # funny global gamble counter cus funny
    total_sum = Profile.select(peewee.fn.SUM(Profile.gambles)).scalar()
    embed = discord.Embed(title="The Catsino", description=f"One spin costs 5 {get_emoji('epiccat')} Epic cats\nSo far you gambled {profile.gambles} times.\nAll Cat Bot users gambled {total_sum:,} times.", color=0x750F0E)

    async def spin(interaction):
        nonlocal message
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        if message.user.id in casino_lock:
            await interaction.response.send_message("you get kicked out of the catsino because you are already there, and two of you playing at once would cause a glitch in the universe", ephemeral=True)
            return
        user = get_profile(interaction.guild.id, interaction.user.id)
        if user.cat_Epic < 5:
            await interaction.response.send_message("BROKE ALERT ‼️", ephemeral=True)
            await achemb(interaction, "broke", "send")
            return

        await interaction.response.defer()
        casino_lock.append(message.user.id)
        user.cat_Epic -= 5

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
            f"{get_emoji('8bitcat')} 7 8bit cats"
        ]

        random.shuffle(variants)

        for i in variants:
            embed = discord.Embed(title="The Catsino", description=f"**{i}**", color=0x750F0E)
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass
            await asyncio.sleep(1)

        amount = random.randint(1, 5)

        embed = discord.Embed(title="The Catsino", description=f"You won:\n**{get_emoji('finecat')} {amount} Fine cats**", color=0x750F0E)
        user.cat_Fine += amount

        button = Button(label="Spin", style=ButtonStyle.blurple)
        button.callback = spin

        myview = View(timeout=3600)
        myview.add_item(button)

        casino_lock.remove(message.user.id)
        user.gambles += 1
        user.save()

        if user.gambles >= 10:
            await achemb(message, "gambling_one", "send")
        if user.gambles >= 50:
            await achemb(message, "gambling_two", "send")

        try:
            await interaction.edit_original_response(embed=embed, view=myview)
        except Exception:
            await interaction.followup.send(embed=embed, view=myview)

    button = Button(label="Spin", style=ButtonStyle.blurple)
    button.callback = spin

    myview = View(timeout=3600)
    myview.add_item(button)

    await message.response.send_message(embed=embed, view=myview)



@bot.tree.command(description="oh no")
async def slots(message: discord.Interaction):
    if message.user.id in slots_lock:
        await message.response.send_message("you get kicked out of the slot machine because you are already there, and two of you playing at once would cause a glitch in the universe", ephemeral=True)
        await achemb(message, "paradoxical_gambler", "send")
        return

    profile = get_profile(message.guild.id, message.user.id)
    total_spins = Profile.select(peewee.fn.SUM(Profile.slot_spins)).scalar()
    total_wins = Profile.select(peewee.fn.SUM(Profile.slot_wins)).scalar()
    total_big_wins = Profile.select(peewee.fn.SUM(Profile.slot_big_wins)).scalar()
    embed = discord.Embed(title=":slot_machine: The Slot Machine", description=f"__Your stats__\n{profile.slot_spins} spins\n{profile.slot_wins} wins\n{profile.slot_big_wins} big wins\n\n__Global stats__\n{total_spins} spins\n{total_wins} wins\n{total_big_wins} big wins", color=0x750F0E)

    async def spin(interaction):
        nonlocal message
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        if message.user.id in slots_lock:
            await interaction.response.send_message("you get kicked out of the slot machine because you are already there, and two of you playing at once would cause a glitch in the universe", ephemeral=True)
            return
        user = get_profile(interaction.guild.id, interaction.user.id)

        await interaction.response.defer()
        await achemb(interaction, "slots", "send")
        slots_lock.append(message.user.id)
        user.slot_spins += 1

        variants = ['🍒', '🍋', '🍇', '🔔', '⭐', ':seven:']

        # the k number is much cycles it will go before stopping + 1
        col1 = random.choices(variants, k=11)
        col2 = random.choices(variants, k=16)
        col3 = random.choices(variants, k=26)

        if message.user.id in rigged_users:
            col1[len(col1) - 2] = ":seven:"
            col2[len(col2) - 2] = ":seven:"
            col3[len(col3) - 2] = ":seven:"

        for current3 in range(1, len(col3) - 1):
            current1 = min(len(col1) - 2, current3)
            current2 = min(len(col2) - 2, current3)
            desc = ""
            for offset in [-1, 0, 1]:
                desc += f"{col1[current1 + offset]} {col2[current2 + offset]} {col3[current3 + offset]}\n"
            embed = discord.Embed(title=":slot_machine: The Slot Machine", description=desc, color=0x750F0E)
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass
            await asyncio.sleep(0.5)

        if col1[current1] == col2[current2] == col3[current3]:
            user.slot_wins += 1
            await achemb(interaction, "win_slots", "send")
            if col1[current1] == ":seven:":
                desc = "**BIG WIN!**\n\n" + desc
                user.slot_big_wins += 1
                await achemb(interaction, "big_win_slots", "send")
            else:
                desc = "**You win!**\n\n" + desc
        else:
            desc = "**You lose!**\n\n" + desc

        embed = discord.Embed(title=":slot_machine: The Slot Machine", description=desc, color=0x750F0E)

        button = Button(label="Spin", style=ButtonStyle.blurple)
        button.callback = spin

        myview = View(timeout=3600)
        myview.add_item(button)

        slots_lock.remove(message.user.id)
        user.save()

        try:
            await interaction.edit_original_response(embed=embed, view=myview)
        except Exception:
            await interaction.followup.send(embed=embed, view=myview)


    button = Button(label="Spin", style=ButtonStyle.blurple)
    button.callback = spin

    myview = View(timeout=3600)
    myview.add_item(button)

    await message.response.send_message(embed=embed, view=myview)



async def toggle_reminders(interaction):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("Please use a text channel.", ephemeral=True)
        return
    user, _ = User.get_or_create(user_id=interaction.user.id)
    if user.vote_remind != 0:
        user.vote_remind = 0
        await interaction.response.send_message("Vote reminders have been turned off.", ephemeral=True)
    else:
        user.vote_remind = interaction.channel.id
        await interaction.response.send_message("Vote reminders have been turned on.", ephemeral=True)
    user.save()


if config.WEBHOOK_VERIFY:
    @bot.tree.command(description="Vote for Cat Bot for free cats")
    async def vote(message: discord.Interaction):
        await message.response.defer()

        current_day = datetime.datetime.utcnow().isoweekday()
        user, _ = User.get_or_create(user_id=message.user.id)

        if message.guild is not None:
            user.vote_channel = message.channel.id
            user.save()

        weekend_message = "🌟 **It's weekend! All vote rewards are DOUBLED!**\n\n" if current_day in [6, 7] else ""

        if [message.user.id, "topgg"] in pending_votes:
            pending_votes.remove([message.user.id, "topgg"])
            await claim_reward(user, message.channel, "topgg")

        view = View(timeout=3600)

        if user.vote_time_topgg + 43200 > time.time():
            left = int(user.vote_time_topgg + 43200 - time.time()) // 60
            button = Button(emoji=get_emoji("topgg"), label=f"{str(left//60).zfill(2)}:{str(left%60).zfill(2)}", style=ButtonStyle.gray, disabled=True)
        else:
            button = Button(emoji=get_emoji("topgg"), label="Vote", style=ButtonStyle.gray, url="https://top.gg/bot/966695034340663367/vote")
        view.add_item(button)

        if user.vote_remind:
            button = Button(label="Disable reminders", style=ButtonStyle.gray)
        else:
            button = Button(label="Enable Reminders!", style=ButtonStyle.green)
        button.callback = toggle_reminders
        view.add_item(button)

        embedVar = discord.Embed(title="Vote for Cat Bot", description=f"{weekend_message}Vote for Cat Bot on top.gg every 12 hours to recieve mystery cats.", color=0x6E593C)
        await message.followup.send(embed=embedVar, view=view)


@bot.tree.command(description="get a super accurate rating of something")
@discord.app_commands.describe(thing="The thing or person to check", stat="The stat to check")
async def rate(message: discord.Interaction, thing: str, stat: str):
    if len(thing) > 100 or len(stat) > 100:
        await message.response.send_message("thats kinda long", ephemeral=True)
        return
    await message.response.send_message(f"{thing} is {random.randint(0, 100)}% {stat}")


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
        "concetrate and ask again"
    ]

    await achemb(message, "balling", "send")
    await message.response.send_message(f"{question}\n:8ball: **{random.choice(catball_responses)}**")


@bot.tree.command(description="get a reminder in the future (+- 5 minutes)")
@discord.app_commands.describe(days="in how many days", hours="in how many hours", minutes="in how many minutes (+- 5 minutes)", text="what to remind")
async def remind(message: discord.Interaction, days: Optional[int], hours: Optional[int], minutes: Optional[int], text: Optional[str]):
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
    await message.response.send_message(f"ok, <t:{goal_time}:R> (+- 5 min) ill remind you of:\n{text}")
    msg = await message.original_response()
    message_link = msg.jump_url
    text += f"\n\n*This is a [reminder](<{message_link}>) you set.*"
    Reminder.create(user_id=message.user.id, text=text, time=goal_time)
    await achemb(message, "reminder", "send")  # the ai autocomplete thing suggested this and its actually a cool ach


@bot.tree.command(name="random", description="Get a random cat")
async def random_cat(message: discord.Interaction):
    await message.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('https://api.thecatapi.com/v1/images/search', timeout=15) as response:
                data = await response.json()
                await message.followup.send(data[0]['url'])
                await achemb(message, "randomizer", "send")
        except Exception:
            await message.followup.send("no cats :(")


@bot.tree.command(name="fact", description="get a random cat fact")
async def cat_fact(message: discord.Interaction):
    facts = [
        "you love cats",
        f"cat bot is in {len(bot.guilds):,} servers",
        "cat",
        "cats are the best"
    ]

    # give a fact from the list or the API
    if random.randint(0, 10) == 0:
        await message.response.send_message(random.choice(facts))
    else:
        await message.response.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://catfact.ninja/fact", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    await message.followup.send(data["fact"])
                else:
                    await message.followup.send("failed to fetch a cat fact.")

    if not isinstance(message.channel, Union[discord.TextChannel, discord.StageChannel, discord.VoiceChannel, discord.Thread]):
        return

    user = get_profile(message.guild.id, message.user.id)
    user.facts += 1
    user.save()
    if user.facts >= 10:
        await achemb(message, "fact_enjoyer", "send")

    try:
        channel = Channel.get_or_none(channel_id=message.channel.id)
        if channel and channel.cat and message.channel.permissions_for(message.guild.me).read_message_history:
            catchmsg = await message.channel.fetch_message(channel.cat)
            if str(get_emoji("professorcat")) in catchmsg.content:
                await achemb(message, "nerd_battle", "send")
    except Exception:
        pass


async def light_market(message):
    cataine_prices = [[10, "Fine"], [30, "Fine"], [20, "Good"], [15, "Rare"], [20, "Wild"], [10, "Epic"], [20, "Sus"], [15, "Rickroll"],
                      [7, "Superior"], [5, "Legendary"], [3, "8bit"], [4, "Divine"], [3, "Real"], [2, "Ultimate"], [1, "eGirl"]]
    user = get_profile(message.guild.id, message.user.id)
    if user.cataine_active < int(time.time()):
        count = user.cataine_week
        lastweek = user.recent_week
        embed = discord.Embed(title="The Mafia Hideout", description="you break down the door. the cataine machine lists what it needs.")

        if lastweek != datetime.datetime.utcnow().isocalendar()[1]:
            lastweek = datetime.datetime.utcnow().isocalendar()[1]
            count = 0
            user.cataine_week = 0
            user.recent_week = datetime.datetime.utcnow().isocalendar()[1]
            user.save()

        state = random.getstate()
        random.seed(datetime.datetime.utcnow().isocalendar()[1])
        deals = []

        r = range(random.randint(3, 5))
        for i in r:
            # 3-5 prices are possible per week
            deals.append(random.randint(0, 14))

        deals.sort()

        for i in r:
            deals[i] = cataine_prices[deals[i]]

        random.setstate(state)
        if count < len(deals):
            deal = deals[count]
        else:
            embed = discord.Embed(title="The Mafia Hideout", description="you have used up all of your cataine for the week. please come back later.")
            await message.followup.send(embed=embed, ephemeral=True)
            return

        type = deal[1]
        amount = deal[0]
        embed.add_field(name="🧂 12h of Cataine", value=f"Price: {get_emoji(type.lower() + 'cat')} {amount} {type}")

        async def make_cataine(interaction):
            nonlocal message, type, amount
            if user[f"cat_{type}"] < amount or user.cataine_active > time.time():
                return
            user[f"cat_{type}"] -= amount
            user.cataine_active = int(time.time()) + 43200
            user.cataine_week += 1
            user.save()
            await interaction.response.send_message("The machine spools down. Your cat catches will be doubled for the next 12 hours.", ephemeral=True)

        myview = View(timeout=3600)

        if user[f"cat_{type}"] >= amount:
            button = Button(label="Buy", style=ButtonStyle.blurple)
        else:
            button = Button(label="You don't have enough cats!", style=ButtonStyle.gray, disabled=True)
        button.callback = make_cataine

        myview.add_item(button)

        await message.followup.send(embed=embed, view=myview, ephemeral=True)
    else:
        embed = discord.Embed(title="The Mafia Hideout", description=f"the machine is recovering. you can use machine again <t:{user.cataine_active}:R>.")
        await message.followup.send(embed=embed, ephemeral=True)


async def dark_market(message):
    cataine_prices = [[10, "Fine"], [30, "Fine"], [20, "Good"], [15, "Rare"], [20, "Wild"], [10, "Epic"], [20, "Sus"], [15, "Rickroll"],
                      [7, "Superior"], [5, "Legendary"], [3, "8bit"], [4, "Divine"], [3, "Real"], [2, "Ultimate"], [1, "eGirl"], [100, "eGirl"]]
    user = get_profile(message.guild.id, message.user.id)
    if user.cataine_active < int(time.time()):
        level = user.dark_market_level
        embed = discord.Embed(title="The Dark Market", description="after entering the secret code, they let you in. today's deal is:")
        deal = cataine_prices[level] if level < len(cataine_prices) else cataine_prices[-1]
        type = deal[1]
        amount = deal[0]
        embed.add_field(name="🧂 12h of Cataine", value=f"Price: {get_emoji(type.lower() + 'cat')} {amount} {type}")

        async def buy_cataine(interaction):
            nonlocal message, type, amount
            if user[f"cat_{type}"] < amount or user.cataine_active > time.time():
                return
            user[f"cat_{type}"] -= amount
            user.cataine_active = int(time.time()) + 43200
            user.dark_market_level += 1
            user.save()
            await interaction.response.send_message("Thanks for buying! Your cat catches will be doubled for the next 12 hours.", ephemeral=True)

        debounce = False

        async def complain(interaction):
            nonlocal debounce
            if debounce:
                return
            debounce = True

            person = interaction.user
            phrases = [
                "*Because of my addiction I'm paying them a fortune.*",
                f"**{person}**: Hey, I'm not fine with those prices.",
                "**???**: Hmm?",
                "**???**: Oh.",
                "**???**: It seems you don't understand.",
                "**???**: We are the ones setting prices, not you.",
                f"**{person}**: Give me a more fair price or I will report you to the police.",
                "**???**: Huh?",
                "**???**: Well, it seems like you chose...",
                "# DEATH",
                "**???**: Better start running :)",
                "*Uh oh.*"
            ]

            await interaction.response.send_message("*That's not funny anymore. Those prices are insane.*", ephemeral=True)
            await asyncio.sleep(5)
            for i in phrases:
                await interaction.followup.send(i, ephemeral=True)
                await asyncio.sleep(5)

            # there is actually no time pressure anywhere but try to imagine there is
            counter = 0
            async def step(interaction):
                nonlocal counter
                counter += 1
                await interaction.response.defer()
                if counter == 30:
                    try:
                        await interaction.edit_original_response(view=None)
                    except Exception:
                        pass

                    await asyncio.sleep(5)
                    await interaction.followup.send("You barely manage to turn around a corner and hide to run away.", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction.followup.send("You quietly get to the police station and tell them everything.", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction.followup.send("## The next day.", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction.followup.send("A nice day outside. You open the news:", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction.followup.send("*Dog Mafia, the biggest cataine distributor, was finally caught after anonymous report.*", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction.followup.send("HUH? It was dogs all along...", ephemeral=True)
                    await asyncio.sleep(5)

                    await achemb(interaction, "thanksforplaying", "send")
                    user.story_complete = True
                    user.save()

            run_view = View(timeout=3600)
            button = Button(label="RUN", style=ButtonStyle.green)
            button.callback = step
            run_view.add_item(button)

            await interaction.followup.send("RUN!\nSpam the button a lot of times as fast as possible to run away!", view=run_view, ephemeral=True)


        myview = View(timeout=3600)

        if level == len(cataine_prices) - 1:
            button = Button(label="What???", style=ButtonStyle.red)
            button.callback = complain
        else:
            if user[f"cat_{type}"] >= amount:
                button = Button(label="Buy", style=ButtonStyle.blurple)
            else:
                button = Button(label="You don't have enough cats!", style=ButtonStyle.gray, disabled=True)
            button.callback = buy_cataine
        myview.add_item(button)

        await message.followup.send(embed=embed, view=myview, ephemeral=True)
    else:
        embed = discord.Embed(title="The Dark Market", description=f"you already bought from us recently. you can do next purchase <t:{user.cataine_active}:R>.")
        await message.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(description="View your achievements")
async def achievements(message: discord.Interaction):
    # this is very close to /inv's ach counter
    user = get_profile(message.guild.id, message.user.id)
    if user.funny >= 50:
        await achemb(message, "its_not_working", "send")

    unlocked = 0
    minus_achs = 0
    minus_achs_count = 0
    for k in ach_names:
        if ach_list[k]["category"] == "Hidden":
            minus_achs_count += 1
        if user[k]:
            if ach_list[k]["category"] == "Hidden":
                minus_achs += 1
            else:
                unlocked += 1
    total_achs = len(ach_list) - minus_achs_count
    minus_achs = "" if minus_achs == 0 else f" + {minus_achs}"

    hidden_counter = 0

    # this is a single page of the achievement list
    def gen_new(category):
        nonlocal message, unlocked, total_achs, hidden_counter

        unlocked = 0
        minus_achs = 0
        minus_achs_count = 0

        for k in ach_names:
            if ach_list[k]["category"] == "Hidden":
                minus_achs_count += 1
            if user[k]:
                if ach_list[k]["category"] == "Hidden":
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
            hidden_suffix = "\n\nThis is a \"Hidden\" category. Achievements here only show up after you complete them."
            hidden_counter += 1
        else:
            hidden_counter = 0

        newembed = discord.Embed(
                title=category, description=f"Achievements unlocked (total): {unlocked}/{total_achs}{minus_achs}{hidden_suffix}", color=0x6E593C
        ).set_footer(text="☔ Get tons of cats /rain")

        global_user, _ = User.get_or_create(user_id=message.user.id)
        if len(news_list) > len(global_user.news_state.strip()) or "0" in global_user.news_state:
            newembed.set_author(name="You have unread news! /news")

        for k, v in ach_list.items():
            if v["category"] == category:
                if k == "thanksforplaying":
                    if user[k]:
                        newembed.add_field(name=str(get_emoji("demonic")) + " Cataine Addict", value="Defeat the dog mafia", inline=True)
                    else:
                        newembed.add_field(name=str(get_emoji("no_demonic")) + " Thanks For Playing", value="Complete the story", inline=True)
                    continue

                icon = str(get_emoji("no_cat_throphy")) + " "
                if user[k]:
                    newembed.add_field(name=str(get_emoji("cat_throphy")) + " " + v["title"], value=v["description"], inline=True)
                elif category != "Hidden":
                    newembed.add_field(name=icon + v["title"], value="???" if v["is_hidden"] else v["description"], inline=True)

        return newembed

    # creates buttons at the bottom of the full view
    def insane_view_generator(category):
        myview = View(timeout=3600)
        buttons_list = []

        async def callback_hell(interaction):
            thing = interaction.data["custom_id"]
            await interaction.response.defer()
            try:
                await interaction.edit_original_response(embed=gen_new(thing), view=insane_view_generator(thing))
            except Exception:
                pass

            if hidden_counter == 3 and user.dark_market_active:
                if not user.story_complete:
                    # open the totally not suspicious dark market
                    await dark_market(message)
                else:
                    await light_market(message)
                await achemb(message, "dark_market", "followup")

            if hidden_counter == 20:
                await achemb(interaction, "darkest_market", "send")

        for i in ["Cat Hunt", "Random", "Silly", "Hard", "Hidden"]:
            if category == i:
                buttons_list.append(Button(label=i, custom_id=i, style=ButtonStyle.green))
            else:
                buttons_list.append(Button(label=i, custom_id=i, style=ButtonStyle.blurple))
            buttons_list[-1].callback = callback_hell

        for j in buttons_list:
            myview.add_item(j)
        return myview

    await message.response.send_message(embed=gen_new("Cat Hunt"), ephemeral=True, view=insane_view_generator("Cat Hunt"))

    if unlocked >= 15:
        await achemb(message, "achiever", "send")


async def catch(message: discord.Interaction, msg: discord.Message):
    if not message.channel.permissions_for(message.guild.me).attach_files:
        await message.response.send_message("i cant attach files here!", ephemeral=True)
        return
    if message.user.id in catchcooldown and catchcooldown[message.user.id] + 6 > time.time():
        await message.response.send_message("your phone is overheating bro chill", ephemeral=True)
        return
    await message.response.defer()

    event_loop = asyncio.get_event_loop()
    result = await event_loop.run_in_executor(None, msg2img.msg2img, msg)

    await message.followup.send("cought in 4k", file=result)

    catchcooldown[message.user.id] = time.time()

    await achemb(message, "4k", "send")

    if msg.author.id == bot.user.id and msg.content == "cought in 4k":
        await achemb(message, "8k", "send")

    try:
        is_cat = Channel.get(channel_id=message.channel.id).cat
    except Exception:
        is_cat = False

    if int(is_cat) == int(msg.id):
        await achemb(message, "not_like_that", "send")


@bot.tree.command(description="View the leaderboards")
@discord.app_commands.rename(leaderboard_type="type")
@discord.app_commands.describe(leaderboard_type="The leaderboard type to view!")
async def leaderboards(message: discord.Interaction, leaderboard_type: Optional[Literal["Cats", "Value", "Fast", "Slow"]]):
    if not leaderboard_type:
        leaderboard_type = "Cats"

    # this fat function handles a single page
    async def lb_handler(interaction, type, do_edit=None):
        nonlocal message
        if do_edit is None:
            do_edit = True
        await interaction.response.defer()

        messager = None
        interactor = None
        string = ""
        if type == "Cats":
            unit = "cats"
            # dynamically generate sum expression
            total_sum_expr = peewee.fn.SUM(sum(getattr(Profile, f"cat_{cat_type}").cast("BIGINT") for cat_type in cattypes))

            # run the query
            result = (Profile
                .select(Profile.user_id, total_sum_expr.alias("final_value"))
                .where(Profile.guild_id == message.guild.id)
                .group_by(Profile.user_id)
                .order_by(total_sum_expr.desc())
            ).execute()

            # find rarest
            rarest = None
            for i in cattypes[::-1]:
                non_zero_count = Profile.select().where((Profile.guild_id == message.guild.id) & (getattr(Profile, f"cat_{i}") > 0)).execute()
                if len(non_zero_count) != 0:
                    rarest = i
                    rarest_holder = non_zero_count
                    break

            if rarest:
                catmoji = get_emoji(rarest.lower() + "cat")
                rarest_holder = [f"<@{i.user_id}>" for i in rarest_holder]
                joined = ", ".join(rarest_holder)
                if len(rarest_holder) > 10:
                    joined = f"{len(rarest_holder)} people"
                string = f"Rarest cat: {catmoji} ({joined}'s)\n"
        elif type == "Value":
            unit = "value"
            total_sum_expr = peewee.fn.SUM(sum((len(CAT_TYPES) / type_dict[cat_type]) * getattr(Profile, f"cat_{cat_type}").cast("BIGINT") for cat_type in cattypes))
            result = (Profile
                .select(Profile.user_id, total_sum_expr.alias("final_value"))
                .where(Profile.guild_id == message.guild.id)
                .group_by(Profile.user_id)
                .order_by(total_sum_expr.desc())
            ).execute()
        elif type == "Fast":
            unit = "sec"
            result = (Profile
                .select(Profile.user_id, Profile.time.alias("final_value"))
                .where(Profile.guild_id == message.guild.id)
                .group_by(Profile.user_id, Profile.time)
                .order_by(Profile.time.asc())
            ).execute()
        elif type == "Slow":
            unit = "h"
            result = (Profile
                .select(Profile.user_id, Profile.timeslow.alias("final_value"))
                .where(Profile.guild_id == message.guild.id)
                .group_by(Profile.user_id, Profile.timeslow)
                .order_by(Profile.timeslow.desc())
            ).execute()
        else:
            # qhar
            return

        # find the placement of the person who ran the command and optionally the person who pressed the button
        interactor_placement = 0
        messager_placement = 0
        for index, position in enumerate(result):
            if position.user_id == interaction.user.id:
                interactor_placement = index
                interactor = position.final_value
            if interaction.user != message.user and position.user_id == message.user.id:
                messager_placement = index
                messager = position.final_value

        if type == "Slow":
            if interactor:
                interactor = round(interactor / 3600, 2)
            if messager:
                messager = round(messager / 3600, 2)

        # dont show placements if they arent defined
        if interactor and type in ["Cats", "Slow", "Value"]:
            if interactor <= 0:
                interactor_placement = 0
            interactor = round(interactor)
        elif interactor and type == "Fast" and interactor >= 99999999999999:
            interactor_placement = 0

        if messager and type in ["Cats", "Slow", "Value"]:
            if messager <= 0:
                messager_placement = 0
            messager = round(messager)
        elif messager and type == "Fast" and messager >= 99999999999999:
            messager_placement = 0

        # the little place counter
        current = 1
        leader = False
        for i in result[:15]:
            num = i.final_value
            if type == "Slow":
                if num <= 0:
                    break
                num = round(num / 3600, 2)
            elif type == "Cats" and num <= 0:
                break
            elif type == "Value":
                if num <= 0:
                    break
                num = round(num)
            elif type == "Fast" and num >= 99999999999999:
                break
            string = string + f"{current}. {num:,} {unit}: <@{i.user_id}>\n"
            if message.user.id == i.user_id and current <= 5:
                leader = True
            current += 1

        # add the messager and interactor
        # todo: refactor this
        if messager_placement > 15 or interactor_placement > 15:
            string = string + "...\n"
            # sort them correctly!
            if messager_placement > interactor_placement:
                # interactor should go first
                if interactor_placement > 15 and str(interaction.user.id) not in string:
                    string = string + f"{interactor_placement}\\. {interactor:,} {unit}: <@{interaction.user.id}>\n"
                if messager_placement > 15 and str(message.user.id) not in string:
                    string = string + f"{messager_placement}\\. {messager:,} {unit}: <@{message.user.id}>\n"
            else:
                # messager should go first
                if messager_placement > 15 and str(message.user.id) not in string:
                    string = string + f"{messager_placement}\\. {messager:,} {unit}: <@{message.user.id}>\n"
                if interactor_placement > 15 and str(interaction.user.id) not in string:
                    string = string + f"{interactor_placement}\\. {interactor:,} {unit}: <@{interaction.user.id}>\n"

        embedVar = discord.Embed(
                title=f"{type} Leaderboards:", description=string.rstrip(), color=0x6E593C
        ).set_footer(text="☔ Get tons of cats /rain")

        global_user, _ = User.get_or_create(user_id=message.user.id)
        if len(news_list) > len(global_user.news_state.strip()) or "0" in global_user.news_state:
            embedVar.set_author(name=f"{message.user} has unread news! /news")

        # handle funny buttons
        if type == "Cats":
            button1 = Button(label="Refresh", style=ButtonStyle.green)
        else:
            button1 = Button(label="Cats", style=ButtonStyle.blurple)

        if type == "Value":
            button2 = Button(label="Refresh", style=ButtonStyle.green)
        else:
            button2 = Button(label="Value", style=ButtonStyle.blurple)

        if type == "Fast":
            button3 = Button(label="Refresh", style=ButtonStyle.green)
        else:
            button3 = Button(label="Fast", style=ButtonStyle.blurple)

        if type == "Slow":
            button4 = Button(label="Refresh", style=ButtonStyle.green)
        else:
            button4 = Button(label="Slow", style=ButtonStyle.blurple)

        button1.callback = catlb
        button2.callback = valuelb
        button3.callback = fastlb
        button4.callback = slowlb

        myview = View(timeout=3600)
        myview.add_item(button1)
        myview.add_item(button2)
        myview.add_item(button3)
        myview.add_item(button4)

        # just send if first time, otherwise edit existing
        try:
            if not do_edit:
                raise Exception
            await interaction.edit_original_response(embed=embedVar, view=myview)
        except Exception:
            await interaction.followup.send(embed=embedVar, view=myview)

        if leader:
            await achemb(message, "leader", "send")

    # helpers! everybody loves helpers.
    async def catlb(interaction):
        await lb_handler(interaction, "Cats")

    async def valuelb(interaction):
        await lb_handler(interaction, "Value")

    async def fastlb(interaction):
        await lb_handler(interaction, "Fast")

    async def slowlb(interaction):
        await lb_handler(interaction, "Slow")

    await lb_handler(message, leaderboard_type, False)


@bot.tree.command(description="(ADMIN) Give cats to people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="who", amount="how many", cat_type="what")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def givecat(message: discord.Interaction, person_id: discord.User, amount: int, cat_type: str):
    if cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    user = get_profile(message.guild.id, person_id.id)
    user[f"cat_{cat_type}"] += amount
    user.save()
    embed = discord.Embed(title="Success!", description=f"gave <@{person_id.id}> {amount:,} {cat_type} cats", color=0x6E593C)
    await message.response.send_message(embed=embed)


@bot.tree.command(name="setup", description="(ADMIN) Setup cat in current channel")
@discord.app_commands.default_permissions(manage_guild=True)
async def setup_channel(message: discord.Interaction):
    if Channel.get_or_none(channel_id=message.channel.id):
        await message.response.send_message("bruh you already setup cat here are you dumb\n\nthere might already be a cat sitting in chat. type `cat` to catch it.")
        return

    with open("images/cat.png", "rb") as f:
        try:
            channel_permissions = message.channel.permissions_for(message.guild.me)
            needed_perms = {
                "View Channel": channel_permissions.view_channel,
                "Manage Webhooks": channel_permissions.manage_webhooks,
                "Send Messages": channel_permissions.send_messages,
                "Attach Files": channel_permissions.attach_files,
                "Use External Emojis": channel_permissions.use_external_emojis,
                "Read Message History": channel_permissions.read_message_history
            }
            if isinstance(message.channel, discord.Thread):
                needed_perms["Send Messages in Threads"] = channel_permissions.send_messages_in_threads

            for name, value in needed_perms.copy().items():
                if value:
                    needed_perms.pop(name)

            missing_perms = list(needed_perms.keys())
            if len(missing_perms) != 0:
                await message.response.send_message(f":x: Missing Permissions! Please give me the following:\n- {'\n- '.join(missing_perms)}\nHint: try setting channel permissions if server ones don't work.")
                return

            if isinstance(message.channel, discord.Thread):
                parent = bot.get_channel(message.channel.parent_id)
                if not isinstance(parent, Union[discord.TextChannel, discord.ForumChannel]):
                    raise Exception
                wh = await parent.create_webhook(name="Cat Bot", avatar=f.read())
                Channel.create(channel_id=message.channel.id, webhook=wh.url, thread_mappings=True)
            elif isinstance(message.channel, Union[discord.TextChannel, discord.StageChannel, discord.VoiceChannel]):
                wh = await message.channel.create_webhook(name="Cat Bot", avatar=f.read())
                Channel.create(channel_id=message.channel.id, webhook=wh.url, thread_mappings=False)
        except Exception:
            await message.response.send_message("this channel gives me bad vibes.")
            return

    await spawn_cat(str(message.channel.id))
    await message.response.send_message(f"ok, now i will also send cats in <#{message.channel.id}>")


@bot.tree.command(description="(ADMIN) Undo the setup")
@discord.app_commands.default_permissions(manage_guild=True)
async def forget(message: discord.Interaction):
    if channel := Channel.get_or_none(channel_id=message.channel.id):
        await unsetup(channel)
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
    perms: discord.Permissions = message.channel.permissions_for(message.guild.me)
    if not isinstance(message.channel, Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.Thread]):
        return
    fakecooldown[message.user.id] = time.time()
    try:
        if not perms.send_messages or not perms.attach_files:
            raise Exception
        await message.response.send_message(str(icon) + " eGirl cat hasn't appeared! Type \"cat\" to catch ratio!", file=file)
    except Exception:
        await message.response.send_message("i dont have perms lmao here is the ach anyways", ephemeral=True)
        pass
    await achemb(message, "trolled", "followup")


@bot.tree.command(description="(ADMIN) Force cats to appear")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(cat_type="select a cat type ok")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def forcespawn(message: discord.Interaction, cat_type: Optional[str]):
    if cat_type and cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    try:
        if Channel.get_or_none(channel_id=message.channel.id).cat:
            await message.response.send_message("there is already a cat", ephemeral=True)
            return
    except Exception:
        await message.response.send_message("this channel is not /setup-ed", ephemeral=True)
        return
    await spawn_cat(str(message.channel.id), cat_type)
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

    person = get_profile(message.guild.id, person_id.id)

    if valid and ach_id == "thanksforplaying" and not person.thanksforplaying:
        await message.response.send_message("HAHAHHAHAH\nno", ephemeral=True)
        return

    if valid:
        # if it is, do the thing
        reverse = person[ach_id]
        person[ach_id] = not reverse
        person.save()
        color, title, icon = 0x007F0E, "Achievement forced!", "https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/cat_throphy.png"
        if reverse:
            color, title, icon = 0xff0000, "Achievement removed!", "https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/no_cat_throphy.png"
        ach_data = ach_list[ach_id]
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=color).set_author(name=title, icon_url=icon).set_footer(text=f"for {person_id.name}")
        await message.response.send_message(embed=embed)
    else:
        await message.response.send_message("i cant find that achievement! try harder next time.", ephemeral=True)


@bot.tree.command(description="(ADMIN) Reset people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="who")
async def reset(message: discord.Interaction, person_id: discord.User):
    async def confirmed(interaction):
        if interaction.user.id == message.user.id:
            try:
                get_profile(message.guild.id, person_id.id).delete_instance()
                await interaction.edit_original_response(content=f"Done! rip <@{person_id.id}>. f's in chat.", view=None)
            except Exception:
                await interaction.edit_original_response(content="ummm? this person isnt even registered in cat bot wtf are you wiping?????", view=None)
        else:
            await do_funny(interaction)


    view = View(timeout=3600)
    button = Button(style=ButtonStyle.red, label="Confirm")
    button.callback = confirmed
    view.add_item(button)
    await message.response.send_message(f"Are you sure you want to reset <@{person_id.id}>?", view=view)


@bot.tree.command(description="(HIGH ADMIN) [VERY DANGEROUS] Reset all Cat Bot data of this server")
@discord.app_commands.default_permissions(administrator=True)
async def nuke(message: discord.Interaction):
    warning_text = "⚠️ This will completely reset **all** Cat Bot progress of **everyone** in this server. Spawn channels and their settings *will not be affected*.\nPress the button 5 times to continue."
    counter = 5

    async def gen(counter):
        lines = ["", "I'm absolutely sure! (1)", "I understand! (2)", "You can't undo this! (3)", "This is dangerous! (4)", "Reset everything! (5)"]
        view = View(timeout=3600)
        button = Button(label=lines[counter], style=ButtonStyle.red)
        button.callback = count
        view.add_item(button)
        return view

    async def count(interaction: discord.Interaction):
        nonlocal message, counter
        if interaction.user.id == message.user.id:
            await interaction.response.defer()
            counter -= 1
            if counter <= 0:
                # ~~Scary!~~ Not anymore!
                # how this works is we basically change the server id to the message id and then add user with id of 0 to mark it as deleted
                # this can be rolled back decently easily by asking user for the id of nuking message

                changed_profiles = []
                changed_prisms = []

                for i in Profile.select().where(Profile.guild_id == message.guild.id):
                    i.guild_id = interaction.message.id
                    changed_profiles.append(i)

                for i in Prism.select().where(Prism.guild_id == message.guild.id):
                    i.guild_id = interaction.message.id
                    changed_prisms.append(i)

                with db.atomic():
                    Profile.bulk_update(changed_profiles, fields=[Profile.guild_id], batch_size=50)
                    Prism.bulk_update(changed_prisms, fields=[Prism.guild_id], batch_size=50)

                Profile.create(guild_id=interaction.message.id, user_id=0)

                try:
                    await interaction.edit_original_response(content="Done. If you want to roll this back, please contact us in our discord: <https://discord.gg/staring>.", view=None)
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


async def claim_reward(user, channeley, type):
    # who at python hq though this was reasonable syntax
    vote_choices = [
        *([["Fine", 10]] * 1000),
        *([["Good", 5]] * 500),
        *([["Epic", 3]] * 400),
        *([["Brave", 2]] * 300),
        *([["TheTrashCell", 2]] * 200),
        *([["8bit", 1]] * 100),
        *([["Divine", 1]] * 50),
        *([["Real", 1]] * 20),
        ["eGirl", 1]
    ]

    cool_name = "Top.gg"

    cattype, amount = random.choice(vote_choices)
    icon = get_emoji(cattype.lower() + "cat")
    num_amount = amount

    current_day = datetime.datetime.utcnow().isoweekday()

    weekend_message = ""
    if current_day == 6 or current_day == 7:
        num_amount = amount * 2
        amount = f"~~{amount}~~ **{amount*2}**"
        weekend_message = "🌟 **It's weekend! All vote rewards are DOUBLED!**\n\n"

    profile = get_profile(channeley.guild.id, user.user_id)
    profile[f"cat_{cattype}"] += num_amount
    profile.save()
    user.vote_time_topgg = time.time()
    user.reminder_topgg_exists = 0
    user.save()
    view = None
    if not user.vote_remind:
        view = View(timeout=3600)
        button = Button(label="Enable Vote Reminders!", style=ButtonStyle.green)
        button.callback = toggle_reminders
        view.add_item(button)

    embedVar = discord.Embed(title="Vote redeemed!", description=f"{weekend_message}You have received {icon} {amount} {cattype} cats for voting on {cool_name}.\nVote again in 12 hours.", color=0x007F0E)
    try:
        if channeley.permissions_for(channeley.guild.me).send_messages:
            await channeley.send(f"<@{user.user_id}>", embed=embedVar, view=view)
    except Exception:
        pass


async def recieve_vote(request):
    if request.headers.get('authorization', '') != config.WEBHOOK_VERIFY:
        return web.Response(text="bad", status=403)
    request_json = await request.json()

    user, _ = User.get_or_create(user_id=int(request_json["user"]))
    type = "topgg"
    if user.vote_time_topgg + 43100 > time.time():
        # top.gg is NOT realiable with their webhooks, but we politely pretend they are
        return web.Response(text="you fucking dumb idiot", status=200)

    try:
        channeley = bot.get_channel(user.vote_channel)
        if not isinstance(channeley, Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.Thread]) or not channeley.guild:
            raise Exception
    except Exception:
        pending_votes.append([user.user_id, type])
        return web.Response(text="ok", status=200)

    await claim_reward(user, channeley, type)
    return web.Response(text="ok", status=200)


# this is the crash handler
async def on_command_error(ctx, error):
    if ctx.guild is None:
        try:
            await ctx.channel.send("hello good sir i would politely let you know cat bot is no workey in dms please consider gettng the hell out of here")
        except Exception:
            pass
        return

    # implement your own filtering i give up

    if config.CRASH_MODE == "DM":
        try:
            cont = ctx.guild.id
        except Exception:
            cont = "Error getting"

        error2 = error.original.__traceback__

        if not milenakoos:
            return
        await milenakoos.send(
                "There is an error happend:\n"
                + str("".join(traceback.format_tb(error2))) + str(type(error).__name__) + str(error)
                + "\n\nGuild: "
                + str(cont)
        )
    elif config.CRASH_MODE == "RAISE":
        raise


async def setup(bot2):
    global bot, DONATE_ID, RAIN_ID, vote_server

    for command in bot.tree.walk_commands():
        # copy all the commands
        command.guild_only = True
        bot2.tree.add_command(command)

    context_menu_command = discord.app_commands.ContextMenu(
        name="catch",
        callback=catch
    )
    context_menu_command.guild_only = True
    bot2.tree.add_command(context_menu_command)

    # copy all the events
    bot2.on_ready = on_ready
    bot2.on_guild_join = on_guild_join
    bot2.on_message = on_message

    # copy the error logger
    bot2.tree.error = on_command_error

    if config.WEBHOOK_VERIFY:
        app = web.Application()
        app.add_routes([web.post("/", recieve_vote)])
        vote_server = web.AppRunner(app)
        await vote_server.setup()
        site = web.TCPSite(vote_server, '0.0.0.0', 8069)
        await site.start()

    # finally replace the fake bot with the real one
    bot = bot2

    app_commands = await bot.tree.sync()
    for i in app_commands:
        if i.name == "donate":
            DONATE_ID = i.id
        elif i.name == "rain":
            RAIN_ID = i.id

    if bot.is_ready() and not on_ready_debounce:
        await on_ready()


async def teardown(bot):
    await vote_server.cleanup()
