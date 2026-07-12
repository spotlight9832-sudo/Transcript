"""
Telegram bot: fetches transcripts from YouTube and RedNote (Xiaohongshu).

- YouTube: reads the platform's own caption data directly (fast, no
  download needed). Offers a language-picker since multiple caption
  tracks can exist for one video.
- RedNote: has no caption API, so the bot downloads the post's audio and
  runs it through a local, free speech-to-text model instead. Slower,
  and the download step can occasionally fail — see
  sources/rednote_source.py for why.

Setup instructions are in README.md.
"""

import asyncio
import logging
import os
import tempfile

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from chunking import chunk_text
from sources import rednote_source, youtube_source
from transcription.backends import get_transcription_backend

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TEMP_DIR = os.path.join(tempfile.gettempdir(), "yt-transcript-bot")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Namaste! Mujhe YouTube ya RedNote (Xiaohongshu) ka link bhejo.\n\n"
        "YouTube: available caption languages dikhaunga, tum choose karoge.\n"
        "RedNote: audio nikaal ke free local speech-to-text se transcript "
        "banaunga — isme thoda zyada time lagta hai, aur download kabhi "
        "kabhi fail bhi ho sakta hai (README mein wajah likhi hai)."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""

    video_id = youtube_source.extract_video_id(text)
    if video_id:
        await handle_youtube_link(update, context, video_id)
        return

    rednote_url = rednote_source.extract_rednote_url(text)
    if rednote_url:
        await handle_rednote_link(update, context, rednote_url)
        return

    await update.message.reply_text(
        "Ye YouTube ya RedNote (Xiaohongshu) ka link nahi laga. Pura link bhejo, jaise:\n"
        "https://www.youtube.com/watch?v=XXXXXXXXXXX\n"
        "https://xhslink.com/o/XXXXXXXX"
    )


# ---------- YouTube flow ----------

async def handle_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE, video_id: str) -> None:
    status_msg = await update.message.reply_text("Available languages check kar raha hoon...")

    try:
        transcript_list = youtube_source.list_transcripts(video_id)
    except youtube_source.TranscriptsDisabled:
        await status_msg.edit_text("Is video par transcripts/captions disabled hain.")
        return
    except youtube_source.VideoUnavailable:
        await status_msg.edit_text("Ye video available nahi hai (private/deleted ho sakta hai).")
        return
    except youtube_source.AgeRestricted:
        await status_msg.edit_text("Ye video age-restricted hai, bina login ke access nahi ho sakta.")
        return
    except youtube_source.InvalidVideoId:
        await status_msg.edit_text("Video link/ID sahi format mein nahi hai.")
        return
    except youtube_source.PoTokenRequired:
        await status_msg.edit_text(
            "YouTube is video ke liye extra bot-verification (PoToken) maang raha hai. "
            "Ye library ki abhi ki known limitation hai — proxy isko fix nahi karega. "
            "Koi doosra video try karo."
        )
        return
    except youtube_source.RequestBlocked:
        await status_msg.edit_text(
            "YouTube ne is server ka IP block kar diya hai. .env mein "
            "WEBSHARE_PROXY_USERNAME/PASSWORD set karo — README.md mein steps hain."
        )
        return
    except Exception as e:
        logger.exception("list_transcripts failed for %s", video_id)
        await status_msg.edit_text(f"Kuch gadbad ho gayi: {e}")
        return

    buttons = []
    for t in transcript_list:
        label = f"{t.language} ({'auto' if t.is_generated else 'manual'})"
        callback_data = f"yt|{video_id}|{t.language_code}|{int(t.is_generated)}"
        buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])

    if not buttons:
        await status_msg.edit_text("Is video ke liye koi transcript nahi mila.")
        return

    # Cache the TranscriptList so selecting a language doesn't need a second
    # network round-trip to YouTube (fewer requests = less blocking risk).
    context.chat_data.setdefault("transcript_lists", {})[video_id] = transcript_list
    await status_msg.edit_text("Language chuno:", reply_markup=InlineKeyboardMarkup(buttons))


