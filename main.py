import nextcord as discord
import msg2img, base64, sys, re, time, json, requests, traceback, os, io, aiohttp, heapq, datetime
from nextcord.ext import tasks, commands
from nextcord import ButtonStyle
from nextcord.ui import Button, View
from typing import Optional
from random import randint, choice

### Setup values start

GUILD_ID = 966586000417619998 # for emojis
BACKUP_ID = 1060545763194707998 # channel id for db backups, private extremely recommended

# discord bot token, use os.environ for more security
TOKEN = os.environ['token']
# TOKEN = "token goes here"

# set to False to disable /vote
TOP_GG_TOKEN = os.environ['topggtoken']

# set to False to disable /dream
# token for stability ai, at https://beta.dreamstudio.ai/
STABILITY_KEY = os.environ['STABILITY_KEY']

# this will automatically restart the bot if message in GITHUB_CHANNEL_ID is sent, you can use a github webhook for that
# set to False to disable
GITHUB_CHANNEL_ID = 1060965767044149249

BANNED_ID = [1029044762340241509] # banned from using /dream and /tiktok

STATUS_PAGE_URL = "https://status.milenakos.tk/" # leave empty to disable

### Setup values end

# trigger warning, base64 encoded for your convinience
NONOWORDS = [base64.b64decode(i).decode('utf-8') for i in ["bmlja2E=", "bmlja2Vy", "bmlnYQ==", "bmlnZ2E=", "bmlnZ2Vy"]]

CAT_TYPES = (
        ["Fine"] * 1000
        + ["Nice"] * 750
        + ["Good"] * 500
        + ["Rare"] * 350
        + ["Wild"] * 275
        + ["Baby"] * 230
        + ["Epic"] * 200
        + ["Sus"] * 175
        + ["Brave"] * 150
        + ["Rickroll"] * 125
        + ["Reverse"] * 100
        + ["Superior"] * 80
        + ["TheTrashCell"] * 50
        + ["Legendary"] * 35
        + ["Mythic"] * 25
        + ["8bit"] * 20
        + ["Corrupt"] * 15
        + ["Professor"] * 10
        + ["Divine"] * 8
        + ["Real"] * 5
        + ["Ultimate"] * 3
        + ["eGirl"] * 2
)

with open("db.json", "r") as f:
    try:
        db = json.load(f)
    except Exception:
        f.close()
        import reverse
        reverse.reverse()
        with open("db.json", "r") as f:
            db = json.load(f)

with open("aches.json", "r") as f:
    ach_list = json.load(f)

with open("battlepass.json", "r") as f:
    battle = json.load(f)

ach_names = ach_list.keys()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="Cat Bot by Milenakos#3310", intents=intents, help_command=None)

cattypes = ["Fine", "Nice", "Good", "Rare", "Wild", "Baby", "Epic", "Sus", "Brave", "Rickroll", "Reverse", "Superior", "TheTrashCell", "Legendary", "Mythic", "8bit", "Corrupt", "Professor", "Divine", "Real", "Ultimate", "eGirl"]

funny = ["why did you click this this arent yours", "absolutely not", "cat bot not responding, try again later", "you cant", "can you please stop", "try again", "403 not allowed", "stop", "get a life"]

summon_id = db["summon_ids"]

delays = [120, 1200]

timeout = 0
starting_time = 0
message_thing = 0
milenakoos = 0

super_prefix = ""

fire = {}
for i in summon_id:
    fire[i] = False

def save():
    with open("db.json", "w") as f:
        json.dump(db, f)
    with open("backup.txt", "w") as f:
        f.write(str(db))

def add_cat(server_id, person_id, cattype, val=1, overwrite=False):
    register_member(server_id, person_id)
    try:
        if overwrite:
            db[str(server_id)][str(person_id)][cattype] = val
        else:
            db[str(server_id)][str(person_id)][cattype] = db[str(server_id)][str(person_id)][cattype] + val
    except Exception as e:
        print("add_cat", e)
        db[str(server_id)][str(person_id)][cattype] = val
    save()
    return db[str(server_id)][str(person_id)][cattype]

def remove_cat(server_id, person_id, cattype, val=1):
    register_member(server_id, person_id)
    try:
        db[str(server_id)][str(person_id)][cattype] = db[str(server_id)][str(person_id)][cattype] - val
        result = db[str(server_id)][str(person_id)][cattype]
    except Exception:
        db[str(server_id)][str(person_id)][cattype] = 0
        result = False
    save()
    return result

def register_guild(server_id):
    try:
        if db[str(server_id)]:
            pass
    except KeyError:
        db[str(server_id)] = {}
        save()

def register_member(server_id, person_id):
    register_guild(server_id)
    search = "Fine"
    try:
        if db[str(server_id)][str(person_id)][search]:
            pass
    except KeyError:
        db[str(server_id)][str(person_id)] = {}
        save()

def get_cat(server_id, person_id, cattype):
    try:
        result = db[str(server_id)][str(person_id)][cattype]
    except Exception:
        register_member(server_id, person_id)
        add_cat(server_id, person_id, cattype, 0)
        result = 0
        save()
    return result

def get_time(server_id, person_id, type=None):
    if type == None: type = ""
    try:
        result = db[str(server_id)][str(person_id)]["time" + type]
        if isinstance(result, str):
            db[str(server_id)][str(person_id)]["time" + type] = float(result)
            save()
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
    save()
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
        save()
        return False

