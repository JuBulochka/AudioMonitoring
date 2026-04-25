"""User auth views (session-based for web UI)."""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone

from .models import OperatorProfile


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            user.last_activity = timezone.now()
            user.save(update_fields=["last_activity"])
            # Create profile if missing
            OperatorProfile.objects.get_or_create(user=user)
            next_url = request.GET.get("next", "/")
            return redirect(next_url)
        else:
            messages.error(request, "Неверный логин или пароль.")

    return render(request, "auth/login.html")


def logout_view(request):
    logout(request)
    return redirect("/auth/login/")
