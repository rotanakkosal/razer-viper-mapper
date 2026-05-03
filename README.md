# Razer Viper Mini — Button Mapper for macOS

A lightweight macOS application to detect and remap all Razer Viper Mini mouse buttons to custom keyboard shortcuts. Built as an alternative to Razer Synapse for Mac.

## Features

- **Real-time button detection** — see every button press light up on an interactive mouse diagram
- **25+ preset macOS shortcuts** — Mission Control, Screenshot, App Switcher, Spotlight, and more
- **Custom key combos** — map any button to any Cmd/Option/Ctrl/Shift + Key combination
- **Profile system** — save/load different configurations, assign profiles to specific apps
- **Dark Razer-themed UI** — runs in your browser at localhost:5000

## Detectable Buttons

| Button | Description |
|--------|------------|
| Left Click | Primary click |
| Right Click | Secondary click |
| Middle Click | Scroll wheel press |
| Side Back | Thumb button (back) |
| Side Forward | Thumb button (forward) |
| Scroll Up/Down | Scroll wheel |

> **Note:** The DPI button is handled by onboard firmware and cannot be detected or remapped.

## Requirements

- **macOS** (uses CGEventTap API)
- **Python 3.10+**
- **Accessibility permission** for your Terminal app

## Setup

1. **Install dependencies:**
   ```bash
   cd razer-viper-mapper
   pip install -r requirements.txt
   ```

2. **Grant Accessibility permission:**
   - Open **System Settings → Privacy & Security → Accessibility**
   - Click the **+** button and add your **Terminal** app (or iTerm, VS Code terminal, etc.)
   - If using a Python virtual environment, you may need to add the Python binary directly

3. **Run the app:**
   ```bash
   python app.py
   ```

4. **Open in browser:**
   Navigate to [http://localhost:5000](http://localhost:5000)

## Usage

1. Click **"Start Detection"** to begin listening for mouse events
2. Press any mouse button — it will light up on the diagram
3. **Click a button on the diagram** to open its configuration panel
4. Choose a **preset shortcut** or create a **custom key combination**
5. Toggle **"Enable Remapping"** to activate your mappings
6. **Save your configuration** as a profile for later use

## How It Works

- **Detection:** Uses macOS `CGEventTap` to intercept mouse events at the system level
- **Remapping:** Suppresses the original mouse event and simulates a keyboard shortcut via `CGEventCreateKeyboardEvent`
- **Communication:** Flask-SocketIO provides real-time WebSocket updates between the Python backend and the browser UI
- **Profiles:** Saved as JSON files in the `profiles/` directory

## Troubleshooting

**"Failed to start detection"**
→ Make sure Accessibility permission is granted to your terminal app. You may need to restart the terminal after granting permission.

**Side buttons not detected**
→ Some third-party mouse drivers may intercept events before they reach CGEventTap. Make sure no other mouse utility software is running.

**Remapping doesn't work**
→ Ensure "Enable Remapping" is toggled ON. The app needs to restart the event tap in active mode (not listen-only) to intercept events.

## Project Structure

```
razer-viper-mapper/
├── app.py              # Flask backend + WebSocket server
├── mouse_detector.py   # CGEventTap mouse event detection
├── remapper.py         # Button-to-shortcut remapping engine
├── profiles.py         # Profile save/load manager
├── requirements.txt    # Python dependencies
├── profiles/           # Saved profile JSON files
│   └── default.json
└── static/
    ├── index.html      # Main UI page
    ├── style.css       # Dark theme styles
    └── app.js          # Frontend logic + WebSocket client
```

## License

MIT — use freely for personal or commercial purposes.
