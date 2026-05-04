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

## How It Works

1. At launch, the script reads the current clipboard state and stores it without processing — this prevents the leftover clipboard content from triggering a workflow immediately.
2. It then continuously polls the clipboard every second for new content.
3. If new content is detected, the script loads a workflow JSON from the `clipboard/` subfolder (saved in **API format**) and patches the appropriate node:
   - For images: a `LoadImage` node titled **`load_clipboard_image`** — the image is saved to `ComfyUI/input/clipboard_images/` first.
   - For text: any node titled **`load_clipboard_text`** (e.g. `CLIPTextEncode`).
4. The modified workflow is sent to the ComfyUI API for execution.
5. A `clipboard.log` file is written next to `clipboard.py` for easy access regardless of ComfyUI's installation path.

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

### 3. Configure Paths in `clipboard.py`

Open `clipboard.py` and set `COMFY_DIR` to match your installation:

```python
if sys.platform == "win32":
    COMFY_DIR = Path(r"D:\ComfyUI_windows_portable") / "ComfyUI"
    COMFY_API = "http://127.0.0.1:8188/prompt"
else:
    COMFY_DIR = Path.home() / "ComfyUI"   # e.g. /home/yourname/ComfyUI
    COMFY_API = "http://127.0.0.1:3001/prompt"
```

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
→ `COMFY_DIR` in `clipboard.py` does not point to a valid directory. Double-check the path.

**`Workflow template not found`**
→ The `default.json` profile is missing. Save your workflow via **Save (API Format)** into `ComfyUI/user/default/workflows/clipboard/default.json`.

**`Cannot execute because node ... does not exist`**
→ Your workflow uses a custom node that is not installed. Use **ComfyUI Manager → Install Missing Custom Nodes**.

**Script runs but nothing happens**
→ Check that node titles are set exactly to `load_clipboard_image` / `load_clipboard_text`.
→ Confirm the workflow was saved using **Save (API Format)**, not the regular Save.
→ Make sure you are copying **new** content — duplicates are intentionally skipped.

**Linux: clipboard image not detected**
→ GTK clipboard only holds images copied from GUI applications. Screenshots from tools like `gnome-screenshot` or `flameshot` work; raw file copies in a file manager typically don't.

## File Structure

```
ComfyUI-Clipboard-Workflow-Automator/
├── clipboard.py           # Main script (cross-platform)
├── requirements_win.txt   # Windows dependencies
├── requirements_linux.txt # Linux dependencies
├── LICENSE
└── README.md

ComfyUI/user/default/workflows/clipboard/
├── default.json           # Default profile (required)
├── upscale.json           # Example additional profile
└── faceswap.json          # Example additional profile
```

> `clipboard.log` is created at runtime next to `clipboard.py` — add it to `.gitignore`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
