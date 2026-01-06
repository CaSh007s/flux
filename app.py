import os
from dotenv import load_dotenv
from google import genai # Using the new library
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Transaction, Goal, Subscription
from datetime import datetime, timedelta

# 1. Load Environment Variables
load_dotenv()

app = Flask(__name__)

# 2. Configure App
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 3. Configure AI
api_key = os.getenv('GOOGLE_API_KEY')
client = None

if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Error initializing AI: {e}")
else:
    print("WARNING: GOOGLE_API_KEY not found in .env")

# Initialize DB and Login Manager
db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- ROUTES ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists.')
            return redirect(url_for('signup'))
        
        new_user = User(username=username, password=generate_password_hash(password, method='scrypt'))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))
        
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check details.')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # 1. Fetch All Data
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    goals = Goal.query.filter_by(user_id=current_user.id).all()
    subscriptions = Subscription.query.filter_by(user_id=current_user.id).all()
    
    # 2. Basic Math
    total_income = sum(t.amount for t in transactions if t.type == 'income')
    total_expense = sum(t.amount for t in transactions if t.type == 'expense')
    balance = total_income - total_expense
    
    # 3. GHOST MODE
    today = datetime.now()
    first_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate previous month start/end
    last_month_end = first_this_month - timedelta(days=1)
    first_last_month = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Filter expenses
    this_month_expense = sum(t.amount for t in transactions 
                             if t.type == 'expense' and t.date >= first_this_month)
    
    last_month_expense = sum(t.amount for t in transactions 
                             if t.type == 'expense' and first_last_month <= t.date < first_this_month)
    
    # Calculate Delta 
    if last_month_expense > 0:
        delta = ((this_month_expense - last_month_expense) / last_month_expense) * 100
    else:
        delta = 100 if this_month_expense > 0 else 0
        
    # Format for UI
    delta = round(delta, 1)
    is_spending_up = delta > 0

    # 4. Subscription Burn Rate
    monthly_burn = 0
    for sub in subscriptions:
        if sub.billing_cycle == 'Monthly':
            monthly_burn += sub.amount
        elif sub.billing_cycle == 'Yearly':
            monthly_burn += (sub.amount / 12)
            
    # 5. Chart Data
    expense_by_category = {}
    for t in transactions:
        if t.type == 'expense':
            expense_by_category[t.category] = expense_by_category.get(t.category, 0) + t.amount
            
    chart_labels = list(expense_by_category.keys())
    chart_values = list(expense_by_category.values())
    
    return render_template('dashboard.html', 
                           name=current_user.username, 
                           transactions=transactions,
                           goals=goals,
                           subscriptions=subscriptions,
                           monthly_burn=monthly_burn,
                           balance=balance,
                           income=total_income,
                           expense=total_expense,
                           delta=delta,
                           is_spending_up=is_spending_up,
                           this_month_expense=this_month_expense,
                           chart_labels=chart_labels,
                           chart_values=chart_values)

@app.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction():
    try:
        amount = float(request.form.get('amount'))
        category = request.form.get('category')
        description = request.form.get('description')
        t_type = request.form.get('type')
        
        new_trans = Transaction(
            amount=amount,
            category=category,
            description=description,
            type=t_type,
            user_id=current_user.id
        )
        db.session.add(new_trans)
        db.session.commit()
        flash('Flow updated.')
        
    except ValueError:
        flash('Error: Invalid amount.')
        
    return redirect(url_for('dashboard'))

@app.route('/add_goal', methods=['POST'])
@login_required
def add_goal():
    name = request.form.get('name')
    target = float(request.form.get('target'))
    
    new_goal = Goal(name=name, target_amount=target, user_id=current_user.id)
    db.session.add(new_goal)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/add_funds/<int:goal_id>', methods=['POST'])
@login_required
def add_funds(goal_id):
    goal = db.session.get(Goal, goal_id)
    try:
        amount = float(request.form.get('amount'))
        
        if goal and goal.user_id == current_user.id:
            # 1. Add to Jar
            goal.current_amount += amount
            
            # 2. Deduct from Balance
            transfer_txn = Transaction(
                amount=amount,
                category='Savings',
                description=f'Transfer to {goal.name}',
                type='expense',
                user_id=current_user.id
            )
            
            db.session.add(transfer_txn)
            db.session.commit()
            flash(f'Moved ${amount} to {goal.name} jar.')
            
    except ValueError:
        flash('Invalid amount.')
        
    return redirect(url_for('dashboard'))

@app.route('/add_subscription', methods=['POST'])
@login_required
def add_subscription():
    name = request.form.get('name')
    amount = float(request.form.get('amount'))
    cycle = request.form.get('cycle')
    
    new_sub = Subscription(name=name, amount=amount, billing_cycle=cycle, user_id=current_user.id)
    db.session.add(new_sub)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/roast_me', methods=['GET'])
@login_required
def roast_me():
    # Safety Check
    if not client:
        return jsonify({'roast': "System Error: AI Brain not found. Check your .env file."})

    # 1. Gather User's Financial Shame
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    goals = Goal.query.filter_by(user_id=current_user.id).all()
    
    total_spent = sum(t.amount for t in transactions if t.type == 'expense')
    balance = sum(t.amount for t in transactions if t.type == 'income') - total_spent
    
    categories = {}
    for t in transactions:
        if t.type == 'expense':
            categories[t.category] = categories.get(t.category, 0) + t.amount
    top_category = max(categories, key=categories.get) if categories else "Nothing"
    
    # 2. Construct the Prompt
    prompt = f"""
    You are a rude, snarky financial advisor. 
    My stats:
    - Balance: ₹{balance}
    - Total Spent: ₹{total_spent}
    - Top Expense: {top_category} for ₹{categories.get(top_category, 0)}
    - Savings Jars: {len(goals)}
    
    Roast me in one short, brutal sentence.
    """
    
    try:
        # NEW CALL SYNTAX (google-genai)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return jsonify({'roast': response.text})
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({'roast': "I'm currently offline due to a budget cut. Try again later."})

# Create DB if not exists
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, port=5001)