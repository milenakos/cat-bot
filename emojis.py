import os

import discord

import config

intents = discord.Intents.default()
client = discord.Client(intents=intents)

repo = "https://github.com/VishramKidPG123/emojis"
clear_all_existing_emojis=False
non_spawning_emojis = True
spawning_emojis = {
    "default": True,
    "birthday": False,
    "halloween": False, 
    "old": False
}

async def add_emojis(folder=None):
    for item in os.listdir(folder):
        try:
            if item.endswith(".png"):
                path = folder + "/" + item if folder else item
                with open(path, 'rb') as image:
                    await client.create_application_emoji(name=item[:-4], image=image.read())
        except:
            pass

@client.event
async def on_ready():
    print('Logged on as', client.user)
    os.system(f"git clone {repo}")
    os.chdir("emojis")
    if clear_all_existing_emojis:
        for emoji in await client.fetch_application_emojis():
            await emoji.delete()
        print("all emojis cleared")
    if non_spawning_emojis:
        await add_emojis()
        print("non-spawning emojis added")
    os.chdir("spawning")
    for i in spawning_emojis:
        if spawning_emojis[i]:
            await add_emojis(i)
            print(f"{i} spawning emojis added")
    os.chdir("../..")
    os.system("rm -rf emojis")
    await client.close()

client.run(config.TOKEN)
