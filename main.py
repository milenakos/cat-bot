import nextcord as discord
import msg2img, base64, sys, re, time, json, requests, natsort, traceback, os
from nextcord.ext import tasks, commands
from nextcord import ButtonStyle
from nextcord.ui import Button, View
from typing import Optional
from random import randint, choice

OWNER_ID = 553093932012011520 # for dms
GUILD_ID = 966586000417619998 # for emojis
BOT_ID = 966695034340663367

TOKEN = os.environ['token']
# TOKEN = "token goes here"

with open("db.json", "r") as f:
	try:
		db = json.load(f)
	except Exception:
		f.close()
		import reverse
		reverse.reverse()
		with open("db.json", "r") as f:
			db = json.load(f)

f = open("aches.json", "r")
ach_list = json.load(f)
f.close()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="idk how this works but you need to have spaces in it or it may crash", intents=intents)

cattypes = ["Fine", "Nice", "Good", "Rare", "Wild", "Baby", "Epic", "Sus", "Brave", "Rickroll", "Reverse", "Superior", "TheTrashCell", "Legendary", "Mythic", "8bit", "Corrupt", "Professor", "Divine", "Real", "Ultimate", "eGirl"]

summon_id = db["summon_ids"]

delays = [120, 1200]

timeout = 0
starting_time = 0
message_thing = 0

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
	except Exception:
		if type == "":
			add_cat(server_id, person_id, "time", 99999999999999)
			result = 99999999999999
		else:
			add_cat(server_id, person_id, "time" + type, 0)
			result = 0
		save()
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
	global super_prefix, bot, fire, summon_id, delays
	await bot.change_presence(
		activity=discord.Activity(type=discord.ActivityType.playing, name=f"/help | Providing life support for {len(bot.guilds)} servers")
	)
	summon_id = db["summon_ids"]
	myLoop.change_interval(seconds = randint(delays[0], delays[1]))
	for i in summon_id:
		try:
			if fire[i]:
				if not db["cat"][str(i)]:
					file = discord.File("cat.png", filename="cat.png")
					cat_types = (
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
	
					localcat = choice(cat_types)
					db["cattype"][str(i)] = localcat
					icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=localcat.lower()+"cat")   
					channeley = await bot.fetch_channel(int(i))
					message_is_sus = await channeley.send(super_prefix + str(icon) + " " + db["cattype"][str(i)] + " cat has appeared! Type \"cat\" to catch it!", file=file)
					db["cat"][str(i)] = message_is_sus.id
					save()
			if not fire[i]:
				fire[i] = True
		except Exception as e:
			print("summon", e)
	super_prefix = ""

@bot.event
async def on_ready():
	await bot.change_presence(
		activity=discord.Activity(type=discord.ActivityType.playing, name=f"/help | Providing life support for {len(bot.guilds)} servers")
	)
	myLoop.start()

