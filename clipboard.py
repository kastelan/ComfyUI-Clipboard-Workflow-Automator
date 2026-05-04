"""
clipboard.py — Cross-platform ComfyUI clipboard monitor
Supports Windows (win32clipboard + PIL.ImageGrab) and Linux (GTK + pyperclip).

Polls the system clipboard every second and forwards new image or text content
to a running ComfyUI instance via its HTTP API.
"""

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import requests
from PIL import Image

# ---------------------------------------------------------------------------
# Platform-specific imports and clipboard implementations
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import win32clipboard
    from PIL import ImageGrab

    def get_clipboard_image() -> Image.Image | None:
        """
        Retrieves an image from the Windows clipboard using win32clipboard.
        Checks for CF_DIB format availability before attempting to grab.
        Returns a PIL Image or None if no image is present / clipboard is busy.
        """
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                image = ImageGrab.grabclipboard()
                if isinstance(image, Image.Image):
                    return image
        except Exception:
            pass  # Clipboard may be locked by another process — silently skip
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
        return None

    def get_clipboard_text() -> str | None:
        """
        Retrieves Unicode text from the Windows clipboard using win32clipboard.
        Returns the text string or None if unavailable / clipboard is busy.
        """
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except Exception:
            pass
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
        return None

else:  # Linux (and other GTK-capable platforms)
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gtk, Gdk
    # GTK must be initialised before any clipboard or widget operations.
    Gtk.init([])

    def get_clipboard_image() -> Image.Image | None:
        """
        Retrieves an image from the Linux clipboard via GTK/GDK.

        Handles both RGB and RGBA pixbufs correctly by checking get_has_alpha().
        Strips GDK row-padding when rowstride exceeds the raw pixel row width,
        which is common due to memory alignment requirements.
        Returns a PIL Image or None if no image is present.
        """
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        pixbuf = clipboard.wait_for_image()
        if not pixbuf:
            return None

        width = pixbuf.get_width()
        height = pixbuf.get_height()
        rowstride = pixbuf.get_rowstride()
        has_alpha = pixbuf.get_has_alpha()
        mode = "RGBA" if has_alpha else "RGB"
        n_channels = 4 if has_alpha else 3

        # Rowstride must be at least width * channels; GDK may add alignment padding
        if rowstride < width * n_channels:
            logging.warning(
                f"Unexpected rowstride ({rowstride}) for {width}x{height} {mode} — skipping."
            )
            return None

        pixels = pixbuf.get_pixels()

        if rowstride == width * n_channels:
            image = Image.frombytes(mode, (width, height), pixels)
        else:
            # Strip per-row padding before passing to PIL
            row_size = width * n_channels
            clean = b"".join(
                pixels[r * rowstride: r * rowstride + row_size]
                for r in range(height)
            )
            image = Image.frombytes(mode, (width, height), clean)

        return image

    def get_clipboard_text() -> str | None:
        """
        Retrieves plain text from the Linux clipboard via GTK.
        Uses the same clipboard handle as get_clipboard_image() — no pyperclip needed.
        Returns the text string or None if the clipboard holds no text.
        """
        try:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            text = clipboard.wait_for_text()
            return text if text else None
        except Exception as e:
            logging.error(f"Error reading text from clipboard: {e}")
            return None

# ---------------------------------------------------------------------------
# Configuration — platform-appropriate defaults
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    COMFY_DIR = Path(r"X:\ComfyUI_windows_portable") / "ComfyUI"
    COMFY_API = "http://127.0.0.1:3001/prompt"
else:
    COMFY_DIR = Path.home() / "ComfyUI"   # e.g. /home/nk/ComfyUI
    COMFY_API = "http://127.0.0.1:3001/prompt"

INPUT_DIR = COMFY_DIR / "input" / "clipboard_images"
WORKFLOWS_DIR = COMFY_DIR / "user" / "default" / "workflows" / "clipboard"
WORKFLOW_TEMPLATE = WORKFLOWS_DIR / "default.json"  # overridden by --profile

