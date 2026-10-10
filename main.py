import sys
import threading

from luma.core.interface.serial import i2c, spi, pcf8574
from luma.core.interface.parallel import bitbang_6800
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1309, ssd1325, ssd1331, sh1106, sh1107, ws0010
from luma.core.sprite_system import spritesheet, framerate_regulator

from PIL import ImageFont, ImageDraw, Image

from pathlib import Path

import random

SPRITESHEET_NAME = 'character.png'

RESOLUTION = (128, 64)

serial = i2c(port=1, address=0x3C)

device = sh1106(serial)

data = {
    'image': str(Path(__file__).resolve().parent.joinpath('images', SPRITESHEET_NAME)),
    'frames': {
        'width': 32,
        'height': 32,
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
        self.frame = next(self.runner)
        self.dragon_position = (RESOLUTION[0] // 4, RESOLUTION[1] // 4)
        #safe zone 0 0 to 32 32
        self.wander_path = [[8, 25], [27, 12], [16, 16], [4, 19], [20, 10], [18, 15], [9, 12], [20, 29]]

    def set_panel(self, panel):
        self.panel = panel

    def set_animation(self, animation, duration=sys.maxsize):
        self.animation = animation
        self.runner = self.sheet.animate(self.animation, loop=False)
        while duration > 0:
            with self.regulator:
                self.frame = next(self.runner)
                self.render()
            duration -= 1

    def start_wander(self):
        self.wander_thread = threading.Thread(target=self.wander)
        self.wander_thread.start()

    def stop_wander(self):
        if hasattr(self, 'wander_thread'):
            self.wander_thread.join()
            del self.wander_thread

    def set_title(self, title):
        self.title = title
        self.render()
    
    def wander(self, duration=sys.maxsize):
        self.animation = "run-right"
        self.runner = self.sheet.animate(self.animation, loop=True)

        direction = [random.choice([-1, 0, 1]), random.choice([-1, 0, 1])]
        length = random.randint(5, 15)
        pause = random.randint(30, 40)
        while duration > 0:
            with self.regulator:
                if length <= 0:
                    if pause > 0:
                        pause -= 1
                    else:
                        direction = [random.choice([-1, 0, 1]), random.choice([-1, 0, 1])]
                        length = random.randint(5, 15)
                        pause = random.randint(30, 40)
                else:
                    self.frame = next(self.runner)
                    
                    if (self.dragon_position[0] < 1 or self.dragon_position[0] > RESOLUTION[0]/2 - 33 or
                        self.dragon_position[1] < 1 or self.dragon_position[1] > RESOLUTION[1] - 33):
                        direction = [random.choice([-1, 0, 1]), random.choice([-1, 0, 1])]
                        length = random.randint(5, 15)
                    else:
                        self.dragon_position[0] += direction[0]
                        self.dragon_position[1] += direction[1]
                
                self.render()
                
            duration -= 1

    def render(self):
        with canvas(device) as draw:
            draw.text((RESOLUTION[0] // 2 + 3, 0), self.title, fill="white")
            draw.bitmap((self.dragon_position[0], self.dragon_position[1]), self.frame)
            draw.bitmap((RESOLUTION[0]//2 + 3, RESOLUTION[1]//2), self.panel)

