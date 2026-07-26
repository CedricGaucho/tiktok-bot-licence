import os
import requests
import re
import time
import random
import string
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes

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
    CREATE_DAYS,
    RENEW_ID,
    RENEW_DAYS,
    DETAIL_ID,
    UNBLOCK_ID,
) = range(8)

# === CLAVIERS ===
def get_main_keyboard():
    """Clavier principal affiché en bas."""
    keyboard = [
        ["➕ Créer un ID unique"],
        ["🔄 Renouveler un abonnement"],
        ["📋 Liste des utilisateurs"],
        ["🔍 Détails d'un utilisateur"],
        ["🔓 Débloquer un utilisateur"],
        ["📊 Statistiques"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    """Clavier avec un seul bouton Annuler."""
    return ReplyKeyboardMarkup([["❌ Annuler"]], resize_keyboard=True)

# === COMMANDE /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Accès réservé à l'administrateur.")
        return

    context.user_data.clear()
    await update.message.reply_text(
        "👋 **Dashboard Admin**\nChoisissez une action :",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

# === ANNULER / RETOUR ===
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Opération annulée.\nChoisissez une action :",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def check_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vérifie si le message est 'Annuler' et annule la conversation."""
    if update.message.text == "❌ Annuler":
        await cancel(update, context)
        return True
    return False

# === GESTION DES MENUS (boutons principaux) ===
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "➕ Créer un ID unique":
        await update.message.reply_text("Entrez le **nom** de l'utilisateur (sans espaces) :", reply_markup=get_cancel_keyboard())
        return CREATE_NAME
    elif text == "🔄 Renouveler un abonnement":
        await update.message.reply_text("Entrez l'**ID unique** ou l'**ID Telegram** :", reply_markup=get_cancel_keyboard())
        return RENEW_ID
    elif text == "📋 Liste des utilisateurs":
        await list_users_paginated(update, context, page=0)
        return ConversationHandler.END
    elif text == "🔍 Détails d'un utilisateur":
        await update.message.reply_text("Entrez l'**ID unique** ou l'**ID Telegram** :", reply_markup=get_cancel_keyboard())
        return DETAIL_ID
    elif text == "🔓 Débloquer un utilisateur":
        await update.message.reply_text("Entrez l'**ID unique** ou l'**ID Telegram** à débloquer :", reply_markup=get_cancel_keyboard())
        return UNBLOCK_ID
    elif text == "📊 Statistiques":
        await stats(update)
        return ConversationHandler.END
    elif text == "❌ Annuler":
        await cancel(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Commande inconnue. Utilisez les boutons.")
        return ConversationHandler.END

# === CRÉATION D'UN UTILISATEUR ===
async def create_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    name = update.message.text.strip()
    if " " in name:
        await update.message.reply_text("❌ Le nom ne doit pas contenir d'espaces. Réessayez :")
        return CREATE_NAME
    context.user_data['name'] = name
    await update.message.reply_text("Entrez l'**API ID** (8 chiffres) :")
    return CREATE_API_ID

async def create_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    text = update.message.text.strip()
    if not text.isdigit() or len(text) != 8:
        await update.message.reply_text("❌ L'API ID doit être un nombre de 8 chiffres. Réessayez :")
        return CREATE_API_ID
    context.user_data['api_id'] = int(text)
    await update.message.reply_text("Entrez l'**API Hash** (32 caractères alphanumériques) :")
    return CREATE_API_HASH

async def create_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    text = update.message.text.strip()
    if len(text) != 32 or not text.isalnum():
        await update.message.reply_text("❌ L'API Hash doit faire 32 caractères alphanumériques. Réessayez :")
        return CREATE_API_HASH
    context.user_data['api_hash'] = text

    # Génération automatique de l'ID unique : Nom + 10 caractères aléatoires
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    unique_id = context.user_data['name'] + suffix
    context.user_data['unique_id'] = unique_id

    await update.message.reply_text(
        f"✅ **ID unique généré** : `{unique_id}`\n"
        "Entrez le **nombre de jours** d'abonnement (0 pour un essai de 8h) :"
    )
    return CREATE_DAYS

async def create_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    text = update.message.text.strip()
    try:
        days = int(text)
        if days < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Entrez un nombre entier >= 0. Réessayez :")
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
                f"Expiration : {time.strftime('%d/%m/%Y %H:%M', time.localtime(data['expires_at']))}",
                reply_markup=get_main_keyboard()
            )
        else:
            await update.message.reply_text(f"❌ Erreur serveur : {resp.text[:200]}", reply_markup=get_main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}", reply_markup=get_main_keyboard())

    context.user_data.clear()
    return ConversationHandler.END

# === RENOUVELLEMENT ===
async def renew_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    context.user_data['renew_id'] = update.message.text.strip()
    await update.message.reply_text("Entrez le **nombre de jours** à ajouter :")
    return RENEW_DAYS

async def renew_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    text = update.message.text.strip()
    try:
        days = int(text)
        if days <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Entrez un nombre entier positif. Réessayez :")
        return RENEW_DAYS

    payload = {
        "admin_token": ADMIN_TOKEN,
        "identifier": context.user_data['renew_id'],
        "days": days
    }
    try:
        resp = requests.post(f"{SERVER_URL}/renew_user", json=payload, timeout=10)
        if resp.status_code == 200:
            await update.message.reply_text(f"✅ Abonnement prolongé de {days} jours.", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(f"❌ Erreur : {resp.text[:200]}", reply_markup=get_main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}", reply_markup=get_main_keyboard())

    context.user_data.clear()
    return ConversationHandler.END

# === DÉTAILS D'UN UTILISATEUR ===
async def detail_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    identifier = update.message.text.strip()
    payload = {"admin_token": ADMIN_TOKEN, "identifier": identifier}
    try:
        resp = requests.get(f"{SERVER_URL}/user_detail", params=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            msg = (
                f"🔍 **Détails de l'utilisateur**\n"
                f"ID unique : `{data.get('unique_id')}`\n"
                f"Nom : {data.get('name')}\n"
                f"API ID : {data.get('api_id')}\n"
                f"API Hash : {data.get('api_hash', '')[:10]}...\n"
                f"Expiration : {time.strftime('%d/%m/%Y %H:%M', time.localtime(data.get('expires_at')))}\n"
                f"Fingerprint : {data.get('active_fingerprint', 'Aucun')[:8] if data.get('active_fingerprint') else 'Aucun'}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(f"❌ {resp.text[:200]}", reply_markup=get_main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}", reply_markup=get_main_keyboard())

    context.user_data.clear()
    return ConversationHandler.END

# === DÉBLOQUER UN UTILISATEUR ===
async def unblock_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    identifier = update.message.text.strip()
    payload = {
        "admin_token": ADMIN_TOKEN,
        "identifier": identifier
    }
    try:
        resp = requests.post(f"{SERVER_URL}/unblock_user", json=payload, timeout=10)
        if resp.status_code == 200:
            await update.message.reply_text(f"✅ Utilisateur débloqué avec succès.", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(f"❌ Erreur : {resp.text[:200]}", reply_markup=get_main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}", reply_markup=get_main_keyboard())

    context.user_data.clear()
    return ConversationHandler.END

# === LISTE PAGINÉE (avec InlineKeyboard) ===
async def list_users_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    if 'users_list' not in context.user_data or context.user_data.get('page') != page:
        # Charger la liste depuis le serveur
        payload = {"admin_token": ADMIN_TOKEN}
        try:
            resp = requests.get(f"{SERVER_URL}/list_users", params=payload, timeout=10)
            if resp.status_code != 200:
                await update.message.reply_text(f"❌ Erreur serveur : {resp.text[:200]}", reply_markup=get_main_keyboard())
                return
            users = resp.json().get('users', [])
            context.user_data['users_list'] = users
            context.user_data['page'] = page
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur de connexion : {e}", reply_markup=get_main_keyboard())
            return
    else:
        users = context.user_data['users_list']

    if not users:
        await update.message.reply_text("📭 Aucun utilisateur enregistré.", reply_markup=get_main_keyboard())
        return

    page_size = 10
    total_pages = (len(users) + page_size - 1) // page_size
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    start = page * page_size
    end = min(start + page_size, len(users))
    page_users = users[start:end]

    msg = f"📋 **Liste des utilisateurs (page {page+1}/{total_pages})**\n\n"
    for u in page_users:
        status = "✅ Actif" if u.get('active') else "❌ Expiré"
        msg += f"• {u['name']} - `{u['unique_id']}` - {status}\n"

    # Boutons de pagination et détails par utilisateur
    keyboard = []
    for u in page_users:
        keyboard.append([InlineKeyboardButton(u['name'], callback_data=f"detail_{u['unique_id']}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Précédent", callback_data=f"list_page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("▶️ Suivant", callback_data=f"list_page_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🏠 Menu principal", callback_data="back_to_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        await update.callback_query.answer()
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

# === GESTION DES CALLBACKS (pagination + détails) ===
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith("list_page_"):
        page = int(data.split("_")[2])
        await list_users_paginated(update, context, page=page)
    elif data.startswith("detail_"):
        unique_id = data.split("_")[1]
        payload = {"admin_token": ADMIN_TOKEN, "identifier": unique_id}
        try:
            resp = requests.get(f"{SERVER_URL}/user_detail", params=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                msg = (
                    f"🔍 **Détails de l'utilisateur**\n"
                    f"ID unique : `{data.get('unique_id')}`\n"
                    f"Nom : {data.get('name')}\n"
                    f"API ID : {data.get('api_id')}\n"
                    f"API Hash : {data.get('api_hash', '')[:10]}...\n"
                    f"Expiration : {time.strftime('%d/%m/%Y %H:%M', time.localtime(data.get('expires_at')))}\n"
                    f"Fingerprint : {data.get('active_fingerprint', 'Aucun')[:8] if data.get('active_fingerprint') else 'Aucun'}"
                )
                await query.message.reply_text(msg, parse_mode="Markdown")
            else:
                await query.message.reply_text(f"❌ Erreur : {resp.text[:200]}")
        except Exception as e:
            await query.message.reply_text(f"❌ Erreur de connexion : {e}")
    elif data == "back_to_menu":
        await query.message.delete()
        await query.message.reply_text(
            "👋 **Dashboard Admin**\nChoisissez une action :",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
        context.user_data.pop('users_list', None)
        context.user_data.pop('page', None)

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
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(f"❌ Erreur serveur : {resp.text[:200]}", reply_markup=get_main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur de connexion : {e}", reply_markup=get_main_keyboard())

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
            UNBLOCK_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, unblock_id)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )
    return conv

# === MAIN ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(callback_handler, pattern="^(list_page_|detail_|back_to_menu)"))
    app.add_handler(get_conversation_handler())
    print("Bot démarré avec succès !")
    app.run_polling()

if __name__ == "__main__":
    main()