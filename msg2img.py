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
import re

import discord
import requests
from PIL import Image, ImageColor, ImageDraw, ImageFont
from pilmoji import Pilmoji
from pilmoji.helpers import NodeType, to_nodes

CANVAS_WIDTH = 1067
AVATAR_SIZE = 80
AVATAR_X = 12
AVATAR_Y = 12
TEXT_X = 122
NAME_Y = 8
TEXT_Y = 50
LINE_HEIGHT = 45
MAX_TEXT_WIDTH = 930
MAX_ATTACH_WIDTH = 930
EMOJI_SCALE = 1.4

BG_DEFAULT = (49, 51, 56)
BG_PINGED = (73, 68, 60)
COLOR_PING_BG = "#414675"
COLOR_PING_BAR = "#FAA81A"
COLOR_TIMESTAMP = "#A3A4AA"
COLOR_BOT_BADGE = (88, 101, 242)
COLOR_GUILD_BADGE = (70, 70, 77)

FETCH_TIMEOUT = (5, 10)


def _fetch_url(url: str) -> bytes:
    with requests.get(url, timeout=FETCH_TIMEOUT) as resp:
        resp.raise_for_status()
        return resp.content


FONTS = {
    "normal": _fetch_url("https://discord.com/assets/66d715454104d24e.woff2"),
    "bold": _fetch_url("https://discord.com/assets/2df2c3ff74408972.woff2"),
    "italic": _fetch_url("https://discord.com/assets/dd24010f3cf7def7.woff2"),
    "bold_italic": _fetch_url("https://discord.com/assets/ce3b8055f5114434.woff2"),
}

body_fonts = {style: ImageFont.truetype(io.BytesIO(f), 32) for style, f in FONTS.items()}
time_font = ImageFont.truetype(io.BytesIO(FONTS["normal"]), 23)
badge_font = ImageFont.truetype(io.BytesIO(FONTS["bold"]), 20)


def _text_size(font: ImageFont.FreeTypeFont, text: str) -> tuple[float, float]:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _measure(text: str, font: ImageFont.FreeTypeFont) -> int:
    width = 0
    for node in to_nodes(text)[0] if text else []:
        if node.type is NodeType.text:
            width += int(font.getlength(node.content))
        else:
            width += int(EMOJI_SCALE * font.size)
    return width


def _split_keep_spaces(segment: str) -> list[str]:
    return [t + " " for t in segment.split(" ")]


def _fetch_image(url: str, size: tuple[int, int] | None = None) -> Image.Image | None:
    try:
        resp = _fetch_url(url)
        if not resp:
            return None
        img = Image.open(io.BytesIO(resp)).convert("RGBA")
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


_MD_RE = re.compile(r"\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*")


def _parse_markdown(text: str) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    pos = 0
    for m in _MD_RE.finditer(text):
        if m.start() > pos:
            segments.append(("normal", text[pos : m.start()]))
        if m.group(1) is not None:
            segments.append(("bold_italic", m.group(1)))
        elif m.group(2) is not None:
            segments.append(("bold", m.group(2)))
        else:
            segments.append(("italic", m.group(3)))
        pos = m.end()
    if pos < len(text):
        segments.append(("normal", text[pos:]))
    return segments


