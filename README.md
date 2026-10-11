# Welp

E ####
H ####
requirements.txt todo

colorzero 2.0
gpiozero 2.0.1.post3
setuptools84.0.0

```shell
# S
rsync -a --delete ./ blueberry@blueberry.local:~/Welp/
ssh blueberry@blueberry.local "luma-env/bin/python Welp/main.py"


> Pushups
	Squats
	Back
Pet Stats
E #####
H #####

----
Workout

P: 0
S: 0
----
Select

Pushups
Squats
Back
----
Pushups

< 0 >
----
Squats

< 0 >
----
Nutrition

F: 0
W: 0
----
Select

> Food
	Water
	Back
Food

< 0 >
----
Water

< 0 >
```

This is a Raspberry Pi project with an OLED SH1106 display 

## Current screen flow

The app now uses a compact overview with a split-screen layout: the animated pet is drawn on the left and the active content appears on the right.

### Tabs

Left and right cycle through `P`, `W`, and `N` from the overview.

Select opens the focused tab's next screen.

### P

The overview shows exercise and water totals with a 4-bar progress display. The detail view keeps the same compact style.

### W

The overview shows total workout reps and the rep breakdown. Select opens the `Select` menu, then a count page.

### N

The overview shows total servings and the water/food breakdown. Select opens the `Select` menu, then a count page.

## Controls

The three-button input handler is wired through `UnitTests/input_handler_3button.py`.

Left and right move through the current tab when you are on the overview page. In the `Select` menu, select chooses the highlighted item.

## Tests

Run the unit tests with:

```bash
python -m unittest discover UnitTests
```
