import requests
import time
import json
import os
import sys
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio

# ------------------ CONFIGURATION ------------------
API_KEY = "dbf85125f5976abc68f1a2b168cdc83f"
BASE_URL = "https://botp.live/api"

TELEGRAM_BOT_TOKEN = "8746609920:AAG3u2p-f7tC-gLTrTdGMuToQ4eRzq9Vjw8"
ADMIN_USER_IDS = [1857783746]  # Admin Telegram User IDs
YOUR_PROFILE_LINK = "https://t.me/FUR_MAN"  # Apna profile link daalo

INSTAGRAM_APP_ID = "5"  # Instagram service app ID
USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"

# ------------------ DATABASE FUNCTIONS ------------------
def load_json(filename, default=None):
    if default is None:
        default = {}
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(filename, data):
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving {filename}: {e}")

def get_user_data(user_id):
    users = load_json(USERS_FILE)
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {
            "credits": 0,
            "total_spent": 0,
            "joined_date": str(datetime.now()),
            "orders": []
        }
        save_json(USERS_FILE, users)
    return users[user_id], users

def save_user_data(user_id, data):
    users = load_json(USERS_FILE)
    users[str(user_id)] = data
    save_json(USERS_FILE, users)

# ------------------ API FUNCTIONS ------------------
def api_request(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=15)
        text = response.text
        if text.startswith('\ufeff'):
            text = text[1:]
        return json.loads(text)
    except Exception as e:
        print(f"API Error: {e}")
        return None

def buy_number(app_id):
    return api_request(f"{BASE_URL}/sim/buy", {"key": API_KEY, "app": app_id})

def check_order(order_id):
    return api_request(f"{BASE_URL}/sim/check", {"key": API_KEY, "id": order_id})

def get_apps():
    data = api_request(f"{BASE_URL}/apps", {"key": API_KEY})
    if data and data.get("success"):
        return data["data"]
    return []

def get_instagram_price():
    try:
        apps = get_apps()
        for app in apps:
            if str(app['id']) == INSTAGRAM_APP_ID:
                return float(app['price'])
    except:
        pass
    return 10.0  # Default price

