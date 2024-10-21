import io
import os

import discord
import requests
from PIL import Image, ImageColor, ImageDraw, ImageFont
from pilmoji import Pilmoji


def getsize(font, token):
    # thanks pillow
    left, top, right, bottom = font.getbbox(token)
    return right - left, bottom - top

def msg2img(message):
    move = 0
    is_bot = message.author.bot
    is_pinged = message.mention_everyone
    text = message.clean_content
    if not text:
        text = message.system_content
    try:
        nick = message.author.nick
    except Exception:
        nick = message.author.global_name
    color = (message.author.color.r, message.author.color.g, message.author.color.b)
    if color == (0, 0, 0):
        color = (255, 255, 255)
    if not nick:
        nick = message.author.name

    custom_image = None
    for i in message.attachments:
        if not i.content_type or "image" not in i.content_type:
            continue

        try:
            custom_image = Image.open(requests.get(i.url, stream=True).raw).convert("RGBA")
        except Exception:
            continue

        max_width = 930
        width, height = custom_image.size

        if max_width >= width:
            # no rescaling needed
            calculated_height = height
            break

        # calculate the height
        decrease_amount = width / max_width
        calculated_height = int(height / decrease_amount)

        custom_image = custom_image.resize((max_width, calculated_height))

        break

    def break_text(text, font, max_width):
        lines = []
        pings = []

        pilmoji_inst = Pilmoji(Image.new("RGBA", (1, 1)), emoji_scale_factor=45/33)

        if not text:
            return lines, pings
        for txt in text.split("\n"):
            width_of_line = 0
            line = ""
            for token in txt.split():
                start_x = width_of_line
                start_y = len(lines) * 37
                token = token + " "
                token_width = pilmoji_inst.getsize(token, font)[0]
                if width_of_line + token_width < max_width:
                    line += token
                    width_of_line += token_width
                elif token_width >= max_width:
                    in_word_width = width_of_line
                    part_moved = ""
                    saved_width_of_line = 0
                    for i in token:
                        in_word_width += pilmoji_inst.getsize(i, font)[0]
                        if in_word_width < max_width:
                            part_moved += i
                        else:
                            lines.append(part_moved)
                            if not saved_width_of_line:
                                saved_width_of_line = (
                                    in_word_width - pilmoji_inst.getsize(i, font)[0] + 7
                                )
                            in_word_width = 0
                            width_of_line = 0
                            part_moved = ""
                    line = part_moved
                    width_of_line = saved_width_of_line
                else:
                    lines.append(line)
                    line = token
                    width_of_line = token_width
                    start_x = 0
                    start_y = (len(lines) * 37) - 37
                if token[0] == "@":
                    pings.append([start_x, start_y, width_of_line, start_y + 37])

            lines.append(line)
        return lines, pings

    print(os.path.abspath('.'))  # woo debugging
    font = ImageFont.truetype(os.path.abspath("./fonts/whitneysemibold.otf"), 32)  # load fonts
    font2 = ImageFont.truetype(os.path.abspath("./fonts/ggsans-Medium.ttf"), 32)  # load fonts
    font3 = ImageFont.truetype(os.path.abspath("./fonts/whitneysemibold.otf"), 23)  # load fonts

    text_temp = ""
    lines, pings = break_text(text, font2, 930)
    for line in lines:
        text_temp += line + "\n"
    text = text_temp[:-2]

    the_size_and_stuff = 0
    for i in text.split("\n"):
        the_size_and_stuff += 36
    if custom_image:
        if text:
            previous_size = the_size_and_stuff + 55 + 18
            the_size_and_stuff += 18
        else:
            previous_size = 55
            the_size_and_stuff -= 36
        the_size_and_stuff += calculated_height

    if isinstance(color, str):
        color = ImageColor.getrgb(color)

    bg_color = (49, 51, 56)
    if is_pinged:
        bg_color = (73, 68, 60)
    new_img = Image.new("RGBA", (1067, 75 + the_size_and_stuff), bg_color)
    pencil = ImageDraw.Draw(new_img)
    try:
        pfp = requests.get(message.author.display_avatar.url, stream=True).raw
        im2 = Image.open(pfp).resize((800, 800)).convert("RGBA")  # resize user avatar
    except Exception: # if the pfp is bit too silly
        new_url = "https://cdn.discordapp.com/embed/avatars/0.png"
        pfp = requests.get(new_url, stream=True).raw
        im2 = Image.open(pfp).resize((800, 800)).convert("RGBA")  # resize user avatar

    mask_im = Image.new("L", (800, 800), 0)  # make a mask image for making pfp circle
    draw = ImageDraw.Draw(mask_im)  # enable drawing mode on mask
    draw.ellipse((0, 0, 800, 800), fill=255)  # draw circle on mask
    newer_img = Image.new("RGBA", (800, 800), bg_color)
    newer_img.paste(im2, (0, 0), mask_im)  # apply mask to avatar
    newer_img = newer_img.resize((80, 80), Image.Resampling.LANCZOS)
    new_img.paste(newer_img, (10, 10), newer_img)

    if custom_image:
        new_img.paste(custom_image, (122, previous_size), custom_image)

    for ping in pings:
        pencil.rounded_rectangle(
            (ping[0] + 122, ping[1] + 57, ping[2] + 115, ping[3] + 57),
            fill=ImageColor.getrgb("#414675"),
            radius=7,
        )

    if is_pinged:
        pencil.rectangle(
            (0, 0, 0, 65 + the_size_and_stuff), fill=ImageColor.getrgb("#FAA81A")
        )

    pencil.text((122, 8), nick, font=font, fill=color)  # draw author name
    if is_bot:
        botfont = ImageFont.truetype(os.path.abspath("./fonts/whitneysemibold.otf"), 20)

        pencil.rounded_rectangle(
            (
                129 + getsize(font, nick)[0] + 5,
                8 + 5,
                129 + getsize(font, nick)[0] + 14 + getsize(botfont, "APP")[0],
                10 + 6 + 25,
            ),
            fill=(88, 101, 242),
            radius=3,
        )

        pencil.text(
            (131 + getsize(font, nick)[0] + 8, 10 + 4),
            "APP",
            font=botfont,
            fill=(255, 255, 255),
        )
        move = getsize(botfont, "APP")[0] + 20

    with Pilmoji(new_img) as pilmoji2:
        pilmoji2.text((122, 55), text.strip(), (255, 255, 255), font2, emoji_scale_factor=45/33)

    now = message.created_at
    # there is probably easier way than this but ehhh
    twelvehour = now.strftime("%I:%M")
    twentyfourhour = now.strftime("%H:%M")
    if twelvehour == twentyfourhour:
        suffix = "AM"
    else:
        suffix = "PM"

    # 09:34 -> 9:34
    if twelvehour[0] == "0" and twelvehour[1] != ":":
        twelvehour = twelvehour[1:]

    pencil.text(
        (13 + 122 + getsize(font, nick)[0] + move, 17),
        f"Today at {twelvehour} {suffix}",
        font=font3,
        fill=ImageColor.getrgb("#A3A4AA"),
    )  # draw time

    with io.BytesIO() as image_binary:
        new_img.save(image_binary, "PNG")
        image_binary.seek(0)
        return discord.File(fp=image_binary, filename="catch.png")


# italic          https://discord.com/assets/7f18f1d5ab6ded7cf71bbc1f907ee3d4.woff2
# bold            https://discord.com/assets/f9e7047f6447547781512ec4b977b2ab.woff2
# bold and italic https://discord.com/assets/21070f52a8a6a61edef9785eaf303fb8.woff2
