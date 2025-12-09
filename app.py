from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secret-key-' + os.urandom(24).hex()

# Configure PostgreSQL database with your Render URL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://cashine_ewallet_user:JFNT45Cuh64Uo8LpTuLJjybZQdoDpsn9@dpg-d4s24imuk2gs73a3nhl0-a/cashine_ewallet'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models for eWallet
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdrawal, transfer
    description = db.Column(db.String(200))
    recipient_id = db.Column(db.Integer, nullable=True)  # for transfers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))

# Serve the single HTML file
@app.route('/')
def home():
    return render_template('index.html')

# API Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    
    if not username or not email:
        return jsonify({'error': 'Username and email required'}), 400
    
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'error': 'Username already exists'}), 400
    
    new_user = User(username=username, email=email)
    db.session.add(new_user)
    db.session.commit()
    
    session['user_id'] = new_user.id
    
    return jsonify({
        'message': 'Registration successful',
        'user': {
            'id': new_user.id,
            'username': new_user.username,
            'email': new_user.email,
            'balance': new_user.balance
        }
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    session['user_id'] = user.id
    
    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'balance': user.balance
        }
    })

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/current-user')
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = User.query.get(user_id)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'balance': user.balance
    })

@app.route('/api/deposit', methods=['POST'])
def deposit():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    amount = data.get('amount')
    
    if not amount or amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    
    user = User.query.get(user_id)
    user.balance += amount
    
    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        transaction_type='deposit',
        description='Deposit to account'
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'message': 'Deposit successful',
        'new_balance': user.balance
    })

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    amount = data.get('amount')
    
    if not amount or amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    
    user = User.query.get(user_id)
    
    if user.balance < amount:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    user.balance -= amount
    
    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        transaction_type='withdrawal',
        description='Withdrawal from account'
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'message': 'Withdrawal successful',
        'new_balance': user.balance
    })

@app.route('/api/transfer', methods=['POST'])
def transfer():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    amount = data.get('amount')
    recipient_username = data.get('recipient_username')
    description = data.get('description', '')
    
    if not amount or amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    
    if not recipient_username:
        return jsonify({'error': 'Recipient username required'}), 400
    
    sender = User.query.get(user_id)
    recipient = User.query.filter_by(username=recipient_username).first()
    
    if not recipient:
        return jsonify({'error': 'Recipient not found'}), 404
    
    if sender.id == recipient.id:
        return jsonify({'error': 'Cannot transfer to yourself'}), 400
    
    if sender.balance < amount:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Perform transfer
    sender.balance -= amount
    recipient.balance += amount
    
    # Create transactions for both users
    sender_transaction = Transaction(
        user_id=sender.id,
        amount=amount,
        transaction_type='transfer',
        description=f'Transfer to {recipient.username}: {description}',
        recipient_id=recipient.id
    )
    
    recipient_transaction = Transaction(
        user_id=recipient.id,
        amount=amount,
        transaction_type='transfer',
        description=f'Transfer from {sender.username}: {description}',
        recipient_id=sender.id
    )
    
    db.session.add(sender_transaction)
    db.session.add(recipient_transaction)
    db.session.commit()
    
    return jsonify({
        'message': 'Transfer successful',
        'new_balance': sender.balance
    })

@app.route('/api/transactions')
def get_transactions():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).limit(20).all()
    
    return jsonify([{
        'id': t.id,
        'amount': t.amount,
        'type': t.transaction_type,
        'description': t.description,
        'date': t.created_at.strftime('%Y-%m-%d %H:%M')
    } for t in transactions])

@app.route('/api/users')
def get_users():
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'balance': u.balance
    } for u in users])

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'database': 'connected',
        'timestamp': datetime.utcnow().isoformat()
    })

# Initialize database
@app.before_first_request
def create_tables():
    db.create_all()
    # Create a demo user if none exists
    if not User.query.filter_by(username='demo').first():
        demo_user = User(username='demo', email='demo@example.com', balance=1000.0)
        db.session.add(demo_user)
        db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
