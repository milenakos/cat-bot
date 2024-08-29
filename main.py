import asyncio
import base64
import datetime
import heapq
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
from aiohttp import web
from discord import ButtonStyle
from discord.ext import commands
from discord.ui import Button, View

import msg2img
from database import db, Profile, User, Channel

logging.basicConfig(level=logging.INFO)

### Setup values start

GUILD_ID = 966586000417619998 # for emojis
CATS_GUILD_ID = False # alternative guild purely for cattype emojis (use for christmas/halloween etc), False to disable
BACKUP_ID = 1060545763194707998 # channel id for db backups, private extremely recommended

# top.gg voting key
# set to False to disable
WEBHOOK_VERIFY = os.environ["webhook_verify"]

# top.gg api token because they use ancient technology and you need to post server count manually smh
# set to False to disable
TOP_GG_TOKEN = os.environ["top_gg_token"]

# this will automatically restart the bot if message in GITHUB_CHANNEL_ID is sent, you can use a github webhook for that
# set to False to disable
GITHUB_CHANNEL_ID = 1060965767044149249

# all messages in this channel will be interpreted as user ids to give premium access to
# set to False to disable
DONOR_CHANNEL_ID = 1249343008890028144

# all messages in this channel are allowed to be cat!rain commands
# set to False to disable
RAIN_CHANNEL_ID = 1278705994536321157

BANNED_ID = [] # banned from using /tiktok

WHITELISTED_BOTS = [] # bots which are allowed to catch cats

# use if bot is in a team
# if you dont know what that is or dont use it,
# you can remove this line
OWNER_ID = 553093932012011520

# what to do when there is a crash
CRASH_MODE = "RAISE"

### Setup values end

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

allowedemojis = []
for i in type_dict.keys():
    allowedemojis.append(i.lower() + "cat")

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

intents = discord.Intents(message_content=True, messages=True, guilds=True, emojis=True)
bot = commands.AutoShardedBot(command_prefix="this is a placebo bot which will be replaced when this will get loaded", intents=intents, help_command=None, chunk_guilds_at_startup=False)

# this list stores unique non-duplicate cattypes
cattypes = []
for e in CAT_TYPES:
    if e not in cattypes:
        cattypes.append(e)

funny = ["why did you click this this arent yours", "absolutely not", "cat bot not responding, try again later", "you cant", "can you please stop", "try again", "403 not allowed", "stop", "get a life", "not for you", "no", "nuh uh"]

milenakoos = None
try:
    if not OWNER_ID:
        OWNER_ID = 0
except Exception:
    OWNER_ID = 0

# store credits usernames to prevent excessive api calls
gen_credits = {}

# due to some stupid individuals spamming the hell out of reactions, we ratelimit them
# you can do 50 reactions before they stop, limit resets on global cat loop
reactions_ratelimit = {}

# cat bot auto-claims in the channel user last ran /vote in
# this is a failsafe to store the fact they voted until they ran that atleast once
pending_votes = []

# prevent ratelimits
casino_lock = []

# cat rains
cat_rains = {}

# to prevent double catches
temp_catches_storage = []

# prevent timetravel
in_the_past = False
about_to_stop = False

# docs suggest on_ready can be called multiple times
on_ready_debounce = False

# we store all discord text emojis to not refetch them a bajillion times
# (this does mean you will need to restart the bot if you reupload an emoji)
emojis = {}
do_save_emojis = False

# for mentioning it in catch message, will be auto-fetched in on_ready()
DONATE_ID = 1249368737824374896
RAIN_ID = 1270470307102195752

# we restart every some loops to pull new code and fix stuff it breaks
loop_count = 0

# loops in dpy can randomly break, i check if is been over 20 minutes since last loop to restart it
last_loop_time = time.time()


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
        try:
            if name in allowedemojis and CATS_GUILD_ID:
                result = discord.utils.get(bot.get_guild(CATS_GUILD_ID).emojis, name=name)
            else:
                result = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=name)
            if not result:
                raise Exception
            if do_save_emojis:
                emojis[name] = str(result)
            return result
        except Exception:
            return "🔳"

# this is some common code which is run whether someone gets an achievement
async def achemb(message, ach_id, send_type, author_string=None):
    if not author_string:
        try:
            author = message.author.id
            author_string = message.author
        except Exception:
            author = message.user.id
            author_string = message.user
    else:
        author = author_string.id
    profile = get_profile(message.guild.id, author)
    if not profile[ach_id]:
        profile[ach_id] = True
        profile.save()
        ach_data = ach_list[ach_id]
        desc = ach_data["description"]
        if ach_id == "dataminer":
            desc = "Your head hurts -- you seem to have forgotten what you just did to get this."

        if ach_id != "thanksforplaying":
            embed = discord.Embed(title=ach_data["title"], description=desc, color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png").set_footer(text=f"Unlocked by {author_string.name}")
        else:
            embed = discord.Embed(title="Cataine Addict", description="Defeat the dog mafia\nThanks for playing! ✨", color=0xC12929).set_author(name="Demonic achievement unlocked! 🌟", icon_url="https://pomf2.lain.la/f/ez0enx2d.png").set_footer(text=f"Congrats to {author_string.name}!!")

        try:
            if send_type == "reply":
                result = await message.reply(embed=embed)
            elif send_type == "send":
                result = await message.channel.send(embed=embed)
            elif send_type == "followup":
                result = await message.followup.send(embed=embed, ephemeral=True)
            elif send_type == "response":
                result = await message.response.send_message(embed=embed)
        except Exception:
            pass

        if ach_id == "thanksforplaying":
            await asyncio.sleep(2)
            embed2 = discord.Embed(title="Cataine Addict", description="Defeat the dog mafia\nThanks for playing! ✨", color=0xFFFF00).set_author(name="Demonic achievement unlocked! 🌟", icon_url="https://pomf2.lain.la/f/ez0enx2d.png").set_footer(text=f"Congrats to {author_string.name}!!")
            await result.edit(embed=embed2)
            await asyncio.sleep(2)
            await result.edit(embed=embed)
            await asyncio.sleep(2)
            await result.edit(embed=embed2)
            await asyncio.sleep(2)
            await result.edit(embed=embed)

# function to autocomplete cat_type choices for /gift, /giftcat, and /forcespawn, which also allows more than 25 options
async def cat_type_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [discord.app_commands.Choice(name=choice, value=choice) for choice in cattypes if current.lower() in choice.lower()][:25]

# converts string to lowercase alphanumeric characters only
def alnum(string):
    return "".join(item for item in string.lower() if item.isalnum())

# function to autocomplete achievement choice for /giveachievement, which also allows more than 25 options
async def ach_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [discord.app_commands.Choice(name=val["title"], value=key) for (key, val) in ach_list.items() if (alnum(current) in alnum(key) or alnum(current) in alnum(val["title"]))][:25]

async def spawn_cat(ch_id, localcat=None):
    try:
        channel = Channel.get(channel_id=ch_id)
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
            channeley = bot.get_channel(int(ch_id))
            if not isinstance(channeley, Union[discord.TextChannel, discord.VoiceChannel]):
                return
            with open("images/cat.png", "rb") as f:
                try:
                    wh = await channeley.create_webhook(name="Cat Bot", avatar=f.read())
                    channel.webhook = wh.url
                    channel.save()
                    await spawn_cat(ch_id, localcat) # respawn
                except Exception:
                    await channeley.send("Error spawning the cat - cat moved to new system and failed to automatically migrate this channel. Please make sure the bot has **Manage Webhooks** permission - either give it manually or re-invite the bot, then resetup this channel.")
            return

        appearstring = "{emoji} {type} cat has appeared! Type \"cat\" to catch it!" if not channel.appear else channel.appear

        if channel.cat or in_the_past:
            return  # its never too late to return

        if thread_id:
            message_is_sus = await channeley.send(appearstring.replace("{emoji}", str(icon)).replace("{type}", localcat), file=file, wait=True, thread=discord.Object(int(ch_id)))
        else:
            message_is_sus = await channeley.send(appearstring.replace("{emoji}", str(icon)).replace("{type}", localcat), file=file, wait=True)
        if str(message_is_sus.id)[0] != "1":
            # check for broken ids idk
            return
        channel.cat = message_is_sus.id
        channel.yet_to_spawn = 0
        channel.save()
    except Exception:
        pass

# a loop for various maintaince which is ran every 5 minutes
async def maintaince_loop():
    global reactions_ratelimit, last_loop_time, loop_count, in_the_past, about_to_stop
    last_loop_time = time.time()
    reactions_ratelimit = {}
    await bot.change_presence(
        activity=discord.CustomActivity(name=f"Catting in {len(bot.guilds):,} servers")
    )

    if TOP_GG_TOKEN:
        async with aiohttp.ClientSession() as session:
            # send server count to top.gg
            try:
                await session.post(f'https://top.gg/api/bots/{bot.user.id}/stats',
                                    headers={"Authorization": TOP_GG_TOKEN},
                                    json={"server_count": len(bot.guilds), "shard_count": len(bot.shards)},
                                    timeout=15)
            except Exception:
                print("Posting failed.")

    for channel in Channel.select().where((Channel.yet_to_spawn < time.time()) & (~Channel.cat)):
        await spawn_cat(str(channel.channel_id))
        await asyncio.sleep(0.1)

    notified_users = []
    errored_users = []
    # THIS IS CONSENTUAL AND TURNED OFF BY DEFAULT DONT BAN ME
    for user in User.select().where((User.vote_remind) & (User.vote_time_topgg + 43200 < time.time()) & (~User.reminder_topgg_exists)):
        await asyncio.sleep(0.1)

        channeley = bot.get_channel(user.vote_remind)
        if not isinstance(channeley, discord.TextChannel):
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

    backupchannel = bot.get_channel(BACKUP_ID)
    thing = discord.File("catbot.db", filename="catbot.db")
    if not isinstance(backupchannel, Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]):
        raise ValueError
    await backupchannel.send(f"In {len(bot.guilds)} servers, loop {loop_count}.", file=thing)

    loop_count += 1
    if loop_count >= 12 and not cat_rains:
        about_to_stop = True
        os.system("git pull")
        await vote_server.cleanup()
        in_the_past = True
        await bot.cat_bot_reload_hook()  # pyright: ignore


