import nextcord as discord
import msg2img, base64, sys, re, time, json, traceback, os, io, aiohttp, heapq, datetime, subprocess, asyncio, tarfile
from nextcord.ext import tasks, commands
from nextcord import ButtonStyle
from nextcord.ui import Button, View
from typing import Optional
from random import randint, choice
from PIL import Image
from collections import UserDict

### Setup values start

GUILD_ID = 966586000417619998 # for emojis
BACKUP_ID = 1060545763194707998 # channel id for db backups, private extremely recommended

# discord bot token, use os.environ for more security
TOKEN = os.environ['token']
# TOKEN = "token goes here"

# set to False to disable /vote
TOP_GG_TOKEN = os.environ['topggtoken']

# this will automatically restart the bot if message in GITHUB_CHANNEL_ID is sent, you can use a github webhook for that
# set to False to disable
GITHUB_CHANNEL_ID = 1060965767044149249

BANNED_ID = [1029044762340241509] # banned from using /tiktok

WHITELISTED_BOTS = [1087001524774912050, 823896940847824936] # bots which are allowed to catch cats

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

CAT_TYPES = []
for k, v in type_dict.items():
    CAT_TYPES.extend([k] * v)

# migrate from db.json if found
if os.path.isfile("db.json"):
    print("db.json file found, migrating...")
    
    with open("db.json", "r") as f:
        temp_db = json.load(f)
    
    if not os.path.exists('data'):
        os.mkdir("data")
    
    for k, v in temp_db.items():
        with open(f"data/{k}.json", "w") as f:
            json.dump(v, f)
    
    os.rename("db.json", "old_db.json")
    print(f"migrated {len(temp_db)} files, db.json was renamed to prevent this triggering again.")
    print("it is recommended check if everything is okay.")

class PopulatedDict(UserDict):
    # this will fetch the server info from file if it wasn't fetched yet
    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            try:
                with open(f"data/{key}.json", "r") as f:
                    item = json.load(f)
                super().__setitem__(key, item)
                return item
            except Exception:
                raise KeyError

db = PopulatedDict()

with open("aches.json", "r") as f:
    ach_list = json.load(f)

with open("battlepass.json", "r") as f:
    battle = json.load(f)

ach_names = ach_list.keys()
ach_titles = {value["title"].lower(): key for (key, value) in ach_list.items()}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.AutoShardedBot(command_prefix="https://www.youtube.com/watch?v=dQw4w9WgXcQ", intents=intents, help_command=None)

cattypes = []
for e in CAT_TYPES:
    if e not in cattypes:
        cattypes.append(e)

funny = ["why did you click this this arent yours", "absolutely not", "cat bot not responding, try again later", "you cant", "can you please stop", "try again", "403 not allowed", "stop", "get a life"]

summon_id = db["summon_ids"]

milenakoos = 0
OWNER_ID = 0

fire = {}
for i in summon_id:
    fire[i] = True

def save(id):
    id = str(id)
    with open(f"data/{id}.json", "w") as f:
        json.dump(db[id], f)

try:
    if not db["total_members"]:
        raise KeyError
except KeyError:
    db["total_members"] = 0
    save("total_members")


def add_cat(server_id, person_id, cattype, val=1, overwrite=False):
    register_member(server_id, person_id)
    try:
        if overwrite:
            db[str(server_id)][str(person_id)][cattype] = val
        else:
            db[str(server_id)][str(person_id)][cattype] = db[str(server_id)][str(person_id)][cattype] + val
    except Exception as e:
        db[str(server_id)][str(person_id)][cattype] = val
    save(server_id)
    return db[str(server_id)][str(person_id)][cattype]

def remove_cat(server_id, person_id, cattype, val=1):
    register_member(server_id, person_id)
    try:
        db[str(server_id)][str(person_id)][cattype] = db[str(server_id)][str(person_id)][cattype] - val
        result = db[str(server_id)][str(person_id)][cattype]
    except Exception:
        db[str(server_id)][str(person_id)][cattype] = 0
        result = False
    save(server_id)
    return result

def register_guild(server_id):
    try:
        if db[str(server_id)]:
            pass
    except KeyError:
        db[str(server_id)] = {}

def register_member(server_id, person_id):
    register_guild(server_id)
    search = "Fine"
    try:
        if db[str(server_id)][str(person_id)][search]:
            pass
    except KeyError:
        db[str(server_id)][str(person_id)] = {"Fine": 0}

def get_cat(server_id, person_id, cattype):
    try:
        result = db[str(server_id)][str(person_id)][cattype]
    except Exception:
        register_member(server_id, person_id)
        add_cat(server_id, person_id, cattype, 0)
        result = 0
        save(server_id)
    return result

def get_time(server_id, person_id, type=None):
    if type == None: type = ""
    try:
        result = db[str(server_id)][str(person_id)]["time" + type]
        if isinstance(result, str):
            db[str(server_id)][str(person_id)]["time" + type] = float(result)
    except Exception:
        if type == "":
            result = 99999999999999
        else:
            result = 0
    return result

def set_time(server_id, person_id, time, type=None):
    if type == None: type = ""
    register_member(server_id, person_id)
    db[str(server_id)][str(person_id)]["time" + type] = time
    save(server_id)
    return db[str(server_id)][str(person_id)]["time" + type]

def has_ach(server_id, person_id, ach_id, do_register=True, db_var=None):
    if do_register:
        register_member(server_id, person_id)
    try:
        if db_var == None:
            db_var = db[str(server_id)][str(person_id)]["ach"]
        if ach_id in db_var:
            return db_var[ach_id]
        db_var[ach_id] = False
        return False
    except:
        db[str(server_id)][str(person_id)]["ach"] = {}
        db[str(server_id)][str(person_id)]["ach"][ach_id] = False
        return False

def give_ach(server_id, person_id, ach_id, reverse=False):
    register_member(server_id, person_id)
    if not reverse:
        if not has_ach(server_id, person_id, ach_id):
            db[str(server_id)][str(person_id)]["ach"][ach_id] = True
    else:
        if has_ach(server_id, person_id, ach_id):
            db[str(server_id)][str(person_id)]["ach"][ach_id] = False
    save(server_id)
    return ach_list[ach_id]

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
    if not has_ach(message.guild.id, author, ach_id):
        ach_data = give_ach(message.guild.id, author, ach_id)
        desc = ach_data["description"]
        if ach_id == "dataminer":
            desc = "Your head hurts -- you seem to have forgotten what you just did to get this."
        embed = discord.Embed(title=ach_data["title"], description=desc, color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png").set_footer(text=f"Unlocked by {author_string.name}")
        if send_type == "reply": await message.reply(embed=embed)
        elif send_type == "send": await message.channel.send(embed=embed)
        elif send_type == "followup": await message.followup.send(embed=embed, ephemeral=True)
        elif send_type == "response": await message.response.send_message(embed=embed)

async def myLoop():
    global bot, fire, summon_id
    total_members = db["total_members"]
    await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.competing, name=f"{len(bot.guilds)} servers with {total_members} people")
    )
    summon_id = db["summon_ids"]
    print("Started cat loop (don't shutdown)")
    for i in summon_id:
        try:
            if fire[i]:
                if not db["cat"][str(i)]:
                    file = discord.File("cat.png")
                    localcat = choice(CAT_TYPES)
                    db["cattype"][str(i)] = localcat
                    icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=localcat.lower() + "cat")
                    channeley = await bot.fetch_channel(int(i))
                    message_is_sus = await channeley.send(str(icon) + " " + db["cattype"][str(i)] + " cat has appeared! Type \"cat\" to catch it!", file=file)
                    db["cat"][str(i)] = message_is_sus.id
            if not fire[i]:
                fire[i] = True
        except Exception:
            pass
    db["summon_ids"] = list(dict.fromkeys(summon_id)) # remove all duplicates
    print("Finished cat loop")
    save("cattype")
    save("cat")
    
    with tarfile.open("backup.tar.gz", "w:gz") as tar:
        tar.add("data", arcname=os.path.sep)
    
    backupchannel = await bot.fetch_channel(BACKUP_ID)
    thing = discord.File("backup.tar.gz", filename="backup.tar.gz")
    await backupchannel.send(f"In {len(bot.guilds)} servers.", file=thing)
    if not TOP_GG_TOKEN:
        return
    async with aiohttp.ClientSession() as session:
        await session.post(f'https://top.gg/api/bots/{bot.user.id}/stats',
                                headers={"Authorization": TOP_GG_TOKEN},
                                json={"server_count": len(bot.guilds)})

