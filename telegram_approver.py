import os
import asyncio
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler
from telegram.request import HTTPXRequest

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

class TelegramApprovalSession:
    def __init__(self):
        self.decision = None
        self.decision_event = asyncio.Event()

    async def handle_callback(self, update: Update, context):
        query = update.callback_query
        await query.answer()

        if query.data == "approve":
            self.decision = "approved"
            await query.edit_message_caption(caption="✅ Approved! Uploading directly to YouTube Shorts...")
        elif query.data == "reject":
            self.decision = "rejected"
            await query.edit_message_caption(caption="❌ Discarded. Video will not be published.")
        
        self.decision_event.set()

async def request_approval(video_path: str, metadata: dict) -> str:
    """
    Sends the video file and metadata to your Telegram with interactive buttons.
    Waits until you press [Approve] or [Discard] on your phone, then returns the result.
    """
    session = TelegramApprovalSession()
    req = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=300.0,
        write_timeout=300.0,
        pool_timeout=300.0
    )
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(req).build()
    app.add_handler(CallbackQueryHandler(session.handle_callback))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve & Publish", callback_data="approve"),
            InlineKeyboardButton("❌ Discard", callback_data="reject")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    tags_formatted = " ".join([f"#{t.strip('#')}" for t in metadata.get("tags", [])])
    caption = (
        f"🎬 *New Short Ready For Review*\n\n"
        f"📌 *Title:* {metadata.get('title', 'Untitled')}\n\n"
        f"📝 *Description:* {metadata.get('description', '')}\n\n"
        f"🏷 *Tags:* {tags_formatted}"
    )

    print("3. Sending video preview and buttons to Telegram...")
    with open(video_path, 'rb') as video_file:
        await app.bot.send_video(
            chat_id=TELEGRAM_CHAT_ID,
            video=video_file,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            read_timeout=300,
            write_timeout=300
        )

    print("⏳ Awaiting your tap on Telegram ([Approve] or [Discard])...")
    await session.decision_event.wait()

    await app.updater.stop()
    await app.stop()
    await app.shutdown()

    return session.decision