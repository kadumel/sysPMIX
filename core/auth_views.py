from django.contrib.auth.views import LoginView

from controleBI.perfil_utils import url_pos_login


class PerfilLoginView(LoginView):
    template_name = 'registration/login.html'

    def get_success_url(self):
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        return url_pos_login(self.request.user)