@tasks.loop(seconds=3600)
async def update_presence():
    # while servers are updated on every loop, members are more resource and api-calls intensive, thus update once a hour
    total = 0
    for i in bot.guilds:
        g = await bot.fetch_guild(i.id)
        total += g.approximate_member_count
    db["total_members"] = total
    save("total_members")
        
@bot.event
async def on_ready():
    global milenakoos, OWNER_ID
    print("cat is now online")
    total_members = db["total_members"]
    await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.competing, name=f"{len(bot.guilds)} servers with {total_members} people")
    )
    appinfo = await bot.application_info()
    milenakoos = appinfo.owner
    OWNER_ID = milenakoos.id
    update_presence.start()
    while True:
        try:
            await asyncio.sleep(randint(120, 1200))
            await myLoop()
        except Exception:
            pass

@bot.event
async def on_message(message):
    global fire, summon_id
    text = message.content
    if message.author.id == bot.user.id:
        return
    
    achs = [["cat?", "startswith", "???"],
        ["catn", "exact", "catn"], 
        ["cat!coupon jr0f-pzka", "exact", "coupon_user"],
        ["pineapple", "exact", "pineapple"],
        ["cat!i_like_cat_website", "exact", "website_user"],
        ["f[0oо]w[0oо]", "re", "fuwu"],
        ["ce[li]{2}ua bad", "re", "cellua"],
        ["new cells cause cancer", "exact", "cancer"],
        [str(bot.user.id), "in", "who_ping"],
        ["lol_i_have_dmed_the_cat_bot_and_got_an_ach", "exact", "dm"],
        ["dog", "exact", "not_quite"],
        ["egril", "exact", "egril"]]

    reactions = [["v1;", "custom", "why_v1"],
        ["proglet", "custom", "professor_cat"],
        ["xnopyt", "custom", "vanish"],
        ["silly", "custom", "sillycat"],
        ["indev", "vanilla", "🐸"]]

    responses = [["testing testing 1 2 3", "exact", "test success"],
        ["cat!sex", "exact", "..."],
        ["cellua good", "in", ".".join([str(randint(2, 254)) for _ in range(4)])]]
    
    if GITHUB_CHANNEL_ID and message.channel.id == GITHUB_CHANNEL_ID:
        os.system("git pull")
        os.execv(sys.executable, ['python'] + sys.argv)
    
    if not (" " in text) and len(text) > 7 and text.isalnum():
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
            await message.add_reaction(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="staring_cat"))
    
    if "robotop" in message.author.name.lower() and "i rate **cat" in message.content.lower():
        icon = str(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="no_cat_throphy")) + " "
        await message.reply("**RoboTop**, I rate **you** 0 cats " + icon * 5)

    if "leafbot" in message.author.name.lower() and "hmm... i would rate cat" in message.content.lower():
        icon = str(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="no_cat_throphy")) + " "
        await message.reply("Hmm... I would rate you **0 cats**! " + icon * 5)
        
    if text == "lol_i_have_dmed_the_cat_bot_and_got_an_ach" and not message.guild:
        await message.channel.send("which part of \"send in server\" was unclear?")
        return
    elif message.guild == None:
        await message.channel.send("good job! please send \"lol_i_have_dmed_the_cat_bot_and_got_an_ach\" in server to get your ach!")
        return
    
    if text == "cat!n4lltvuCOKe2iuDCmc6JsU7Jmg4vmFBj8G8l5xvoDHmCoIJMcxkeXZObR6HbIV6":
        msg = message
        await message.delete()
        await achemb(msg, "dataminer", "send")
    
    for ach in achs:
        if (ach[1] == "startswith" and text.lower().startswith(ach[0])) or \
        (ach[1] == "re" and re.search(ach[0], text.lower())) or \
        (ach[1] == "exact" and ach[0] == text.lower()) or \
        (ach[1] == "in" and ach[0] in text.lower()):
            await achemb(message, ach[2], "reply")
            
    for r in reactions:
        if r[0] in text.lower():
            if r[1] == "custom": await message.add_reaction(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=r[2]))
            elif r[1] == "vanilla": await message.add_reaction(r[2])
            
    for resp in responses:
        if (resp[1] == "startswith" and text.lower().startswith(resp[0])) or \
        (resp[1] == "re" and re.seach(resp[0], text.lower())) or \
        (resp[1] == "exact" and resp[0] == text.lower()) or \
        (resp[1] == "in" and resp[0] in text.lower()):
            await message.reply(resp[2])
        
    if message.author in message.mentions: await message.add_reaction(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="staring_cat"))

    if (":place_of_worship:" in text or "🛐" in text) and (":cat:" in text or ":staring_cat:" in text or "🐱" in text): await achemb(message, "worship", "reply")
    if text.lower() in ["ach", "cat!ach"]: await achemb(message, "test_ach", "reply")
    
    if text.lower() == "please do not the cat":
        await message.reply(f"ok then\n{message.author.name} lost 1 fine cat!!!1!")
        remove_cat(message.guild.id, message.author.id, "Fine")
        await achemb(message, "pleasedonotthecat", "reply")
    
    if text.lower() == "please do the cat":
        thing = discord.File("socialcredit.jpg", filename="socialcredit.jpg")
        await message.reply(file=thing)
        await achemb(message, "pleasedothecat", "reply")
    if text.lower() == "car":
        file = discord.File("car.png", filename="car.png")
        embed = discord.Embed(title="car!", color=0x6E593C).set_image(url="attachment://car.png")
        await message.reply(file=file, embed=embed)
        await achemb(message, "car", "reply")
    if text.lower() == "cart":
        file = discord.File("cart.png", filename="cart.png")
        embed = discord.Embed(title="cart!", color=0x6E593C).set_image(url="attachment://cart.png")
        await message.reply(file=file, embed=embed)
    
    if text.lower() == "cat":
        register_member(message.guild.id, message.author.id)
        try:
            timestamp = db[str(message.guild.id)][str(message.author.id)]["timeout"]
        except Exception:
            db[str(message.guild.id)][str(message.author.id)]["timeout"] = 0
            timestamp = 0
        try:
            is_cat = db["cat"][str(message.channel.id)]
        except Exception:
            is_cat = False
        if not is_cat or timestamp > time.time() or (message.author.bot and message.author.id not in WHITELISTED_BOTS):
            icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="pointlaugh")
            await message.add_reaction(icon)
        elif is_cat:
            current_time = message.created_at
            current_time = time.mktime(current_time.timetuple()) + current_time.microsecond / 1e6
            cat_temp = db["cat"][str(message.channel.id)]
            db["cat"][str(message.channel.id)] = False
            save("cat")
            try:
                await message.delete()
            except discord.errors.Forbidden:
                await message.channel.send("I don't have permission to delete messages. Please re-invite the bot or manually add that permission.")
            try:
                var = await message.channel.fetch_message(cat_temp)
                catchtime = var.created_at
                await var.delete()

                then = time.mktime(catchtime.timetuple()) + catchtime.microsecond / 1e6
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
            except Exception as e:
                print(e)
                do_time = False
                caught_time = "undefined amounts of time "

            le_emoji = db["cattype"][str(message.channel.id)]
            icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=le_emoji.lower() + "cat")
            if le_emoji == "Corrupt":
                coughstring = "{name} coought{cattype} c{icon}at!!!!404!\nYou now BEEP {catcount} cats of dCORRUPTED!!\nthis fella wa- {time}!!!!"
            elif le_emoji == "eGirl":
                coughstring = "{name} cowought {icon} {cattype} cat~~ ^^\nYou-u now *blushes* hawe {catcount} cats of dat tywe~!!!\nthis fella was <3 cought in {time}!!!!"
            elif le_emoji == "Rickroll":
                coughstring = "{name} cought {icon} {cattype} cat!!!!1!\nYou will never give up {catcount} cats of dat type!!!\nYou wouldn't let them down even after {time}!!!!"
            elif le_emoji == "Sus":
                coughstring = "{name} cought {icon} {cattype} cat!!!!1!\nYou have vented infront of {catcount} cats of dat type!!!\nthis sussy baka was cought in {time}!!!!"
            elif le_emoji == "Professor":
                coughstring = "{name} caught {icon} {cattype} cat!\nThou now hast {catcount} cats of that type!\nThis fellow was caught 'i {time}!"
            elif le_emoji == "8bit":
                coughstring = "{name} c0ught {icon} {cattype} cat!!!!1!\nY0u n0w h0ve {catcount} cats 0f dat type!!!\nth1s fe11a was c0ught 1n {time}!!!!"
            elif le_emoji == "Reverse":
                coughstring = "!!!!{time} in cought was fella this\n!!!type dat of cats {catcount} have now You\n!1!!!!cat {cattype} {icon} cought {name}"
            else:
                coughstring = "{name} cought {icon} {cattype} cat!!!!1!\nYou now have {catcount} cats of dat type!!!\nthis fella was cought in {time}!!!!"
            raw_user = await bot.fetch_user(message.author.id)
            await message.channel.send(coughstring.format(name=raw_user.display_name.replace("@", "`@`"),
                                                           icon=icon,
                                                           cattype=le_emoji,
                                                           catcount=add_cat(message.guild.id, message.author.id, le_emoji),
                                                           time=caught_time[:-1]))
            if do_time and time_caught < get_time(message.guild.id, message.author.id):
                set_time(message.guild.id, message.author.id, time_caught)
            if do_time and time_caught > get_time(message.guild.id, message.author.id, "slow"):
                set_time(message.guild.id, message.author.id, time_caught, "slow")

            await achemb(message, "first", "send")
            
            if do_time and get_time(message.guild.id, message.author.id) <= 5: await achemb(message, "fast_catcher", "send")

            if do_time and get_time(message.guild.id, message.author.id, "slow") >= 3600: await achemb(message, "slow_catcher", "send")

            async def do_reward(message, level):
                db[str(message.guild.id)][str(message.author.id)]["progress"] = 0
                reward = level["reward"]
                reward_amount = level["reward_amount"]
                add_cat(message.guild.id, message.author.id, reward, reward_amount)
                icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=reward.lower() + "cat")
                new = add_cat(message.guild.id, message.author.id, "battlepass")
                embed = discord.Embed(title=f"Level {new} complete!", description=f"You have recieved {icon} {reward_amount} {reward} cats!", color=0x007F0E).set_author(name="Cattlepass level!", icon_url="https://pomf2.lain.la/f/zncxu6ej.png")
                await message.channel.send(embed=embed)

            if not get_cat(message.guild.id, message.author.id, "battlepass"):
                db[str(message.guild.id)][str(message.author.id)]["battlepass"] = 0
            if not get_cat(message.guild.id, message.author.id, "progress"):
                db[str(message.guild.id)][str(message.author.id)]["progress"] = 0

            battlelevel = battle["levels"][get_cat(message.guild.id, message.author.id, "battlepass")]
            if battlelevel["req"] == "catch_fast" and do_time and time_caught < battlelevel["req_data"]:
                await do_reward(message, battlelevel)
            if battlelevel["req"] == "catch":
                add_cat(message.guild.id, message.author.id, "progress")
                if get_cat(message.guild.id, message.author.id, "progress") == battlelevel["req_data"]:
                    await do_reward(message, battlelevel)
            if battlelevel["req"] == "catch_type" and le_emoji == battlelevel["req_data"]:
                await do_reward(message, battlelevel)

    if text.lower().startswith("cat!beggar") and message.author.id == OWNER_ID:
        give_ach(message.guild.id, int(text[10:].split(" ")[1]), text[10:].split(" ")[2])
        await message.reply("success")
    if text.lower().startswith("cat!sweep") and message.author.id == OWNER_ID:
        db["cat"][str(message.channel.id)] = False
        save("cat")
        await message.reply("success")
    if text.lower().startswith("cat!setup") and message.author.id == OWNER_ID:
        abc = db["summon_ids"]
        abc.append(int(message.channel.id))
        db["summon_ids"] = abc
        db["cat"][str(message.channel.id)] = False
        db["cattype"][str(message.channel.id)] = ""
        fire[str(message.channel.id)] = True
        save("summon_ids")
        save("cat")
        save("cattype")
        await message.reply(f"ok, now i will also send cats in <#{message.channel.id}>")
    if text.lower().startswith("cat!print") and message.author.id == OWNER_ID:
        await message.reply(eval(text[9:]))
    if text.lower().startswith("cat!news") and message.author.id == OWNER_ID:
        for i in summon_id:
            try:
                channeley = await bot.fetch_channel(int(i))
                await channeley.send(text[8:])
            except Exception:
                pass
    if text.lower().startswith("cat!custom") and message.author.id == OWNER_ID:
        stuff = text.split(" ")
        register_member(str(stuff[1]), str(message.guild.id))
        if stuff[2] == "None":
            del db["0"][str(stuff[1])]["custom"]
        else:
            try:
                db["0"][str(stuff[1])]["custom"] = stuff[2]
            except Exception:
                db["0"][str(stuff[1])] = {}
                db["0"][str(stuff[1])]["custom"] = stuff[2]
        save("0")
        await message.reply("success")
    
    try:
        if db["cattype"][str(message.channel.id)] == "Sus":
            for i in ["sus", "amogus", "among", "vent", "report"]:
                if i in text.lower():
                    await achemb(message, "sussy", "send")
                    break
    except KeyError: pass

