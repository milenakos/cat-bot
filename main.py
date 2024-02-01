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
CATS_GUILD_ID = False # alternative guild purely for cattype emojis (use for christmas/halloween etc), False to disable
BACKUP_ID = 1060545763194707998 # channel id for db backups, private extremely recommended

# discord bot token, use os.environ for more security
TOKEN = os.environ['token']
# TOKEN = "token goes here"

# tiktok session id, set to False to disable
TIKTOK_SESSION = os.environ["tiktok_session"]

# this will automatically restart the bot if message in GITHUB_CHANNEL_ID is sent, you can use a github webhook for that
# set to False to disable
GITHUB_CHANNEL_ID = 1060965767044149249

BANNED_ID = [1029044762340241509] # banned from using /tiktok

WHITELISTED_BOTS = [] # bots which are allowed to catch cats

# use if bot is in a team
# if you dont know what that is or dont use it,
# you can remove this line
OWNER_ID = 553093932012011520 

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
                super().__setitem__(key, {})
                return {}

db = PopulatedDict()

# laod the jsons
with open("aches.json", "r") as f:
    ach_list = json.load(f)

with open("battlepass.json", "r") as f:
    battle = json.load(f)

# convert achievement json to a few other things
ach_names = ach_list.keys()
ach_titles = {value["title"].lower(): key for (key, value) in ach_list.items()}

intents = discord.Intents(message_content=True, messages=True, reactions=True, guilds=True)
bot = commands.AutoShardedBot(command_prefix="https://www.youtube.com/watch?v=dQw4w9WgXcQ", intents=intents, help_command=None, max_messages=None)

# this list stores unique non-duplicate cattypes
cattypes = []
for e in CAT_TYPES:
    if e not in cattypes:
        cattypes.append(e)

funny = ["why did you click this this arent yours", "absolutely not", "cat bot not responding, try again later", "you cant", "can you please stop", "try again", "403 not allowed", "stop", "get a life", "not for you", "no", "nuh uh"]

summon_id = db["summon_ids"]

milenakoos = 0
try:
    if not OWNER_ID:
        OWNER_ID = 0
except Exception:
    OWNER_ID = 0

save_queue = []
terminate_queue = []
update_queue = []

# docs suggest on_ready can be called multiple times
on_ready_debounce = False

# we store all discord text emojis to not refetch them a bajillion times
# (this does mean you will need to restart the bot if you reupload an emoji)
emojis = {}
do_save_emojis = False

# fire list controls whether to spawn the cat or skip to the next cycle
# (this is done on /forcespawn to prevent too many spawns)
fire = {}
for i in summon_id:
    fire[i] = True

# this is a helper which saves id to its .json file
def save(id):
    id = str(id)
    save_queue.append(id)

# this is probably a good time to explain the database structure
# each server is a json file
# however there are multiple jsons which arent for servers yet are stored the same way

# create total_members variable if it isnt real already
try:
    if not db["total_members"]:
        raise KeyError
except KeyError:
    db["total_members"] = 0
    save("total_members")

