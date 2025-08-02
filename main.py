import telegram
from telegram import Update
# ... (بقية الـ imports من الكود القديم)
import json
import os
import logging
from functools import wraps
import asyncio
from datetime import datetime

# المكتبات الجديدة للذكاء الاصطناعي
import chromadb
from sentence_transformers import SentenceTransformer

# --- الإعدادات ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

ADMIN_ID = 720330522
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
QUESTIONS_FILE = 'questions.json' # ما زلنا نحتاجه لواجهة الآدمن
STATS_FILE = 'stats.json'
QUESTIONS_PER_PAGE = 5

# إعدادات قاعدة البيانات الذكية
DB_PATH = "./chroma_db"
COLLECTION_NAME = "barnes_questions"

# --- تحميل النماذج عند بدء التشغيل ---
print("Initializing AI models...")
try:
    model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)
    print("AI models loaded successfully.")
except Exception as e:
    print(f"CRITICAL ERROR: Could not load AI models. {e}")
    print("Please run sync_db.py first to create the database.")
    model = None
    collection = None

# ... (كل دوال الآدمن والديكوريتور وملفات JSON تبقى كما هي لأنها مفيدة لواجهة التحكم) ...
# (PANEL_ROUTES, ADD_QUESTION, etc.)
# (admin_only, load_data, save_data)
# (start, admin_panel, and all admin conversation functions)
# --- نسخ ولصق كل دوال الآدمن من الكود القديم هنا ---
(PANEL_ROUTES, ADD_QUESTION, ADD_ANSWER, PHOTO_RECEIVE, PHOTO_QUESTION, PHOTO_ANSWER, DELETE_SEARCH, DELETE_CHOICE) = range(8)

def admin_only(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            if update.callback_query: await update.callback_query.answer("هذا الأمر للآدمن فقط.", show_alert=True)
            else: await update.message.reply_text("هذا الأمر للآدمن فقط.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def load_data(file_path, default_data={}):
    try:
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f: json.dump(default_data, f)
        with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception as e:
        logging.error(f"Error loading {file_path}: {e}"); return default_data

def save_data(data, file_path):
    try:
        with open(file_path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e: logging.error(f"Error saving {file_path}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = load_data(STATS_FILE, default_data={"users": [], "last_added": "N/A"})
    if user_id not in stats["users"]:
        stats["users"].append(user_id)
        save_data(stats, STATS_FILE)
    welcome_message = ("أهلاً بك! أنا بوت بسام لمساعدتك في حل أسئلة بارنز كافيه. أرسل لي أي سؤال." "\n\n---\n*إذا استفدت من البوت، فلا تنساني ووالديّ من صالح دعائك.*")
    if user_id == ADMIN_ID: welcome_message += "\n\nبصفتك الآدمن، استخدم /admin لعرض لوحة التحكم."
    await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
# --- ## دالة البحث الجديدة والمطورة ## ---
async def handle_regular_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not model or not collection:
        await update.message.reply_text("عذراً، نظام الذكاء الاصطناعي لا يعمل حالياً. يرجى إبلاغ الآدمن.")
        return

    question = update.message.text.strip()
    processing_message = await update.message.reply_text("⏳ جارٍ البحث في قاعدة المعرفة...")
    
    # تحويل سؤال المستخدم إلى فيكتور
    question_embedding = model.encode([question])
    
    # البحث في قاعدة البيانات عن أقرب تطابق
    results = collection.query(
        query_embeddings=question_embedding.tolist(),
        n_results=1
    )
    
    # التحقق من جودة النتيجة
    if results and results['distances'][0][0] < 0.5: # 0.5 هو حد الثقة، يمكن تعديله
        answer = results['metadatas'][0][0]['answer']
        await processing_message.edit_text(answer)
    else:
        # TODO: هنا سنضيف المرحلة الثانية (البحث الخارجي و Gemini)
        if update.effective_user.id == ADMIN_ID:
            not_found_message = "لم أجد إجابة مطابقة بدقة في قاعدة المعرفة الداخلية."
        else:
            not_found_message = "عذراً، لم أجد إجابة دقيقة لهذا السؤال في قاعدة بياناتي."
        await processing_message.edit_text(not_found_message)

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (الكود كما هو) ...
    pass
# ... (انسخ والصق كل دوال محادثات الآدمن هنا) ...

def main():
    if not TOKEN:
        print("خطأ فادح: لم يتم العثور على توكن البوت.")
        return
    
    application = Application.builder().token(TOKEN).build()

    # ... (تسجيل كل معالجات الآدمن كما كانت) ...
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_regular_question))
    
    print("بوت بسام يعمل الآن بقاعدة المعرفة الذكية...")
    application.run_polling()

if __name__ == '__main__':
    main()
