import requests
import os
import json
import hashlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Récupération des variables d'environnement
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
SERVER_URL = "https://cgaucho.pythonanywhere.com"

# Fonction pour générer un unique_id à partir de api_id, api_hash et nom_telegram
def generate_unique_id(api_id, api_hash, telegram_name):
    data = f"{api_id}|{api_hash}|{telegram_name}"
    return hashlib.sha256(data.encode()).hexdigest()

# Menu principal
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Voir mon abonnement", callback_data="status")],
        [InlineKeyboardButton("🔄 Renouveler mon abonnement", callback_data="renew")],
        [InlineKeyboardButton("⏳ Prolonger un abonnement (admin)", callback_data="admin_renew")],
        [InlineKeyboardButton("🆕 Créer un ID unique", callback_data="create_id")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Bienvenue ! Choisissez une option :",
        reply_markup=reply_markup
    )

# Gestionnaire de callback pour les boutons
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data

    if data == "status":
        # Voir abonnement
        resp = requests.get(f"{SERVER_URL}/get_subscription?telegram_id={user_id}")
        if resp.status_code == 200:
            data_resp = resp.json()
            if data_resp.get('status') == 'active':
                await query.edit_message_text(f"✅ Abonnement actif. Jours restants : {data_resp['days_left']}")
            else:
                await query.edit_message_text("❌ Abonnement expiré.")
        elif resp.status_code == 404:
            await query.edit_message_text("❌ Aucun abonnement trouvé pour votre compte.")
        else:
            await query.edit_message_text("❌ Erreur lors de la vérification.")

    elif data == "renew":
        # Renouveler son propre abonnement (ex: ajouter 7 jours par défaut, ou demander un nombre)
        # Ici on va demander combien de jours via une question
        context.user_data['renew_action'] = 'ask_days'
        await query.edit_message_text("Combien de jours souhaitez-vous ajouter ? (entrez un nombre)")

    elif data == "admin_renew":
        # Réservé à l'admin : prolonger un autre utilisateur
        if user_id != ADMIN_ID:
            await query.edit_message_text("⛔ Cette commande est réservée à l'administrateur.")
            return
        # On demande l'ID et les jours
        context.user_data['admin_renew_action'] = 'ask_telegram_id'
        await query.edit_message_text("Entrez l'ID Telegram de l'utilisateur à prolonger :")

    elif data == "create_id":
        # Générer un ID unique à partir de api_id, api_hash, nom Telegram
        context.user_data['create_id_action'] = 'ask_api_id'
        await query.edit_message_text("Entrez votre API ID :")

# Gestion des messages texte (pour les réponses aux questions)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if 'renew_action' in context.user_data:
        if context.user_data['renew_action'] == 'ask_days':
            try:
                days = int(text)
                if days <= 0:
                    raise ValueError
                # Appel à l'API pour prolonger l'abonnement de l'utilisateur courant
                payload = {
                    "admin_token": ADMIN_TOKEN,
                    "telegram_id": user_id,
                    "days": days
                }
                resp = requests.post(f"{SERVER_URL}/renew_subscription", json=payload)
                if resp.status_code == 200:
                    await update.message.reply_text(f"✅ Abonnement prolongé de {days} jours.")
                else:
                    await update.message.reply_text("❌ Erreur lors du renouvellement.")
                context.user_data.pop('renew_action', None)
            except ValueError:
                await update.message.reply_text("❌ Veuillez entrer un nombre valide.")
        return

    if 'admin_renew_action' in context.user_data:
        if context.user_data['admin_renew_action'] == 'ask_telegram_id':
            try:
                target_id = int(text)
                context.user_data['admin_renew_target'] = target_id
                context.user_data['admin_renew_action'] = 'ask_days_admin'
                await update.message.reply_text("Combien de jours à ajouter ?")
            except ValueError:
                await update.message.reply_text("❌ ID invalide, veuillez entrer un nombre.")
        elif context.user_data['admin_renew_action'] == 'ask_days_admin':
            try:
                days = int(text)
                if days <= 0:
                    raise ValueError
                target_id = context.user_data['admin_renew_target']
                payload = {
                    "admin_token": ADMIN_TOKEN,
                    "telegram_id": target_id,
                    "days": days
                }
                resp = requests.post(f"{SERVER_URL}/renew_subscription", json=payload)
                if resp.status_code == 200:
                    await update.message.reply_text(f"✅ Abonnement de l'utilisateur {target_id} prolongé de {days} jours.")
                else:
                    await update.message.reply_text("❌ Erreur lors du renouvellement.")
                context.user_data.pop('admin_renew_action', None)
                context.user_data.pop('admin_renew_target', None)
            except ValueError:
                await update.message.reply_text("❌ Veuillez entrer un nombre valide.")
        return

    if 'create_id_action' in context.user_data:
        if context.user_data['create_id_action'] == 'ask_api_id':
            try:
                api_id = int(text)
                context.user_data['create_api_id'] = api_id
                context.user_data['create_id_action'] = 'ask_api_hash'
                await update.message.reply_text("Entrez votre API HASH :")
            except ValueError:
                await update.message.reply_text("❌ API ID doit être un nombre.")
        elif context.user_data['create_id_action'] == 'ask_api_hash':
            api_hash = text.strip()
            context.user_data['create_api_hash'] = api_hash
            context.user_data['create_id_action'] = 'ask_telegram_name'
            await update.message.reply_text("Entrez votre nom Telegram (sans @) :")
        elif context.user_data['create_id_action'] == 'ask_telegram_name':
            name = text.strip()
            api_id = context.user_data['create_api_id']
            api_hash = context.user_data['create_api_hash']
            # Générer l'ID unique
            unique_id = generate_unique_id(api_id, api_hash, name)
            # Ici, on peut l'enregistrer dans la base de données ? Pas directement, on va plutôt le renvoyer à l'utilisateur.
            await update.message.reply_text(f"✅ Votre ID unique est : `{unique_id}`\nGardez-le précieusement !")
            # On peut aussi afficher un message pour le copier.
            context.user_data.pop('create_id_action', None)
            context.user_data.pop('create_api_id', None)
            context.user_data.pop('create_api_hash', None)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CommandHandler("status", button_callback))  # au cas où
    app.add_handler(CommandHandler("renew", button_callback))
    app.add_handler(CommandHandler("admin_renew", button_callback))
    app.add_handler(CommandHandler("create_id", button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot démarré...")
    app.run_polling()

if __name__ == "__main__":
    from telegram.ext import MessageHandler, filters
    main()