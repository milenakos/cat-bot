# ![Cat Bot PFP](https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png&h=25) Cat Bot [![top.gg](https://top.gg/api/widget/servers/966695034340663367.svg?noavatar=true)](https://top.gg/bot/966695034340663367) [![Discord Server](https://img.shields.io/discord/966586000417619998?label=discord&logo=discord)](https://discord.gg/cat-stand-966586000417619998)

Discord Cat Bot Source Code

# Development

Please note self-hosting is hacky and isn't supported, instructions below are for testing/development/messing around. I won't stop you, but you WILL have to mess around with the code a bunch for it to work good, so be warned.

## Prerequisites

- Python 3
- Git (optional)
- PostgreSQL (optional)

## Instructions

1. Clone the repository. You can use green "Code" button at the top or a git command:

   `git clone https://github.com/milenakos/cat-bot.git`

2. Install requirements:

   `pip install -r requirements.txt`

3. You will need to add all emojis you want to Discord's App Emoji in the Dev Portal.

   If they aren't found there, they will be replaced with a placeholder.

   All emojis can be downloaded [here](https://github.com/staring-cat/emojis/releases/latest/download/emojis.zip).

4. Go inside of the `config.py` file and configure everything for your liking.

5. Run the bot with `python bot.py`

6. Done!

# License

Cat Bot is licensed under GNU Affero General Public License v3.0 license. View `LICENSE` for more information.