@bot.event
async def on_guild_join(guild):
    def verify(ch):
        return ch and ch.permissions_for(guild.me).send_messages

    def find(patt, channels):
        for i in channels:
            if patt in i.name:
                return i
    
    ch = find("cat", guild.text_channels)
    if not verify(ch): ch = find("bots", guild.text_channels)
    if not verify(ch):
        chindex = 1
        ch = guild.text_channels[0]
        while not verify(ch):
            ch = guild.text_channels[chindex]
            chindex += 1
    
    # you are free to change/remove this, its just a note for general user letting them know
    unofficial_note = "**NOTE: This is an unofficial Cat Bot instance.**\n\n"
    if bot.user.id == 966695034340663367: unofficial_note = ""
    await ch.send(unofficial_note + "Thanks for adding me!\nTo setup a channel to summon cats in, use /setup!\nJoin the support server here: https://discord.gg/WCTzD3YQEk\nHave a nice day :)")

@bot.slash_command(description="View information about the bot")
async def info(message: discord.Interaction):
    await message.response.defer()
    credits = {
        "author": [553093932012011520],
        "contrib": [576065759185338371, 819980535639572500, 432966085025857536, 646401965596868628, 696806601771974707],
        "tester": [712639066373619754, 902862104971849769, 709374062237057074, 520293520418930690, 689345298686148732, 717052784163422244, 839458185059500032],
        "emoji": [709374062237057074],
        "trash": [520293520418930690]
    }

    gen_credits = {}

    for key in credits.keys():
        peoples = []
        try:
            for i in credits[key]:
                user = await bot.fetch_user(i)
                peoples.append(user.name.replace("_", r"\_"))
        except Exception:
            pass # death
        gen_credits[key] = ", ".join(peoples)
    
    embedVar = discord.Embed(title="Cat Bot", color=0x6E593C, description="[Join support server](https://discord.gg/WCTzD3YQEk)\n[GitHub Page](https://github.com/milena-kos/cat-bot)\n\n" + \
                             f"Bot made by {gen_credits['author']}\nWith contributions by {gen_credits['contrib']}.\n\nThis bot adds Cat Hunt to your server with many different types of cats for people to discover! People can see leaderboards and give cats to each other.\n\n" + \
                             f"Thanks to:\n**pathologicals** for the cat image\n**{gen_credits['emoji']}** for getting troh to add cat as an emoji\n**thecatapi.com** for random cats API\n**weilbyte** for TikTok TTS API\n**{gen_credits['trash']}** for making cat, suggestions, and a lot more.\n\n**{gen_credits['tester']}** for being test monkeys\n\n**And everyone for the support!**")
    if GITHUB_CHANNEL_ID:
        embedVar.timestamp = datetime.datetime.fromtimestamp(int(subprocess.check_output(["git", "show", "-s", "--format=%ct"]).decode("utf-8")))
        embedVar.set_footer(text="Last updated:")
    await message.followup.send(embed=embedVar)

