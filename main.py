import os

import bcrypt
import stripe
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import exists

# Secret used to sign the Flask session cookie. Must be set via env in any
# environment that matters; the fallback below is only for a quick local run.
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-only-insecure-secret-key')

# Stripe secret key (test mode). Get one at https://dashboard.stripe.com/test/apikeys
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')

planet_price_dict = {
    'mercury': {
        'price_data': {
            'currency': 'usd',
            'product_data': {
                'name': 'Mercury',
            },
            'unit_amount': 1000000,
        },
        'quantity': 1,
    },
    'venus': {
        'price_data': {
            'currency': 'usd',
            'product_data': {
                'name': 'Venus',
            },
            'unit_amount': 3000000,
        },
        'quantity': 1,
    },
    'earth': {
        'price_data': {
            'currency': 'usd',
            'product_data': {
                'name': 'Earth',
            },
            'unit_amount': 77777777,
        },
        'quantity': 1,
    },
    'mars': {
        'price_data': {
            'currency': 'usd',
            'product_data': {
                'name': 'Mars',
            },
            'unit_amount': 5000000,
        },
        'quantity': 1,
    },
    'jupiter': {
        'price_data': {
            'currency': 'usd',
            'product_data': {
                'name': 'Jupiter',
            },
            'unit_amount': 50000000,
        },
        'quantity': 1,
    },
    'saturn': {
        'price_data': {
            'currency': 'usd',
            'product_data': {
                'name': 'Saturn',
            },
            'unit_amount': 50000000,
        },
        'quantity': 1,
    },
    'uranus': {
        'price_data': {
            'currency': 'usd',
            'product_data': {
                'name': 'Uranus',
            },
            'unit_amount': 4206900,
        },
        'quantity': 1,
    },
    'neptune': {
        'price_data': {
            'currency': 'usd',
            'product_data': {
                'name': 'Neptune',
            },
            'unit_amount': 900100,
        },
        'quantity': 1,
    },
    'pluto': {
        'price_data': {
            'currency': 'usd',
            'product_data': {
                'name': 'Pluto',
            },
            'unit_amount': 999999999999999,
        },
        'quantity': 1,
    },
}

# Display copy for the storefront. Keeps names/images/descriptions in one
# place; price is always derived from planet_price_dict below so the number
# shown on the card can never drift from what Stripe actually charges.
PLANET_ORDER = [
    'mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn', 'uranus',
    'neptune', 'pluto',
]

PLANET_INFO = {
    'mercury': {
        'name': 'Mercury',
        'image': 'mercury.jpeg',
        'description': (
            'The first planet from the sun and the smallest in the solar '
            'system, terrestrial, cratered, with an exosphere. A great '
            'place to tan (or burn).'
        ),
    },
    'venus': {
        'name': 'Venus',
        'image': 'venus.jpeg',
        'description': (
            'The second planet from the sun, rocky with the thickest '
            'atmosphere of the rocky bodies, known as the "morning" or '
            '"evening" star. Bring your own oxygen mask if you visit.'
        ),
    },
    'earth': {
        'name': 'Earth',
        'image': 'earth.jpeg',
        'description': (
            'A cozy little planet, third from the sun. Many beautiful '
            'locations to visit, if you can stand the ruling population.'
        ),
    },
    'mars': {
        'name': 'Mars',
        'image': 'mars.jpeg',
        'description': (
            'Known as "The Red Planet", home to the Martians. They are '
            'currently protesting the takeover of their planet by an '
            'earthling known as \'The Musk\'.'
        ),
    },
    'jupiter': {
        'name': 'Jupiter',
        'image': 'jupiter.jpeg',
        'description': (
            'The largest planet in the solar system, this gas giant\'s '
            'mass is more than two and a half of all the other planets '
            'combined. Known for a famous storm in its hydrogen-rich '
            'clouds.'
        ),
    },
    'saturn': {
        'name': 'Saturn',
        'image': 'saturn.jpeg',
        'description': (
            'The sixth planet from the sun, a gas giant known for its '
            'majestic rings.'
        ),
    },
    'uranus': {
        'name': 'Uranus',
        'image': 'uranus.jpeg',
        'description': (
            'Known for its punny name, this ice giant is composed of '
            'water, ammonia, and methane.'
        ),
    },
    'neptune': {
        'name': 'Neptune',
        'image': 'neptune.jpeg',
        'description': (
            'Number eight, and feeling great, composed mostly of gases '
            'and liquids. Orbits the sun once every 164 years, so get '
            'used to only having one birthday.'
        ),
    },
    'pluto': {
        'name': 'Pluto',
        'image': 'pluto.jpeg',
        'description': (
            'Voted a dwarf planet by people who have definitely not had '
            'fun in years. This is the people\'s favorite.'
        ),
    },
}


