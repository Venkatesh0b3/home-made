from flask import Flask, render_template_string, render_template , redirect, url_for, session, request, flash, jsonify
from functools import wraps
import smtplib
import logging
from email.mime.text import MIMEText
from datetime import datetime
from werkzeug.exceptions import BadRequest
from werkzeug.security import generate_password_hash, check_password_hash
import os
import boto3
import uuid


# -------------------- Config --------------------

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# AWS configuration
region = 'ap-south-1'  # Change if needed
DYNAMODB_TABLE = 'PickleOrders'

# Email settings
EMAIL_HOST = 'smtp.@gmail.com'
EMAIL_PORT = 587
EMAIL_USER = '@gmail.com'
EMAIL_PASSWORD = ""


# -------------------- Logger Setup --------------------

log_folder = 'logs'
log_file = os.path.join(log_folder, 'app.log')

if os.path.exists(log_folder):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
else:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger(__name__)

# -------------------- AWS Setup --------------------

dynamodb = boto3.resource('dynamodb', region_name=region)
orders_table = dynamodb.Table(DYNAMODB_TABLE)
users_table = dynamodb.Table('users')

# SNS Setup

sns = boto3.client('sns', region_name=region)

# -------------------- Helper Functions --------------------

def send_order_email(to_email, order_summary):
    try:
        msg = MIMEText(order_summary)
        msg['Subject'] = 'Your Order Confirmation'
        msg['From'] = EMAIL_USER
        msg['To'] = to_email

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)

        logger.info("Order email sent to %s", to_email)
    except Exception as e:
        logger.error("Failed to send email: %s", e)
def save_order_to_dynamodb(order_data):
    try:
        orders_table.put_item(Item=order_data)
        logger.info("Order saved to DynamoDB: %s", order_data['order_id'])
    except Exception as e:
        logger.error("DynamoDB error: %s", e)

def send_sns_notification(message, phone_number=None, topic_arn=None):
    try:
        if phone_number:
            sns.publish(PhoneNumber=phone_number, Message=message)
            logger.info(f"SNS SMS sent to {phone_number}")
        elif topic_arn:
            sns.publish(TopicArn=topic_arn, Message=message)
            logger.info(f"SNS message published to topic {topic_arn}")
        else:
            logger.info("SNS notification skipped (no phone number or topic)")
    except Exception as e:
        logger.error("SNS send failed: %s", e)

# DynamoDB tables
contacts_table = dynamodb.Table('contacts')
reviews_table = dynamodb.Table('reviews')

 # Simple in-memory user storage
users = {}

# Store reviews and contacts in files
REVIEWS_FILE = 'reviews.txt'
CONTACTS_FILE = 'contacts.txt'

# Product List with Online Image URLs
products = [
    # Non-Veg Pickles
    {
        "id": 1,
        "name": "chicken pickle",
        "price": 350,
        "image": "https://i0.wp.com/ahahomefoods.com/wp-content/uploads/2024/06/chicken-pickle-with-bone.jpeg?fit=2491%2C2560&ssl=1",
        "description": "We sell authentic , Spicy, Meaty pickles . We are known for our soul melting taste and high quality and organic ingredients"
    },
    {
        "id": 2,
        "name": "Gongura Mutton Pickle",
        "price": 320,
        "image": "https://andhrapachallu.com/cdn/shop/files/Image-50-scaled.png?v=1721547061",
        "description": "Similar to the chicken version, this pickle combines mutton with gongura."
    },
    {
        "id": 3,
        "name": "Boti Pickle",
        "price": 400,
        "image": "https://chefsarufoods.com/wp-content/uploads/2024/10/gongura-boti-product-image-scaled.jpg",
        "description": "newly introduced pickle made with boti (tripe)."
    },
    {
        "id": 4,
        "name": "Fish Pickle",
        "price": 380,
        "image": "https://5.imimg.com/data5/ANDROID/Default/2022/1/ZG/CF/RB/145196166/product-jpeg-500x500.jpg",
        "description": "Juicy fish pieces."
    },

    # Veg Pickles
    {
        "id": 5,
        "name": "Mango Pickle",
        "price": 280,
        "image": "https://i0.wp.com/binjalsvegkitchen.com/wp-content/uploads/2024/04/Instant-Mango-Pickle-H1.jpg?resize=600%2C900&ssl=1",
        "description": "A classic Andhra-style pickle made with raw mangoes, mustard seeds, and spices."
    },
    {
        "id": 6,
        "name": "Mixed Veg Pickle",
        "price": 280,
        "image": "https://s3-ap-south-1.amazonaws.com/betterbutterbucket-silver/divya-r20180620215346113.jpeg",
        "description": "Carrot, cauliflower, lime and mango combo"
    },
    {
        "id": 7,
        "name": "Tomato Pickle",
        "price": 250,
        "image": "https://www.indianhealthyrecipes.com/wp-content/uploads/2020/06/tomato-pickle-recipe.jpg",
        "description": "Ripe tomatoes with a blend of spices"
    },
    {
        "id": 8,
        "name": "Gongura Pickle",
        "price": 220,
        "image": "https://vellankifoods.com/cdn/shop/products/gongura_pickle_2.jpg?v=1680180278",
        "description": "Tangy sorrel leaves with special spice"
    },

    # Snacks
    {
        "id": 9,
        "name": "Madras Mixture",
        "price": 230,
        "image": "https://masalamonk.com/wp-content/uploads/2025/02/Unusual-Indian-Pickles.jpg",
        "description": "A spicy and crunchy snack mix from South India."
    },
    {
        "id": 10,
        "name": "Murkku chakki",
        "price": 300,
        "image": "https://5.imimg.com/data5/SELLER/Default/2025/3/497746042/ZR/YQ/CF/67465829/muruk-condiments-500x500.pn",
        "description": "Roasted murkku with delicious taste"
    },
    {
        "id": 11,
        "name": "Net Based Snacks",
        "price": 220,
        "image": "https://girijapaati.com/cdn/shop/collections/enh_classicribbon.jpg?v=1691556230",
        "description": "Tasty GirijaPaati"
    },
    {
        "id": 12,
        "name": "Bombay Mixture",
        "price": 150,
        "image": "https://karaikaliyangars.com/cdn/shop/products/BombayMixture.jpg?v=1628014057",
        "description": "Crunchy Bombay Mixture"
    }
]

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