@bot.event
async def on_message(message):
	global fire, summon_id, delays
	text = message.content
	if message.author.id == bot.user.id:
		return
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
	if re.search("ce[lI]{2}ua bad", text.lower()) and not has_ach(message.guild.id, message.author.id, "cellua"):
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
	if ("@Cat Bot#9575" in text or f"<@{BOT_ID}>" in text or f"<@!{BOT_ID}>" in text) and not has_ach(message.guild.id, message.author.id, "who_ping"):
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
		await message.reply(f"ok then\n{safe}#{str(message.author.discriminator)} lost 1 fine cat!!!1!")
		remove_cat(message.guild.id, message.author.id, "Fine")
		if not has_ach(message.guild.id, message.author.id, "pleasedonotthecat"):
			ach_data = give_ach(message.guild.id, message.author.id, "pleasedonotthecat")
			embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
			await message.reply(embed=embed)
	if text.lower() == "please do the cat":
		thing = discord.File("socialcredit.jpg", filename="socialcredit.jpg")
		await message.reply(file=thing)
	if text.lower() == "dog" and not has_ach(message.guild.id, message.author.id, "not_quite"):
		ach_data = give_ach(message.guild.id, message.author.id, "not_quite")
		embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
		await message.reply(embed=embed)
	if text.lower() == "ach" and not has_ach(message.guild.id, message.author.id, "test_ach"):
		ach_data = give_ach(message.guild.id, message.author.id, "test_ach")
		embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
		await message.reply(embed=embed)
	if text.lower() == "cat":
		try:
			is_cat = db["cat"][str(message.channel.id)]
		except Exception:
			is_cat = False
		if not is_cat:
			icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="pointlaugh")
			await message.add_reaction(icon)
		elif is_cat:
			current_time = time.time()
			register_member(message.guild.id, message.author.id)
			cat_temp = db["cat"][str(message.channel.id)]
			db["cat"][str(message.channel.id)] = False
			save()
			await message.delete()
			try:
				var = await message.channel.fetch_message(cat_temp)
				catchtime = var.created_at
				super_prefix_redux = var.content.split("\n")[0]
				await var.delete()
				
				if "cat has appeared! Type \"cat\" to catch it!" in super_prefix_redux:
					super_prefix_redux = ""
				else:
					super_prefix_redux += "\n"

				time_caught = (round((current_time - time.mktime(catchtime.timetuple())) * 100) / 100)
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
			except Exception:
				do_time = False
				caught_time = "undefined amounts of time "
				pass
			
			le_emoji = db["cattype"][str(message.channel.id)]
			icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=le_emoji.lower()+"cat")
			await message.channel.send(message.author.name.replace("@", "`@`") + "#" + str(message.author.discriminator) + " cought " + str(icon) + " " + db["cattype"][str(message.channel.id)] + " cat!!!!1!\nYou now have " + str(add_cat(message.guild.id, message.author.id, db["cattype"][str(message.channel.id)])) + " cats of dat type!!!\nthis fella was cought in " + caught_time[:-1] + "!!!!")
			if do_time and time_caught < get_time(message.guild.id, message.author.id):
				set_time(message.guild.id, message.author.id, time_caught)
			if do_time and time_caught > get_time(message.guild.id, message.author.id, "slow"):
				set_time(message.guild.id, message.author.id, time_caught, "slow")
			
			if do_time and not has_ach(message.guild.id, message.author.id, "fast_catcher") and get_time(message.guild.id, message.author.id) <= 5:
				ach_data = give_ach(message.guild.id, message.author.id, "fast_catcher")
				embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
				await message.channel.send(embed=embed)
			
			if do_time and not has_ach(message.guild.id, message.author.id, "slow_catcher") and get_time(message.guild.id, message.author.id, "slow") >= 3600:
				ach_data = give_ach(message.guild.id, message.author.id, "slow_catcher")
				embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
				await message.channel.send(embed=embed)
	if text.lower().startswith("cat!beggar") and message.author.id == OWNER_ID:
		give_ach(message.guild.id, int(text[10:].split(" ")[1]), text[10:].split(" ")[2])
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
	if text.lower().startswith("indev2"):
		await message.reply(":frog:")
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
		value="**/random** - get random cat image\n**right click > apps > catch** - catch someone in 4k\n**/tiktok** - read message as tiktok woman tts\n**/help** - this command\n**/admin** - help for server admins\n**/cat** - get staring cat image\n**/info** - get info bout bot and credits",
	)
	await message.response.send_message(embed=embedVar)

@bot.slash_command(description="Give feedback, report bugs or suggest ideas")
async def feedback(message: discord.Interaction, feedback: str):
	if len(str(message.user) + "\n" + feedback) >= 2000:
		await message.response.send_message("ah hell nah man, ur msg is too long :skull:", ephemeral=True)
		return
	milenakoos = await bot.fetch_user(OWNER_ID)
	await milenakoos.send(str(message.user) + "\n" + feedback)
	await message.response.send_message("your feedback was directed to the bot owner!", ephemeral=True)

