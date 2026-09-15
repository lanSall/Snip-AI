# snip-ai

Press a hotkey, send what’s on your screen to AI, and get a **small corner toast** with the answer. The full answer is also copied so you can paste it.

```
Ctrl+Shift+Space   capture the monitor under the cursor
Ctrl+Shift+.       drag a rectangle (snip), then solve that region
Ctrl+Shift+/       open Settings (change your key or model)
```

The toast does not steal keyboard focus. It stays quiet (no sound) and dismisses itself.

New installs use **Gemini 3.8 Flash** (fast, usually free in AI Studio). You can switch to Flash-Lite or Pro in Settings — no YAML editing.

## Get started (about two minutes)

You only need to do this once.

1. **Install Python 3.10 or newer** from [python.org/downloads](https://www.python.org/downloads/).
   - Windows: in the installer, check **Add python.exe to PATH**. Leave the **tcl/tk** option on.
2. **Start snip-ai**
   - Windows: double-click `Start.bat` (a console may flash, then the app runs in the background)
   - Mac: double-click `Start.command` (if macOS warns it, right-click → Open)
   - Linux: run `./Start.sh` (Ubuntu/Debian also need `sudo apt install python3-venv python3-dev python3-tk`)
3. A **setup window** asks for an API key. Click **Get a free Gemini key**, create one, paste it, pick a **model**, then **Save and start**.
4. Leave snip-ai running. Put a question or error on screen and press **Ctrl+Shift+Space**.

That’s it. The first launch installs snip-ai for you; later launches just start it.

On **Windows**, look for the snip-ai icon in the notification area (near the clock). Right-click it for **Last answers**, **Settings**, **Open at login**, and **Quit**. If you do not see it, click the `^` overflow arrow.

A Gemini app / Gemini Pro subscription is not an API key. Create one at [Google AI Studio](https://aistudio.google.com/api-keys). OpenAI, Anthropic, OpenRouter, and a local [Ollama](https://ollama.com/) vision model also work — pick them in the same setup window.

### If Python is already installed

From a terminal, in this folder:

```bash
python -m pip install -e .
snip-ai
```

The same setup window appears if no key is saved yet. You can also save a key without the window:

```bash
snip-ai init --key YOUR_KEY
```

Windows PowerShell: run `.\Start.bat` from this folder. To keep a debug console instead of hiding it, set `SNIPAI_CONSOLE=1` then start as usual.

## After it is running

1. Put a problem, error, or question on screen.
2. Press **Ctrl+Shift+Space** (whole current monitor) or **Ctrl+Shift+.** (drag a snip).
3. A tiny **Solving…** toast appears, then the answer. Click the toast for the full write-up.
4. Paste if you want — it is also on the clipboard. Older answers: tray **Last answers** (keeps the last 10).

Change your key or model anytime: tray **Settings**, or **Ctrl+Shift+/**.

Other commands:

```bash
snip-ai                    # same as snip-ai run
snip-ai init               # open setup again (or use Settings while running)
snip-ai test-notify "ANSWER: 42"
snip-ai once               # capture + solve once, then exit
snip-ai once --region
snip-ai solve path/to/shot.png
snip-ai solve path/to/shot.png --no-notify
```

`mock` as the provider skips the network and is useful while you try the hotkey and toast.

## macOS permissions

Grant **Accessibility** (global hotkeys) and **Screen Recording** (capture) to Terminal, or to Python, depending on how you launched it.

## Wayland

Global hotkeys and screenshots are more reliable on Windows, macOS, and X11. On Wayland, run `snip-ai once` or `snip-ai solve FILE` if the background listener cannot bind keys.

## Settings file (optional)

Most people never need this. Settings from the window writes a small file:

| Platform | Path |
| --- | --- |
| Windows | `%APPDATA%\snip-ai\config.yaml` |
| macOS | `~/Library/Application Support/snip-ai/config.yaml` |
| Linux | `~/.config/snip-ai/config.yaml` |

You can also set `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` in the environment instead of pasting a key.

## Privacy

Each capture is sent to whatever provider you configured. Screenshots are not saved unless you set `save_shots: true`. The last 10 answers are stored on this computer (`%LOCALAPPDATA%\snip-ai\answers.json` / `~/.local/share/snip-ai/answers.json`). Logs go to the same data folder.
