from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock


TAB_LABELS = ('P', 'W', 'N')
WORKOUT_OPTIONS = ('Pushups', 'Squats', 'Back')
NUTRITION_OPTIONS = ('Food', 'Water', 'Back')


@dataclass(frozen=True)
class ViewModel:
    title: str
    lines: tuple[str, ...]
    progress: tuple[tuple[str, int], ...] = ()


@dataclass
class WelpState:
    tab_index: int = 0
    screen: str = 'overview'
    workout_index: int = 0
    nutrition_index: int = 0
    workout_counts: dict[str, int] = field(default_factory=lambda: {'Pushups': 0, 'Squats': 0})
    nutrition_counts: dict[str, int] = field(default_factory=lambda: {'Food': 0, 'Water': 0})
    exercise_progress: int = 0
    water_progress: int = 0


class WelpApp:
    def __init__(self):
        self.state = WelpState()
        self._lock = RLock()

    def handle_button(self, button: str):
        button = button.strip().lower()

        with self._lock:
            if self.state.screen == 'overview':
                self._handle_overview_button(button)
            elif self.state.screen == 'pet_detail':
                if button == 'select':
                    self.state.screen = 'overview'
            elif self.state.screen == 'workout_menu':
                self._handle_workout_menu_button(button)
            elif self.state.screen == 'workout_detail':
                self._handle_workout_detail_button(button)
            elif self.state.screen == 'nutrition_menu':
                self._handle_nutrition_menu_button(button)
            elif self.state.screen == 'nutrition_detail':
                self._handle_nutrition_detail_button(button)

    def build_view(self) -> ViewModel:
        with self._lock:
            tab = TAB_LABELS[self.state.tab_index]

            if self.state.screen == 'overview':
                return self._build_overview_view(tab)

            if self.state.screen == 'pet_detail':
                return ViewModel(
                    title='Pet Stats',
                    lines=(
                        f'E {self._bar(self.state.exercise_progress, 4)}',
                        f'H {self._bar(self.state.water_progress, 4)}',
                    ),
                )

            if self.state.screen == 'workout_menu':
                return ViewModel(
                    title='Select',
                    lines=self._menu_lines(WORKOUT_OPTIONS, self.state.workout_index),
                )

            if self.state.screen == 'workout_detail':
                active_name = WORKOUT_OPTIONS[self.state.workout_index]
                count = self.state.workout_counts[active_name]
                return ViewModel(
                    title=active_name,
                    lines=(f'< {count} >',),
                )

            if self.state.screen == 'nutrition_menu':
                return ViewModel(
                    title='Select',
                    lines=self._menu_lines(NUTRITION_OPTIONS, self.state.nutrition_index),
                )

            if self.state.screen == 'nutrition_detail':
                active_name = NUTRITION_OPTIONS[self.state.nutrition_index]
                count = self.state.nutrition_counts[active_name]
                return ViewModel(
                    title=active_name,
                    lines=(f'< {count} >',),
                )

            raise ValueError(f'Unknown screen: {self.state.screen}')

    def _build_overview_view(self, tab: str) -> ViewModel:
        if tab == 'P':
            return ViewModel(
                title='Pet Stats',
                lines=(
                    f'E {self._bar(self.state.exercise_progress, 4)}',
                    f'H {self._bar(self.state.water_progress, 4)}',
                ),
            )

        if tab == 'W':
            return ViewModel(
                title='Workout',
                lines=(
                    f'P: {self.state.workout_counts["Pushups"]}',
                    f'S: {self.state.workout_counts["Squats"]}',
                ),
            )

        return ViewModel(
            title='Nutrition',
            lines=(
                f'F: {self.state.nutrition_counts["Food"]}',
                f'W: {self.state.nutrition_counts["Water"]}',
            ),
        )

    def _handle_overview_button(self, button: str):
        if button == 'left':
            self.state.tab_index = (self.state.tab_index - 1) % len(TAB_LABELS)
        elif button == 'right':
            self.state.tab_index = (self.state.tab_index + 1) % len(TAB_LABELS)
        elif button == 'select':
            tab = TAB_LABELS[self.state.tab_index]
            if tab == 'P':
                self.state.screen = 'pet_detail'
            elif tab == 'W':
                self.state.screen = 'workout_menu'
            elif tab == 'N':
                self.state.screen = 'nutrition_menu'

    def _handle_workout_menu_button(self, button: str):
        if button == 'left':
            self.state.workout_index = (self.state.workout_index - 1) % len(WORKOUT_OPTIONS)
        elif button == 'right':
            self.state.workout_index = (self.state.workout_index + 1) % len(WORKOUT_OPTIONS)
        elif button == 'select':
            choice = WORKOUT_OPTIONS[self.state.workout_index]
            if choice == 'Back':
                self.state.screen = 'overview'
            else:
                self.state.screen = 'workout_detail'

    def _handle_workout_detail_button(self, button: str):
        active_name = WORKOUT_OPTIONS[self.state.workout_index]
        if button == 'left':
            self._set_workout_count(active_name, -1)
        elif button == 'right':
            self._set_workout_count(active_name, 1)
        elif button == 'select':
            self.state.screen = 'workout_menu'

    def _handle_nutrition_menu_button(self, button: str):
        if button == 'left':
            self.state.nutrition_index = (self.state.nutrition_index - 1) % len(NUTRITION_OPTIONS)
        elif button == 'right':
            self.state.nutrition_index = (self.state.nutrition_index + 1) % len(NUTRITION_OPTIONS)
        elif button == 'select':
            choice = NUTRITION_OPTIONS[self.state.nutrition_index]
            if choice == 'Back':
                self.state.screen = 'overview'
            else:
                self.state.screen = 'nutrition_detail'

    def _handle_nutrition_detail_button(self, button: str):
        active_name = NUTRITION_OPTIONS[self.state.nutrition_index]
        if button == 'left':
            self._set_nutrition_count(active_name, -1)
        elif button == 'right':
            self._set_nutrition_count(active_name, 1)
        elif button == 'select':
            self.state.screen = 'nutrition_menu'

    def _set_workout_count(self, workout: str, delta: int):
        next_value = max(0, self.state.workout_counts[workout] + delta)
        self.state.workout_counts[workout] = next_value
        self.state.exercise_progress = min(5, next_value)

    def _set_nutrition_count(self, nutrition: str, delta: int):
        next_value = max(0, self.state.nutrition_counts[nutrition] + delta)
        self.state.nutrition_counts[nutrition] = next_value
        if nutrition == 'Water':
            self.state.water_progress = min(5, next_value)

    def _menu_lines(self, options: tuple[str, ...], selected_index: int) -> tuple[str, ...]:
        lines = []
        for index, option in enumerate(options):
            prefix = '> ' if index == selected_index else '  '
            lines.append(f'{prefix}{option}')
        return tuple(lines)

    def _bar(self, value: int, maximum: int = 5) -> str:
        filled = min(max(value, 0), maximum)
        return ''.join('#' if index < filled else '□' for index in range(maximum))