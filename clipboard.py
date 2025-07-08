import time
import logging
from pathlib import Path
from PIL import Image, ImageGrab
import win32clipboard
import requests
import json
import hashlib

# --- CONFIGURATION ---
BASE_DIR = Path(r"D:\ComfyUI_windows_portable")
COMFY_DIR = BASE_DIR / "ComfyUI"
INPUT_DIR = COMFY_DIR / "input" / "clipboard_images"
WORKFLOW_TEMPLATE = COMFY_DIR / "user/default/workflows" / "clipboard_processor.json"
COMFY_API = "http://127.0.0.1:8188/prompt"

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(COMFY_DIR / "clipboard.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# --- GLOBAL VARIABLES FOR DUPLICATE CHECKING ---
last_image_hash = None
last_text_content = None

def get_image_hash(image: Image.Image) -> str:
    """Calculates an MD5 hash of an image."""
    return hashlib.md5(image.tobytes()).hexdigest()

def get_clipboard_image() -> Image.Image | None:
    """Safely retrieves an image from the system clipboard."""
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
            image = ImageGrab.grabclipboard()
            if isinstance(image, Image.Image):
                return image
    except Exception:
        pass # Ignore errors if clipboard is busy or format is not DIB
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass
    return None

def get_clipboard_text() -> str | None:
    """Safely retrieves text from the system clipboard."""
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return text
    except Exception:
        pass
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass
    return None

def create_api_prompt(content, content_type: str) -> dict:
    """
    Loads the API-formatted workflow and performs a targeted modification
    based on the content type (image or text).
    """
    with open(WORKFLOW_TEMPLATE, "r", encoding="utf-8") as f:
        prompt = json.load(f)

    node_found = False
    if content_type == 'image':
        image_path = content
        target_title = 'load_clipboard_image'
        target_input = 'image'
        # We must provide a relative path from the `ComfyUI/input/` directory.
        new_value = f"{INPUT_DIR.name}/{image_path.name}".replace("\\", "/")
    elif content_type == 'text':
        target_title = 'load_clipboard_text'
        target_input = 'text' # Standard input name for CLIPTextEncode etc.
        new_value = content
    else:
        return None # Should not happen

    # Find the target node by its title and modify it.
    for node_id, node_data in prompt.items():
        if isinstance(node_data, dict) and node_data.get("_meta", {}).get("title") == target_title:
            prompt[node_id]["inputs"][target_input] = new_value
            logging.info(f"Found and updated node '{target_title}' (ID: {node_id}) with new {content_type}.")
            node_found = True
            break
            
    if not node_found:
        logging.warning(f"No node with the title '{target_title}' found. The {content_type} from clipboard will not be used.")

    return {"prompt": prompt, "client_id": "clipboard_script"}

def process_clipboard():
    """
    Main processing function. Checks for an image first, then for text,
    and triggers the workflow if new content is found.
    """
    global last_image_hash, last_text_content

    # --- 1. Check for an image first ---
    image = get_clipboard_image()
    if image:
        current_hash = get_image_hash(image)
        if current_hash == last_image_hash:
            return # Same image, do nothing

        logging.info(f"New image detected (hash: {current_hash[:8]}...). Processing.")
        last_image_hash = current_hash
        last_text_content = None # Reset text tracker

        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        image_path = INPUT_DIR / f"clipboard_{int(time.time())}.png"
        image.save(image_path)
        logging.info(f"Image saved to: {image_path}")
        
        # Prepare and send the prompt for the image
        workflow_prompt = create_api_prompt(image_path, 'image')
        send_to_api(workflow_prompt)
        return

    # --- 2. If no image, check for text ---
    text = get_clipboard_text()
    if text and text.strip(): # Ensure text is not empty or just whitespace
        if text == last_text_content:
            return # Same text, do nothing

        logging.info(f"New text detected: '{text[:50]}...'. Processing.")
        last_text_content = text
        last_image_hash = None # Reset image tracker
        
        # Prepare and send the prompt for the text
        workflow_prompt = create_api_prompt(text, 'text')
        send_to_api(workflow_prompt)
        return

    # --- 3. If clipboard is empty or unsupported, reset trackers ---
    if last_image_hash is not None or last_text_content is not None:
        logging.info("Clipboard is empty or contains unsupported data. Resetting trackers.")
        last_image_hash = None
        last_text_content = None

def send_to_api(workflow_prompt: dict):
    """Sends the prepared workflow prompt to the ComfyUI API."""
    if not workflow_prompt:
        logging.error("Workflow prompt is empty, cannot send to API.")
        return
    try:
        logging.debug(f"Sending API prompt: {json.dumps(workflow_prompt, indent=2)}")
        response = requests.post(COMFY_API, json=workflow_prompt)
        response.raise_for_status()
        logging.info(f"ComfyUI API response: {response.json()}")
    except Exception as e:
        logging.error(f"Error while processing workflow: {e}")

def main():
    """The main entry point of the script."""
    logging.info("Clipboard monitor started. Waiting for new image or text...")
    try:
        while True:
            process_clipboard()
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Clipboard monitor stopped by user.")

if __name__ == "__main__":
    main()
