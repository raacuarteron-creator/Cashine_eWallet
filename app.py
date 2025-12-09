from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
from datetime import datetime
import sys

app = Flask(__name__)
CORS(app)

# Get secret key from environment or use fallback
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secure-key-' + os.urandom(32).hex()

# Configure PostgreSQL database
database_url = os.environ.get('DATABASE_URL') or 'postgresql://cashine_ewallet_user:JFNT45Cuh64Uo8LpTuLJjybZQdoDpsn9@dpg-d4s24imuk2gs73a3nhl0-a/cashine_ewallet'

# Fix URL format for SQLAlchemy
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Add connection pool options for Render
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
}

db = SQLAlchemy(app)

# Models for eWallet
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'balance': self.balance,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdrawal, transfer
    description = db.Column(db.String(200))
    recipient_id = db.Column(db.Integer, nullable=True)  # for transfers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'type': self.transaction_type,
            'description': self.description,
            'date': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }

# Serve the single HTML file
@app.route('/')
def home():
    return render_template('index.html')

# API Routes
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
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({'error': 'Username already exists'}), 400
        
        new_user = User(username=username, email=email)
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        
        return jsonify({
            'message': 'Registration successful',
            'user': new_user.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        username = data.get('username')
        
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        session['user_id'] = user.id
        
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/current-user')
def get_current_user():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        return jsonify(user.to_dict())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deposit', methods=['POST'])
def deposit():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        amount = data.get('amount')
        
        if not amount or float(amount) <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        
        user = User.query.get(user_id)
        user.balance += float(amount)
        
        transaction = Transaction(
            user_id=user_id,
            amount=float(amount),
            transaction_type='deposit',
            description='Deposit to account'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'message': 'Deposit successful',
            'new_balance': user.balance
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
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        amount = data.get('amount')
        
        if not amount or float(amount) <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        
        user = User.query.get(user_id)
        
        if user.balance < float(amount):
            return jsonify({'error': 'Insufficient balance'}), 400
        
        user.balance -= float(amount)
        
        transaction = Transaction(
            user_id=user_id,
            amount=float(amount),
            transaction_type='withdrawal',
            description='Withdrawal from account'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'message': 'Withdrawal successful',
            'new_balance': user.balance
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
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        amount = data.get('amount')
        recipient_username = data.get('recipient_username')
        description = data.get('description', '')
        
        if not amount or float(amount) <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        
        if not recipient_username:
            return jsonify({'error': 'Recipient username required'}), 400
        
        sender = User.query.get(user_id)
        recipient = User.query.filter_by(username=recipient_username).first()
        
        if not recipient:
            return jsonify({'error': 'Recipient not found'}), 404
        
        if sender.id == recipient.id:
            return jsonify({'error': 'Cannot transfer to yourself'}), 400
        
        if sender.balance < float(amount):
            return jsonify({'error': 'Insufficient balance'}), 400
        
        # Perform transfer
        sender.balance -= float(amount)
        recipient.balance += float(amount)
        
        # Create transactions for both users
        sender_transaction = Transaction(
            user_id=sender.id,
            amount=float(amount),
            transaction_type='transfer',
            description=f'Transfer to {recipient.username}: {description}',
            recipient_id=recipient.id
        )
        
        recipient_transaction = Transaction(
            user_id=recipient.id,
            amount=float(amount),
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
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions')
def get_transactions():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401
        
        transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).limit(20).all()
        
        return jsonify([t.to_dict() for t in transactions])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users')
def get_users():
    try:
        users = User.query.all()
        return jsonify([{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'balance': u.balance
        } for u in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Initialize database tables
def init_database():
    try:
        with app.app_context():
            print("Creating database tables...")
            db.create_all()
            print("Database tables created successfully!")
            
            # Create demo user if none exists
            if not User.query.filter_by(username='demo').first():
                print("Creating demo user...")
                demo_user = User(username='demo', email='demo@example.com', balance=1000.0)
                db.session.add(demo_user)
                db.session.commit()
                print("Demo user created with $1000 balance")
                
    except Exception as e:
        print(f"Error initializing database: {e}")

# Run database initialization when app starts
init_database()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting Flask app on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