@bot.slash_command(description="Read text as TikTok's TTS woman")
async def tiktok(message: discord.Interaction, text: str = discord.SlashOption(description="The text to be read!")):
    if message.user.id in BANNED_ID:
        await message.response.send_message("You do not have access to that command.", ephemeral=True)
        return
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
        async with session.post("https://tiktok-tts.weilnet.workers.dev/api/generation",
                                headers={"Content-Type": "application/json"},
                                json={"text": text, "voice": "en_us_002"}) as response:
            try:
                stuff = await response.json()
                data = "" + stuff["data"]
            except:
                await message.followup.send("i dont speak your language (remove non-english characters, or make message shorter)")
                return
            with io.BytesIO() as f:
                ba = "data:audio/mpeg;base64," + data
                f.write(base64.b64decode(ba))
                f.seek(0)
                await message.followup.send(file=discord.File(fp=f, filename='output.mp3'))

@bot.slash_command(description="(ADMIN) Prevent someone from catching cats for a certain time period", default_member_permissions=32)
async def preventcatch(message: discord.Interaction, person: discord.Member = discord.SlashOption(description="A person to timeout!"), timeout: int = discord.SlashOption(description="How many seconds? (0 to reset)")):
    if timeout < 0:
        await message.response.send_message("uhh i think time is supposed to be a number", ephemeral=True)
        return
    register_member(message.guild.id, person.id)
    timestamp = round(time.time()) + timeout
    db[str(message.guild.id)][str(person.id)]["timeout"] = timestamp
    save(message.guild.id)
    if timeout > 0:
        await message.response.send_message(f"{person.name} can't catch cats until <t:{timestamp}:R>")
    else:
        await message.response.send_message(f"{person.name} can now catch cats again.")

@bot.slash_command(description="(ADMIN) Use if cat spawning is broken", default_member_permissions=32)
async def repair(message: discord.Interaction):
    db["cat"][str(message.channel.id)] = False
    save("cat")
    await message.response.send_message("success")

@bot.slash_command(description="Get Daily cats")
async def daily(message: discord.Interaction):
    suffix = ""
    if TOP_GG_TOKEN: suffix = "\nthere ARE cats for voting tho, check out `/vote`"
    await message.response.send_message("there is no daily cats why did you even try this" + suffix)
    await achemb(message, "daily", "send")

@bot.slash_command(description="View your inventory")
async def inventory(message: discord.Interaction, person_id: Optional[discord.Member] = discord.SlashOption(required=False, name="user", description="Person to view the inventory of!")):
    if person_id is None:
        me = True
        person_id = message.user
    else:
        me = False
    await message.response.defer()

    register_member(message.guild.id, person_id.id)
    has_ach(message.guild.id, person_id.id, "test_ach")

    db_var = db[str(message.guild.id)][str(person_id.id)]["ach"]

    unlocked = 0
    minus_achs = 0
    minus_achs_count = 0
    for k in ach_names:
        if ach_list[k]["category"] == "Hidden":
            minus_achs_count += 1
        if has_ach(message.guild.id, person_id.id, k, False, db_var):
            if ach_list[k]["category"] == "Hidden":
                minus_achs += 1
            else:
                unlocked += 1
    total_achs = len(ach_list) - minus_achs_count
    if minus_achs != 0:
        minus_achs = f" + {minus_achs}"
    else:
        minus_achs = ""

    catch_time = str(get_time(message.guild.id, person_id.id))
    is_empty = True
    if catch_time >= "99999999999999":
        catch_time = "never"
    else:
        catch_time = str(round(float(catch_time) * 100) / 100)
    slow_time = get_time(message.guild.id, person_id.id, "slow")
    if str(slow_time) == "0":
        slow_time = "never"
    else:
        slow_time = slow_time / 3600
        slow_time = str(round(slow_time * 100) / 100)
    try:
        if float(slow_time) <= 0:
            set_time(message.guild.id, person_id.id, 0, "slow")
        if float(catch_time) <= 0:
            set_time(message.guild.id, person_id.id, 99999999999999)
    except Exception: pass
   
    if me:
        your = "Your"
    else:
        your = person_id.name + "'s"

    embedVar = discord.Embed(
            title=your + " cats:", description=f"{your} fastest catch is: {catch_time} s\nand {your} slowest catch is: {slow_time} h\nAchievements unlocked: {unlocked}/{total_achs}{minus_achs}", color=0x6E593C
    )
    give_collector = True
    do_save = False
    total = 0
    try:
        custom = db["0"][str(person_id.id)]["custom"]
    except Exception as e:
        try:
            db["0"][str(person_id.id)]["custom"] = False
        except Exception:
            db["0"][str(person_id.id)] = {}
            db["0"][str(person_id.id)]["custom"] = False
        custom = False
        do_save = True
    db_var_two_electric_boogaloo = db[str(message.guild.id)][str(person_id.id)]
    for i in cattypes:
        icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=i.lower() + "cat")
        try:
            cat_num = db_var_two_electric_boogaloo[i]
        except KeyError:
            db[str(message.guild.id)][str(person_id.id)][i] = 0
            cat_num = 0
            do_save = True
        if isinstance(cat_num, float):
            db[str(message.guild.id)][str(person_id.id)][i] = int(cat_num)
            cat_num = int(cat_num)
            do_save = True
        if cat_num != 0:
            total += cat_num
            embedVar.add_field(name=f"{icon} {i}", value=cat_num, inline=True)
            is_empty = False
        if cat_num <= 0:
            give_collector = False
    if custom:
        icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=custom.lower() + "cat")
        embedVar.add_field(name=f"{icon} {custom}", value=1, inline=True)
    if is_empty:
        embedVar.add_field(name="None", value="u hav no cats :cat_sad:", inline=True)
    if do_save:
        save(message.guild.id)
    embedVar.set_footer(text=f"Total cats: {total}")
    await message.followup.send(embed=embedVar)
    if me:
        if give_collector: await achemb(message, "collecter", "send")
        if get_time(message.guild.id, message.user.id) <= 5: await achemb(message, "fast_catcher", "send")
        if get_time(message.guild.id, message.user.id, "slow") >= 3600: await achemb(message, "slow_catcher", "send")

