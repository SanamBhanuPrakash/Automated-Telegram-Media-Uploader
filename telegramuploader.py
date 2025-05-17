import os
import asyncio
import aiofiles
import aiohttp
from aiohttp import ClientSession
from dotenv import load_dotenv
import time

# Load environment variables from .env
load_dotenv()

# ------------------ CONFIGURATION ------------------

# Path to the main folder containing media subfolders
PARENT_FOLDER = "/path/to/your/media/folder"  # <-- Set your media folder path here

# Allowed file extensions
ALLOWED_PHOTO_TYPES = {'.jpg', '.jpeg', '.png'}
ALLOWED_VIDEO_TYPES = {'.mp4', '.avi'}

# Max Telegram file size in MB (Telegram limits ~2GB)
MAX_FILE_SIZE_MB = 2000

# Cooldown after each successful upload (seconds)
COOLDOWN_PER_FILE = 5

# Max retries per file upload
MAX_RETRIES = 3

# Delay between retry attempts (seconds)
RETRY_DELAY = 5

# ------------------ BOT CONFIGURATION ------------------

# Read tokens and chat IDs from environment variables
PHOTO_BOTS = [
    {"token": os.getenv(f"PHOTO_BOT_TOKEN_{i}"), "chat_id": os.getenv("PHOTO_CHAT_ID")}
    for i in range(1, 6)
]

VIDEO_BOTS = [
    {"token": os.getenv(f"VIDEO_BOT_TOKEN_{i}"), "chat_id": os.getenv("VIDEO_CHAT_ID")}
    for i in range(1, 6)
]

# ------------------ HELPERS ------------------

def get_folder_log_paths(folder_path):
    """
    Each folder will have its own log files to track uploads and huge files.
    """
    uploaded_log = os.path.join(folder_path, "uploaded_files.txt")
    huge_log = os.path.join(folder_path, "huge_files.txt")
    return uploaded_log, huge_log


def is_photo(file_path):
    return os.path.splitext(file_path)[1].lower() in ALLOWED_PHOTO_TYPES

def is_video(file_path):
    return os.path.splitext(file_path)[1].lower() in ALLOWED_VIDEO_TYPES

async def read_uploaded_list(uploaded_log_path):
    """
    Read uploaded files log and return a set of full file paths.
    """
    if not os.path.exists(uploaded_log_path):
        return set()
    async with aiofiles.open(uploaded_log_path, "r") as f:
        lines = await f.readlines()
        return set(line.strip() for line in lines if line.strip())

async def log_file(path, log_path):
    """
    Append a file path to the given log file.
    """
    async with aiofiles.open(log_path, "a") as f:
        await f.write(path + "\n")

async def upload_file(file_path, bot_token, chat_id, session: ClientSession):
    """
    Upload a file to Telegram using bot token & chat id.
    Returns True if upload succeeded, False otherwise.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

    try:
        # Open file as binary
        with open(file_path, 'rb') as file_obj:
            data = aiohttp.FormData()
            data.add_field('chat_id', chat_id)
            data.add_field('document', file_obj, filename=os.path.basename(file_path))

            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    print(f"[SUCCESS] Uploaded: {file_path}")
                    return True
                else:
                    error_text = await resp.text()
                    print(f"[FAIL] Upload failed for {file_path} | Status: {resp.status} | Response: {error_text}")
                    return False

    except Exception as e:
        print(f"[ERROR] Exception uploading {file_path}: {str(e)}")
        return False

async def worker(queue: asyncio.Queue, bot_list, session: ClientSession):
    """
    Worker coroutine that uploads files from the queue using available bots.
    It tries each bot until upload succeeds or all bots fail.
    """
    while True:
        try:
            file_path, uploaded_log, huge_log = await queue.get()
        except asyncio.CancelledError:
            break

        # Check file size and log huge files (skipped from upload)
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            print(f"[SKIP] File too large (>2GB), logged: {file_path}")
            await log_file(file_path, huge_log)
            queue.task_done()
            continue

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            for bot in bot_list:
                uploaded = await upload_file(file_path, bot["token"], bot["chat_id"], session)
                if uploaded:
                    await log_file(file_path, uploaded_log)
                    success = True
                    await asyncio.sleep(COOLDOWN_PER_FILE)
                    break
                else:
                    print(f"[RETRY] Attempt {attempt}, trying next bot for {file_path}")
                    await asyncio.sleep(3)  # Short delay before next bot try
            if success:
                break
            else:
                print(f"[WAIT] Retry attempt {attempt} failed for {file_path}, waiting {RETRY_DELAY}s")
                await asyncio.sleep(RETRY_DELAY)

        if not success:
            print(f"[FAILED] All attempts failed for {file_path}")

        queue.task_done()


async def main():
    print("[INFO] Scanning media folders...")

    # Scan all subfolders
    tasks = []
    queue_photo = asyncio.Queue()
    queue_video = asyncio.Queue()

    # Walk all folders and queue files to respective queues
    for root, _, files in os.walk(PARENT_FOLDER):
        uploaded_log, huge_log = get_folder_log_paths(root)
        uploaded_files = await read_uploaded_list(uploaded_log)

        for f in files:
            full_path = os.path.join(root, f)
            if full_path in uploaded_files:
                # Skip already uploaded files
                continue

            ext = os.path.splitext(f)[1].lower()
            if ext not in ALLOWED_PHOTO_TYPES and ext not in ALLOWED_VIDEO_TYPES:
                continue

            # Put file in respective queue along with its log paths
            if is_photo(full_path):
                await queue_photo.put((full_path, uploaded_log, huge_log))
            elif is_video(full_path):
                await queue_video.put((full_path, uploaded_log, huge_log))

    async with aiohttp.ClientSession() as session:
        workers = []

        # Start 5 photo workers
        for _ in range(5):
            workers.append(asyncio.create_task(worker(queue_photo, PHOTO_BOTS, session)))

        # Start 5 video workers
        for _ in range(5):
            workers.append(asyncio.create_task(worker(queue_video, VIDEO_BOTS, session)))

        # Wait for queues to be processed
        await queue_photo.join()
        await queue_video.join()

        # Cancel worker tasks after queue is done
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    print("[INFO] All uploads completed.")

if __name__ == "__main__":
    asyncio.run(main())
