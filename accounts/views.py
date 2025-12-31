from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from .forms import CustomUserCreationForm


def register(request):
    """Registro de novos usuários."""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, "Conta criada com sucesso!")
            return redirect("ui:dashboard")
    else:
        form = CustomUserCreationForm()
    
    return render(request, "accounts/register.html", {"form": form})


def logout_view(request):
    """Logout do usuário."""
    logout(request)
    return redirect("accounts:login")
