import os
import requests
import hashlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

# Variables d'environnement
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
SERVER_URL = "https://cgaucho.pythonanywhere.com"

# États de la conversation
(
    UNIQUE_ID_NAME,
    UNIQUE_ID_API_ID,
    UNIQUE_ID_API_HASH,
    UNIQUE_ID_DAYS,
    RENEW_ID,
    RENEW_DAYS,
    DETAIL_ID,
) = range(7)

# ... le reste du code

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu principal avec boutons"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Accès réservé à l'administrateur.")
        return

    keyboard = [
        [InlineKeyboardButton("📋 Créer un ID unique", callback_data="create")],
        [InlineKeyboardButton("🔄 Renouveler un abonnement", callback_data="renew")],
        [InlineKeyboardButton("👥 Liste des utilisateurs", callback_data="list")],
        [InlineKeyboardButton("🔍 Détails d'un utilisateur", callback_data="detail")],
        [InlineKeyboardButton("📊 Statistiques", callback_data="stats")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Admin Dashboard\nChoisissez une action :", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les clics sur les boutons"""
    query = update.callback_query
    await query.answer()

    if query.data == "create":
        await query.edit_message_text("Entrez le nom Telegram de l'utilisateur (ex: @jean) :")
        context.user_data['action'] = 'create'
        return UNIQUE_ID_NAME

    elif query.data == "renew":
        await query.edit_message_text("Entrez l'ID unique ou l'ID Telegram de l'utilisateur :")
        context.user_data['action'] = 'renew'
        return RENEW_ID

    elif query.data == "list":
        await query.edit_message_text("Liste des utilisateurs en cours de chargement...")
        # Appel API pour récupérer la liste
        resp = requests.get(f"{SERVER_URL}/list_users?admin_token={ADMIN_TOKEN}")
        if resp.status_code == 200:
            data = resp.json()
            if data:
                text = "📋 *Liste des utilisateurs :*\n\n"
                for user in data:
                    status = "✅ Actif" if user['expires_at'] > int(time.time()) else "❌ Expiré"
                    text += f"▪️ *{user['unique_id']}* ({user['telegram_id']})\n"
                    text += f"   Expire: {user['expires_at']} | {status}\n\n"
                # Tronquer si trop long
                if len(text) > 4000:
                    text = text[:4000] + "..."
                await query.edit_message_text(text, parse_mode='Markdown')
            else:
                await query.edit_message_text("Aucun utilisateur enregistré.")
        else:
            await query.edit_message_text("❌ Erreur lors de la récupération de la liste.")
        return ConversationHandler.END

    elif query.data == "detail":
        await query.edit_message_text("Entrez l'ID unique ou l'ID Telegram de l'utilisateur :")
        context.user_data['action'] = 'detail'
        return RENEW_ID  # on réutilise l'état

    elif query.data == "stats":
        # Statistiques rapides
        resp = requests.get(f"{SERVER_URL}/stats?admin_token={ADMIN_TOKEN}")
        if resp.status_code == 200:
            data = resp.json()
            text = f"📊 *Statistiques*\n\n"
            text += f"Total utilisateurs : {data.get('total', 0)}\n"
            text += f"Actifs : {data.get('active', 0)}\n"
            text += f"Expirés : {data.get('expired', 0)}"
            await query.edit_message_text(text, parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ Erreur lors des statistiques.")
        return ConversationHandler.END

async def create_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text.strip()
    await update.message.reply_text("Entrez l'API ID de l'utilisateur :")
    return UNIQUE_ID_API_ID

async def create_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['api_id'] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ L'API ID doit être un nombre. Réessayez :")
        return UNIQUE_ID_API_ID
    await update.message.reply_text("Entrez l'API Hash de l'utilisateur :")
    return UNIQUE_ID_API_HASH

async def create_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['api_hash'] = update.message.text.strip()
    await update.message.reply_text("Entrez le nombre de jours d'abonnement (ex: 30) :")
    return UNIQUE_ID_EXPIRY

async def create_expiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Entrez un nombre de jours valide (ex: 30) :")
        return UNIQUE_ID_EXPIRY

    name = context.user_data['name']
    api_id = context.user_data['api_id']
    api_hash = context.user_data['api_hash']

    # Générer l'ID unique (hash SHA256 des 3 éléments)
    raw = f"{name}{api_id}{api_hash}"
    unique_id = hashlib.sha256(raw.encode()).hexdigest()[:16]  # on prend les 16 premiers caractères

    # Appel API pour créer l'utilisateur
    payload = {
        "admin_token": ADMIN_TOKEN,
        "unique_id": unique_id,
        "telegram_id": None,  # on ne connaît pas encore le telegram_id, on peut le laisser nul
        "days": days,
        "name": name,
        "api_id": api_id,
        "api_hash": api_hash,
    }
    resp = requests.post(f"{SERVER_URL}/create_user", json=payload)
    if resp.status_code == 200:
        await update.message.reply_text(f"✅ Utilisateur créé avec succès !\nID unique : `{unique_id}`\nExpire dans {days} jours.", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Erreur lors de la création de l'utilisateur.")
    return ConversationHandler.END

async def renew_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['identifier'] = update.message.text.strip()
    await update.message.reply_text("Entrez le nombre de jours à ajouter :")
    return RENEW_DAYS

async def renew_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Entrez un nombre de jours valide :")
        return RENEW_DAYS

    identifier = context.user_data['identifier']
    payload = {
        "admin_token": ADMIN_TOKEN,
        "identifier": identifier,
        "days": days
    }
    resp = requests.post(f"{SERVER_URL}/renew_user", json=payload)
    if resp.status_code == 200:
        data = resp.json()
        await update.message.reply_text(f"✅ Abonnement prolongé de {days} jours.\nNouvelle expiration : {data['new_expires_at']}")
    elif resp.status_code == 404:
        await update.message.reply_text("❌ Utilisateur non trouvé.")
    else:
        await update.message.reply_text("❌ Erreur lors du renouvellement.")
    return ConversationHandler.END

async def detail_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identifier = update.message.text.strip()
    resp = requests.get(f"{SERVER_URL}/user_detail?admin_token={ADMIN_TOKEN}&identifier={identifier}")
    if resp.status_code == 200:
        data = resp.json()
        text = f"📋 *Détails de l'utilisateur*\n\n"
        text += f"▪️ ID unique : `{data.get('unique_id')}`\n"
        text += f"▪️ Telegram ID : {data.get('telegram_id') or 'Non renseigné'}\n"
        text += f"▪️ Nom : {data.get('name') or 'N/A'}\n"
        text += f"▪️ API ID : {data.get('api_id') or 'N/A'}\n"
        text += f"▪️ Expire le : {data.get('expires_at')}\n"
        text += f"▪️ Statut : {'✅ Actif' if data.get('active') else '❌ Expiré'}\n"
        text += f"▪️ Fingerprint actif : {data.get('active_fingerprint') or 'Aucun'}"
        await update.message.reply_text(text, parse_mode='Markdown')
    elif resp.status_code == 404:
        await update.message.reply_text("❌ Utilisateur non trouvé.")
    else:
        await update.message.reply_text("❌ Erreur lors de la récupération des détails.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Opération annulée.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler pour 'create'
    create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^create$")],
        states={
            UNIQUE_ID_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_name)],
            UNIQUE_ID_API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_api_id)],
            UNIQUE_ID_API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_api_hash)],
            UNIQUE_ID_EXPIRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_expiry)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Conversation handler pour 'renew'
    renew_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^renew$")],
        states={
            RENEW_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, renew_id)],
            RENEW_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, renew_days)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Conversation handler pour 'detail'
    detail_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^detail$")],
        states={
            RENEW_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, detail_result)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^list$"))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^stats$"))
    app.add_handler(create_conv)
    app.add_handler(renew_conv)
    app.add_handler(detail_conv)

    print("Bot admin démarré...")
    app.run_polling()

if __name__ == "__main__":
    import time
    main()