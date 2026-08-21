# ComfyUI Clipboard Workflow Automator

## Overview

A cross-platform background script that monitors your clipboard and automatically runs a predefined ComfyUI workflow whenever a new image or text is copied. Designed for power users looking to automate repetitive tasks like face-swapping, upscaling, or applying consistent styles with zero clicks.

Supports **Windows** (via `win32clipboard` + `PIL.ImageGrab`) and **Linux** (via GTK/GDK).

## Key Features

- **Cross-platform:** Single script runs on both Windows and Linux — platform detected automatically at startup.
- **Background Monitoring:** Runs silently, waiting for new clipboard content.
- **Full Workflow Automation:** Triggers your entire ComfyUI workflow from start to finish.
- **Duplicate Detection:** Skips content that was already processed (MD5 hash for images, direct comparison for text).
- **Startup Skip:** Content already in the clipboard when the script launches is ignored — only genuinely new changes trigger a workflow.
- **Dual Input Support:** Handles both images (via a `LoadImage` node) and text (via any text input node).
- **Startup Validation:** Checks that `COMFY_DIR` and the workflow JSON exist before entering the monitor loop, with clear error messages if not.
- **API-Driven:** Uses the ComfyUI HTTP API for robust execution.
- **Configurable without editing source:** Optional `config.toml` overrides paths, retry, and retention settings.
- **Resilient sends:** Failed API calls retry automatically with exponential backoff; if ComfyUI is unreachable even after retries, the prompt is queued and resent automatically on next startup instead of being lost.
- **Self-cleaning:** Old images in `clipboard_images/` are pruned automatically by age and/or count, so disk usage doesn't grow forever.

## How It Works

1. At launch, the script reads the current clipboard state and stores it without processing — this prevents the leftover clipboard content from triggering a workflow immediately.
2. It then continuously polls the clipboard every second for new content.
3. If new content is detected, the script loads a workflow JSON from the `clipboard/` subfolder (saved in **API format**) and patches the appropriate node:
   - For images: a `LoadImage` node titled **`load_clipboard_image`** — the image is saved to `ComfyUI/input/clipboard_images/` first.
   - For text: any node titled **`load_clipboard_text`** (e.g. `CLIPTextEncode`).
4. The modified workflow is sent to the ComfyUI API for execution. If the send fails, it's retried automatically with exponential backoff; if it still fails after all retries, it's saved to `failed_prompts/` and retried once automatically the next time the script starts.
5. A `clipboard.log` file is written next to `clipboard.py` for easy access regardless of ComfyUI's installation path. It rotates at 5 MB (3 backups kept) so it never grows unbounded.
6. Periodically (once at startup, then on the interval set in `config.toml`), the script prunes old files from `clipboard_images/` by age and/or count.

## Requirements

- Python 3.10 or higher (uses `X | Y` type union syntax).
- A running instance of ComfyUI.
- All custom nodes required by your workflow installed in ComfyUI.

### Platform-specific dependencies

| Package | Windows | Linux |
|---|---|---|
| `Pillow` | ✅ | ✅ |
| `requests` | ✅ | ✅ |
| `pywin32` | ✅ | ❌ |
| `PyGObject` | ❌ | ✅ |

Install with:
```bash
# Windows
pip install -r requirements_win.txt

# Linux
pip install -r requirements_linux.txt
```

> **Linux note:** `PyGObject` requires system GTK libraries. On Ubuntu/Debian:
> ```bash
> sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0
> ```

## Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/kastelan/ComfyUI-Clipboard-Workflow-Automator.git
cd ComfyUI-Clipboard-Workflow-Automator
```

### 2. Install Python Dependencies
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Windows
pip install -r requirements_win.txt

# Linux
pip install -r requirements_linux.txt
```

### 3. Configure

Copy the example config and edit it to match your setup — no source editing needed:

```bash
cp config.example.toml config.toml
```

```toml
[comfyui]
dir = "/home/yourname/ComfyUI"                  # Linux example
# dir = "D:\\ComfyUI_windows_portable\\ComfyUI"  # Windows example
api_url = "http://127.0.0.1:8188/prompt"

[retry]
count = 3               # retry attempts before giving up on a send
backoff_seconds = 2     # doubles each attempt: 2s, 4s, 8s...

[retention]
max_age_days = 7        # delete clipboard_images older than this (0 = disabled)
max_files = 500         # keep at most this many, newest first (0 = disabled)
check_interval_seconds = 3600
```