@bot.slash_command(description="I like fortnite")
async def battlepass(message: discord.Interaction):
    await message.response.defer()
    register_member(message.user.id, message.guild.id)
    if not get_cat(message.guild.id, message.user.id, "battlepass"):
        db[str(message.guild.id)][str(message.user.id)]["battlepass"] = 0
    if not get_cat(message.guild.id, message.user.id, "progress"):
        db[str(message.guild.id)][str(message.user.id)]["progress"] = 0

    current_level = get_cat(message.guild.id, message.user.id, "battlepass")
    embedVar = discord.Embed(title="Cattlepass™", description="who thought this was a good idea", color=0x6E593C)

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
                progress = int(get_cat(message.guild.id, message.user.id, "progress"))
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
        current = ":black_large_square:"
    if current_level != 0:
        embedVar.add_field(name=f"✅ Level {current_level} (complete)", value=battlelevel(battle, current_level - 1), inline=False)
    embedVar.add_field(name=f"{current} Level {current_level + 1}", value=battlelevel(battle, current_level, True), inline=False)
    embedVar.add_field(name=f"Level {current_level + 2}", value=battlelevel(battle, current_level + 1), inline=False)

    await message.followup.send(embed=embedVar)

@bot.slash_command(description="Pong")
async def ping(message: discord.Interaction):
    await message.response.defer()
    latency = round(bot.latency * 1000)
    await message.followup.send(f"cat has brain delay of {latency} ms " + str(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="staring_cat")))

@bot.slash_command(description="give cats now")
async def gift(message: discord.Interaction, \
                 person: discord.Member = discord.SlashOption(description="Whom to donate?"), \
                 cat_type: str = discord.SlashOption(choices=cattypes, name="type", description="Select a donate cat type"), \
                 amount: Optional[int] = discord.SlashOption(required=False, description="And how much?")):
    if not amount: amount = 1
    person_id = person.id
    if get_cat(message.guild.id, message.user.id, cat_type) >= amount and amount > 0 and message.user.id != person_id:
        remove_cat(message.guild.id, message.user.id, cat_type, amount)
        add_cat(message.guild.id, person_id, cat_type, amount)
        embed = discord.Embed(title="Success!", description=f"Successfully transfered {amount} {cat_type} cats from <@{message.user.id}> to <@{person_id}>!", color=0x6E593C)
        await message.response.send_message(embed=embed)
        
        await achemb(message, "donator", "send")
        await achemb(message, "anti_donator", "send", person)
        if person_id == bot.user.id and cat_type == "Ultimate" and int(amount) >= 5: await achemb(message, "rich", "send")
        
        if amount >= 5 and person_id != OWNER_ID and cat_type == "Fine":
            tax_amount = round(amount * 0.2)

            async def pay(interaction):
                if interaction.user.id == message.user.id:
                    await interaction.message.edit(view=None)
                    remove_cat(interaction.guild.id, interaction.user.id, "Fine", tax_amount)
                    await interaction.response.send_message(f"Tax of {tax_amount} Fine cats was withdrawn from your account!")
                else:
                    await interaction.response.send_message(choice(funny), ephemeral=True)
            
            async def evade(interaction):
                if interaction.user.id == message.user.id:
                    await interaction.message.edit(view=None)
                    await achemb(message, "secret", "send")
                    await interaction.response.send_message(f"You evaded the tax of {tax_amount} Fine cats.")
                else:
                    await interaction.response.send_message(choice(funny), ephemeral=True)
                
            embed = discord.Embed(title="HOLD UP!", description="Thats rather large amount of fine cats! You will need to pay a cat tax of 20% your transaction, do you agree?", color=0x6E593C)
            
            button = Button(label="Pay!", style=ButtonStyle.green)
            button.callback = pay
            
            button2 = Button(label="Evade the tax", style=ButtonStyle.red)
            button2.callback = evade

            myview = View(timeout=None)

            myview.add_item(button)
            myview.add_item(button2)
            await message.channel.send(embed=embed, view=myview)
    else:
        await message.response.send_message("no", ephemeral=True)

