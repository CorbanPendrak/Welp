from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106
from PIL import Image

from welp_app import METER_MAX, ViewModel, WelpApp

SPRITESHEET_NAME = "KipDragon.png"
SPRITE_DARK_ON_LIGHT = True  # dragon drawn dark; flip to False if it's light art
SPRITE_THRESHOLD = 128
RESOLUTION = (128, 64)
BAR_MAX = METER_MAX


# --- kipdragon layout: one animation per row, frames left-to-right ----------
# Set FRAME_SIZE and the per-row frame counts to match the actual sheet.
FRAME_SIZE = (32, 32)
ANIMATIONS = {
    "fwd_right": {"row": 0, "frames": 4},  # forward, looking right
    "fwd_left": {"row": 1, "frames": 4},  # forward, looking left
    "back": {"row": 2, "frames": 4},  # moving back (away)
    "left": {"row": 3, "frames": 4},  # moving left
    "right": {"row": 4, "frames": 4},  # moving right
    "idle_smile": {"row": 5, "frames": 4},  # idle smile
    "idle_blink": {"row": 6, "frames": 4},  # idle blink
}
ICON_NAMES = ("energy", "food", "heart", "water", "weight")
BLINK_CHANCE = 0.08  # per idle frame
BLINK_FRAME_TICKS = 1  # blink plays fast


def load_icon(name):
    base = Path(__file__).resolve().parent.joinpath("assets")
    return load_sprite_mask(
        base.joinpath(f"{name}.png")
    )  # reuses the alpha/mask loader


def load_sprite_mask(path):
    """Return a mode-'1' mask where the CHARACTER pixels are 'on' (so draw.bitmap paints them)."""
    img = Image.open(path)
    if "A" in img.getbands():  # transparent PNG -> use alpha
        mask = img.getchannel("A").point(lambda a: 255 if a > 0 else 0)
    else:
        lum = img.convert("L")
        if SPRITE_DARK_ON_LIGHT:  # dark art -> invert so it lights up
            mask = lum.point(lambda p: 255 if p < SPRITE_THRESHOLD else 0)
        else:
            mask = lum.point(lambda p: 255 if p >= SPRITE_THRESHOLD else 0)
    return mask.convert("1", dither=Image.NONE)  # no dithering for crisp sprites


class SpriteAgent:
    """Wanders a dragon around a bounded area with natural, target-based motion."""

    def __init__(self, sheet, frame_size, animations, bounds, rng=None):
        self._sheet = sheet
        self._fw, self._fh = frame_size
        self._anims = animations
        self._max_x = max(0, bounds[0] - self._fw)
        self._max_y = max(0, bounds[1] - self._fh)
        self._rng = rng or random.Random()

        self.x = self._max_x / 2.0
        self.y = self._max_y / 2.0
        self._tx, self._ty = self.x, self.y
        self._speed = 1.5  # px/frame while walking
        self._moving = False
        self._dwell = self._rng.randint(15, 45)
        self._anim = "idle_smile"
        self._frame = 0
        self._tick = 0
        self._cache = {}
        self._last_good = None
        self._blinking = False

    def update(self):
        if self._moving:
            self._move()
        else:
            self._idle()
        self._tick += 1
        self._advance_frame()

    def _advance_frame(self):
        nframes = max(1, self._anims[self._anim]["frames"])
        if self._moving:
            if self._tick % 2 == 0:
                self._frame = (self._frame + 1) % nframes
        elif self._blinking:
            if self._tick % BLINK_FRAME_TICKS == 0:
                self._frame += 1
                if self._frame >= nframes:  # finished -> back to smile
                    self._blinking = False
                    self._set_anim("idle_smile")
        else:
            if self._tick % 5 == 0:
                self._frame = (self._frame + 1) % nframes

    def _move(self):
        dx, dy = self._tx - self.x, self._ty - self.y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= self._speed:  # arrived -> pause
            self.x, self.y = self._tx, self._ty
            self._moving = False
            self._dwell = self._rng.randint(15, 45)
            self._set_anim("idle_smile")
            return
        self.x += self._speed * dx / dist  # constant-speed straight line
        self.y += self._speed * dy / dist
        self._set_anim(self._direction_anim(dx, dy))

    def _idle(self):
        self._dwell -= 1
        if not self._blinking and self._rng.random() < BLINK_CHANCE:
            self._blinking = True
            self._set_anim("idle_blink")  # resets _frame to 0
        if self._dwell <= 0 and not self._blinking:
            self._tx = self._rng.uniform(0, self._max_x)
            self._ty = self._rng.uniform(0, self._max_y)
            self._moving = True

    def _direction_anim(self, dx, dy):
        if abs(dx) >= abs(dy):
            return "right" if dx > 0 else "left"
        if dy > 0:  # toward the viewer = "forward"
            return "fwd_right" if dx >= 0 else "fwd_left"
        return "back"

    def _set_anim(self, name):
        if name != self._anim:
            self._anim = name
            self._frame = 0

    def frame_image(self):
        key = (self._anim, self._frame)
        if key in self._cache:
            return self._cache[key]
        left = self._frame * self._fw
        top = self._anims[self._anim]["row"] * self._fh
        crop = self._sheet.crop((left, top, left + self._fw, top + self._fh))
        if crop.getbbox() is None:  # empty cell -> reuse last good frame
            return self._last_good or crop
        self._last_good = crop  # remember + cache only real frames
        self._cache[key] = crop
        return crop

    def position(self):
        return int(round(self.x)), int(round(self.y))


