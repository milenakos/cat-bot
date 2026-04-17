# ![Cat Bot PFP](https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png&h=25) Cat Bot [![top.gg](https://top.gg/api/widget/servers/966695034340663367.svg?noavatar=true)](https://top.gg/bot/966695034340663367) [![Discord Server](https://img.shields.io/discord/966586000417619998?label=discord&logo=discord)](https://discord.gg/staring) [![Wiki](https://img.shields.io/badge/Wiki-blue?label=Cat%20Bot&logo=wiki.js)](https://wiki.minkos.lol)

Discord Cat Bot Source Code

# Development

Please note that self-hosting is hacky and isn't supported; instructions below are for testing/development/messing around. I won't stop you, but you WILL have to mess around with the code a bunch for it to work good, so be warned.

## Prerequisites

- Python 3 (around 3.8 or so, newer is better ofc)
- PostgreSQL

## Instructions

1. Clone/download the repository.

2. `pip install -r requirements.txt` (use venv if desired)

3. Download [the emojis](https://github.com/staring-cat/emojis/releases/latest/download/emojis.zip) and upload them to "App Emojis" in Discord Dev Portal.

5. Setup your Postgres: (example instructions)
 - `createdb -U postgres -O cat_bot cat_bot`
 - `psql -U cat_bot`
 - Copy-paste everything from `schema.sql`.

6. Configure the bot inside `config.py` file. Most things are optional. You can hardcode the values if you don't want to use environment variables.

7. Run the bot with `python bot.py`.

# License

Cat Bot is licensed under GNU Affero General Public License v3.0 license. View `LICENSE` for more information.

CatPG, our custom-made `asyncpg` wrapper, is licensed under MIT License instead. The license text is present in the beginning of `catpg.py` file.
