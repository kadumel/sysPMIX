"""
Tarefas Django Q2 para integrações Sankhya (execução fora do ciclo request/response).
"""


def run_integracao_sankhya(chave: str) -> dict:
    from api_sankhya.views import INTEGRACOES

    if chave not in INTEGRACOES:
        return {"erro": "chave inválida"}
    resultado = INTEGRACOES[chave]["runner"]()
    if not isinstance(resultado, dict):
        resultado = {}
    return resultado


def run_todas_integracoes_sankhya() -> dict:
    from api_sankhya.views import INTEGRACOES

    erros: list[str] = []
    for _chave, integracao in INTEGRACOES.items():
        nome = integracao["nome"]
        try:
            integracao["runner"]()
        except Exception as exc:
            erros.append(f"{nome}: {exc}")
    return {"erros": erros}