# those are helper functions to automatically check if value exists, save it if needed etc
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
            if not result: raise Exception
            if do_save_emojis: emojis[name] = str(result)
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
    if not has_ach(message.guild.id, author, ach_id):
        ach_data = give_ach(message.guild.id, author, ach_id)
        desc = ach_data["description"]
        if ach_id == "dataminer":
            desc = "Your head hurts -- you seem to have forgotten what you just did to get this."
        
        if ach_id != "thanksforplaying":
            embed = discord.Embed(title=ach_data["title"], description=desc, color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png").set_footer(text=f"Unlocked by {author_string.name}")
        else:
            embed = discord.Embed(title="Cataine Addict", description="Defeat the dog mafia\nThanks for playing! ✨", color=0xC12929).set_author(name="Demonic achievement unlocked! 🌟", icon_url="https://pomf2.lain.la/f/ez0enx2d.png").set_footer(text=f"Congrats to {author_string.name}!!")

        if send_type == "reply": result = await message.reply(embed=embed)
        elif send_type == "send": result = await message.channel.send(embed=embed)
        elif send_type == "followup": result = await message.followup.send(embed=embed, ephemeral=True)
        elif send_type == "response": result = await message.response.send_message(embed=embed)

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


# if ch_id is None it runs the default loop for all servers
# otherwise only for ch_id
# this is used for custom cat spawn timings
async def run_spawn(ch_id=None):
    global bot, fire, save_queue, db
    
    if ch_id:
        summon_id = [int(ch_id)]
    else:
        # update status
        total_members = db["total_members"]
        await bot.change_presence(
                activity=discord.CustomActivity(name=f"Catting in {len(bot.guilds):,} servers with {total_members:,} people", emoji=discord.PartialEmoji.from_str(get_emoji("staring_cat")))
        )

        summon_id = db["summon_ids"]
        print("Main cat loop is running")
    
    for i in summon_id:
        try:
            if fire[i] and not db["cat"][str(i)] and (ch_id or str(i) not in db["spawn_times"].keys()):
                file = discord.File("cat.png")
                localcat = choice(CAT_TYPES)
                icon = get_emoji(localcat.lower() + "cat")
                channeley = await bot.fetch_channel(int(i))
                try:
                    if db[str(channeley.guild.id)]["appear"]:
                        appearstring = db[str(channeley.guild.id)]["appear"]
                    else:
                        appearstring = "{emoji} {type} cat has appeared! Type \"cat\" to catch it!"
                except Exception as e:
                    db[str(channeley.guild.id)]["appear"] = ""
                    appearstring = "{emoji} {type} cat has appeared! Type \"cat\" to catch it!"
                
                message_is_sus = await channeley.send(appearstring.format(emoji=str(icon), type=localcat), file=file)
                db["cat"][str(i)] = message_is_sus.id
        except discord.NotFound:
            summon_id.remove(i)
        except discord.Forbidden:
            summon_id.remove(i)
        except Exception:
            pass
        fire[i] = True
    
    save("cat")
    
    if not ch_id:
        db["summon_ids"] = list(set(summon_id)) # remove all duplicates
        save("summon_ids")
        print("Finished cat loop")

        for id in set(save_queue):
            with open(f"data/{id}.json", "w") as f:
                json.dump(db[id], f)
    
        save_queue = []
    
        # backup
        with tarfile.open("backup.tar.gz", "w:gz") as tar:
            tar.add("data", arcname=os.path.sep)
        
        backupchannel = await bot.fetch_channel(BACKUP_ID)
        thing = discord.File("backup.tar.gz", filename="backup.tar.gz")
        await backupchannel.send(f"In {len(bot.guilds)} servers.", file=thing)


# update the server counter in bot's status
@tasks.loop(seconds=3600)
async def update_presence():
    # while servers are updated on every loop, members are more resource and api-calls intensive, thus update once a hour
    total = 0
    for i in bot.guilds:
        g = await bot.fetch_guild(i.id)
        total += g.approximate_member_count
    db["total_members"] = total
    save("total_members")


# main spawn waiting loop
# again, if ch_id is None its for basic spawns
# otherwise for custom timings
async def spawning_loop(times, ch_id):
    global terminate_queue, update_queue
    print("opened a loop for", ch_id)
    can_recover = True # we only recover the first time the loop is ran
    while True:
        try:
            if can_recover and db["recovery_times"][str(ch_id)] > time.time():
                # recover
                wait_time = db["recovery_times"][str(ch_id)] - time.time()
                print("recovered", ch_id, "looping in", wait_time)
            else:
                raise Exception
        except Exception:
            wait_time = randint(times[0], times[1])
            db["recovery_times"][str(ch_id)] = time.time() + wait_time
            save("recovery_times")

        can_recover = False

        await asyncio.sleep(wait_time)

        if str(ch_id) in terminate_queue:
            print("terminating", ch_id)
            terminate_queue.remove(str(ch_id))
            return
        if str(ch_id) in update_queue:
            print("updating", ch_id)
            update_queue.remove(str(ch_id))
            times = db["spawn_times"][ch_id]

        try:
            await run_spawn(ch_id)
        except Exception as e:
            print(e)

# some code which is run when bot is started
@bot.event
async def on_ready():
    global milenakoos, OWNER_ID, do_save_emojis, save_queue, on_ready_debounce
    if on_ready_debounce:
        return
    on_ready_debounce = True
    print("cat is now online")
    do_save_emojis = True
    total_members = db["total_members"]
    await bot.change_presence(
        activity=discord.CustomActivity(name=f"Just restarted! In {len(bot.guilds):,} servers with {total_members:,} people")
    )
    appinfo = await bot.application_info()
    if not OWNER_ID:
        milenakoos = appinfo.owner
        OWNER_ID = milenakoos.id
    else:
        milenakoos = await bot.fetch_user(OWNER_ID)
    update_presence.start()

    register_guild("spawn_times")
    register_guild("recovery_times")

    # we create all spawning loops
    for k, v in db["spawn_times"].items():
        bot.loop.create_task(spawning_loop(v, k))

    bot.loop.create_task(spawning_loop([120, 1200], None))


# this is all the code which is ran on every message sent
# its mostly for easter eggs or achievements
@bot.event
async def on_message(message):
    global fire, save_queue
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
        ["indev", "vanilla", "🐸"],
        ["bleh", "custom", "blepcat"],
        ["blep", "custom", "blepcat"]]

    responses = [["testing testing 1 2 3", "exact", "test success"],
        ["cat!sex", "exact", "..."],
        ["cellua good", "in", ".".join([str(randint(2, 254)) for _ in range(4)])],
        ["https://tenor.com/view/this-cat-i-have-hired-this-cat-to-stare-at-you-hired-cat-cat-stare-gif-26392360", "exact", "https://tenor.com/view/cat-staring-cat-gif-16983064494644320763"]]

    # this is auto-update thing
    if GITHUB_CHANNEL_ID and message.channel.id == GITHUB_CHANNEL_ID:
        for id in set(save_queue):
            with open(f"data/{id}.json", "w") as f:
                json.dump(db[id], f)
        os.system("git pull")
        os.execv(sys.executable, ['python'] + sys.argv)

    # :staring_cat: reaction on "bullshit"
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
            await message.add_reaction(get_emoji("staring_cat"))
    
    if "robotop" in message.author.name.lower() and "i rate **cat" in message.content.lower():
        icon = str(get_emoji("no_cat_throphy")) + " "
        await message.reply("**RoboTop**, I rate **you** 0 cats " + icon * 5)

    if "leafbot" in message.author.name.lower() and "hmm... i would rate cat" in message.content.lower():
        icon = str(get_emoji("no_cat_throphy")) + " "
        await message.reply("Hmm... I would rate you **0 cats**! " + icon * 5)
        
    if text == "lol_i_have_dmed_the_cat_bot_and_got_an_ach" and not message.guild:
        await message.channel.send("which part of \"send in server\" was unclear?")
        return
    elif message.guild == None:
        await message.channel.send("good job! please send \"lol_i_have_dmed_the_cat_bot_and_got_an_ach\" in server to get your ach!")
        return
    
    if "cat!n4lltvuCOKe2iuDCmc6JsU7Jmg4vmFBj8G8l5xvoDHmCoIJMcxkeXZObR6HbIV6" in text:
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
            if r[1] == "custom": await message.add_reaction(get_emoji(r[2]))
            elif r[1] == "vanilla": await message.add_reaction(r[2])
            
    for resp in responses:
        if (resp[1] == "startswith" and text.lower().startswith(resp[0])) or \
        (resp[1] == "re" and re.seach(resp[0], text.lower())) or \
        (resp[1] == "exact" and resp[0] == text.lower()) or \
        (resp[1] == "in" and resp[0] in text.lower()):
            await message.reply(resp[2])
        
    if message.author in message.mentions: await message.add_reaction(get_emoji("staring_cat"))

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

    # this is run whether someone says "cat" (very complex)
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
            # if there is no cat, you are /preventcatch-ed, or you aren't a whitelisted bot
            icon = get_emoji("pointlaugh")
            await message.add_reaction(icon)
        elif is_cat:
            current_time = message.created_at.timestamp()
            db["lastcatches"][str(message.channel.id)] = current_time
            cat_temp = db["cat"][str(message.channel.id)]
            db["cat"][str(message.channel.id)] = False
            save("cat")
            save("lastcatches")
            try:
                await message.delete()
            except discord.errors.Forbidden:
                await message.channel.send("I don't have permission to delete messages. Please re-invite the bot or manually add that permission.")
            try:
                var = await message.channel.fetch_message(cat_temp)
            except Exception:
                await message.channel.send(f"oopsie poopsie i cant access the original message but {message.author.mention} *did* catch a cat rn")
                return
            catchtime = var.created_at
            catchcontents = var.content
            await var.delete()
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
            except Exception as e:
                # if some of the above explodes just give up
                print(e)
                do_time = False
                caught_time = "undefined amounts of time "

            icon = None
            for v in allowedemojis:
                if v in catchcontents:
                    partial_type = v
                    break

            for i in type_dict.keys():
                if i.lower() in partial_type:
                    le_emoji = i
                    break

            if not le_emoji: return
                
            icon = get_emoji(partial_type)

            try:
                if db[str(message.guild.id)]["cought"]:
                    pass
            except Exception:
                db[str(message.guild.id)]["cought"] = ""

            suffix_string = ""
            silly_amount = 1
            if get_cat(message.guild.id, message.author.id, "cataine_active") > time.time():
                # cataine is active
                silly_amount = 2
                suffix_string = f"\n🧂 cataine worked! you got 2 cats instead!"
                
            elif get_cat(message.guild.id, message.author.id, "cataine_active") != 0:
                # cataine ran out
                add_cat(message.guild.id, message.author.id, "cataine_active", 0, True)
                suffix_string = f"\nyour cataine buff has expired. you know where to get a new one 😏"

            if db[str(message.guild.id)]["cought"]:
                coughstring = db[str(message.guild.id)]["cought"]
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
                if get_cat(message.guild.id, message.author.id, "dark_market") != 0:
                    await interaction.response.send_message("the shadowy figure is nowhere to be found.", ephemeral=True)
                    return
                add_cat(message.guild.id, message.author.id, "dark_market", 1, True)
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
            
            if randint(0, 50) == 0:
                button = Button(label="Join our Discord!", style=ButtonStyle.gray, url="https://discord.gg/WCTzD3YQEk")
            elif randint(0, 10) == 0 and get_cat(message.guild.id, message.author.id, "Fine") >= 20 and get_cat(message.guild.id, message.author.id, "dark_market") == 0:
                button = Button(label="You see a shadow...", style=ButtonStyle.blurple)
                button.callback = dark_market_cutscene
            
            if button:
                view = View(timeout=1200)
                view.add_item(button)
            
            await message.channel.send(coughstring.format(username=message.author.name.replace("_", "\_"),
                                                           emoji=icon,
                                                           type=le_emoji,
                                                           count=add_cat(message.guild.id, message.author.id, le_emoji, silly_amount),
                                                           time=caught_time[:-1]) + suffix_string,
                                       view=view,
                                       allowed_mentions=None)
            
            # handle fastest and slowest catches
            if do_time and time_caught < get_time(message.guild.id, message.author.id):
                set_time(message.guild.id, message.author.id, time_caught)
            if do_time and time_caught > get_time(message.guild.id, message.author.id, "slow"):
                set_time(message.guild.id, message.author.id, time_caught, "slow")

            await achemb(message, "first", "send")
            
            if do_time and get_time(message.guild.id, message.author.id) <= 5: await achemb(message, "fast_catcher", "send")

            if do_time and get_time(message.guild.id, message.author.id, "slow") >= 3600: await achemb(message, "slow_catcher", "send")

            if do_time and time_caught == 3.14: await achemb(message, "pie", "send")

            # handle battlepass
            async def do_reward(message, level):
                db[str(message.guild.id)][str(message.author.id)]["progress"] = 0
                reward = level["reward"]
                reward_amount = level["reward_amount"]
                add_cat(message.guild.id, message.author.id, reward, reward_amount)
                icon = get_emoji(reward.lower() + "cat")
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

    # those are "owner" commands which are not really interesting
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
        fire[str(message.channel.id)] = True
        save("summon_ids")
        save("cat")
        await message.reply(f"ok, now i will also send cats in <#{message.channel.id}>")
    if text.lower().startswith("cat!print") and message.author.id == OWNER_ID:
        # just a simple one-line with no async (e.g. 2+3)
        await message.reply(eval(text[9:]))
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
        exec(complete)
    if text.lower().startswith("cat!news") and message.author.id == OWNER_ID:
        for i in db["summon_ids"]:
            try:
                channeley = await bot.fetch_channel(int(i))
                await channeley.send(text[8:])
            except Exception:
                pass
    if text.lower().startswith("cat!dark") and message.author.id == OWNER_ID:
        stuff = text.split(" ")
        add_cat(message.guild.id, stuff[1], "dark_market")
        await message.reply("success")
    if text.lower().startswith("cat!darkoff") and message.author.id == OWNER_ID:
        stuff = text.split(" ")
        add_cat(message.guild.id, stuff[1], "dark_market", 0, True)
        await message.reply("success")
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
        catchmsg = await message.channel.fetch_message(db["cat"][str(message.channel.id)])
        if get_emoji("suscat") in catchmsg.content:
            for i in ["sus", "amogus", "among", "vent", "report"]:
                if i in text.lower():
                    await achemb(message, "sussy", "send")
                    break
    except Exception:
        pass