def give_ach(server_id, person_id, ach_id, reverse=False):
    register_member(server_id, person_id)
    if not reverse:
        if not has_ach(server_id, person_id, ach_id):
            db[str(server_id)][str(person_id)]["ach"][ach_id] = True
    else:
        if has_ach(server_id, person_id, ach_id):
            db[str(server_id)][str(person_id)]["ach"][ach_id] = False
    save()
    return ach_list[ach_id]

@tasks.loop(seconds = randint(delays[0], delays[1]))
async def myLoop():
    global bot, fire, summon_id, delays
    await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name=f"/help | Providing life support for {len(bot.guilds)} servers")
    )
    summon_id = db["summon_ids"]
    myLoop.change_interval(seconds = randint(delays[0], delays[1]))
    file = discord.File("cat.png", filename="cat.png")
    for i in summon_id:
        try:
            if fire[i]:
                if not db["cat"][str(i)]:
                    file = discord.File("cat.png", filename="cat.png")
                    localcat = choice(CAT_TYPES)
                    db["cattype"][str(i)] = localcat
                    icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=localcat.lower() + "cat")
                    channeley = await bot.fetch_channel(int(i))
                    message_is_sus = await channeley.send(str(icon) + " " + db["cattype"][str(i)] + " cat has appeared! Type \"cat\" to catch it!", file=file)
                    db["cat"][str(i)] = message_is_sus.id
                    save()
            if not fire[i]:
                fire[i] = True
        except Exception as e:
            print("error", i, e)
    backupchannel = await bot.fetch_channel(BACKUP_ID)
    thing = discord.File("db.json", filename="db.json")
    await backupchannel.send(f"In {len(bot.guilds)} servers.", file=thing)

@bot.event
async def on_ready():
    global milenakoos
    print("cat is now online")
    await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name=f"/help | Providing life support for {len(bot.guilds)} servers")
    )
    appinfo = await bot.application_info()
    milenakoos = appinfo.owner
    OWNER_ID = milenakoos.id
    if TOP_GG_TOKEN:
        import topgg
        bot.topggpy = topgg.DBLClient(TOP_GG_TOKEN, default_bot_id=bot.user.id)
    myLoop.cancel()
    myLoop.start()

