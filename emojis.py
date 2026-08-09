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

# Uploads Cat Bot's emojis to your own bot application, so you don't have to do it by hand.
# Run with: python emojis.py

import asyncio
import os
import shutil
import subprocess

import discord

import config

EMOJI_REPO = "https://github.com/staring-cat/emojis"
LOCAL_CLONE_DIR = "cat-bot-emojis-tmp"

# wipe every emoji already on the application before uploading (useful for switching themes cleanly)
REPLACE_EXISTING_EMOJIS = False

# the non-themed icons (achievements, packs, prisms, etc.) and the /fish icons - always needed regardless of theme
UPLOAD_BASE_EMOJIS = True
UPLOAD_FISH_EMOJIS = True

# which cat-catching spawn emoji themes to upload; "default" is the theme config.EMOJI = None uses
SPAWN_EMOJI_THEMES = {
    "default": True,
    "birthday": False,
    "halloween": False,
    "old": False,
}


async def upload_emoji_folder(client: discord.Client, folder: str) -> None:
    for filename in os.listdir(folder):
        if not filename.endswith(".png"):
            continue
        emoji_name = filename.removesuffix(".png")
        try:
            with open(os.path.join(folder, filename), "rb") as image:
                await client.create_application_emoji(name=emoji_name, image=image.read())
        except discord.HTTPException as e:
            print(f"couldn't upload {emoji_name}: {e}")


async def main() -> None:
    subprocess.run(["git", "clone", "--depth", "1", EMOJI_REPO, LOCAL_CLONE_DIR], check=True)

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    try:
        # login() only authenticates the HTTP session - no need to open a gateway connection for this
        await client.login(config.TOKEN)

        if REPLACE_EXISTING_EMOJIS:
            for existing_emoji in await client.fetch_application_emojis():
                await existing_emoji.delete()
            print("cleared all existing application emojis")

        if UPLOAD_BASE_EMOJIS:
            await upload_emoji_folder(client, os.path.join(LOCAL_CLONE_DIR, "base"))
            print("uploaded base (non-spawning) emojis")

        if UPLOAD_FISH_EMOJIS:
            await upload_emoji_folder(client, os.path.join(LOCAL_CLONE_DIR, "spawning", "fish"))
            print("uploaded /fish emojis")

        for theme, enabled in SPAWN_EMOJI_THEMES.items():
            if not enabled:
                continue
            await upload_emoji_folder(client, os.path.join(LOCAL_CLONE_DIR, "spawning", theme))
            print(f"uploaded '{theme}' spawn emoji theme")
    finally:
        await client.close()
        shutil.rmtree(LOCAL_CLONE_DIR, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
