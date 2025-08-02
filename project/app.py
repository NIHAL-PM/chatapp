from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import os
from flask_cors import CORS

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
CORS(app)  # Enable CORS for API routes

# MongoDB connection
try:
    uri = os.environ.get('MONGODB_URI')
    if not uri:
        raise ValueError("MONGODB_URI environment variable not set")
    client = MongoClient(uri, server_api={'version': '1', 'strict': True, 'deprecation_errors': True})
    db = client['chat_app']
    messages_collection = db['messages']
    signaling_collection = db['signaling']
    users_collection = db['users']
    client.admin.command('ping')  # Test MongoDB connection
except Exception as e:
    print(f"MongoDB connection failed: {str(e)}")
    raise

# Encryption setup
try:
    key = os.environ.get('ENCRYPTION_KEY', Fernet.generate_key())
    cipher = Fernet(key)
except Exception as e:
    print(f"Encryption setup failed: {str(e)}")
    raise

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error rendering index: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Failed to load index page'}), 500

@app.route('/api/health', methods=['GET'])
def health():
    try:
        client.admin.command('ping')
        return jsonify({'status': 'success', 'message': 'Server and MongoDB are healthy'})
    except Exception as e:
        print(f"Health check failed: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/send_message', methods=['POST'])
def send_message():
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid JSON payload'}), 400
        username = data.get('username')
        message = data.get('message')
        
        if not username or not message:
            return jsonify({'status': 'error', 'message': 'Username and message required'}), 400
        
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
        
        # Store for signaling
        signaling_collection.insert_one({
            'type': 'message',
            'username': username,
            'message': message,
            'timestamp': message_doc['timestamp'].isoformat(),
            'status': 'sent'
        })
        
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error in send_message: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/signal', methods=['POST'])
def signal():
    try:
        data = request.json
        if not data or not data.get('type') or not data.get('sender'):
            return jsonify({'status': 'error', 'message': 'Type and sender required'}), 400
        
        signaling_collection.insert_one({
            'type': data['type'],
            'sender': data['sender'],
            'recipient': data.get('recipient'),
            'data': data['data'],
            'timestamp': datetime.utcnow()
        })
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error in signal: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get_signals/<username>', methods=['GET'])
def get_signals(username):
    try:
        if not username:
            return jsonify({'status': 'error', 'message': 'Username required'}), 400
        signals = list(signaling_collection.find({'recipient': username}).sort('timestamp', -1).limit(50))
        signaling_collection.delete_many({'recipient': username})
        return jsonify([{
            'type': s['type'],
            'sender': s['sender'],
            'data': s['data'],
            'timestamp': s['timestamp'].isoformat()
        } for s in signals])
    except Exception as e:
        print(f"Error in get_signals: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get_messages', methods=['GET'])
def get_messages():
    try:
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
    except Exception as e:
        print(f"Error in get_messages: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/update_user', methods=['POST'])
def update_user():
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid JSON payload'}), 400
        username = data.get('username')
        status = data.get('status')
        
        if not username or not status:
            return jsonify({'status': 'error', 'message': 'Username and status required'}), 400
        
        users_collection.update_one(
            {'username': username},
            {'$set': {'status': status, 'last_seen': datetime.utcnow()}},
            upsert=True
        )
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error in update_user: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get_online_users', methods=['GET'])
def get_online_users():
    try:
        active_users = list(users_collection.find({
            'status': 'online',
            'last_seen': {'$gte': datetime.utcnow() - timedelta(seconds=10)}
        }))
        return jsonify({'count': len(active_users), 'usernames': [u['username'] for u in active_users]})
    except Exception as e:
        print(f"Error in get_online_users: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
