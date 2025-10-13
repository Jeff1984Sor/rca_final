from django.shortcuts import render, redirect
from django.contrib.auth import views as auth_views
from .forms import CustomAuthenticationForm
from django.contrib.auth import logout

def home(request):
    # Se o usuário estiver autenticado, mostra a página de boas-vindas.
    if request.user.is_authenticated:
        return render(request, 'core/home.html')
    
    # Se o usuário NÃO estiver autenticado, redireciona para a página de login.
    return redirect('login')


class CustomLoginView(auth_views.LoginView):
    """
    Nossa view de login customizada, que usa nosso formulário customizado.
    """
    authentication_form = CustomAuthenticationForm
    template_name = 'registration/login.html'

def logout_view(request):
    """
    Desloga o usuário e redireciona para a página de login.
    """
    logout(request)
    return redirect('login')