from django.core.mail import send_mail
from django.urls import reverse

def send_welcome_email(user, password):
    subject = "Welcome to semanticIQ"
    message = (
        f"Hello {user.first_name},\n\n"
        "You have been assigned an account on semanticIQ.\n\n"
        f"Username: {user.username}\n"
        f"Temporary Password: {password}\n\n"
        "You will be asked to reset your password when you first log in.\n\n"
        "Login here:\n"
        "https://http://127.0.0.1:8000/login\n\n" # TODO: replace with actual domain
        "Best regards,\n"
        "The semanticIQ Team"
    )

    send_mail(
        subject,
        message,
        "malvern@semanticiq.co",
        [user.email],
        fail_silently=False,
    )