@bot.slash_command(description="Trade cats!")
async def trade(message: discord.Interaction, person_id: discord.Member = discord.SlashOption(name="user", description="why would you need description")):
    person1 = message.user
    person2 = person_id
        
    blackhole = False
        
    if person1 == person2: await achemb(message, "introvert", "send")
        
    person1accept = False
    person2accept = False
    
    person1gives = {}
    person2gives = {}
    
    if person2.id == bot.user.id:
        person2gives = {"eGirl": 9999999}
    
    async def denyb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole
        if interaction.user != person1 and interaction.user != person2:
            await interaction.response.send_message(choice(funny), ephemeral=True)
            return
        
        blackhole = True
        person1gives = {}
        person2gives = {}
        await interaction.message.edit(f"<@{interaction.user.id}> has cancelled the trade.", embed=None, view=None)
            
    async def acceptb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
        if interaction.user != person1 and interaction.user != person2:
            await interaction.response.send_message(choice(funny), ephemeral=True)
            return
        if interaction.user == person1:
            person1accept = not person1accept
        elif interaction.user == person2:
            person2accept = not person2accept
        
        await interaction.response.defer()
        await update_trade_embed(interaction)
            
        if person1accept and person2accept:
            error = False
            for k, v in person1gives.items():
                if get_cat(interaction.guild.id, person1.id, k) < v:
                    error = True
                    break
                
            for k, v in person2gives.items():
                if get_cat(interaction.guild.id, person2.id, k) < v:
                    error = True
                    break
                    
            if error:
                await interaction.message.edit("Not enough cats - some of the cats disappeared while trade was happening", embed=None, view=None)
                return
            
            for k, v in person1gives.items():
                remove_cat(interaction.guild.id, person1.id, k, v)
                add_cat(interaction.guild.id, person2.id, k, v)
                
            for k, v in person2gives.items():
                remove_cat(interaction.guild.id, person2.id, k, v)
                add_cat(interaction.guild.id, person1.id, k, v)

            await interaction.message.edit(f"Trade finished!", view=None)
            await achemb(message, "extrovert", "send")
            await achemb(message, "extrovert", "send", person2)
        
    async def addb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
        if interaction.user != person1 and interaction.user != person2:
            await interaction.response.send_message(choice(funny), ephemeral=True)
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
        await handle_modal(currentuser, interaction)
                
    async def handle_modal(currentuser, interaction):
        modal = TradeModal(currentuser)
        await interaction.response.send_modal(modal)
    
    async def gen_embed():
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole
        if blackhole:
            await achemb(message, "blackhole", "send")
            await achemb(message, "blackhole", "send", person2)
            return discord.Embed(color=0x6E593C, title=f"Blackhole", description="How Did We Get Here?"), None
        view = View(timeout=None)
    
        accept = Button(label="Accept", style=ButtonStyle.green)
        accept.callback = acceptb
        
        deny = Button(label="Deny", style=ButtonStyle.red)
        deny.callback = denyb
        
        add = Button(label="Offer cats", style=ButtonStyle.blurple)
        add.callback = addb
        
        view.add_item(accept)
        view.add_item(deny)
        view.add_item(add)

        coolembed = discord.Embed(color=0x6E593C, title=f"{person1.name} and {person2.name} trade", description="no way")

        def field(personaccept, persongives, person):
            nonlocal coolembed
            icon = "⬜"
            if personaccept:
                icon = "✅"
            valuestr = ""
            valuenum = 0
            for k, v in persongives.items():
                valuenum += (len(CAT_TYPES) / type_dict[k]) * v
                aicon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=k.lower() + "cat")
                valuestr += str(aicon) + " " + k + " " + str(v) + "\n"
            if not valuestr:
                valuestr = "No cats offered!"
            else:
                valuestr += f"*Total value: {round(valuenum)}*"
            coolembed.add_field(name=f"{icon} {person.name}", inline=True, value=valuestr)
        
        field(person1accept, person1gives, person1)
        field(person2accept, person2gives, person2)
        
        return coolembed, view
    
    embed, view = await gen_embed()
    await message.response.send_message(embed=embed, view=view)
        
    async def update_trade_embed(interaction):
        embed, view = await gen_embed()
        await interaction.message.edit(embed=embed, view=view)
        
    class TradeModal(discord.ui.Modal):
        def __init__(self, currentuser):
            super().__init__(
                "Add cats to the trade",
                timeout=5 * 60,  # 5 minutes
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

        async def callback(self, interaction: discord.Interaction):
            nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
            try:
                if int(self.amount.value) <= 0:
                    raise Exception
            except Exception:
                await interaction.send("plz number?", ephemeral=True)
                return
            if self.cattype.value not in cattypes:
                await interaction.send("add a valid cat type 💀💀💀", ephemeral=True)
                return
            try:
                if self.currentuser == 1:
                    currset = person1gives[self.cattype.value]
                else:
                    currset = person2gives[self.cattype.value]
            except KeyError:
                currset = 0
            if get_cat(interaction.guild.id, interaction.user.id, self.cattype.value) < int(self.amount.value) + currset:
                await interaction.send("hell naww dude you dont even have that many cats 💀💀💀", ephemeral=True)
                return
            if self.currentuser == 1:
                try:
                    person1gives[self.cattype.value] += int(self.amount.value)
                except KeyError:
                    person1gives[self.cattype.value] = int(self.amount.value)
            else:
                try:
                    person2gives[self.cattype.value] += int(self.amount.value)
                except KeyError:
                    person2gives[self.cattype.value] = int(self.amount.value)
            await interaction.response.defer()
            await update_trade_embed(interaction)

@bot.slash_command(description="Get Cat Image, does not add a cat to your inventory")
async def cat(message: discord.Interaction):
    file = discord.File("cat.png", filename="cat.png")
    await message.response.send_message(file=file)

@bot.slash_command(description="Get Cursed Cat")
async def cursed(message: discord.Interaction):
    file = discord.File("cursed.jpg", filename="cursed.jpg")
    await message.response.send_message(file=file)

@bot.slash_command(description="Get a warning")
async def warning(message: discord.Interaction):
    file = discord.File("warning.png", filename="warning.png")
    await message.response.send_message(file=file)

@bot.slash_command(description="Get Your balance")
async def bal(message: discord.Interaction):
    file = discord.File("money.png", filename="money.png")
    embed = discord.Embed(title="cat coins", color=0x6E593C).set_image(url="attachment://money.png")
    await message.response.send_message(file=file, embed=embed)

@bot.slash_command(description="Brew some coffee to catch cats more efficiently")
async def brew(message: discord.Interaction):
   await message.response.send_message("HTTP 418: I'm a teapot. <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/418>")
   await achemb(message, "coffee", "send")

if TOP_GG_TOKEN:
    @bot.slash_command(description="Vote on topgg for free cats")
    async def vote(message: discord.Interaction):
        icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="goodcat")
        if get_cat(0, message.user.id, "vote_time") + 43200 > time.time():
            countdown = round(get_cat(0, message.user.id, "vote_time") + 43200)
            embedVar = discord.Embed(title="Already voted!", description=f"You have already [voted for Cat Bot on top.gg](https://top.gg/bot/966695034340663367)!\nVote again <t:{countdown}:R> to recieve {icon} 5 more Good cats.", color=0x6E593C)
            await message.response.send_message(embed=embedVar)
            return
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://top.gg/api/bots/{bot.user.id}/check",
                                   params={"userId": message.user.id},
                                   headers={"Authorization": TOP_GG_TOKEN}) as response:
                resp = await response.json()
        if resp["voted"] == 1:
            # valid vote
            add_cat(message.guild.id, message.user.id, "Good", 5)
            add_cat(0, message.user.id, "vote_time", time.time(), True)
            embedVar = discord.Embed(title="Vote redeemed!", description=f"You have recieved {icon} 5 Good cats.\nVote again in 12 hours.", color=0x007F0E)
            await message.response.send_message(embed=embedVar)
        else:
            embedVar = discord.Embed(title="Vote for Cat Bot", description=f"[Vote for Cat Bot on top.gg](https://top.gg/bot/966695034340663367) every 12 hours to recieve {icon} 5 Good cats.\n\nRun this command again after you voted to recieve your cats.", color=0x6E593C)
            await message.response.send_message(embed=embedVar)

@bot.slash_command(description="Get a random cat")
async def random(message: discord.Interaction):
    counter = 0
    async with aiohttp.ClientSession() as session:
        while True:
            if counter == 11:
                return
            try:
                async with session.get('https://api.thecatapi.com/v1/images/search') as response:
                    data = await response.json()
                    await message.response.send_message(data[0]['url'])
                    counter += 1
                    await achemb(message, "randomizer", "send")
                    return
            except Exception:
                pass
            counter += 1