# some code which is run when bot is started
async def on_ready():
    global milenakoos, OWNER_ID, do_save_emojis, on_ready_debounce, gen_credits, last_loop_time
    if on_ready_debounce:
        return
    on_ready_debounce = True
    print("cat is now online")
    do_save_emojis = True
    await bot.change_presence(
        activity=discord.CustomActivity(name=f"Just restarted! Catting in {len(bot.guilds):,} servers.")
    )
    appinfo = await bot.application_info()
    if not OWNER_ID:
        milenakoos = appinfo.owner
        OWNER_ID = milenakoos.id
    else:
        milenakoos = await bot.fetch_user(OWNER_ID)

    credits = {
        "author": [553093932012011520],
        "contrib": [576065759185338371, 819980535639572500, 432966085025857536, 646401965596868628, 696806601771974707, 804762486946660353, 931342092121280543, 695359046928171118],
        "tester": [712639066373619754, 902862104971849769, 709374062237057074, 520293520418930690, 689345298686148732, 1004128541853618197, 839458185059500032],
        "emoji": [709374062237057074],
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
            pass # death
        gen_credits[key] = ", ".join(peoples)


# this is all the code which is ran on every message sent
# its mostly for easter eggs or achievements
async def on_message(message):
    global in_the_past
    text = message.content
    if not bot.user or message.author.id == bot.user.id:
        return

    if time.time() > last_loop_time + 300:
        await maintaince_loop()

    achs = [["cat?", "startswith", "???"],
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
        ["tac", "exact", "reverse"]]

    reactions = [["v1;", "custom", "why_v1"],
        ["proglet", "custom", "professor_cat"],
        ["xnopyt", "custom", "vanish"],
        ["silly", "custom", "sillycat"],
        ["indev", "vanilla", "🐸"],
        ["bleh", "custom", "blepcat"],
        ["blep", "custom", "blepcat"]]

    responses = [["cat!sex", "exact", "..."],
        ["cellua good", "in", ".".join([str(random.randint(2, 254)) for _ in range(4)])],
        ["https://tenor.com/view/this-cat-i-have-hired-this-cat-to-stare-at-you-hired-cat-cat-stare-gif-26392360", "exact", "https://tenor.com/view/cat-staring-cat-gif-16983064494644320763"]]

    # this is auto-update thing
    if GITHUB_CHANNEL_ID and message.channel.id == GITHUB_CHANNEL_ID:
        os.system("git pull")
        await vote_server.cleanup()
        in_the_past = True
        await bot.cat_bot_reload_hook()  # pyright: ignore

    if DONOR_CHANNEL_ID and message.channel.id == DONOR_CHANNEL_ID:
        user, _ = User.get_or_create(user_id=message.content)
        user.premium = True
        user.save()

    if RAIN_CHANNEL_ID and message.channel.id == RAIN_CHANNEL_ID and text.lower().startswith("cat!rain"):
        things = text.split(" ")
        user, _ = User.get_or_create(user_id=things[1])
        if things[2] == "short":
            user.shortrain += 1
        elif things[2] == "medium":
            user.mediumrain += 1
        elif things[2] == "long":
            user.longrain += 1
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
                await message.add_reaction(get_emoji("staring_cat"))
                react_count += 1
            except Exception:
                pass

    try:
        if "robotop" in message.author.name.lower() and "i rate **cat" in message.content.lower():
            icon = str(get_emoji("no_cat_throphy")) + " "
            await message.reply("**RoboTop**, I rate **you** 0 cats " + icon * 5)

        if "leafbot" in message.author.name.lower() and "hmm... i would rate cat" in message.content.lower():
            icon = str(get_emoji("no_cat_throphy")) + " "
            await message.reply("Hmm... I would rate you **0 cats**! " + icon * 5)

        if text == "lol_i_have_dmed_the_cat_bot_and_got_an_ach" and not message.guild:
            await message.channel.send("which part of \"send in server\" was unclear?")
            return
        elif message.guild is None:
            await message.channel.send("good job! please send \"lol_i_have_dmed_the_cat_bot_and_got_an_ach\" in server to get your ach!")
            return
    except Exception:
        pass

    if message.author.bot or message.webhook_id is not None:
        return

    if "cat!n4lltvuCOKe2iuDCmc6JsU7Jmg4vmFBj8G8l5xvoDHmCoIJMcxkeXZObR6HbIV6" in text:
        msg = message
        try:
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
        if message.author in message.mentions:
            await message.add_reaction(get_emoji("staring_cat"))
            react_count += 1
    except Exception:
        pass

    if react_count >= 3:
        await achemb(message, "silly", "send")

    if (":place_of_worship:" in text or "🛐" in text) and (":cat:" in text or ":staring_cat:" in text or "🐱" in text):
        await achemb(message, "worship", "reply")
    if text.lower() in ["testing testing 1 2 3", "cat!ach"]:
        try:
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
            await message.reply(f"ok then\n{message.author.name.replace("_", r"\_")} lost 1 fine cat!!!1!\nYou now have {user.cat_Fine} cats of dat type!")
        except Exception:
            pass
        await achemb(message, "pleasedonotthecat", "reply")

    if text.lower() == "please do the cat":
        thing = discord.File("images/socialcredit.jpg", filename="socialcredit.jpg")
        try:
            await message.reply(file=thing)
        except Exception:
            pass
        await achemb(message, "pleasedothecat", "reply")
    if text.lower() == "car":
        file = discord.File("images/car.png", filename="car.png")
        embed = discord.Embed(title="car!", color=0x6E593C).set_image(url="attachment://car.png")
        try:
            await message.reply(file=file, embed=embed)
        except Exception:
            pass
        await achemb(message, "car", "reply")
    if text.lower() == "cart":
        file = discord.File("images/cart.png", filename="cart.png")
        embed = discord.Embed(title="cart!", color=0x6E593C).set_image(url="attachment://cart.png")
        try:
            await message.reply(file=file, embed=embed)
        except Exception:
            pass

    try:
        if ("sus" in text.lower() or "amog" in text.lower() or "among" in text.lower() or "impost" in text.lower() or "report" in text.lower()) and \
            (channel := Channel.get_or_none(channel_id=message.channel.id)) and channel.cat:
            catchmsg = await message.channel.fetch_message(channel.cat)
            if get_emoji("suscat") in catchmsg.content:
                await achemb(message, "sussy", "send")
    except Exception:
        pass

    if text.lower() == "i voted":
        # recheck votes
        user, _ = User.get_or_create(user_id=message.author.id)
        if user.vote_time_topgg + 43200 < time.time():
            async with aiohttp.ClientSession() as session:
                try:
                    answer = await session.get(f'https://top.gg/api/bots/{bot.user.id}/check?userId={message.author.id}',
                                                headers={"Authorization": TOP_GG_TOKEN},
                                                timeout=15)
                    resp = await answer.json()
                    if resp["voted"]:
                        await claim_reward(user, message.channel, "topgg")
                except Exception:
                    pass

    # this is run whether someone says "cat" (very complex)
    if text.lower() == "cat":
        user = get_profile(message.guild.id, message.author.id)
        channel = Channel.get_or_none(channel_id=message.channel.id)
        if not channel or not channel.cat or channel.cat in temp_catches_storage or (user.timeout) > time.time() or message.webhook_id or (message.author.bot and message.author.id not in WHITELISTED_BOTS):
            # if there is no cat, you are /preventcatch-ed, or you aren't a whitelisted bot
            if cat_rains.get(str(message.channel.id), 0) < time.time():
                icon = get_emoji("pointlaugh")
            try:
                await message.add_reaction(icon)
            except Exception:
                pass
        elif channel.cat:
            temp_catches_storage.append(channel.cat)
            times = [channel.spawn_times_min, channel.spawn_times_max]
            if cat_rains.get(str(message.channel.id), 0) != 0:
                if cat_rains.get(str(message.channel.id), 0) > time.time():
                    times = [1, 2]
                else:
                    del cat_rains[str(message.channel.id)]
                    await message.channel.send("# :bangbang: this concludes the cat rain.")
                    await message.channel.send("# :bangbang: this concludes the cat rain.")
                    await message.channel.send("# :bangbang: this concludes the cat rain.")
            decided_time = random.uniform(times[0], times[1])
            channel.yet_to_spawn = time.time() + decided_time + 10
            try:
                current_time = message.created_at.timestamp()
                channel.lastcatches = current_time
                cat_temp = channel.cat
                channel.cat = 0
                try:
                    var = await message.channel.fetch_message(cat_temp)
                except Exception:
                    try:
                        await message.channel.send(f"oopsie poopsie i cant access the original message but {message.author.mention} *did* catch a cat rn")
                    except Exception:
                        pass
                    return
                catchtime = var.created_at
                catchcontents = var.content
                try:
                    channeley = discord.Webhook.from_url(channel.webhook, client=bot)
                    if channel.thread_mappings:
                        await channeley.delete_message(cat_temp, thread=discord.Object(int(message.channel.id)))
                    else:
                        await channeley.delete_message(cat_temp)
                except Exception:
                    pass
                try:
                    # some math to make time look cool
                    then = catchtime.timestamp()
                    time_caught = abs(round(((current_time - then) * 100)) / 100) # cry about it
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
                        acc_seconds = round(seconds * 100) / 100
                        caught_time = caught_time + str(acc_seconds) + " seconds "
                    do_time = True
                    if time_caught <= 0:
                        do_time = False
                except Exception:
                    # if some of the above explodes just give up
                    do_time = False
                    caught_time = "undefined amounts of time "

                if cat_rains.get(str(message.channel.id), 0) > time.time():
                    do_time = False

                icon = None
                partial_type = None
                for v in allowedemojis:
                    if v in catchcontents:
                        partial_type = v
                        break

                if not partial_type:
                    return

                for i in type_dict.keys():
                    if i.lower() in partial_type:
                        le_emoji = i
                        break

                icon = get_emoji(partial_type)

                suffix_string = ""
                silly_amount = 1
                if user.cataine_active > time.time():
                    # cataine is active
                    silly_amount = 2
                    suffix_string = "\n🧂 cataine worked! you got 2 cats instead!"

                elif user.cataine_active != 0:
                    # cataine ran out
                    user.cataine_active = 0
                    suffix_string = "\nyour cataine buff has expired. you know where to get a new one 😏"

                if random.randint(0, 7) == 0:
                    # shill rains
                    suffix_string += f"\n☔ get tons of cats and have fun: </rain:{RAIN_ID}>"

                elif random.randint(0, 7) == 0:
                    # shill donating
                    suffix_string += f"\n👑 donate to cat bot and get cool perks: </donate:{DONATE_ID}>"

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
                elif WEBHOOK_VERIFY and vote_time_user.vote_time_topgg + 43200 < time.time():
                    button = Button(emoji=get_emoji("topgg"), label=random.choice(vote_button_texts), url="https://top.gg/bot/966695034340663367/vote")
                elif random.randint(0, 20) == 0:
                    button = Button(label="Join our Discord!", url="https://discord.gg/staring")

                if button:
                    view = View(timeout=3600)
                    view.add_item(button)

                try:
                    send_target = discord.Webhook.from_url(channel.webhook, client=bot)
                except Exception:
                    send_target = message.channel

                user[f"cat_{le_emoji}"] += silly_amount
                new_count = user[f"cat_{le_emoji}"]
                # i love dpy
                try:
                    if channel.thread_mappings:
                        if view:
                            await send_target.send(coughstring.replace("{username}", message.author.name.replace("_", "\\_"))
                                                            .replace("{emoji}", str(icon))
                                                            .replace("{type}", le_emoji)
                                                            .replace("{count}", str(new_count))
                                                            .replace("{time}", caught_time[:-1]) + suffix_string,
                                                view=view,
                                                thread=discord.Object(message.channel.id),
                                                allowed_mentions=discord.AllowedMentions.none())
                        else:
                            await send_target.send(coughstring.replace("{username}", message.author.name.replace("_", "\\_"))
                                                            .replace("{emoji}", str(icon))
                                                            .replace("{type}", le_emoji)
                                                            .replace("{count}", str(new_count))
                                                            .replace("{time}", caught_time[:-1]) + suffix_string,
                                                thread=discord.Object(message.channel.id),
                                                allowed_mentions=discord.AllowedMentions.none())
                    else:
                        if view:
                            await send_target.send(coughstring.replace("{username}", message.author.name.replace("_", "\\_"))
                                                            .replace("{emoji}", str(icon))
                                                            .replace("{type}", le_emoji)
                                                            .replace("{count}", str(new_count))
                                                            .replace("{time}", caught_time[:-1]) + suffix_string,
                                                view=view,
                                                allowed_mentions=discord.AllowedMentions.none())
                        else:
                            await send_target.send(coughstring.replace("{username}", message.author.name.replace("_", "\\_"))
                                                            .replace("{emoji}", str(icon))
                                                            .replace("{type}", le_emoji)
                                                            .replace("{count}", str(new_count))
                                                            .replace("{time}", caught_time[:-1]) + suffix_string,
                                                allowed_mentions=discord.AllowedMentions.none())
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
                async def do_reward(message, level):
                    user.progress = 0
                    reward = level["reward"]
                    reward_amount = level["reward_amount"]
                    user[f"cat_{reward}"] += reward_amount
                    icon = get_emoji(reward.lower() + "cat")
                    user.battlepass += 1
                    embed = discord.Embed(title=f"Level {user.battlepass} complete!", description=f"You have recieved {icon} {reward_amount} {reward} cats!", color=0x007F0E).set_author(name="Cattlepass level!", icon_url="https://pomf2.lain.la/f/zncxu6ej.png")
                    try:
                        await message.channel.send(embed=embed)
                    except Exception:
                        pass

                battlelevel = battle["levels"][user.battlepass]
                if battlelevel["req"] == "catch_fast" and do_time and time_caught < battlelevel["req_data"]:
                    await do_reward(message, battlelevel)
                if battlelevel["req"] == "catch":
                    user.progress += 1
                    if user.progress == battlelevel["req_data"]:
                        await do_reward(message, battlelevel)
                if battlelevel["req"] == "catch_type" and le_emoji == battlelevel["req_data"]:
                    await do_reward(message, battlelevel)
            except Exception:
                raise
            finally:
                user.save()
                channel.save()
                await asyncio.sleep(decided_time)
                await spawn_cat(str(message.channel.id))

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
        if things[2] == "short":
            user.shortrain += 1
        elif things[2] == "medium":
            user.mediumrain += 1
        elif things[2] == "long":
            user.longrain += 1
        user.save()
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
        #   <stuff goes here>
        #
        # bot.loop.create_task(go())

        silly_billy = text[9:]

        spaced = ""
        for i in silly_billy.split("\n"):
            spaced += " " + i + "\n"

        intro = "async def go(message, bot):\n"
        ending = "\nbot.loop.create_task(go(message, bot))"

        complete = intro + spaced + ending
        print(complete)
        try:
            exec(complete)
        except Exception:
            try:
                await message.reply(traceback.format_exc())
            except Exception:
                pass
    if text.lower().startswith("cat!news") and message.author.id == OWNER_ID:
        for i in Channel.select():
            try:
                channeley = await bot.fetch_channel(int(i.channel_id))
                if not isinstance(channeley, Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]):
                    continue
                await channeley.send(text[8:])
            except Exception:
                pass
    if text.lower().startswith("cat!custom") and message.author.id == OWNER_ID:
        stuff = text.split(" ")
        user, _ = User.get_or_create(user_id=stuff[1])
        if stuff[2] == "None":
            user.custom = ""
        else:
            user.custom = stuff[2]
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

    # we try to find a channel with the name "cat", then "bots", then whenever we cat atleast chat
    ch = find("cat", guild.text_channels)
    if not verify(ch):
        ch = find("bots", guild.text_channels)

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
        await ch.send(unofficial_note + "Thanks for adding me!\nTo start, use `/help`!\nJoin the support server here: https://discord.gg/staring\nHave a nice day :)")
    except Exception:
        pass

