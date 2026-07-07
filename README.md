# Flask Online Shop

A small e-commerce demo built with Flask: browse a catalog, create an account,
log in, and pay through Stripe Checkout in test mode.

## Why it exists

A self-contained exercise in wiring up the parts a real online store needs:
session-based auth with hashed passwords, a SQLite-backed user table, and a
hosted payment flow, without pulling in a framework that hides how any of it
works.

## Features

- Product cards (image, name, price, description, "Buy" button) rendered
  from a single planet catalog in `main.py`, one card per planet, nine in
  total.
- A shared header/nav on every page (brand link plus a login/logout button
  that reflects the actual session state) and a consistent dark/light color
  scheme across the storefront, auth pages, and result pages.
- Login and registration pages styled as a single card with labeled fields,
  masked password inputs, and inline validation error messages (wrong
  password, unknown email, mismatched passwords on signup).
- A clean success page and a distinct "something went wrong, try again"
  cancel page, replacing the previous one-line Bootstrap defaults.
- Account creation and login with bcrypt-hashed passwords stored in SQLite.
- Stripe Checkout session creation per purchase, with success and cancel
  pages.
- Session-based login state (a `logged_in` flag on the user row), now read
  through a Flask context processor so the nav is correct on every page, not
  only the home page.

## Architecture

Single Flask app (`main.py`) with:

- **Flask-SQLAlchemy** for a one-table `User` model (email, hashed password,
  logged-in flag), backed by a SQLite file created on startup under
  `instance/`.
- **bcrypt** for password hashing and verification.
- **stripe** SDK to create a Checkout Session per order and redirect the
  browser to Stripe's hosted payment page. This logic was not touched during
  the UI work below, apart from the home route now passing a display list of
  planets to the template instead of the template hardcoding nine copies of
  the same markup.
- **Jinja templates** (`templates/`) extending a shared `base.html`: a nav
  bar, flashed-message rendering, and a footer live in the base template so
  every page (catalog, login, register, success, cancel) looks and behaves
  the same way. Styled with Bootstrap 5 plus a custom stylesheet
  (`static/css/styles.css`) built around CSS variables for color, a
  reusable product-card component, and shared auth-card/result-card
  components for the login, register, success, and cancel pages.
- A single `PLANET_INFO` dict plus `planet_price_dict` (the dict already
  used to build the Stripe line item) are combined by `get_planets()` into
  the list the template loops over, so the displayed price is always
  derived from the same number sent to Stripe, never a second hand-typed
  copy of it.

There is no cart: each "Buy" button on the home page starts a single-item
Stripe Checkout session for that planet.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: set FLASK_SECRET_KEY and STRIPE_SECRET_KEY
```

Environment variables (see `.env.example`):

- `FLASK_SECRET_KEY`: signs the session cookie. Generate one with
  `python -c "import secrets; print(secrets.token_hex(32))"`.
- `STRIPE_SECRET_KEY`: a Stripe **test mode** secret key from
  `https://dashboard.stripe.com/test/apikeys`. Without a real key, the app
  boots and the catalog/login pages work, but clicking "Buy" on a planet
  fails when it calls the Stripe API.
- `YOUR_DOMAIN`: base URL Stripe redirects back to after checkout (defaults
  to `http://127.0.0.1:5000`).

## Usage

```bash
python main.py
```

Visit `http://127.0.0.1:5000/`. Create an account, log in, then click "Buy"
on any planet's card to start a Stripe Checkout session. With a valid Stripe
test key, use one of Stripe's test card numbers
(`https://stripe.com/docs/testing`) to complete a test payment.

## What was verified here

- The app installs cleanly in a fresh virtualenv from `requirements.txt` and
  boots with the Flask dev server.
- `GET /` returns HTTP 200 and renders nine product cards, one per planet,
  each with an image, name, price, and a "Buy `<planet>`" button.
- A full register-then-login-then-logout flow was driven end to end with a
  `requests` session against the running server: registering a new account
  redirects to `/`, logging in with that account's real password redirects
  to `/` and flips the nav from "Login" to "Logout" with a flash message,
  logging in with a wrong password or an unregistered email renders the
  matching inline error text on the login page, and `/logout` redirects back
  to `/`.
- `POST /create-checkout-session` was hit directly with a valid planet name
  and no Stripe key configured: it reaches `stripe.checkout.Session.create`
  and fails only on Stripe's authentication check (no API key provided),
  confirming the route is wired correctly up to the point where a real key
  is required.

## What was not verified here