# the message when cat gets added to a new server
@bot.event
async def on_guild_join(guild):
    def verify(ch):
        return ch and ch.permissions_for(guild.me).send_messages

    def find(patt, channels):
        for i in channels:
            if patt in i.name:
                return i

    # we try to find a channel with the name "cat", then "bots", then whenever we cat atleast chat
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
    await ch.send(unofficial_note + "Thanks for adding me!\nTo start, use `/help`!\nJoin the support server here: https://discord.gg/WCTzD3YQEk\nHave a nice day :)")

@bot.slash_command(description="Learn to use the bot")
async def help(message):
    embed1 = discord.Embed(
        title = "How to Setup",
        description = "Server moderator (anyone with *Manage Server* permission) needs to run `/setup` in any channel. After that, cats will start to spawn in 2-20 minute intervals inside of that channel.\nYou can customize those intervals with `/changetimings` and change the spawn message with `/changemessage`.\nCat spawns can also be forced by moderators using `/forcespawn` command.\nYou can have unlimited amounts of setupped channels at once.\nYou can stop the spawning in a channel by running `/forget`.",
        color = 0x6E593C
    ).set_thumbnail(
        "https://pomf2.lain.la/f/zncxu6ej.png"
    )
    
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
        value="Cat Bot has various other mechanics to make fun funnier. You can collect various `/achievements`, progress in the `/battlepass`, or have beef with the mafia over cataine addiction. The amount you worship is the limit!",
        inline=False
    ).add_field(
        name="Other features",
        value="Cat Bot has extra fun commands which you will discover along the way.\nAnything unclear? Drop us a line at our [Discord server](https://discord.gg/WCTzD3YQEk).",
        inline=False
    ).set_footer(
        text=f"Cat Bot by Milenakos, {datetime.datetime.now().year}",
        icon_url="https://pomf2.lain.la/f/zncxu6ej.png"
    )

    await message.response.send_message(embeds=[embed1, embed2])

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
    
    embedVar = discord.Embed(title="Cat Bot", color=0x6E593C, description="[Join support server](https://discord.gg/WCTzD3YQEk)\n[GitHub Page](https://github.com/milena-kos/cat-bot)\n\n" + \
                             f"Bot made by {gen_credits['author']}\nWith contributions by {gen_credits['contrib']}.\n\nThis bot adds Cat Hunt to your server with many different types of cats for people to discover! People can see leaderboards and give cats to each other.\n\n" + \
                             f"Thanks to:\n**pathologicals** for the cat image\n**{gen_credits['emoji']}** for getting troh to add cat as an emoji\n**thecatapi.com** for random cats API\n**{gen_credits['trash']}** for making cat, suggestions, and a lot more.\n\n**{gen_credits['tester']}** for being test monkeys\n\n**And everyone for the support!**")
    
    # add "last update" to footer if we are using git
    if GITHUB_CHANNEL_ID:
        embedVar.timestamp = datetime.datetime.fromtimestamp(int(subprocess.check_output(["git", "show", "-s", "--format=%ct"]).decode("utf-8")))
        embedVar.set_footer(text="Last updated:")
    await message.followup.send(embed=embedVar)