# ------------------ BOT HANDLERS ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - Bot ka welcome message"""
    user = update.effective_user
    user_data, _ = get_user_data(user.id)
    
    # Save user info
    users = load_json(USERS_FILE)
    if str(user.id) not in users:
        users[str(user.id)] = {
            "credits": 0,
            "total_spent": 0,
            "joined_date": str(datetime.now()),
            "username": user.username or user.first_name
        }
        save_json(USERS_FILE, users)
    
    keyboard = [
        [InlineKeyboardButton("🔑 Buy Instagram Number", callback_data="menu_generate")],
        [InlineKeyboardButton("💰 My Credits", callback_data="menu_credit")],
        [InlineKeyboardButton("📋 Purchase History", callback_data="menu_history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎉 *Welcome to SIM Rental Bot!*\n\n"
        f"👤 *User:* {user.first_name}\n"
        f"💰 *Credits:* {user_data['credits']}\n\n"
        f"📱 *Instagram Number Price:* {get_instagram_price()} credits\n\n"
        f"📋 *Commands:*\n"
        f"• /generate - Buy Instagram number\n"
        f"• /credit - Check credits\n"
        f"• /history - Purchase history\n\n"
        f"💡 *Need credits?* Contact admin!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate Instagram number"""
    user = update.effective_user
    user_data, users = get_user_data(user.id)
    insta_price = get_instagram_price()
    
    # Check credits
    if user_data['credits'] < insta_price:
        keyboard = [[InlineKeyboardButton("💳 Buy Credits", url=YOUR_PROFILE_LINK)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ *Insufficient Credits!*\n\n"
            f"💰 Required: *{insta_price}* credits\n"
            f"📊 Your Balance: *{user_data['credits']}* credits\n\n"
            f"Contact admin to purchase credits:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Deduct credits
    user_data['credits'] -= insta_price
    user_data['total_spent'] += insta_price
    save_user_data(user.id, user_data)
    
    # Send waiting message
    msg = await update.message.reply_text("🔄 *Purchasing number... Please wait*", parse_mode='Markdown')
    
    # Buy number from API
    result = buy_number(INSTAGRAM_APP_ID)
    
    if not result or not result.get("success"):
        # Refund
        user_data['credits'] += insta_price
        user_data['total_spent'] -= insta_price
        save_user_data(user.id, user_data)
        
        error = result.get('msg', 'API Error') if result else 'No response'
        await msg.edit_text(f"❌ *Purchase Failed!*\nCredits refunded.\nError: {error}", parse_mode='Markdown')
        return
    
    data = result["data"]
    order_id = data["id"]
    number = data["number"]
    price = data["price"]
    
    # Save order
    try:
        order_info = {
            "user_id": user.id,
            "username": user.username or user.first_name,
            "order_id": order_id,
            "number": number,
            "price": price,
            "status": "pending",
            "created_at": str(datetime.now()),
            "otp": None
        }
        with open(ORDERS_FILE, 'a') as f:
            f.write(json.dumps(order_info) + "\n")
    except:
        pass
    
    await msg.edit_text(
        f"✅ *Number Purchased!*\n\n"
        f"📱 *Number:* `{number}`\n"
        f"💰 *Cost:* {price} credits\n"
        f"🆔 *Order:* `{order_id}`\n\n"
        f"⏳ *Waiting for OTP...*",
        parse_mode='Markdown'
    )
    
    # Monitor OTP
    await monitor_otp(msg, order_id, number)

async def monitor_otp(message, order_id, number):
    """Monitor OTP with live updates"""
    for i in range(60):  # 5 minutes max
        await asyncio.sleep(5)
        
        try:
            result = check_order(order_id)
            if not result or not result.get("success"):
                continue
                
            data = result["data"]
            status = data.get("status")
            
            if status == 1:  # OTP received
                code = data.get("code", "N/A")
                sms = data.get("message", "")
                
                # Update order
                update_order(order_id, "completed", code)
                
                await message.edit_text(
                    f"✅ *OTP RECEIVED!*\n\n"
                    f"📱 *Number:* `{number}`\n"
                    f"🔑 *OTP:* `{code}`\n"
                    f"📝 *Message:* {sms}\n\n"
                    f"🎉 Use this OTP for verification!",
                    parse_mode='Markdown'
                )
                return
                
            elif status == -1:  # Failed
                await message.edit_text(
                    f"❌ *Order Failed*\n\n"
                    f"📱 Number: `{number}`\n"
                    f"🆔 Order: `{order_id}`",
                    parse_mode='Markdown'
                )
                return
                
            else:  # Still waiting
                dots = "." * ((i % 3) + 1)
                if i % 2 == 0:  # Update every 10s
                    await message.edit_text(
                        f"📱 *Number:* `{number}`\n"
                        f"⏳ *Waiting{dots}*\n"
                        f"🔄 {i*5}s elapsed\n\n"
                        f"🆔 Order: `{order_id}`",
                        parse_mode='Markdown'
                    )
        except:
            pass
    
    # Timeout
    await message.edit_text(
        f"⏰ *Timeout!*\n\n"
        f"📱 Number: `{number}`\n"
        f"No OTP received in 5 minutes.\n"
        f"Try again with /generate",
        parse_mode='Markdown'
    )

def update_order(order_id, status, otp=None):
    """Update order in file"""
    try:
        if not os.path.exists(ORDERS_FILE):
            return
        orders = []
        with open(ORDERS_FILE, 'r') as f:
            for line in f:
                try:
                    o = json.loads(line.strip())
                    if o.get('order_id') == order_id:
                        o['status'] = status
                        if otp:
                            o['otp'] = otp
                    orders.append(o)
                except:
                    pass
        with open(ORDERS_FILE, 'w') as f:
            for o in orders:
                f.write(json.dumps(o) + "\n")
    except:
        pass

async def credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check credits"""
    user = update.effective_user
    user_data, _ = get_user_data(user.id)
    
    keyboard = [
        [InlineKeyboardButton("💳 Purchase Credits", url=YOUR_PROFILE_LINK)],
        [InlineKeyboardButton("📋 History", callback_data="menu_history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"💳 *Credit Info*\n\n"
        f"👤 User: {user.first_name}\n"
        f"💰 Available: *{user_data['credits']}* credits\n"
        f"💸 Total Spent: *{user_data['total_spent']}* credits\n\n"
        f"📱 Instagram: {get_instagram_price()} credits/num\n\n"
        f"Need more? Click below:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Purchase history"""
    user = update.effective_user
    
    # Load orders
    user_orders = []
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, 'r') as f:
            for line in f:
                try:
                    o = json.loads(line.strip())
                    if str(o.get('user_id')) == str(user.id):
                        user_orders.append(o)
                except:
                    pass
    
    if not user_orders:
        await update.message.reply_text(
            "📋 *No History*\n\nUse /generate to buy your first number!",
            parse_mode='Markdown'
        )
        return
    
    # Show last 5
    recent = sorted(user_orders, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
    
    text = "📋 *Last 5 Purchases*\n\n"
    for i, o in enumerate(recent, 1):
        s = "✅" if o.get('status') == 'completed' else "⏳"
        otp = f"\n🔑 OTP: `{o['otp']}`" if o.get('otp') else ""
        text += (
            f"{s} *#{i}*\n"
            f"📱 `{o['number']}`\n"
            f"💰 {o['price']} credits\n"
            f"📅 {o['created_at'][:19]}{otp}\n"
            f"───\n"
        )
    
    keyboard = [[InlineKeyboardButton("🔑 Buy New", callback_data="menu_generate")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def addcredit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Add credits"""
    user = update.effective_user
    
    if user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin only command!")
        return
    
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("Usage: /addcredit user_id amount")
            return
        
        target_id = str(args[0])
        amount = float(args[1])
        
        users = load_json(USERS_FILE)
        if target_id not in users:
            await update.message.reply_text("❌ User not found! They must /start first.")
            return
        
        users[target_id]['credits'] += amount
        save_json(USERS_FILE, users)
        
        await update.message.reply_text(
            f"✅ *Credits Added!*\n\n"
            f"👤 User: `{target_id}`\n"
            f"💰 Amount: *{amount}*\n"
            f"📊 New Balance: *{users[target_id]['credits']}*",
            parse_mode='Markdown'
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=int(target_id),
                text=f"💰 *Credits Added!*\n\n+{amount} credits\nBalance: {users[target_id]['credits']}\n\nUse /generate to buy numbers!",
                parse_mode='Markdown'
            )
        except:
            pass
            
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu_generate":
        # Trigger generate command
        fake_msg = query.message
        fake_msg.from_user = query.from_user
        await generate_command(Update(update.update_id, message=fake_msg), context)
    
    elif query.data == "menu_credit":
        user_data, _ = get_user_data(query.from_user.id)
        await query.message.reply_text(
            f"💰 *Credits:* {user_data['credits']}\nUse /credit for details.",
            parse_mode='Markdown'
        )
    
    elif query.data == "menu_history":
        fake_msg = query.message
        fake_msg.from_user = query.from_user
        await history_command(Update(update.update_id, message=fake_msg), context)

async def post_init(application: Application):
    """Set commands after init"""
    commands = [
        BotCommand("start", "Start bot"),
        BotCommand("generate", "Buy Instagram number"),
        BotCommand("credit", "Check credits"),
        BotCommand("history", "Purchase history"),
        BotCommand("addcredit", "Admin: Add credits")
    ]
    await application.bot.set_my_commands(commands)
    print("✅ Commands set!")

def main():
    print("🤖 Starting Bot...")
    
    # Build application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("generate", generate_command))
    app.add_handler(CommandHandler("credit", credit_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("addcredit", addcredit_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Bot ready!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
