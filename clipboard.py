import time
import logging
from pathlib import Path
from PIL import Image, ImageGrab
import win32clipboard
import requests
import json
import hashlib

# --- CONFIGURATION ---
# Adjust these paths to match your ComfyUI installation directory.
BASE_DIR = Path(r"D:\ComfyUI_windows_portable")
COMFY_DIR = BASE_DIR / "ComfyUI"
INPUT_DIR = COMFY_DIR / "input" / "clipboard_images"
WORKFLOW_TEMPLATE = COMFY_DIR / "user/default/workflows" / "clipboard_processor.json"
COMFY_API = "http://127.0.0.1:8188/prompt"

# --- LOGGING SETUP ---
# Configures logging to both a file and the console for easy debugging.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(COMFY_DIR / "clipboard.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# --- GLOBAL VARIABLE FOR DUPLICATE CHECKING ---
# This will store the hash of the last successfully processed image to avoid re-running the same job.
last_image_hash = None

def get_image_hash(image: Image.Image) -> str:
    """Calculates an MD5 hash of an image to create a unique fingerprint."""
    return hashlib.md5(image.tobytes()).hexdigest()

def get_clipboard_image(retries=3, delay=0.5) -> Image.Image | None:
    """
    Safely retrieves an image from the system clipboard.
    Retries a few times in case the clipboard is busy.
    """
    for attempt in range(retries):
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                image = ImageGrab.grabclipboard()
                if isinstance(image, Image.Image):
                    return image
        except Exception as e:
            logging.warning(f"Attempt {attempt+1} to read clipboard failed: {e}")
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
        time.sleep(delay)
    return None

def create_api_prompt(image_path: Path) -> dict:
    """
    Loads the entire API-formatted workflow and performs a targeted modification.
    This is the most robust method for complex workflows as it preserves all hidden properties.
    """
    with open(WORKFLOW_TEMPLATE, "r", encoding="utf-8") as f:
        prompt = json.load(f)

    # 1. Find the ID of the node we want to modify.
    #    We identify it by its special title set in the ComfyUI interface.
    target_node_id = None
    for node_id, node_data in prompt.items():
        # The node title is stored in the "_meta" key in the API format.
        if isinstance(node_data, dict) and node_data.get("_meta", {}).get("title") == "load_clipboard_image":
            target_node_id = node_id
            break
            
    # 2. If the target node was found, modify its "image" input.
    if target_node_id:
        if prompt[target_node_id]["class_type"] == "LoadImage":
            # We must provide a relative path from the `ComfyUI/input/` directory.
            relative_path = f"{INPUT_DIR.name}/{image_path.name}"
            prompt[target_node_id]["inputs"]["image"] = relative_path.replace("\\", "/")
            logging.info(f"Found and updated node '{prompt[target_node_id]['_meta']['title']}' (ID: {target_node_id}) with the new image.")
        else:
            logging.warning(f"Node with title 'load_clipboard_image' was found but it is not a LoadImage node!")
    else:
        logging.warning("No node with the title 'load_clipboard_image' found. The clipboard image will not be used.")

    # Return the entire prompt object, now with the modified input.
    return {"prompt": prompt, "client_id": "clipboard_script"}

def process_image():
    """
    The main processing function. It checks for a new image and, if found,
    saves it and sends it to the ComfyUI API.
    """
    global last_image_hash # We need to modify the global variable.

    image = get_clipboard_image()
    if not image:
        # If the clipboard is empty, reset the hash so the next image can be processed.
        if last_image_hash is not None:
            logging.info("Clipboard is empty, resetting last image hash.")
            last_image_hash = None
        return

    # Calculate the hash of the image currently in the clipboard.
    current_hash = get_image_hash(image)

    # If the hash is the same as the last one, do nothing.
    if current_hash == last_image_hash:
        return # It's the same image, so we exit the function.

    # It's a new image! Let's process it.
    logging.info(f"New image detected in clipboard (hash: {current_hash[:8]}...). Processing.")
    last_image_hash = current_hash # Update the hash to this new one.

    # Save the image to the designated input directory.
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    image_path = INPUT_DIR / f"clipboard_{int(time.time())}.png"
    image.save(image_path)
    logging.info(f"Image saved to: {image_path}")

    # Send the job to the ComfyUI API.
    try:
        workflow_prompt = create_api_prompt(image_path)
        logging.debug(f"Sending API prompt: {json.dumps(workflow_prompt, indent=2)}")
        response = requests.post(COMFY_API, json=workflow_prompt)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx).
        logging.info(f"ComfyUI API response: {response.json()}")
    except Exception as e:
        logging.error(f"Error while processing workflow: {e}")

def main():
    """The main entry point of the script."""
    logging.info("Clipboard monitor started. Waiting for a new image...")
    try:
        while True:
            process_image()
            time.sleep(1) # Check the clipboard every second.
    except KeyboardInterrupt:
        logging.info("Clipboard monitor stopped by user.")

if __name__ == "__main__":
    main()