@bot.event
async def on_message(message):
    global fire, summon_id, delays
    text = message.content
    if message.author.id == bot.user.id:
        return
    if GITHUB_CHANNEL_ID and message.channel.id == GITHUB_CHANNEL_ID:
        os.system("git pull")
        myLoop.cancel()
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
    if text.lower().startswith("cat?") and not has_ach(message.guild.id, message.author.id, "???"):
        ach_data = give_ach(message.guild.id, message.author.id, "???")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text == "lol_i_have_dmed_the_cat_bot_and_got_an_ach" and not message.guild:
        await message.channel.send("which part of \"send in server\" was unclear?")
        return
    elif message.guild == None and message.author.id != bot.user.id:
        await message.channel.send("good job! please send \"lol_i_have_dmed_the_cat_bot_and_got_an_ach\" in server to get your ach!")
        return
    if "V1;" in text:
        icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="why_v1")
        await message.add_reaction(icon)
    if text == "catn" and not has_ach(message.guild.id, message.author.id, "catn"):
        ach_data = give_ach(message.guild.id, message.author.id, "catn")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text == "cat!coupon JR0F-PZKA" and not has_ach(message.guild.id, message.author.id, "coupon_user"):
        ach_data = give_ach(message.guild.id, message.author.id, "coupon_user")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text == "pineapple" and not has_ach(message.guild.id, message.author.id, "pineapple"):
        ach_data = give_ach(message.guild.id, message.author.id, "pineapple")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text == "cat!i_like_cat_website" and not has_ach(message.guild.id, message.author.id, "website_user"):
        ach_data = give_ach(message.guild.id, message.author.id, "website_user")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text == "cat!n4lltvuCOKe2iuDCmc6JsU7Jmg4vmFBj8G8l5xvoDHmCoIJMcxkeXZObR6HbIV6" and not has_ach(message.guild.id, message.author.id, "dataminer"):
        msg = message
        await message.delete()
        ach_data = give_ach(msg.guild.id, msg.author.id, "dataminer")
        embed = discord.Embed(title=ach_data["title"], description="Description is redacted to keep this ach a secret.", color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await msg.channel.send(embed=embed)
    if re.search("f[0oо]w[0oо]", text.lower()) and not has_ach(message.guild.id, message.author.id, "fuwu"):
        ach_data = give_ach(message.guild.id, message.author.id, "fuwu")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if re.search("ce[li]{2}ua bad", text.lower()) and not has_ach(message.guild.id, message.author.id, "cellua"):
        ach_data = give_ach(message.guild.id, message.author.id, "cellua")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text == "new cells cause cancer" and not has_ach(message.guild.id, message.author.id, "cancer"):
        ach_data = give_ach(message.guild.id, message.author.id, "cancer")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text.lower() == "testing testing 1 2 3":
        await message.reply("test success")
    if text.lower() == "cat!sex":
        await message.reply("...")
    if "proglet" in text.lower():
        await message.add_reaction(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="professor_cat"))
    if ("@" + str(bot.user) in text or f"<@{bot.user.id}>" in text or f"<@!{bot.user.id}>" in text) and not has_ach(message.guild.id, message.author.id, "who_ping"):
        ach_data = give_ach(message.guild.id, message.author.id, "who_ping")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text == "lol_i_have_dmed_the_cat_bot_and_got_an_ach" and message.guild and not has_ach(message.guild.id, message.author.id, "dm"):
        ach_data = give_ach(message.guild.id, message.author.id, "dm")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if (":place_of_worship:" in text or "🛐" in text) and (":cat:" in text or ":staring_cat:" in text or "🐱" in text) and not has_ach(message.guild.id, message.author.id, "worship"):
        ach_data = give_ach(message.guild.id, message.author.id, "worship")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text.lower() == "please do not the cat":
        safe = str(message.author).replace("@", "`@`")
        await message.reply(f"ok then\n{safe} lost 1 fine cat!!!1!")
        remove_cat(message.guild.id, message.author.id, "Fine")
        if not has_ach(message.guild.id, message.author.id, "pleasedonotthecat"):
            ach_data = give_ach(message.guild.id, message.author.id, "pleasedonotthecat")
            embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
            await message.reply(embed=embed)
    if text.lower() == "please do the cat":
        thing = discord.File("socialcredit.jpg", filename="socialcredit.jpg")
        await message.reply(file=thing)
        if not has_ach(message.guild.id, message.author.id, "pleasedothecat"):
            ach_data = give_ach(message.guild.id, message.author.id, "pleasedothecat")
            embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
            await message.reply(embed=embed)
    if text.lower() == "dog" and not has_ach(message.guild.id, message.author.id, "not_quite"):
        ach_data = give_ach(message.guild.id, message.author.id, "not_quite")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text.lower() == "ach" and not has_ach(message.guild.id, message.author.id, "test_ach"):
        ach_data = give_ach(message.guild.id, message.author.id, "test_ach")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text.lower() == "egril" and not has_ach(message.guild.id, message.author.id, "egril"):
        ach_data = give_ach(message.guild.id, message.author.id, "egril")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.reply(embed=embed)
    if text.lower() == "cat":
        register_member(message.guild.id, message.author.id)
        try:
            timestamp = db[str(message.guild.id)][str(message.author.id)]["timeout"]
        except Exception:
            db[str(message.guild.id)][str(message.author.id)]["timeout"] = 0
            timestamp = 0
            save()
        try:
            is_cat = db["cat"][str(message.channel.id)]
        except Exception:
            is_cat = False
        if not is_cat or timestamp > time.time():
            icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="pointlaugh")
            await message.add_reaction(icon)
        elif is_cat:
            current_time = time.time() - float(datetime.datetime.now().astimezone().tzinfo.utcoffset(datetime.datetime.now()).seconds) # this is laughable, i hate time
            cat_temp = db["cat"][str(message.channel.id)]
            db["cat"][str(message.channel.id)] = False
            save()
            await message.delete()
            try:
                var = await message.channel.fetch_message(cat_temp)
                catchtime = var.created_at
                await var.delete()

                then = time.mktime(catchtime.timetuple()) + catchtime.microsecond / 1e6
                time_caught = round(((current_time - then) * 100)) / 100
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
                do_time = False
                caught_time = "undefined amounts of time "
                pass

            le_emoji = db["cattype"][str(message.channel.id)]
            icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=le_emoji.lower() + "cat")
            await message.channel.send(message.author.name.replace("@", "`@`") + "#" + str(message.author.discriminator) + " cought " + str(icon) + " " + db["cattype"][str(message.channel.id)] + " cat!!!!1!\nYou now have " + str(add_cat(message.guild.id, message.author.id, db["cattype"][str(message.channel.id)])) + " cats of dat type!!!\nthis fella was cought in " + caught_time[:-1] + "!!!!")
            if do_time and time_caught < get_time(message.guild.id, message.author.id):
                set_time(message.guild.id, message.author.id, time_caught)
            if do_time and time_caught > get_time(message.guild.id, message.author.id, "slow"):
                set_time(message.guild.id, message.author.id, time_caught, "slow")

            if not has_ach(message.guild.id, message.author.id, "first"):
                ach_data = give_ach(message.guild.id, message.author.id, "first")
                embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
                if get_cat(message.guild.id, message.author.id, "Fine") > 20:
                    embed.set_footer(text="well thats rather comedical isnt it")
                await message.channel.send(embed=embed)
            
            if do_time and not has_ach(message.guild.id, message.author.id, "fast_catcher") and get_time(message.guild.id, message.author.id) <= 5:
                ach_data = give_ach(message.guild.id, message.author.id, "fast_catcher")
                embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
                await message.channel.send(embed=embed)

            if do_time and not has_ach(message.guild.id, message.author.id, "slow_catcher") and get_time(message.guild.id, message.author.id, "slow") >= 3600:
                ach_data = give_ach(message.guild.id, message.author.id, "slow_catcher")
                embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
                await message.channel.send(embed=embed)

            async def do_reward(message, level):
                db[str(message.guild.id)][str(message.author.id)]["progress"] = 0
                save()
                reward = level["reward"]
                reward_amount = level["reward_amount"]
                add_cat(message.guild.id, message.author.id, reward, reward_amount)
                icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=reward.lower() + "cat")
                new = add_cat(message.guild.id, message.author.id, "battlepass")
                embed = discord.Embed(title=f"Level {new} complete!", description=f"You have recieved {icon} {reward_amount} {reward} cats!", color=0x007F0E).set_author(name="Battlepass level!", icon_url="https://pomf2.lain.la/f/zncxu6ej.png")
                await message.channel.send(embed=embed)

            if not get_cat(message.guild.id, message.author.id, "battlepass"):
                db[str(message.guild.id)][str(message.author.id)]["battlepass"] = 0
                save()
            if not get_cat(message.guild.id, message.author.id, "progress"):
                db[str(message.guild.id)][str(message.author.id)]["progress"] = 0
                save()

            battlelevel = battle["levels"][get_cat(message.guild.id, message.author.id, "battlepass")]
            if battlelevel["req"] == "catch_fast" and do_time and time_caught < battlelevel["req_data"]:
                await do_reward(message, battlelevel)
            if battlelevel["req"] == "catch":
                add_cat(message.guild.id, message.author.id, "progress")
                if get_cat(message.guild.id, message.author.id, "progress") == battlelevel["req_data"]:
                    await do_reward(message, battlelevel)
            if battlelevel["req"] == "catch_type" and le_emoji == battlelevel["req_data"]:
                await do_reward(message, battlelevel)

    if ':sob:' in text.lower() or "😭" in text.lower():
        icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="pointlaugh")
        await message.add_reaction(icon)
    if text.lower().startswith("cat!beggar") and message.author.id == OWNER_ID:
        give_ach(message.guild.id, int(text[10:].split(" ")[1]), text[10:].split(" ")[2])
        await message.reply("success")
    if text.lower().startswith("cat!sweep") and message.author.id == OWNER_ID:
        db["cat"][str(message.channel.id)] = False
        save()
        await message.reply("success")
    if text.lower().startswith("cat!setup") and message.author.id == OWNER_ID:
        abc = db["summon_ids"]
        abc.append(int(message.channel.id))
        db["summon_ids"] = abc
        db["cat"][str(message.channel.id)] = False
        db["cattype"][str(message.channel.id)] = ""
        fire[str(message.channel.id)] = True
        save()
        await message.reply(f"ok, now i will also send cats in <#{message.channel.id}>")
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
        db[str(message.guild.id)][str(stuff[1])]["custom"] = stuff[2]
        save()
        await message.reply("success")
    if text.lower().startswith("car") and not text.lower().startswith("cart"):
        file = discord.File("car.png", filename="car.png")
        embed = discord.Embed(title="car!", color=0x6E593C).set_image(url="attachment://car.png")
        await message.reply(file=file, embed=embed)
        if not has_ach(message.guild.id, message.author.id, "car"):
            ach_data = give_ach(message.guild.id, message.author.id, "car")
            embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
            await message.reply(embed=embed)
    if text.lower().startswith("cart"):
        file = discord.File("cart.png", filename="cart.png")
        embed = discord.Embed(title="cart!", color=0x6E593C).set_image(url="attachment://cart.png")
        await message.reply(file=file, embed=embed)
    if 'indev2' in text.lower():
        await message.add_reaction('🐸')
    await bot.process_commands(message)

