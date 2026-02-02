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

import catpg
import config


async def connect():
    await catpg.connect(user="cat_bot", password=config.DB_PASS, database="cat_bot", host="127.0.0.1", max_size=25, timeout=1)


async def close():
    await catpg.close()


class Profile(catpg.Model):
    _capped_ints = [
        "cats_gifted",
        "cat_gifts_recieved",
        "cats_traded",
        "cat_Fine",
        "cat_Nice",
        "cat_Good",
        "cat_Rare",
        "cat_Wild",
        "cat_Baby",
        "cat_Epic",
        "cat_Sus",
        "cat_Brave",
        "cat_Rickroll",
        "cat_Reverse",
        "cat_Superior",
        "cat_Trash",
        "cat_Legendary",
        "cat_Mythic",
        "cat_8bit",
        "cat_Corrupt",
        "cat_Professor",
        "cat_Divine",
        "cat_Real",
        "cat_Ultimate",
        "cat_eGirl",
    ]


class User(catpg.Model):
    _primary_key = "user_id"
    _capped_ints = ["custom_num"]


class Channel(catpg.Model):
    _primary_key = "channel_id"


class Prism(catpg.Model):
    pass


class Reminder(catpg.Model):
    pass


class Server(catpg.Model):
    _primary_key = "server_id"