@bot.tree.command(description="Learn to use the bot")
async def help(message):
    embed1 = discord.Embed(
        title = "How to Setup",
        description = "Server moderator (anyone with *Manage Server* permission) needs to run `/setup` in any channel. After that, cats will start to spawn in 2-20 minute intervals inside of that channel.\nYou can customize those intervals with `/changetimings` and change the spawn message with `/changemessage`.\nCat spawns can also be forced by moderators using `/forcespawn` command.\nYou can have unlimited amounts of setupped channels at once.\nYou can stop the spawning in a channel by running `/forget`.",
        color = 0x6E593C
    ).set_thumbnail(url="https://pomf2.lain.la/f/zncxu6ej.png")

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
        icon_url="https://pomf2.lain.la/f/zncxu6ej.png"
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
                             f"Bot made by {gen_credits['author']}\nWith contributions by {gen_credits['contrib']}.\n\nThis bot adds Cat Hunt to your server with many different types of cats for people to discover! People can see leaderboards and give cats to each other.\n\n" + \
                             f"Thanks to:\n**pathologicals** for the cat image\n**{gen_credits['emoji']}** for getting troh to add cat as an emoji\n**thecatapi.com** for random cats API\n**countik** for TikTok TTS API\n**{gen_credits['trash']}** for making cat, suggestions, and a lot more.\n\n**{gen_credits['tester']}** for being test monkeys\n\n**And everyone for the support!**")

    # add "last update" to footer if we are using git
    if GITHUB_CHANNEL_ID:
        embedVar.timestamp = datetime.datetime.fromtimestamp(int(subprocess.check_output(["git", "show", "-s", "--format=%ct"]).decode("utf-8")))
        embedVar.set_footer(text="Last code update:")
    await message.followup.send(embed=embedVar)

