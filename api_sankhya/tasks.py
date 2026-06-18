"""
Tarefas Django Q2 para integrações Sankhya (execução fora do ciclo request/response).
"""


def run_integracao_sankhya(
    chave: str,
    codigo_tabela: int | None = None,
    dtalter_desde: str | None = None,
) -> dict:
    from api_sankhya.views import INTEGRACOES

    if chave not in INTEGRACOES:
        return {"erro": "chave inválida"}
    if chave == "precos":
        resultado = INTEGRACOES[chave]["runner"](codigo_tabela=codigo_tabela)
    elif chave == "clientes":
        resultado = INTEGRACOES[chave]["runner"](dtalter_desde=dtalter_desde)
    else:
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
