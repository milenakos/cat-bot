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

# standalone color/other emojis (rainbow, red, pink, cyan, yellow, etc.) used for aura display and dropdowns
UPLOAD_OTHER_EMOJIS = True

# which cat-catching spawn emoji themes to upload; "default" is the theme config.EMOJI = None uses
SPAWN_EMOJI_THEMES = {
    "default": True,
    "birthday": False,
    "halloween": False,
    "old": False,
    "fish": False,
}


async def upload_emoji_folder(client: discord.Client, folder: str) -> tuple[int, int]:
    # walks subfolders too, since base/ is split into categories (packs/, badges/, etc.)
    found = 0
    uploaded = 0
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
                uploaded += 1
            except discord.HTTPException as e:
                if "already exists" not in str(e).lower():
                    print(f"couldn't upload {emoji_name}: {e}")
    return found, uploaded


async def main() -> None:
    # a freshly-generated temp dir can't collide with anything pre-existing (unlike a fixed
    # directory name), and cleans itself up even if git clone fails partway through
    with tempfile.TemporaryDirectory(prefix="cat-bot-emojis-") as clone_dir:
        proc = await asyncio.create_subprocess_exec("git", "clone", "--depth", "1", EMOJI_REPO, clone_dir)
        await proc.wait()

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
                found, uploaded = await upload_emoji_folder(client, os.path.join(clone_dir, "base"))
                if found == 0:
                    raise RuntimeError("no base emojis found - does the cloned branch have a 'base/' folder?")
                print(f"uploaded {uploaded} base (non-spawning) emojis ({found - uploaded} already existed)")

            if UPLOAD_OTHER_EMOJIS:
                found, uploaded = await upload_emoji_folder(client, os.path.join(clone_dir, "other"))
                if found == 0:
                    raise RuntimeError("no other emojis found - does the cloned branch have an 'other/' folder?")
                print(f"uploaded {uploaded} other emojis ({found - uploaded} already existed)")

            for theme, enabled in SPAWN_EMOJI_THEMES.items():
                if not enabled:
                    continue
                found, uploaded = await upload_emoji_folder(client, os.path.join(clone_dir, "cattypes", theme))
                if found == 0:
                    raise RuntimeError(f"no emojis found for the '{theme}' theme - does the cloned branch have 'cattypes/{theme}/'?")
                print(f"uploaded {uploaded} '{theme}' spawn emoji theme ({found - uploaded} already existed)")

            # invalidate bot emoji cache so the bot picks up newly uploaded emojis on next startup
            cache_path = os.path.join(os.path.dirname(__file__), "config", "emojis_cache.json")
            try:
                os.remove(cache_path)
                print("cleared emojis_cache.json — bot will refresh on next startup")
            except FileNotFoundError:
                pass
        finally:
            await client.close()


if __name__ == "__main__":
    asyncio.run(main())