if TIKTOK_SESSION:
    @bot.slash_command(description="Read text as TikTok's TTS woman")
    async def tiktok(message: discord.Interaction, text: str = discord.SlashOption(description="The text to be read! (300 characters max)")):
        if message.user.id in BANNED_ID:
            await message.response.send_message("You do not have access to that command.", ephemeral=True)
            return
        
        # detect n-words
        for i in NONOWORDS:
            if i in text.lower():
                await message.response.send_message("Do not.", ephemeral=True)
                return
    
        text = text.replace("+", "plus").replace(" ", "+").replace("&", "and")
        
        await message.response.defer()
        
        if text == "bwomp":
            file = discord.File("bwomp.mp3", filename="bwomp.mp3")
            await message.followup.send(file=file)
            await achemb(message, "bwomp", "send")
            return

        # https://github.com/oscie57/tiktok-voice/blob/main/main.py
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"https://api16-normal-v6.tiktokv.com/media/api/text/speech/invoke/?text_speaker=en_us_002&req_text={text}&speaker_map_type=0&aid=1233",
                                    headers={'User-Agent': 'com.zhiliaoapp.musically/2022600030 (Linux; U; Android 7.1.2; es_ES; SM-G988N; Build/NRD90M;tt-ok/3.12.13.1)',
                                             'Cookie': f'sessionid={TIKTOK_SESSION}'}) as response:
                    stuff = await response.json()
                    data = "" + stuff["data"]["v_str"]
                    with io.BytesIO() as f:
                        ba = "data:audio/mpeg;base64," + data
                        f.write(base64.b64decode(ba))
                        f.seek(0)
                        await message.followup.send(file=discord.File(fp=f, filename='output.mp3'))
            except Exception:
                await message.followup.send("i dont speak your language (remove non-english characters, make sure the message is below 300 chars)")

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
    if int(message.channel.id) in db["spawn_times"]:
        try: del db["recovery_times"][str(message.channel.id)]
        except: pass
        save("recovery_times")
    await message.response.send_message("success. if you still have issues, join our server: https://discord.gg/WCTzD3YQEk")

@bot.slash_command(description="(ADMIN) Change the cat appear timings", default_member_permissions=32)
async def changetimings(message: discord.Interaction,
                        minimum_time: Optional[int] = discord.SlashOption(required=False, description="In seconds, minimum possible time between spawns (leave both empty to reset)"),
                        maximum_time: Optional[int] = discord.SlashOption(required=False, description="In seconds, maximum possible time between spawns (leave both empty to reset)")):
    global terminate_queue, update_queue
    # terminate and update queues indicate the loops to do stuff when they are done with waiting

    if int(message.channel.id) not in db["summon_ids"]:
        await message.response.send_message("This channel isnt setupped. Please select a valid channel.", ephemeral=True)
        return

    if not minimum_time and not maximum_time:
        # reset
        if str(message.channel.id) in terminate_queue:
            await message.response.send_message("You already reset the timings here recently. To prevent weird behaviour, please wait before doing this again.")
            return
        terminate_queue.append(str(message.channel.id))
        try:
            del db["spawn_times"][str(message.channel.id)]
            del db["recovery_times"][str(message.channel.id)]
        except:
            await message.response.send_message("This channel already has default spawning intervals.")
            return
        save("spawn_times")
        save("recovery_times")
        await message.response.send_message("Success! This channel is now reset back to usual spawning intervals.")
    elif minimum_time and maximum_time:
        if minimum_time < 20:
            await message.response.send_message("Sorry, but minimum time must be above 20 seconds.", ephemeral=True)
            return
        if maximum_time <= minimum_time:
            await message.response.send_message("Sorry, but minimum time must be less than maximum time.", ephemeral=True)
            return

        # create a custom loop if it wasnt already created
        if str(message.channel.id) not in db["spawn_times"].keys():
            do_spawn = True
        else:
            do_spawn = False
            update_queue.append(str(message.channel.id))

        db["spawn_times"][str(message.channel.id)] = [minimum_time, maximum_time]
        save("spawn_times")

        if do_spawn:
            bot.loop.create_task(spawning_loop([minimum_time, maximum_time], message.channel.id))

        await message.response.send_message(f"Success! The next spawn will be {minimum_time} to {maximum_time} seconds from now.")
    else:
        await message.response.send_message("Please input all times.", ephemeral=True)


