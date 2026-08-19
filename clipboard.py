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
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    import tomllib  # Python 3.11+ stdlib
except ModuleNotFoundError:
    tomllib = None  # config.toml support disabled; hardcoded defaults still work

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
        except win32clipboard.error as e:
            # Clipboard is commonly locked briefly by another process (e.g. a
            # screenshot tool mid-write) — this is expected and transient.
            logging.debug(f"Clipboard busy while reading image: {e}")
        except Exception as e:
            logging.warning(f"Unexpected error reading clipboard image: {e}", exc_info=True)
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception as e:
                logging.debug(f"CloseClipboard failed (likely already closed): {e}")
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
        except win32clipboard.error as e:
            logging.debug(f"Clipboard busy while reading text: {e}")
        except Exception as e:
            logging.warning(f"Unexpected error reading clipboard text: {e}", exc_info=True)
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception as e:
                logging.debug(f"CloseClipboard failed (likely already closed): {e}")
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
<<<<<<< HEAD
# Logging — file next to clipboard.py + stdout
=======
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
>>>>>>> 124e5c2bd237e19d6f7c3f5fb61fbeebfdc0cf33
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        # Log file sits next to clipboard.py — no dependency on COMFY_DIR existing.
        # Rotates at 5 MB, keeps 3 backups, so it can run unattended indefinitely.
        RotatingFileHandler(
            Path(__file__).parent / "clipboard.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        ),
        logging.StreamHandler()
    ]
)

# ---------------------------------------------------------------------------
# Configuration — platform defaults, overridable via config.toml
# ---------------------------------------------------------------------------
#
# Drop a config.toml next to this script to override any default below
# without editing source — see config.example.toml for the full format.
# Any key missing from config.toml (or the whole file, if absent) falls
# back to the hardcoded default, so this is a drop-in upgrade: no config
# file is required for the script to keep working exactly as before.

if sys.platform == "win32":
    _DEFAULT_COMFY_DIR = r"X:\ComfyUI_windows_portable\ComfyUI"
else:
    _DEFAULT_COMFY_DIR = str(Path.home() / "ComfyUI")

_DEFAULTS = {
    "comfy_dir": _DEFAULT_COMFY_DIR,
    "comfy_api": "http://127.0.0.1:3001/prompt",
    "retry_count": 3,
    "retry_backoff_seconds": 2,
    "retention_max_age_days": 7,
    "retention_max_files": 500,
    "retention_check_interval_seconds": 3600,
}

CONFIG_PATH = Path(__file__).parent / "config.toml"


