from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime
from cryptography.fernet import Fernet
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()

# MongoDB connection
uri = "mongodb+srv://muhammednihal24ag039:l6ZrDiiOk3TY74aV@cluster0.pppmmcf.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri, server_api={'version': '1', 'strict': True, 'deprecation_errors': True})
db = client['chat_app']
messages_collection = db['messages']
signaling_collection = db['signaling']
users_collection = db['users']

# Encryption setup
key = Fernet.generate_key()
cipher = Fernet(key)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    username = data.get('username')
    message = data.get('message')
    
    # Encrypt the message
    encrypted_message = cipher.encrypt(message.encode()).decode()
    
    # Store message in MongoDB
    message_doc = {
        'username': username,
        'message': encrypted_message,
        'timestamp': datetime.utcnow(),
        'status': 'sent'
    }
    messages_collection.insert_one(message_doc)
    
    # Store for signaling (to notify peers)
    signaling_collection.insert_one({
        'type': 'message',
        'username': username,
        'message': message,  # Decrypted for signaling
        'timestamp': message_doc['timestamp'].isoformat(),
        'status': 'sent'
    })
    
    return jsonify({'status': 'success'})

@app.route('/signal', methods=['POST'])
def signal():
    data = request.json
    signaling_collection.insert_one({
        'type': data['type'],
        'sender': data['sender'],
        'recipient': data.get('recipient'),
        'data': data['data'],
        'timestamp': datetime.utcnow()
    })
    return jsonify({'status': 'success'})

@app.route('/get_signals/<username>', methods=['GET'])
def get_signals(username):
    signals = list(signaling_collection.find({'recipient': username}).sort('timestamp', -1).limit(50))
    signaling_collection.delete_many({'recipient': username})  # Clear signals after fetching
    return jsonify([{
        'type': s['type'],
        'sender': s['sender'],
        'data': s['data'],
        'timestamp': s['timestamp'].isoformat()
    } for s in signals])

@app.route('/get_messages', methods=['GET'])
def get_messages():
    messages = list(messages_collection.find().sort('timestamp', -1).limit(50))
    decrypted_messages = []
    
    for msg in messages:
        try:
            decrypted_message = cipher.decrypt(msg['message'].encode()).decode()
            decrypted_messages.append({
                'username': msg['username'],
                'message': decrypted_message,
                'timestamp': msg['timestamp'].isoformat(),
                'status': msg.get('status', 'sent')
            })
        except:
            continue
            
    return jsonify(decrypted_messages)

@app.route('/update_user', methods=['POST'])
def update_user():
    data = request.json
    username = data.get('username')
    status = data.get('status')
    
    users_collection.update_one(
        {'username': username},
        {'$set': {'status': status, 'last_seen': datetime.utcnow()}},
        upsert=True
    )
    return jsonify({'status': 'success'})

@app.route('/get_online_users', methods=['GET'])
def get_online_users():
    # Consider users active if last_seen is within the last 10 seconds
    active_users = list(users_collection.find({
        'status': 'online',
        'last_seen': {'$gte': datetime.utcnow() - timedelta(seconds=10)}
    }))
    return jsonify({'count': len(active_users), 'usernames': [u['username'] for u in active_users]})

if __name__ == '__main__':
    app.run(debug=True)