`config.toml` is optional — any key you don't set (or the whole file, if you skip this step) falls back to the script's built-in defaults. `config.toml` is gitignored, so your local paths never get committed.

> Requires Python 3.11+ for built-in TOML support (`tomllib`). On older Python, install `tomli` (`pip install tomli`) or just skip `config.toml` and rely on defaults.

### 4. Prepare Your ComfyUI Workflow

**Step 4a — Title the input nodes**

In ComfyUI, right-click the node that should receive clipboard content and select **"Title"**:
- Image input node → set title to exactly **`load_clipboard_image`**
- Text input node → set title to exactly **`load_clipboard_text`**

**Step 4b — Save in API format**

- Open ComfyUI Settings (⚙️) and enable **"Dev mode Options"**.
- Click **"Save (API Format)"** and save the file as:
  ```
  ComfyUI/user/default/workflows/clipboard/default.json
  ```

## Usage

1. Make sure ComfyUI is running.
2. Run the script:
   ```bash
   # Default profile (clipboard/default.json)
   python clipboard.py

   # Specific profile (clipboard/upscale.json)
   python clipboard.py --profile upscale

   # List all available profiles
   python clipboard.py --list-profiles
   ```
3. You should see:
   ```
   INFO - Startup: existing clipboard text ignored ('...').
   INFO - Clipboard monitor started (Linux). Press Ctrl+C to stop.
   ```
4. Copy any image or text — the workflow fires automatically.
5. Logs appear in the terminal and in `clipboard.log` next to the script.

## Troubleshooting

**`ComfyUI directory not found`**
→ `comfy_dir` in `config.toml` (or the built-in default) does not point to a valid directory. Double-check the path.

**`Workflow template not found`**
→ The `default.json` profile is missing. Save your workflow via **Save (API Format)** into `ComfyUI/user/default/workflows/clipboard/default.json`.
<<<<<<< HEAD

**`Workflow template ... is empty or not valid JSON`**
→ `default.json` (or your `--profile` file) is empty or truncated — usually from an interrupted save. Re-save it via **Save (API Format)** in ComfyUI. The script logs this and skips the current clipboard item instead of crashing.

**`Node '...' has no valid 'inputs' block` / `has no '...' input`**
→ The workflow JSON was saved without the expected node structure, or the titled node isn't the type you expect (e.g. `load_clipboard_text` was put on a node with no `text` input). Re-check the node title and type in ComfyUI, then re-save in API format.

**`Cannot execute because node ... does not exist`**
→ Your workflow uses a custom node that is not installed. Use **ComfyUI Manager → Install Missing Custom Nodes**.

**Script runs but nothing happens**
→ Check that node titles are set exactly to `load_clipboard_image` / `load_clipboard_text`.
→ Confirm the workflow was saved using **Save (API Format)**, not the regular Save.
→ Make sure you are copying **new** content — duplicates are intentionally skipped.

**Linux: clipboard image not detected**
→ GTK clipboard only holds images copied from GUI applications. Screenshots from tools like `gnome-screenshot` or `flameshot` work; raw file copies in a file manager typically don't.

**`Giving up after N retries` / files appearing in `failed_prompts/`**
→ ComfyUI wasn't reachable at `api_url` even after retries (check it's running and the port matches). The failed prompt isn't lost — it's saved to `failed_prompts/` and automatically retried once the next time you start the script. You can also just delete the file if you don't need that particular clipboard capture anymore.

**Old images not being deleted from `clipboard_images/`**
→ `config.toml` and code changes only take effect on a fresh start — restart the script after editing `config.toml`. Then check `clipboard.log` for `Loaded configuration overrides from config.toml.` (confirms the file was read) and `Retention cleanup: removed N old clipboard image(s)` (confirms cleanup ran, at startup and every `check_interval_seconds` after that).

## File Structure

```
ComfyUI-Clipboard-Workflow-Automator/
├── clipboard.py           # Main script (cross-platform)
├── config.example.toml    # Copy to config.toml and edit — see step 3 above
├── config.toml             # Your local config (gitignored, optional)
├── requirements_win.txt   # Windows dependencies
├── requirements_linux.txt # Linux dependencies
├── LICENSE
└── README.md

ComfyUI/user/default/workflows/clipboard/
├── default.json           # Default profile (required)
├── upscale.json           # Example additional profile
└── faceswap.json          # Example additional profile
```

> `clipboard.log`, `config.toml`, and `failed_prompts/` are created/used at runtime next to `clipboard.py` and are already covered by `.gitignore`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
# Clipboard-Automator-
