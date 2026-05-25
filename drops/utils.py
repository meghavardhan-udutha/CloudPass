import random
import string
import re
import io
import base64
import zipfile
import requests

import qrcode
from .models import CodeDrop

import cloudinary.utils

# ---------------------------------------------------------------------------
# Access-code helpers
# ---------------------------------------------------------------------------

ADJECTIVES = [
    'BLUE', 'RED', 'GOLD', 'DARK', 'FAST', 'COOL', 'IRON', 'SOFT',
    'BOLD', 'KEEN', 'WILD', 'CALM', 'DEEP', 'PURE', 'SLIM', 'SWIFT',
]

NOUNS = [
    'HAWK', 'WOLF', 'BEAR', 'CROW', 'LAKE', 'PINE', 'STAR', 'MOON',
    'RAIN', 'FIRE', 'WAVE', 'ROCK', 'LEAF', 'MIST', 'DUST', 'SPARK',
]


def generate_word_code():
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    num = random.randint(10, 99)
    return f"{adj}-{noun}-{num}"


def generate_random_code(length=7):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


def generate_unique_code(use_words=True):
    for _ in range(20):
        code = generate_word_code() if use_words else generate_random_code()

        if not CodeDrop.objects.filter(code=code).exists():
            return code

    for _ in range(20):
        code = generate_random_code(8)

        if not CodeDrop.objects.filter(code=code).exists():
            return code

    raise RuntimeError("Could not generate unique code")


def validate_vanity_code(raw):
    code = raw.strip().upper()

    if len(code) < 3:
        return None, "Code must be at least 3 characters."

    if len(code) > 32:
        return None, "Code must be 32 characters or fewer."

    if not re.match(r'^[A-Z0-9\-]+$', code):
        return None, "Code may only contain letters, digits, and hyphens."

    if CodeDrop.objects.filter(code=code).exists():
        return None, f"'{code}' already exists."

    return code, None


# ---------------------------------------------------------------------------
# QR-code helper
# ---------------------------------------------------------------------------

def generate_qr_base64(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )

    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format='PNG')

    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return f"data:image/png;base64,{b64}"


# ---------------------------------------------------------------------------
# ZIP helper
# ---------------------------------------------------------------------------

def build_zip_bytes(dropped_files):

    memory_file = io.BytesIO()

    with zipfile.ZipFile(
        memory_file,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zf:

        seen_names = {}

        for df in dropped_files:

            name = df.original_filename

            if name in seen_names:
                seen_names[name] += 1
                base, dot, ext = name.rpartition('.')

                if ext:
                    name = f"{base}_{seen_names[name]}.{ext}"
                else:
                    name = f"{name}_{seen_names[name]}"
            else:
                seen_names[name] = 0

            try:
                file_url = cloudinary.utils.cloudinary_url(
                    df.cloudinary_public_id,
                    resource_type="raw",
                    secure=True,
                    sign_url=True
                )[0]

                response = requests.get(
                    file_url,
                    timeout=30
                )

                if response.status_code == 200:
                    zf.writestr(
                        name,
                        response.content
                    )

            except Exception as e:
                print("ZIP Error:", e)

    memory_file.seek(0)

    return memory_file.read()