@bot.slash_command(description="View admin help", default_member_permissions=8)
async def admin(message: discord.Interaction):
	embedVar = discord.Embed(
		title="Send Admin Help", description=discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="staring_cat"), color=0x6E593C
	).add_field(name="Admin Commands", value="**/setup** - makes cat bot send cats in the channel this command is ran in\n**/forget** - reverse of /setup (i forgor :skull:)\n**/summon** - makes cats disappear and reappear out of thin air\n**/giveach** - gib (or take) achievements to people\n**/force** - makes cat appear in chat\n**/say** - chat as cat\n**/reset** - fully resets one's account")
	await message.response.send_message(embed=embedVar)

@bot.slash_command(description="View information about the bot")
async def info(message: discord.Interaction):
	embedVar = discord.Embed(title="Cat Bot", color=0x6E593C, description="Bot made by Milenakos#3310\nThis bot adds Cat Hunt to your server with many different types of cats for people to discover! People can see leaderboards and give cats to each other.\n\nThanks to:\n**???** for the cat image\n**SLOTHS2005#1326** for getting troh to add cat as an emoji\n**aws.random.cat** for random cats API\n**@weilbyte on GitHub** for TikTok TTS API\n**TheTrashCell#0001** for making cat, suggestions, and a lot more.\n\n**CrazyDiamond469#3422, Phace#9474, SLOTHS2005#1326, frinkifail#1809, Aflyde#3846, TheTrashCell#0001 and Sior Simotideis#4198** for being test monkeys\n\n**And everyone for the support!**")
	await message.response.send_message(embed=embedVar)

@bot.slash_command(description="Read text as TikTok's TTS woman")
async def tiktok(message: discord.Interaction, text: str):
	stuff = requests.post("https://tiktok-tts.weilnet.workers.dev/api/generation", headers={"Content-Type": "application/json"}, json={"text": text, "voice": "en_us_002"})
	try:
		data = "" + stuff.json()["data"]
	except TypeError:
		await message.response.send_message("i dont speak your language (remove non-english characters)", ephemeral=True)
		return
	with open("result.mp3", "wb") as f:
		ba = "data:audio/mpeg;base64," + data
		f.write(base64.b64decode(ba))
	file = discord.File("result.mp3", filename="result.mp3")
	await message.response.send_message(file=file)

@tasks.loop(seconds = 1)
async def spawn_cat():
	global message_thing, timeout, starting_time
	if time.time() - starting_time <= timeout:
		fire[message_thing.channel.id] = False
		if not db["cat"][str(message_thing.channel.id)]:
			file = discord.File("cat.png", filename="cat.png")
			cat_types = (
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

			localcat = choice(cat_types)
			db["cattype"][str(message_thing.channel.id)] = localcat
			icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=localcat.lower()+"cat")   
			message_is_sus = await message_thing.channel.send(str(icon) + " " + db["cattype"][str(message_thing.channel.id)] + " cat has appeared! Type \"cat\" to catch it!", file=file)
			db["cat"][str(message_thing.channel.id)] = message_is_sus.id
			save()
	else:
		await message_thing.channel.send("this concludes the cat rain.")
		spawn_cat.close()

@bot.slash_command(description="Get Daily cats")
async def daily(message: discord.Interaction):
	await message.response.send_message("there is no daily cats why did you even try this")
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
	for k in ach_list.keys():
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
	slow_time = get_time(message.guild.id, person_id.id, "slow")
	if str(slow_time) == "0":
		slow_time = "never"
	else:
		slow_time = slow_time / 3600
		slow_time = str(round(slow_time * 100) / 100)
		
	if me:
		your = "Your"
	else:
		your = person_id.name + "'s"

	embedVar = discord.Embed(
		title=your + " cats:", description=f"{your} fastest catch is: {catch_time} s\nand {your} slowest catch is: {slow_time} h\nAchievements unlocked: {unlocked}/{total_achs} + {minus_achs}", color=0x6E593C
	)
	give_collector = True
	do_save = False
	db_var_two_electric_boogaloo = db[str(message.guild.id)][str(person_id.id)]
	for i in cattypes:
		icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=i.lower()+"cat")
		try:
			cat_num = db_var_two_electric_boogaloo[i]
		except KeyError:
			db[str(message.guild.id)][str(person_id.id)][i] = 0
			cat_num = 0
			do_save = True
		if cat_num != 0:
			embedVar.add_field(name=f"{icon} {i}", value=cat_num, inline=True)
			is_empty = False
		if cat_num <= 0:
			give_collector = False
	if is_empty:
		embedVar.add_field(name="None", value="u hav no cats :cat_sad:", inline=True)
	if do_save:
		save()
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

