import redis
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import redirect, abort, request, jsonify

from config import Config

# inisialisasi Ekstensi
db = SQLAlchemy()
redis_client = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT)
limiter = Limiter(
    key_func=get_remote_address,
    app=None,
    storage_uri=Config.LIMITER_STORAGE_URI
)

# Model Database
class URLMapping(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    short_code = db.Column(db.String(10), unique=True, nullable=False)
    long_url = db.Column(db.String(512), nullable=False)
    click_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.now())

    def __repr__(self):
        return f"<URLMapping {self.short_code}>"

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # inisialisasi ekstensi dengan aplikasi FLask
    db.init_app(app)
    limiter.init_app(app)

    # import dan registrasi blueprint/routes akan di tahap selanjutnya

    with app.app_context():

        db.create_all()
    return app

app = create_app()
    

BASE62_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def base62_encode(num):
    """mengonversi ID integer menjadi string base62"""
    if num == 0:
        return BASE62_CHARS[0]
    
    encoded = ""
    base = len(BASE62_CHARS)
    while num > 0:
        encoded = BASE62_CHARS[num % base] + encoded
        num //= base
    return encoded


@app.route('/api/v1/shorten', methods=['POST'])
@limiter.limit("5 per minute")
def shorten_url():
    data = request.get_json()
    long_url = data.get('long_url')

    if not long_url:
        return jsonify({"error": "long_url is required"}), 400

    try:
        # 1. Simpan URL Panjang ke DB (tanpa short_code)
        new_mapping = URLMapping(long_url=long_url, short_code='temp')
        db.session.add(new_mapping)
        db.session.commit()

        # 2. Hasilkan short_code dari ID yang baru di buat
        short_code = base62_encode(new_mapping.id)

        # 3. update baris di DB dengan short_code yang sebenarnya
        new_mapping.short_code = short_code
        db.session.commit()

        # 4. simpan juga ke redis (optional: pre-caching)
        redis_client.setex(short_code, 86400, long_url)

        return jsonify({
            "short_url": f"http://localhost:5003/{short_code}",
            "short_code": short_code
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Server Error"}), 500


@app.route('/<short_code>', methods=['GET'])
def redirect_to_long_url(short_code):

    # 1. Cache Check (Redis) - Layer 1 (Tercepat)
    long_url_from_cache = redis_client.get(short_code)
    if long_url_from_cache:
        print(f"CAHCE HIT for {short_code}")
        return redirect(long_url_from_cache.decode('utf-8'))

    # 2. Database Check (PostgreSQL) - Layer 2
    mapping = URLMapping.query.filter_by(short_code=short_code).first()

    if mapping:
        # 3. update cache
        redis_client.setex(short_code,86400, mapping.long_url)

        # 4. Update click count
        mapping.click_count += 1
        db.session.commit()

        # 5. Redirect
        return redirect(mapping.long_url)
    
    else:
        abort(404)
    



@app.route('/test', methods=['GET'])
def test_route():
    return "Server is running!"


if __name__ == '__main__':
    
    app.run(debug=True, port=5003)