def format_price(unit_amount_cents):
    """Render a Stripe unit_amount (cents) as a display price.

    Drops the cents when the amount is a whole dollar figure so
    '$10,000' still reads clean, but keeps them otherwise (e.g.
    '$777,777.77'). Always derived from the same number passed to
    Stripe, so the displayed price can never disagree with the charge.
    """
    dollars = unit_amount_cents / 100
    if dollars == int(dollars):
        return f'${int(dollars):,}'
    return f'${dollars:,.2f}'


def get_planets():
    planets = []
    for slug in PLANET_ORDER:
        info = PLANET_INFO[slug]
        price_cents = planet_price_dict[slug]['price_data']['unit_amount']
        planets.append({
            'slug': slug,
            'name': info['name'],
            'image': info['image'],
            'description': info['description'],
            'price_display': format_price(price_cents),
        })
    return planets


base_path = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_path, 'templates')
static_dir = os.path.join(base_path, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = SECRET_KEY

instance_dir = os.path.join(base_path, 'instance')
os.makedirs(instance_dir, exist_ok=True)
path_to_sql_file = os.path.join(instance_dir, 'db.sqlite3')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{path_to_sql_file}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100))
    password = db.Column(db.String(100))
    logged_in = db.Column(db.Integer)


# Create the tables if they don't exist yet. db.create_all() is idempotent,
# so it's safe to call on every startup instead of hand-rolling a file check.
with app.app_context():
    db.create_all()


stripe.api_key = STRIPE_SECRET_KEY

YOUR_DOMAIN = os.environ.get('YOUR_DOMAIN', 'http://127.0.0.1:5000')


def is_logged_in():
    return bool(db.session.query(exists().where(User.logged_in == 1)).scalar())


@app.context_processor
def inject_nav_state():
    # Makes the login/logout link in the shared nav (base.html) correct on
    # every page, not just the home page.
    return {'logged_in': is_logged_in()}


@app.route('/')
def home():
    return render_template('index.html', planets=get_planets())


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    planet = request.form.get('name')
    checkout_session = stripe.checkout.Session.create(
        line_items=[planet_price_dict[planet]],
        mode='payment',
        success_url=f'{YOUR_DOMAIN}/success',
        cancel_url=f'{YOUR_DOMAIN}/cancel',
    )
    return redirect(checkout_session.url, code=303)


@app.route('/success')
def success():
    return render_template('success.html')


@app.route('/cancel')
def cancel():
    return render_template('cancel.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    session.pop('_flashes', None)
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        pw = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            encoded_pw = bytes(pw, 'UTF-8')
            check = bcrypt.checkpw(encoded_pw, user.password.encode('UTF-8') if isinstance(user.password, str) else user.password)
            if check:
                flash('You are now Logged In')
                user.logged_in = 1
                db.session.commit()
                return redirect(url_for('home'))
            else:
                error = 'That password is incorrect'
                return render_template('login.html', error=error)
        else:
            error = 'That email is not in our system'
            return render_template('login.html', error=error)
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    user = User.query.filter_by(logged_in=1).first()
    if user:
        user.logged_in = 0
        db.session.commit()
    flash('You are now logged out')
    return redirect(url_for('home'))


@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        pw = request.form.get('password')
        re_pw = request.form.get('re-entered-pw')
        email = request.form.get('email')
        if pw != re_pw:
            flash("Sorry, your passwords didn't match")
            return redirect(url_for('add_user'))
        pw_to_bytes = bytes(pw, 'UTF-8')
        hashed = bcrypt.hashpw(pw_to_bytes, bcrypt.gensalt())
        new_user = User(
            password=hashed,
            email=email,
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('create_user.html')


if __name__ == '__main__':
    app.config['SESSION_TYPE'] = 'filesystem'
    app.run(debug=True)
