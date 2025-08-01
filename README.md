# ComfyUI Clipboard Workflow Automator

## Overview

A powerful background script that monitors your clipboard and automatically runs a predefined, complex ComfyUI workflow whenever a new image or text is copied. This tool is designed for power users and developers looking to automate repetitive tasks like face-swapping, upscaling, or applying consistent styles and prompts with zero clicks.

## Key Features

- **Background Monitoring:** Runs silently in the background, waiting for new images or text.
- **Full Workflow Automation:** Triggers your entire, complex workflow from start to finish, not just pasting content.
- **Duplicate Detection:** Intelligently detects if the content in the clipboard is the same as the last processed, preventing redundant jobs.
- **Dual Input Support:** Handles both images (via a `LoadImage` node) and text (via a text input node like `CLIPTextEncode`).
- **Universally Compatible:** Works with **any** ComfyUI workflow, no matter how complex, by targeting specifically named nodes.
- **API-Driven:** Uses the ComfyUI API for robust and reliable execution.

## How It Works

1. The script continuously monitors the system clipboard for new image or text data.
2. To avoid re-processing, it calculates a unique identifier (hash for images, direct comparison for text) and compares it to the previously processed content.
3. If new content is detected, the script loads a `clipboard_processor.json` file, which must be saved in the **API format**.
4. It then finds the appropriate node within the workflow:
   - For images: a `LoadImage` node with the title **`load_clipboard_image`**.
   - For text: a node with the title **`load_clipboard_text`** (e.g., `CLIPTextEncode`).
5. It updates the node's input (`image` for images, `text` for text) with the new content from the clipboard.
6. Finally, it sends the complete, modified workflow to the ComfyUI API for execution.

## Requirements

- Python 3.8 or higher.
- A running instance of ComfyUI.
- All custom nodes required by your workflow must be correctly installed in ComfyUI.
- Python libraries: `requests`, `Pillow`, and `pywin32`.

## Installation & Setup

Follow these steps carefully to get the automator running.

### 1. Clone the Repository
```bash
git clone https://github.com/kastelan/ComfyUI-Clipboard-Workflow-Automator.git
cd ComfyUI-Clipboard-Workflow-Automator
```

### 2. Install Python Dependencies
It's recommended to use a virtual environment.
```bash
# Create a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install required packages
pip install -r requirements.txt
```

### 3. Prepare Your ComfyUI Workflow (Crucial Steps!)

This is the most important part of the setup.

- **Step 3a: Target the Input Nodes**
  - In the ComfyUI interface, load the workflow you want to automate.
  - For image input: Find the **`LoadImage`** node that should receive the image from your clipboard. Right-click on this node, select **"Title"**, and set its title to exactly **`load_clipboard_image`**.
  - For text input: Find the node that should receive text (e.g., `CLIPTextEncode` for prompts). Right-click, select **"Title"**, and set its title to exactly **`load_clipboard_text`**.

- **Step 3b: Save the Workflow in API Format**
  - This script requires the workflow to be in the API-specific JSON format to preserve all node properties.
  - In ComfyUI's settings (the gear icon ⚙️), check the box for **"Enable Dev mode Options"**.
  - A new button, **"Save (API Format)"**, will appear. Click it.
  - Save the file as **`clipboard_processor.json`** inside this project's directory, overwriting the placeholder if it exists.

### 4. Configure Paths in `clipboard.py`
Open the `clipboard.py` script and ensure the paths at the top match your system configuration, especially `BASE_DIR`.

```python
# --- CONFIGURATION ---
BASE_DIR = Path(r"D:\ComfyUI_windows_portable")
# ... other paths are derived from this
```

## Usage

1. Make sure your ComfyUI server is running.
2. Open a terminal, navigate to the project directory, and run the script:
   ```bash
   python clipboard.py
   ```
3. The script will print a message that it's monitoring the clipboard.
4. Now, simply copy any image or text to your clipboard (e.g., from a web browser, screenshot tool, or text editor).
5. The script will detect the new content, save images if applicable, and trigger your ComfyUI workflow. You will see log messages in the terminal, and the job will appear in your ComfyUI queue.

## Troubleshooting

- **`Cannot execute because node ... does not exist`**: This error is misleading. It usually means you are **missing one or more custom nodes** required by your workflow. Use the **ComfyUI Manager** -> **"Install Missing Custom Nodes"** feature to scan your workflow and install all dependencies.
- **Script runs but nothing happens**:
  - Check if you correctly set the node titles to `load_clipboard_image` or `load_clipboard_text`.
  - Ensure you saved the workflow using **"Save (API Format)"**.
  - Make sure you are copying **new** content. The script ignores duplicates.
- **`NameError: 'INPUT_DIR' is not defined`**: You have accidentally deleted the configuration block at the top of the `clipboard.py` script. Restore it from this repository.
- **`Invalid image file`**: The path to the image is incorrect. Ensure the `INPUT_DIR` path is correctly set and that the script is generating the relative path correctly.

## Files to Include in Your Repository

### `requirements.txt`
```
requests
Pillow
pywin32
```


## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

*This project was born out of a real-world need to automate complex image and text processing tasks in ComfyUI. It has been through extensive debugging and is designed to be as robust as possible.*


