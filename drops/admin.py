from django.contrib import admin
from .models import CodeDrop, DroppedFile


class DroppedFileInline(admin.TabularInline):
    model = DroppedFile
    extra = 0
    readonly_fields = ('original_filename', 'cloudinary_url', 'file_type', 'file_size', 'uploaded_at')


@admin.register(CodeDrop)
class CodeDropAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_password_protected', 'created_at', 'expires_at', 'download_count', 'is_expired')
    readonly_fields = ('created_at',)
    inlines = [DroppedFileInline]

    def is_password_protected(self, obj):
        return obj.is_password_protected
    is_password_protected.boolean = True

    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True


@admin.register(DroppedFile)
class DroppedFileAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'drop', 'file_type', 'file_size', 'uploaded_at')
    list_filter = ('file_type',)
    readonly_fields = ('uploaded_at',)