@bot.slash_command(description="Send Help")
async def help(message: discord.Interaction):
    embedVar = discord.Embed(
            title="Send Help", description=discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="staring_cat"), color=0x6E593C
    ).add_field(
            name="Cat Hunt Commands",
            inline=False,
            value="**/inv** - your cats\n**/leaderboards** - da cat leaderboad\n**/donate** - donate your cats to another person\n**/achs** - view your achievements\n**/feedback** - give suggestions, report bugs, and everything in between",
    ).add_field(
            name="Info Commands",
            inline=False,
            value="**/random** - get random cat image\n**right click > apps > catch** - catch someone in 4k\n**/tiktok** - read message as tiktok woman tts\n**/dream** - use funny ai to create images from text\n**/help** - this command\n**/admin** - help for server admins\n**/cat** - get staring cat image\n**/info** - get info bout bot and credits",
    )
    await message.response.send_message(embed=embedVar)

@bot.slash_command(description="Give feedback, report bugs or suggest ideas")
async def feedback(message: discord.Interaction, feedback: str):
    if len(str(message.user) + "\n" + feedback) >= 2000:
        await message.response.send_message("ah hell nah man, ur msg is too long :skull:", ephemeral=True)
        return
    await milenakoos.send(str(message.user) + "\n" + feedback)
    await message.response.send_message("your feedback was directed to the bot owner!", ephemeral=True)

@bot.slash_command(description="View admin help", default_member_permissions=8)
async def admin(message: discord.Interaction):
    embedVar = discord.Embed(
            title="Send Admin Help", description=discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="staring_cat"), color=0x6E593C
    ).add_field(name="Admin Commands", value="**/setup** - makes cat bot send cats in the channel this command is ran in\n**/forget** - reverse of /setup (i forgor :skull:)\n**/sweep** - use if cats stopped spawning for some reason**/summon** - makes cats disappear and reappear out of thin air\n**/giveach** - gib (or take) achievements to people\n**/force** - makes cat appear in chat\n**/say** - chat as cat\n**/reset** - fully resets one's account\n**/nerdmode** - stops someone from catching cats for a certain time period")
    await message.response.send_message(embed=embedVar)

@bot.slash_command(description="View information about the bot")
async def info(message: discord.Interaction):
    embedVar = discord.Embed(title="Cat Bot", color=0x6E593C, description="[Join support server](https://discord.gg/WCTzD3YQEk)\n[GitHub Page](https://github.com/milena-kos/cat-bot)\n\nBot made by Milenakos#3310\nWith contributions by: Calion#0501, youtissoum#5935 and uku1928#8305.\n\nThis bot adds Cat Hunt to your server with many different types of cats for people to discover! People can see leaderboards and give cats to each other.\n\nThanks to:\n**???** for the cat image\n**SLOTHS2005#1326** for getting troh to add cat as an emoji\n**aws.random.cat** for random cats API\n**@weilbyte on GitHub** for TikTok TTS API\n**TheTrashCell#0001** for making cat, suggestions, and a lot more.\n\n**CrazyDiamond469#3422, Phace#9474, SLOTHS2005#1326, frinkifail#1809, Aflyde#3846, TheTrashCell#0001 and Sior Simotideis#4198** for being test monkeys\n\n**And everyone for the support!**")
    await message.response.send_message(embed=embedVar)

