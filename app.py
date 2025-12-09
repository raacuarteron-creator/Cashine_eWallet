from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
from datetime import datetime

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Get secret key from environment or use fallback
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secure-key-' + os.urandom(32).hex()

# Configure PostgreSQL database
DATABASE_URL = os.environ.get('DATABASE_URL') or 'postgresql://cashine_ewallet_user:JFNT45Cuh64Uo8LpTuLJjybZQdoDpsn9@dpg-d4s24imuk2gs73a3nhl0-a/cashine_ewallet'

# Fix URL format
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
}

db = SQLAlchemy(app)

# Models
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
    transaction_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200))
    recipient_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        username = data.get('username')
        email = data.get('email')
        
        if not username or not email:
            return jsonify({'error': 'Username and email required'}), 400
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username exists'}), 400
        
        user = User(username=username, email=email)
        db.session.add(user)
        db.session.commit()
        
        session['user_id'] = user.id
        
        return jsonify({
            'message': 'Registered',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'balance': user.balance
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        session['user_id'] = user.id
        
        return jsonify({
            'message': 'Logged in',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'balance': user.balance
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out'})

@app.route('/api/current-user')
def current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'balance': user.balance
    })

@app.route('/api/deposit', methods=['POST'])
def deposit():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.get_json()
        amount = float(data.get('amount', 0))
        
        if amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        
        user = User.query.get(user_id)
        user.balance += amount
        
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type='deposit',
            description='Deposit'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'message': 'Deposited',
            'balance': user.balance
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.get_json()
        amount = float(data.get('amount', 0))
        
        if amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        
        user = User.query.get(user_id)
        if user.balance < amount:
            return jsonify({'error': 'Insufficient balance'}), 400
        
        user.balance -= amount
        
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type='withdrawal',
            description='Withdrawal'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'message': 'Withdrawn',
            'balance': user.balance
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/transfer', methods=['POST'])
def transfer():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.get_json()
        amount = float(data.get('amount', 0))
        recipient_username = data.get('recipient_username')
        
        if amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        
        if not recipient_username:
            return jsonify({'error': 'Recipient required'}), 400
        
        sender = User.query.get(user_id)
        recipient = User.query.filter_by(username=recipient_username).first()
        
        if not recipient:
            return jsonify({'error': 'Recipient not found'}), 404
        
        if sender.id == recipient.id:
            return jsonify({'error': 'Cannot transfer to self'}), 400
        
        if sender.balance < amount:
            return jsonify({'error': 'Insufficient balance'}), 400
        
        sender.balance -= amount
        recipient.balance += amount
        
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type='transfer',
            description=f'Transfer to {recipient.username}'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'message': 'Transferred',
            'balance': sender.balance
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions')
def transactions():
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
def users():
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
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat()
    })

# Initialize database - FIXED for Flask 2.3+
with app.app_context():
    try:
        db.create_all()
        # Create demo user if none exists
        if not User.query.filter_by(username='demo').first():
            user = User(username='demo', email='demo@example.com', balance=1000.0)
            db.session.add(user)
            db.session.commit()
            print("Demo user created with $1000 balance")
    except Exception as e:
        print(f"Database initialization error: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