class OLEDRenderer:
    def __init__(self):
        self._canvas = canvas
        self._device = sh1106(i2c(port=1, address=0x3C))
        sheet_path = (
            Path(__file__).resolve().parent.joinpath("assets", SPRITESHEET_NAME)
        )
        sheet = load_sprite_mask(sheet_path)
        # the dragon roams the left panel, i.e. left of the divider at x=63
        self._agent = SpriteAgent(sheet, FRAME_SIZE, ANIMATIONS, (63, RESOLUTION[1]))
        self._line_h = None
        self._text_top = 0
        self._device.contrast(200)  # 0-255
        self._icons = {name: load_icon(name) for name in ICON_NAMES}

    def render(self, view: ViewModel):
        with self._canvas(self._device) as draw:
            if view.heatmap is not None:
                self._render_heatmap(draw, view)
            else:
                self._render_pet(draw, view)

    def _render_pet(self, draw, view: ViewModel):
        # white left panel + black gutter (x=63..65) separating it from content
        draw.rectangle((0, 0, 62, RESOLUTION[1] - 1), fill="white")
        self._agent.update()
        draw.bitmap(self._agent.position(), self._agent.frame_image(), fill="black")
        draw.text((68, 0), view.title, fill="white", font_size=12)

        line_h = self._text_metrics(draw) - 1
        y = self._render_lines(draw, view, line_h)

        if view.progress:
            for label, level in view.progress:
                self._draw_bar(draw, 68, y, label, level)
                y += 16

    def _render_heatmap(self, draw, view):
        draw.text((2, 0), view.title, fill="white")
        n = max(1, max(len(levels) for _, levels in view.heatmap))
        label_w, gap, right_margin, top, row_gap = 16, 2, 3, 12, 4
        cell = max(4, (RESOLUTION[0] - label_w - right_margin - gap * (n - 1)) // n)

        for row, (label, levels) in enumerate(view.heatmap):
            y0 = top + row * (cell + row_gap)
            self._blit_icon(draw, label, 2, y0, cell)  # icon row label
            for i, level in enumerate(levels):
                x0 = label_w + i * (cell + gap)
                self._fill_cell(draw, x0, y0, x0 + cell - 1, y0 + cell - 1, level)

        ly = top + 2 * (cell + row_gap) + 2
        draw.text((2, ly), "less", fill="white")
        lx = 34
        for level in range(5):
            self._fill_cell(draw, lx, ly, lx + 5, ly + 5, level)
            lx += 7
        draw.text((lx + 4, ly), "more", fill="white")

    def _blit_icon(self, draw, name, x, y, line_h, fill="white"):
        icon = self._icons[name]
        iy = y + max(0, (line_h - icon.height) // 2)
        draw.bitmap((x, iy), icon, fill=fill)
        return icon.width

    def _fill_cell(self, draw, x0, y0, x1, y1, level):
        if level <= 0:
            draw.rectangle((x0, y0, x1, y1), outline="white")  # empty day
            return
        if level >= 4:
            draw.rectangle((x0, y0, x1, y1), fill="white")  # goal met
            return
        draw.rectangle((x0, y0, x1, y1), outline="white")  # 1-3: dithered shade
        for px in range(x0, x1 + 1):
            for py in range(y0, y1 + 1):
                if self._dither(px, py, level):
                    draw.point((px, py), fill="white")

    def _render_lines(self, draw, view, line_h):
        PAD, GAP, top0 = 2, 2, 17
        lines, icons, subs = view.lines, view.icons, view.sublines
        n = len(lines)
        if n == 0:
            return top0

        def has_sub(i):
            return i < len(subs) and subs[i]

        def entry_h(i):
            return line_h + (line_h if has_sub(i) else 0) + 2 * PAD + GAP

        def visible_from(start):
            y, vis = top0, []
            for i in range(start, n):
                if vis and y + entry_h(i) > RESOLUTION[1]:
                    break
                vis.append(i)
                y += entry_h(i)
                if y >= RESOLUTION[1]:
                    break
            return vis

        # scroll so the selected entry stays visible (sits near the bottom, context above)
        start = 0
        sel = view.selected
        if sel is not None:
            start = sel
            while start > 0 and sel in visible_from(start - 1):
                start -= 1

        vis = visible_from(start)
        y = top0
        for i in vis:
            tx = 68
            if i < len(icons) and icons[i]:
                tx = 68 + self._blit_icon(draw, icons[i], 68, y, line_h) + 3
            row_h = line_h + (line_h if has_sub(i) else 0)
            if i == sel:
                self._menu_highlight(draw, y - PAD, y + row_h + PAD)
            draw.text((tx, y - self._text_top), lines[i], fill="white")
            if has_sub(i):
                draw.text((tx + 0, y + line_h - self._text_top), subs[i], fill="white")
            y += entry_h(i)

        if start > 0:
            draw.text((120, 0), "^", fill="white")
        if vis and vis[-1] < n - 1:
            draw.text((120, RESOLUTION[1] - line_h), "v", fill="white")
        return y

    def _menu_highlight(self, draw, top, bottom):
        for py in range(top, bottom):
            if py == top or py == bottom - 1:
                draw.point((67, py), fill="white")
                draw.point((68, py), fill="white")
                draw.point((69, py), fill="white")
            else:
                draw.point((66, py), fill="white")

    @staticmethod
    def _dither(px, py, level):
        if level == 1:
            return (px + py) % 3 == 0  # sparse
        if level == 2:
            return (px + py) % 2 == 0  # checkerboard
        return (px + py) % 3 != 0  # dense

    def _draw_bar(self, draw, x: int, y: int, label: str, filled: int):
        line_h = self._text_metrics(draw)
        icon_w = self._blit_icon(draw, label, x, y, line_h)  # label is an icon name
        gap = 3
        bar_x = x + icon_w + gap
        bar_y = y + 1
        height = 7
        bottom = bar_y + height
        right = RESOLUTION[0] - 3

        self._bar_cap(draw, bar_x, bar_y, bottom, +1)
        self._bar_cap(draw, right, bar_y, bottom, -1)

        inner_left, inner_right = bar_x + 2, right - 2
        fraction = max(0, min(filled, BAR_MAX)) / BAR_MAX
        fill_w = round((inner_right - inner_left) * fraction)
        top, bot = bar_y + 2, bottom - 2
        for sx in range(inner_left, inner_left + fill_w, 3):
            draw.rectangle(
                (sx, top, min(sx + 1, inner_left + fill_w - 1), bot), fill="white"
            )

    def _bar_cap(self, draw, cx: int, top_y: int, bottom_y: int, facing: int):
        # vertical edge
        for py in range(top_y, bottom_y + 1):
            draw.point((cx, py), fill="white")
        # 3px serifs at top & bottom, pointing inward (facing +1 = right, -1 = left)
        for d in (1, 2, 3):
            draw.point((cx + facing * d, top_y), fill="white")
            draw.point((cx + facing * d, bottom_y), fill="white")

    def _current_frame(self):
        frame_number = self._frame_index % self._frame_count
        column = frame_number % 10
        row = frame_number // 10
        left = column * self._frame_width
        top = row * self._frame_height
        right = left + self._frame_width
        bottom = top + self._frame_height
        return self._sheet_image.crop((left, top, right, bottom))

    def _text_metrics(self, draw):
        if self._line_h is None:
            # "ApqY" spans ascenders + descenders -> full glyph box
            _, top, _, bottom = draw.textbbox((0, 0), "ApqY")
            self._line_h = bottom - top
            self._text_top = top
        return self._line_h


def main():
    parser = argparse.ArgumentParser(description="Welp wellness tamagotchi")
    parser.add_argument(
        "--save",
        dest="save_path",
        default=str(Path(__file__).resolve().parent / "welp_state.json"),
        help="Path to the save file (handy for demos/tests)",
    )
    args = parser.parse_args()

    app = WelpApp(save_path=args.save_path)
    renderer = OLEDRenderer()

    from UnitTests.input_handler_3button import InputHandler3Buttons

    input_handler = InputHandler3Buttons(on_button=app.handle_button)

    try:
        while True:
            _ = input_handler
            view = app.build_view()
            renderer.render(view)
            app.maybe_save()
            time.sleep(0.1)
    except KeyboardInterrupt:
        return
    finally:
        app.save()


if __name__ == "__main__":
    main()
