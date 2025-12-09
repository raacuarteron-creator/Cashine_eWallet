from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import re

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["https://your-app.onrender.com", "http://localhost:3000"])

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
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    birthdate = db.Column(db.Date)
    address = db.Column(db.Text)
    wallet_id = db.Column(db.String(20), unique=True, nullable=False)
    pin_hash = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=500.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    fee = db.Column(db.Float, default=0.0)
    note = db.Column(db.Text)
    recipient_id = db.Column(db.Integer, nullable=True)
    recipient_name = db.Column(db.String(100))
    bank_details = db.Column(db.JSON, nullable=True)
    cashout_method = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Helper function for fee calculation
def calculate_fee_percent(amount):
    """Calculate 5% fee with a minimum of ₱5."""
    fee = amount * 0.05
    return max(fee, 5.0)

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        birthdate = data.get('birthdate')
        address = data.get('address')
        pin = data.get('pin')
        
        if not all([name, email, phone, pin]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400
        
        if len(pin) != 4:
            return jsonify({'success': False, 'error': 'PIN must be 4 digits'}), 400
        
        # Validate email
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({'success': False, 'error': 'Invalid email format'}), 400
        
        # Check if email or phone exists
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email already registered'}), 400
        
        if User.query.filter_by(phone=phone).first():
            return jsonify({'success': False, 'error': 'Phone number already registered'}), 400
        
        # Generate wallet ID
        wallet_id = f"CASH{datetime.now().strftime('%y%m%d')}{db.session.query(User).count() + 10000}"
        
        # Create user
        user = User(
            name=name,
            email=email,
            phone=phone,
            birthdate=datetime.strptime(birthdate, '%Y-%m-%d') if birthdate else None,
            address=address,
            wallet_id=wallet_id,
            pin_hash=generate_password_hash(pin),
            balance=500.0
        )
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Account created successfully',
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'wallet_id': user.wallet_id,
                'balance': user.balance
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        identifier = data.get('identifier')  # Can be email, phone, or wallet_id
        pin = data.get('pin')
        
        if not identifier or not pin:
            return jsonify({'success': False, 'error': 'Identifier and PIN required'}), 400
        
        # Find user by email, phone, or wallet_id
        user = User.query.filter(
            (User.email == identifier) | 
            (User.phone == identifier) | 
            (User.wallet_id == identifier)
        ).first()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        if not check_password_hash(user.pin_hash, pin):
            return jsonify({'success': False, 'error': 'Invalid PIN'}), 401
        
        # Set session
        session['user_id'] = user.id
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'wallet_id': user.wallet_id,
                'balance': user.balance,
                'address': user.address,
                'birthdate': user.birthdate.strftime('%Y-%m-%d') if user.birthdate else None
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'success': True, 'message': 'Logged out'})

@app.route('/api/current-user', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'phone': user.phone,
            'wallet_id': user.wallet_id,
            'balance': user.balance,
            'address': user.address,
            'birthdate': user.birthdate.strftime('%Y-%m-%d') if user.birthdate else None
        }
    })