if STATUS_PAGE_URL:
    @bot.slash_command(description="View status of Cat Bot")
    async def status(message: discord.Interaction):
        embedVar = discord.Embed(title="Cat Bot Status", color=0x6E593C, description=f"You can view live status page of Cat Bot [here]({STATUS_PAGE_URL}).\n You can also [join Cat Bot server](https://discord.gg/WCTzD3YQEk) to recieve live notifications of downtimes.")
        await message.response.send_message(embed=embedVar)

if STABILITY_KEY:
    @bot.slash_command(description="Generate images from text using Stable Diffusion")
    async def dream(message: discord.Interaction, text: str):
        await message.response.defer()
        if message.user.id in BANNED_ID:
            await message.followup.send("You do not have access to that command.", ephemeral=True)
            return
        url = "https://api.stability.ai/v1alpha/generation/stable-diffusion-v1-5/text-to-image"
        payload = {
                "cfg_scale": 8,
                "height": 512,
                "width": 512,
                "samples": 1,
                "text_prompts": [
                        {
                                "text": text,
                                "weight": 1
                        }
                ],
        }
        headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": STABILITY_KEY
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    if response.status == 400:
                        await message.followup.send("we ran out of api credits, they will be refilled shortly.")
                        await milenakoos.send("/dream api token ran out!")
                    elif response.status == 429:
                        await message.followup.send("Too many requests, try again later.")
                    else:
                        await message.followup.send(f"failed lmao\n\nHTTP {response.status}")
                    return
                answer = await response.json()
                answer = answer["artifacts"][0]
                if answer["finishReason"] == "CONTENT_FILTERED":
                    await message.followup.send("🤨")
                    return
                decoded = base64.decodebytes(answer["base64"].encode("ascii"))
                with io.BytesIO() as f:
                    f.write(decoded)
                    f.seek(0)
                    await message.followup.send(file=discord.File(fp=f, filename='output.png'))

@bot.slash_command(description="Read text as TikTok's TTS woman")
async def tiktok(message: discord.Interaction, text: str):
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
        if not has_ach(message.guild.id, message.user.id, "bwomp"):
            ach_data = give_ach(message.guild.id, message.user.id, "bwomp")
            embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
            await message.channel.send(embed=embed)
        return
    stuff = requests.post("https://tiktok-tts.weilnet.workers.dev/api/generation", headers={"Content-Type": "application/json"}, json={"text": text, "voice": "en_us_002"})
    try:
        data = "" + stuff.json()["data"]
    except TypeError:
        await message.followup.send("i dont speak your language (remove non-english characters, or make message shorter)")
        return
    with io.BytesIO() as f:
        ba = "data:audio/mpeg;base64," + data
        f.write(base64.b64decode(ba))
        f.seek(0)
        await message.followup.send(file=discord.File(fp=f, filename='output.mp3'))

@bot.slash_command(description="Prevent someone from catching cats for a certain time period", default_member_permissions=8)
async def nerdmode(message: discord.Interaction, person: discord.Member, timeout: int):
    if timeout < 0:
        await message.response.send_message("uhh i think time is supposed to be a number", ephemeral=True)
        return
    register_member(message.guild.id, person.id)
    timestamp = round(time.time()) + timeout
    db[str(message.guild.id)][str(person.id)]["timeout"] = timestamp
    save()
    if timeout > 0:
        await message.response.send_message(f"{person} is now in nerd mode until <t:{timestamp}:R>")
    else:
        await message.response.send_message(f"{person} is no longer in nerd mode.")

@bot.slash_command(description="Use if cat spawning is broken", default_member_permissions=8)
async def sweep(message: discord.Interaction):
    db["cat"][str(message.channel.id)] = False
    save()
    await message.response.send_message("success")

@bot.slash_command(description="Get Daily cats")
async def daily(message: discord.Interaction):
    await message.response.send_message("there is no daily cats why did you even try this\nthere ARE cats for voting tho, check out `/vote`")
    if not has_ach(message.guild.id, message.user.id, "daily"):
        ach_data = give_ach(message.guild.id, message.user.id, "daily")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.channel.send(embed=embed)

@bot.slash_command(description="View your inventory")
async def inv(message: discord.Interaction, person_id: Optional[discord.Member] = discord.SlashOption(required=False)):
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
    if slow_time <= 0:
        set_time(message.guild.id, person_id.id, 0, "slow")
    if catch_time <= 0:
        set_time(message.guild.id, person_id.id, 99999999999999)
     
    if me:
        your = "Your"
    else:
        your = person_id.name + "'s"

    embedVar = discord.Embed(
            title=your + " cats:", description=f"{your} fastest catch is: {catch_time} s\nand {your} slowest catch is: {slow_time} h\nAchievements unlocked: {unlocked}/{total_achs} + {minus_achs}", color=0x6E593C
    )
    give_collector = True
    do_save = False
    total = 0
    try:
        custom = db[str(message.guild.id)][str(person_id.id)]["custom"]
    except Exception as e:
        db[str(message.guild.id)][str(person_id.id)]["custom"] = False
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
        save()
    embedVar.set_footer(text=f"Total cats: {total}")
    await message.followup.send(embed=embedVar)
    if me:
        if not has_ach(message.guild.id, message.user.id, "collecter") and give_collector:
            ach_data = give_ach(message.guild.id, message.user.id, "collecter")
            embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
            await message.channel.send(embed=embed)
        if not has_ach(message.guild.id, message.user.id, "fast_catcher") and get_time(message.guild.id, message.user.id) <= 5:
            ach_data = give_ach(message.guild.id, message.user.id, "fast_catcher")
            embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
            await message.channel.send(embed=embed)
        if not has_ach(message.guild.id, message.user.id, "slow_catcher") and get_time(message.guild.id, message.user.id, "slow") >= 3600:
            ach_data = give_ach(message.guild.id, message.user.id, "slow_catcher")
            embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
            await message.channel.send(embed=embed)