@bot.slash_command(description="View your achievements")
async def achievements(message: discord.Interaction):
    register_member(message.guild.id, message.user.id)
    has_ach(message.guild.id, message.user.id, "test_ach")
    db_var = db[str(message.guild.id)][str(message.user.id)]["ach"]

    unlocked = 0
    minus_achs = 0
    minus_achs_count = 0
    for k in ach_names:
        if ach_list[k]["category"] == "Hidden":
            minus_achs_count += 1
        if has_ach(message.guild.id, message.user.id, k, False, db_var):
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

    def gen_new(category):
        nonlocal db_var, message, unlocked, total_achs
        hidden_suffix = ""
        if category == "Hidden":
            hidden_suffix = "\n\nThis is a \"Hidden\" category. Achievements here only show up after you complete them."
        newembed = discord.Embed(
                title=category, description=f"Achievements unlocked (total): {unlocked}/{total_achs}{minus_achs}{hidden_suffix}", color=0x6E593C
        )
        for k, v in ach_list.items():
            if v["category"] == category:
                icon = str(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="no_cat_throphy")) + " "
                if has_ach(message.guild.id, message.user.id, k, False, db_var):
                    newembed.add_field(name=str(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="cat_throphy")) + " " + v["title"], value=v["description"], inline=True)
                elif category != "Hidden":
                    if v["is_hidden"]:
                        newembed.add_field(name=icon + v["title"], value="???", inline=True)
                    else:
                        newembed.add_field(name=icon + v["title"], value=v["description"], inline=True)

        return newembed

    async def send_full(interaction):
        nonlocal message
        if interaction.user.id == message.user.id:
            await interaction.response.send_message(embed=gen_new("Cat Hunt"), ephemeral=True, view=insane_view_generator("Cat Hunt"))
        else:
            await interaction.response.send_message(choice(funny), ephemeral=True)
            await achemb(interaction, "curious", "send")

    def insane_view_generator(category):
        myview = View(timeout=None)
        buttons_list = []
        lambdas_list = []

        # would be much more optimized but i cant get this to work
        # for i in ["Cat Hunt", "Random", "Unfair"]:
        #   if category == i:
        #        buttons_list.append(Button(label=i, style=ButtonStyle.green))
        #   else:
        #        buttons_list.append(Button(label=i, style=ButtonStyle.blurple))
        #   lambdas_list.append(lambda interaction : (await interaction.edit(embed=gen_new(i), view=insane_view_generator(i)) for _ in '_').__anext__())
        #   buttons_list[-1].callback = lambdas_list[-1]

        if category == "Cat Hunt":
            buttons_list.append(Button(label="Cat Hunt", style=ButtonStyle.green))
        else:
            buttons_list.append(Button(label="Cat Hunt", style=ButtonStyle.blurple))
        lambdas_list.append(lambda interaction : (await interaction.edit(embed=gen_new("Cat Hunt"), view=insane_view_generator("Cat Hunt")) for _ in '_').__anext__())
        buttons_list[-1].callback = lambdas_list[-1]

        if category == "Random":
            buttons_list.append(Button(label="Random", style=ButtonStyle.green))
        else:
            buttons_list.append(Button(label="Random", style=ButtonStyle.blurple))
        lambdas_list.append(lambda interaction : (await interaction.edit(embed=gen_new("Random"), view=insane_view_generator("Random")) for _ in '_').__anext__())
        buttons_list[-1].callback = lambdas_list[-1]

        if category == "Unfair":
            buttons_list.append(Button(label="Unfair", style=ButtonStyle.green))
        else:
            buttons_list.append(Button(label="Unfair", style=ButtonStyle.blurple))
        lambdas_list.append(lambda interaction : (await interaction.edit(embed=gen_new("Unfair"), view=insane_view_generator("Unfair")) for _ in '_').__anext__())
        buttons_list[-1].callback = lambdas_list[-1]

        if category == "Hidden":
            buttons_list.append(Button(label="Hidden", style=ButtonStyle.green))
        else:
            buttons_list.append(Button(label="Hidden", style=ButtonStyle.blurple))
        lambdas_list.append(lambda interaction : (await interaction.edit(embed=gen_new("Hidden"), view=insane_view_generator("Hidden")) for _ in '_').__anext__())
        buttons_list[-1].callback = lambdas_list[-1]

        for j in buttons_list:
            myview.add_item(j)
        return myview

    button = Button(label="View all achievements", style=ButtonStyle.blurple)
    button.callback = send_full

    myview = View(timeout=None)
    myview.add_item(button)

    await message.response.send_message(embed=embedVar, view=myview)
            
@bot.message_command(name="catch")
async def catch(message: discord.Interaction, msg):
    msg2img.msg2img(msg, bot, True)
    file = discord.File("generated.png", filename="generated.png")
    await message.response.send_message("cought in 4k", file=file)
    register_member(message.guild.id, msg.author.id)
    if msg.author.id != bot.user.id: await achemb(message, "4k", "send")

@bot.message_command()
async def pointLaugh(message: discord.Interaction, msg):
    icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="pointlaugh")
    await msg.add_reaction(icon)
    await message.response.send_message(icon, ephemeral=True)

@bot.slash_command(description="View the leaderboards")
async def leaderboards(message: discord.Interaction, leaderboard_type: Optional[str] = discord.SlashOption(name="type", description="The leaderboard type to view!", choices=["Cats", "Fastest", "Slowest"], required=False)):
    if not leaderboard_type: leaderboard_type = "Cats"
    async def lb_handler(interaction, type, do_edit=None):
        nonlocal message
        if do_edit == None: do_edit = True
        await interaction.response.defer()
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
        register_guild(message.guild.id)
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
        for i in db[str(message.guild.id)].keys():
            if not main:
                value = get_time(message.guild.id, i, time_type)
                if int(value) < 0:
                    set_time(message.guild.id, i, int(default_value), time_type)
                    continue
            else:
                value = 0
                for a, b in db[str(message.guild.id)][i].items():
                    if a in cattypes:
                        try:
                            value += b
                            if b > 0 and rarities.index(a) > rarest:
                                rarest = rarities.index(a)
                                rarest_holder = {"<@" + i + ">": b}
                            elif b > 0 and rarities.index(a) == rarest:
                                rarest_holder["<@" + i + ">"] = b
                        except Exception:
                            pass
            if str(value) != default_value:
                thingy = round((value / devider) * 100) / 100
                if thingy == int(thingy):
                    thingy = int(thingy) # trim .0
                the_dict[f" {unit}: <@" + i + ">"] = thingy

        heap = [(-value, key) for key, value in the_dict.items()]
        if fast:
            largest = heapq.nlargest(15, heap)
        else:
            largest = heapq.nsmallest(15, heap)
        largest = [(key, -value) for value, key in largest]
        string = ""

        if main:
            catmoji = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=rarities[rarest].lower() + "cat")
            if rarest != -1:
                rarest_holder = list(dict(sorted(rarest_holder.items(), key=lambda item: item[1], reverse=True)).keys())
                joined = ", ".join(rarest_holder)
                string = f"Rarest cat: {catmoji} ({joined}'s)\n"

        current = 1
        for i, num in largest:
            string = string + str(current) + ". " + str(num) + i + "\n"
            current += 1
        embedVar = discord.Embed(
                title=f"{title} Leaderboards:", description=string, color=0x6E593C
        )

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

        myview = View(timeout=None)
        myview.add_item(button1)
        myview.add_item(button2)
        myview.add_item(button3)

        if do_edit:
            await interaction.edit(embed=embedVar, view=myview)
        else:
            await interaction.followup.send(embed=embedVar, view=myview)

    async def slowlb(interaction):
        await lb_handler(interaction, "slow")

    async def fastlb(interaction):
        await lb_handler(interaction, "fast")

    async def catlb(interaction):
        await lb_handler(interaction, "main")
        
    await lb_handler(message, {"Fastest": "fast", "Slowest": "slow", "Cats": "main"}[leaderboard_type], False)

