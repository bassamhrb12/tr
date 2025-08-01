import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)
import json
import os
import logging
from functools import wraps
import asyncio
from thefuzz import process
import pytesseract
from PIL import Image
from datetime import datetime

# --- الإعدادات ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ADMIN_ID = 720330522
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
QUESTIONS_FILE = 'questions.json'
STATS_FILE = 'stats.json'
QUESTIONS_PER_PAGE = 5

# تعريف حالات المحادثات
(PANEL_ROUTES, ADD_QUESTION, ADD_ANSWER, PHOTO_RECEIVE, PHOTO_QUESTION, PHOTO_ANSWER, DELETE_CHOICE) = range(7)

# --- Decorator للتحقق من الآدمن ---
def admin_only(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            if update.callback_query:
                await update.callback_query.answer("هذا الأمر للآدمن فقط.", show_alert=True)
            else:
                await update.message.reply_text("هذا الأمر للآدمن فقط.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- وظائف مساعدة للتعامل مع ملف JSON ---
def load_data(file_path, default_data={}):
    try:
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_data, f)
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"Error loading {file_path}: {e}")
        return default_data

def save_data(data, file_path):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving {file_path}: {e}")

# --- أوامر المستخدمين ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (الكود كما هو) ...
    user_id = update.effective_user.id
    stats = load_data(STATS_FILE, default_data={"users": [], "last_added": "N/A"})
    if user_id not in stats["users"]:
        stats["users"].append(user_id)
        save_data(stats, STATS_FILE)
    welcome_message = (
        "أهلاً بك! أنا بوت بسام لمساعدتك في حل أسئلة بارنز كافيه. أرسل لي أي سؤال."
        "\n\n---\n*إذا استفدت من البوت، فلا تنساني ووالديّ من صالح دعائك.*"
    )
    if user_id == ADMIN_ID:
        welcome_message += "\n\nبصفتك الآدمن، استخدم /admin لعرض لوحة التحكم."
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def handle_regular_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (الكود كما هو) ...
    question = update.message.text.strip()
    processing_message = await update.message.reply_text("⏳ جاري البحث عن إجابة...")
    await asyncio.sleep(1)
    data = load_data(QUESTIONS_FILE)
    if not data:
        await processing_message.edit_text("عذراً، قاعدة البيانات فارغة حالياً.")
        return
    best_match = process.extractOne(question, data.keys(), score_cutoff=90)
    if best_match:
        answer = data[best_match[0]]
        await processing_message.edit_text(answer)
    else:
        if update.effective_user.id == ADMIN_ID:
            not_found_message = "لم أجد سؤالاً مطابقاً بدقة. استخدم /admin لإضافة سؤال جديد."
        else:
            not_found_message = "عذراً، لم أجد إجابة دقيقة لهذا السؤال في قاعدة بياناتي."
        await processing_message.edit_text(not_found_message)