@bot.slash_command(description="I like fortnite")
async def battlepass(message: discord.Interaction):
    await message.response.defer()
    register_member(message.user.id, message.guild.id)
    if not get_cat(message.guild.id, message.user.id, "battlepass"):
        db[str(message.guild.id)][str(message.user.id)]["battlepass"] = 0
        save()
    if not get_cat(message.guild.id, message.user.id, "progress"):
        db[str(message.guild.id)][str(message.user.id)]["progress"] = 0
        save()

    current_level = get_cat(message.guild.id, message.user.id, "battlepass")
    embedVar = discord.Embed(title="Cat Battlepass™", description="who thought this was a good idea", color=0x6E593C)

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
        return "Touch grass.\nReward: 1 ~~e~~Girl~~cats~~friend."

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
async def donate(message: discord.Interaction, person: discord.Member, cat_type: str = discord.SlashOption(choices=cattypes), amount: Optional[int] = discord.SlashOption(required=False)):
    if not amount: amount = 1
    person_id = person.id
    if get_cat(message.guild.id, message.user.id, cat_type) >= amount and amount > 0 and message.user.id != person_id:
        remove_cat(message.guild.id, message.user.id, cat_type, amount)
        add_cat(message.guild.id, person_id, cat_type, amount)
        embed = discord.Embed(title="Success!", description=f"Successfully transfered {amount} {cat_type} cats from <@{message.user.id}> to <@{person_id}>!", color=0x6E593C)
        await message.response.send_message(embed=embed)
        if not has_ach(message.guild.id, message.user.id, "donator"):
            ach_data = give_ach(message.guild.id, message.user.id, "donator")
            embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
            await message.channel.send(embed=embed)
        if not has_ach(message.guild.id, person_id, "anti_donator"):
            ach_data = give_ach(message.guild.id, person_id, "anti_donator")
            embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
            await message.channel.send(embed=embed.set_footer(text="unlocked by " + person.name + ", not you"))
        if not has_ach(message.guild.id, message.user.id, "rich") and person_id == bot.user.id and cat_type == "Ultimate" and int(amount) >= 5:
            ach_data = give_ach(message.guild.id, message.user.id, "rich")
            embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
            await message.channel.send(embed=embed)
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
                    if not has_ach(message.guild.id, person_id, "secret"):
                        ach_data = give_ach(message.guild.id, person_id, "secret")
                        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
                        await message.channel.send(embed=embed)
                    await interaction.response.send_message(f"You evaded the tax of {tax_amount} Fine cats.")
                else:
                    await interaction.response.send_message(choice(funny), ephemeral=True)
                
            embed = discord.Embed(title="HOLD UP!", description="Thats rather large amount of fine cats! You will need to pay a cat tax of 20% your transaction, do you agree?", color=0x6E593C)
            
            button = Button(label="Pay!", style=ButtonStyle.green)
            button.callback = pay
            
            button2 = Button(label="Evade the tax", style=ButtonStyle.red)
            button2.callback = evade

            myview = View()

            myview.add_item(button)
            myview.add_item(button2)
            await message.channel.send(embed=embed, view=myview)
    else:
        await message.response.send_message("no", ephemeral=True)

@bot.slash_command(description="Get Cat")
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

if TOP_GG_TOKEN:
    @bot.slash_command(description="Vote on topgg for free cats")
    async def vote(message: discord.Interaction):
        vote_status = await bot.topggpy.get_user_vote(message.user.id)
        icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="goodcat")
        if vote_status:
            if get_cat(0, message.user.id, "vote_time") + 43200 <= time.time():
                # valid vote
                add_cat(message.guild.id, message.user.id, "Good", 5)
                add_cat(0, message.user.id, "vote_time", time.time(), True)
                embedVar = discord.Embed(title="Vote redeemed!", description=f"You have recieved {icon} 5 Good cats.\nVote again in 12 hours.", color=0x007F0E)
                await message.response.send_message(embed=embedVar)
            else:
                countdown = round(get_cat(0, message.user.id, "vote_time") + 43200)
                embedVar = discord.Embed(title="Already voted!", description=f"You have already [voted for Cat Bot on top.gg](https://top.gg/bot/966695034340663367)!\nVote again <t:{countdown}:R> to recieve {icon} 5 more Good cats.", color=0x6E593C)
                await message.response.send_message(embed=embedVar)
        else:
            embedVar = discord.Embed(title="Vote for Cat Bot", description=f"[Vote for Cat Bot on top.gg](https://top.gg/bot/966695034340663367) every 12 hours to recieve {icon} 5 Good cats.\n\nRun this command again after you voted to recieve your cats.", color=0x6E593C)
            await message.response.send_message(embed=embedVar)

@bot.slash_command(description="Get a random cat")
async def random(message: discord.Interaction):
    counter = 0
    while True:
        if counter == 11:
            return
        response = requests.get('https://aws.random.cat/meow')
        try:
            data = response.json()
            await message.response.send_message(data['file'])
            counter += 1
            if not has_ach(message.guild.id, message.user.id, "randomizer"):
                ach_data = give_ach(message.guild.id, message.user.id, "randomizer")
                embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
                await message.channel.send(embed=embed)
            return
        except Exception:
            pass
        counter += 1