@bot.slash_command(description="(ADMIN) Give cats to people", default_member_permissions=32)
async def givecat(message: discord.Interaction, person_id: discord.Member = discord.SlashOption(name="user", description="who"), \
                 amount: int = discord.SlashOption(description="how many"), \
                 cat_type: str = discord.SlashOption(choices=cattypes, description="what")):
    add_cat(message.guild.id, person_id.id, cat_type, amount)
    embed = discord.Embed(title="Success!", description=f"gave <@{person_id.id}> {amount} {cat_type} cats", color=0x6E593C)
    await message.response.send_message(embed=embed)

@bot.slash_command(description="(ADMIN) Say stuff as cat", default_member_permissions=32)
async def say(message: discord.Interaction, text: str = discord.SlashOption(description="you will figure")):
    await message.response.send_message("success", ephemeral=True)
    await message.channel.send(text[:2000])

@bot.slash_command(description="(ADMIN) Setup cat in current channel", default_member_permissions=32)
async def setup(message: discord.Interaction):
    if int(message.channel.id) in db["summon_ids"]:
        await message.response.send_message("bruh you already setup cat here are you dumb\n\nthere might already be a cat sitting in chat. type `cat` to catch it.\nalternatively, you can try `/repair` if it still doesnt work")
        return
    abc = db["summon_ids"]
    abc.append(int(message.channel.id))
    db["summon_ids"] = abc
    db["cat"][str(message.channel.id)] = False
    db["cattype"][str(message.channel.id)] = ""
    fire[str(message.channel.id)] = True
    await soft_force(message.channel)
    await message.response.send_message(f"ok, now i will also send cats in <#{message.channel.id}>")

@bot.slash_command(description="(ADMIN) Undo the setup", default_member_permissions=32)
async def forget(message: discord.Interaction):
    if int(message.channel.id) in db["summon_ids"]:
        abc = db["summon_ids"]
        abc.remove(int(message.channel.id))
        db["summon_ids"] = abc
        save("summon_ids")
        await message.response.send_message(f"ok, now i wont send cats in <#{message.channel.id}>")
    else:
        await message.response.send_message("your an idiot there is literally no cat setupped in this channel you stupid")

@bot.slash_command(description="LMAO TROLLED SO HARD :JOY:")
async def fake(message: discord.Interaction):
    file = discord.File("australian cat.png", filename="australian cat.png")
    icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="egirlcat")
    await message.channel.send(str(icon) + " eGirl cat hasn't appeared! Type \"cat\" to catch ratio!", file=file)
    await message.response.send_message("OMG TROLLED SO HARD LMAOOOO :joy:", ephemeral=True)
    await achemb(message, "trolled", "followup")

async def soft_force(channeley, cat_type=None):
    fire[channeley.id] = False
    file = discord.File("cat.png", filename="cat.png")
    if not cat_type:
        localcat = choice(CAT_TYPES)
    else:
        localcat = cat_type
    db["cattype"][str(channeley.id)] = localcat
    icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=localcat.lower() + "cat")
    message_lmao = await channeley.send(str(icon) + " " + db["cattype"][str(channeley.id)] + " cat has appeared! Type \"cat\" to catch it!", file=file)
    db["cat"][str(channeley.id)] = message_lmao.id
    save("cattype")
    save("cat")

@bot.slash_command(description="(ADMIN) Force cats to appear", default_member_permissions=32)
async def forcespawn(message: discord.Interaction, cat_type: Optional[str] = discord.SlashOption(required=False, choices=cattypes, name="type", description="select a cat type ok")):
    try:
        if db["cat"][str(message.channel.id)]:
            await message.response.send_message("there is already a cat", ephemeral=True)
            return
    except Exception:
        await message.response.send_message("this channel is not /setup-ed", ephemeral=True)
        return
    await soft_force(message.channel, cat_type)
    await message.response.send_message("done!\n**Note:** you can use `/givecat` to give yourself cats, there is no need to spam this", ephemeral=True)

@bot.slash_command(description="(ADMIN) Give achievements to people", default_member_permissions=32)
async def giveachievement(message: discord.Interaction, person_id: discord.Member = discord.SlashOption(name="user", description="who"), \
                  ach_id: str = discord.SlashOption(name="name", description="name or id of the achievement")):
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
    if valid:
        reverse = has_ach(message.guild.id, person_id.id, ach_id)
        ach_data = give_ach(message.guild.id, person_id.id, ach_id, reverse)
        color, title, icon = 0x007F0E, "Achievement forced!", "https://pomf2.lain.la/f/hbxyiv9l.png"
        if reverse:
            color, title, icon = 0xff0000, "Achievement removed!", "https://pomf2.lain.la/f/b8jxc27g.png"
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=color).set_author(name=title, icon_url=icon).set_footer(text=f"for {person_id.name}")
        await message.response.send_message(embed=embed)
    else:
        await message.response.send_message("i cant find that achievement! try harder next time.", ephemeral=True)

@bot.slash_command(description="(ADMIN) Reset people", default_member_permissions=32)
async def reset(message: discord.Interaction, person_id: discord.Member = discord.SlashOption(name="user", description="who")):
    try:
        del db[str(message.guild.id)][str(person_id.id)]
        save(message.guild.id)
        await message.response.send_message(embed=discord.Embed(color=0x6E593C, description=f'Done! rip <@{person_id.id}>. f\'s in chat.'))
    except KeyError:
        await message.response.send_message("ummm? this person isnt even registered in cat bot wtf are you wiping?????", ephemeral=True)

async def on_command_error(ctx, error):
    # ctx here is interaction
    if "KeyboardInterrupt" in str(type(error)):
        return
    elif "errors.Forbidden" in str(type(error)):
        await ctx.channel.send("i don't have permissions to do that. (try reinviting the bot)")
    elif "errors.NotFound" in str(type(error)):
        await ctx.channel.send("took too long, try running the command again")
    else:
        await ctx.channel.send("cat crashed lmao\ni automatically sent crash reports so yes")
        try:
            await achemb(ctx, "crasher", "send")
        except Exception:
            pass

        try:
            cont = ctx.content
            print("debug", cont)
        except Exception as e:
            cont = "Error getting"

        try:
            serv = ctx.guild.name
            print("debug", cont)
        except Exception as e:
            cont = "Error getting"

        _, _, error2 = sys.exc_info()

        await milenakoos.send(
                "There is an error happend:\n"
                + str("".join(traceback.format_tb(error2))) + str(type(error)) + str(error)
                + "\n\nMore info on error:\n\nMessage link: "
                + link
                + "\nMessage text: "
                + cont
                + "\n\nServer name: "
                + serv
        )

bot.on_application_command_error = on_command_error
bot.run(TOKEN)
