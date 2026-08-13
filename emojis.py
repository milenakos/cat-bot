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
import tempfile

import anyio
import discord

import config

EMOJI_REPO = "https://github.com/staring-cat/emojis"

# wipe every emoji already on the application before uploading (useful for switching themes cleanly)
REPLACE_EXISTING_EMOJIS = False

# the non-themed icons - achievements, packs, prisms, /fish icons, etc. - always needed regardless of theme
UPLOAD_BASE_EMOJIS = True

# which cat-catching spawn emoji themes to upload; "default" is the theme config.EMOJI = None uses
SPAWN_EMOJI_THEMES = {
    "default": True,
    "birthday": False,
    "halloween": False,
    "old": False,
}


async def upload_emoji_folder(client: discord.Client, folder: str) -> int:
    # walks subfolders too, since base/ is split into categories (packs/, badges/, etc.)
    found = 0
    for root, _dirs, filenames in os.walk(folder):
        for filename in filenames:
            name, ext = os.path.splitext(filename)
            if ext not in (".png", ".gif"):
                continue
            found += 1
            emoji_name = name
            image_path = os.path.join(root, filename)
            if os.path.islink(image_path):
                print(f"skipping symbolic link: {image_path}")
                continue
            try:
                async with await anyio.open_file(image_path, "rb") as image:
                    await client.create_application_emoji(name=emoji_name, image=await image.read())
            except discord.HTTPException as e:
                print(f"couldn't upload {emoji_name}: {e}")
    return found


async def main() -> None:
    # a freshly-generated temp dir can't collide with anything pre-existing (unlike a fixed
    # directory name), and cleans itself up even if git clone fails partway through
    with tempfile.TemporaryDirectory(prefix="cat-bot-emojis-") as clone_dir:
        await asyncio.create_subprocess_exec("git", "clone", "--depth", "1", EMOJI_REPO, clone_dir)

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
                found = await upload_emoji_folder(client, os.path.join(clone_dir, "base"))
                if found == 0:
                    raise RuntimeError("no base emojis found - does the cloned branch have a 'base/' folder?")
                print(f"uploaded {found} base (non-spawning) emojis")

            for theme, enabled in SPAWN_EMOJI_THEMES.items():
                if not enabled:
                    continue
                found = await upload_emoji_folder(client, os.path.join(clone_dir, "spawning", theme))
                if found == 0:
                    raise RuntimeError(f"no emojis found for the '{theme}' theme - does the cloned branch have 'spawning/{theme}/'?")
                print(f"uploaded {found} '{theme}' spawn emoji theme")
        finally:
            await client.close()


if __name__ == "__main__":
    asyncio.run(main())