@bot.tree.command(description="Read text as TikTok's TTS woman")
@discord.app_commands.describe(text="The text to be read! (300 characters max)")
async def tiktok(message: discord.Interaction, text: str):
    if message.user.id in BANNED_ID:
        await message.response.send_message("You do not have access to that command.", ephemeral=True)
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
    user = get_profile(message.channel.id, person.id)
    timestamp = round(time.time()) + timeout
    user.timeout = timestamp
    user.save()
    if timeout > 0:
        await message.response.send_message(f"{person.name.replace("_", r"\_")} can't catch cats until <t:{timestamp}:R>")
    else:
        await message.response.send_message(f"{person.name.replace("_", r"\_")} can now catch cats again.")

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
        try:
            channel.spawn_times_min = 120
            channel.spawn_times_max = 1200
        except Exception:
            await message.response.send_message("This channel already has default spawning intervals.")
            return
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
                if self.type == "Appear":
                    check = ["{emoji}", "{type}"]
                else:
                    check = ["{emoji}", "{type}", "{username}", "{count}", "{time}"]
                for i in check:
                    if i not in input_value:
                        await interaction.response.send_message(f"nuh uh! you are missing `{i}`.", ephemeral=True)
                        return
                for i in allowedemojis:
                    if i in input_value:
                        await interaction.response.send_message(f"nuh uh! you cant use `{i}`. sorry!", ephemeral=True)
                        return
                icon = get_emoji("fine_cat")
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
            await interaction.response.send_message(random.choice(funny), ephemeral=True)
            user = get_profile(interaction.guild.id, interaction.user.id)
            user.funny += 1
            user.save()
            return
        modal = InputModal("Appear")
        await interaction.response.send_modal(modal)

    async def ask_catch(interaction):
        nonlocal caller

        if interaction.user != caller:
            await interaction.response.send_message(random.choice(funny), ephemeral=True)
            user = get_profile(interaction.guild.id, interaction.user.id)
            user.funny += 1
            user.save()
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
    suffix = ""
    if WEBHOOK_VERIFY:
        suffix = "\nthere ARE cats for voting tho, check out `/vote`"
    await message.response.send_message("there is no daily cats why did you even try this" + suffix)
    await achemb(message, "daily", "send")

@bot.tree.command(description="View when the last cat was caught in this channel")
async def last(message: discord.Interaction):
    # im gonna be honest i dont know what im doing
    try:
        lasttime = Channel.get_or_none(channel_id=message.channel.id).lastcatches
        displayedtime = f"<t:{int(lasttime)}:R>"
    except Exception:
        displayedtime = "forever ago"
    await message.response.send_message(f"the last cat in this channel was caught {displayedtime}.")


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
    if minus_achs != 0:
        minus_achs = f" + {minus_achs}"
    else:
        minus_achs = ""

    # now we count time i think
    catch_time = person.time
    is_empty = True

    if catch_time >= 99999999999999:
        catch_time = "never"
    else:
        catch_time = str(round(float(catch_time) * 100) / 100)

    slow_time = person.timeslow

    if str(slow_time) == "0":
        slow_time = "never"
    else:
        slow_time = float(slow_time) / 3600
        slow_time = str(round(slow_time * 100) / 100)

    if me:
        your = "Your"
    else:
        your = person_id.name.replace("_", r"\_") + "'s"

    if user.emoji:
        emoji_prefix = str(user.emoji) + " "
    else:
        emoji_prefix = ""

    if user.color:
        color = user.color
    else:
        color = "#6E593C"

    embedVar = discord.Embed(
        title=f"{emoji_prefix}{your} cats:",
        description=f"{your} fastest catch is: {catch_time} s\nand {your} slowest catch is: {slow_time} h\nAchievements unlocked: {unlocked}/{total_achs}{minus_achs}",
        color=discord.Colour.from_str(color)
    )

    give_collector = True
    total = 0

    # for every cat
    for i in cattypes:
        icon = get_emoji(i.lower() + "cat")
        cat_num = person[f"cat_{i}"]
        if cat_num != 0:
            total += cat_num
            embedVar.add_field(name=f"{icon} {i}", value=cat_num, inline=True)
            is_empty = False
        else:
            give_collector = False

    if user.custom:
        icon = get_emoji(user.custom.lower() + "cat")
        embedVar.add_field(name=f"{icon} {user.custom}", value=1, inline=True)

    if is_empty and not user.custom:
        embedVar.add_field(name="None", value=f"u hav no cats {get_emoji('cat_cry')}", inline=True)

    if embedVar.description:
        embedVar.description += f"\nTotal cats: {total}"

    if user.image.startswith("https://cdn.discordapp.com/attachments/"):
        embedVar.set_thumbnail(url=user.image)

    if me:
        # give some aches if we are vieweing our own inventory
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

    if DONOR_CHANNEL_ID:
        embedVar.set_footer(text="👑 Make this pretty with /editprofile")

    await message.followup.send(embed=embedVar)


@bot.tree.command(description="its raining cats")
async def rain(message: discord.Interaction):
    user, _ = User.get_or_create(user_id=message.user.id)

    if not user.claimed_free_rain:
        user.shortrain += 1
        user.claimed_free_rain = True
        user.save()

    embed = discord.Embed(title="Cat Rains", description=f"""Cat Rains are power-ups which spawn cats instantly for a limited amounts of time in channel of your choice.

You can get those by buying them at our [store](<https://hipolink.me/milenakos>) or by winning them in an event.
This bot is developed by a single person so buying one would be very appreciated.

You currently have:
2-minute long rains **{user.shortrain}**
10-minute long rains **{user.mediumrain}**
20-minute long rains **{user.longrain}**

Note: fastest times are not saved during rains.

Click buttons below to start a rain in the current channel.""", color=0x6E593C)

    async def do_rain(interaction, rain_type):
        # i LOOOOVE checks
        if message.user.id != interaction.user.id:
            await interaction.response.send_message(random.choice(funny), ephemeral=True)
            profile = get_profile(message.guild.id, message.user.id)
            profile.funny += 1
            profile.save()
            return

        if (rain_type == "shortrain" and not user.shortrain) or (rain_type == "mediumrain" and not user.mediumrain) or (rain_type == "longrain" and not user.longrain):
            await interaction.response.send_message("you dont have a rain of dat type! buy one [here](<https://hipolink.me/milenakos>)", ephemeral=True)
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

        if cat_rains.get(str(message.channel.id), 0) != 0:
            await interaction.response.send_message("there is already a rain running!", ephemeral=True)
            return

        if not isinstance(message.channel, Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]):
            return

        type_mappings = {"shortrain": 120, "mediumrain": 600, "longrain": 1200}
        cat_rains[str(message.channel.id)] = time.time() + type_mappings[rain_type]
        if rain_type == "shortrain":
            user.shortrain -= 1
        elif rain_type == "mediumrain":
            user.mediumrain -= 1
        elif rain_type == "longrain":
            user.longrain -= 1
        user.save()
        await message.channel.send(f"cat rain was started by <@{interaction.user.id}>!")
        await spawn_cat(str(message.channel.id))

    async def short(interaction):
        await do_rain(interaction, "shortrain")

    async def medium(interaction):
        await do_rain(interaction, "mediumrain")

    async def long(interaction):
        await do_rain(interaction, "longrain")

    button1 = Button(label="Short", style=ButtonStyle.blurple)
    button1.callback = short

    button2 = Button(label="Medium", style=ButtonStyle.blurple)
    button2.callback = medium

    button3 = Button(label="Long", style=ButtonStyle.blurple)
    button3.callback = long

    view = View(timeout=3600)
    view.add_item(button1)
    view.add_item(button2)
    view.add_item(button3)

    await message.response.send_message(embed=embed, view=view)