# Contact Page
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        with open(CONTACTS_FILE, 'a') as f:
            f.write(f"{name} ({email}): {message}\n")
        flash("Thank you for contacting us!", "success")
        return redirect(url_for('contact'))
    try:
        with open(CONTACTS_FILE, 'r') as f:
            contacts = f.readlines()
    except FileNotFoundError:
        contacts = []

    return render_template_string("""
    <body style="background-image: url('{{ url_for('static', filename='images/bg-new.jpg') }}');
             background-size: contain;
             background-position: top center;
             background-repeat: no-repeat;
             font-family: 'Open Sans', sans-serif;
             padding: 40px 20px;">
    <h2 style="color:#2c3e50;">Contact Us</h2>
    <form method="POST">
        Name: <input type="text" name="name" required><br><br>
        Email: <input type="email" name="email" required><br><br>
        Message: <br><textarea name="message" rows="5" cols="40" required></textarea><br><br>
        <button type="submit">Send</button>
    </form>
    <ul style="list-style:none;">                              
     {% for line in contacts %}
    <li  style="margin-bottom:25px; padding:10px; background:#fff; border-radius:10px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);">{{ line }}</li>
    {% endfor %}
    </ul>

    <a href="{{ url_for('products_page') }}">⬅ Back to Products</a>
    """,contacts=contacts)

# Reviews Page
@app.route('/reviews', methods=['GET', 'POST'])
def product_reviews():
    if request.method == 'POST':
        user = session.get('username', 'Guest')
        review = request.form['review']
        reviews_table.put_item(Item={
            'id': str(uuid.uuid4()),
            'user': user,
            'review': review
         })
        with open(REVIEWS_FILE, 'a') as f:
            f.write(f"{user}: {review}\n")
        flash("Thanks for your review!", "success")
        return redirect(url_for('product_reviews'))
   # DynamoDB doesn't support scan() without provisioned throughput in free tier well
    reviews = []
    try:
        response = reviews_table.scan()
        reviews = [item['user'] + ': ' + item['review'] for item in response.get('Items', [])]
    except Exception as e:
        reviews = ["Error fetching reviews: " + str(e)]


    return render_template_string("""
    <body style="background-image: url('{{ url_for('static', filename='images/bg-new.jpg') }}');
             background-size: contain;
             background-position: top center;
             background-repeat: no-repeat;
             font-family: 'Open Sans', sans-serif;
             padding: 40px 20px;">
    <h2 style="color:#2c3e50;">Leave a Review</h2>
    <form method="POST">
        <textarea name="review" rows="4" cols="50" placeholder="Write your review here..." required></textarea><br><br>
        <button type="submit">Submit Review</button>
    </form>
    <h3 style="color:#34495e;">All Reviews</h3>
    <ul style="list-style:none;" >
    {% for r in reviews %}
    <li style="margin-bottom:25px; padding:10px; background:#fff; border-radius:10px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);"> {{ r }}</li>
    {% endfor %}
    </ul>
    <a href="{{ url_for('products_page') }}">⬅ Back to Products</a>
    """, reviews=reviews)