@bot.slash_command(description="(ADMIN) Change the cat appear and cought messages", default_member_permissions=32)
async def changemessage(message: discord.Interaction):
    caller = message.user

    # this is the silly popup when you click the button
    class InputModal(discord.ui.Modal):
        def __init__(self, type):
            super().__init__(
                f"Change {type} Message",
                timeout=600,
            )

            self.type = type

            self.input = discord.ui.TextInput(
                min_length=0,
                max_length=1000,
                label="Input",
                style=discord.TextInputStyle.paragraph,
                required=False,
                placeholder="{emoji} {type} has appeared! Type \"cat\" to catch it!",
                default_value=db[str(message.guild.id)][self.type.lower()]
            )
            self.add_item(self.input)

        async def callback(self, interaction: discord.Interaction):
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
                icon = get_emoji("staring_cat")
                await interaction.response.send_message("Success! Here is a preview:\n" + \
                                                    input_value.format(emoji=icon, type="Example", username="Cat Bot", count="1", time="69 years 420 days"))
            else:
                await interaction.response.send_message("Reset to defaults.")
            db[str(message.guild.id)][self.type.lower()] = input_value
            save(message.guild.id)

    # helper to make the above popup appear
    async def ask_appear(interaction):
        nonlocal caller

        try:
            if db[str(message.guild.id)]["appear"]:
                pass
        except Exception:
            db[str(message.guild.id)]["appear"] = ""
        
        if interaction.user != caller:
            await interaction.response.send_message(choice(funny), ephemeral=True)
            return
        modal = InputModal("Appear")
        await interaction.response.send_modal(modal)

    async def ask_catch(interaction):
        nonlocal caller
        
        try:
            if db[str(message.guild.id)]["cought"]:
                pass
        except Exception:
            db[str(message.guild.id)]["cought"] = ""
        
        if interaction.user != caller:
            await interaction.response.send_message(choice(funny), ephemeral=True)
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

    view = View(timeout=600)
    view.add_item(button1)
    view.add_item(button2)

    await message.response.send_message(embed=embed, view=view)

@bot.slash_command(description="Get Daily cats")
async def daily(message: discord.Interaction):
    await message.response.send_message("there is no daily cats why did you even try this")
    await achemb(message, "daily", "send")

@bot.slash_command(description="View when the last cat was caught in this channel")
async def last(message: discord.Interaction):
    # im gonna be honest i dont know what im doing
    try:
        lasttime = db["lastcatches"][str(message.channel.id)]
        displayedtime = f"<t:{int(lasttime)}:R>"
    except KeyError:
        displayedtime = "forever ago"
    await message.response.send_message(f"the last cat in this channel was caught {displayedtime}.")

@bot.slash_command(description="View your inventory")
async def inventory(message: discord.Interaction, person_id: Optional[discord.Member] = discord.SlashOption(required=False, name="user", description="Person to view the inventory of!")):
    # UGGHHH GOOD LUCK

    # check if we are viewing our own inv or some other person
    if person_id is None:
        me = True
        person_id = message.user
    else:
        me = False
    await message.response.defer()

    register_member(message.guild.id, person_id.id)
    has_ach(message.guild.id, person_id.id, "test_ach") # why is this here? im not sure and im too scared to remove this

    # around here we count aches
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

    # now we count time i think
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

    # check if we have any customs
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

    # for every cat
    for i in cattypes:
        icon = get_emoji(i.lower() + "cat")
        try:
            cat_num = db_var_two_electric_boogaloo[i]
        except KeyError:
            db[str(message.guild.id)][str(person_id.id)][i] = 0
            cat_num = 0
            do_save = True
        if isinstance(cat_num, float):
            # if we somehow got fractional cats, round them back to normal
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
        icon = get_emoji(custom.lower() + "cat")
        embedVar.add_field(name=f"{icon} {custom}", value=1, inline=True)
    
    if is_empty and not custom:
        embedVar.add_field(name="None", value=f"u hav no cats {get_emoji('cat_cry')}", inline=True)
    
    if do_save:
        save(message.guild.id)
    
    embedVar.set_footer(text=f"Total cats: {total}")
    await message.followup.send(embed=embedVar)
    
    if me:
        # give some aches if we are vieweing our own inventory
        if give_collector: await achemb(message, "collecter", "send")
        if get_time(message.guild.id, message.user.id) <= 5: await achemb(message, "fast_catcher", "send")
        if get_time(message.guild.id, message.user.id, "slow") >= 3600: await achemb(message, "slow_catcher", "send")

@bot.slash_command(description="I like fortnite")
async def battlepass(message: discord.Interaction):
    await message.response.defer()
    
    register_member(message.user.id, message.guild.id)

    # set the battlepass variables if they arent real already
    if not get_cat(message.guild.id, message.user.id, "battlepass"):
        db[str(message.guild.id)][str(message.user.id)]["battlepass"] = 0
    
    if not get_cat(message.guild.id, message.user.id, "progress"):
        db[str(message.guild.id)][str(message.user.id)]["progress"] = 0

    current_level = get_cat(message.guild.id, message.user.id, "battlepass")
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
        current = "⬛"
    if current_level != 0:
        embedVar.add_field(name=f"✅ Level {current_level} (complete)", value=battlelevel(battle, current_level - 1), inline=False)
    embedVar.add_field(name=f"{current} Level {current_level + 1}", value=battlelevel(battle, current_level, True), inline=False)
    embedVar.add_field(name=f"Level {current_level + 2}", value=battlelevel(battle, current_level + 1), inline=False)

    await message.followup.send(embed=embedVar)

@bot.slash_command(description="Pong")
async def ping(message: discord.Interaction):
    await message.response.defer()
    try:
        latency = round(bot.latency * 1000)
    except OverflowError:
        latency = "infinite"
    await message.followup.send(f"cat has brain delay of {latency} ms " + str(get_emoji("staring_cat")))

