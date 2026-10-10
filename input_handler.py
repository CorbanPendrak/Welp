import threading
from gpiozero import Button, MCP3008

class InputHandler:
    def __init__(self, a_pin, b_pin, x_axis_channel, y_axis_channel, joystick_threshold): # joystick_threshold from 0-1
        self.a_button = Button(a_pin)
        self.b_button = Button(b_pin)

        self.x_axis = MCP3008(channel=x_axis_channel)
        self.y_axis = MCP3008(channel=y_axis_channel)
        self.joystick_threshold = joystick_threshold

        joystick_thread = threading.Thread(target=self.joystick_thread_target)
        joystick_thread.start()

        self.a_button.when_deactivated(lambda: self.button_pressed('A'))
        self.b_button.when_deactivated(lambda: self.button_pressed('B'))


    def button_pressed(self, button): # callback for buttons being pressed
        if button == 'A':
            print("You pressed the A button!")
        if button == 'B':
            print("You pressed the B button!")


    def joystick_callback(self, axis, dir): # callback for joysticks to count as a directional input
        print(f"The joystick was pressed on the {axis} axis in the {dir} direction")


    def joystick_thread_target(self):
        while True:
            try:
                axis = [self.x_axis, self.y_axis]
                for i in range(2):
                    if axis[i].value < 1-self.joystick_threshold:
                        self.joystick_callback(i, 0)
                    if axis[i].value > self.joystick_threshold:
                        self.joystick_callback(i, 1)
            except KeyboardInterrupt:
                continue