@bot.slash_command(description="View your achievements")
async def achs(message: discord.Interaction):
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
    embedVar = discord.Embed(
            title="Your achievements:", description=f"{unlocked}/{total_achs} + {minus_achs}", color=0x6E593C
    )

    def gen_new(category):
        nonlocal db_var, message, unlocked, total_achs
        hidden_suffix = ""
        if category == "Hidden":
            hidden_suffix = "\n\nThis is a \"Hidden\" category. Achievements here only show up after you complete them."
        newembed = discord.Embed(
                title=category, description=f"Achievements unlocked (total): {unlocked}/{total_achs} + {minus_achs}{hidden_suffix}", color=0x6E593C
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
            if not has_ach(message.guild.id, interaction.user.id, "curious"):
                ach_data = give_ach(message.guild.id, interaction.user.id, "curious")
                embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png").set_footer(text="Proudly unlocked by " + interaction.user.name)
                await message.channel.send(embed=embed)

    def insane_view_generator(category):
        myview = View()
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

    myview = View()
    myview.add_item(button)

    await message.response.send_message(embed=embedVar, view=myview)

@bot.message_command(name="catch (Whitney)")
async def catch_old(message: discord.Interaction, msg):
    await catch(message, msg, False)

@bot.message_command(name="catch (gg sans)")
async def catch_new(message: discord.Interaction, msg):
    await catch(message, msg, True)

async def catch(message: discord.Interaction, msg, sansgg):
    try:
        msg2img.msg2img(msg, bot, sansgg)
        file = discord.File("generated.png", filename="generated.png")
        await message.response.send_message("cought in 4k", file=file)
    except Exception as e:
        await message.response.send_message(f"the message appears to have commited no live anymore\n\n{e}", ephemeral=True)
    register_member(message.guild.id, msg.author.id)
    if not has_ach(message.guild.id, msg.author.id, "4k") and msg.author.id != bot.user.id:
        ach_data = give_ach(message.guild.id, message.user.id, "4k")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.channel.send(embed=embed)

@bot.message_command(name="Whitney vs gg sans")
async def comparison(message: discord.Interaction, msg):
    await message.response.send_message(file=discord.File("ggsanswhitney.png", filename="ggsanswhitney.png"))

@bot.message_command()
async def pointLaugh(message: discord.Interaction, msg):
    icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="pointlaugh")
    await msg.add_reaction(icon)
    await message.response.send_message(icon, ephemeral=True)

@bot.slash_command(description="View the leaderboards")
async def leaderboards(message: discord.Interaction):
    async def lb_handler(interaction, type):
        nonlocal message
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
                    if a != "time" and a != "timeslow" and a != "ach" and a != "custom" and a != "timeout" and a != "battlepass" and a != "progress":
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
                if len(rarest_holder) <= 5:
                    joined = ", ".join(rarest_holder)
                    string = f"Rarest cat: {catmoji} ({joined}'s)\n"
                else:
                    joined = ", ".join(rarest_holder[:3])
                    string = f"Rarest cat: {catmoji} ({joined} and others)\n"

        current = 1
        for i, num in largest:
            string = string + str(current) + ". " + str(num) + i + "\n"
            current += 1
        embedVar = discord.Embed(
                title=f"{title} Leaderboards:", description=string, color=0x6E593C
        ).set_footer(text="if two people have same pb, random dad joke determines who places above")

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

        myview = View()
        myview.add_item(button1)
        myview.add_item(button2)
        myview.add_item(button3)

        await interaction.edit(embed=embedVar, view=myview)

    async def slowlb(interaction):
        await lb_handler(interaction, "slow")

    async def fastlb(interaction):
        await lb_handler(interaction, "fast")

    async def catlb(interaction):
        await lb_handler(interaction, "main")

    embed = discord.Embed(title="The Leaderboards", description="select your leaderboard using buttons below", color=0x6E593C)
    button1 = Button(label="Cats", style=ButtonStyle.blurple)
    button1.callback = catlb

    button2 = Button(label="Fastest", style=ButtonStyle.blurple)
    button2.callback = fastlb

    button3 = Button(label="Slowest", style=ButtonStyle.blurple)
    button3.callback = slowlb

    myview = View()
    myview.add_item(button1)
    myview.add_item(button2)
    myview.add_item(button3)

    await message.response.send_message(embed=embed, view=myview)

@bot.slash_command(description="Give cats to people", default_member_permissions=8)
async def summon(message: discord.Interaction, person_id: discord.Member, amount: int, cat_type: str = discord.SlashOption(choices=cattypes)):
    add_cat(message.guild.id, person_id.id, cat_type, amount)
    embed = discord.Embed(title="Success!", description=f"gave <@{person_id.id}> {amount} {cat_type} cats", color=0x6E593C)
    await message.response.send_message(embed=embed)

@bot.slash_command(description="Say stuff as cat", default_member_permissions=8)
async def say(message: discord.Interaction, text: str):
    await message.response.send_message("success", ephemeral=True)
    await message.channel.send(text)

@bot.slash_command(description="Setup cat in current channel", default_member_permissions=8)
async def setup(message: discord.Interaction):
    if int(message.channel.id) in db["summon_ids"]:
        await message.response.send_message("bruh you already setup cat here are you dumb\n\nthere might already be a cat sitting in chat. type `cat` to catch it.")
        return
    abc = db["summon_ids"]
    abc.append(int(message.channel.id))
    db["summon_ids"] = abc
    db["cat"][str(message.channel.id)] = False
    db["cattype"][str(message.channel.id)] = ""
    fire[str(message.channel.id)] = True
    save()
    await message.response.send_message(f"ok, now i will also send cats in <#{message.channel.id}>")

