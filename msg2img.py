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

import datetime
import io
import os

import discord
import requests
from PIL import Image, ImageColor, ImageDraw, ImageFont
from pilmoji import Pilmoji

CANVAS_WIDTH = 1067
AVATAR_SIZE = 80
AVATAR_X = 12
AVATAR_Y = 12
TEXT_X = 122
NAME_Y = 8
TEXT_Y = 55
LINE_HEIGHT = 37
LINE_HEIGHT_H = 36
MAX_TEXT_WIDTH = 930
MAX_ATTACH_WIDTH = 930
EMOJI_SCALE = 45 / 33

BG_DEFAULT = (49, 51, 56)
BG_PINGED = (73, 68, 60)
COLOR_PING_BG = "#414675"
COLOR_PING_BAR = "#FAA81A"
COLOR_TIMESTAMP = "#A3A4AA"
COLOR_BOT_BADGE = (88, 101, 242)
COLOR_GUILD_BADGE = (70, 70, 77)

FONT_GGSANS = os.path.abspath("./assets/ggsans-Medium.ttf")

FETCH_TIMEOUT = (5, 10)


def _text_size(font: ImageFont.FreeTypeFont, text: str) -> tuple[float, float]:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _fetch_image(url: str, size: tuple[int, int] | None = None) -> Image.Image | None:
    try:
        with requests.get(url, stream=True, timeout=FETCH_TIMEOUT) as resp:
            resp.raise_for_status()
            img = Image.open(resp.raw).convert("RGBA")
        if size:
            img = img.resize(size, Image.Resampling.LANCZOS)
        return img
    except Exception:
        return None


def _circular_avatar(url: str, diameter: int, bg: tuple) -> Image.Image:
    RAW = 800
    img = _fetch_image(url, (RAW, RAW)) or _fetch_image("https://cdn.discordapp.com/embed/avatars/0.png", (RAW, RAW)) or Image.new("RGBA", (RAW, RAW), bg)
    mask = Image.new("L", (RAW, RAW), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, RAW, RAW), fill=255)
    base = Image.new("RGBA", (RAW, RAW), bg)
    base.paste(img, (0, 0), mask)
    return base.resize((diameter, diameter), Image.Resampling.LANCZOS)


def _scale_to_width(img: Image.Image, max_width: int) -> Image.Image:
    w, h = img.size
    if w <= max_width:
        return img
    return img.resize((max_width, int(h * max_width / w)))


def _member_color(member: discord.User | discord.Member) -> tuple[int, int, int]:
    if not isinstance(member, discord.Member):
        return (255, 255, 255)
    c = member.color
    return (255, 255, 255) if (c.r, c.g, c.b) == (0, 0, 0) else (c.r, c.g, c.b)


def _format_timestamp(dt: datetime.datetime) -> str:
    fmt = "%H:%M" if dt.date() == discord.utils.utcnow().date() else "%d.%m.%Y, %H:%M"
    return dt.strftime(fmt)


def _break_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> tuple[list[str], list[tuple[int, int, int, int]]]:
    if not text:
        return [], []

    lines: list[str] = []
    pings: list[tuple[int, int, int, int]] = []
    ruler = Pilmoji(Image.new("RGBA", (1, 1)), emoji_scale_factor=EMOJI_SCALE)

    for paragraph in text.split("\n"):
        line_w = 0
        current = ""

        for word in paragraph.split():
            token = word + " "
            token_w = ruler.getsize(token, font)[0]
            token_x = line_w
            token_y = len(lines) * LINE_HEIGHT

            if line_w + token_w < max_width:
                current += token
                line_w += token_w
            elif token_w >= max_width:
                char_x = line_w
                fragment = current
                current = ""
                for ch in token:
                    ch_w = ruler.getsize(ch, font)[0]
                    char_x += ch_w
                    if char_x < max_width:
                        fragment += ch
                    else:
                        lines.append(fragment)
                        fragment = ch
                        char_x = ch_w
                current = fragment
                line_w = char_x
            else:
                lines.append(current)
                current = token
                line_w = token_w
                token_x = 0
                token_y = len(lines) * LINE_HEIGHT - LINE_HEIGHT

            if token[0] == "@":
                pings.append((token_x, token_y, line_w, token_y + LINE_HEIGHT))

        lines.append(current)

    return lines, pings


