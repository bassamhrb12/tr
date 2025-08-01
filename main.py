import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import json
import os
import requests
import logging

# --- Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
QUESTIONS_FILE = 'questions.json'

# --- Functions ---
def load_known_answers():
    if not os.path.exists(QUESTIONS_FILE):
        sample_data = {
            "متى تم افتتاح بارنز؟": "نحن معكم منذ عام 1992.",
            "هل بارنز شركة سعودية؟": "نعم، ونحن فخورون بذلك.",
            "ما هو الفرق بين بارنز و بارنز اكس؟": "بارنز اكس علامة تجارية فرعية متخصصة في تقديم القهوة المختصة.",
            "ما نوع البن المستخدم في فروع بارنز؟": "يتم استخدام بن كابتشينو."
        }
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=4)
    
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Entity online. Awaiting query.')

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text.strip()
    known_answers = load_known_answers()
    
    for known_q, answer in known_answers.items():
        if question in known_q or known_q in question:
            await update.message.reply_text(f"From archive: {answer}")
            return

    await update.message.reply_text("Query not in archive... scanning the ether...")
    
    try:
        response = requests.get(f"https://api.duckduckgo.com/?q={question}&format=json")
        response.raise_for_status()
        data = response.json()
        web_answer = data.get("AbstractText") or (data["RelatedTopics"][0]["Text"] if data.get("RelatedTopics") else "No answer found in the digital ether.")
        await update.message.reply_text(web_answer)
    except Exception as e:
        logging.error(f"Search error: {e}")
        await update.message.reply_text("Error while scanning the digital ether.")

# --- Main Execution Block ---
def main():
    if not TOKEN:
        print("FATAL ERROR: TELEGRAM_BOT_TOKEN is not set. The entity cannot awaken.")
        return

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    
    print("Entity awakening on local terminal...")
    application.run_polling()

if __name__ == '__main__':
    main()