@app.route('/about')
def about():
    return render_template('about.html')
   
@app.route('/')
@login_required
def products_page():
    return render_template_string("""
    <body style="background-image: url('{{ url_for('static', filename='images/bg-new.jpg') }}');
             background-size: contain;
             background-position: top center;
             background-repeat: no-repeat;
             font-family: 'Open Sans', sans-serif;
             padding: 40px 20px;">
    <h1 style="color:#2c3e50;">Welcome, {{ session['username'] }}!</h1>
    <a href="{{ url_for('logout') }}">Logout</a><br><br>                             
    <a href="{{ url_for('contact') }}">📬 Contact</a> |
    <a href="{{ url_for('product_reviews') }}">⭐ Reviews</a> |
    <a href="{{ url_for('about') }}"> ℹAbout</a><br><br>   
                                                                          
    <h2 style="color:#34495e;">Products</h2>
    <ul style="list-style:none;">
        {% for product in products %}
        <li>
            <img src="{{ product.image }}" width="100" style="border-radius:8px;"><br>
            <b>{{ product.name }}</b><br>
            ₹{{ product.price }}<br>
            <a href="{{ url_for('add_to_cart', product_id=product.id) }}">Add to Cart</a>
        </li><br>
        {% endfor %}
    </ul>
    <a href="{{ url_for('cart') }}">Go to Cart</a>
    """, products=products)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if username in users:
            flash("Username already exists.", "error")
        elif not username or not password:
            flash("Please enter both username and password.", "error")
        else:
            users[username] = password
            flash("Registered successfully. Please login.", "success")
            return redirect(url_for('login'))
    return render_template_string("""
    <body style="background-image: url('{{ url_for('static', filename='images/bg-new.jpg') }}');
             background-size: contain;
             background-position: top center;
             background-repeat: no-repeat;
             font-family: 'Open Sans', sans-serif;
             padding: 40px 20px;">
    <h2 style="color:#2c3e50;">Register</h2>
    <form method="POST">
        Username: <input type="text" name="username"><br><br>
        Password: <input type="password" name="password"><br><br>
        <button type="submit">Register</button>
    </form>
    <a href="{{ url_for('login') }}">Already registered? Login</a>
    """)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if users.get(username) == password:
            session['username'] = username
            flash("Logged in successfully!", "success")
            return redirect(url_for('products_page'))
        else:
            flash("Invalid username or password.", "error")
    return render_template_string("""
    <body style="background-image: url('{{ url_for('static', filename='images/bg-new.jpg') }}');
             background-size: contain;
             background-position: top center;
             background-repeat: no-repeat;
             font-family: 'Open Sans', sans-serif;
             padding: 40px 20px;">                          
    <h2 style="color:#2c3e50;">Login</h2>
    <form method="POST">
        Username: <input type="text" name="username"><br><br>
        Password: <input type="password" name="password"><br><br>
        <button type="submit">Login</button>
    </form>
    <a href="{{ url_for('register') }}">Don't have an account? Register</a>
    """)

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

@app.route('/add_to_cart/<int:product_id>')
@login_required
def add_to_cart(product_id):
    product = next((p for p in products if p['id'] == product_id), None)
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('products_page'))

    cart = session.get('cart', {})
    key = str(product_id)
    cart[key] = cart.get(key, 0) + 1
    session['cart'] = cart
    session.modified = True
    flash(f'{product["name"]} added to cart', 'success')
    return redirect(url_for('products_page'))

@app.route('/update_cart/<int:product_id>/<int:change>')
@login_required
def update_cart(product_id, change):
    if change not in (-1, 1):
        raise BadRequest("Invalid quantity change")

    cart = session.get('cart', {})
    key = str(product_id)

    if key in cart:
        cart[key] += change
        if cart[key] <= 0:
            del cart[key]
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:product_id>')
@login_required
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    key = str(product_id)
    if key in cart:
        del cart[key]
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('cart'))

