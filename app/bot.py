import os
import requests
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS
import hashlib
import logging
import mimetypes
import signal
import asyncio
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
import time

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=os.getenv("LOG_LEVEL", "INFO")
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

BOT_NAME = os.getenv("BOT_NAME", "Telegram to Immich Bot")
BOT_VERSION = "0.8"

def validate_config():
    """Validate required environment variables."""
    missing_vars = []

    if not TELEGRAM_BOT_TOKEN:
        missing_vars.append("TELEGRAM_BOT_TOKEN")
    if not IMMICH_API_KEY:
        missing_vars.append("IMMICH_API_KEY")
    if not IMMICH_API_URL:
        missing_vars.append("IMMICH_API_URL")

    if not ALLOWED_USER_IDS:
        missing_vars.append("ALLOWED_USER_IDS")

    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

IMMICH_API_URL = os.getenv("IMMICH_API_URL", "http://your-immich-instance.ltd/api")
IMMICH_API_KEY = os.getenv("IMMICH_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

allowed_user_ids = os.getenv("ALLOWED_USER_IDS")
if not allowed_user_ids:
    raise ValueError("ALLOWED_USER_IDS environment variable is required")

ALLOWED_USER_IDS = [int(user_id.strip()) for user_id in allowed_user_ids.split(",") if user_id.strip()]
validate_config()

SUPPORTED_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.heic', '.heif', '.webp')
SUPPORTED_VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.3gp', '.m4v')
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS
SUPPORTED_FILE_TYPES = (
    "Images: JPG, PNG, GIF, BMP, TIFF, HEIC, WEBP\n"
    "Videos: MP4, MOV, AVI, MKV, WEBM, 3GP"
)

def get_file_type(file_path):
    """Determine file type based on extension and MIME type."""
    ext = os.path.splitext(file_path)[1].lower()
    mime_type, _ = mimetypes.guess_type(file_path)

    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        return "image"
    elif ext in SUPPORTED_VIDEO_EXTENSIONS:
        return "video"
    elif mime_type and mime_type.startswith('video/'):
        return "video"
    elif mime_type and mime_type.startswith('image/'):
        return "image"
    return "other"

def is_user_allowed(user_id):
    """Check if a user is allowed to upload files. If not set, all users can upload files"""
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS

def format_iso_date(dt):
    """Format datetime as ISO 8601 with Z timezone."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def get_image_metadata(file_path):
    """Extract metadata from image files."""
    try:
        with Image.open(file_path) as img:
            exif_data = img._getexif() or {}
            metadata = {TAGS.get(tag, tag): value for tag, value in exif_data.items()}

            if 'DateTimeOriginal' in metadata:
                created_at = datetime.strptime(metadata['DateTimeOriginal'], '%Y:%m:%d %H:%M:%S')
                # If there's no timezone info (common in EXIF), assume generic or UTC
                # Though technically EXIF is usually local. But keeping simple for now.
                # However format_iso_date expects a datetime object.
                # If it's naive, we might want to make it aware or just pass it.
            elif 'DateTime' in metadata:
                created_at = datetime.strptime(metadata['DateTime'], '%Y:%m:%d %H:%M:%S')
            else:
                 # Raise exception to trigger fallback
                 raise ValueError("No date in EXIF")

            return format_iso_date(created_at), format_iso_date(datetime.now(timezone.utc))
    except Exception:
        raise ValueError("Could not extract image metadata")

def get_video_metadata(file_path):
    """Extract creation date from video files using hachoir."""
    try:
        parser = createParser(file_path)
        if not parser:
            return None
            
        with parser:
            metadata = extractMetadata(parser)
            if not metadata:
                return None
            
            # Check for generic creation date
            creation_date = metadata.get('creation_date')
            if creation_date:
                # hachoir returns datetime object
                return format_iso_date(creation_date), format_iso_date(creation_date)
            
    except Exception as e:
        logger.warning(f"Failed to extract video metadata: {e}")
    
    raise ValueError("Could not extract video metadata")

def calculate_sha1(file_path):
    """Calculate SHA1 checksum of a file."""
    sha1 = hashlib.sha1()
    with open(file_path, 'rb') as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()

def check_immich_connection():
    """Simple check if Immich server is reachable."""
    try:
        response = requests.get(
            f"{IMMICH_API_URL}/server/ping",
            headers={'x-api-key': IMMICH_API_KEY},
            timeout=5
        )
        return response.status_code == 200
    except Exception:
        return False

async def get_immich_status():
    """Check Immich server status and user info."""
    immich_status = "❌ Disconnected"
    user_info = "Unknown user"

    try:
        logger.debug(f"Checking Immich status at {IMMICH_API_URL}")
        ping_response = requests.get(
            f"{IMMICH_API_URL}/server/ping",
            headers={'x-api-key': IMMICH_API_KEY},
            timeout=5
        )

        if ping_response.status_code == 200:
            immich_status = f"✅ Connected to Immich ({IMMICH_API_URL})"

            # If reachable, get user info
            try:
                user_response = requests.get(
                    f"{IMMICH_API_URL}/users/me",
                    headers={'x-api-key': IMMICH_API_KEY},
                    timeout=5
                )
                if user_response.status_code == 200:
                    try:
                        user_data = user_response.json()
                        user_info = f"👤 {user_data.get('name', 'Unknown')}"
                        if user_data.get('isAdmin', False):
                            user_info += " [Admin]"
                    except ValueError:
                        logger.error(f"Failed to decode JSON from Immich response. Status: {user_response.status_code}")
                        logger.error(f"Response Body: {user_response.text}")
                        user_info = "⚠️ Invalid response from Immich" 
                else:
                    logger.error(f"Failed to get user info. Status: {user_response.status_code}, Response: {user_response.text}")
                    user_info = f"⚠️ Could not retrieve user info ({user_response.status_code})"
            except Exception as e:
                logger.error(f"Failed to get user info: {e}", exc_info=True)
                user_info = "⚠️ Could not retrieve user info"
        else:
            immich_status = f"❌ Server ping failed (HTTP {ping_response.status_code})"
            logger.error(f"Server ping failed. Status: {ping_response.status_code}, Response: {ping_response.text}")

    except Exception as e:
        logger.error(f"Failed to connect to Immich: {e}", exc_info=True)
        immich_status = f"❌ Connection failed: {str(e)}"

    return immich_status, user_info

async def send_startup_message(application: Application):
    """Send startup message to all allowed users when container starts."""
    immich_status, user_info = await get_immich_status()

    if "Connected" in immich_status:
        logger.info("==========================================================")
        logger.info(f"✅ CONNECTION SUCCESSFUL: Linked to Immich instance")
        logger.info(f"   URL: {IMMICH_API_URL}")
        logger.info(f"   User: {user_info}") 
        logger.info("==========================================================")
    else:
        logger.error("==========================================================")
        logger.error(f"❌ CONNECTION FAILED: Could not link to Immich instance")
        logger.error(f"   Status: {immich_status}") 
        logger.error("==========================================================")

    startup_message = (
        f"🤖 {BOT_NAME} v{BOT_VERSION} has started!\n\n"
        f"{immich_status}\n"
        f"Logged in as {user_info}\n\n"
        "Bot is ready to receive your files."
    )

    logger.info(f"Sending startup messages to {len(ALLOWED_USER_IDS)} allowed users")

    for user_id in ALLOWED_USER_IDS:
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=startup_message
            )
            logger.info(f"Successfully sent startup message to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send startup message to user {user_id}: {e}")

async def send_shutdown_message(application: Application):
    """Send shutdown message to allowed users."""
    logger.info("Sending shutdown messages...")
    shutdown_message = f"🛑 {BOT_NAME} is shutting down."
    
    for user_id in ALLOWED_USER_IDS:
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=shutdown_message
            )
        except Exception as e:
            logger.error(f"Failed to send shutdown message to user {user_id}: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message with Immich connection status."""
    immich_status, user_info = await get_immich_status()

    help_message = (
        f"ℹ️ {BOT_NAME} v{BOT_VERSION}\n\n"
        f"{immich_status}\n"
        f"Logged in as {user_info}\n\n"
        "Available commands:\n"
        "/help - Show this help message\n"
        "/version - Show bot version\n"
        "/files - Show supported file types\n\n"
        "Send me files and I'll upload them to your Immich instance!"
    )

    await update.message.reply_text(help_message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for help command."""
    await help_command(update, context)

async def version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the bot version when the command /version is issued."""
    await update.message.reply_text(f"📋 {BOT_NAME} version: {BOT_VERSION}")

async def files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send supported file types when the command /files is issued."""
    await update.message.reply_text(f"📄 Supported file types:\n{SUPPORTED_FILE_TYPES}")

async def upload_to_immich(update: Update, file_path: str, file_name: str, file_type: str, message_date: datetime = None):
    """Helper to upload a file to Immich."""
    try:
        file_size = os.path.getsize(file_path)
        logger.debug(f"Processing {file_type} file: {file_name} ({file_size} bytes)")

        # Determine creation date
        # Priority:
        # 1. File Metadata (EXIF for images, Headers for video)
        # 2. Original Message Date (forward_date) - passed as message_date
        # 3. Message Date (date) - passed as message_date if forward_date is None
        # 4. Current Time
        
        file_created_at = None
        
        # 1. Try Metadata
        try:
            if file_type == "image":
                file_created_at, _ = get_image_metadata(file_path)
                logger.debug("Used image EXIF data for date")
            elif file_type == "video":
                file_created_at, _ = get_video_metadata(file_path)
                logger.debug("Used video metadata for date")
        except Exception:
            logger.debug(f"No internal metadata found for {file_type}")
            pass

        # 2 & 3. Try Message Date
        if not file_created_at and message_date:
             file_created_at = format_iso_date(message_date)
             logger.info("Used message date for date")

        # 4. Fallback to now
        if not file_created_at:
             now = datetime.now(timezone.utc)
             file_created_at = format_iso_date(now)
             logger.info("Used current time for date (fallback)")

        file_modified_at = file_created_at
        
        device_asset_id = f"{file_name}-{file_size}"
        checksum = calculate_sha1(file_path)
        logger.debug(f"Calculated checksum {checksum} for file {file_name}")

        with open(file_path, 'rb') as f:
            files = {'assetData': (file_name, f)}
            data = {
                'deviceAssetId': device_asset_id,
                'deviceId': 'telegram-bot-device',
                'fileCreatedAt': file_created_at,
                'fileModifiedAt': file_modified_at,
                'isFavorite': 'false',
                'visibility': 'timeline'
            }
            headers = {
                'x-api-key': IMMICH_API_KEY,
                'x-immich-checksum': checksum
            }

            logger.debug(f"⬆️ STARTED UPLOAD: Uploading {file_type} {file_name} to Immich server...")
            response = requests.post(
                f"{IMMICH_API_URL}/assets",
                headers=headers,
                files=files,
                data=data
            )

            if response.status_code in (200, 201):
                response_data = response.json()
                if response.status_code == 200 and response_data.get('status') == 'duplicate':
                    logger.info(f"{file_type.capitalize()} {file_name} is a duplicate in Immich")
                    await update.message.reply_text(f"ℹ️ {file_type.capitalize()} already exists in Immich.")
                else:
                    logger.info(f"Successfully uploaded {file_type} {file_name} to Immich")
                    await update.message.reply_text(f"✅ {file_type.capitalize()} uploaded successfully!")
            else:
                logger.error(f"Failed to upload {file_type} {file_name} to Immich. Status code: {response.status_code}, Response: {response.text}")
                await update.message.reply_text(f"❌ Failed to upload {file_type}. Error: {response.text}")

    except Exception as e:
        logger.error(f"Error uploading {file_name}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ An error occurred during upload: {str(e)}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads with improved logging."""
    # Check connection first
    if not check_immich_connection():
         await update.message.reply_text("❌ cannot connect to immich. please try again later or check the logs.")
         return

    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    file_name = update.message.document.file_name

    logger.info(f"Processing file upload from user {username} (ID: {user_id}): {file_name}")

    try:
        # Check user permission
        if not is_user_allowed(user_id):
            logger.debug(f"Unauthorized upload attempt by user {username} (ID: {user_id})")
            return

        document = update.message.document
        file_id = document.file_id
        temp_file_path = f"/tmp/{file_id}_{file_name}"

        logger.info(f"Downloading file {file_name} from Telegram")
        file = await context.bot.get_file(file_id)
        await file.download_to_drive(temp_file_path)

        if not os.path.exists(temp_file_path):
            logger.error(f"Failed to download file {file_name} from Telegram")
            await update.message.reply_text("❌ Failed to download file.")
            return

        # Check file type
        file_type = get_file_type(file_name)
        if file_type == "other":
            logger.warning(f"User {username} (ID: {user_id}) attempted to upload unsupported file type: {file_name}")
            await update.message.reply_text("❌ Unsupported file type. Only images and videos are currently supported.")
            return

        # Get message date (prefer forward_date if available)
        message_date = getattr(update.message, 'forward_date', None) or update.message.date
        
        await upload_to_immich(update, temp_file_path, file_name, file_type, message_date)

    except Exception as e:
        logger.error(f"Unexpected error processing file {file_name} for user {username}: {str(e)}", exc_info=True)
        await update.message.reply_text("❌ An unexpected error occurred. Please try again later.")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.debug(f"Cleaned up temporary file: {temp_file_path}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads (when users send pictures as photos)."""
    # Check connection first
    if not check_immich_connection():
         await update.message.reply_text("❌ cannot connect to immich. please try again later or check the logs.")
         return

    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    photo = update.message.photo[-1]
    file_id = photo.file_id
    file_name = f"photo_{file_id}.jpg"

    logger.debug(f"Processing photo upload from user {username} (ID: {user_id})")

    # Check user permission
    if not is_user_allowed(user_id):
        logger.debug(f"Unauthorized upload attempt: {username} (ID: {user_id})")
        return

    temp_file_path = f"/tmp/{file_id}_{file_name}"

    try:
        logger.info(f"Downloading photo {file_name} from Telegram")
        file = await context.bot.get_file(file_id)
        await file.download_to_drive(temp_file_path)

        if not os.path.exists(temp_file_path):
            logger.error(f"Failed to download photo {file_name}")
            await update.message.reply_text("❌ Failed to download photo.")
            return

        # Get message date (prefer forward_date if available)
        message_date = getattr(update.message, 'forward_date', None) or update.message.date

        await upload_to_immich(update, temp_file_path, file_name, "image", message_date)

    except Exception as e:
        logger.error(f"Error processing photo {file_name}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.debug(f"Cleaned up temporary photo file: {temp_file_path}")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video uploads."""
    # Check connection first
    if not check_immich_connection():
         await update.message.reply_text("❌ cannot connect to immich. please try again later or check the logs.")
         return

    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    
    # Check user permission
    if not is_user_allowed(user_id):
        logger.debug(f"Unauthorized video upload attempt by user {username} (ID: {user_id})")
        return

    video = update.message.video
    file_id = video.file_id
    # Use file_name if available, otherwise generate one
    file_name = getattr(video, 'file_name', None) or f"video_{file_id}.mp4"
    
    logger.info(f"Processing video upload from user {username} (ID: {user_id}): {file_name}")

    temp_file_path = f"/tmp/{file_id}_{file_name}"

    try:
        logger.debug(f"Downloading video {file_name} from Telegram")
        file = await context.bot.get_file(file_id)
        await file.download_to_drive(temp_file_path)

        if not os.path.exists(temp_file_path):
            logger.error(f"Failed to download video {file_name}")
            await update.message.reply_text("❌ Failed to download video.")
            return

        # Get message date (prefer forward_date if available)
        # Check if message is a forward first (the attribute might not exist or be None)
        message_date = getattr(update.message, 'forward_date', None) or update.message.date

        await upload_to_immich(update, temp_file_path, file_name, "video", message_date)

    except Exception as e:
        logger.error(f"Error processing video {file_name}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.debug(f"Cleaned up temporary video file: {temp_file_path}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    
    if not is_user_allowed(user_id):
        logger.debug(f"Unauthorized message from user {username} (ID: {user_id})")
        return

    text = update.message.text
    
    logger.info(f"Received message from user {username} (ID: {user_id}): {text}")

    if not check_immich_connection():
        await update.message.reply_text("❌ cannot connect to immich. please try again later or check the logs.")
    else:
        await update.message.reply_text("✅ Immich is connected. Send me an image or file to upload!")

def main():
    """Start the bot with command handlers."""
    try:
        validate_config()

        # logging is already configured at module level

        application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_stop(send_shutdown_message).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("version", version))
        application.add_handler(CommandHandler("files", files))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.VIDEO, handle_video))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            asyncio.create_task(send_startup_message(application))
        else:
            loop.run_until_complete(send_startup_message(application))

        logger.info(f"{BOT_NAME} v{BOT_VERSION} started successfully")
        logger.info(f"Allowed users: {ALLOWED_USER_IDS}")

        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    main()