# --- لوحة تحكم الآدمن ---
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (الكود كما هو) ...
    keyboard = [
        [
            InlineKeyboardButton("➕ إضافة نصية", callback_data='admin_add_start'),
            InlineKeyboardButton("🖼️ إضافة من صورة", callback_data='admin_photo_start')
        ],
        [InlineKeyboardButton("📖 عرض كل الأسئلة", callback_data='admin_list_0')],
        [InlineKeyboardButton("🗑️ حذف سؤال", callback_data='admin_delete_start')],
        [InlineKeyboardButton("📊 عرض الإحصائيات", callback_data='admin_stats')],
        [InlineKeyboardButton("✖️ إغلاق", callback_data='admin_close')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "⚙️ **لوحة تحكم الآدمن** ⚙️\n\nاختر الإجراء المطلوب:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    return PANEL_ROUTES

# --- دوال الأزرار ---
async def close_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("تم إغلاق لوحة التحكم.")
    return ConversationHandler.END

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (الكود كما هو) ...
    query = update.callback_query
    await query.answer()
    questions = load_data(QUESTIONS_FILE)
    stats = load_data(STATS_FILE, default_data={"users": [], "last_added": "N/A"})
    stats_text = (
        f"📊 **إحصائيات البوت** 📊\n\n"
        f"🔸 **إجمالي الأسئلة:** {len(questions)}\n"
        f"👤 **إجمالي المستخدمين:** {len(stats['users'])}\n"
        f"📅 **آخر إضافة سؤال:** {stats['last_added']}"
    )
    keyboard = [[InlineKeyboardButton("🔙 رجوع للوحة التحكم", callback_data='admin_back_to_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
    return PANEL_ROUTES

# --- دوال ومحادثات الآدمن ---
@admin_only
async def list_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (الكود كما هو) ...
    query = update.callback_query
    page = int(query.data.split('_')[2])
    data = load_data(QUESTIONS_FILE)
    questions = list(data.items())
    if not questions:
        await query.edit_message_text("الأرشيف فارغ حالياً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_back_to_panel')]]))
        return PANEL_ROUTES
    start_index = page * QUESTIONS_PER_PAGE
    end_index = start_index + QUESTIONS_PER_PAGE
    paginated_questions = questions[start_index:end_index]
    message = "📖 **الأسئلة الموجودة (صفحة " + str(page + 1) + "):**\n\n"
    for i, (q, a) in enumerate(paginated_questions, start_index + 1):
        message += f"**{i}. س:** {q}\n**ج:** {a}\n---\n"
    keyboard = []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("◀️ السابق", callback_data=f'admin_list_{page - 1}'))
    if end_index < len(questions):
        row.append(InlineKeyboardButton("التالي ▶️", callback_data=f'admin_list_{page + 1}'))
    keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 رجوع للوحة التحكم", callback_data='admin_back_to_panel')])
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return PANEL_ROUTES

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (الكود كما هو) ...
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("حسناً، أرسل لي نص السؤال الجديد. لإلغاء العملية أرسل /cancel.")
    return ADD_QUESTION

async def add_get_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_question'] = update.message.text
    await update.message.reply_text("تمام. الآن أرسل لي الجواب الصحيح.")
    return ADD_ANSWER

async def add_get_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (الكود كما هو) ...
    question = context.user_data.get('new_question')
    if not question:
        await update.message.reply_text("حدث خطأ، لم يتم العثور على السؤال. تم إلغاء العملية.")
        return await admin_panel(update, context)
    answer = update.message.text
    questions_data = load_data(QUESTIONS_FILE)
    questions_data[question] = answer
    save_data(questions_data, QUESTIONS_FILE)
    stats_data = load_data(STATS_FILE, default_data={"users": [], "last_added": "N/A"})
    stats_data["last_added"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(stats_data, STATS_FILE)
    await update.message.reply_text(f"✅ تم حفظ السؤال بنجاح!")
    context.user_data.clear()
    return await admin_panel(update, context)


async def photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (الكود كما هو) ...
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("الآن، أرسل الصورة التي تريد استخلاص النص منها. لإلغاء العملية أرسل /cancel.")
    return PHOTO_RECEIVE

async def photo_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (الكود كما هو) ...
    photo_file = await update.message.photo[-1].get_file()
    photo_path = f'{photo_file.file_id}.jpg'
    await photo_file.download_to_drive(photo_path)
    await update.message.reply_text('تم استلام الصورة. جارٍ قراءة النص...')
    try:
        extracted_text = pytesseract.image_to_string(Image.open(photo_path), lang='ara+eng')
        if not extracted_text.strip():
            await update.message.reply_text('لم أتمكن من قراءة أي نص. حاول بصورة أوضح. تم إلغاء العملية.')
            return await admin_panel(update, context)
        await update.message.reply_text(f"النص المستخرج:\n---\n{extracted_text}\n---\n\nالآن، أرسل السؤال الصحيح.")
        return PHOTO_QUESTION
    except Exception as e:
        logging.error(f"OCR Error: {e}")
        await update.message.reply_text('حدث خطأ أثناء قراءة الصورة. تم إلغاء العملية.')
        return await admin_panel(update, context)
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)

async def photo_get_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_question'] = update.message.text
    await update.message.reply_text("تمام. الآن أرسل الجواب الصحيح.")
    return PHOTO_ANSWER

# --- ## تم تعديل وإصلاح نظام الحذف بالكامل هنا ## ---

@admin_only
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = load_data(QUESTIONS_FILE)
    questions = list(data.keys())
    
    if not questions:
        await query.edit_message_text("الأرشيف فارغ، لا يوجد ما يمكن حذفه.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_back_to_panel')]]))
        return PANEL_ROUTES
    
    # حفظ قائمة الأسئلة مؤقتاً للمستخدم
    context.user_data['questions_for_deletion'] = questions
    
    message = "الرجاء إرسال **رقم** السؤال الذي تريد حذفه من القائمة التالية. لإلغاء العملية أرسل /cancel.\n\n"
    for i, q in enumerate(questions, 1):
        message += f"**{i}.** {q}\n"
    
    await query.edit_message_text(message, parse_mode='Markdown')
    return DELETE_CHOICE

async def delete_get_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        choice = int(update.message.text)
        questions = context.user_data.get('questions_for_deletion')
        
        if not questions:
             await update.message.reply_text("حدث خطأ. الرجاء البدء من جديد عبر /admin.")
             return await admin_panel(update, context)

        if 1 <= choice <= len(questions):
            question_to_delete = questions[choice - 1]
            data = load_data(QUESTIONS_FILE)
            if question_to_delete in data:
                del data[question_to_delete]
                save_data(data, QUESTIONS_FILE)
                await update.message.reply_text(f"🗑️ تم حذف السؤال بنجاح: '{question_to_delete}'")
            else:
                await update.message.reply_text("عفواً، هذا السؤال تم حذفه بالفعل.")
        else:
            await update.message.reply_text("رقم غير صالح. الرجاء إرسال رقم من القائمة.")
            return DELETE_CHOICE # يبقى في نفس الحالة لانتظار رقم صحيح
            
    except (ValueError, IndexError):
        await update.message.reply_text("إدخال غير صالح. الرجاء إرسال رقم فقط.")
        return DELETE_CHOICE # يبقى في نفس الحالة
    
    context.user_data.clear()
    return await admin_panel(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data:
        context.user_data.clear()
    # نتحقق إذا كان الأمر من زر أو رسالة
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text('تم إلغاء العملية الحالية.')
    else:
        await update.message.reply_text('تم إلغاء العملية الحالية.')
        
    return await admin_panel(update, context)


# --- كتلة التنفيذ الرئيسية ---
def main():
    if not TOKEN:
        print("خطأ فادح: لم يتم العثور على توكن البوت.")
        return
    
    application = Application.builder().token(TOKEN).build()

    admin_handler = ConversationHandler(
        entry_points=[CommandHandler('admin', admin_panel)],
        states={
            PANEL_ROUTES: [
                CallbackQueryHandler(list_questions, pattern='^admin_list_'),
                CallbackQueryHandler(delete_start, pattern='^admin_delete_start$'),
                CallbackQueryHandler(add_start, pattern='^admin_add_start$'),
                CallbackQueryHandler(photo_start, pattern='^admin_photo_start$'),
                CallbackQueryHandler(show_stats, pattern='^admin_stats$'),
                CallbackQueryHandler(close_panel, pattern='^admin_close$'),
                CallbackQueryHandler(admin_panel, pattern='^admin_back_to_panel$'),
            ],
            # تم تغيير معالج الحذف ليكون نصياً
            DELETE_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_get_choice)],
            ADD_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_question)],
            ADD_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_answer)],
            PHOTO_RECEIVE: [MessageHandler(filters.PHOTO, photo_receive)],
            PHOTO_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, photo_get_question)],
            PHOTO_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_answer)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )

    application.add_handler(admin_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_regular_question))
    
    print("بوت بسام يعمل الآن بنظام الحذف المصحح...")
    application.run_polling()

if __name__ == '__main__':
    main()
