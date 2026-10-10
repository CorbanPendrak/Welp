import sys

from luma.core.interface.serial import i2c, spi, pcf8574
from luma.core.interface.parallel import bitbang_6800
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1309, ssd1325, ssd1331, sh1106, sh1107, ws0010

from PIL import ImageFont, ImageDraw, Image

from pathlib import Path

from luma.core.sprite_system import spritesheet, framerate_regulator

SPRITESHEET_NAME = 'character.png'

RESOLUTION = (128, 64)

serial = i2c(port=1, address=0x3C)

device = sh1106(serial)

data = {
    'image': str(Path(__file__).resolve().parent.joinpath('images', SPRITESHEET_NAME)),
    'frames': {
        'width': 64,
        'height': 64,
        'regX': 0,
        'regY': 0
    },
    'animations': {
        'run-right': {
            'frames': range(19, 9, -1),
            'next': "run-right",
        },
        'run-left': {
            'frames': range(0, 10),
            'next': "run-left"
        }
    }
    }

regulator = framerate_regulator()
sheet = spritesheet(**data)


class Display:
    def __init__(self, animation, title, panel):
        self.animation = animation
        self.title = title
        self.panel = panel
        self.regulator = framerate_regulator()
        self.sheet = spritesheet(**data)
        self.runner = self.sheet.animate(self.animation, loop=False)

    def set_panel(self, panel):
        self.panel = panel

    def set_animation(self, animation, duration=sys.maxsize):
        self.animation = animation
        self.runner = self.sheet.animate(self.animation, loop=False)
        while duration > 0:
            with self.regulator:
                self.render()
            duration -= 1

    def render(self):
        with canvas(device) as draw:
            draw.text((RESOLUTION[0] // 2 + 3, 0), self.title, fill="white")
            frame = next(self.runner)
            draw.bitmap((0, 0), frame, fill="white")
            draw.bitmap((RESOLUTION[0]//2 + 3, RESOLUTION[1]//2), frame, fill="white")

