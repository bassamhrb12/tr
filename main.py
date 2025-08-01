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
import uuid
from thefuzz import process
import pytesseract
from PIL import Image

# --- الإعدادات ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ADMIN_ID = 720330522
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
QUESTIONS_FILE = 'questions.json'
QUESTIONS_PER_PAGE = 5

# تعريف حالات المحادثات
(ADD_QUESTION, ADD_ANSWER) = range(2)
(PHOTO_RECEIVE, PHOTO_QUESTION, PHOTO_ANSWER) = range(2, 5)
(DELETE_CHOICE) = range(5, 6)
(PANEL_ROUTES) = range(6, 7)

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
def load_data():
    try:
        if not os.path.exists(QUESTIONS_FILE):
            with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f)
        with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"Error loading data file: {e}")
        return {}

def save_data(data):
    try:
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving data file: {e}")

# --- أوامر المستخدمين ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "أهلاً بك! أنا بوت بسام لمساعدتك في حل أسئلة بارنز كافيه. أرسل لي أي سؤال."
        "\n\n---\n*إذا استفدت من البوت، فلا تنساني ووالديّ من صالح دعائك.*"
    )
    if update.effective_user.id == ADMIN_ID:
        welcome_message += "\n\nبصفتك الآدمن، استخدم /admin لعرض لوحة التحكم."
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def handle_regular_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text.strip()
    processing_message = await update.message.reply_text("⏳ جاري البحث عن إجابة...")
    await asyncio.sleep(1) # تأخير بسيط لمحاكاة البحث

    data = load_data()
    if not data:
        await processing_message.edit_text("عذراً، قاعدة البيانات فارغة حالياً.")
        return

    # تم رفع دقة البحث إلى 85 لتقليل الإجابات العشوائية
    best_match = process.extractOne(question, data.keys(), score_cutoff=85)
    
    if best_match:
        answer = data[best_match[0]]
        await processing_message.edit_text(answer)
    else:
        if update.effective_user.id == ADMIN_ID:
            not_found_message = "لم أجد سؤالاً مطابقاً بدقة. استخدم /admin لإضافة سؤال جديد."
        else:
            not_found_message = "عذراً، لم أجد إجابة دقيقة لهذا السؤال في قاعدة بياناتي."
        await processing_message.edit_text(not_found_message)

