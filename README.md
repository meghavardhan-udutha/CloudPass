# CodeDrop

Share files instantly with a short access code. No login needed.

Upload files → get a code like `BLUE-HAWK-33` → anyone with the code can preview and download.

---

## Features

- Drag-and-drop multi-file upload
- 6–8 char auto-generated codes (e.g. `BLUE-HAWK-33`) or custom vanity codes
- Optional password protection per drop
- QR code generated alongside the access code
- In-browser preview: images, videos, PDFs
- Bulk download as ZIP
- Light / Dark theme toggle (saved in localStorage)
- All files stored on Cloudinary — no local disk storage
- MySQL database via Django ORM

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Django 4.2 |
| Database | MySQL (via `mysqlclient`) |
| File storage | Cloudinary |
| QR codes | `qrcode` + `Pillow` |
| ZIP downloads | Python built-in `zipfile` |
| Static files | WhiteNoise |
| Deployment | Railway or Render |

---

## Local Setup

### 1. Prerequisites

- Python 3.11+
- MySQL 8.0+ running locally
- A free [Cloudinary](https://cloudinary.com) account

### 2. Clone & create virtualenv

```bash
git clone <your-repo>
cd codedrop

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
# macOS (MySQL client headers)
brew install mysql-client
export LDFLAGS="-L$(brew --prefix mysql-client)/lib"
export CPPFLAGS="-I$(brew --prefix mysql-client)/include"

# Ubuntu / Debian
sudo apt-get install default-libmysqlclient-dev build-essential

pip install -r requirements.txt
```

### 4. Create MySQL database

```sql
CREATE DATABASE codedrop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 5. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your values (see Environment Variables section below)
```

### 6. Run migrations

```bash
python manage.py migrate
```

### 7. Collect static files & run

```bash
python manage.py collectstatic --noinput
python manage.py runserver
```

Open http://127.0.0.1:8000

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Django secret key (any long random string) |
| `DEBUG` | ✅ | `True` for dev, `False` for production |
| `ALLOWED_HOSTS` | ✅ | Comma-separated list of allowed hosts |
| `DATABASE_URL` | ✅* | Full MySQL connection URL (for Railway/Render) |
| `DB_NAME` | ✅* | Database name (local dev) |
| `DB_USER` | ✅* | Database user (local dev) |
| `DB_PASSWORD` | ✅* | Database password (local dev) |
| `DB_HOST` | ✅* | Database host, e.g. `localhost` |
| `DB_PORT` | ✅* | Database port, e.g. `3306` |
| `CLOUDINARY_CLOUD_NAME` | ✅ | From Cloudinary Dashboard |
| `CLOUDINARY_API_KEY` | ✅ | From Cloudinary Dashboard |
| `CLOUDINARY_API_SECRET` | ✅ | From Cloudinary Dashboard |

*Use `DATABASE_URL` for production deployments, individual `DB_*` vars for local dev.

---

## Deployment

### Railway

1. Push your code to GitHub.
2. Create a new project on [Railway](https://railway.app).
3. Click **New Service → GitHub Repo** and select your repo.
4. Add a **MySQL** plugin from Railway's Add Service menu.
5. Railway auto-sets `DATABASE_URL`. Add the remaining env vars:
   ```
   SECRET_KEY=<generate a new one>
   DEBUG=False
   ALLOWED_HOSTS=<your-app>.up.railway.app
   CLOUDINARY_CLOUD_NAME=...
   CLOUDINARY_API_KEY=...
   CLOUDINARY_API_SECRET=...
   ```
6. Railway will detect the `Procfile` and deploy automatically.
7. After first deploy, open a Railway shell and run:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

### Render

1. Push your code to GitHub.
2. Create a new **Web Service** on [Render](https://render.com).
3. Set **Build Command**:
   ```
   pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
   ```
4. Set **Start Command**:
   ```
   gunicorn codedrop.wsgi --log-file -
   ```
5. Create a **MySQL** database on Render (or use PlanetScale free tier).
6. Add environment variables in the Render dashboard (same list as Railway above).

### Generate a SECRET_KEY

```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## Project Structure

```
codedrop/
├── codedrop/           # Django project package
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── drops/              # Main app
│   ├── models.py       # CodeDrop, DroppedFile
│   ├── views.py        # Upload, access, download endpoints
│   ├── urls.py
│   ├── utils.py        # Code generation, QR, ZIP
│   └── admin.py
├── templates/
│   ├── base.html
│   └── drops/
│       ├── index.html  # Upload page
│       └── access.html # Retrieve page
├── static/
│   └── css/main.css
├── manage.py
├── requirements.txt
├── Procfile
├── runtime.txt
└── .env.example
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload/` | Upload files, returns code + QR |
| `GET` | `/api/access/<code>/` | List files (or ask for password) |
| `POST` | `/api/access/<code>/` | List files with password in body |
| `GET` | `/download/<code>/` | Stream all files as ZIP |
| `GET` | `/download/<code>/?password=<pw>` | ZIP download for protected drop |

### POST /upload/

Form fields:
- `files` (multipart, multiple) — required
- `password` (string) — optional
- `vanity_code` (string) — optional, e.g. `RESUME-2026`

Response:
```json
{
  "code": "BLUE-HAWK-33",
  "access_url": "https://yourapp.com/access/BLUE-HAWK-33/",
  "qr_code": "data:image/png;base64,...",
  "password_protected": false,
  "expires_at": "2025-09-01T00:00:00Z",
  "files": [
    { "id": 1, "filename": "resume.pdf", "url": "https://res.cloudinary.com/...", "file_type": "pdf", "size": "142.3 KB" }
  ]
}
```

---

## Notes

- Drops expire after **7 days** by default.
- File size limit is **100 MB** per request (configurable in `settings.py`).
- Cloudinary free tier supports 25 GB storage and 25 GB monthly bandwidth.
