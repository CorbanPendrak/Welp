from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from threading import RLock

TAB_LABELS = ("P", "E", "N", "I", "S")
WORKOUT_OPTIONS = ("Pushups", "Squats", "Back")
NUTRITION_OPTIONS = ("Food", "Water", "Back")
GOAL_OPTIONS = ("Pushups", "Squats", "Food", "Water", "Back")

METER_MAX = 100  # exported for BAR_MAX in main.py

DEFAULT_GOALS = {"Pushups": 50, "Squats": 50, "Food": 3, "Water": 8}  # per day
DECAY = {"Pushups": 2.5, "Squats": 2.5, "Food": 5.0, "Water": 7.0}  # pts/hour
NEGLECT_RATE = 10.0  # pts/hour while a meter is 0
NEGLECT_CAP = 50.0
GOAL_MIN = 1
HISTORY_DAYS = 60
HEATMAP_DAYS = 7


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class ViewModel:
    title: str
    lines: tuple[str, ...]
    progress: tuple[tuple[str, int], ...] = ()
    selected: int | None = None
    heatmap: tuple[tuple[str, tuple[int, ...]], ...] | None = None
    icons: tuple[str | None, ...] = ()
    sublines: tuple[str | None, ...] = ()


@dataclass
class WelpState:
    tab_index: int = 0
    screen: str = "overview"
    workout_index: int = 0
    nutrition_index: int = 0

    # today's logs
    workout_counts: dict[str, int] = field(
        default_factory=lambda: {"Pushups": 0, "Squats": 0}
    )
    nutrition_counts: dict[str, int] = field(
        default_factory=lambda: {"Food": 0, "Water": 0}
    )

    # living engine
    meters: dict[str, float] = field(
        default_factory=lambda: {
            "Pushups": 50.0,
            "Squats": 50.0,
            "Food": 50.0,
            "Water": 50.0,
        }
    )
    last_update: float = field(default_factory=time.time)
    happiness: float = 100.0
    health: float = 50.0
    nourishment: float = 50.0
    fitness: float = 50.0
    streak: int = 0
    streak_bonus: float = 0.0
    neglect: float = 0.0

    # daily-rollover accumulators
    day_key: str | None = None
    day_happiness_sum: float = 0.0
    day_samples: int = 0
    day_min_nourishment: float = 100.0
    day_min_fitness: float = 100.0

    # Goals
    settings_index: int = 0
    goals: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_GOALS))
    history: dict[str, dict[str, float]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "WelpState":
        """Overlay saved values onto defaults so old save files survive upgrades."""
        state = cls()
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state


class WelpApp:
    def __init__(self, save_path: str | os.PathLike | None = None):
        self._save_path = str(save_path) if save_path else None
        self._lock = RLock()
        self._dirty = False
        self._last_save = 0.0
        self._save_interval = 3.0
        self.state = self._load() or WelpState()
        with self._lock:
            self._tick()

    def _load(self) -> "WelpState | None":
        if not self._save_path or not os.path.exists(self._save_path):
            return None
        try:
            with open(self._save_path, "r") as fh:
                return WelpState.from_dict(json.load(fh))
        except (OSError, ValueError):
            return None  # corrupt/missing -> start fresh

    def _save(self):
        if not self._save_path:
            return
        tmp = f"{self._save_path}.tmp"
        try:
            with open(tmp, "w") as fh:
                json.dump(asdict(self.state), fh)
            os.replace(tmp, self._save_path)  # atomic swap
        except OSError:
            pass

    def maybe_save(self, force: bool = False):
        with self._lock:
            if not self._save_path or (not self._dirty and not force):
                return
            now = time.time()
            if force or now - self._last_save >= self._save_interval:
                self._save()
                self._dirty = False
                self._last_save = now

    def save(self):
        self.maybe_save(force=True)

    def handle_button(self, button: str):
        button = button.strip().lower()
        with self._lock:
            if self.state.screen == "overview":
                self._handle_overview_button(button)
            elif self.state.screen == "pet_detail":
                if button == "select":
                    self.state.screen = "overview"
            elif self.state.screen == "exercise_menu":
                self._handle_exercise_menu_button(button)
            elif self.state.screen == "workout_detail":
                self._handle_workout_detail_button(button)
            elif self.state.screen == "nutrition_menu":
                self._handle_nutrition_menu_button(button)
            elif self.state.screen == "nutrition_detail":
                self._handle_nutrition_detail_button(button)
            elif self.state.screen == "info":
                if button == "select":
                    self.state.screen = "overview"
            elif self.state.screen == "settings_menu":
                self._handle_settings_menu_button(button)
            elif self.state.screen == "settings_detail":
                self._handle_settings_detail_button(button)
            self._dirty = True

    def build_view(self) -> ViewModel:
        with self._lock:
            self._tick()
            tab = TAB_LABELS[self.state.tab_index]

            if self.state.screen == "overview":
                return self._build_overview_view(tab)

            if self.state.screen == "pet_detail":
                return self._build_pet_view()

            if self.state.screen == "exercise_menu":
                return ViewModel(
                    title="Workout",
                    lines=WORKOUT_OPTIONS,
                    selected=self.state.workout_index,
                )

            if self.state.screen == "workout_detail":
                active_name = WORKOUT_OPTIONS[self.state.workout_index]
                count = self.state.workout_counts[active_name]
                return ViewModel(
                    title=active_name,
                    lines=(f"< {count} >",),
                )

            if self.state.screen == "nutrition_menu":
                return ViewModel(
                    title="Nutrition",
                    lines=NUTRITION_OPTIONS,
                    selected=self.state.nutrition_index,
                )

            if self.state.screen == "nutrition_detail":
                active_name = NUTRITION_OPTIONS[self.state.nutrition_index]
                count = self.state.nutrition_counts[active_name]
                return ViewModel(
                    title=active_name,
                    lines=(f"< {count} >",),
                )

            if self.state.screen == "info":
                return self._build_info_view()

            if self.state.screen == "settings_menu":
                return self._build_settings_view()

            if self.state.screen == "settings_detail":
                return self._build_goal_detail_view()

            raise ValueError(f"Unknown screen: {self.state.screen}")

    def _handle_overview_button(self, button: str):
        if button == "left":
            self.state.tab_index = (self.state.tab_index - 1) % len(TAB_LABELS)
        elif button == "right":
            self.state.tab_index = (self.state.tab_index + 1) % len(TAB_LABELS)
        elif button == "select":
            screen = {
                "P": "pet_detail",
                "E": "exercise_menu",
                "N": "nutrition_menu",
                "I": "info",
                "S": "settings_menu",
            }[TAB_LABELS[self.state.tab_index]]
            self.state.screen = screen

    def _build_overview_view(self, tab: str) -> ViewModel:
        if tab == "P":
            return self._build_pet_view()
        if tab == "E":
            g, wc = self.state.goals, self.state.workout_counts
            return ViewModel(
                title="Exercise",
                lines=(
                    f"P: {wc['Pushups']} / {g['Pushups']}",
                    f"S: {wc['Squats']} / {g['Squats']}",
                ),
            )
        if tab == "N":
            g, nc = self.state.goals, self.state.nutrition_counts
            return ViewModel(
                title="Nutrition",
                lines=(f"{nc['Food']} / {g['Food']}", f"{nc['Water']} / {g['Water']}"),
                icons=("food", "water"),
            )
        if tab == "I":
            return ViewModel(title="Info", lines=("Press OK",))
        return ViewModel(title="Setup", lines=("Press OK",))  # tab == "S"

    def _handle_exercise_menu_button(self, button: str):
        if button == "left":
            self.state.workout_index = (self.state.workout_index - 1) % len(
                WORKOUT_OPTIONS
            )
        elif button == "right":
            self.state.workout_index = (self.state.workout_index + 1) % len(
                WORKOUT_OPTIONS
            )
        elif button == "select":
            choice = WORKOUT_OPTIONS[self.state.workout_index]
            if choice == "Back":
                self.state.screen = "overview"
            else:
                self.state.screen = "workout_detail"

    def _handle_workout_detail_button(self, button: str):
        active_name = WORKOUT_OPTIONS[self.state.workout_index]
        if button == "left":
            self._set_workout_count(active_name, -1)
        elif button == "right":
            self._set_workout_count(active_name, 1)
        elif button == "select":
            self.state.screen = "exercise_menu"

    def _handle_nutrition_menu_button(self, button: str):
        if button == "left":
            self.state.nutrition_index = (self.state.nutrition_index - 1) % len(
                NUTRITION_OPTIONS
            )
        elif button == "right":
            self.state.nutrition_index = (self.state.nutrition_index + 1) % len(
                NUTRITION_OPTIONS
            )
        elif button == "select":
            choice = NUTRITION_OPTIONS[self.state.nutrition_index]
            if choice == "Back":
                self.state.screen = "overview"
            else:
                self.state.screen = "nutrition_detail"

    def _handle_nutrition_detail_button(self, button: str):
        active_name = NUTRITION_OPTIONS[self.state.nutrition_index]
        if button == "left":
            self._set_nutrition_count(active_name, -1)
        elif button == "right":
            self._set_nutrition_count(active_name, 1)
        elif button == "select":
            self.state.screen = "nutrition_menu"

    def _set_workout_count(self, workout: str, delta: int):
        before = self.state.workout_counts[workout]
        self.state.workout_counts[workout] = max(0, before + delta)
        self._log(workout, self.state.workout_counts[workout] - before)

    def _set_nutrition_count(self, nutrition: str, delta: int):
        before = self.state.nutrition_counts[nutrition]
        self.state.nutrition_counts[nutrition] = max(0, before + delta)
        self._log(nutrition, self.state.nutrition_counts[nutrition] - before)

    def _build_pet_view(self) -> ViewModel:
        return ViewModel(
            title=self._mood(),
            lines=(),
            progress=(
                ("food", round(self.state.nourishment)),
                ("energy", round(self.state.fitness)),
                ("heart", round(self.state.health)),
            ),
        )

    def _tick(self):
        """Lazily catch up decay + rollover based on wall-clock time. Cheap to call often."""
        now = time.time()
        dt = (now - self.state.last_update) / 3600.0  # hours elapsed
        if dt > 0:
            for name in self.state.meters:
                self.state.meters[name] = _clamp(
                    self.state.meters[name] - DECAY[name] * dt, 0, METER_MAX
                )
            starving = min(self.state.meters.values()) <= 0
            step = NEGLECT_RATE * dt * (1 if starving else -1)
            self.state.neglect = _clamp(self.state.neglect + step, 0, NEGLECT_CAP)
            self.state.last_update = now
        self._maybe_rollover(now)
        self._recompute()
        self._accumulate_day()

    def _log(self, activity: str, amount: int):
        if amount == 0:
            return
        self._tick()
        gain = METER_MAX * amount / self.state.goals[activity]
        self.state.meters[activity] = _clamp(
            self.state.meters[activity] + gain, 0, METER_MAX
        )
        self._recompute()

    def _recompute(self):
        m = self.state.meters
        self.state.nourishment = 0.4 * m["Water"] + 0.6 * m["Food"]
        self.state.fitness = 0.5 * m["Pushups"] + 0.5 * m["Squats"]
        needs = (self.state.nourishment, self.state.fitness)
        base = 0.4 * (sum(needs) / 2) + 0.6 * min(needs)  # weakest-link mood
        self.state.happiness = _clamp(
            base + self.state.streak_bonus - self.state.neglect, 0, METER_MAX
        )

    def _accumulate_day(self):
        self.state.day_happiness_sum += self.state.happiness
        self.state.day_samples += 1
        self.state.day_min_nourishment = min(
            self.state.day_min_nourishment, self.state.nourishment
        )
        self.state.day_min_fitness = min(self.state.day_min_fitness, self.state.fitness)

    def _maybe_rollover(self, now: float):
        today = time.strftime("%Y-%m-%d", time.localtime(now))
        if self.state.day_key is None:
            self.state.day_key = today
        elif today != self.state.day_key:
            self._daily_rollover(self.state.day_key)  # day_key is str here
            self.state.day_key = today

    def _mood(self) -> str:
        h = self.state.happiness
        return (
            "Thriving"
            if h >= 80
            else "Happy"
            if h >= 60
            else "Okay"
            if h >= 40
            else "Sad"
            if h >= 20
            else "Sick"
        )

    def _daily_rollover(self, day_key: str):
        avg = self.state.day_happiness_sum / max(self.state.day_samples, 1)
        self.state.health += 0.1 * (avg - self.state.health)
        met_both = (
            self.state.day_min_nourishment >= 60 and self.state.day_min_fitness >= 60
        )
        self.state.streak = self.state.streak + 1 if met_both else 0
        self.state.streak_bonus = min(5 * self.state.streak, 20)

        # snapshot the finished day's completion before resetting counts
        self.state.history[day_key] = self._completion(
            self.state.workout_counts, self.state.nutrition_counts
        )

        self._prune_history()
        self.state.day_happiness_sum = 0.0
        self.state.day_samples = 0
        self.state.day_min_nourishment = 100.0
        self.state.day_min_fitness = 100.0
        self.state.workout_counts = {"Pushups": 0, "Squats": 0}
        self.state.nutrition_counts = {"Food": 0, "Water": 0}
        self._dirty = True

    def _completion(self, workout_counts, nutrition_counts) -> dict:
        g = self.state.goals
        workout = (
            min(1.0, workout_counts["Pushups"] / g["Pushups"])
            + min(1.0, workout_counts["Squats"] / g["Squats"])
        ) / 2
        nutrition = (
            min(1.0, nutrition_counts["Food"] / g["Food"])
            + min(1.0, nutrition_counts["Water"] / g["Water"])
        ) / 2
        return {"workout": workout, "nutrition": nutrition}

    def _prune_history(self):
        if len(self.state.history) > HISTORY_DAYS:
            for key in sorted(self.state.history)[:-HISTORY_DAYS]:
                del self.state.history[key]

    def _build_info_view(self) -> ViewModel:
        today = time.strftime("%Y-%m-%d", time.localtime())
        today_done = self._completion(
            self.state.workout_counts, self.state.nutrition_counts
        )
        workout, nutrition = [], []
        for day in self._recent_days(HEATMAP_DAYS):
            rec = today_done if day == today else self.state.history.get(day)
            workout.append(self._level(rec["workout"]) if rec else 0)
            nutrition.append(self._level(rec["nutrition"]) if rec else 0)
        return ViewModel(
            title="Activity",
            lines=(),
            heatmap=(("weight", tuple(workout)), ("food", tuple(nutrition))),
        )

    def _recent_days(self, count: int) -> list[str]:
        now = time.time()
        days = [
            time.strftime("%Y-%m-%d", time.localtime(now - i * 86400))
            for i in range(count)
        ]
        return list(reversed(days))  # oldest -> newest (newest on the right)

    @staticmethod
    def _level(ratio: float) -> int:
        if ratio <= 0.0:
            return 0
        if ratio < 0.34:
            return 1
        if ratio < 0.67:
            return 2
        if ratio < 1.0:
            return 3
        return 4

    def _build_settings_view(self) -> ViewModel:
        lines = tuple(name if name == "Back" else f"{name}" for name in GOAL_OPTIONS)
        return ViewModel(title="Goals", lines=lines, selected=self.state.settings_index)

    def _build_goal_detail_view(self) -> ViewModel:
        name = GOAL_OPTIONS[self.state.settings_index]
        return ViewModel(title=name, lines=(f"< {self.state.goals[name]} >",))

    def _handle_settings_menu_button(self, button: str):
        if button == "left":
            self.state.settings_index = (self.state.settings_index - 1) % len(
                GOAL_OPTIONS
            )
        elif button == "right":
            self.state.settings_index = (self.state.settings_index + 1) % len(
                GOAL_OPTIONS
            )
        elif button == "select":
            if GOAL_OPTIONS[self.state.settings_index] == "Back":
                self.state.screen = "overview"
            else:
                self.state.screen = "settings_detail"

    def _handle_settings_detail_button(self, button: str):
        name = GOAL_OPTIONS[self.state.settings_index]
        if button == "left":
            self.state.goals[name] = max(GOAL_MIN, self.state.goals[name] - 1)
        elif button == "right":
            self.state.goals[name] = self.state.goals[name] + 1
        elif button == "select":
            self.state.screen = "settings_menu"
