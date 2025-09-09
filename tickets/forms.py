"""
Forms for the tickets application.
Includes ticket creation, editing, and attachment handling.
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import Ticket, TicketAttachment, Category
from django.contrib.auth.models import User
import mimetypes


# Allowed file types and their MIME types
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

ALLOWED_DOCUMENT_TYPES = {"application/pdf"}

ALLOWED_MIME_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_DOCUMENT_TYPES

# File size limits
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_SIZE = 3 * 1024 * 1024  # 3 MB for images


class TicketForm(forms.ModelForm):
    """Form for creating and editing tickets"""

    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by(
            "first_name", "last_name"
        ),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Assign to",
    )

    class Meta:
        model = Ticket
        fields = [
            "title",
            "description",
            "category",
            "priority",
            "location",
            "department",
            "assigned_to",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Brief description of the issue",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Detailed description of the issue, steps to reproduce, etc.",
                }
            ),
            "category": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "location": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g., Building A, Room 101",
                }
            ),
            "department": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., IT, HR, Finance"}
            ),
            "assigned_to": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make category required
        self.fields["category"].required = True
        self.fields["category"].empty_label = "Select a category"


class TicketAttachmentForm(forms.ModelForm):
    """Form for uploading ticket attachments"""

    class Meta:
        model = TicketAttachment
        fields = ["file", "description"]
        widgets = {
            "file": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".jpg,.jpeg,.png,.webp,.pdf",
                    "multiple": False,
                }
            ),
            "description": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": 'Optional: Describe what this file shows (e.g., "Error screenshot", "System diagram")',
                    "maxlength": 200,
                }
            ),
        }

    def clean_file(self):
        """Validate uploaded file"""
        file = self.cleaned_data.get("file")

        if not file:
            return file

        # Check file size
        if file.size > MAX_FILE_SIZE:
            raise ValidationError(
                f"File size ({file.size // (1024*1024)} MB) exceeds maximum allowed size "
                f"({MAX_FILE_SIZE // (1024*1024)} MB)."
            )

        # Get content type
        content_type = getattr(file, "content_type", "")

        # If content_type is not set, try to guess from filename
        if not content_type:
            content_type, _ = mimetypes.guess_type(file.name)

        # Validate content type
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(
                "Only JPG, PNG, WebP images and PDF documents are allowed."
            )

        # Additional size check for images
        if content_type in ALLOWED_IMAGE_TYPES and file.size > MAX_IMAGE_SIZE:
            raise ValidationError(
                f"Image size ({file.size // (1024*1024)} MB) exceeds maximum allowed size "
                f"for images ({MAX_IMAGE_SIZE // (1024*1024)} MB)."
            )

        # Basic security check - ensure file is not executable
        if file.name.lower().endswith((".exe", ".bat", ".cmd", ".scr", ".com", ".pif")):
            raise ValidationError("Executable files are not allowed.")

        return file


class MultipleFileInput(forms.ClearableFileInput):
    """Custom widget for multiple file uploads"""

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Custom field for multiple file uploads"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class TicketWithAttachmentsForm(forms.Form):
    """Combined form for creating a ticket with attachments"""

    # Ticket fields
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Brief description of the issue",
            }
        ),
    )

    description = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Detailed description of the issue, steps to reproduce, etc.",
            }
        )
    )

    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="Select a category",
    )

    priority = forms.ChoiceField(
        choices=Ticket._meta.get_field("priority").choices,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    location = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "e.g., Building A, Room 101"}
        ),
    )

    department = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "e.g., IT, HR, Finance"}
        ),
    )

    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by(
            "first_name", "last_name"
        ),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Assign to",
    )

    # Attachment fields
    attachments = MultipleFileField(
        required=False,
        widget=MultipleFileInput(
            attrs={
                "class": "form-control",
                "accept": ".jpg,.jpeg,.png,.webp,.pdf",
                "multiple": True,
            }
        ),
        help_text="Optional: Upload images (JPG, PNG, WebP) or PDF documents. Max 5MB per file.",
    )

    cc_admins = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_staff=True, is_active=True).order_by(
            "first_name", "last_name"
        ),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-control select2",
                "data-placeholder": "Select admins to CC...",
            }
        ),
        label="CC Admins",
        help_text="Optional: Select additional staff/admins to CC.",
    )
    cc_non_admins = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_staff=False, is_active=True).order_by(
            "first_name", "last_name"
        ),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-control select2",
                "data-placeholder": "Select users to CC...",
            }
        ),
        label="CC Non-Admins",
        help_text="Optional: Select additional non-admin users to CC.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize the label display for both CC fields
        self.fields["cc_admins"].label_from_instance = (
            lambda obj: obj.get_full_name() or obj.username
        )
        self.fields["cc_non_admins"].label_from_instance = (
            lambda obj: obj.get_full_name() or obj.username
        )

    def clean_attachments(self):
        """Validate all uploaded attachments"""
        files = self.cleaned_data.get("attachments")

        if not files:
            return files

        # Ensure files is a list
        if not isinstance(files, list):
            files = [files]

        # Validate each file
        for file in files:
            if file:
                # Use the same validation as TicketAttachmentForm
                form = TicketAttachmentForm()
                try:
                    form.clean_file = lambda: file
                    validated_file = form.clean_file()
                except ValidationError as e:
                    raise ValidationError(f"File '{file.name}': {e.message}")

        return files
