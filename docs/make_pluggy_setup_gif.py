"""Render docs/pluggy-setup.gif, the step-by-step Meu Pluggy setup guide shown in the README.

Dev-only dependency: pip install Pillow
Run: python docs/make_pluggy_setup_gif.py
Steps follow https://github.com/pluggyai/meu-pluggy (Item ID step: Actual Budget's Pluggy guide).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).with_name("pluggy-setup.gif")
W, H = 960, 540
STEP_MS = 3800

BG = "#f6f7f9"
CARD = "#ffffff"
INK = "#1d2330"
MUTED = "#5b6475"
ACCENT = "#6d3cf5"  # Pluggy-ish purple
TRACK = "#dfe2e8"

SANS = "/System/Library/Fonts/Helvetica.ttc"
MONO = "/System/Library/Fonts/Menlo.ttc"


def font(path: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, index=index)


F_KICKER = font(SANS, 20, 1)
F_TITLE = font(SANS, 40, 1)
F_BODY = font(SANS, 25)
F_PILL = font(MONO, 21)
F_NUM = font(SANS, 96, 1)

# (where, title, description lines). Quoted labels are verbatim from Pluggy's UI.
STEPS = [
    ("meu.pluggy.ai", "Create your Meu Pluggy account",
     "Free for personal use. This is where your banks get connected."),
    ("meu.pluggy.ai", "Connect each bank",
     "Press the connect button, pick your institution and authorize it via Open Finance."),
    ("dashboard.pluggy.ai", "Create a Pluggy developer account",
     "Starts a 15-day trial. Do steps 4 to 7 before it ends; data keeps flowing afterwards."),
    ("dashboard.pluggy.ai  ›  your application", "Add the MeuPluggy connector",
     "Customize your application so MeuPluggy appears in its connector list."),
    ("dashboard.pluggy.ai  ›  your application", "Create a Development Application",
     "Copy its client_id and client_secret. Treat the secret like a password."),
    ("dashboard.pluggy.ai  ›  \"Ir para Demo\"", "Authorize MeuPluggy in the demo app",
     "Run \"MeuPluggy OAuth Authorization\" once per bank (per bank, not per account)."),
    ("demo app  ›  three-dot menu", "Copy each bank's Item ID",
     "Use \"Copiar Item ID\" on every connection. The API has no way to list them."),
    ("GitHub secrets  /  .env", "Fill in the credentials",
     "PLUGGY_CLIENT_ID, PLUGGY_CLIENT_SECRET and PLUGGY_ITEM_IDS (comma-separated)."),
]


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=fnt) <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    return lines + [line]


def progress(draw: ImageDraw.ImageDraw, current: int) -> None:
    n = len(STEPS)
    gap, y = 10, H - 46
    seg = (W - 120 - gap * (n - 1)) / n
    for i in range(n):
        x0 = 60 + i * (seg + gap)
        draw.rounded_rectangle([x0, y, x0 + seg, y + 8], radius=4, fill=ACCENT if i <= current else TRACK)


def frame_step(i: int) -> Image.Image:
    where, title, body = STEPS[i]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((60, 36), "SETTING UP MEU PLUGGY FOR GROK-FINANCE", font=F_KICKER, fill=MUTED)
    d.rounded_rectangle([60, 84, W - 60, H - 84], radius=22, fill=CARD, outline=TRACK, width=2)

    d.text((100, 120), str(i + 1), font=F_NUM, fill=ACCENT)
    d.text((100, 232), f"of {len(STEPS)}", font=F_KICKER, fill=MUTED)

    x = 230
    pill_w = d.textlength(where, font=F_PILL) + 36
    d.rounded_rectangle([x, 128, x + pill_w, 170], radius=21, fill="#efeafe")
    d.text((x + 18, 138), where, font=F_PILL, fill=ACCENT)

    y = 196
    for line in wrap(d, title, F_TITLE, W - 60 - 40 - x):
        d.text((x, y), line, font=F_TITLE, fill=INK)
        y += 50
    y += 14
    for line in wrap(d, body, F_BODY, W - 60 - 40 - x):
        d.text((x, y), line, font=F_BODY, fill=MUTED)
        y += 36
    progress(d, i)
    return img


def frame_cover() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((60, 190), "Meu Pluggy setup", font=font(SANS, 64, 1), fill=INK)
    d.text((62, 276), f"{len(STEPS)} steps to get client_id, client_secret and Item IDs", font=F_BODY, fill=MUTED)
    d.rounded_rectangle([60, 330, 200, 338], radius=4, fill=ACCENT)
    return img


def main() -> None:
    frames = [frame_cover()] + [frame_step(i) for i in range(len(STEPS))]
    durations = [2200] + [STEP_MS] * len(STEPS)
    durations[-1] = 5500
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
