import os
import re
import logging
import asyncio
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
from fastapi import FastAPI
import uvicorn

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
PORT = int(os.getenv("PORT", 10000))

app_web = FastAPI()

@app_web.get("/")
def read_root():
    return {"status": "Bot is running perfectly!"}

START_MESSAGE = (
    "**أهلاً بك في أقوى بوت تحميل على تليجرام!** 🔥\n\n"
    "راحت أيام روابط المواقع والإعلانات المزعجة! 🥳 هنا تقدر تحمّل أي فيديو أو صورة من "
    "(تيك توك، إنستغرام، يوتيوب، فيسبوك، و Pinterest) بضغطة واحدة وبأعلى جودة! 🎬✨\n\n"
    "**كيف تستخدم البوت؟**\n"
    "1️⃣ انسخ رابط الفيديو أو الصورة.\n"
    "2️⃣ أرسل الرابط هنا في المحادثة مباشرة.\n"
    "3️⃣ استلم ملفك خلال ثوانٍ معدودة! ⚡\n\n"
    "💡 *جرّب الآن بإرسال أول رابط، وشوف السرعة بنفسك!*"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_MESSAGE, parse_mode="Markdown")

async def download_youtube_via_api(url, status_message, update, context):
    """دالة خاصة لتحميل يوتيوب عبر سيرفر خارجي لتخطي حظر Render"""
    try:
        # استخدام API خارجي مجاني ومفتوح لتحميل فيديوهات يوتيوب بدون حظر
        api_url = f"https://cobalt.tools"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        data = {
            "url": url,
            "videoQuality": "720",
            "downloadMode": "auto"
        }
        
        response = requests.post(api_url, json=data, headers=headers, timeout=15)
        res_data = response.json()
        
        if response.status_code == 200 and "url" in res_data:
            video_download_url = res_data["url"]
            await status_message.delete()
            # إرسال الفيديو للمستخدم مباشرة عبر الرابط السحابي لتوفير مساحة السيرفر
            await update.message.reply_video(
                video=video_download_url,
                caption="✨ تم تحميل فيديو يوتيوب بنجاح لتخطي الحظر! 🎬",
                supports_streaming=True
            )
            return True
    except Exception as api_err:
        logger.error(f"Cobalt API Error: {api_err}")
    return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not re.match(r'^https?://', url):
        await update.message.reply_text("❌ عذراً، يرجى إرسال رابط صحيح.")
        return

    status_message = await update.message.reply_text("⏳ جاري معالجة الرابط والتحميل السريع... انتظر ثوانٍ 🚀")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_video")

    # إذا كان الرابط من يوتيوب، نستخدم الـ API الخارجي فوراً لتفادي الحظر الموضح بالصورة
    if "youtube.com" in url or "youtu.be" in url:
        success = await download_youtube_via_api(url, status_message, update, context)
        if success:
            return
        # إذا فشل الـ API نتركه يحاول بالطريقة العادية كخيار احتياطي

    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }
    }

    try:
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
        await status_message.edit_text("❌ تعذر تحميل هذا الرابط حالياً. تأكد أن المحتوى عام وليس خاصاً.")

async def run_bot():
    if not TOKEN: return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await app.initialize()
    await app.updater.start_polling()
    await app.start()

@app_web.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == '__main__':
    uvicorn.run(app_web, host="0.0.0.0", port=PORT)
