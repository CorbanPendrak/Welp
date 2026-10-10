from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from welp_app import ViewModel, WelpApp

SPRITESHEET_NAME = 'runner.png'
RESOLUTION = (128, 64)


class OLEDRenderer:
    def __init__(self):
        from luma.core.interface.serial import i2c
        from luma.core.render import canvas
        from luma.oled.device import sh1106

        self._canvas = canvas
        self._device = sh1106(i2c(port=1, address=0x3C))
        sheet_path = Path(__file__).resolve().parent.joinpath('assets', SPRITESHEET_NAME)
        self._sheet_image = Image.open(sheet_path).convert('1')
        self._frame_width = 64
        self._frame_height = 69
        self._frame_count = self._sheet_image.width // self._frame_width
        self._frame_index = 0

    def render(self, view: ViewModel):
        with self._canvas(self._device) as draw:
            draw.line((63, 0, 63, RESOLUTION[1]), fill='white')
            draw.bitmap((0, 0), self._current_frame(), fill='white')
            draw.text((68, 0), view.title, fill='white')

            y = 12
            for line in view.lines:
                draw.text((68, y), line, fill='white')
                y += 10

            if view.progress:
                for label, level in view.progress:
                    self._draw_bar(draw, 68, y, label, level)
                    y += 16

            self._frame_index = (self._frame_index + 1) % self._frame_count

    def _draw_bar(self, draw, x: int, y: int, label: str, filled: int):
        draw.text((x, y), f'{label}:', fill='white')
        bar_y = y + 8
        for index in range(5):
            left = x + index * 10
            right = left + 7
            bottom = bar_y + 6
            if index < filled:
                draw.rectangle((left, bar_y, right, bottom), outline='white', fill='white')
            else:
                draw.rectangle((left, bar_y, right, bottom), outline='white')

    def _current_frame(self):
        frame_number = self._frame_index % self._frame_count
        column = frame_number % 10
        row = frame_number // 10
        left = column * self._frame_width
        top = row * self._frame_height
        right = left + self._frame_width
        bottom = top + self._frame_height
        return self._sheet_image.crop((left, top, right, bottom))


def main():
    app = WelpApp()
    renderer = OLEDRenderer()

    from UnitTests.input_handler_3button import InputHandler3Buttons

    input_handler = InputHandler3Buttons(on_button=app.handle_button)

    try:
        while True:
            _ = input_handler
            view = app.build_view()
            renderer.render(view)
            time.sleep(0.1)
    except KeyboardInterrupt:
        return


if __name__ == '__main__':
    main()
