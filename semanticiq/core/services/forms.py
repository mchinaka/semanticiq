from django import forms
from ..models import SignupRequest
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox
from django.core.exceptions import ValidationError


# Common personal/free email providers to block
FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "aol.com", "protonmail.com", "live.com",
    "msn.com", "yandex.com", "zoho.com"
}

class SignupForm(forms.ModelForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)

    class Meta:
        model = SignupRequest
        fields = ["email", "full_name", "company_name", "position", "country", "captcha"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "company_name": forms.TextInput(attrs={"class": "form-control"}),
            "position": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"]
        domain = email.split("@")[1].lower()

        # Block free/personal email domains
        if domain in FREE_EMAIL_DOMAINS:
            raise ValidationError("Please use your business email address.")

        # Block subdomains of free providers (e.g., mail.gmail.com)
        for free in FREE_EMAIL_DOMAINS:
            if domain.endswith("." + free):
                raise ValidationError("Please use your business email address.")

        return email



        