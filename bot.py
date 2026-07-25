import os
import requests
import hashlib
import json
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

# === CONFIGURATION ===
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

# === COMMANDES ===
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
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(
        "👋 **Dashboard Admin**\nChoisissez une action :",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# === GESTION DES MENUS (Réponses aux boutons) ===
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "➕ Créer un ID unique":
        await update.message.reply_text("Entrez le **nom Telegram** de l'utilisateur :")
        return UNIQUE_ID_NAME
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

# === ÉTAPES DE CRÉATION ===
async def create_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Entrez l'**API ID** (nombre) :")
    return UNIQUE_ID_API_ID

async def create_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['api_id'] = int(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ L'API ID doit être un nombre. Réessayez :")
        return UNIQUE_ID_API_ID
    await update.message.reply_text("Entrez l'**API Hash** :")
    return UNIQUE_ID_API_HASH

async def create_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['api_hash'] = update.message.text
    await update.message.reply_text("Entrez le **nombre de jours** d'abonnement (ex: 30) :")
    return UNIQUE_ID_DAYS

async def create_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text)
        if days <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Entrez un nombre de jours valide (positif) :")
        return UNIQUE_ID_DAYS

    name = context.user_data['name']
    api_id = context.user_data['api_id']
    api_hash = context.user_data['api_hash']
    raw = f"{name}{api_id}{api_hash}"
    unique_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    payload = {
        "admin_token": ADMIN_TOKEN,
        "unique_id": unique_id,
        "name": name,
        "api_id": api_id,
        "api_hash": api_hash,
        "days": days
    }
    try:
        resp = requests.post(f"{SERVER_URL}/create_user", json=payload, timeout=10)
        if resp.status_code == 200:
            await update.message.reply_text(
                f"✅ **Utilisateur créé !**\n"
                f"ID unique : `{unique_id}`\n"
                f"Nom : {name}\n"
                f"Jours : {days}\n"
                f"Expiration : {datetime.fromtimestamp(resp.json().get('expires_at')).strftime('%d/%m/%Y')}"
            )
        else:
            await update.message.reply_text(f"❌ Erreur serveur : {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}")

    return ConversationHandler.END

async def renew_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['renew_id'] = update.message.text
    await update.message.reply_text("Entrez le **nombre de jours** à ajouter :")
    return RENEW_DAYS

async def renew_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text)
        if days <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Entrez un nombre de jours valide :")
        return RENEW_DAYS

    user_id = context.user_data['renew_id']
    payload = {
        "admin_token": ADMIN_TOKEN,
        "identifier": user_id,
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

async def detail_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text
    payload = {"admin_token": ADMIN_TOKEN, "identifier": user_id}
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
                f"Expiration : {datetime.fromtimestamp(data.get('expires_at')).strftime('%d/%m/%Y')}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}")

    return ConversationHandler.END

# === FONCTIONS D'AFFICHAGE (listes et stats) ===
async def list_users(update: Update):
    payload = {"admin_token": ADMIN_TOKEN}
    try:
        resp = requests.get(f"{SERVER_URL}/list_users", params=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            users = data.get('users', [])
            if not users:
                await update.message.reply_text("📭 Aucun utilisateur enregistré.")
                return
            msg = "📋 **Liste des utilisateurs :**\n\n"
            for u in users:
                status = "✅ Actif" if u.get('active') else "❌ Expiré"
                msg += f"• `{u['unique_id']}` - {u['name']} - {status}\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Erreur serveur : {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}")

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
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)],
        states={
            UNIQUE_ID_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_name)],
            UNIQUE_ID_API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_api_id)],
            UNIQUE_ID_API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_api_hash)],
            UNIQUE_ID_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_days)],
            RENEW_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, renew_id)],
            RENEW_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, renew_days)],
            DETAIL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, detail_id)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: u.message.reply_text("Annulé."))],
        per_message=False,
    )
    return conv_handler

# === MAIN ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(get_conversation_handler())
    print("Bot démarré avec succès !")
    app.run_polling()

if __name__ == "__main__":
    main()