@bot.slash_command(description="give cats now")
async def gift(message: discord.Interaction, \
                 person: discord.Member = discord.SlashOption(description="Whom to donate?"), \
                 cat_type: str = discord.SlashOption(choices=cattypes, name="type", description="Select a donate cat type"), \
                 amount: Optional[int] = discord.SlashOption(required=False, description="And how much?")):
    if not amount: amount = 1  # default the amount to 1
    person_id = person.id

    # if we even have enough cats
    if get_cat(message.guild.id, message.user.id, cat_type) >= amount and amount > 0 and message.user.id != person_id:
        remove_cat(message.guild.id, message.user.id, cat_type, amount)
        add_cat(message.guild.id, person_id, cat_type, amount)
        embed = discord.Embed(title="Success!", description=f"Successfully transfered {amount} {cat_type} cats from <@{message.user.id}> to <@{person_id}>!", color=0x6E593C)
        await message.response.send_message(embed=embed)

        # handle aches
        await achemb(message, "donator", "send")
        await achemb(message, "anti_donator", "send", person)
        if person_id == bot.user.id and cat_type == "Ultimate" and int(amount) >= 5: await achemb(message, "rich", "send")

        # handle tax
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

            myview = View(timeout=600)

            myview.add_item(button)
            myview.add_item(button2)
            await message.channel.send(embed=embed, view=myview)
    else:
        # haha skill issue
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

    # do the funny
    if person2.id == bot.user.id:
        person2gives = {"eGirl": 9999999}

    # this is the deny button code
    async def denyb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole
        if interaction.user != person1 and interaction.user != person2:
            await interaction.response.send_message(choice(funny), ephemeral=True)
            return
        
        blackhole = True
        person1gives = {}
        person2gives = {}
        await interaction.message.edit(f"<@{interaction.user.id}> has cancelled the trade.", embed=None, view=None)

    # this is the accept button code
    async def acceptb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
        if interaction.user != person1 and interaction.user != person2:
            await interaction.response.send_message(choice(funny), ephemeral=True)
            return
        # clicking accept again would make you un-accept
        if interaction.user == person1:
            person1accept = not person1accept
        elif interaction.user == person2:
            person2accept = not person2accept
        
        await interaction.response.defer()
        await update_trade_embed(interaction)
            
        if person1accept and person2accept:
            error = False
            # check if we have enough cats (person could have moved them during the trade)
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

            # exchange cats
            for k, v in person1gives.items():
                remove_cat(interaction.guild.id, person1.id, k, v)
                add_cat(interaction.guild.id, person2.id, k, v)
                
            for k, v in person2gives.items():
                remove_cat(interaction.guild.id, person2.id, k, v)
                add_cat(interaction.guild.id, person1.id, k, v)

            await interaction.message.edit(f"Trade finished!", view=None)
            await achemb(message, "extrovert", "send")
            await achemb(message, "extrovert", "send", person2)

    # add cat code
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
        # all we really do is spawn the modal
        await handle_modal(currentuser, interaction)
                
    async def handle_modal(currentuser, interaction):
        # not sure why i needed this helper that badly but oh well
        modal = TradeModal(currentuser)
        await interaction.response.send_modal(modal)

    # this is ran like everywhere when you do anything
    # it updates the embed
    async def gen_embed():
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole
        
        if blackhole:
            # no way thats fun
            await achemb(message, "blackhole", "send")
            await achemb(message, "blackhole", "send", person2)
            return discord.Embed(color=0x6E593C, title=f"Blackhole", description="How Did We Get Here?"), None
        
        view = View(timeout=600)
    
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

        # a single field for one person
        def field(personaccept, persongives, person):
            nonlocal coolembed
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
            coolembed.add_field(name=f"{icon} {person.name}", inline=True, value=valuestr)
        
        field(person1accept, person1gives, person1)
        field(person2accept, person2gives, person2)
        
        return coolembed, view
    
    embed, view = await gen_embed()
    await message.response.send_message(embed=embed, view=view)

    # this is wrapper around gen_embed() to edit the mesage automatically
    async def update_trade_embed(interaction):
        embed, view = await gen_embed()
        await interaction.message.edit(embed=embed, view=view)

    # lets go add cats modal thats fun
    class TradeModal(discord.ui.Modal):
        def __init__(self, currentuser):
            super().__init__(
                "Add cats to the trade",
                timeout=600,  # 5 minutes
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
        async def callback(self, interaction: discord.Interaction):
            nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
            # hella ton of checks
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

            # OKE SEEMS GOOD LETS ADD CATS TO THE TRADE
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
                        
@bot.slash_command(description="Get a random cat")
async def random(message: discord.Interaction):
    await message.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('https://api.thecatapi.com/v1/images/search', timeout=15) as response:
                data = await response.json()
                await message.followup.send(data[0]['url'])
                await achemb(message, "randomizer", "send")
        except Exception:
            await message.followup.send("no cats :(")

async def dark_market(message):
    cataine_prices = [[10, "Fine"], [30, "Fine"], [20, "Good"], [15, "Rare"], [20, "Wild"], [10, "Epic"], [20, "Sus"], [15, "Rickroll"],
                      [7, "Superior"], [5, "Legendary"], [3, "8bit"], [4, "Professor"], [3, "Real"], [2, "Ultimate"], [1, "eGirl"], [100, "eGirl"]]

    if get_cat(message.guild.id, message.user.id, "cataine_active") < int(time.time()):
        level = get_cat(message.guild.id, message.user.id, "dark_market_level")
        embed = discord.Embed(title="The Dark Market", description="after entering the secret code, they let you in. today's deal is:")
        deal = cataine_prices[level]
        type = deal[1]
        amount = deal[0]
        embed.add_field(name="🧂 12h of Cataine", value=f"Price: {get_emoji(type.lower() + 'cat')} {amount} {type}")

        async def buy_cataine(interaction):
            nonlocal message, type, amount
            if get_cat(message.guild.id, message.user.id, type) < amount or get_cat(message.guild.id, message.user.id, "cataine_active") != 0:
                return
            remove_cat(message.guild.id, message.user.id, type, amount)
            add_cat(message.guild.id, message.user.id, "cataine_active", int(time.time()) + 43200)
            add_cat(message.guild.id, message.user.id, "dark_market_level")
            await interaction.response.send_message("Thanks for buying! Your cat catches will be doubled for the next 12 hours.", ephemeral=True)

        debounce = False

        async def complain(interaction):
            nonlocal debounce
            if debounce: return
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
                       f"*Uh oh.*"]
            
            await interaction.response.send_message("*That's not funny anymore. Those prices are insane.*", ephemeral=True)
            await asyncio.sleep(5)
            for i in phrases:
                await interaction.followup.send(i, ephemeral=True)
                await asyncio.sleep(5)

            # there is actually no time pressure anywhere but try to imagine there is
            counter = 0
            async def step(interaction2):
                nonlocal counter
                counter += 1
                await interaction2.response.defer()
                if counter == 30:
                    await interaction2.edit_original_message(view=None)
                    await asyncio.sleep(5)
                    await interaction2.followup.send("You barely manage to turn around a corner and hide to run away.", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction2.followup.send("You quietly get to the police station and tell them everything.", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction2.followup.send("## The next day.", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction2.followup.send("A nice day outside. You open the news:", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction2.followup.send("*Dog Mafia, the biggest cataine distributor, was finally caught after anonymous report.*", ephemeral=True)
                    await asyncio.sleep(5)
                    await interaction2.followup.send("HUH? It was dogs all along...", ephemeral=True)
                    await asyncio.sleep(5)
                    await achemb(interaction, "thanksforplaying", "send")
                    add_cat(interaction.guild.id, interaction.user.id, "story_complete")
                    
            run_view = View(timeout=600)
            button = Button(label="RUN", style=ButtonStyle.green)
            button.callback = step
            run_view.add_item(button)
            
            await interaction.followup.send("RUN!\nSpam the button a lot of times as fast as possible to run away!", view=run_view, ephemeral=True)
            
        
        myview = View(timeout=600)
        
        if level == len(cataine_prices) - 1:
            button = Button(label="What???", style=ButtonStyle.red)
            button.callback = complain
        else:
            if get_cat(message.guild.id, message.user.id, type) >= amount:
                button = Button(label="Buy", style=ButtonStyle.blurple)
            else:
                button = Button(label="You don't have enough cats!", style=ButtonStyle.gray, disabled=True)
            button.callback = buy_cataine
        myview.add_item(button)

        await message.followup.send(embed=embed, view=myview, ephemeral=True)
    else:
        embed = discord.Embed(title="The Dark Market", description=f"you already bought from us recently. you can do next purchase <t:{get_cat(message.guild.id, message.user.id, 'cataine_active')}:R>.")
        await message.followup.send(embed=embed, ephemeral=True)

@bot.slash_command(description="View your achievements")
async def achievements(message: discord.Interaction):
    # this is very close to /inv's ach counter
    register_member(message.guild.id, message.user.id)
    has_ach(message.guild.id, message.user.id, "test_ach") # and there is this cursed line again wtf
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

    hidden_counter = 0
    # this is a single page of the achievement list
    def gen_new(category):
        nonlocal db_var, message, unlocked, total_achs, hidden_counter
        hidden_suffix = ""
        if category == "Hidden":
            hidden_suffix = "\n\nThis is a \"Hidden\" category. Achievements here only show up after you complete them."
            hidden_counter += 1
        else:
            hidden_counter = 0
        newembed = discord.Embed(
                title=category, description=f"Achievements unlocked (total): {unlocked}/{total_achs}{minus_achs}{hidden_suffix}", color=0x6E593C
        )
        for k, v in ach_list.items():
            if v["category"] == category:
                if k == "thanksforplaying":
                    if has_ach(message.guild.id, message.user.id, k, False, db_var):
                        newembed.add_field(name=str(get_emoji("demonic")) + " Cataine Addict", value="Defeat the dog mafia", inline=True)
                    else:
                        newembed.add_field(name=str(get_emoji("no_demonic")) + " Thanks For Playing", value="Complete the story", inline=True)
                    continue
                
                icon = str(get_emoji("no_cat_throphy")) + " "
                if has_ach(message.guild.id, message.user.id, k, False, db_var):
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
            await interaction.response.send_message(choice(funny), ephemeral=True)
            await achemb(interaction, "curious", "send")

    # creates buttons at the bottom of the full view
    def insane_view_generator(category):
        myview = View(timeout=600)
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

        async def callback_hell(interaction, thing):
            await interaction.edit(embed=gen_new(thing), view=insane_view_generator(thing))
            
            if hidden_counter == 3 and get_cat(message.guild.id, message.user.id, "dark_market") and get_cat(message.guild.id, message.user.id, "story_complete") != 1:
                # open the totally not suspicious dark market
                await dark_market(message)
        
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

        if category == "Unfair":
            buttons_list.append(Button(label="Unfair", style=ButtonStyle.green))
        else:
            buttons_list.append(Button(label="Unfair", style=ButtonStyle.blurple))
        lambdas_list.append(lambda interaction : (await callback_hell(interaction, "Unfair") for _ in '_').__anext__())
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

    myview = View(timeout=600)
    myview.add_item(button)

    await message.response.send_message(embed=embedVar, view=myview)
            
@bot.message_command(name="catch")
async def catch(message: discord.Interaction, msg):
    await message.response.defer()
    msg2img.msg2img(msg, bot, True)
    file = discord.File("generated.png", filename="generated.png")
    await message.followup.send("cought in 4k", file=file)
    register_member(message.guild.id, msg.author.id)
    if msg.author.id != bot.user.id: await achemb(message, "4k", "send")

@bot.message_command()
async def pointLaugh(message: discord.Interaction, msg):
    icon = get_emoji("pointlaugh")
    await msg.add_reaction(icon)
    await message.response.send_message(icon, ephemeral=True)

@bot.slash_command(description="View the leaderboards")
async def leaderboards(message: discord.Interaction, leaderboard_type: Optional[str] = discord.SlashOption(name="type", description="The leaderboard type to view!", choices=["Cats", "Fastest", "Slowest"], required=False)):
    if not leaderboard_type: leaderboard_type = "Cats"

    # this fat function handles a single page
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
            try:
                int(i)
            except Exception:
                continue
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
                # round the value (for time dislays)
                thingy = round((value / devider) * 100) / 100
                
                # if it perfectly ends on .00, trim it
                if thingy == int(thingy):
                    thingy = int(thingy)
                
                the_dict[f" {unit}: <@" + i + ">"] = thingy

        # some weird quick sorting thing (dont you just love when built-in libary you never heard of saves your ass)
        heap = [(-value, key) for key, value in the_dict.items()]
        if fast:
            largest = heapq.nlargest(15, heap)
        else:
            largest = heapq.nsmallest(15, heap)
        largest = [(key, -value) for value, key in largest]
        string = ""

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
            current += 1
        embedVar = discord.Embed(
                title=f"{title} Leaderboards:", description=string, color=0x6E593C
        )

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

        myview = View(timeout=600)
        myview.add_item(button1)
        myview.add_item(button2)
        myview.add_item(button3)

        # just send if first time, otherwise edit existing
        if do_edit:
            await interaction.edit(embed=embedVar, view=myview)
        else:
            await interaction.followup.send(embed=embedVar, view=myview)

    # helpers! everybody loves helpers.
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

@bot.slash_command(description="(ADMIN) Setup cat in current channel", default_member_permissions=32)
async def setup(message: discord.Interaction):
    register_guild(message.guild.id)
    if int(message.channel.id) in db["summon_ids"]:
        await message.response.send_message("bruh you already setup cat here are you dumb\n\nthere might already be a cat sitting in chat. type `cat` to catch it.\nalternatively, you can try `/repair` if it still doesnt work")
        return
    # we just set a lot of variables nothing to see here
    abc = db["summon_ids"]
    abc.append(int(message.channel.id))
    db["summon_ids"] = abc
    try:
        del db["spawn_times"][str(message.channel.id)]
        save("spawn_times")
    except Exception:
         pass
    db["cat"][str(message.channel.id)] = False
    fire[str(message.channel.id)] = True
    save("summon_ids")
    save("cat")
    await soft_force(message.channel) # force the first cat spawn incase something isnt working
    await message.response.send_message(f"ok, now i will also send cats in <#{message.channel.id}>")

@bot.slash_command(description="(ADMIN) Undo the setup", default_member_permissions=32)
async def forget(message: discord.Interaction):
    if int(message.channel.id) in db["summon_ids"]:
        abc = db["summon_ids"]
        abc.remove(int(message.channel.id))
        db["summon_ids"] = abc
        del db["cat"][str(message.channel.id)]
        save("summon_ids")
        save("cat")
        await message.response.send_message(f"ok, now i wont send cats in <#{message.channel.id}>")
    else:
        await message.response.send_message("your an idiot there is literally no cat setupped in this channel you stupid")

@bot.slash_command(description="LMAO TROLLED SO HARD :JOY:")
async def fake(message: discord.Interaction):
    file = discord.File("australian cat.png", filename="australian cat.png")
    icon = get_emoji("egirlcat")
    await message.channel.send(str(icon) + " eGirl cat hasn't appeared! Type \"cat\" to catch ratio!", file=file)
    await message.response.send_message("OMG TROLLED SO HARD LMAOOOO 😂", ephemeral=True)
    await achemb(message, "trolled", "followup")

async def soft_force(channeley, cat_type=None):
    # this is common called between /forcespawn and /setup
    fire[channeley.id] = False
    file = discord.File("cat.png", filename="cat.png")
    if not cat_type:
        localcat = choice(CAT_TYPES)
    else:
        localcat = cat_type
    icon = get_emoji(localcat.lower() + "cat")
    try:
        if db[str(channeley.guild.id)]["appear"]:
            appearstring = db[str(channeley.guild.id)]["appear"]
        else:
            appearstring = "{emoji} {type} cat has appeared! Type \"cat\" to catch it!"
    except Exception as e:
        db[str(channeley.guild.id)]["appear"] = ""
        appearstring = "{emoji} {type} cat has appeared! Type \"cat\" to catch it!"
    
    message_is_sus = await channeley.send(appearstring.format(emoji=str(icon), type=localcat), file=file)
    db["cat"][str(channeley.id)] = message_is_sus.id
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

    if valid and ach_id == "thanksforplaying":
        await message.response.send_message("HAHAHHAHAH\nno", ephemeral=True)
        return
                      
    if valid:
        # if it is, do the thing
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

# this is the crash handler
@bot.event
async def on_application_command_error(ctx, error):
    def in_error(x):
        return bool(x in str(type(error)) or x in str(error))

    if ctx.guild == None:
        await ctx.channel.send("hello good sir i would politely let you know cat bot is no workey in dms please consider gettng the hell out of here")
        return
    
    # ctx here is interaction
    normal_crash = False
    if in_error("KeyboardInterrupt"): # keyboard interrupt
        sys.exit()
    elif in_error("Forbidden"):
        # forbidden error usually means we dont have permission to send messages in the channel
        print("logged a Forbidden error.")
        # except-ception lessgo
        forbidden_error = "i don't have permissions to do that.\ntry reinviting the bot or give it roles needed to access this chat (for example, verified role)"
        try:
            await ctx.channel.send(forbidden_error) # try as normal message (most likely will fail)
        except Exception:
            try:
                await ctx.response.send_message(forbidden_error) # try to respond to /command literally
            except Exception:
                try:
                    await ctx.followup.send(forbidden_error) # or as a followup if it already got responded to
                except Exception:
                    try:
                        await ctx.user.send(forbidden_error) # as last resort, dm the runner
                    except Exception:
                        pass # give up
    elif in_error("NotFound"):
        # discord just pretends if interaction took more than 3 seconds it never happened and its annoying af
        print("logged a NotFound error.")
        await ctx.channel.send("took too long, try running the command again")
    else:
        print("not a common error, crash reporting.")
        normal_crash = True
        await ctx.channel.send("cat crashed lmao\ni automatically sent crash reports so yes")
        # give the ach! (or atleast try)
        try:
            await achemb(ctx, "crasher", "send")
        except Exception:
            pass

    # try to get some context maybe if we get lucky
    try:
        cont = ctx.guild.id
        print("debug", cont)
    except Exception as e:
        cont = "Error getting"

    error2 = error.original.__traceback__

    # if actually interesting crash, dm to bot owner
    if normal_crash:
        await milenakoos.send(
                "There is an error happend:\n"
                + str("".join(traceback.format_tb(error2))) + str(type(error).__name__) + str(error)
                + "\n\nMessage guild: "
                + cont
        )
    else:
        # otherwise log to console
        print(str("".join(traceback.format_tb(error2))) + str(type(error).__name__) + str(error))

# run the bot!
bot.run(TOKEN)
