import telegram
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
import json
import os
import requests
import logging
import pytesseract
from PIL import Image

# --- الإعدادات ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# !! هام: استبدل الرقم صفر برقم الـ ID الخاص بك الذي حصلت عليه !!
ADMIN_ID = 0 

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
QUESTIONS_FILE = 'questions.json'

# تعريف حالات المحادثة لإضافة سؤال جديد
PHOTO, QUESTION, ANSWER = range(3)

# --- الوظائف الأساسية ---
def load_known_answers():
    """تحميل الأجوبة من الأرشيف"""
    if not os.path.exists(QUESTIONS_FILE):
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_known_answers(data):
    """حفظ الأجوبة في الأرشيف"""
    with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الاستجابة لأمر البدء"""
    welcome_message = "أهلاً بك! أنا بوت بسام لمساعدتك في حل أسئلة بارنز كافيه. أرسل لي أي سؤال."
    await update.message.reply_text(welcome_message)

async def handle_regular_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأسئلة النصية العادية"""
    question = update.message.text.strip()
    known_answers = load_known_answers()
    
    for known_q, answer in known_answers.items():
        if question.lower() in known_q.lower() or known_q.lower() in question.lower():
            await update.message.reply_text(f"من الأرشيف: {answer}")
            return

    await update.message.reply_text("السؤال غير موجود في أرشيفي... سأبحث لك الآن...")
    # ... (يمكن إضافة كود البحث هنا لاحقاً)
    await update.message.reply_text("لم أجد إجابة في الإنترنت. يمكنك إضافتها يدوياً إذا كنت الآدمن.")

# --- وظائف الآدمن لإضافة سؤال من صورة ---

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يبدأ محادثة إضافة سؤال جديد عند استلام صورة من الآدمن"""
    user = update.message.from_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("هذه الخاصية للآدمن فقط.")
        return ConversationHandler.END

    photo_file = await update.message.photo[-1].get_file()
    photo_path = f'{photo_file.file_id}.jpg'
    await photo_file.download_to_drive(photo_path)
    
    await update.message.reply_text('تم استلام الصورة. جارٍ قراءة النص...')
    
    try:
        extracted_text = pytesseract.image_to_string(Image.open(photo_path), lang='ara+eng')
        if not extracted_text.strip():
             await update.message.reply_text('لم أتمكن من قراءة أي نص من الصورة. حاول إرسال صورة أوضح.')
             os.remove(photo_path)
             return ConversationHandler.END

        await update.message.reply_text(f"النص الذي تم استخراجه:\n\n---\n{extracted_text}\n---\n\nالآن، أرسل لي السؤال بشكل صحيح وواضح.")
        context.user_data['extracted_text'] = extracted_text
        os.remove(photo_path) # حذف الصورة بعد القراءة
        return QUESTION
    except Exception as e:
        logging.error(f"خطأ في قراءة الصورة: {e}")
        await update.message.reply_text('حدث خطأ أثناء محاولة قراءة الصورة.')
        os.remove(photo_path)
        return ConversationHandler.END

async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يحفظ السؤال وينتظر الجواب"""
    question_text = update.message.text
    context.user_data['question'] = question_text
    await update.message.reply_text('ممتاز. الآن أرسل لي الجواب الصحيح لهذا السؤال.')
    return ANSWER

async def get_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يحفظ الجواب في الأرشيف وينهي المحادثة"""
    answer_text = update.message.text
    question = context.user_data['question']
    
    known_answers = load_known_answers()
    known_answers[question] = answer_text
    save_known_answers(known_answers)
    
    await update.message.reply_text(f"تم الحفظ بنجاح!\n\nالسؤال: {question}\nالجواب: {answer_text}\n\nالمحادثة انتهت. يمكنك إرسال صورة جديدة لبدء محادثة أخرى.")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """إلغاء عملية إضافة السؤال"""
    await update.message.reply_text('تم إلغاء العملية.')
    context.user_data.clear()
    return ConversationHandler.END

# --- كتلة التنفيذ الرئيسية ---
def main():
    if not TOKEN:
        print("خطأ فادح: لم يتم العثور على توكن البوت.")
        return
    if ADMIN_ID == 0:
        print("خطأ فادح: يجب تحديد رقم الآدمن (ADMIN_ID) في الشيفرة.")
        return

    application = Application.builder().token(TOKEN).build()

    # محادثة إضافة سؤال جديد للآدمن
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, handle_photo)],
        states={
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_question)],
            ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_answer)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_regular_question))
    
    print("بوت بسام يعمل الآن بالخاصية الجديدة للآدمن...")
    application.run_polling()

if __name__ == '__main__':
    main()
