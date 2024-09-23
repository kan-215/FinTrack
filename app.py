from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import os

# Initialize the Flask app
app = Flask(__name__)

# App configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER')  # Your email address
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS')  # Your email password

# Initialize extensions
db = SQLAlchemy(app)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# Models
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

# Create all tables if they don't exist
with app.app_context():
    db.create_all()

# Send confirmation email with password reset token
def send_password_reset_email(user):
    token = serializer.dumps(user.email, salt='password-reset-salt')
    reset_link = url_for('change_password_with_token', token=token, _external=True)
    
    msg = Message('Password Reset Request', 
                  sender=app.config['MAIL_USERNAME'], 
                  recipients=[user.email])
    msg.body = f'Click the link to reset your password: {reset_link}'
    mail.send(msg)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "danger")
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash("Email already exists!", "danger")
            return redirect(url_for('register'))
        
        new_user = User(username=username, password_hash=generate_password_hash(password), email=email)
        db.session.add(new_user)
        db.session.commit()
        flash("Account created successfully!", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        user_id = session['user_id']
        
        # Fetch all transactions for the current user
        transactions = Transaction.query.filter_by(user_id=user_id).all()

        # Calculate total income and total expenses
        total_income = sum(t.amount for t in transactions if t.transaction_type == 'income')
        total_expenses = sum(t.amount for t in transactions if t.transaction_type == 'expense')

        # Calculate available balance
        available_balance = total_income - total_expenses

        return render_template(
            'dashboard.html',
            transactions=transactions,
            total_income=total_income,
            total_expenses=total_expenses,
            available_balance=available_balance
        )
    return redirect(url_for('login'))

@app.route('/transactions')
def transactions():
    if 'user_id' in session:
        user_id = session['user_id']
        transactions = Transaction.query.filter_by(user_id=user_id).all()
        return render_template('transactions.html', transactions=transactions)
    return redirect(url_for('login'))

@app.route('/add_transaction', methods=['GET', 'POST'])
def add_transaction():
    if 'user_id' in session:
        if request.method == 'POST':
            amounts = request.form.getlist('amount')
            descriptions = request.form.getlist('description')
            transaction_types = request.form.getlist('transaction_type')
            dates = request.form.getlist('date')

            if not amounts or not descriptions or not transaction_types or not dates:
                flash("All fields are required.", "danger")
                return redirect(url_for('add_transaction'))

            for amount, description, transaction_type, date in zip(amounts, descriptions, transaction_types, dates):
                new_transaction = Transaction(
                    amount=float(amount),
                    description=description,
                    transaction_type=transaction_type,
                    date=datetime.strptime(date, '%Y-%m-%d'),
                    user_id=session['user_id']
                )
                db.session.add(new_transaction)

            db.session.commit()
            flash("Transactions added successfully.", "success")
            return redirect(url_for('transactions'))

        return render_template('add_transaction.html')
    return redirect(url_for('login'))

@app.route('/expenses')
def expenses():
    if 'user_id' in session:
        user_id = session['user_id']
        transactions = Transaction.query.filter_by(user_id=user_id, transaction_type='expense').all()
        return render_template('expenses.html', transactions=transactions)
    return redirect(url_for('login'))

@app.route('/income')
def income():
    if 'user_id' in session:
        user_id = session['user_id']
        transactions = Transaction.query.filter_by(user_id=user_id, transaction_type='income').all()
        return render_template('income.html', transactions=transactions)
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if request.method == 'POST':
            if 'username' in request.form and request.form['username']:
                user.username = request.form['username']
                db.session.commit()
                flash("Username updated successfully.", "success")

            if 'current_password' in request.form and 'new_password' in request.form:
                if check_password_hash(user.password_hash, request.form['current_password']):
                    user.password_hash = generate_password_hash(request.form['new_password'])
                    db.session.commit()
                    flash("Password changed successfully.", "success")
                else:
                    flash("Current password is incorrect.", "danger")

            if 'email' in request.form and request.form['email']:
                user.email = request.form['email']
                db.session.commit()
                flash("Email updated successfully.", "success")
                
        return render_template('account.html', user=user)
    return redirect(url_for('login'))

@app.route('/edit_transaction/<int:transaction_id>', methods=['GET', 'POST'])
def edit_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    transaction = Transaction.query.get_or_404(transaction_id)

    if request.method == 'POST':
        transaction.amount = request.form['amount']
        transaction.description = request.form['description']
        transaction.transaction_type = request.form['transaction_type']
        transaction.date = datetime.strptime(request.form['date'], '%Y-%m-%d')

        db.session.commit()
        flash("Transaction updated successfully.", "success")
        return redirect(url_for('transactions'))

    return render_template('edit_transaction.html', transaction=transaction)

@app.route('/delete_transaction/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    if 'user_id' in session:
        transaction = Transaction.query.get_or_404(transaction_id)
        db.session.delete(transaction)
        db.session.commit()
        flash("Transaction deleted successfully.", "success")
    return redirect(url_for('transactions'))

# Password Reset Routes
@app.route('/request_password_change', methods=['POST'])
def request_password_change():
    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()
    
    if user:
        send_password_reset_email(user)
        flash('A password reset link has been sent to your email.', 'success')
    else:
        flash('Email not found.', 'danger')
    
    return redirect(url_for('login'))

@app.route('/change_password/<token>', methods=['GET', 'POST'])
def change_password_with_token(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception as e:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()
    if request.method == 'POST':
        new_password = request.form['new_password']
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash('Your password has been changed!', 'success')
        return redirect(url_for('login'))

    return render_template('change_password.html', token=token)

if __name__ == '__main__':
    app.run(debug=True, port = 8000)