- A real Stripe checkout end to end (creating a session, completing payment,
  landing on `/success`). That needs a real Stripe test-mode secret key,
  which this environment does not have. The checkout route itself was
  exercised structurally (see above) and matches Stripe's documented
  Checkout Session API.

## Challenges

- **A login bug that only breaks with more than one user.** The original
  code checked whether the submitted email existed, then always fetched the
  password hash for user id 1 to compare against, regardless of which email
  was submitted. With exactly one seeded user this happens to work; with a
  second account it lets any password through as long as it matches user 1's
  hash, or rejects a correct password for user 2. Fixed by looking up the
  user by the submitted email and checking against that row's own hash.
- **A hardcoded Stripe test secret key and Flask signing key in source.**
  Both were removed and replaced with `os.environ.get(...)` reads, with
  `.env.example` documenting what each variable is for.
- **Stripe CA bundle plumbing that pointed nowhere.** The original code set
  `stripe.ca_bundle_path` to a `stripe/data/ca-certificates.crt` file that
  does not exist anywhere in the project, and separately set
  `REQUESTS_CA_BUNDLE` to a GitHub blob URL (not a filesystem path, which is
  what that variable expects). Neither had any effect since the Stripe
  Python SDK bundles its own CA certificates; both were dead code and were
  removed.
- **Double slashes in the Stripe redirect URLs.** `success_url` and
  `cancel_url` were built as `'http://127.0.0.1:5000//success'` (note the
  double slash), which still resolves in most browsers/servers but is a
  copy-paste artifact. Rebuilt from a single `YOUR_DOMAIN` env var with
  correct joins.
- **SQLite path resolved from `sys.argv[0]`.** The original database path
  was built from `os.path.abspath(os.path.dirname(sys.argv[0]))`, which
  breaks if the app is launched with a different working directory or
  invoked through a different entry point. Replaced with
  `os.path.dirname(os.path.abspath(__file__))`, which is stable regardless
  of how the script is invoked.
- **A displayed price that didn't match the actual charge.** The home page
  hardcoded "Uranus: $69,420" in the template, but `planet_price_dict`
  (the dict actually sent to Stripe) had Uranus's `unit_amount` set to
  4,206,900 cents, which is $42,069, not $69,420. Every other planet's
  hardcoded price happened to agree with its Stripe amount, so this only
  showed up by cross-checking each one. Fixed by deriving the displayed
  price from `planet_price_dict` itself (`format_price()` in `main.py`)
  instead of typing it twice, so the two numbers can't drift apart again.
- **Password fields typed as `type="text"`.** Both the login and registration
  forms used `<input type="text">` for the password field, so the password
  was shown in plain text while typing. Changed to `type="password"`; this
  is purely an HTML attribute, it doesn't touch how the value is read,
  hashed, or checked server-side.
- **Nine near-identical card blocks in one template.** The catalog page had
  nine copies of the same `<article class="card">` markup, one per planet,
  differing only in the text and image filename. Replaced with a single
  Jinja loop over a list built by `get_planets()`, so adding a planet is now
  one dict entry instead of a copy-pasted block.

## What I learned

- A password check that hardcodes which row to compare against (instead of
  the row for the submitted identity) is a bug that only surfaces once more
  than one row exists, which is exactly the kind of thing that survives solo
  testing and breaks in front of someone else.
- `REQUESTS_CA_BUNDLE` and `stripe.ca_bundle_path` both expect a local file
  path, not a URL; pointing them at a GitHub page silently does nothing
  useful, it does not raise an error.
- Flask's session-cookie secret and any payment provider secret key need to
  come from the environment from the first commit, not be added later. It
  is much easier to design for that from the start than to retrofit it.
- A price that's typed into a template and a price that's sent to a payment
  API are the same fact and should come from one place. Keeping them as two
  separate literals is how a customer ends up seeing one number and getting
  charged another.

## What I'd do differently

- Use `flask-login` instead of a hand-rolled `logged_in` integer column;
  the current approach has no real session isolation between browser tabs
  or devices, since "logged in" is a property of the user row, not of a
  session or cookie.
- Add a real cart instead of a single-item-per-click checkout, so a buyer
  could purchase more than one planet in a single Stripe session.
- Add server-side validation on signup (a maximum password length is
  enforced only in the HTML `maxlength` attribute, which a user can bypass
  by not using the form).
- Add a Stripe webhook handler to confirm payment server-side instead of
  trusting the `/success` redirect, which a user can hit directly without
  ever paying.
- Add client- and server-side field-level validation (email format,
  minimum password length) instead of relying on HTML `required`/`type`
  attributes and a single post-submit error message.
