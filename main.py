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
import logging
from functools import wraps

# --- الإعدادات ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# !! هام: استبدل الرقم صفر برقم الـ ID الخاص بك !!
ADMIN_ID = 0 

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
QUESTIONS_FILE = 'questions.json'

# تعريف حالات المحادثات المختلفة
(ADD_QUESTION, ADD_ANSWER) = range(2)
(PHOTO_QUESTION, PHOTO_ANSWER) = range(2, 4)
(DELETE_CHOICE) = range(4, 5)

# --- Decorator للتحقق من الآدمن ---
def admin_only(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("هذا الأمر للآدمن فقط.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- وظائف مساعدة للتعامل مع ملف JSON ---
def load_data():
    if not os.path.exists(QUESTIONS_FILE):
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- أوامر المستخدم العادي ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = "أهلاً بك! أنا بوت بسام لمساعدتك في حل أسئلة بارنز كافيه. أرسل لي أي سؤال."
    if update.effective_user.id == ADMIN_ID:
        welcome_message += "\n\nبصفتك الآدمن، يمكنك استخدام /adminhelp لعرض أوامر التحكم."
    await update.message.reply_text(welcome_message)

async def handle_regular_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    question = update.message.text.strip()
    data = load_data()
    
    for q, a in data.items():
        if question.lower() in q.lower() or q.lower() in question.lower():
            await update.message.reply_text(f"من الأرشيف: {a}")
            return

    if user.id == ADMIN_ID:
        await update.message.reply_text("هذا السؤال غير موجود. استخدم /add لإضافته نصياً، أو أرسل صورة السؤال مباشرة.")
    else:
        await update.message.reply_text("عذراً، لم أجد إجابة لهذا السؤال في قاعدة بياناتي الحالية.")

# --- أوامر الآدمن ---

@admin_only
async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
    **أوامر الآدمن الاحترافية:**

    /add - إضافة سؤال وجواب جديد.
    /list - عرض كل الأسئلة في الأرشيف.
    /delete - حذف سؤال من الأرشيف.
    /cancel - إلغاء العملية الحالية.
    
    يمكنك أيضاً إرسال صورة مباشرة لبدء عملية الإضافة من صورة.
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# --- محادثة إضافة سؤال نصي ---
@admin_only
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("حسناً، أرسل لي نص السؤال الجديد الذي تريد إضافته.")
    return ADD_QUESTION

async def add_get_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_question'] = update.message.text
    await update.message.reply_text("تمام. الآن أرسل لي الجواب الصحيح لهذا السؤال.")
    return ADD_ANSWER

async def add_get_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    question = context.user_data['new_question']
    answer = update.message.text
    data = load_data()
    data[question] = answer
    save_data(data)
    await update.message.reply_text(f"✅ تم حفظ السؤال بنجاح!")
    context.user_data.clear()
    return ConversationHandler.END

# --- محادثة حذف سؤال ---
@admin_only
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = load_data()
    if not data:
        await update.message.reply_text("الأرشيف فارغ، لا يوجد ما يمكن حذفه.")
        return ConversationHandler.END
    
    context.user_data['questions_for_deletion'] = list(data.keys())
    message = "اختر رقم السؤال الذي تريد حذفه:\n\n"
    for i, q in enumerate(context.user_data['questions_for_deletion'], 1):
        message += f"{i}. {q}\n"
    
    await update.message.reply_text(message)
    return DELETE_CHOICE

async def delete_get_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        choice = int(update.message.text)
        questions = context.user_data['questions_for_deletion']
        if 1 <= choice <= len(questions):
            question_to_delete = questions[choice - 1]
            data = load_data()
            del data[question_to_delete]
            save_data(data)
            await update.message.reply_text(f"🗑️ تم حذف السؤال بنجاح: '{question_to_delete}'")
        else:
            await update.message.reply_text("رقم غير صالح. حاول مرة أخرى أو استخدم /cancel.")
            return DELETE_CHOICE
    except (ValueError, IndexError):
        await update.message.reply_text("إدخال غير صالح. الرجاء إرسال رقم فقط.")
        return DELETE_CHOICE
    
    context.user_data.clear()
    return ConversationHandler.END

# --- عرض كل الأسئلة ---
@admin_only
async def list_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data:
        await update.message.reply_text("الأرشيف فارغ حالياً.")
        return

    message = "📖 **الأسئلة الموجودة في الأرشيف:**\n\n"
    for i, (q, a) in enumerate(data.items(), 1):
        message += f"**{i}. السؤال:** {q}\n**الجواب:** {a}\n---\n"
    
    # إرسال الرسالة في أجزاء إذا كانت طويلة جداً
    for i in range(0, len(message), 4096):
        await update.message.reply_text(message[i:i + 4096], parse_mode='Markdown')

# --- محادثة إضافة سؤال من صورة (موجودة سابقاً) ---
@admin_only
async def photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = await update.message.photo[-1].get_file()
    photo_path = f'{photo_file.file_id}.jpg'
    await photo_file.download_to_drive(photo_path)
    await update.message.reply_text('تم استلام الصورة. جارٍ قراءة النص...')
    try:
        extracted_text = pytesseract.image_to_string(Image.open(photo_path), lang='ara+eng')
        os.remove(photo_path)
        if not extracted_text.strip():
            await update.message.reply_text('لم أتمكن من قراءة أي نص. حاول بصورة أوضح.')
            return ConversationHandler.END
        await update.message.reply_text(f"النص المستخرج:\n---\n{extracted_text}\n---\n\nالآن، أرسل السؤال الصحيح.")
        return PHOTO_QUESTION
    except Exception as e:
        logging.error(f"OCR Error: {e}")
        await update.message.reply_text('حدث خطأ أثناء قراءة الصورة.')
        return ConversationHandler.END

async def photo_get_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_question'] = update.message.text
    await update.message.reply_text("تمام. الآن أرسل الجواب الصحيح.")
    return PHOTO_ANSWER

async def photo_get_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await add_get_answer(update, context) # Re-use the same final step

# --- إلغاء المحادثة ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data:
        context.user_data.clear()
    await update.message.reply_text('تم إلغاء العملية الحالية.')
    return ConversationHandler.END

# --- كتلة التنفيذ الرئيسية ---
def main():
    if not TOKEN:
        print("خطأ: لم يتم العثور على توكن البوت.")
        return
    if ADMIN_ID == 0:
        print("خطأ: يجب تحديد رقم الآدمن (ADMIN_ID) في الشيفرة.")
        return

    application = Application.builder().token(TOKEN).build()

    # محادثة الإضافة النصية
    add_conv = ConversationHandler(
        entry_points=[CommandHandler('add', add_start)],
        states={
            ADD_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_question)],
            ADD_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_answer)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # محادثة الإضافة من صورة
    photo_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, photo_start)],
        states={
            PHOTO_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, photo_get_question)],
            PHOTO_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, photo_get_answer)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # محادثة الحذف
    delete_conv = ConversationHandler(
        entry_points=[CommandHandler('delete', delete_start)],
        states={
            DELETE_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_get_choice)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # تسجيل كل الأوامر والمحادثات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("adminhelp", admin_help))
    application.add_handler(CommandHandler("list", list_questions))
    application.add_handler(add_conv)
    application.add_handler(photo_conv)
    application.add_handler(delete_conv)
    
    # معالج الرسائل العادية يجب أن يكون الأخير
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_regular_question))
    
    print("بوت بسام يعمل الآن بالواجهة الاحترافية للآدمن...")
    application.run_polling()

if __name__ == '__main__':
    main()
