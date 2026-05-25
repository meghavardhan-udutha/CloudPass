from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
import datetime


class CodeDrop(models.Model):
    code = models.CharField(max_length=64, unique=True, db_index=True)
    password_hash = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'code_drop'
        ordering = ['-created_at']

    def __str__(self):
        return self.code

    def set_password(self, raw_password):
        if raw_password:
            self.password_hash = make_password(raw_password)
        else:
            self.password_hash = None

    def check_password(self, raw_password):
        if not self.password_hash:
            return True
        return check_password(raw_password, self.password_hash)

    @property
    def is_password_protected(self):
        return bool(self.password_hash)

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class DroppedFile(models.Model):
    FILE_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('pdf', 'PDF'),
        ('audio', 'Audio'),
        ('archive', 'Archive'),
        ('document', 'Document'),
        ('other', 'Other'),
    ]

    drop = models.ForeignKey(CodeDrop, on_delete=models.CASCADE, related_name='files')
    original_filename = models.CharField(max_length=500)
    cloudinary_url = models.URLField(max_length=1000)
    cloudinary_public_id = models.CharField(max_length=500, blank=True)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='other')
    file_size = models.BigIntegerField(default=0)  # bytes
    mime_type = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dropped_file'
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{self.original_filename} ({self.drop.code})"

    @property
    def size_display(self):
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @classmethod
    def detect_file_type(cls, mime_type, filename):
        mime = (mime_type or '').lower()
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        if mime.startswith('image/') or ext in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico'):
            return 'image'
        if mime.startswith('video/') or ext in ('mp4', 'webm', 'mov', 'avi', 'mkv', 'flv'):
            return 'video'
        if mime == 'application/pdf' or ext == 'pdf':
            return 'pdf'
        if mime.startswith('audio/') or ext in ('mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a'):
            return 'audio'
        if ext in ('zip', 'tar', 'gz', 'rar', '7z', 'bz2') or 'zip' in mime or 'compressed' in mime:
            return 'archive'
        if ext in ('doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'md') or 'document' in mime or 'text' in mime:
            return 'document'
        return 'other'