@bot.slash_command(description="View list of achievements names", default_member_permissions=8)
async def achlist(message: discord.Interaction):
	stringy = ""
	for k,v in ach_list.items():
		stringy = stringy + k + " - " + v["title"] + "\n"
	embed = discord.Embed(title="Ach IDs", description=stringy, color=0x6E593C)
	await message.response.send_message(embed=embed)

@bot.slash_command(description="Pong")
async def ping(message: discord.Interaction):
	await message.response.send_message(f"cat has brain delay of {round(bot.latency * 1000)} ms " + str(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="staring_cat")))

@bot.slash_command(description="give cats now")
async def donate(message: discord.Interaction, person: discord.Member, cat_type: str = discord.SlashOption(choices=cattypes), amount: Optional[int] = discord.SlashOption(required=False)):
	if not amount: amount = 1
	person_id = person.id
	if get_cat(message.guild.id, message.user.id, cat_type) >= amount and amount > 0:
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
			await message.channel.send(embed=embed.set_footer(text="unlocked by "+person.name+", not you"))
		if not has_ach(message.guild.id, message.user.id, "rich") and person_id == BOT_ID and cat_type == "Ultimate" and int(amount) >= 5:
			ach_data = give_ach(message.guild.id, message.user.id, "rich")
			embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
			await message.response.send_message(embed=embed)
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

@bot.slash_command(description="Get Your balance")
async def bal(message: discord.Interaction):
	file = discord.File("money.png", filename="money.png")
	embed = discord.Embed(title="cat coins", color=0x6E593C).set_image(url="attachment://money.png")
	await message.response.send_message(file=file, embed=embed)

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
	for k in ach_list.keys():
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
				icon = str(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="no_cat_throphy"))	 + " "
				if has_ach(message.guild.id, message.user.id, k, False, db_var):
					newembed.add_field(name=str(discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="cat_throphy"))+" "+v["title"], value=v["description"], inline=True)
				elif category != "Hidden":
					if v["is_hidden"]:
						newembed.add_field(name=icon+v["title"], value="???", inline=True)
					else:
						newembed.add_field(name=icon+v["title"], value=v["description"], inline=True)
		
		return newembed
	
	async def send_full(interaction):
		nonlocal message
		if interaction.user.id == message.user.id:
			await interaction.response.send_message(embed=gen_new("Cat Hunt"), ephemeral=True, view=insane_view_generator("Cat Hunt"))
		else:
			funny = ["why did you click this this arent yours", "absolutely not", "cat bot not responding, try again later", "you cant", "can you please stop", "try again", "403 not allowed", "stop", "get a life"]
			await interaction.response.send_message(choice(funny), ephemeral=True)
			if not has_ach(message.guild.id, interaction.user.id, "curious"):
				ach_data = give_ach(message.guild.id, interaction.user.id, "curious")
				embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png").set_footer(text="Proudly unlocked by " + interaction.user.name)
				await message.channel.send(embed=embed)

	def insane_view_generator(category):
		myview = View(timeout=180)
		buttons_list = []
		lambdas_list = []
		
		# would be much more optimized but i cant get this to work
		# for i in ["Cat Hunt", "Random", "Unfair"]:
		#   if category == i:
		#	 buttons_list.append(Button(label=i, style=ButtonStyle.green))
		#   else:
		#	 buttons_list.append(Button(label=i, style=ButtonStyle.blurple))
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

	myview = View(timeout=180)
	myview.add_item(button)
	
	await message.response.send_message(embed=embedVar, view=myview)

