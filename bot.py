import os
import requests
import re
import random
import string
import time
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler, ContextTypes

# === CONFIGURATION ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
SERVER_URL = "https://cgaucho.pythonanywhere.com"
ITEMS_PER_PAGE = 5  # Nombre d'utilisateurs par page

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

# === FONCTIONS UTILITAIRES ===
def get_main_menu_keyboard():
    keyboard = [
        ["➕ Créer un ID unique"],
        ["🔄 Renouveler un abonnement"],
        ["📋 Liste des utilisateurs"],
        ["🔍 Détails d'un utilisateur"],
        ["📊 Statistiques"],
        ["❌ Annuler / Retour"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def send_main_menu(update: Update, message: str = "👋 **Dashboard Admin**\nChoisissez une action :"):
    await update.message.reply_text(
        message,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

# === COMMANDE /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Accès réservé à l'administrateur.")
        return
    await send_main_menu(update)

# === GESTION DU MENU PRINCIPAL ===
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "➕ Créer un ID unique":
        await update.message.reply_text("Entrez le **nom** de l'utilisateur (sans espaces) :")
        return CREATE_NAME
    elif text == "🔄 Renouveler un abonnement":
        await update.message.reply_text("Entrez l'**ID unique** ou l'**ID Telegram** :")
        return RENEW_ID
    elif text == "📋 Liste des utilisateurs":
        await list_users(update, page=0)  # Page 0 = première page
        return ConversationHandler.END  # On sort de la conversation, car on utilise des callbacks
    elif text == "🔍 Détails d'un utilisateur":
        await update.message.reply_text("Entrez l'**ID unique** :")
        return DETAIL_ID
    elif text == "📊 Statistiques":
        await stats(update)
        return ConversationHandler.END
    elif text == "❌ Annuler / Retour":
        await send_main_menu(update, "✅ Retour au menu principal.")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Commande inconnue. Utilisez les boutons.")
        return ConversationHandler.END

# === CRÉATION D'UN UTILISATEUR ===
async def create_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if " " in name:
        await update.message.reply_text("❌ Le nom ne doit pas contenir d'espaces.")
        return CREATE_NAME
    context.user_data['name'] = name
    await update.message.reply_text("Entrez l'**API ID** (6 chiffres) :")
    return CREATE_API_ID

async def create_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or len(text) != 6:
        await update.message.reply_text("❌ L'API ID doit être un nombre de 6 chiffres.")
        return CREATE_API_ID
    context.user_data['api_id'] = int(text)
    await update.message.reply_text("Entrez l'**API Hash** (32 caractères alphanumériques) :")
    return CREATE_API_HASH

async def create_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) != 32 or not text.isalnum():
        await update.message.reply_text("❌ L'API Hash doit faire 32 caractères alphanumériques.")
        return CREATE_API_HASH
    context.user_data['api_hash'] = text

    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    unique_id = context.user_data['name'] + suffix
    context.user_data['unique_id'] = unique_id

    await update.message.reply_text(
        f"✅ **ID unique généré** : `{unique_id}`\n"
        "Entrez le **nombre de jours** d'abonnement (0 pour un essai de 8h) :"
    )
    return CREATE_DAYS

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
                f"Expiration : {time.strftime('%d/%m/%Y %H:%M', time.localtime(data['expires_at']))}"
            )
        else:
            await update.message.reply_text(f"❌ Erreur serveur : {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}")

    # Retour au menu
    await send_main_menu(update, "✅ Opération terminée.")
    return ConversationHandler.END

# === RENOUVELLEMENT ===
async def renew_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Annuler / Retour":
        await send_main_menu(update, "✅ Retour au menu principal.")
        return ConversationHandler.END
    context.user_data['renew_id'] = text
    await update.message.reply_text("Entrez le **nombre de jours** à ajouter :")
    return RENEW_DAYS

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

    await send_main_menu(update, "✅ Opération terminée.")
    return ConversationHandler.END

# === DÉTAIL D'UN UTILISATEUR (saisie manuelle) ===
async def detail_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Annuler / Retour":
        await send_main_menu(update, "✅ Retour au menu principal.")
        return ConversationHandler.END
    await show_user_detail(update, text)
    await send_main_menu(update, "✅ Détails affichés.")
    return ConversationHandler.END

# === FONCTION AFFICHER LES DÉTAILS D'UN UTILISATEUR (réutilisable) ===
async def show_user_detail(update: Update, identifier: str):
    payload = {"admin_token": ADMIN_TOKEN, "identifier": identifier}
    try:
        resp = requests.get(f"{SERVER_URL}/user_detail", params=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            fingerprint = data.get('active_fingerprint', 'Aucun')
            if fingerprint and fingerprint != 'None':
                fingerprint = fingerprint[:8] + "..."
            else:
                fingerprint = "Aucun"
            msg = (
                f"🔍 **Détails de l'utilisateur**\n"
                f"🆔 ID unique : `{data.get('unique_id')}`\n"
                f"👤 Nom : {data.get('name')}\n"
                f"📱 API ID : {data.get('api_id')}\n"
                f"🔑 API Hash : {data.get('api_hash', '')[:10]}...\n"
                f"📅 Expiration : {time.strftime('%d/%m/%Y %H:%M', time.localtime(data.get('expires_at')))}\n"
                f"📱 Fingerprint : {fingerprint}\n"
                f"🕒 Dernière connexion : {time.strftime('%d/%m/%Y %H:%M', time.localtime(data.get('last_seen', 0))) if data.get('last_seen') else 'Jamais'}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        elif resp.status_code == 404:
            await update.message.reply_text("❌ Utilisateur non trouvé.")
        else:
            await update.message.reply_text(f"❌ Erreur serveur : {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}")

# === LISTE DES UTILISATEURS (paginée) ===
async def list_users(update: Update, page: int = 0):
    payload = {"admin_token": ADMIN_TOKEN}
    try:
        resp = requests.get(f"{SERVER_URL}/list_users", params=payload, timeout=10)
        if resp.status_code != 200:
            await update.message.reply_text(f"❌ Erreur serveur : {resp.text[:200]}")
            return
        data = resp.json()
        users = data.get('users', [])
        if not users:
            await update.message.reply_text("📭 Aucun utilisateur enregistré.")
            return

        total = len(users)
        start = page * ITEMS_PER_PAGE
        end = min(start + ITEMS_PER_PAGE, total)
        page_users = users[start:end]

        # Construire le message
        msg = f"📋 **Liste des utilisateurs** (page {page+1}/{ (total-1)//ITEMS_PER_PAGE + 1 })\n\n"
        for u in page_users:
            status = "✅" if u.get('active') else "❌"
            msg += f"{status} `{u['unique_id']}` - {u['name']}\n"

        # Boutons de pagination et de détail
        keyboard = []
        row = []
        if page > 0:
            row.append(InlineKeyboardButton("◀️ Précédent", callback_data=f"list_{page-1}"))
        if end < total:
            row.append(InlineKeyboardButton("Suivant ▶️", callback_data=f"list_{page+1}"))
        if row:
            keyboard.append(row)

        # Ajouter des boutons pour chaque utilisateur de la page (pour voir les détails)
        for u in page_users:
            keyboard.append([InlineKeyboardButton(
                f"🔍 {u['name']} ({u['unique_id']})",
                callback_data=f"detail_{u['unique_id']}"
            )])

        # Bouton retour au menu
        keyboard.append([InlineKeyboardButton("🏠 Retour au menu", callback_data="menu")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
            await update.callback_query.answer()
        else:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}")

# === GESTION DES CALLBACKS (pagination et détails) ===
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("list_"):
        page = int(data.split("_")[1])
        await list_users(update, page)
    elif data.startswith("detail_"):
        unique_id = data.split("_", 1)[1]
        await show_user_detail(update, unique_id)
        # Après affichage, on renvoie vers la liste
        await list_users(update, 0)  # Retour à la première page
    elif data == "menu":
        await send_main_menu(update, "✅ Retour au menu principal.")
        await query.message.delete()  # Supprime le message de la liste
        await query.answer()
    else:
        await query.answer("Action inconnue.")

# === STATISTIQUES ===
async def stats(update: Update):
    payload = {"admin_token": ADMIN_TOKEN}
    try:
        resp = requests.get(f"{SERVER_URL}/stats", params=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            msg = (
                f"📊 **Statistiques**\n"
                f"Total utilisateurs : {data.get('total')}\n"
                f"✅ Actifs : {data.get('active')}\n"
                f"❌ Expirés : {data.get('expired')}"
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
        fallbacks=[
            CommandHandler("cancel", lambda u, c: u.message.reply_text("Annulé.")),
            MessageHandler(filters.Regex("^❌ Annuler / Retour$"), lambda u, c: send_main_menu(u, "✅ Retour au menu principal."))
        ],
        per_message=False,
    )
    return conv

# === MAIN ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(get_conversation_handler())
    app.add_handler(CallbackQueryHandler(button_callback))
    print("Bot démarré avec succès !")
    app.run_polling()

if __name__ == "__main__":
    main()