# --- لوحة تحكم الآدمن الاحترافية ---
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("➕ إضافة نصية", callback_data='admin_add_start'),
            InlineKeyboardButton("🖼️ إضافة من صورة", callback_data='admin_photo_start')
        ],
        [InlineKeyboardButton("📖 عرض كل الأسئلة", callback_data='admin_list_0')],
        [InlineKeyboardButton("🗑️ حذف سؤال", callback_data='admin_delete_start')],
        [InlineKeyboardButton("✖️ إغلاق", callback_data='admin_close')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text("⚙️ **لوحة تحكم الآدمن** ⚙️\n\nاختر الإجراء المطلوب:", reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text("⚙️ **لوحة تحكم الآدمن** ⚙️\n\nاختر الإجراء المطلوب:", reply_markup=reply_markup, parse_mode='Markdown')
    return PANEL_ROUTES

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    # تفكيك بيانات الزر لتحديد الإجراء والبيانات الإضافية
    parts = query.data.split('_')
    command = parts[0]
    action = parts[1] if len(parts) > 1 else None
    value = parts[2] if len(parts) > 2 else None

    if command == 'admin':
        if action == 'close':
            await query.edit_message_text("تم إغلاق لوحة التحكم.")
            return ConversationHandler.END
        elif action == 'list':
            await list_questions(update, context, page=int(value))
            return PANEL_ROUTES
        elif action == 'delete' and value == 'confirm':
             return await delete_get_choice(update, context) # Transition to delete confirmation
        # باقي الأوامر يتم معالجتها كـ Entry Points في المحادثات
    return PANEL_ROUTES

# --- عرض الأسئلة بنظام الصفحات ---
@admin_only
async def list_questions(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    data = load_data()
    questions = list(data.items())
    if not questions:
        await query.edit_message_text("الأرشيف فارغ حالياً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_back_to_panel')]]))
        return
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

# --- باقي دوال ومحادثات الآدمن ---

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("حسناً، أرسل لي نص السؤال الجديد. لإلغاء العملية أرسل /cancel.")
    return ADD_QUESTION

async def add_get_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_question'] = update.message.text
    await update.message.reply_text("تمام. الآن أرسل لي الجواب الصحيح.")
    return ADD_ANSWER

async def add_get_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    question = context.user_data.get('new_question')
    if not question:
        await update.message.reply_text("حدث خطأ، لم يتم العثور على السؤال. تم إلغاء العملية.")
        await admin_panel(update, context)
        return ConversationHandler.END
    answer = update.message.text
    data = load_data()
    data[question] = answer
    save_data(data)
    await update.message.reply_text(f"✅ تم حفظ السؤال بنجاح!")
    context.user_data.clear()
    await admin_panel(update, context) # العودة للوحة التحكم
    return ConversationHandler.END

async def photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("الآن، أرسل الصورة التي تريد استخلاص النص منها. لإلغاء العملية أرسل /cancel.")
    return PHOTO_RECEIVE

async def photo_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = await update.message.photo[-1].get_file()
    photo_path = f'{photo_file.file_id}.jpg'
    await photo_file.download_to_drive(photo_path)
    await update.message.reply_text('تم استلام الصورة. جارٍ قراءة النص...')
    try:
        extracted_text = pytesseract.image_to_string(Image.open(photo_path), lang='ara+eng')
        if not extracted_text.strip():
            await update.message.reply_text('لم أتمكن من قراءة أي نص. حاول بصورة أوضح. تم إلغاء العملية.')
            await admin_panel(update, context)
            return ConversationHandler.END
        await update.message.reply_text(f"النص المستخرج:\n---\n{extracted_text}\n---\n\nالآن، أرسل السؤال الصحيح.")
        return PHOTO_QUESTION
    except Exception as e:
        logging.error(f"OCR Error: {e}")
        await update.message.reply_text('حدث خطأ أثناء قراءة الصورة. تم إلغاء العملية.')
        return ConversationHandler.END
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)

async def photo_get_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_question'] = update.message.text
    await update.message.reply_text("تمام. الآن أرسل الجواب الصحيح.")
    return PHOTO_ANSWER

async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = load_data()
    if not data:
        await query.edit_message_text("الأرشيف فارغ، لا يوجد ما يمكن حذفه.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_back_to_panel')]]))
        return ConversationHandler.END
    
    keyboard = []
    for q in data.keys():
        callback_data_q = (q[:50] + '..') if len(q) > 52 else q
        keyboard.append([InlineKeyboardButton(q, callback_data=f"admin_delete_confirm_{callback_data_q}")])
    keyboard.append([InlineKeyboardButton("🔙 إلغاء والرجوع", callback_data='admin_back_to_panel')])
    
    await query.edit_message_text("اختر السؤال الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DELETE_CHOICE

async def delete_get_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    question_to_delete_prefix = query.data.replace('admin_delete_confirm_', '')

    data = load_data()
    full_question_key = ""
    for q_key in data.keys():
        if q_key.startswith(question_to_delete_prefix):
            full_question_key = q_key
            break
            
    if full_question_key and full_question_key in data:
        del data[full_question_key]
        save_data(data)
        await query.edit_message_text(f"🗑️ تم حذف السؤال بنجاح!")
    else:
        await query.edit_message_text(f"حدث خطأ، لم يتم العثور على السؤال للحذف.")

    await asyncio.sleep(2)
    await admin_panel(update, context)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data:
        context.user_data.clear()
    await update.message.reply_text('تم إلغاء العملية الحالية.')
    await admin_panel(update, context)
    return ConversationHandler.END

# --- كتلة التنفيذ الرئيسية ---
def main():
    if not TOKEN:
        print("خطأ فادح: لم يتم العثور على توكن البوت.")
        return
    
    application = Application.builder().token(TOKEN).build()

    # محادثة الآدمن الرئيسية
    admin_handler = ConversationHandler(
        entry_points=[CommandHandler('admin', admin_panel)],
        states={
            PANEL_ROUTES: [
                CallbackQueryHandler(list_questions, pattern='^admin_list_'),
                CallbackQueryHandler(delete_start, pattern='^admin_delete_start$'),
                CallbackQueryHandler(add_start, pattern='^admin_add_start$'),
                CallbackQueryHandler(photo_start, pattern='^admin_photo_start$'),
                CallbackQueryHandler(close_panel, pattern='^admin_close$'),
                CallbackQueryHandler(admin_panel, pattern='^admin_back_to_panel$'),
            ],
            DELETE_CHOICE: [CallbackQueryHandler(delete_get_choice, pattern='^admin_delete_confirm_')],
            ADD_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_question)],
            ADD_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_answer)],
            PHOTO_RECEIVE: [MessageHandler(filters.PHOTO, photo_receive)],
            PHOTO_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, photo_get_question)],
            PHOTO_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_answer)],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('admin', admin_panel)],
    )

    application.add_handler(admin_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_regular_question))
    
    print("بوت بسام يعمل الآن بالنسخة المحسنة والأكثر استقراراً...")
    application.run_polling()

if __name__ == '__main__':
    main()
