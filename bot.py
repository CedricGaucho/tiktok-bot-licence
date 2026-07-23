from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
SERVER_URL = "https://cgaucho.pythonanywhere.com"

# Clavier personnalisé qui s'affiche par défaut
main_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📊 Voir mon abonnement")],
        [KeyboardButton("🔄 Renouveler l'abonnement"), KeyboardButton("⏳ Prolonger (admin)")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bienvenue sur le bot de gestion d'abonnements !\n"
        "Utilisez les boutons ci-dessous pour interagir.",
        reply_markup=main_keyboard
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "📊 Voir mon abonnement":
        resp = requests.get(f"{SERVER_URL}/get_subscription?telegram_id={user_id}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'active':
                await update.message.reply_text(
                    f"✅ Abonnement actif.\nJours restants : {data['days_left']}\nExpire le : {data['expires_at']}",
                    reply_markup=main_keyboard
                )
            else:
                await update.message.reply_text("❌ Abonnement expiré.", reply_markup=main_keyboard)
        elif resp.status_code == 404:
            await update.message.reply_text("❌ Aucun abonnement trouvé pour votre compte.", reply_markup=main_keyboard)
        else:
            await update.message.reply_text("❌ Erreur lors de la vérification.", reply_markup=main_keyboard)

    elif text == "🔄 Renouveler l'abonnement":
        # Ici vous pouvez intégrer un paiement ou demander une confirmation.
        # Pour l'instant, on informe que c'est payant.
        await update.message.reply_text(
            "💳 Pour renouveler, veuillez effectuer un paiement de X €.\n"
            "Après validation, votre abonnement sera prolongé automatiquement.\n"
            "Contactez l'admin pour plus d'informations.",
            reply_markup=main_keyboard
        )

    elif text == "⏳ Prolonger (admin)":
        if user_id != ADMIN_ID:
            await update.message.reply_text("⛔ Cette commande est réservée à l'administrateur.", reply_markup=main_keyboard)
            return
        # On demande les paramètres : ID du destinataire et nombre de jours
        await update.message.reply_text(
            "✏️ Envoyez le message au format :\n`/renew <telegram_id> <jours>`\nExemple : `/renew 123456789 7`",
            parse_mode='Markdown',
            reply_markup=main_keyboard
        )

async def renew_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Commande réservée à l'administrateur.", reply_markup=main_keyboard)
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("❌ Format : /renew <telegram_id> <jours>", reply_markup=main_keyboard)
        return

    try:
        target_id = int(args[0])
        days = int(args[1])
        if days <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Paramètres invalides.", reply_markup=main_keyboard)
        return

    payload = {"admin_token": ADMIN_TOKEN, "telegram_id": target_id, "days": days}
    resp = requests.post(f"{SERVER_URL}/renew_subscription", json=payload)
    if resp.status_code == 200:
        await update.message.reply_text(f"✅ Abonnement prolongé de {days} jours pour l'ID {target_id}.", reply_markup=main_keyboard)
    else:
        await update.message.reply_text("❌ Erreur lors du renouvellement.", reply_markup=main_keyboard)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("renew", renew_command))  # toujours disponible en commande
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))  # gestion des boutons

    print("Bot démarré...")
    app.run_polling()

if __name__ == "__main__":
    main()