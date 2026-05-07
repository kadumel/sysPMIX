from django.urls import path

from . import views

urlpatterns = [
    path(
        "integracoes/sankhya/task/<str:task_id>/status/",
        views.integracao_task_status,
        name="api_sankhya_integracao_task_status",
    ),
    path(
        "integracoes/sankhya/",
        views.gestao_integracoes,
        name="api_sankhya_gestao_integracoes",
    ),
    path(
        "integracoes/sankhya/atualizar-todas/",
        views.atualizar_todas_integracoes,
        name="api_sankhya_atualizar_todas_integracoes",
    ),
    path(
        "integracoes/sankhya/atualizar/<slug:chave>/",
        views.atualizar_integracao,
        name="api_sankhya_atualizar_integracao",
    ),
]
