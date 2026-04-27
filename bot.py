import requests
import time
import json
import os
import sys
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio

# Check Python version
if sys.version_info >= (3, 13):
    print("⚠️ Python 3.13 detected - Using compatibility mode")

# ------------------ CONFIGURATION ------------------
API_KEY = "dbf85125f5976abc68f1a2b168cdc83f"
BASE_URL = "https://botp.live/api"

# ---------- TELEGRAM CONFIG ----------
TELEGRAM_BOT_TOKEN = "8746609920:AAG3u2p-f7tC-gLTrTdGMuToQ4eRzq9Vjw8"
ADMIN_USER_IDS = [1857783746]  # Admin Telegram User IDs
YOUR_PROFILE_LINK = "https://t.me/FUR_MAN"  # Apna Telegram profile link yahan daalo

# ---------- INSTAGRAM APP ID ----------
INSTAGRAM_APP_ID = "5"  # Instagram service ka app ID

# ------------------ DATABASE (JSON Files) ------------------
USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"

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
        print(f"❌ API Error: {e}")
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

# ------------------ TELEGRAM BOT HANDLERS ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    try:
        user = update.effective_user
        user_data, _ = get_user_data(user.id)
        
        welcome_msg = f"""
🎉 <b>Welcome to SIM Rental Bot!</b>

👤 <b>User:</b> {user.first_name}
💰 <b>Credits:</b> {user_data['credits']}

📱 <b>Available Commands:</b>
/generate - Buy Instagram verification number
/credit - Check your credits & purchase more
/history - View your purchase history

💡 <b>How it works:</b>
1. Purchase credits from admin
2. Use /generate to get Instagram number
3. Wait for OTP delivery
4. Use OTP for verification

🔑 <b>Instagram Service Price:</b> {get_instagram_price()} credits per number
        """
        
        keyboard = [
            [InlineKeyboardButton("🔑 Generate Number", callback_data="generate")],
            [InlineKeyboardButton("💰 Check Credits", callback_data="check_credit")],
            [InlineKeyboardButton("📋 History", callback_data="history")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='HTML')
    except Exception as e:
        print(f"Error in start: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate command - Buy Instagram number"""
    try:
        user = update.effective_user
        user_data, users = get_user_data(user.id)
        
        insta_price = get_instagram_price()
        
        if user_data['credits'] < insta_price:
            keyboard = [[InlineKeyboardButton("💰 Buy Credits", url=YOUR_PROFILE_LINK)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"❌ <b>Insufficient Credits!</b>\n\n"
                f"💰 Required: <b>{insta_price}</b> credits\n"
                f"📊 Your Balance: <b>{user_data['credits']}</b> credits\n\n"
                f"Click below to purchase credits:",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return
        
        # Deduct credits
        user_data['credits'] -= insta_price
        user_data['total_spent'] += insta_price
        save_user_data(user.id, user_data)
        
        # Purchase number from API
        waiting_msg = await update.message.reply_text("🔄 <b>Purchasing Instagram number...</b>", parse_mode='HTML')
        
        result = buy_number(INSTAGRAM_APP_ID)
        
        if not result or not result.get("success"):
            # Refund credits
            user_data['credits'] += insta_price
            user_data['total_spent'] -= insta_price
            save_user_data(user.id, user_data)
            
            error_msg = result.get('msg', 'Unknown error') if result else 'No response from API'
            await waiting_msg.edit_text(
                f"❌ <b>Purchase Failed!</b>\n\n"
                f"💰 Credits refunded: {insta_price}\n"
                f"❌ Error: {error_msg}",
                parse_mode='HTML'
            )
            return
        
        data = result["data"]
        order_id = data["id"]
        number = data["number"]
        price = data["price"]
        
        # Save order
        try:
            with open(ORDERS_FILE, 'a') as f:
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
                f.write(json.dumps(order_info) + "\n")
        except Exception as e:
            print(f"Error saving order: {e}")
        
        await waiting_msg.edit_text(
            f"✅ <b>Number Purchased Successfully!</b>\n\n"
            f"📱 <b>Number:</b> <code>{number}</code>\n"
            f"💰 <b>Price:</b> {price} credits\n"
            f"🆔 <b>Order ID:</b> <code>{order_id}</code>\n\n"
            f"⏳ <b>Waiting for OTP...</b>\n"
            f"🔄 Auto-checking every 5 seconds...",
            parse_mode='HTML'
        )
        
        # Start OTP monitoring
        await monitor_otp_telegram(waiting_msg, order_id, number, user.id)
        
    except Exception as e:
        print(f"Error in generate: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

async def monitor_otp_telegram(message, order_id, number, user_id):
    """Monitor OTP and update Telegram message"""
    attempts = 0
    max_attempts = 60  # 5 minutes
    
    while attempts < max_attempts:
        try:
            result = check_order(order_id)
            
            if result and result.get("success"):
                data = result["data"]
                status = data.get("status")
                
                if status == 1:  # OTP received
                    code = data.get("code", "N/A")
                    sms_message = data.get("message", "")
                    
                    # Update order file
                    update_order_status(order_id, "completed", code)
                    
                    await message.edit_text(
                        f"✅ <b>OTP Received!</b>\n\n"
                        f"📱 <b>Number:</b> <code>{number}</code>\n"
                        f"🔑 <b>OTP Code:</b> <code>{code}</code>\n"
                        f"📝 <b>Message:</b> {sms_message}\n"
                        f"🆔 <b>Order ID:</b> {order_id}\n\n"
                        f"🎉 <b>Use this OTP for verification!</b>",
                        parse_mode='HTML'
                    )
                    return
                    
                elif status == -1:  # Failed
                    await message.edit_text(
                        f"❌ <b>Order Failed!</b>\n\n"
                        f"🆔 Order ID: <code>{order_id}</code>\n"
                        f"📱 Number: <code>{number}</code>\n",
                        parse_mode='HTML'
                    )
                    return
                    
                else:  # Still waiting
                    dots = "." * ((attempts % 3) + 1)
                    if attempts % 2 == 0:  # Update every 10 seconds
                        try:
                            await message.edit_text(
                                f"📱 <b>Number:</b> <code>{number}</code>\n"
                                f"⏳ <b>Waiting for OTP</b>{dots}\n"
                                f"🔄 Checking... ({attempts*5}s elapsed)\n\n"
                                f"🆔 Order ID: <code>{order_id}</code>",
                                parse_mode='HTML'
                            )
                        except:
                            pass
            
            await asyncio.sleep(5)
            attempts += 1
            
        except Exception as e:
            print(f"Monitor error: {e}")
            await asyncio.sleep(5)
            attempts += 1
    
    # Timeout
    try:
        await message.edit_text(
            f"⏰ <b>Timeout!</b>\n\n"
            f"📱 Number: <code>{number}</code>\n"
            f"🆔 Order ID: <code>{order_id}</code>\n\n"
            f"No OTP received within 5 minutes.\n"
            f"Please try again with /generate",
            parse_mode='HTML'
        )
    except:
        pass

def update_order_status(order_id, status, otp=None):
    """Update order status in file"""
    try:
        orders = []
        if os.path.exists(ORDERS_FILE):
            with open(ORDERS_FILE, 'r') as f:
                for line in f:
                    try:
                        order = json.loads(line.strip())
                        if order['order_id'] == order_id:
                            order['status'] = status
                            if otp:
                                order['otp'] = otp
                        orders.append(order)
                    except:
                        pass
        
        with open(ORDERS_FILE, 'w') as f:
            for order in orders:
                f.write(json.dumps(order) + "\n")
    except Exception as e:
        print(f"Error updating order: {e}")

async def credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Credit command - Check credits and show purchase button"""
    try:
        user = update.effective_user
        user_data, _ = get_user_data(user.id)
        
        keyboard = [
            [InlineKeyboardButton("💰 Purchase Credits", url=YOUR_PROFILE_LINK)],
            [InlineKeyboardButton("📋 View History", callback_data="history")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"💳 <b>Credit Information</b>\n\n"
            f"👤 <b>User:</b> {user.first_name}\n"
            f"💰 <b>Available Credits:</b> {user_data['credits']}\n"
            f"💸 <b>Total Spent:</b> {user_data['total_spent']}\n\n"
            f"📱 <b>Instagram Number:</b> {get_instagram_price()} credits each\n\n"
            f"<i>Click below to purchase more credits:</i>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Error in credit: {e}")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """History command - Show last 5 purchases"""
    try:
        user = update.effective_user
        
        # Load user's orders
        user_orders = []
        if os.path.exists(ORDERS_FILE):
            with open(ORDERS_FILE, 'r') as f:
                for line in f:
                    try:
                        order = json.loads(line.strip())
                        if str(order.get('user_id')) == str(user.id):
                            user_orders.append(order)
                    except:
                        pass
        
        if not user_orders:
            await update.message.reply_text(
                "📋 <b>No purchase history found!</b>\n\n"
                "Use /generate to buy your first number.",
                parse_mode='HTML'
            )
            return
        
        # Get last 5 orders
        recent_orders = sorted(user_orders, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
        
        history_msg = "📋 <b>Last 5 Purchases</b>\n\n"
        
        for i, order in enumerate(recent_orders, 1):
            status_emoji = "✅" if order.get('status') == 'completed' else "⏳"
            otp_info = f"\n🔑 OTP: <code>{order['otp']}</code>" if order.get('otp') else ""
            
            history_msg += (
                f"{status_emoji} <b>Order #{i}</b>\n"
                f"📱 Number: <code>{order['number']}</code>\n"
                f"💰 Cost: {order['price']} credits\n"
                f"📅 Date: {order['created_at'][:19]}{otp_info}\n"
                f"🆔 ID: <code>{order['order_id']}</code>\n"
                f"{'─' * 30}\n\n"
            )
        
        keyboard = [[InlineKeyboardButton("🔑 Generate New", callback_data="generate")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(history_msg, reply_markup=reply_markup, parse_mode='HTML')
    except Exception as e:
        print(f"Error in history: {e}")

async def admin_credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to add credits to users"""
    try:
        user = update.effective_user
        
        # Check if user is admin
        if user.id not in ADMIN_USER_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        # Parse command: /addcredit user_id amount
        args = context.args
        if len(args) != 2:
            await update.message.reply_text(
                "❌ <b>Usage:</b> /addcredit user_id amount\n\n"
                "Example: /addcredit 123456789 50",
                parse_mode='HTML'
            )
            return
        
        target_user_id = str(args[0])
        amount = float(args[1])
        
        # Get target user data
        users = load_json(USERS_FILE)
        if target_user_id not in users:
            await update.message.reply_text("❌ User not found in database. They need to /start the bot first.")
            return
        
        users[target_user_id]['credits'] += amount
        save_json(USERS_FILE, users)
        
        await update.message.reply_text(
            f"✅ <b>Credits Added Successfully!</b>\n\n"
            f"👤 User ID: <code>{target_user_id}</code>\n"
            f"💰 Amount: <b>{amount}</b> credits\n"
            f"📊 New Balance: <b>{users[target_user_id]['credits']}</b> credits",
            parse_mode='HTML'
        )
        
        # Notify target user
        try:
            await context.bot.send_message(
                chat_id=int(target_user_id),
                text=f"💰 <b>Credits Added!</b>\n\n"
                     f"Amount: <b>{amount}</b> credits\n"
                     f"New Balance: <b>{users[target_user_id]['credits']}</b> credits\n\n"
                     f"Use /generate to buy Instagram numbers!",
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Could not notify user: {e}")
            
    except Exception as e:
        print(f"Error in admin_credit: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button clicks"""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "generate":
            await query.message.reply_text("🔑 Use /generate command to purchase an Instagram number.")
        elif query.data == "check_credit":
            user_data, _ = get_user_data(query.from_user.id)
            await query.message.reply_text(
                f"💰 <b>Your Credits:</b> {user_data['credits']}\n\n"
                f"Use /credit for more details.",
                parse_mode='HTML'
            )
        elif query.data == "history":
            await history_command(update, context)
    except Exception as e:
        print(f"Error in button handler: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    print(f"Update {update} caused error {context.error}")

def main():
    """Main function to run the bot"""
    print("🤖 Starting Telegram Bot...")
    print(f"Python version: {sys.version}")
    
    try:
        # Create application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("generate", generate_command))
        application.add_handler(CommandHandler("credit", credit_command))
        application.add_handler(CommandHandler("history", history_command))
        application.add_handler(CommandHandler("addcredit", admin_credit_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_error_handler(error_handler)
        
        # Set bot commands
        async def set_commands(app):
            commands = [
                BotCommand("start", "Start the bot"),
                BotCommand("generate", "Buy Instagram number"),
                BotCommand("credit", "Check credits & purchase"),
                BotCommand("history", "View purchase history"),
                BotCommand("addcredit", "Admin: Add credits to user")
            ]
            await app.bot.set_my_commands(commands)
            print("✅ Bot commands configured!")
        
        # Run set_commands after initialization
        application.job_queue.run_once(lambda ctx: asyncio.create_task(set_commands(application)), 0)
        
        print("✅ Bot is starting...")
        
        # Start polling
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
