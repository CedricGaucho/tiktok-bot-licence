import requests
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Récupération des tokens depuis les variables d'environnement (plus sécurisé)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))  # Votre ID Telegram
SERVER_URL = "https://cgaucho.pythonanywhere.com"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bienvenue !\n"
        "/status - Voir votre abonnement\n"
        "/renew <telegram_id> <jours> - (Admin) Prolonger un abonnement"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    resp = requests.get(f"{SERVER_URL}/get_subscription?telegram_id={user_id}")
    if resp.status_code == 200:
        data = resp.json()
        if data.get('status') == 'active':
            await update.message.reply_text(f"✅ Abonnement actif. Jours restants : {data['days_left']}")
        else:
            await update.message.reply_text("❌ Abonnement expiré.")
    elif resp.status_code == 404:
        await update.message.reply_text("❌ Aucun abonnement trouvé pour votre compte.")
    else:
        await update.message.reply_text("❌ Erreur lors de la vérification.")

async def renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Commande réservée à l'administrateur.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Utilisation : /renew <telegram_id> <jours>")
        return

    try:
        telegram_id = int(args[0])
        days = int(args[1])
        if days <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Paramètres invalides.")
        return

    payload = {
        "admin_token": ADMIN_TOKEN,
        "telegram_id": telegram_id,
        "days": days
    }
    resp = requests.post(f"{SERVER_URL}/renew_subscription", json=payload)
    if resp.status_code == 200:
        await update.message.reply_text(f"✅ Abonnement prolongé de {days} jours.")
    else:
        await update.message.reply_text("❌ Erreur lors du renouvellement.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("renew", renew))
    print("Bot démarré...")
    app.run_polling()

if __name__ == "__main__":
    main()