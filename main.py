from luma.core.interface.serial import i2c, spi, pcf8574
from luma.core.interface.parallel import bitbang_6800
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1309, ssd1325, ssd1331, sh1106, sh1107, ws0010
from PIL import ImageFont, ImageDraw, Image

RESOLUTION = (128, 64)

serial = i2c(port=1, address=0x3C)

device = sh1106(serial)

class Display:
    def __init__(self, animation, title, panel):
        self.animation = animation
        self.title = title
        self.panel = panel

    def set_panel(self, panel):
        self.panel = panel

    def set_animation(self, animation):
        self.animation = animation

    def render(self):
        with canvas(self.panel) as draw:
            curAnim = Image.open(self.animation)

            font = ImageFont.load_default()
            draw.text(((RESOLUTION[0]/2) + 3, 0), self.title, font=font, fill="white")
            draw.bitmap((0, 0), curAnim, fill="white")
            draw.bitmap((RESOLUTION[0]/2, RESOLUTION[1]/2), self.panel, fill="white") # panel may end up being a class or something but for now...