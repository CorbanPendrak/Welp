try:
    from gpiozero import Button
except ImportError:
    class Button:
        def __init__(self, pin):
            self.pin = pin
            self.when_pressed = None


class _DummyButton:
    def __init__(self, pin):
        self.pin = pin
        self.when_pressed = None


class InputHandler3Buttons:
    def __init__(self, left_pin=22, right_pin=17, select_pin=27, on_button=None):
        self.on_button = on_button or self._default_button_handler

        try:
            self.left_button = Button(left_pin)
            self.right_button = Button(right_pin)
            self.select_button = Button(select_pin)
        except Exception:
            self.left_button = _DummyButton(left_pin)
            self.right_button = _DummyButton(right_pin)
            self.select_button = _DummyButton(select_pin)

        self.left_button.when_pressed = lambda: self.button_pressed('Left')
        self.right_button.when_pressed = lambda: self.button_pressed('Right')
        self.select_button.when_pressed = lambda: self.button_pressed('Select')

    def _default_button_handler(self, button):
        print(f"You pressed the {button} button!")

    def button_pressed(self, button):
        self.on_button(button)

