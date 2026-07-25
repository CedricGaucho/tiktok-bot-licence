import os
import requests
import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

# === CONFIGURATION ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
SERVER_URL = "https://cgaucho.pythonanywhere.com"

# États de la conversation
(
    CREATE_NAME,
    CREATE_API_ID,
    CREATE_API_HASH,
    CREATE_UNIQUE_ID,
    CREATE_DAYS,
    RENEW_ID,
    RENEW_DAYS,
    DETAIL_ID,
) = range(8)

# === COMMANDE /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Accès réservé à l'administrateur.")
        return

    keyboard = [
        ["➕ Créer un ID unique"],
        ["🔄 Renouveler un abonnement"],
        ["📋 Liste des utilisateurs"],
        ["🔍 Détails d'un utilisateur"],
        ["📊 Statistiques"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 **Dashboard Admin**\nChoisissez une action :",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# === GESTION DES MENUS (boutons) ===
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "➕ Créer un ID unique":
        await update.message.reply_text("Entrez le **nom** de l'utilisateur (sans espaces) :")
        return CREATE_NAME
    elif text == "🔄 Renouveler un abonnement":
        await update.message.reply_text("Entrez l'**ID unique** ou l'**ID Telegram** :")
        return RENEW_ID
    elif text == "📋 Liste des utilisateurs":
        await list_users(update)
        return ConversationHandler.END
    elif text == "🔍 Détails d'un utilisateur":
        await update.message.reply_text("Entrez l'**ID unique** ou l'**ID Telegram** :")
        return DETAIL_ID
    elif text == "📊 Statistiques":
        await stats(update)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Commande inconnue.")
        return ConversationHandler.END

# === ÉTAPE : Nom ===
async def create_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if " " in name:
        await update.message.reply_text("❌ Le nom ne doit pas contenir d'espaces.")
        return CREATE_NAME
    context.user_data['name'] = name
    await update.message.reply_text("Entrez l'**API ID** (6 chiffres) :")
    return CREATE_API_ID

# === ÉTAPE : API ID ===
async def create_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or len(text) != 6:
        await update.message.reply_text("❌ L'API ID doit être un nombre de 6 chiffres.")
        return CREATE_API_ID
    context.user_data['api_id'] = int(text)
    await update.message.reply_text("Entrez l'**API Hash** (32 caractères alphanumériques) :")
    return CREATE_API_HASH

# === ÉTAPE : API Hash ===
async def create_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) != 32 or not text.isalnum():
        await update.message.reply_text("❌ L'API Hash doit faire 32 caractères alphanumériques.")
        return CREATE_API_HASH
    context.user_data['api_hash'] = text

    # Génération automatique de l'ID unique : Nom + 10 caractères aléatoires
    import random, string
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    unique_id = context.user_data['name'] + suffix
    context.user_data['unique_id'] = unique_id

    await update.message.reply_text(
        f"✅ **ID unique généré** : `{unique_id}`\n"
        "Entrez le **nombre de jours** d'abonnement (0 pour un essai de 8h) :"
    )
    return CREATE_DAYS

# === ÉTAPE : Jours ===
async def create_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        days = int(text)
        if days < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Entrez un nombre entier >= 0.")
        return CREATE_DAYS

    context.user_data['days'] = days

    # Appel API pour créer l'utilisateur
    payload = {
        "admin_token": ADMIN_TOKEN,
        "unique_id": context.user_data['unique_id'],
        "name": context.user_data['name'],
        "api_id": context.user_data['api_id'],
        "api_hash": context.user_data['api_hash'],
        "days": days
    }
    try:
        resp = requests.post(f"{SERVER_URL}/create_user", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            await update.message.reply_text(
                f"✅ **Utilisateur créé !**\n"
                f"ID unique : `{data['unique_id']}`\n"
                f"Nom : {context.user_data['name']}\n"
                f"Jours : {days}\n"
                f"Expiration : {time.strftime('%d/%m/%Y', time.localtime(data['expires_at']))}"
            )
        else:
            await update.message.reply_text(f"❌ Erreur serveur : {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}")

    return ConversationHandler.END

# === RENOUVELLEMENT : ID ===
async def renew_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['renew_id'] = update.message.text.strip()
    await update.message.reply_text("Entrez le **nombre de jours** à ajouter :")
    return RENEW_DAYS

# === RENOUVELLEMENT : Jours ===
async def renew_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        days = int(text)
        if days <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Entrez un nombre entier positif.")
        return RENEW_DAYS

    payload = {
        "admin_token": ADMIN_TOKEN,
        "identifier": context.user_data['renew_id'],
        "days": days
    }
    try:
        resp = requests.post(f"{SERVER_URL}/renew_user", json=payload, timeout=10)
        if resp.status_code == 200:
            await update.message.reply_text(f"✅ Abonnement prolongé de {days} jours.")
        else:
            await update.message.reply_text(f"❌ Erreur : {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}")

    return ConversationHandler.END

# === DÉTAIL ===
async def detail_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identifier = update.message.text.strip()
    payload = {"admin_token": ADMIN_TOKEN, "identifier": identifier}
    try:
        resp = requests.get(f"{SERVER_URL}/user_detail", params=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            msg = (
                f"🔍 **Détails**\n"
                f"ID unique : `{data.get('unique_id')}`\n"
                f"Nom : {data.get('name')}\n"
                f"API ID : {data.get('api_id')}\n"
                f"API Hash : {data.get('api_hash', '')[:10]}...\n"
                f"Expiration : {time.strftime('%d/%m/%Y', time.localtime(data.get('expires_at')))}\n"
                f"Fingerprint : {data.get('active_fingerprint', 'Aucun')[:8]}..."
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}")

    return ConversationHandler.END

# === LISTE ===
async def list_users(update: Update):
    payload = {"admin_token": ADMIN_TOKEN}
    try:
        resp = requests.get(f"{SERVER_URL}/list_users", params=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            users = data.get('users', [])
            if not users:
                await update.message.reply_text("📭 Aucun utilisateur.")
                return
            msg = "📋 **Liste des utilisateurs** :\n\n"
            for u in users:
                status = "✅ Actif" if u.get('active') else "❌ Expiré"
                msg += f"• `{u['unique_id']}` - {u['name']} - {status}\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Erreur serveur : {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}")

# === STATISTIQUES ===
async def stats(update: Update):
    payload = {"admin_token": ADMIN_TOKEN}
    try:
        resp = requests.get(f"{SERVER_URL}/stats", params=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            msg = (
                f"📊 **Statistiques**\n"
                f"Total : {data.get('total')}\n"
                f"Actifs : {data.get('active')}\n"
                f"Expirés : {data.get('expired')}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Erreur serveur : {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}")

# === CONVERSATION HANDLER ===
def get_conversation_handler():
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)],
        states={
            CREATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_name)],
            CREATE_API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_api_id)],
            CREATE_API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_api_hash)],
            CREATE_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_days)],
            RENEW_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, renew_id)],
            RENEW_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, renew_days)],
            DETAIL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, detail_id)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: u.message.reply_text("Annulé."))],
        per_message=False,
    )
    return conv

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(get_conversation_handler())
    print("Bot démarré avec succès !")
    app.run_polling()

if __name__ == "__main__":
    main()