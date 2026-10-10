import threading
from gpiozero import Button, MCP3008

class InputHandler3Buttons:
    def __init__(self, left_pin=22, right_pin=17, select_pin=27): # joystick_threshold from 0-1
        self.left_button = Button(left_pin)
        self.right_button = Button(right_pin)
        self.select_button = Button(select_pin)

        self.left_button.when_deactivated(lambda: self.button_pressed('Left'))
        self.right_button.when_deactivated(lambda: self.button_pressed('Right'))
        self.select_button.when_deactivated(lambda: self.button_pressed('Select'))


    def button_pressed(self, button): # callback for buttons being pressed
        if button == 'Left':
            print("You pressed the Left button!")
        if button == 'Right':
            print("You pressed the Right button!")
        if button == 'Select':
            print("You pressed the Select button!")

