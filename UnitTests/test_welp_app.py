import unittest
import importlib
from unittest.mock import patch

from PIL import Image

from welp_app import WelpApp


class FakeButton:
    def __init__(self, pin):
        self.pin = pin
        self.when_pressed = None


class WelpAppTests(unittest.TestCase):
    def setUp(self):
        self.app = WelpApp()

    def test_left_and_right_cycle_tabs_from_the_overview(self):
        view = self.app.build_view()
        self.assertEqual(view.title, 'Pet Stats')
        self.assertEqual(view.lines[0], 'E □□□□')

        self.app.handle_button('right')
        view = self.app.build_view()
        self.assertEqual(view.title, 'Workout')
        self.assertEqual(view.lines[0], 'P: 0')

        self.app.handle_button('right')
        view = self.app.build_view()
        self.assertEqual(view.title, 'Nutrition')
        self.assertEqual(view.lines[0], 'F: 0')

        self.app.handle_button('right')
        view = self.app.build_view()
        self.assertEqual(view.title, 'Pet Stats')

    def test_select_opens_workout_menu_and_detail(self):
        self.app.handle_button('right')
        self.app.handle_button('select')
        view = self.app.build_view()
        self.assertEqual(view.title, 'Select')
        self.assertEqual(view.lines, ('> Pushups', '  Squats', '  Back'))

        self.app.handle_button('select')
        view = self.app.build_view()
        self.assertEqual(view.title, 'Pushups')
        self.assertEqual(view.lines[0], '< 0 >')

        self.app.handle_button('right')
        self.app.handle_button('right')
        self.app.handle_button('select')
        self.assertEqual(self.app.build_view().title, 'Select')

    def test_pet_stats_graph_caps_at_five_bars(self):
        self.app.state.exercise_progress = 5
        self.app.state.water_progress = 2
        self.app.state.screen = 'pet_detail'

        view = self.app.build_view()
        self.assertEqual(view.title, 'Pet Stats')
        self.assertEqual(view.lines[0], 'E ####')
        self.assertEqual(view.lines[1], 'H ##□□')

    def test_workout_overview_reports_totals(self):
        self.app.state.tab_index = 1
        self.app.state.workout_counts['Pushups'] = 3
        self.app.state.workout_counts['Squats'] = 2

        view = self.app.build_view()
        self.assertEqual(view.title, 'Workout')
        self.assertEqual(view.lines[0], 'P: 3')
        self.assertEqual(view.lines[1], 'S: 2')

    def test_nutrition_overview_reports_totals(self):
        self.app.state.tab_index = 2
        self.app.state.nutrition_counts['Food'] = 1
        self.app.state.nutrition_counts['Water'] = 2

        view = self.app.build_view()
        self.assertEqual(view.title, 'Nutrition')
        self.assertEqual(view.lines[0], 'F: 1')
        self.assertEqual(view.lines[1], 'W: 2')


class InputHandlerTests(unittest.TestCase):
    def test_input_handler_dispatches_button_names(self):
        module = importlib.import_module('UnitTests.input_handler_3button')
        with patch.object(module, 'Button', FakeButton):
            InputHandler3Buttons = module.InputHandler3Buttons

            pressed = []
            handler = InputHandler3Buttons(on_button=pressed.append)

            handler.left_button.when_pressed()
            handler.right_button.when_pressed()
            handler.select_button.when_pressed()

            self.assertEqual(pressed, ['Left', 'Right', 'Select'])

    def test_input_handler_falls_back_when_gpio_buttons_cannot_initialize(self):
        module = importlib.import_module('UnitTests.input_handler_3button')

        class RaisingButton:
            def __init__(self, pin):
                raise OSError('gpio unavailable')

        with patch.object(module, 'Button', RaisingButton):
            InputHandler3Buttons = module.InputHandler3Buttons

            pressed = []
            handler = InputHandler3Buttons(on_button=pressed.append)

            handler.left_button.when_pressed()
            handler.right_button.when_pressed()
            handler.select_button.when_pressed()

            self.assertEqual(pressed, ['Left', 'Right', 'Select'])


class SpriteFrameTests(unittest.TestCase):
    def test_runner_sheet_contains_twenty_frames(self):
        sheet = Image.open('assets/runner.png').convert('1')
        frame_width = 64
        frame_height = 69

        self.assertEqual(sheet.width // frame_width, 10)
        self.assertEqual(sheet.height // frame_height, 2)

        frames = []
        for row in range(2):
            for col in range(10):
                frame = sheet.crop((
                    col * frame_width,
                    row * frame_height,
                    (col + 1) * frame_width,
                    (row + 1) * frame_height,
                ))
                frames.append(frame.size)

        self.assertEqual(len(frames), 20)
        self.assertTrue(all(size == (64, 69) for size in frames))


if __name__ == '__main__':
    unittest.main()