@app.route('/cart')
@login_required
def cart():
    cart_items = []
    subtotal = 0

    for product_id, quantity in session.get('cart', {}).items():
        product = next((p for p in products if p['id'] == int(product_id)), None)
        if product:
            item_total = product['price'] * quantity
            cart_items.append({
                'id': product['id'],
                'name': product['name'],
                'quantity': quantity,
                'price': product['price'],
                'image': product['image'],
                'total': item_total
            })
            subtotal += item_total

    shipping = 50 if subtotal > 0 else 0
    total = subtotal + shipping

    return render_template_string("""
    <body style="background-image: url('{{ url_for('static', filename='images/bg-new.jpg') }}');
             background-size: contain;
             background-position: top center;
             background-repeat: no-repeat;
             font-family: 'Open Sans', sans-serif;
             padding: 40px 20px;">                             
    <h1 style="color:#2c3e50;">Your Cart ({{ session['username'] }})</h1>
    <a href="{{ url_for('logout') }}">Logout</a><br><br>
    {% if cart_items %}
        <ul style="list-style:none;">
        {% for item in cart_items %}
            <li>
                <img src="{{ item.image }}" width="100"><br>
                {{ item.name }} (x{{ item.quantity }}) - ₹{{ item.total }}<br>
                <a href="{{ url_for('update_cart', product_id=item.id, change=1) }}">➕</a>
                <a href="{{ url_for('update_cart', product_id=item.id, change=-1) }}">➖</a>
                <a href="{{ url_for('remove_from_cart', product_id=item.id) }}">🗑 Remove</a>
            </li><br>
        {% endfor %}
        </ul>
        <p>Subtotal: ₹{{ subtotal }}</p>
        <p>Shipping: ₹{{ shipping }}</p>
        <p><strong>Total: ₹{{ total }}</strong></p>
        <br>
        <a href="{{ url_for('checkout') }}">🛒 Proceed to Checkout</a><br>
        <a href="{{ url_for('products_page') }}">⬅ Back to Products</a>
    {% else %}
        <p>Your cart is empty.</p>
        <a href="{{ url_for('products_page') }}">⬅ Browse Products</a>
    {% endif %}
    """, cart_items=cart_items, subtotal=subtotal, shipping=shipping, total=total)

@app.route('/checkout')
@login_required
def checkout():
    cart_items = []
    total = 0

    for product_id, quantity in session.get('cart', {}).items():
        product = next((p for p in products if p['id'] == int(product_id)), None)
        if product:
            cart_items.append({
                'name': product['name'],
                'quantity': quantity,
                'items': cart,
                'price': product['price']
            })
            total += product['price'] * quantity

    return render_template_string("""
    <body style="background-image: url('{{ url_for('static', filename='images/bg-new.jpg') }}');
             background-size: contain;
             background-position: top center;
             background-repeat: no-repeat;
             font-family: 'Open Sans', sans-serif;
             padding: 40px 20px;">                              
    <h1  style="color:#2c3e50;">Checkout</h1>
    {% if cart_items %}
        <ul style="list-style:none;">
            {% for item in cart_items %}
                <li>{{ item.name }} × {{ item.quantity }} — ₹{{ item.quantity * item.price }}</li>
            {% endfor %}
        </ul>
        <p><strong>Total: ₹{{ total }}</strong></p>
        <form method="POST" action="{{ url_for('place_order') }}">
        Name:<input name="name"><br>
        Address:<input name="address"><br>
        email:<input name="email"><br>                         
        phone:=<input name="phone"><br> action="{{ url_for('place_order') }}">
        <button type="submit">✅ Place Order</button>
        </form>
    {% else %}
        <p>Your cart is empty.</p>
    {% endif %}
     save_order_to_dynamodb(order_data)
     send_order_email(email, summary)

        # (Optional) SNS call is defined but not triggered here
        # send_sns_notification("New order received.")

    <a href="{{ url_for('cart') }}">← Back to Cart</a>
    """, cart_items=cart_items, total=total)

@app.route('/place_order', methods=['POST'])
@login_required
def place_order():
    session['cart'] = {}
    flash("🎉 Your order has been placed successfully!", "success")
    session.pop('cart', None)
    logger.info("Order placed and cart cleared.")
    return redirect(url_for('order_success'))

@app.route('/success')
@login_required
def order_success():
    return render_template_string("""
    <body style="background-image: url('{{ url_for('static', filename='images/bg-new.jpg') }}');
             background-size: contain;
             background-position: top center;
             background-repeat: no-repeat;
             font-family: 'Open Sans', sans-serif;
             padding: 40px 20px;">                             
    <h2>✅ Order Successful!</h2>
    <p>Thank you for your order, {{ session['username'] }}! 😊</p>
    <a href="{{ url_for('products_page') }}">← Back to Products</a><br>
    <a href="{{ url_for('logout') }}">🚪 Logout</a>
    """)

# -------------------- Error Pages --------------------

@app.errorhandler(404)
def not_found_error(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500



if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get("PORT",5000)))