@bot.message_command()
async def catch(message: discord.Interaction, msg):
	try:
		msg2img.msg2img(msg, bot)
		file = discord.File("generated.png", filename="generated.png")
		await message.response.send_message("cought in 4k", file=file)
	except Exception:
		await message.response.send_message("the message appears to have commited no live anymore", ephemeral=True)
	register_member(message.guild.id, msg.author.id)
	if not has_ach(message.guild.id, msg.author.id, "4k"):
		ach_data = give_ach(message.guild.id, message.user.id, "4k")
		embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
		await message.channel.send(embed=embed)

@bot.message_command()
async def pointLaugh(message: discord.Interaction, msg):
	icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="pointlaugh")
	await msg.add_reaction(icon)
	await message.response.send_message(icon, ephemeral=True)

@bot.slash_command(description="View the leaderboards")
async def leaderboards(message: discord.Interaction):
    # this needs a bit of a cleanup doesnt it
    
	async def catlb(interaction):
		nonlocal message
		await interaction.response.defer()
		results = []
		rarest = -1
		rarest_holder = [f"<@{BOT_ID}>"]
		rarities = cattypes
		place = 1
		msg_author_msg = 6942069
		register_guild(message.guild.id)
		for i in db[str(message.guild.id)].keys():
			value = 0
			for a, b in db[str(message.guild.id)][i].items():
				if a != "time" and a != "timeslow" and a != "ach":
					try:
						value += b
						if b > 0 and rarities.index(a) > rarest:
							rarest = rarities.index(a)
							rarest_holder = ["<@" + i + ">"]
						elif b > 0 and rarities.index(a) == rarest:
							rarest_holder.append("<@" + i + ">")
					except Exception:
						pass
			if value > 0:
				if str(message.user.id) == str(i):
					msg_author_msg = str(value) + " cats: <@" + i + ">"
				results.append(str(value) + " cats: <@" + i + ">")
			place += 1
		results = natsort.natsorted(results, reverse=True)
		if msg_author_msg != 6942069:
			msg_author_place = results.index(msg_author_msg) + 1
		catmoji = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=rarities[rarest].lower()+"cat")
		if rarest != -1:
			if len(rarest_holder) <= 3:
				joined = ", ".join(rarest_holder)
				string = f"Rarest cat: {catmoji} ({joined}'s)\n"
			else:
				joined = ", ".join(rarest_holder[:3])
				string = f"Rarest cat: {catmoji} ({joined} and others)\n"
		else:
			string = "No one has any cats. Atleast thats my theory. A GAME THE~~~"
		for num, i in enumerate(results[:15]):
			if msg_author_msg != 6942069 and num == msg_author_place - 1:
				string = string + "**" + str(num + 1) + ". " + i + "**\n"
			else:
				string = string + str(num + 1) + ". " + i + "\n"
		if len(results) > 15:
			string = string + "...\n"
		if msg_author_msg != 6942069 and msg_author_place > 15:
			string = string + "**" + str(msg_author_place + 1) + ". " + results[msg_author_place - 1] + "**\n"
		embedVar = discord.Embed(
			title="Leaderboards:", description=string, color=0x6E593C
		).set_footer(text="if two people have same amount of cats, nuke output determines who places above")
		
		button1 = Button(label="Cats", style=ButtonStyle.green)
		button1.callback = catlb
		button1.disabled = True
		
		button2 = Button(label="Fastest", style=ButtonStyle.blurple)
		button2.callback = fastlb
		
		button3 = Button(label="Slowest", style=ButtonStyle.blurple)
		button3.callback = slowlb
				
		myview = View(timeout=180)
		myview.add_item(button1)
		myview.add_item(button2)
		myview.add_item(button3)
							
		await interaction.edit(embed=embedVar, view=myview)

	async def fastlb(interaction):
		nonlocal message
		await interaction.response.defer()
		results = []
		place = 1
		msg_author_msg = 6942069
		register_guild(message.guild.id)
		for i in db[str(message.guild.id)].keys():
			value = get_time(message.guild.id, i)
			if str(value) != "99999999999999":
				if str(message.user.id) == str(i):
					msg_author_msg = str(value) + " sec: <@" + i + ">"
				results.append(str(value) + " sec: <@" + i + ">")
				place += 1
		results = natsort.natsorted(results, reverse=False)
		if msg_author_msg != 6942069:
			msg_author_place = results.index(msg_author_msg) + 1
		string = ""
		for num, i in enumerate(results[:15]):
			if msg_author_msg != 6942069 and num == msg_author_place - 1:
				string = string + "**" + str(num + 1) + ". " + i + "**\n"
			else:
				string = string + str(num + 1) + ". " + i + "\n"
		if len(results) > 15:
			string = string + "...\n"
		if msg_author_msg != 6942069 and msg_author_place > 15:
			string = string + "**" + str(msg_author_place + 1) + ". " + results[msg_author_place - 1] + "**\n"
		embedVar = discord.Embed(
			title="Time Leaderboards:", description=string, color=0x6E593C
		).set_footer(text="if two people have same pb, random dad joke determines who places above")
		
		button1 = Button(label="Cats", style=ButtonStyle.blurple)
		button1.callback = catlb
					
		button2 = Button(label="Fastest", style=ButtonStyle.green)
		button2.callback = fastlb
		button2.disabled = True
					
		button3 = Button(label="Slowest", style=ButtonStyle.blurple)
		button3.callback = slowlb
							
		myview = View(timeout=180)
		myview.add_item(button1)
		myview.add_item(button2)
		myview.add_item(button3)
										
		await interaction.edit(embed=embedVar, view=myview)

	async def slowlb(interaction):
		nonlocal message
		await interaction.response.defer()
		results = []
		place = 1
		msg_author_msg = 6942069
		register_guild(message.guild.id)
		for i in db[str(message.guild.id)].keys():
			value = get_time(message.guild.id, i, "slow")
			if str(value) != "0":
				value = value / 3600
				value = str(round(value * 100) / 100)
				if str(message.user.id) == str(i):
					msg_author_msg = str(value) + " h: <@" + i + ">"
				results.append(str(value) + " h: <@" + i + ">")
				place += 1
		results = natsort.natsorted(results, reverse=True)
		if msg_author_msg != 6942069:
			msg_author_place = results.index(msg_author_msg) + 1
		string = ""
		for num, i in enumerate(results[:15]):
			if msg_author_msg != 6942069 and num == msg_author_place - 1:
				string = string + "**" + str(num + 1) + ". " + i + "**\n"
			else:
				string = string + str(num + 1) + ". " + i + "\n"
		if len(results) > 15:
			string = string + "...\n"
		if msg_author_msg != 6942069 and msg_author_place > 15:
			string = string + "**" + str(msg_author_place + 1) + ". " + results[msg_author_place - 1] + "**\n"
		embedVar = discord.Embed(
			title="Slow Leaderboards:", description=string, color=0x6E593C
		).set_footer(text="if two people have same pb, vmquan determines who places above")
		
		button1 = Button(label="Cats", style=ButtonStyle.blurple)
		button1.callback = catlb
								
		button2 = Button(label="Fastest", style=ButtonStyle.blurple)
		button2.callback = fastlb
								
		button3 = Button(label="Slowest", style=ButtonStyle.green)
		button3.callback = slowlb
		button3.disabled = True
										
		myview = View(timeout=180)
		myview.add_item(button1)
		myview.add_item(button2)
		myview.add_item(button3)
													
		await interaction.edit(embed=embedVar, view=myview)

	embed = discord.Embed(title="The Leaderboards", description="select your leaderboard using buttons below", color=0x6E593C)
	button1 = Button(label="Cats", style=ButtonStyle.blurple)
	button1.callback = catlb
											
	button2 = Button(label="Fastest", style=ButtonStyle.blurple)
	button2.callback = fastlb
											
	button3 = Button(label="Slowest", style=ButtonStyle.blurple)
	button3.callback = slowlb
													
	myview = View(timeout=180)
	myview.add_item(button1)
	myview.add_item(button2)
	myview.add_item(button3)
															
	await message.response.send_message(embed=embed, view=myview)

