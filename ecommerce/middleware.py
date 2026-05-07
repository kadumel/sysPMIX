from django.contrib.auth.views import redirect_to_login


class EcommerceLoginRequiredMiddleware:
    """Exige usuário autenticado para qualquer URL sob /ecommerce/."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/ecommerce') and not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        return self.get_response(request)
