import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler, # تمت إضافة هذا للأزرار
)
import json
import os
import logging
from functools import wraps
import asyncio
from thefuzz import process # تمت إضافة هذا للبحث الذكي

# --- الإعدادات ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ADMIN_ID = 720330522 
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
QUESTIONS_FILE = 'questions.json'
QUESTIONS_PER_PAGE = 5 # عدد الأسئلة في كل صفحة

# تعريف حالات المحادثات
(ADD_QUESTION, ADD_ANSWER) = range(2)
(DELETE_CHOICE) = range(2, 3)

# --- Decorator للتحقق من الآدمن ---
def admin_only(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            # إذا كان مصدر الطلب زر، نجاوب على الزر
            if update.callback_query:
                await update.callback_query.answer("هذا الأمر للآدمن فقط.", show_alert=True)
            else:
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
    await asyncio.sleep(1)

    data = load_data()
    if not data:
        await processing_message.edit_text("عذراً، قاعدة البيانات فارغة حالياً.")
        return

    # البحث الذكي باستخدام thefuzz
    # نستخرج أفضل نتيجة مطابقة للسؤال
    best_match = process.extractOne(question, data.keys(), score_cutoff=75) # نسبة التشابه 75% أو أكثر

    if best_match:
        # best_match[0] هو السؤال المطابق
        answer = data[best_match[0]]
        await processing_message.edit_text(answer)
    else:
        # إذا لم نجد نتيجة جيدة
        if update.effective_user.id == ADMIN_ID:
            not_found_message = "لم أجد سؤالاً مطابقاً. استخدم لوحة التحكم /admin لإضافة سؤال جديد."
        else:
            not_found_message = "عذراً، لم أجد إجابة لهذا السؤال في قاعدة بياناتي الحالية."
        await processing_message.edit_text(not_found_message)

# --- لوحة تحكم الآدمن الاحترافية ---

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ إضافة سؤال جديد", callback_data='admin_add')],
        [InlineKeyboardButton("📖 عرض كل الأسئلة", callback_data='admin_list_0')], # نبدأ من الصفحة 0
        [InlineKeyboardButton("🗑️ حذف سؤال", callback_data='admin_delete_start')],
        [InlineKeyboardButton("✖️ إغلاق", callback_data='admin_close')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚙️ **لوحة تحكم الآدمن** ⚙️\n\nاختر الإجراء المطلوب:", reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # مهم جداً لإعلام تيليجرام باستلام الضغطة
    
    command = query.data.split('_')
    action = command[1]

    if action == 'close':
        await query.edit_message_text("تم إغلاق لوحة التحكم.")
        return

    if action == 'add':
        await query.message.reply_text("حسناً، أرسل لي نص السؤال الجديد الذي تريد إضافته. (استخدم /cancel للإلغاء)")
        return ADD_QUESTION

    if action == 'list':
        page = int(command[2])
        await list_questions(update, context, page=page)
    
    if action == 'delete':
        if command[2] == 'start':
            await delete_start(update, context)
        else:
            await delete_get_choice(update, context, question_to_delete=command[2])


# --- عرض الأسئلة بنظام الصفحات ---
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

# --- محادثات الآدمن (إضافة وحذف) ---
# ... (سيتم تعديلها لتعمل مع الأزرار) ...
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
    await admin_panel(update, context) # العودة للوحة التحكم
    context.user_data.clear()
    return ConversationHandler.END

async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (هذه الدالة ستعرض قائمة للحذف) ...
    pass

async def delete_get_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, question_to_delete: str):
    # ... (هذه الدالة ستقوم بالحذف) ...
    pass

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

    # محادثة الإضافة
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u,c: add_start(u,c), pattern='^admin_add$')],
        states={
            ADD_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_question)],
            ADD_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_answer)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        map_to_parent={ConversationHandler.END: 1} # للعودة للوحة التحكم
    )

    # لوحة التحكم الرئيسية
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler('admin', admin_panel)],
        states={
            1: [add_conv, CallbackQueryHandler(button_handler)],
        },
        fallbacks=[CommandHandler('admin', admin_panel)],
    )

    application.add_handler(admin_conv)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_regular_question))
    
    print("بوت بسام يعمل الآن بالحزمة الاحترافية الكاملة...")
    application.run_polling()

if __name__ == '__main__':
    main()