def msg2img(message: discord.Message, member: discord.User | discord.Member) -> discord.File:
    text = message.clean_content or message.system_content
    nick = member.display_name or member.name
    color = _member_color(member)
    is_bot = member.bot
    is_pinged = message.mention_everyone

    body_font = ImageFont.truetype(FONT_GGSANS, 32)
    time_font = ImageFont.truetype(FONT_GGSANS, 23)
    badge_font = ImageFont.truetype(FONT_GGSANS, 20)

    lines, pings = _break_text(text, body_font, MAX_TEXT_WIDTH)
    text = "\n".join(lines)[:-1] if lines else ""

    attachment: Image.Image | None = None
    for a in message.attachments:
        if not a.content_type or "image" not in a.content_type:
            continue
        raw = _fetch_image(a.url)
        if raw is None:
            continue
        attachment = _scale_to_width(raw, MAX_ATTACH_WIDTH)
        break

    n_lines = len(text.split("\n"))
    text_block_h = n_lines * LINE_HEIGHT_H

    if attachment:
        attach_h = attachment.size[1]
        if text:
            attach_y = TEXT_Y + text_block_h + 18
            canvas_h = 75 + text_block_h + 18 + attach_h
        else:
            attach_y = TEXT_Y
            canvas_h = 75 + attach_h
    else:
        canvas_h = 75 + text_block_h
        attach_y = 0  # unused

    bg = BG_PINGED if is_pinged else BG_DEFAULT
    canvas = Image.new("RGBA", (CANVAS_WIDTH, canvas_h), bg)
    draw = ImageDraw.Draw(canvas)

    if attachment:
        canvas.paste(attachment, (TEXT_X, attach_y), attachment)

    for px0, py0, px1, py1 in pings:
        draw.rounded_rectangle(
            (px0 + TEXT_X, py0 + 57, px1 + 115, py1 + 57),
            fill=ImageColor.getrgb(COLOR_PING_BG),
            radius=7,
        )

    if is_pinged:
        draw.rectangle((0, 0, 0, canvas_h - 10), fill=ImageColor.getrgb(COLOR_PING_BAR))

    avatar = _circular_avatar(member.display_avatar.url, AVATAR_SIZE, bg)
    canvas.paste(avatar, (AVATAR_X, AVATAR_Y), avatar)

    if member.avatar_decoration:
        deco = _fetch_image(member.avatar_decoration.url, (96, 96))
        if deco:
            canvas.paste(deco, (4, 4), deco)

    draw.text((TEXT_X, NAME_Y), nick, font=body_font, fill=color)
    nick_w = int(_text_size(body_font, nick)[0])

    icon_offset = 0
    if isinstance(member, discord.Member) and isinstance(member.display_icon, discord.Asset):
        icon = _fetch_image(member.display_icon.url, (30, 30))
        if icon:
            canvas.paste(icon, (TEXT_X + 10 + nick_w, NAME_Y + 5), icon)
            icon_offset = 35

    badge_offset = 0
    if is_bot or (member.primary_guild and member.primary_guild.tag):
        label = "APP" if is_bot else (member.primary_guild.tag or "")
        badge_color = COLOR_BOT_BADGE if is_bot else COLOR_GUILD_BADGE
        badge_x = TEXT_X + nick_w + icon_offset
        label_w = _text_size(badge_font, label)[0]

        draw.rounded_rectangle(
            (badge_x + 5, NAME_Y + 5, badge_x + 14 + label_w, NAME_Y + 33),
            fill=badge_color,
            radius=3,
        )
        draw.text((badge_x + 10, NAME_Y + 6), label, font=badge_font, fill=(255, 255, 255))
        badge_offset = label_w + 20

    with Pilmoji(canvas) as pilmoji:
        pilmoji.text((TEXT_X, TEXT_Y), text.strip(), (255, 255, 255), body_font, emoji_scale_factor=EMOJI_SCALE)

    draw.text(
        (TEXT_X + 7 + nick_w + badge_offset + icon_offset, NAME_Y + 9),
        _format_timestamp(message.created_at),
        font=time_font,
        fill=ImageColor.getrgb(COLOR_TIMESTAMP),
    )

    with io.BytesIO() as buf:
        canvas.save(buf, "PNG")
        buf.seek(0)
        return discord.File(fp=buf, filename="catch.png")
