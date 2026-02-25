# views/auth.py

from django.contrib.auth import authenticate, login
from django.contrib.auth import logout as auth_logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from .services.forms import SignupForm

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "Invalid credentials")
            return render(request, "core/login.html")

        login(request, user)
        return redirect("main_menu")

    return render(request, "core/login.html")

def logout(request):
    auth_logout(request)
    return redirect("/")

def signup_view(request):
    submitted = False

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            signup = form.save()

            # Send email
            send_mail(
                "Thanks for your interest!",
                "We will contact you within 24 hours to finalize your setup.",
                None,
                [signup.email],
            )

            submitted = True
            form = SignupForm()  # reset form if user wants to submit again
    else:
        form = SignupForm()

    return render(request, "core/signup.html", {"form": form, "submitted": submitted})