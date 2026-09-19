import os
import re
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")

START_MESSAGE = (
    "**أهلاً بك في أقوى بوت تحميل على تليجرام!** 🔥\n\n"
    "راحت أيام روابط المواقع والإعلانات المزعجة! 🥳 هنا تقدر تحمّل أي فيديو أو صورة من "
    "(تيك توك، إنستغرام، يوتيوب، فيسبوك، و Pinterest) بضغطة واحدة وبأعلى جودة! 🎬✨\n\n"
    "**كيف تستخدم البوت?**\n"
    "1️⃣ انسخ رابط الفيديو أو الصورة.\n"
    "2️⃣ أرسل الرابط هنا في المحادثة مباشرة.\n"
    "3️⃣ استلم ملفك خلال ثوانٍ معدودة! ⚡\n\n"
    "💡 *جرّب الآن بإرسال أول رابط، وشوف السرعة بنفسك!*"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_MESSAGE, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not re.match(r'^https?://', url):
        await update.message.reply_text("❌ عذراً، يرجى إرسال رابط صحيح.")
        return

    status_message = await update.message.reply_text("⏳ جاري معالجة الرابط والتحميل السريع... انتظر ثوانٍ 🚀")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_video")

    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }
    }

    try:
        # تشغيل yt-dlp في خيط منفصل لتفادي تجميد البوت على السيرفر
        loop = asyncio.get_event_loop()
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
                
        filename = await loop.run_in_executor(None, download)
        actual_filename = filename
        
        if not os.path.exists(actual_filename):
            base, _ = os.path.splitext(filename)
            for ext in ['mp4', 'mkv', 'webm', 'mp3', 'jpg', 'png', 'jpeg']:
                if os.path.exists(f"{base}.{ext}"):
                    actual_filename = f"{base}.{ext}"
                    break

        if os.path.exists(actual_filename):
            await status_message.delete()
            if actual_filename.lower().endswith(('jpg', 'jpeg', 'png')):
                with open(actual_filename, 'rb') as photo_file:
                    await update.message.reply_photo(photo=photo_file, caption="✨ تم تحميل الصورة بنجاح! 📸")
            else:
                with open(actual_filename, 'rb') as video_file:
                    await update.message.reply_video(video=video_file, caption="✨ تم التحميل بنجاح! 🎬", supports_streaming=True)
            os.remove(actual_filename)
        else:
            raise FileNotFoundError()
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_message.edit_text("❌ تعذر تحميل هذا الرابط حالياً. تأكد من جودة الرابط أو أن المحتوى ليس خاصاً.")

async def main():
    if not TOKEN: 
        logger.error("TELEGRAM_TOKEN missing!")
        return
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # الإصلاح البرمجي لـ Render: تشغيل البوت بشكل متوافق تماماً مع السيرفرات السحابية
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    print("⚡ البوت يعمل الآن بنجاح على استضافة Render المجانية...")
    # إبقاء البوت حياً ومستجيباً
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    # تشغيل الدالة الأساسية بشكل متزامن صحيح
    asyncio.run(main())