@bot.slash_command(description="Undo the setup", default_member_permissions=8)
async def forget(message: discord.Interaction):
    if int(message.channel.id) in db["summon_ids"]:
        abc = db["summon_ids"]
        abc.remove(int(message.channel.id))
        db["summon_ids"] = abc
        save()
        await message.response.send_message(f"ok, now i wont send cats in <#{message.channel.id}>")
    else:
        await message.response.send_message("your an idiot there is literally no cat setupped in this channel you stupid")

@bot.slash_command(description="LMAO TROLLED SO HARD :JOY:")
async def fake(message: discord.Interaction):
    file = discord.File("australian cat.png", filename="australian cat.png")
    icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="egirlcat")
    await message.channel.send(str(icon) + " eGirl cat hasn't appeared! Type \"cat\" to catch ratio!", file=file)
    if not has_ach(message.guild.id, message.user.id, "trolled"):
        ach_data = give_ach(message.guild.id, message.user.id, "trolled")
        embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
        await message.response.send_message("OMG TROLLED SO HARD LMAOOOO :joy:", embed=embed, ephemeral=True)
        return
    await message.response.send_message("OMG TROLLED SO HARD LMAOOOO :joy:", ephemeral=True)

@bot.slash_command(description="Force cats to appear", default_member_permissions=8)
async def force(message: discord.Interaction, cat_type: Optional[str] = discord.SlashOption(required=False, choices=cattypes)):
    try:
        if db["cat"][str(message.channel.id)]:
            await message.response.send_message("there is already a cat", ephemeral=True)
            return
    except Exception:
        await message.response.send_message("this channel is not /setup-ed", ephemeral=True)
        return
    channeley = message.channel
    fire[channeley.id] = False
    file = discord.File("cat.png", filename="cat.png")
    if not cat_type:
        localcat = choice(CAT_TYPES)
    else:
        localcat = cat_type
    db["cattype"][str(channeley.id)] = localcat
    icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=localcat.lower() + "cat")
    message_lmao =  await message.channel.send(str(icon) + " " + db["cattype"][str(channeley.id)] + " cat has appeared! Type \"cat\" to catch it!", file=file)
    db["cat"][str(channeley.id)] = message_lmao.id
    save()
    await message.response.send_message("done", ephemeral=True)

@bot.slash_command(description="View list of achievements names", default_member_permissions=8)
async def achlist(message: discord.Interaction):
    stringy = ""
    for k, v in ach_list.items():
        stringy = stringy + k + " - " + v["title"] + "\n"
    embed = discord.Embed(title="Ach IDs", description=stringy, color=0x6E593C)
    await message.response.send_message(embed=embed)

@bot.slash_command(description="Give achievements to people", default_member_permissions=8)
async def giveach(message: discord.Interaction, person_id: discord.Member, ach_id: str):
    try:
        if ach_id in ach_names:
            valid = True
        else:
            valid = False
    except KeyError:
        valid = False
    if valid:
        reverse = has_ach(message.guild.id, person_id.id, ach_id, False)
        give_ach(message.guild.id, person_id, ach_id, reverse)
        embed = discord.Embed(title="Success!", description=f"Successfully set {ach_id} to {not reverse} for <@{person_id.id}>!", color=0x6E593C)
        await message.response.send_message(embed=embed)
    else:
        await message.response.send_message("i cant find that achievement! run `/achlist` for all of achievement ids!", ephemeral=True)

@bot.slash_command(description="Reset people", default_member_permissions=8)
async def reset(message: discord.Interaction, person_id: discord.Member):
    del db[str(message.guild.id)][str(person_id.id)]
    save()
    await message.response.send_message(embed=discord.Embed(color=0x6E593C, description=f'Done! rip <@{person_id.id}>. f\'s in chat.'))

# remove decorators for disabled commands, such as /status or /vote
@dream.error
@myLoop.error
@warning.error
@help.error
@sweep.error
@feedback.error
@admin.error
@info.error
@tiktok.error
@nerdmode.error
@daily.error
@inv.error
@battlepass.error
@ping.error
@donate.error
@status.error
@vote.error
@cat.error
@cursed.error
@bal.error
@random.error
@achs.error
@catch_old.error
@catch_new.error
@pointLaugh.error
@leaderboards.error
@summon.error
@say.error
@setup.error
@forget.error
@fake.error
@force.error
@achlist.error
@giveach.error
@reset.error
async def on_command_error(ctx, error):
    if error == KeyboardInterrupt:
        return
    elif error == discord.errors.Forbidden:
        try:
            await ctx.reply("i don't have permissions to do that. (try reinviting the bot)")
        except:
            await ctx.channel.send("i don't have permissions to do that. (try reinviting the bot)")
    elif error == discord.errors.NotFound:
        try:
            await ctx.reply("took too long, try running the command again")
        except:
            await ctx.channel.send("took too long, try running the command again")
    else:
        try:
            await ctx.reply("cat crashed lmao\ni automatically sent crash reports so yes")
        except:
            await ctx.channel.send("cat crashed lmao\ni automatically sent crash reports so yes")
        try:
            if not has_ach(ctx.guild.id, ctx.user.id, "crasher"):
                ach_data = give_ach(ctx.guild.id, ctx.user.id, "crasher")
                embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
                await ctx.channel.send(embed=embed)
        except Exception:
            pass

        try:
            link = (
                    "https://discord.com/channels/"
                    + str(ctx.guild.id)
                    + "/"
                    + str(ctx.channel.id)
                    + "/"
                    + str(ctx.id)
            )
            print("debug", link)
        except Exception as e:
            link = "Error getting"

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

bot.run(TOKEN)
