import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import json
import os
import requests
import logging

# --- الإعدادات ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
QUESTIONS_FILE = 'questions.json'

# --- الوظائف ---
def load_known_answers():
    """تحميل الأجوبة من الأرشيف عند بدء التشغيل"""
    if not os.path.exists(QUESTIONS_FILE):
        sample_data = {
            "متى تم افتتاح بارنز؟": "نحن معكم منذ عام 1992.",
            "هل بارنز شركة سعودية؟": "نعم، ونحن فخورون بذلك."
        }
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=4)
    
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الاستجابة لأمر البدء"""
    # تم تغيير الرسالة الترحيبية هنا
    welcome_message = "أهلاً بك! أنا بوت بسام لمساعدتك في حل أسئلة بارنز كافيه. أرسل لي أي سؤال."
    await update.message.reply_text(welcome_message)

def search_web_for_answer(question):
    """البحث الذكي عن إجابة عبر الإنترنت"""
    search_queries = [
        f"إجابة سؤال {question} في مسابقة بارنز",
        f"سؤال وجواب بارنز: {question}",
        f"site:twitter.com مسابقة بارنز {question}"
    ]
    
    for query in search_queries:
        try:
            response = requests.get(f"https://api.duckduckgo.com/?q={query}&format=json")
            response.raise_for_status()
            data = response.json()
            
            answer = data.get("AbstractText") or \
                     (data["RelatedTopics"][0]["Text"] if data.get("RelatedTopics") and data["RelatedTopics"][0].get("Text") else None) or \
                     data.get("Answer")

            if answer and "لم يتم العثور" not in str(answer):
                return f"إجابة محتملة من البحث: {answer}"
        except Exception as e:
            logging.error(f"خطأ في البحث عن '{query}': {e}")
            continue

    return "لم أتمكن من العثور على إجابة واضحة بعد البحث في عدة مصادر."

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأسئلة الواردة"""
    question = update.message.text.strip()
    known_answers = load_known_answers()
    
    for known_q, answer in known_answers.items():
        if question in known_q or known_q in question:
            await update.message.reply_text(f"من الأرشيف: {answer}")
            return

    await update.message.reply_text("السؤال غير موجود في أرشيفي... سأبحث لك الآن...")
    web_answer = search_web_for_answer(question)
    await update.message.reply_text(web_answer)

# --- كتلة التنفيذ الرئيسية ---
def main():
    if not TOKEN:
        print("خطأ فادح: لم يتم العثور على توكن البوت.")
        return

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    
    # تم تغيير رسالة التشغيل هنا
    print("بوت بسام يعمل الآن...")
    application.run_polling()

if __name__ == '__main__':
    main()