def _break_text(text: str, fonts: dict[str, ImageFont.FreeTypeFont], max_width: int) -> tuple[list[list[tuple[str, str]]], list[tuple[int, int, int, int]]]:
    if not text:
        return [], []

    lines: list[list[tuple[str, str]]] = []
    pings: list[tuple[int, int, int, int]] = []

    def push_run(line: list[tuple[str, str]], style: str, chunk: str) -> None:
        if not chunk:
            return
        if line and line[-1][0] == style:
            line[-1] = (style, line[-1][1] + chunk)
        else:
            line.append((style, chunk))

    for paragraph in text.split("\n"):
        line_w = 0
        current: list[tuple[str, str]] = []

        tokens: list[tuple[str, str]] = []
        for style, segment in _parse_markdown(paragraph):
            for token in _split_keep_spaces(segment):
                tokens.append((style, token))

        for style, token in tokens:
            font = fonts[style]
            token_w = _measure(token, font)
            token_x = line_w
            token_y = len(lines) * LINE_HEIGHT

            if line_w + token_w < max_width:
                push_run(current, style, token)
                line_w += token_w
            elif token_w >= max_width:
                char_x = line_w
                for ch in token:
                    ch_w = _measure(ch, font)
                    if char_x + ch_w < max_width:
                        push_run(current, style, ch)
                        char_x += ch_w
                    else:
                        lines.append(current)
                        current = []
                        push_run(current, style, ch)
                        char_x = ch_w
                line_w = char_x
            else:
                lines.append(current)
                current = [(style, token)]
                line_w = token_w
                token_x = 0
                token_y = len(lines) * LINE_HEIGHT - LINE_HEIGHT

            if token[0] == "@" and style == "normal":
                pings.append((token_x, token_y, line_w, token_y + LINE_HEIGHT))

        # drop the trailing space at each line's end (it's never visible)
        while current and not current[-1][1].rstrip(" "):
            current.pop()
        if current:
            style, chunk = current[-1]
            current[-1] = (style, chunk.rstrip(" "))
        lines.append(current)

    return lines, pings


def msg2img(message: discord.Message, member: discord.User | discord.Member) -> discord.File:
    text = message.clean_content or message.system_content
    nick = member.display_name or member.name
    color = _member_color(member)
    is_bot = member.bot
    is_pinged = message.mention_everyone

    lines, pings = _break_text(text, body_fonts, MAX_TEXT_WIDTH)
    n_lines = len(lines)

    attachment: Image.Image | None = None
    for a in message.attachments:
        if not a.content_type or "image" not in a.content_type:
            continue
        raw = _fetch_image(a.url)
        if raw is None:
            continue
        attachment = _scale_to_width(raw, MAX_ATTACH_WIDTH)
        break

    text_block_h = n_lines * LINE_HEIGHT

    if attachment:
        attach_h = attachment.size[1]
        if lines:
            attach_y = TEXT_Y + text_block_h + 10
            canvas_h = 60 + text_block_h + 10 + attach_h
        else:
            attach_y = TEXT_Y
            canvas_h = 60 + attach_h
    else:
        canvas_h = 60 + text_block_h
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

    draw.text((TEXT_X, NAME_Y), nick, font=body_fonts["bold"], fill=color)
    nick_w = int(_text_size(body_fonts["bold"], nick)[0])

    icon_offset = 0
    if isinstance(member, discord.Member) and isinstance(member.display_icon, discord.Asset):
        icon = _fetch_image(member.display_icon.url, (30, 30))
        if icon:
            canvas.paste(icon, (TEXT_X + 8 + nick_w, NAME_Y + 7), icon)
            icon_offset = 38

    badge_offset = 0
    if is_bot or (member.primary_guild and member.primary_guild.tag):
        label = "APP" if is_bot else (member.primary_guild.tag or "")
        badge_color = COLOR_BOT_BADGE if is_bot else COLOR_GUILD_BADGE
        badge_x = TEXT_X + 3 + nick_w + icon_offset
        label_w = _text_size(badge_font, label)[0]

        draw.rounded_rectangle(
            (badge_x + 5, NAME_Y + 8, badge_x + 14 + label_w, NAME_Y + 36),
            fill=badge_color,
            radius=4,
        )
        draw.text((badge_x + 10, NAME_Y + 9), label, font=badge_font, fill=(255, 255, 255))
        badge_offset = label_w + 20

    with Pilmoji(canvas) as pilmoji:
        for i, line in enumerate(lines):
            x = TEXT_X
            y = TEXT_Y + i * LINE_HEIGHT
            for style, chunk in line:
                font = body_fonts[style]
                pilmoji.text((x, y), chunk, (255, 255, 255), font, emoji_scale_factor=EMOJI_SCALE)
                x += _measure(chunk, font)

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
