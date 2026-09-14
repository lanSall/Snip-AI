# snip-ai

Hotkey the screen you are looking at, send that picture to a vision model, and get a **small corner toast** with the answer. The full answer is also copied to the clipboard so you can paste it without hunting through windows.

```
Ctrl+Shift+Space   capture the monitor under the cursor
Ctrl+Shift+.       drag a rectangle (snip), then solve that region
```

The toast does not steal keyboard focus. It sits in a corner, stays quiet (no sound), and dismisses itself.

## What you need

- Python 3.10+
- An API key for a vision-capable model:
  - [Gemini](https://aistudio.google.com/api-keys) (`gemini-2.5-pro` or Flash)
  - [OpenAI](https://platform.openai.com/) (`gpt-4o` or `gpt-4o-mini`)
  - [Anthropic](https://www.anthropic.com/) (`claude-sonnet-4-5` or similar)
  - [OpenRouter](https://openrouter.ai/)
  - a local [Ollama](https://ollama.com/) vision model such as `llama3.2-vision`

On Windows, install Python from python.org and leave the **tcl/tk** option enabled (it is on by default). That toolkit draws the snip overlay and the toast.

## Install

```bash
cd snip-ai
python -m venv .venv

# Windows
.venv\Scripts\activate
pip install -e .

# macOS / Linux
source .venv/bin/activate
pip install -e .
```

Linux also needs a compiler and Tk:

```bash
sudo apt install python3-dev python3-tk
```

## Configure

```bash
snip-ai init
```

That writes a config file (it will not overwrite an existing one):

| Platform | Path |
| --- | --- |
| Windows | `%APPDATA%\snip-ai\config.yaml` |
| macOS | `~/Library/Application Support/snip-ai/config.yaml` |
| Linux | `~/.config/snip-ai/config.yaml` |

Put your key in that file (`api_key: "..."`), **not** in `config.example.yaml`. `snip-ai run` prints the path it is using.

A Gemini app / Gemini Pro subscription is not an API key. Create one at [Google AI Studio](https://aistudio.google.com/api-keys).

```yaml
provider: gemini
model: gemini-2.5-pro
api_key: "AIza..."          # paste the AI Studio key here
```

Or set an environment variable instead:

```bash
# Gemini
setx GEMINI_API_KEY "AIza..."         # Windows (new terminals only)
export GEMINI_API_KEY="AIza..."       # macOS / Linux

# OpenAI
setx OPENAI_API_KEY "sk-..."
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

Example `config.yaml`:

```yaml
provider: gemini          # gemini | openai | anthropic | openrouter | openai_compatible | ollama | mock
model: gemini-2.5-pro
api_key: ""
hotkey: ctrl+shift+space
region_hotkey: ctrl+shift+period
clipboard: true
notify:
  enabled: true
  duration_ms: 8000
  max_chars: 180
  position: bottom-right  # bottom-right | bottom-left | top-right | top-left
  sound: false
```

## Use it

```bash
snip-ai run
```

Leave that process running. On Windows, start it with `pythonw -m snipai run` so no console window appears. `scripts/start-windows.vbs` does that; copy it to the Startup folder (`Win+R` → `shell:startup`) after `pip install -e .`.

Then:

1. Put a problem, error, or question on screen.
2. Press **Ctrl+Shift+Space** (whole current monitor) or **Ctrl+Shift+.** (drag a snip).
3. A tiny **Solving…** toast appears, then the answer.
4. Paste if you want the full write-up — it is already on the clipboard.

Other commands:

```bash
snip-ai test-notify "ANSWER: 42"
snip-ai once                  # capture + solve once, then exit
snip-ai once --region
snip-ai solve path/to/shot.png
snip-ai solve path/to/shot.png --no-notify
```

`mock` as the provider skips the network and is useful while you try the hotkey and toast:

```yaml
provider: mock
```

## macOS permissions

Grant **Accessibility** (global hotkeys) and **Screen Recording** (capture) to Terminal, iTerm, or `python`, depending on how you launch it.

## Wayland

Global hotkeys and screenshots are more reliable on Windows, macOS, and X11. On Wayland, run `snip-ai once` or `snip-ai solve FILE` if the background listener cannot bind keys.

## Privacy

Each capture is sent to whatever provider you configured. Screenshots are not saved unless you set `save_shots: true`. Logs go to the platform data dir (`%LOCALAPPDATA%\snip-ai` / `~/.local/share/snip-ai`).