@bot.tree.command(description="Support Cat Bot!")
async def donate(message: discord.Interaction):
    thing = discord.File("images/supporter.png", filename="supporter.png")
    await message.response.send_message("👑 For as little as $3 you can support Cat Bot and unlock profile customization!\n<https://catbot.minkos.lol/donate>", file=thing)

@bot.tree.command(description="Buy Cat Rains!")
async def store(message: discord.Interaction):
    await message.response.send_message("☔ Cat rains make cats spawn instantly! Make your server active, get more cats and have fun!\n<https://hipolink.me/milenakos>")

@bot.tree.command(description="[SUPPORTER] Customize your profile!")
@discord.app_commands.rename(provided_emoji='emoji')
@discord.app_commands.describe(color="Color for your profile in hex form (e.g. #6E593C)",
                               provided_emoji="A default Discord emoji to show near your username.",
                               image="A square image to show in top-right corner of your profile.")
async def editprofile(message: discord.Interaction, color: Optional[str], provided_emoji: Optional[str], image: Optional[discord.Attachment]):
    user, _ = User.get_or_create(user_id=message.user.id)
    if not user.premium:
        await message.response.send_message("👑 This feature is supporter-only!\nFor as little as $3 you can support Cat Bot and unlock profile customization!\n<https://catbot.minkos.lol/donate>")
        return

    if provided_emoji and discord_emoji.to_discord(provided_emoji.strip(), get_all=False, put_colons=False):
        user.emoji = provided_emoji.strip()

    if color:
        match = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color)
        if match:
            user.color = match.group(0)
    if image:
        # reupload image
        channeley = bot.get_channel(DONOR_CHANNEL_ID)
        file = await image.to_file()
        if not isinstance(channeley, Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]):
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
        if req == "catch":
            num_str = num
            if home:
                progress = int(user.progress)
                num_str = f"{num - progress} more"
            return f"Catch {num_str} cats. \nReward: {amount} {thetype} cats."
        elif req == "catch_fast":
            return f"Catch a cat in under {num} seconds.\nReward: {amount} {thetype} cats."
        elif req == "catch_type":
            an = ""
            if num[0].lower() in "aieuo":
                an = "n"
            return f"Catch a{an} {num} cat.\nReward: {amount} {thetype} cats."
        elif req == "nothing":
            return "Touch grass.\nReward: 1 ~~e~~Girl~~cats~~friend."
        else:
            return "Complete a battlepass level.\nReward: freedom"

    current = "🟨"
    if battle["levels"][current_level]["req"] == "nothing":
        current = "⬛"
    if current_level != 0:
        embedVar.add_field(name=f"✅ Level {current_level} (complete)", value=battlelevel(battle, current_level - 1), inline=False)
    embedVar.add_field(name=f"{current} Level {current_level + 1}", value=battlelevel(battle, current_level, True), inline=False)
    embedVar.add_field(name=f"Level {current_level + 2}", value=battlelevel(battle, current_level + 1), inline=False)

    await message.followup.send(embed=embedVar)

@bot.tree.command(description="Pong")
async def ping(message: discord.Interaction):
    try:
        latency = round(bot.latency * 1000)
        if latency >= 100:
            await achemb(message, "infinite", "send")
    except Exception:
        latency = "infinite"
        await achemb(message, "infinite", "send")
    await message.response.send_message(f"cat has brain delay of {latency} ms " + str(get_emoji("staring_cat")))

@bot.tree.command()
@discord.app_commands.describe(mentions='The members you want to get the joined date from; defaults to the user who uses the command')
async def joined(interaction: discord.Interaction, mentions: Optional[str]):
    if not mentions:
        members = [interaction.user]
    else:
        members = []
        for user_id in re.findall(r"\d{17,19}", mentions):
            member = interaction.guild.get_member(user_id)
            if member:
                members.append(member)

@bot.tree.command(description="give cats now")
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(person="Whom to donate?", cat_type="im gonna airstrike your house from orbit", amount="And how much?")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def gift(message: discord.Interaction, person: discord.User, cat_type: str, amount: Optional[int]):
    if not amount:
        amount = 1  # default the amount to 1
    person_id = person.id

    if cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    user = get_profile(message.guild.id, message.user.id)
    catbot = get_profile(message.guild.id, 966695034340663367)
    # if we even have enough cats
    if user[f"cat_{cat_type}"] >= amount and amount > 0 and message.user.id != person_id:
        reciever = get_profile(message.guild.id, person_id)
        user[f"cat_{cat_type}"] -= amount
        reciever[f"cat_{cat_type}"] += amount
        user.save()
        reciever.save()
        embed = discord.Embed(title="Success!", description=f"Successfully transfered {amount} {cat_type} cats from <@{message.user.id}> to <@{person_id}>!", color=0x6E593C)
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

        # handle tax
        if amount >= 5 and person_id != OWNER_ID and cat_type == "Fine":
            tax_amount = round(amount * 0.2)

            async def pay(interaction):
                if interaction.user.id == message.user.id:
                    await interaction.response.defer()
                    try:
                        await interaction.edit_original_response(view=None)
                    except Exception:
                        pass
                    user.cat_Fine -= tax_amount
                    catbot.cat_Fine += tax_amount
                    user.save()
                    catbot.save()
                    await achemb(message, "good_citizen", "send")
                    await interaction.followup.send(f"Tax of {tax_amount} Fine cats was withdrawn from your account!")
                else:
                    await interaction.response.send_message(random.choice(funny), ephemeral=True)
                    clicker = get_profile(interaction.guild.id, interaction.user.id)
                    clicker.funny += 1
                    clicker.save()

            async def evade(interaction):
                if interaction.user.id == message.user.id:
                    await interaction.response.defer()
                    try:
                        await interaction.edit_original_response(view=None)
                    except Exception:
                        pass
                    await achemb(message, "secret", "send")
                    await interaction.followup.send(f"You evaded the tax of {tax_amount} Fine cats.")
                else:
                    await interaction.followup.send(random.choice(funny), ephemeral=True)
                    clicker = get_profile(interaction.guild.id, interaction.user.id)
                    clicker.funny += 1
                    clicker.save()

            embed = discord.Embed(title="HOLD UP!", description="Thats rather large amount of fine cats! You will need to pay a cat tax of 20% your transaction, do you agree?", color=0x6E593C)

            button = Button(label="Pay!", style=ButtonStyle.green)
            button.callback = pay

            button2 = Button(label="Evade the tax", style=ButtonStyle.red)
            button2.callback = evade

            myview = View(timeout=3600)

            myview.add_item(button)
            myview.add_item(button2)
            if not isinstance(message.channel, Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]):
                return
            try:
                await message.channel.send(embed=embed, view=myview)
            except Exception:
                pass
    else:
        # haha skill issue
        await message.response.send_message("no", ephemeral=True)
        if message.user.id == person_id:
            await achemb(message, "lonely", "send")