def _load_config() -> dict:
    """
    Loads config.toml next to the script and merges it over _DEFAULTS.
    Missing file, missing keys, or a broken TOML file are all non-fatal —
    this always returns a complete, usable config dict.
    """
    config = dict(_DEFAULTS)
    if not CONFIG_PATH.exists():
        return config

    if tomllib is None:
        logging.warning(
            f"Found {CONFIG_PATH.name} but this Python (<3.11) has no built-in TOML "
            f"support — run 'pip install tomli' or upgrade Python. Using defaults for now."
        )
        return config

    try:
        with open(CONFIG_PATH, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        logging.warning(f"Could not parse {CONFIG_PATH.name} ({e}) — using defaults.")
        return config
    except OSError as e:
        logging.warning(f"Could not read {CONFIG_PATH.name} ({e}) — using defaults.")
        return config

    comfyui = raw.get("comfyui", {})
    retry = raw.get("retry", {})
    retention = raw.get("retention", {})

    config["comfy_dir"] = comfyui.get("dir", config["comfy_dir"])
    config["comfy_api"] = comfyui.get("api_url", config["comfy_api"])
    config["retry_count"] = retry.get("count", config["retry_count"])
    config["retry_backoff_seconds"] = retry.get("backoff_seconds", config["retry_backoff_seconds"])
    config["retention_max_age_days"] = retention.get("max_age_days", config["retention_max_age_days"])
    config["retention_max_files"] = retention.get("max_files", config["retention_max_files"])
    config["retention_check_interval_seconds"] = retention.get(
        "check_interval_seconds", config["retention_check_interval_seconds"]
    )
    logging.info(f"Loaded configuration overrides from {CONFIG_PATH.name}.")
    return config


CONFIG = _load_config()

COMFY_DIR = Path(CONFIG["comfy_dir"])
COMFY_API = CONFIG["comfy_api"]

INPUT_DIR = COMFY_DIR / "input" / "clipboard_images"
WORKFLOWS_DIR = COMFY_DIR / "user" / "default" / "workflows" / "clipboard"
WORKFLOW_TEMPLATE = WORKFLOWS_DIR / "default.json"  # overridden by --profile
DEAD_LETTER_DIR = Path(__file__).parent / "failed_prompts"

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
<<<<<<< HEAD
    try:
        with open(path, "r", encoding="utf-8") as f:
            prompt = json.load(f)
    except FileNotFoundError:
        logging.error(
            f"Workflow template not found at '{path}' — cannot process this {content_type}. "
            f"Check that the file exists and the path/profile is correct."
        )
        return None
    except json.JSONDecodeError as e:
        logging.error(
            f"Workflow template at '{path}' is empty or not valid JSON "
            f"({e.msg} at line {e.lineno}, col {e.colno}) — cannot process this {content_type}. "
            f"Re-export the workflow from ComfyUI in API format."
        )
        return None
=======
    with open(path, "r", encoding="utf-8") as f:
        prompt = json.load(f)
>>>>>>> 124e5c2bd237e19d6f7c3f5fb61fbeebfdc0cf33

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
<<<<<<< HEAD
        if node_data.get("_meta", {}).get("title") != target_title:
            continue

        node_found = True
        inputs = node_data.get("inputs")
        if not isinstance(inputs, dict):
            # Malformed or hand-edited workflow JSON — node exists but has no
            # (or a non-dict) "inputs" block. Skip it instead of crashing so
            # one bad workflow file doesn't take down the whole monitor loop.
            logging.error(
                f"Node '{target_title}' (ID: {node_id}) has no valid 'inputs' block — "
                f"skipping this {content_type}. Check that '{path.name}' was saved "
                f"correctly in API format."
            )
            return None
        if target_input not in inputs:
            logging.error(
                f"Node '{target_title}' (ID: {node_id}) has no '{target_input}' input — "
                f"skipping this {content_type}. This node may be the wrong type "
                f"for the expected content."
            )
            return None

        inputs[target_input] = new_value
        logging.info(f"Updated node '{target_title}' (ID: {node_id}) with new {content_type}.")
        break
=======
        if node_data.get("_meta", {}).get("title") == target_title:
            prompt[node_id]["inputs"][target_input] = new_value
            logging.info(f"Updated node '{target_title}' (ID: {node_id}) with new {content_type}.")
            node_found = True
            break
>>>>>>> 124e5c2bd237e19d6f7c3f5fb61fbeebfdc0cf33

    if not node_found:
        logging.warning(
            f"Node '{target_title}' not found in workflow — "
            f"the {content_type} from clipboard will not be processed."
        )
        return None

    return {"prompt": prompt, "client_id": "clipboard_script"}


def send_to_api(workflow_prompt: dict | None) -> None:
    """
    POSTs the prepared workflow prompt to the ComfyUI HTTP API.

    Retries on timeout/connection errors with exponential backoff
    (CONFIG["retry_count"] attempts, starting at CONFIG["retry_backoff_seconds"]
    and doubling each time). If every attempt fails, the prompt is written to
    DEAD_LETTER_DIR instead of being silently dropped — replay_dead_letter_queue()
    retries these automatically the next time the script starts.
    """
    if not workflow_prompt:
        logging.error("Workflow prompt is empty — nothing sent to API.")
        return

    retries = CONFIG["retry_count"]
    backoff = CONFIG["retry_backoff_seconds"]
    attempt = 0

    while True:
        attempt += 1
        try:
            logging.debug(f"Sending API prompt: {json.dumps(workflow_prompt, indent=2)}")
            response = requests.post(COMFY_API, json=workflow_prompt, timeout=10)
            response.raise_for_status()
            logging.info(f"ComfyUI API response: {response.json()}")
            return
        except requests.exceptions.Timeout:
            reason = f"request timed out ({COMFY_API})"
        except requests.exceptions.ConnectionError:
            reason = f"could not connect to {COMFY_API} — is ComfyUI running?"
        except Exception as e:
            reason = str(e)

        if attempt > retries:
            logging.error(
                f"Giving up after {attempt - 1} retr{'y' if attempt - 1 == 1 else 'ies'}: {reason}"
            )
            _save_to_dead_letter(workflow_prompt)
            return

        wait = backoff * (2 ** (attempt - 1))
        logging.warning(f"Send attempt {attempt} failed ({reason}) — retrying in {wait}s...")
        time.sleep(wait)


def _save_to_dead_letter(workflow_prompt: dict) -> None:
    """Persists a prompt that failed every retry so it isn't lost outright."""
    try:
        DEAD_LETTER_DIR.mkdir(parents=True, exist_ok=True)
        fname = DEAD_LETTER_DIR / f"failed_{int(time.time())}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(workflow_prompt, f)
        logging.error(f"Saved failed prompt to {fname} — will retry automatically on next startup.")
    except OSError as e:
        logging.error(f"Could not save failed prompt to dead-letter queue: {e}")


def replay_dead_letter_queue() -> None:
    """
    Called once at startup: attempts to resend any prompts left over from a
    previous run where ComfyUI was unreachable even after retries. Successful
    replays are deleted; still-failing ones are left in place for next time.
    """
    if not DEAD_LETTER_DIR.exists():
        return
    pending = sorted(DEAD_LETTER_DIR.glob("failed_*.json"))
    if not pending:
        return

    logging.info(f"Found {len(pending)} previously failed prompt(s) — retrying once...")
    for f in pending:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                prompt = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            logging.warning(f"Could not read dead-letter file {f.name} ({e}) — leaving in place.")
            continue
        try:
            response = requests.post(COMFY_API, json=prompt, timeout=10)
            response.raise_for_status()
            logging.info(f"Replayed {f.name} successfully.")
            f.unlink()
        except Exception as e:
            logging.warning(f"Replay of {f.name} still failing ({e}) — will retry next startup.")

def cleanup_old_images(directory: Path, max_age_days: int, max_files: int) -> None:
    """
    Prunes clipboard_images/ so it doesn't grow forever. A file is removed if
    it's older than max_age_days OR if it falls outside the newest max_files
    (whichever check applies — set either to 0 to disable that check).
    """
    if not directory.exists():
        return

    files = sorted(directory.glob("clipboard_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    now = time.time()
    max_age_seconds = max_age_days * 86400
    removed = 0

    for i, f in enumerate(files):
        too_old = max_age_days > 0 and (now - f.stat().st_mtime) > max_age_seconds
        too_many = max_files > 0 and i >= max_files
        if too_old or too_many:
            try:
                f.unlink()
                removed += 1
            except OSError as e:
                logging.warning(f"Could not delete old clipboard image {f.name}: {e}")

    if removed:
        logging.info(f"Retention cleanup: removed {removed} old clipboard image(s) from {directory}.")


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
<<<<<<< HEAD

    replay_dead_letter_queue()
    cleanup_old_images(INPUT_DIR, CONFIG["retention_max_age_days"], CONFIG["retention_max_files"])
    next_cleanup_time = time.time() + CONFIG["retention_check_interval_seconds"]

=======
>>>>>>> 124e5c2bd237e19d6f7c3f5fb61fbeebfdc0cf33
    try:
        while True:
            process_clipboard()
            if time.time() >= next_cleanup_time:
                cleanup_old_images(INPUT_DIR, CONFIG["retention_max_age_days"], CONFIG["retention_max_files"])
                next_cleanup_time = time.time() + CONFIG["retention_check_interval_seconds"]
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Clipboard monitor stopped by user.")


if __name__ == "__main__":
    main()
