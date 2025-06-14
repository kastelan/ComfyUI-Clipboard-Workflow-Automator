# ComfyUI Clipboard Workflow Automator
Script that monitors your clipboard and automatically runs a predefined, ComfyUI workflow whenever a new image is copied.

(It's highly recommended to create a short GIF showcasing the script in action and replace the link above)

Key Features
Background Monitoring: Runs silently in the background, waiting for new images.

Full Workflow Automation: Instead of just pasting an image, it triggers your entire, complex workflow from start to finish.

Duplicate Detection: Intelligently detects if the image in the clipboard is the same as the last one, preventing the same job from running repeatedly.

Universally Compatible: Designed to work with any ComfyUI workflow, no matter how complex, by targeting a specifically named node.

API-Driven: Uses the ComfyUI API, ensuring robust and reliable execution.

How It Works
The script leverages the ComfyUI API and a clever workflow identification method.

It continuously monitors the system clipboard for new image data.

To avoid re-processing, it calculates an MD5 hash of the image and compares it to the previously processed one.

If a new image is detected, the script loads a clipboard_processor.json file, which must be saved in the API format.

It then finds a LoadImage node within the workflow that has the specific title load_clipboard_image.

It updates this node's image input with the new image from the clipboard.

Finally, it sends the complete, modified workflow to the ComfyUI API for execution.

Requirements
Python 3.8 or higher.

A running instance of ComfyUI.

All custom nodes required by your workflow must be correctly installed in ComfyUI.

Python libraries: requests, Pillow, and pywin32.

Installation & Setup
Follow these steps carefully to get the automator running.

1. Clone the Repository

bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
2. Install Python Dependencies
It's recommended to use a virtual environment.

bash
# Create a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install required packages
pip install -r requirements.txt
3. Prepare Your ComfyUI Workflow (Crucial Steps!)

This is the most important part of the setup.

Step 3a: Target the Input Node
In the ComfyUI interface, load the workflow you want to automate. Find the LoadImage node that should receive the image from your clipboard. Right-click on this node and select "Title". Set its title to exactly load_clipboard_image.

(Replace with an actual screenshot)

Step 3b: Save the Workflow in API Format
This script requires the workflow to be in the API-specific JSON format to preserve all node properties.

In ComfyUI's settings (the gear icon ⚙️), check the box for "Enable Dev mode Options".

A new button, "Save (API Format)", will appear. Click it.

Save the file as clipboard_processor.json inside this project's directory, overwriting the placeholder if it exists.

(Replace with an actual screenshot)

4. Configure Paths in clipboard.py
Open the clipboard.py script and ensure the paths at the top match your system configuration, especially BASE_DIR.

python
# --- CONFIGURATION ---
BASE_DIR = Path(r"D:\ComfyUI_windows_portable")
# ... other paths are derived from this
Usage
Make sure your ComfyUI server is running.

Open a terminal, navigate to the project directory, and run the script:

bash
python clipboard.py
The script will print a message that it's monitoring the clipboard.

Now, simply copy any image to your clipboard (e.g., from a web browser or screenshot tool).

The script will detect the new image, save it, and trigger your ComfyUI workflow. You will see log messages in the terminal and the job will appear in your ComfyUI queue.

Troubleshooting
Cannot execute because node ... does not exist: This error is misleading. It almost always means you are missing one or more custom nodes required by your workflow. Use the ComfyUI Manager -> "Install Missing Custom Nodes" feature to scan your workflow and install all dependencies.

Script runs but nothing happens:

Check if you correctly set the node title to load_clipboard_image.

Ensure you saved the workflow using "Save (API Format)".

Make sure you are copying a new image. The script ignores duplicates.

NameError: 'INPUT_DIR' is not defined: You have accidentally deleted the configuration block at the top of the clipboard.py script. Restore it from this repository.

Invalid image file: The path to the image is incorrect. Ensure the INPUT_DIR path is correctly set and that the script is generating the relative path correctly.

Files to Include in Your Repository
requirements.txt
text
requests
Pillow
pywin32
.gitignore
text
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/

# Logs
*.log

# IDE / OS specific
.idea/
.vscode/
*.DS_Store
License
This project is licensed under the MIT License. See the LICENSE file for details.

This project was born out of a real-world need to automate complex image processing tasks in ComfyUI. It has been through extensive debugging and is designed to be as robust as possible.