@app.route('/api/send-money', methods=['POST'])
def send_money():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        recipient_identifier = data.get('to')
        amount = float(data.get('amount', 0))
        purpose = data.get('purpose', 'Money Transfer')
        pin = data.get('pin')
        
        # Validations
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        # Get sender
        sender = User.query.get(user_id)
        if not check_password_hash(sender.pin_hash, pin):
            return jsonify({'success': False, 'error': 'Invalid PIN'}), 401
        
        # Find recipient
        recipient = User.query.filter(
            (User.wallet_id == recipient_identifier) | 
            (User.phone == recipient_identifier)
        ).first()
        
        if not recipient:
            return jsonify({'success': False, 'error': 'Recipient not found'}), 404
        
        if recipient.id == sender.id:
            return jsonify({'success': False, 'error': 'Cannot send money to yourself'}), 400
        
        # Calculate fee (5% with minimum ₱5)
        fee = calculate_fee_percent(amount)
        total_deduction = amount + fee
        
        if sender.balance < total_deduction:
            return jsonify({'success': False, 'error': 'Insufficient balance'}), 400
        
        # Update balances
        sender.balance -= total_deduction
        recipient.balance += amount
        
        # Create transactions
        sender_transaction = Transaction(
            user_id=sender.id,
            type='Sent',
            amount=-amount,
            fee=-fee,
            note=f'To {recipient.name} ({purpose})',
            recipient_id=recipient.id,
            recipient_name=recipient.name
        )
        
        recipient_transaction = Transaction(
            user_id=recipient.id,
            type='Received',
            amount=amount,
            fee=0,
            note=f'From {sender.name} ({purpose})',
            recipient_id=sender.id,
            recipient_name=sender.name
        )
        
        db.session.add(sender_transaction)
        db.session.add(recipient_transaction)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Money sent successfully to {recipient.name}',
            'new_balance': sender.balance,
            'fee': fee
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/bank-transfer', methods=['POST'])
def bank_transfer():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        bank = data.get('bank')
        account = data.get('account')
        account_name = data.get('account_name')
        amount = float(data.get('amount', 0))
        pin = data.get('pin')
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        user = User.query.get(user_id)
        if not check_password_hash(user.pin_hash, pin):
            return jsonify({'success': False, 'error': 'Invalid PIN'}), 401
        
        fee = 25.0  # Flat fee for bank transfer
        total_deduction = amount + fee
        
        if user.balance < total_deduction:
            return jsonify({'success': False, 'error': 'Insufficient balance'}), 400
        
        user.balance -= total_deduction
        
        transaction = Transaction(
            user_id=user.id,
            type='Bank Transfer',
            amount=-amount,
            fee=-fee,
            note=f'To {bank} - {account_name}',
            bank_details={
                'bank': bank,
                'account': account,
                'account_name': account_name
            }
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Bank transfer initiated',
            'new_balance': user.balance
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cash-out', methods=['POST'])
def cash_out():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        amount = float(data.get('amount', 0))
        method = data.get('method')
        pin = data.get('pin')
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        user = User.query.get(user_id)
        if not check_password_hash(user.pin_hash, pin):
            return jsonify({'success': False, 'error': 'Invalid PIN'}), 401
        
        # Calculate fee (5% with minimum ₱5)
        fee = calculate_fee_percent(amount)
        total_deduction = amount + fee
        
        if user.balance < total_deduction:
            return jsonify({'success': False, 'error': 'Insufficient balance'}), 400
        
        user.balance -= total_deduction
        
        transaction = Transaction(
            user_id=user.id,
            type='Cash Out',
            amount=-amount,
            fee=-fee,
            note=f'Via {method}',
            cashout_method=method
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Cash out request submitted via {method}',
            'new_balance': user.balance,
            'fee': fee,
            'you_receive': amount
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).limit(50).all()
    
    return jsonify({
        'success': True,
        'transactions': [{
            'id': t.id,
            'type': t.type,
            'amount': t.amount,
            'fee': t.fee,
            'note': t.note,
            'recipient_name': t.recipient_name,
            'bank_details': t.bank_details,
            'cashout_method': t.cashout_method,
            'date': t.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for t in transactions]
    })

@app.route('/api/calculate-fee', methods=['POST'])
def calculate_fee():
    data = request.get_json()
    amount = float(data.get('amount', 0))
    transaction_type = data.get('type', 'send')  # send, cashout, bank
    
    if amount <= 0:
        return jsonify({'success': False, 'error': 'Invalid amount'}), 400
    
    if transaction_type == 'bank':
        fee = 25.0
    else:
        fee = calculate_fee_percent(amount)
    
    return jsonify({
        'success': True,
        'amount': amount,
        'fee': fee,
        'total': amount + fee
    })

@app.route('/api/users/search', methods=['POST'])
def search_users():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': True, 'users': []})
        
        users = User.query.filter(
            (User.wallet_id.ilike(f'%{query}%')) |
            (User.phone.ilike(f'%{query}%')) |
            (User.name.ilike(f'%{query}%'))
        ).limit(10).all()
        
        return jsonify({
            'success': True,
            'users': [{
                'wallet_id': u.wallet_id,
                'name': u.name,
                'phone': u.phone
            } for u in users]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'Cashine eWallet',
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'connected' if db.session.execute('SELECT 1').first() else 'disconnected'
    })

# Initialize database
with app.app_context():
    try:
        db.create_all()
        print("Database tables created successfully")
        
        # Create admin user if none exists
        if not User.query.filter_by(email='admin@cashine.com').first():
            admin = User(
                name='Admin User',
                email='admin@cashine.com',
                phone='+639123456789',
                wallet_id='CASH00000001',
                pin_hash=generate_password_hash('1234'),
                balance=10000.0
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created")
            
    except Exception as e:
        print(f"Database initialization error: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