@bot.slash_command(description="Give cats to people", default_member_permissions=8)
async def summon(message: discord.Interaction, person_id: discord.Member, amount: int, cat_type: str = discord.SlashOption(choices=cattypes)):
	add_cat(message.guild.id, person_id.id, cat_type, amount)
	embed = discord.Embed(title="Success!", description=f"gave {person_id.id} {amount} {cat_type} cats")
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
	file = discord.File("cat.png", filename="cat.png")
	icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name="egirlcat")
	await message.channel.send(str(icon) + " eGirl cat hasn't appeared! Type \"cat\" to catch ratio!", file=file)
	if not has_ach(message.guild.id, message.user.id, "trolled"):
		ach_data = give_ach(message.guild.id, message.user.id, "trolled")
		embed = discord.Embed(title=ach_data["title"], description=ach_data["description"], color=0x007F0E).set_author(name="Achievement get!", icon_url="https://pomf2.lain.la/f/hbxyiv9l.png")
		await message.response.send_message("OMG TROLLED SO HARD LMAOOOO :joy:", embed=embed, ephemeral=True)
	await message.response.send_message("OMG TROLLED SO HARD LMAOOOO :joy:", ephemeral=True)

@bot.slash_command(description="Force cats to appear", default_member_permissions=8)
async def force(message: discord.Interaction):
	try:
		if db["cat"][str(message.channel.id)]: return
	except Exception:
		return
	channeley = message.channel
	fire[channeley.id] = False
	file = discord.File("cat.png", filename="cat.png")
	cat_types = (
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
	
	localcat = choice(cat_types)
	db["cattype"][str(channeley.id)] = localcat
	icon = discord.utils.get(bot.get_guild(GUILD_ID).emojis, name=localcat.lower()+"cat")   
	message_lmao =  await message.channel.send(str(icon) + " " + db["cattype"][str(channeley.id)] + " cat has appeared! Type \"cat\" to catch it!", file=file)
	db["cat"][str(channeley.id)] = message_lmao.id
	save()
	await message.response.send_message("done", ephemeral=True)


@bot.slash_command(description="Give achievements to people", default_member_permissions=8)
async def giveach(message: discord.Interaction, person_id: discord.Member, ach_id: str):
	all_of_aches = ach_list.keys()
	try:
		if ach_id in all_of_aches:
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

@help.error
@feedback.error
@admin.error
@info.error
@tiktok.error
@daily.error
@inv.error
@achlist.error
@ping.error
@donate.error
@cat.error
@cursed.error
@bal.error
@random.error
@achs.error
@catch.error
@pointLaugh.error
@leaderboards.error
@summon.error
@say.error
@setup.error
@forget.error
@force.error
@giveach.error
@reset.error
async def on_command_error(ctx, error):
	if error == KeyboardInterrupt:
		return
	if error == discord.errors.Forbidden:
		try:
			await ctx.reply("i don't have permissions to do that. (try reinviting the bot)")
		except:
			await ctx.channel.send("i don't have permissions to do that. (try reinviting the bot)")
	else:
		try:
			await ctx.reply("cat crashed lmao\ni send crash reports to milenakos so yes")
		except:
			await ctx.channel.send("cat crashed lmao\ni send crash reports to milenakos so yes")
		milenakoos = await bot.fetch_user(OWNER_ID)
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