@bot.tree.command(description="Trade cats!")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="why would you need description")
async def trade(message: discord.Interaction, person_id: discord.User):
    person1 = message.user
    person2 = person_id

    blackhole = False

    if person1 == person2:
        await achemb(message, "introvert", "send")

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
        person2gives = {"eGirl": 9999999}

    # this is the deny button code
    async def denyb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole
        if interaction.user != person1 and interaction.user != person2:
            await interaction.response.send_message(random.choice(funny), ephemeral=True)
            clicker = get_profile(interaction.guild.id, interaction.user.id)
            clicker.funny += 1
            clicker.save()
            return

        blackhole = True
        person1gives = {}
        person2gives = {}
        try:
            await interaction.edit_original_response(content=f"<@{interaction.user.id}> has cancelled the trade.", embed=None, view=None)
        except Exception:
            pass

    # this is the accept button code
    async def acceptb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, person1value, person2value
        if interaction.user != person1 and interaction.user != person2:
            await interaction.response.send_message(random.choice(funny), ephemeral=True)
            clicker = get_profile(interaction.guild.id, interaction.user.id)
            clicker.funny += 1
            clicker.save()
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
            error = False
            # check if we have enough cats (person could have moved them during the trade)
            for k, v in person1gives.items():
                if user1[f"cat_{k}"] < v:
                    error = True
                    break

            for k, v in person2gives.items():
                if user2[f"cat_{k}"] < v:
                    error = True
                    break

            if error:
                try:
                    await interaction.edit_original_response(content="Not enough cats - some of the cats disappeared while trade was happening", embed=None, view=None)
                except Exception:
                    await interaction.followup.send("Not enough cats - some of the cats disappeared while trade was happening")
                return

            # exchange cats
            cat_count = 0
            for k, v in person1gives.items():
                cat_count += v
                user1[f"cat_{k}"] -= v
                user2[f"cat_{k}"] += v

            for k, v in person2gives.items():
                cat_count += v
                user1[f"cat_{k}"] += v
                user2[f"cat_{k}"] -= v

            user1.save()
            user2.save()

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
            await interaction.response.send_message(random.choice(funny), ephemeral=True)
            clicker = get_profile(interaction.guild.id, interaction.user.id)
            clicker.funny += 1
            clicker.save()
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
        await handle_modal(currentuser, interaction)

    async def handle_modal(currentuser, interaction):
        # not sure why i needed this helper that badly but oh well
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

        add = Button(label="Offer cats", style=ButtonStyle.blurple)
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
            for k, v in persongives.items():
                valuenum += (len(CAT_TYPES) / type_dict[k]) * v
                aicon = get_emoji(k.lower() + "cat")
                valuestr += str(aicon) + " " + k + " " + str(v) + "\n"
            if not valuestr:
                valuestr = "No cats offered!"
            else:
                valuestr += f"*Total value: {round(valuenum)}*"
                if number == 1:
                    person1value = round(valuenum)
                else:
                    person2value = round(valuenum)
            coolembed.add_field(name=f"{icon} {person.name.replace("_", r"\_")}", inline=True, value=valuestr)

        field(person1accept, person1gives, person1, 1)
        field(person2accept, person2gives, person2, 2)

        return coolembed, view

    embed, view = await gen_embed()
    if not view:
        await message.response.send_message(embed=embed)
    else:
        await message.response.send_message(embed=embed, view=view)

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
                min_length=1,
                max_length=50,
                label="Cat type",
                placeholder="Fine"
            )
            self.add_item(self.cattype)

            self.amount = discord.ui.TextInput(
                label="Amount of cats to offer",
                min_length=1,
                max_length=50,
                placeholder="1"
            )
            self.add_item(self.amount)

        # this is ran when user submits
        async def on_submit(self, interaction: discord.Interaction):
            nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
            # hella ton of checks
            try:
                if int(self.amount.value) <= 0:
                    raise Exception
            except Exception:
                await interaction.response.send_message("plz number?", ephemeral=True)
                return

            if self.cattype.value not in cattypes:
                await interaction.response.send_message("add a valid cat type 💀💀💀", ephemeral=True)
                return

            try:
                if self.currentuser == 1:
                    currset = person1gives[self.cattype.value]
                else:
                    currset = person2gives[self.cattype.value]
            except Exception:
                currset = 0

            if (self.currentuser == 1 and user1[f"cat_{self.cattype.value}"] < int(self.amount.value) + currset) or \
                (self.currentuser == 2 and user2[f"cat_{self.cattype.value}"] < int(self.amount.value) + currset):
                await interaction.response.send_message("hell naww dude you dont even have that many cats 💀💀💀", ephemeral=True)
                return

            # OKE SEEMS GOOD LETS ADD CATS TO THE TRADE
            if self.currentuser == 1:
                try:
                    person1gives[self.cattype.value] += int(self.amount.value)
                except Exception:
                    person1gives[self.cattype.value] = int(self.amount.value)
            else:
                try:
                    person2gives[self.cattype.value] += int(self.amount.value)
                except Exception:
                    person2gives[self.cattype.value] = int(self.amount.value)

            await interaction.response.defer()
            await update_trade_embed(interaction)

@bot.tree.command(description="Get Cat Image, does not add a cat to your inventory")
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(cat_type="select a cat type ok")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def cat(message: discord.Interaction, cat_type: Optional[str]):
    if cat_type and cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    image = f"images/spawn/{cat_type.lower()}_cat.png" if cat_type else "images/cat.png" # ternary operator because why not
    file = discord.File(image, filename=image)
    await message.response.send_message(file=file)

@bot.tree.command(description="Get Cursed Cat")
async def cursed(message: discord.Interaction):
    file = discord.File("images/cursed.jpg", filename="cursed.jpg")
    await message.response.send_message(file=file)

@bot.tree.command(description="Get Your balance")
async def bal(message: discord.Interaction):
    file = discord.File("images/money.png", filename="money.png")
    embed = discord.Embed(title="cat coins", color=0x6E593C).set_image(url="attachment://money.png")
    await message.response.send_message(file=file, embed=embed)

@bot.tree.command(description="Brew some coffee to catch cats more efficiently")
async def brew(message: discord.Interaction):
   await message.response.send_message("HTTP 418: I'm a teapot. <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/418>")
   await achemb(message, "coffee", "send")

@bot.tree.command(description="Gamble your life savings away in our totally-not-rigged casino!")
async def casino(message: discord.Interaction):
    if message.user.id in casino_lock:
        await message.response.send_message("you get kicked out of the casino because you are already there, and two of you playing at once would cause a glitch in the universe", ephemeral=True)
        await achemb(message, "paradoxical_gambler", "send")
        return

    embed = discord.Embed(title="The Casino", description=f"One spin costs 5 {get_emoji('epiccat')} Epic cats", color=0x750F0E)

    async def spin(interaction):
        nonlocal message
        if interaction.user.id != message.user.id:
            await interaction.response.send_message(random.choice(funny), ephemeral=True)
            clicker = get_profile(interaction.guild.id, interaction.user.id)
            clicker.funny += 1
            clicker.save()
            return
        if message.user.id in casino_lock:
            await interaction.response.send_message("you get kicked out of the casino because you are already there, and two of you playing at once would cause a glitch in the universe", ephemeral=True)
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
            embed = discord.Embed(title="The Casino", description=f"**{i}**", color=0x750F0E)
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass
            await asyncio.sleep(1.5)

        amount = random.randint(1, 5)

        embed = discord.Embed(title="The Casino", description=f"You won:\n**{get_emoji('finecat')} {amount} Fine cats**", color=0x750F0E)
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

if WEBHOOK_VERIFY:
    @bot.tree.command(description="Vote for Cat Bot for free cats")
    async def vote(message: discord.Interaction):
        await message.response.defer()

        current_day = datetime.datetime.utcnow().isoweekday()
        user, _ = User.get_or_create(user_id=message.user.id)

        if message.guild is not None:
            user.vote_channel = message.channel.id
            user.save()

        if current_day == 6 or current_day == 7:
            weekend_message = "🌟 **It's weekend! All vote rewards are DOUBLED!**\n\n"
        else:
            weekend_message = ""

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

        embedVar = discord.Embed(title="Vote for Cat Bot", description=f"{weekend_message}Vote for Cat Bot on top.gg every 12 hours to recieve mystery cats.\nIf bot didn't automatically detect your vote, just say `i voted`.", color=0x6E593C)
        await message.followup.send(embed=embedVar, view=view)


@bot.tree.command(description="get a super accurate rating of something")
@discord.app_commands.describe(thing="The thing or person to check", stat="The stat to check")
async def rate(message: discord.Interaction, thing: str, stat: str):
    if len(thing) > 100 or len(stat) > 100:
        await message.response.send_message("thats kinda long")
        return
    await message.response.send_message(f"{thing} is {random.randint(0, 100)}% {stat}")


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
        "chocolate is bad for cats",
        "cat",
        "cats land on their feet",
        "cats bring you mice/birds as a gift",
        "cats are the best"
    ]

    # give a fact from the list or the API
    if random.randint(0, 1) == 0:
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

    if not isinstance(message.channel, Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]):
        return

    user = get_profile(message.guild.id, message.user.id)
    user.facts += 1
    user.save()
    if user.facts >= 10:
        await achemb(message, "fact_enjoyer", "send")

    try:
        channel = Channel.get_or_none(channel_id=message.channel.id)
        if channel and channel.cat:
            catchmsg = await message.channel.fetch_message(channel.cat)
            if str(get_emoji("professorcat")) in catchmsg.content:
                await achemb(message, "nerd_battle", "send")
    except Exception:
        pass

