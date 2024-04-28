from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
import random
import os
import re

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['UPLOAD_FOLDER_USER_AVATAR'] = 'static/uploads'
app.config['USER_AVATAR_FOLDER'] = 'static/uploads'
app.config['UPLOAD_FOLDER_PRODUCT_IMAGE'] = 'static/images'
app.config['PRODUCT_IMAGE_FOLDER'] = 'static/images'

db = SQLAlchemy(app)
migrate = Migrate(app, db)

PASSWORD_PATTERN = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    product = db.relationship('Product', backref='cart_items')


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="user")
    cart = db.relationship('CartItem', backref='user', lazy=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    avatar = db.Column(db.String(100))

    def __repr__(self):
        return f"User('{self.username}', '{self.role}')"


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)


with app.app_context():
    db.create_all()


def is_password_strong(password):
    return bool(re.match(PASSWORD_PATTERN, password))


@app.route('/')
def index():
    advertisement_images = [
        'advertisement1.png',
        'advertisement2.png'
    ]
    recommendations = random.sample(Product.query.all(), 2)
    return render_template('index.html', advertisement_images=advertisement_images,
                           recommendations=recommendations)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    username = request.cookies.get('username')
    user = User.query.filter_by(username=username).first()
    if not user:
        return render_template('login.html')

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        avatar = request.files['avatar']
        if avatar:
            avatar_filename = avatar.filename
            avatar.save(os.path.join(app.config['USER_AVATAR_FOLDER'], avatar_filename))
            user.avatar = avatar_filename
        user.first_name = first_name
        user.last_name = last_name
        db.session.commit()
        return redirect(url_for('profile'))
    return render_template('profile.html', user_info=user)


@app.route('/save_profile', methods=['POST'])
def save_profile():
    username = request.cookies.get('username')
    user = User.query.filter_by(username=username).first()
    if not user:
        return "User not logged in or not registered"
    user.first_name = request.form['first_name']
    user.last_name = request.form['last_name']
    db.session.commit()
    return redirect(url_for('profile'))


@app.route('/products')
def show_products_by_category():
    category = request.args.get('category')
    if category:
        products = Product.query.filter_by(category=category).all()
        return render_template('products.html', category=category, products=products)
    else:
        return "Category parameter is missing", 400


@app.route('/admin')
def admin_panel():
    return render_template('admin_panel.html')


@app.route('/add_product', methods=['POST'])
def add_product():
    name = request.form['productName']
    price = request.form['productPrice']
    category = request.form['productCategory']
    image = request.files['productImage']
    image.save(os.path.join(app.config['PRODUCT_IMAGE_FOLDER'], image.filename))
    new_product = Product(name=name, price=price, image=image.filename, category=category)
    db.session.add(new_product)
    db.session.commit()
    return redirect(url_for('admin_panel'))


@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    product_id = request.form.get('productId')
    if not product_id:
        return jsonify({"error": "Product ID is missing"}), 400

    username = request.cookies.get('username')
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not logged in or not registered"}), 401

    product = Product.query.get(product_id)
    if product:
        existing_cart_item = CartItem.query.filter_by(user_id=user.id, product_id=product_id).first()
        if existing_cart_item:
            existing_cart_item.quantity += 1
            db.session.commit()
        else:
            cart_item = CartItem(user_id=user.id, product_id=product_id)
            db.session.add(cart_item)
            db.session.commit()
        return jsonify({"message": "Product added to cart"}), 200
    else:
        return jsonify({"error": "Product not found"}), 404


@app.route('/cart')
def view_cart():
    username = request.cookies.get('username')
    user = User.query.filter_by(username=username).first()
    if not user:
        return redirect(url_for('login'))
    user_cart_items = CartItem.query.filter_by(user_id=user.id).all()
    return render_template('cart.html', cart_items=user_cart_items)


@app.route('/update_cart', methods=['POST'])
def update_cart():
    cart_item_id = request.form.get('cartItemId')
    new_quantity_str = request.form.get('quantity')
    if new_quantity_str is not None:
        new_quantity = int(new_quantity_str)
        cart_item = CartItem.query.get(cart_item_id)
        if cart_item:
            cart_item.quantity = new_quantity
            db.session.commit()
            return jsonify({"message": "Cart item quantity updated successfully"}), 200
        else:
            return jsonify({"error": "Cart item not found"}), 404
    else:
        return jsonify({"error": "New quantity is not provided"}), 400


@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    cart_item_id = request.form.get('cartItemId')
    cart_item = CartItem.query.get(cart_item_id)
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
        return redirect(url_for('view_cart'))
    else:
        return jsonify({"error": "Cart item not found"}), 404


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            resp = redirect(url_for('index'))
            resp.set_cookie('username', username)
            if user.role == 'admin':
                return redirect(url_for('admin_panel'))
            else:
                return resp
        else:
            return "Invalid credentials"
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        if not is_password_strong(password):
            return ("Пароль недостаточно надежный. Он должен содержать не менее 8 символов, "
                    "включая одну заглавную букву, одну строчную букву, одну цифру и один специальный символ.")

        existing_user = User.query.filter_by(username=username).first()
        if not existing_user:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = User(username=username, password=hashed_password, role=role)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        else:
            return "User already exists"
    return render_template('register.html')


@app.route('/logout')
def logout():
    resp = redirect(url_for('index'))
    resp.delete_cookie('username')
    return resp


@app.route('/about')
def about():
    with open('about_me.txt', 'r', encoding='utf-8') as file:
        about_text = file.read()
    return render_template('about.html', about_text=about_text)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
