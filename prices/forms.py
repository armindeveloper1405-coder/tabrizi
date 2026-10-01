from django import forms


class ReceiptSubmissionForm(forms.Form):
    receipt_reference = forms.CharField(
        label="شناسه یا شماره پیگیری رسید",
        max_length=120,
        strip=True,
    )
    receipt_message = forms.CharField(
        label="پیام برای مدیر",
        max_length=2000,
        required=True,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    receipt_file = forms.FileField(
        label="تصویر یا PDF رسید",
        required=True,
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,application/pdf"}),
    )

    def clean_receipt_file(self):
        uploaded = self.cleaned_data.get("receipt_file")
        if not uploaded:
            return uploaded
        if uploaded.size > 5 * 1024 * 1024:
            raise forms.ValidationError("حجم فایل رسید نباید بیشتر از ۵ مگابایت باشد.")
        signatures = {
            "image/jpeg": lambda header: header.startswith(b"\xff\xd8\xff"),
            "image/png": lambda header: header.startswith(b"\x89PNG\r\n\x1a\n"),
            "application/pdf": lambda header: header.startswith(b"%PDF-"),
        }
        signature_matches = signatures.get(uploaded.content_type)
        header = uploaded.read(8)
        uploaded.seek(0)
        if not signature_matches or not signature_matches(header):
            raise forms.ValidationError("فقط تصویر JPG/PNG یا فایل PDF پذیرفته می‌شود.")
        return uploaded