async def light_market(message):
    cataine_prices = [[10, "Fine"], [30, "Fine"], [20, "Good"], [15, "Rare"], [20, "Wild"], [10, "Epic"], [20, "Sus"], [15, "Rickroll"],
                      [7, "Superior"], [5, "Legendary"], [3, "8bit"], [4, "Professor"], [3, "Real"], [2, "Ultimate"], [1, "eGirl"]]
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

        random.seed(datetime.datetime.utcnow().isocalendar()[1]) # hopefully that works
        deals = []

        r = range(random.randint(3, 5))
        for i in r:
            # 3-5 prices are possible per week
            deals.append(random.randint(0, 14))

        deals.sort()

        for i in r:
            deals[i] = cataine_prices[deals[i]]

        random.seed() # because we don’t want the most recent time this was opened to influence cat spawn times and rarities
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
                      [7, "Superior"], [5, "Legendary"], [3, "8bit"], [4, "Professor"], [3, "Real"], [2, "Ultimate"], [1, "eGirl"], [100, "eGirl"]]
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
            phrases = ["*Because of my addiction I'm paying them a fortune.*",
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
                       "*Uh oh.*"]

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
    if minus_achs != 0:
        minus_achs = f" + {minus_achs}"
    else:
        minus_achs = ""
    embedVar = discord.Embed(
            title="Your achievements:", description=f"{unlocked}/{total_achs}{minus_achs}", color=0x6E593C
    )

    if unlocked >= 15:
        await achemb(message, "achiever", "send")

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
                    if v["is_hidden"]:
                        newembed.add_field(name=icon + v["title"], value="???", inline=True)
                    else:
                        newembed.add_field(name=icon + v["title"], value=v["description"], inline=True)

        return newembed

    # handle button presses (either send hidden embed or laugh at user)
    async def send_full(interaction):
        nonlocal message
        if interaction.user.id == message.user.id:
            await interaction.response.send_message(embed=gen_new("Cat Hunt"), ephemeral=True, view=insane_view_generator("Cat Hunt"))
        else:
            await interaction.response.send_message(random.choice(funny), ephemeral=True)
            clicker = get_profile(interaction.guild.id, interaction.user.id)
            clicker.funny += 1
            clicker.save()
            await achemb(interaction, "curious", "send")

    # creates buttons at the bottom of the full view
    def insane_view_generator(category):
        myview = View(timeout=3600)
        buttons_list = []
        lambdas_list = []

        # would be much more optimized but i cant get this to work
        # for i in ["Cat Hunt", "Random", "Unfair"]:
        #   if category == i:
        #        buttons_list.append(Button(label=i, style=ButtonStyle.green))
        #   else:
        #        buttons_list.append(Button(label=i, style=ButtonStyle.blurple))
        #   lambdas_list.append(lambda interaction : (await interaction.edit_original_response(embed=gen_new(i), view=insane_view_generator(i)) for _ in '_').__anext__())
        #   buttons_list[-1].callback = lambdas_list[-1]

        async def callback_hell(interaction, thing):
            await interaction.response.defer()
            try:
                await interaction.edit_original_response(embed=gen_new(thing), view=insane_view_generator(thing))
            except Exception:
                pass

            if hidden_counter == 3 and user.dark_market_active:
                await achemb(message, "dark_market", "followup")
                if not user.story_complete:
                    # open the totally not suspicious dark market
                    await dark_market(message)
                else:
                    await light_market(message)

            if hidden_counter == 20:
                await achemb(interaction, "darkest_market", "send")

        if category == "Cat Hunt":
            buttons_list.append(Button(label="Cat Hunt", style=ButtonStyle.green))
        else:
            buttons_list.append(Button(label="Cat Hunt", style=ButtonStyle.blurple))
        lambdas_list.append(lambda interaction : (await callback_hell(interaction, "Cat Hunt") for _ in '_').__anext__())
        buttons_list[-1].callback = lambdas_list[-1]

        if category == "Random":
            buttons_list.append(Button(label="Random", style=ButtonStyle.green))
        else:
            buttons_list.append(Button(label="Random", style=ButtonStyle.blurple))
        lambdas_list.append(lambda interaction : (await callback_hell(interaction, "Random") for _ in '_').__anext__())
        buttons_list[-1].callback = lambdas_list[-1]

        if category == "Silly":
            buttons_list.append(Button(label="Silly", style=ButtonStyle.green))
        else:
            buttons_list.append(Button(label="Silly", style=ButtonStyle.blurple))
        lambdas_list.append(lambda interaction : (await callback_hell(interaction, "Silly") for _ in '_').__anext__())
        buttons_list[-1].callback = lambdas_list[-1]

        if category == "Hard":
            buttons_list.append(Button(label="Hard", style=ButtonStyle.green))
        else:
            buttons_list.append(Button(label="Hard", style=ButtonStyle.blurple))
        lambdas_list.append(lambda interaction : (await callback_hell(interaction, "Hard") for _ in '_').__anext__())
        buttons_list[-1].callback = lambdas_list[-1]

        if category == "Hidden":
            buttons_list.append(Button(label="Hidden", style=ButtonStyle.green))
        else:
            buttons_list.append(Button(label="Hidden", style=ButtonStyle.blurple))
        lambdas_list.append(lambda interaction : (await callback_hell(interaction, "Hidden") for _ in '_').__anext__())
        buttons_list[-1].callback = lambdas_list[-1]

        for j in buttons_list:
            myview.add_item(j)
        return myview

    button = Button(label="View all achievements", style=ButtonStyle.blurple)
    button.callback = send_full

    myview = View(timeout=3600)
    myview.add_item(button)

    await message.response.send_message(embed=embedVar, view=myview)

async def catch(message: discord.Interaction, msg: discord.Message):
    user = get_profile(message.guild.id, message.user.id)
    if int(user.catchcooldown) + 6 > time.time():
        await message.response.send_message("your phone is overheating bro chill", ephemeral=True)
        return
    await message.response.defer()
    msg2img.msg2img(msg, bot, True)
    file = discord.File("generated.png", filename="generated.png")
    user.catchcooldown = time.time()
    await message.followup.send("cought in 4k", file=file)

    await achemb(message, "4k", "send")

    if msg.author.id == bot.user.id and msg.content == "cought in 4k":
        await achemb(message, "8k", "send")

    try:
        is_cat = Channel.get(channel_id=message.channel.id).cat
    except Exception:
        is_cat = False

    if int(is_cat) == int(msg.id):
        await achemb(message, "not_like_that", "send")

# pointLaugh lives on in our memories