async def handle_language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    _, video_id, lang_code, is_generated_flag = query.data.split("|")
    await query.edit_message_text(f"'{lang_code}' transcript fetch kar raha hoon...")

    transcript_list = context.chat_data.get("transcript_lists", {}).get(video_id)

    try:
        if transcript_list is None:
            # Cache miss (e.g. bot restarted between steps) - refetch.
            transcript_list = youtube_source.list_transcripts(video_id)
        full_text = youtube_source.fetch_transcript_text(
            transcript_list, video_id, lang_code, is_generated_flag == "1"
        )
    except youtube_source.NoTranscriptFound:
        await query.message.reply_text("Ye transcript ab available nahi mila, video link dobara bhejo.")
        return
    except youtube_source.PoTokenRequired:
        await query.message.reply_text(
            "YouTube is video ke liye extra bot-verification (PoToken) maang raha hai — "
            "proxy isko fix nahi karega, ye library ki abhi ki limitation hai."
        )
        return
    except youtube_source.RequestBlocked:
        await query.message.reply_text(
            "YouTube ne is server ka IP block kar diya hai. Webshare proxy set karo (README.md dekho)."
        )
        return
    except Exception as e:
        logger.exception("fetch_transcript_text failed for %s / %s", video_id, lang_code)
        await query.message.reply_text(f"Transcript fetch nahi ho paya: {e}")
        return

    if not full_text.strip():
        await query.message.reply_text("Transcript khali mila, kuch text nahi tha.")
        return

    await send_as_chunks(query.message, full_text)


# ---------- RedNote flow ----------

async def handle_rednote_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    status_msg = await update.message.reply_text(
        "RedNote se audio download ho raha hai... (thoda time lag sakta hai)"
    )
    loop = asyncio.get_running_loop()

    try:
        # yt-dlp is blocking/synchronous - run it off the event loop so the
        # bot stays responsive to other chats while this downloads.
        audio_path = await loop.run_in_executor(
            None, rednote_source.download_audio, url, TEMP_DIR
        )
    except rednote_source.RedNoteDownloadError as e:
        await status_msg.edit_text(
            f"RedNote se download nahi ho paya: {e}\n\n"
            "RedNote abhi automated downloads par CAPTCHA/blocks laga raha hai — "
            "har link par kaam karne ki guarantee nahi hai, ye known limitation hai. "
            "`pip install -U yt-dlp` karke ek baar retry kar sakte ho."
        )
        return
    except Exception as e:
        logger.exception("RedNote download failed for %s", url)
        await status_msg.edit_text(f"Download mein gadbad ho gayi: {e}")
        return

    await status_msg.edit_text(
        "Download ho gaya. Ab speech-to-text chal raha hai (local model — "
        "pehli baar model download bhi hoga, thoda time lagega)..."
    )

    try:
        backend = get_transcription_backend()
        full_text = await loop.run_in_executor(None, backend.transcribe, audio_path)
    except Exception as e:
        logger.exception("Transcription failed for %s", audio_path)
        await status_msg.edit_text(f"Transcribe nahi ho paya: {e}")
        return
    finally:
        rednote_source.cleanup(audio_path)

    if not full_text.strip():
        await status_msg.edit_text("Is audio mein koi speech detect nahi hui.")
        return

    await status_msg.edit_text("Transcript ready, bhej raha hoon...")
    await send_as_chunks(status_msg, full_text)


# ---------- shared ----------

async def send_as_chunks(message, full_text: str) -> None:
    chunks = chunk_text(full_text)
    total = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        await message.reply_text(chunk)
        if i < total:
            await asyncio.sleep(0.6)  # stay well under Telegram's flood limits


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN set nahi hai — .env file banao (README.md dekho).")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_language_choice, pattern=r"^yt\|"))

    logger.info("Bot polling shuru...")
    app.run_polling()


if __name__ == "__main__":
    main()
