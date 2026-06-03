import json
import mimetypes
import requests
import cloudinary
import cloudinary.utils
import cloudinary.uploader
from decouple import config
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator

from .models import CodeDrop, DroppedFile
from .utils import (
    generate_unique_code,
    validate_vanity_code,
    generate_qr_base64,
    build_zip_bytes,
)

# Configure Cloudinary from env
cloudinary.config(
    cloud_name=config('CLOUDINARY_CLOUD_NAME'),
    api_key=config('CLOUDINARY_API_KEY'),
    api_secret=config('CLOUDINARY_API_SECRET'),
    secure=True,
)

# ---------------------------------------------------------------------------
# File size limits (bytes)
# ---------------------------------------------------------------------------

MAX_SIZE_IMAGE    = 25 * 1024 * 1024   # 25 MB
MAX_SIZE_VIDEO    = 100 * 1024 * 1024  # 100 MB
MAX_SIZE_DEFAULT  = 25 * 1024 * 1024   # 25 MB for pdf, audio, archive, document, other

def get_max_size(file_type):
    if file_type == 'video':
        return MAX_SIZE_VIDEO
    return MAX_SIZE_DEFAULT  # covers image, pdf, audio, archive, document, other


def human_readable(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def index(request):
    """Upload page."""
    return render(request, 'drops/index.html')


def access_page(request, code=None):
    """Receiver page — shows file list / preview."""
    return render(request, 'drops/access.html', {'prefill_code': code or ''})


# ---------------------------------------------------------------------------
# API: Upload
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def upload(request):
    files = request.FILES.getlist('files')
    if not files:
        return JsonResponse({'error': 'No files provided.'}, status=400)

    password = request.POST.get('password', '').strip()
    vanity_code = request.POST.get('vanity_code', '').strip()

    # Determine the access code
    if vanity_code:
        code, err = validate_vanity_code(vanity_code)
        if err:
            return JsonResponse({'error': err}, status=400)
    else:
        code = generate_unique_code(use_words=True)

    from datetime import timedelta
    from django.utils import timezone

    expiry_days = request.POST.get('expiry', '7')

    if expiry_days == '0':
        expires_at = None
    else:
        expires_at = timezone.now() + timedelta(days=int(expiry_days))

    drop = CodeDrop(code=code, expires_at=expires_at)
    drop.set_password(password if password else None)
    drop.save()

    uploaded = []
    errors = []

    for f in files:
        mime_type = f.content_type or (mimetypes.guess_type(f.name)[0] or '')
        file_type = DroppedFile.detect_file_type(mime_type, f.name)

        # ── Size validation ──────────────────────────────────────────────
        max_size = get_max_size(file_type)
        if f.size > max_size:
            errors.append({
                'filename': f.name,
                'error': (
                    f"File size {human_readable(f.size)} exceeds the "
                    f"{human_readable(max_size)} limit for {file_type} files."
                )
            })
            continue
        # ────────────────────────────────────────────────────────────────

        try:
            if file_type == 'image':
                resource_type = 'image'
            elif file_type == 'video':
                resource_type = 'video'
            elif file_type == 'pdf':
                resource_type = 'image'   # IMPORTANT
            else:
                resource_type = 'raw'

            result = cloudinary.uploader.upload(
                f,
                folder=f"codedrop/{code}",
                resource_type=resource_type,
                use_filename=True,
                unique_filename=True,
            )

            df = DroppedFile.objects.create(
                drop=drop,
                original_filename=f.name,
                cloudinary_url=result['secure_url'],
                cloudinary_public_id=result.get('public_id', ''),
                file_type=file_type,
                file_size=f.size,
                mime_type=mime_type,
            )
            uploaded.append({
                'id': df.id,
                'filename': df.original_filename,
                'url': df.cloudinary_url,
                'file_type': df.file_type,
                'size': df.size_display,
            })
        except Exception as e:
            errors.append({'filename': f.name, 'error': str(e)})

    if not uploaded:
        drop.delete()
        return JsonResponse({'error': 'All file uploads failed.', 'details': errors}, status=500)

    access_url = request.build_absolute_uri(f'/access/{code}/')
    qr_data_uri = generate_qr_base64(access_url)

    return JsonResponse({
        'code': code,
        'access_url': access_url,
        'qr_code': qr_data_uri,
        'password_protected': drop.is_password_protected,
        'expires_at': drop.expires_at.isoformat() if drop.expires_at else None,
        'files': uploaded,
        'errors': errors,
    }, status=201)


# ---------------------------------------------------------------------------
# API: Access (list files)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET", "POST"])
def access(request, code):
    drop = get_object_or_404(CodeDrop, code=code.upper())

    if drop.is_expired:
        return JsonResponse({'error': 'This drop has expired.'}, status=410)

    if drop.is_password_protected:
        if request.method == 'GET':
            return JsonResponse({'password_required': True, 'code': code}, status=200)

        body = {}
        try:
            body = json.loads(request.body)
        except Exception:
            pass
        password = body.get('password', '')
        if not drop.check_password(password):
            return JsonResponse({'error': 'Incorrect password.'}, status=403)

    files = []
    for df in drop.files.all():
        files.append({
            'id': df.id,
            'filename': df.original_filename,
            'url': df.cloudinary_url,
            'file_type': df.file_type,
            'size': df.size_display,
            'mime_type': df.mime_type,
        })

    return JsonResponse({
        'code': drop.code,
        'password_protected': drop.is_password_protected,
        'expires_at': drop.expires_at.isoformat() if drop.expires_at else None,
        'file_count': len(files),
        'files': files,
    })


# ---------------------------------------------------------------------------
# API: Download as ZIP
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET", "POST"])
def download_zip(request, code):
    drop = get_object_or_404(CodeDrop, code=code.upper())

    if drop.is_expired:
        return HttpResponse('This drop has expired.', status=410)

    if drop.is_password_protected:
        password = request.GET.get('password', '') or request.POST.get('password', '')
        if not drop.check_password(password):
            return HttpResponse('Incorrect password.', status=403)

    files = list(drop.files.all())
    if not files:
        return HttpResponse('No files in this drop.', status=404)

    drop.download_count += 1
    drop.save(update_fields=['download_count'])

    zip_bytes = build_zip_bytes(files)
    safe_code = code.replace('/', '_')
    response = HttpResponse(zip_bytes, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="codedrop-{safe_code}.zip"'
    response['Content-Length'] = len(zip_bytes)
    return response


# ---------------------------------------------------------------------------
# API: Download single file
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def download_file(request, code, file_id):
    drop = get_object_or_404(CodeDrop, code=code.upper())
    file = get_object_or_404(DroppedFile, id=file_id, drop=drop)

    try:
        response = requests.get(file.cloudinary_url, timeout=30)

        if response.status_code != 200:
            return HttpResponse("Could not fetch file from Cloudinary.", status=500)

        django_response = HttpResponse(response.content, content_type=file.mime_type)
        django_response["Content-Disposition"] = (
            f'attachment; filename="{file.original_filename}"'
        )
        return django_response

    except Exception as e:
        print("DOWNLOAD ERROR:", str(e))
        return HttpResponse(f"Download failed: {str(e)}", status=500)