@bot.tree.command(description="View the leaderboards")
@discord.app_commands.rename(leaderboard_type="type")
@discord.app_commands.describe(leaderboard_type="The leaderboard type to view!")
async def leaderboards(message: discord.Interaction, leaderboard_type: Optional[Literal["Cats", "Fastest", "Slowest"]]):
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
        main = False
        fast = False
        slow = False
        if type == "fast":
            fast = True
        elif type == "slow":
            slow = True
        else:
            main = True
        the_dict = {}
        rarest = -1
        rarest_holder = {f"<@{bot.user.id}>": 0}
        rarities = cattypes

        if fast:
            time_type = ""
            default_value = "99999999999999"
            title = "Time"
            unit = "sec"
            devider = 1
        elif slow:
            time_type = "slow"
            default_value = "0"
            title = "Slow"
            unit = "h"
            devider = 3600
        else:
            default_value = "0"
            title = ""
            unit = "cats"
            devider = 1
        for i in Profile.select().where(Profile.guild_id == message.guild.id):
            if not main:
                if time_type == "slow":
                    value = i.timeslow
                    if value == 0:
                        continue
                else:
                    value = i.time
                    if value == 99999999999999:
                        continue
            else:
                value = 0
                for a in cattypes:
                    try:
                        b = i[f"cat_{a}"]
                        value += b
                        if b > 0 and rarities.index(a) > rarest:
                            rarest = rarities.index(a)
                            rarest_holder = {f"<@{i.user_id}>": b}
                        elif b > 0 and rarities.index(a) == rarest:
                            rarest_holder[f"<@{i.user_id}>"] = b
                    except Exception:
                        pass
                if value == 0:
                    continue
            if str(value) != default_value:
                # round the value (for time dislays)
                thingy = round((float(value) / float(devider)) * 100) / 100

                # if it perfectly ends on .00, trim it
                if thingy == int(thingy):
                    thingy = int(thingy)

                the_dict[f" {unit}: <@{i.user_id}>"] = thingy
                if i == str(interaction.user.id):
                    interactor = thingy
                if i == str(message.user.id):
                    messager = thingy

        # some weird quick sorting thing (dont you just love when built-in libary you never heard of saves your ass)
        heap = [(-value, key) for key, value in the_dict.items()]
        if fast:
            largest = heapq.nlargest(15, heap)
        else:
            largest = heapq.nsmallest(15, heap)
        largest = [(key, -value) for value, key in largest]
        string = ""

        # find the placement of the person who ran the command and optionally the person who pressed the button
        interactor_placement = 0
        messager_placement = 0
        if interactor:
            for i in the_dict.values():
                if (fast and interactor >= i) or (not fast and interactor <= i):
                    interactor_placement += 1
        if messager and message.user.id != interaction.user.id:
            for i in the_dict.values():
                if (fast and messager >= i) or (not fast and messager <= i):
                    messager_placement += 1

        # rarest cat display
        if main:
            catmoji = get_emoji(rarities[rarest].lower() + "cat")
            if rarest != -1:
                rarest_holder = list(dict(sorted(rarest_holder.items(), key=lambda item: item[1], reverse=True)).keys())
                joined = ", ".join(rarest_holder)
                if len(rarest_holder) > 10:
                    joined = f"{len(rarest_holder)} people"
                string = f"Rarest cat: {catmoji} ({joined}'s)\n"

        # the little place counter
        current = 1
        for i, num in largest:
            string = string + str(current) + ". " + str(num) + i + "\n"
            if str(message.user.id) in i and current <= 5:
                await achemb(message, "leader", "send")
            current += 1

        # add the messager and interactor
        if messager_placement > 15 or interactor_placement > 15:
            string = string + "...\n"
            # sort them correctly!
            if messager_placement > interactor_placement:
                # interactor should go first
                if interactor_placement > 15 and str(interaction.user.id) not in string:
                    string = string + f"{interactor_placement}\\. {interactor} {unit}: <@{interaction.user.id}>\n"
                if messager_placement > 15 and str(message.user.id) not in string:
                    string = string + f"{messager_placement}\\. {messager} {unit}: <@{message.user.id}>\n"
            else:
                # messager should go first
                if messager_placement > 15 and str(message.user.id) not in string:
                    string = string + f"{messager_placement}\\. {messager} {unit}: <@{message.user.id}>\n"
                if interactor_placement > 15 and str(interaction.user.id) not in string:
                    string = string + f"{interactor_placement}\\. {interactor} {unit}: <@{interaction.user.id}>\n"

        embedVar = discord.Embed(
                title=f"{title} Leaderboards:", description=string, color=0x6E593C
        ).set_footer(text="☔ Get tons of cats /rain")

        # handle funny buttons
        if not main:
            button1 = Button(label="Cats", style=ButtonStyle.blurple)
        else:
            button1 = Button(label="Refresh", style=ButtonStyle.green)

        if not fast:
            button2 = Button(label="Fastest", style=ButtonStyle.blurple)
        else:
            button2 = Button(label="Refresh", style=ButtonStyle.green)

        if not slow:
            button3 = Button(label="Slowest", style=ButtonStyle.blurple)
        else:
            button3 = Button(label="Refresh", style=ButtonStyle.green)

        button1.callback = catlb
        button2.callback = fastlb
        button3.callback = slowlb

        myview = View(timeout=3600)
        myview.add_item(button1)
        myview.add_item(button2)
        myview.add_item(button3)

        # just send if first time, otherwise edit existing
        try:
            if not do_edit:
                raise Exception
            await interaction.edit_original_response(embed=embedVar, view=myview)
        except Exception:
            await interaction.followup.send(embed=embedVar, view=myview)

    # helpers! everybody loves helpers.
    async def slowlb(interaction):
        await lb_handler(interaction, "slow")

    async def fastlb(interaction):
        await lb_handler(interaction, "fast")

    async def catlb(interaction):
        await lb_handler(interaction, "main")

    await lb_handler(message, {"Fastest": "fast", "Slowest": "slow", "Cats": "main"}[leaderboard_type], False)

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
    embed = discord.Embed(title="Success!", description=f"gave <@{person_id.id}> {amount} {cat_type} cats", color=0x6E593C)
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
                await message.response.send_message(f":x: Missing Permissions! Please give me the following: - {'\n- '.join(missing_perms)}]\nHint: try setting channel permissions if server ones don't work.")
                return

            if isinstance(message.channel, discord.Thread):
                parent = bot.get_channel(message.channel.parent_id)
                if not isinstance(parent, discord.TextChannel):
                    return
                wh = await parent.create_webhook(name="Cat Bot", avatar=f.read())
                Channel.create(channel_id=message.channel.id, webhook=wh.url, thread_mappings=True)
            elif isinstance(message.channel, Union[discord.TextChannel, discord.VoiceChannel]):
                wh = await message.channel.create_webhook(name="Cat Bot", avatar=f.read())
                Channel.create(channel_id=message.channel.id, webhook=wh.url, thread_mappings=False)
        except Exception:
            pass

    await spawn_cat(str(message.channel.id))
    await message.response.send_message(f"ok, now i will also send cats in <#{message.channel.id}>")

@bot.tree.command(description="(ADMIN) Undo the setup")
@discord.app_commands.default_permissions(manage_guild=True)
async def forget(message: discord.Interaction):
    if channel := Channel.get_or_none(channel_id=message.channel.id):
        channel.delete_instance()
        await message.response.send_message(f"ok, now i wont send cats in <#{message.channel.id}>")
    else:
        await message.response.send_message("your an idiot there is literally no cat setupped in this channel you stupid")

@bot.tree.command(description="LMAO TROLLED SO HARD :JOY:")
async def fake(message: discord.Interaction):
    file = discord.File("images/australian cat.png", filename="australian cat.png")
    icon = get_emoji("egirlcat")
    if not isinstance(message.channel, Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]):
        return
    try:
        await message.channel.send(str(icon) + " eGirl cat hasn't appeared! Type \"cat\" to catch ratio!", file=file)
        await message.response.send_message("OMG TROLLED SO HARD LMAOOOO 😂", ephemeral=True)
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
        if ach_id in ach_names:
            valid = True
        else:
            valid = False
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
        person[ach_id] = not person[ach_id]
        color, title, icon = 0x007F0E, "Achievement forced!", "https://pomf2.lain.la/f/hbxyiv9l.png"
        if reverse:
            color, title, icon = 0xff0000, "Achievement removed!", "https://pomf2.lain.la/f/b8jxc27g.png"
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
    try:
        user = get_profile(message.guild.id, person_id.id)
        user.delete_instance()
        await message.response.send_message(embed=discord.Embed(color=0x6E593C, description=f'Done! rip <@{person_id.id}>. f\'s in chat.'))
    except Exception:
        await message.response.send_message("ummm? this person isnt even registered in cat bot wtf are you wiping?????", ephemeral=True)

@bot.tree.command(description="(ADMIN) [VERY DANGEROUS] Reset all Cat Bot data of this server")
@discord.app_commands.default_permissions(manage_guild=True)
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

    async def count(interaction):
        nonlocal message, counter
        if interaction.user.id == message.user.id:
            await interaction.response.defer()
            counter -= 1
            if counter <= 0:
                # Scary!
                Profile.delete().where(Profile.guild_id == message.guild.id).execute()
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
            await interaction.response.send_message(random.choice(funny), ephemeral=True)
            await achemb(interaction, "curious", "send")

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

    embedVar = discord.Embed(title="Vote redeemed!", description=f"{weekend_message}You have recieved {icon} {amount} {cattype} cats for voting on {cool_name}.\nVote again in 12 hours.", color=0x007F0E)
    try:
        await channeley.send(f"<@{user.user_id}>", embed=embedVar, view=view)
    except Exception:
        pass

async def recieve_vote(request):
    if request.headers.get('authorization', '') != WEBHOOK_VERIFY:
        return web.Response(text="bad", status=403)
    request_json = await request.json()

    user, _ = User.get_or_create(user_id=int(request_json["user"]))
    type = "topgg"
    if user.vote_time_topgg + 43100 > time.time():
        # top.gg is NOT realiable with their webhooks, but we politely pretend they are
        return web.Response(text="you fucking dumb idiot", status=200)

    try:
        channeley = await bot.fetch_channel(user.vote_channel)
        if not isinstance(channeley, Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]) or not channeley.guild:
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

    if CRASH_MODE == "DM":
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
    elif CRASH_MODE == "RAISE":
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

    if WEBHOOK_VERIFY:
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
