# Brain Pet Python Replacement

This folder contains a non-Electron replacement for the original `brain-pet` app.

The old `brain-pet/` Electron project is kept as reference only. This new version does not use Electron, Node.js, npm, Chromium, CEF, or WebView2.

## Why this version exists

The original app depended on Electron and Chromium startup behavior that is unreliable in this environment. This replacement avoids that stack entirely and uses Python's built-in `tkinter` GUI toolkit instead.

## Features

- transparent frameless always-on-top desktop window
- appears near the bottom-right of the screen by default
- drag with left mouse button
- right-click menu
- three states: `Idle`, `Focus`, `Break`
- simple breathing / glow / floating animation
- local JSON settings persistence in `settings.json`
- no Electron, Node.js, or Chromium

## Files

- `main.py`: launch entry point
- `brain_pet/constants.py`: migrated constant definitions and app options
- `brain_pet/state_config.py`: migrated state and time overlay definitions
- `brain_pet/settings.py`: JSON settings load/save helpers
- `brain_pet/ui.py`: tkinter desktop pet UI
- `img/`: your layered brain PNG assets
- `settings.json`: created automatically after first run

## Run

From this folder:

```powershell
cd brain-pet-python
python main.py
```

If `python` is not the correct command on your machine, try:

```powershell
py main.py
```

## Controls

- Left drag: move the pet
- Right click: open the menu
- Menu -> `State`: switch between Idle, Focus, and Break
- Menu -> `Size`: resize the pet
- `Toggle Bubble`: show or hide the thought bubble
- `Reset Position`: move the pet back near the bottom-right corner

## Notes on migration

- State naming and region layout were adapted from the Electron project's shared config.
- The Python version keeps the "brain regions + state bubble + overlay mood" concept, but implements it with `tkinter.Canvas` instead of browser rendering.
- The app now loads the PNG layers from `img/`, aligns them by their shared canvas size, and removes the red registration marker during load.
- No attempt is made to preserve Electron-specific infrastructure such as `active-win`, BrowserWindow logic, tray integration, or Chromium rendering.