# ---------------------------------------------------------------------------
# Logging — file next to ComfyUI root + stdout
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        # Log file sits next to clipboard.py — no dependency on COMFY_DIR existing
        logging.FileHandler(Path(__file__).parent / "clipboard.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ---------------------------------------------------------------------------
# State tracking — detect clipboard changes across poll cycles
# ---------------------------------------------------------------------------

last_image_hash: str | None = None
last_text_content: str | None = None

# ---------------------------------------------------------------------------
# Shared utility functions
# ---------------------------------------------------------------------------

def get_image_hash(image: Image.Image) -> str:
    """Returns an MD5 hex digest of raw pixel data, used for change detection."""
    return hashlib.md5(image.tobytes()).hexdigest()


def create_api_prompt(content, content_type: str, workflow_path: Path | None = None) -> dict | None:
    """
    Loads the ComfyUI API-format workflow JSON and patches the node that
    matches the target title ('load_clipboard_image' or 'load_clipboard_text').

    For images, content should be a Path to the saved file.
    For text, content should be the raw string.
    workflow_path overrides the global WORKFLOW_TEMPLATE (used for --profile).
    Returns the patched prompt dict, or None for unknown content types.
    """
    path = workflow_path or WORKFLOW_TEMPLATE
    with open(path, "r", encoding="utf-8") as f:
        prompt = json.load(f)

    if content_type == "image":
        target_title = "load_clipboard_image"
        target_input = "image"
        # ComfyUI expects a path relative to its own `input/` directory
        new_value = f"{INPUT_DIR.name}/{content.name}".replace("\\", "/")
    elif content_type == "text":
        target_title = "load_clipboard_text"
        target_input = "text"
        new_value = content
    else:
        logging.error(f"Unknown content_type '{content_type}' — cannot build API prompt.")
        return None

    # Only patch the target node — resetting the opposite node (e.g. clearing the
    # image node when text arrives) is not safe because LoadImage requires a valid
    # file path and crashes on an empty string. Handle input switching inside the
    # workflow itself using a bypass or primitive switch node.
    node_found = False
    for node_id, node_data in prompt.items():
        if not isinstance(node_data, dict):
            continue
        if node_data.get("_meta", {}).get("title") == target_title:
            prompt[node_id]["inputs"][target_input] = new_value
            logging.info(f"Updated node '{target_title}' (ID: {node_id}) with new {content_type}.")
            node_found = True
            break

    if not node_found:
        logging.warning(
            f"Node '{target_title}' not found in workflow — "
            f"the {content_type} from clipboard will not be processed."
        )

    return {"prompt": prompt, "client_id": "clipboard_script"}


def send_to_api(workflow_prompt: dict | None) -> None:
    """POSTs the prepared workflow prompt to the ComfyUI HTTP API."""
    if not workflow_prompt:
        logging.error("Workflow prompt is empty — nothing sent to API.")
        return
    try:
        logging.debug(f"Sending API prompt: {json.dumps(workflow_prompt, indent=2)}")
        response = requests.post(COMFY_API, json=workflow_prompt, timeout=10)
        response.raise_for_status()
        logging.info(f"ComfyUI API response: {response.json()}")
    except requests.exceptions.Timeout:
        logging.error(f"Request to ComfyUI API timed out ({COMFY_API}).")
    except Exception as e:
        logging.error(f"Error sending workflow to API: {e}")

# ---------------------------------------------------------------------------
# Main poll cycle
# ---------------------------------------------------------------------------

def process_clipboard() -> None:
    """
    Single clipboard poll: checks for image first, then text.
    Skips processing if content matches the last seen hash / string.
    Resets both trackers when the clipboard becomes empty or unsupported.
    """
    global last_image_hash, last_text_content

    # 1. Image takes priority over text
    image = get_clipboard_image()
    if image:
        current_hash = get_image_hash(image)
        if current_hash == last_image_hash:
            return  # Same image — nothing to do

        logging.info(f"New image detected (hash: {current_hash[:8]}...). Processing.")
        last_image_hash = current_hash
        last_text_content = None  # Clear text tracker

        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        image_path = INPUT_DIR / f"clipboard_{int(time.time())}.png"
        image.save(image_path)
        logging.info(f"Image saved to: {image_path}")

        send_to_api(create_api_prompt(image_path, "image"))
        return

    # 2. No image — check for text
    text = get_clipboard_text()
    if text and text.strip():
        if text == last_text_content:
            return  # Same text — nothing to do

        logging.info(f"New text detected: '{text[:50]}...'. Processing.")
        last_text_content = text
        last_image_hash = None  # Clear image tracker

        send_to_api(create_api_prompt(text, "text"))
        return

    # 3. Clipboard is empty or holds an unsupported format — reset trackers
    if last_image_hash is not None or last_text_content is not None:
        logging.info("Clipboard empty or unsupported format — resetting trackers.")
        last_image_hash = None
        last_text_content = None


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="ComfyUI Clipboard Workflow Automator",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--profile",
        metavar="NAME",
        default=None,
        help=(
            "Workflow profile to use.\n"
            "Loads <NAME>.json from the ComfyUI workflows directory.\n"
            "Defaults to 'clipboard_processor' if not specified."
        ),
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List all available workflow profiles and exit.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point: parses args, validates paths, starts the polling loop."""
    global WORKFLOW_TEMPLATE, last_image_hash, last_text_content

    args = parse_args()
    platform_label = "Windows" if sys.platform == "win32" else "Linux"

    # Validate ComfyUI directory first — needed for both --list-profiles and normal run
    if not COMFY_DIR.exists():
        logging.error(f"ComfyUI directory not found: {COMFY_DIR}")
        logging.error("Update COMFY_DIR in the configuration section and try again.")
        sys.exit(1)

    # --list-profiles: show available .json files and exit
    if args.list_profiles:
        profiles = sorted(WORKFLOWS_DIR.glob("*.json"))
        if not profiles:
            logging.info(f"No workflow profiles found in: {WORKFLOWS_DIR}")
        else:
            logging.info(f"Available profiles in {WORKFLOWS_DIR}:")
            for p in profiles:
                marker = " ← default" if p.name == "default.json" else ""
                logging.info(f"  --profile {p.stem}{marker}")
        sys.exit(0)

    # Resolve workflow path from --profile or use default
    if args.profile:
        WORKFLOW_TEMPLATE = WORKFLOWS_DIR / f"{args.profile}.json"
        logging.info(f"Using profile: {args.profile} ({WORKFLOW_TEMPLATE.name})")
    # else: WORKFLOW_TEMPLATE stays as the global default

    if not WORKFLOW_TEMPLATE.exists():
        logging.error(f"Workflow template not found: {WORKFLOW_TEMPLATE}")
        if args.profile:
            logging.error(f"Run with --list-profiles to see available profiles.")
        else:
            logging.error(f"Expected folder: {WORKFLOWS_DIR}")
            logging.error("Save your workflow via ComfyUI: Save > Save (API format) → save as 'default.json' in that folder.")
        sys.exit(1)

    # Pre-load current clipboard state so the first poll does not trigger a workflow.
    # Without this, whatever is in the clipboard at launch would be sent to ComfyUI immediately.
    _init_image = get_clipboard_image()
    if _init_image:
        last_image_hash = get_image_hash(_init_image)
        logging.info("Startup: existing clipboard image ignored.")
    else:
        _init_text = get_clipboard_text()
        if _init_text:
            last_text_content = _init_text
            logging.info(f"Startup: existing clipboard text ignored ('{_init_text[:40]}...').")

    logging.info(f"Clipboard monitor started ({platform_label}) — profile: {WORKFLOW_TEMPLATE.stem}. Press Ctrl+C to stop.")
    try:
        while True:
            process_clipboard()
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Clipboard monitor stopped by user.")


if __name__ == "__main__":
    main()
