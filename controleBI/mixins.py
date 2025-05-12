from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

class AuthRequiredMixin(LoginRequiredMixin):
    """Mixin para requerer autenticação em views"""
    login_url = 'login'
    
    def handle_no_permission(self):
        return redirect(self.login_url) 