"""
Assistente Financeiro com tool calling (OpenAI SDK >= 1.0).

O modelo decide quando chamar as funções de cálculo e extrai os parâmetros
da própria mensagem do usuário ("quanto rendem 5 mil a 12% ao ano em 18 meses?").

Uso (PowerShell):
    pip install -r requirements.txt
    $env:OPENAI_API_KEY = "sua-chave"   # nunca coloque a chave no código
    python assistente_financeiro.py
"""

import json
import os

from openai import OpenAI

MODELO = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # confira o modelo vigente na documentação
MAX_MENSAGENS = 20  # limita o histórico para controlar custo e contexto


SYSTEM_PROMPT = """Você é um assistente de educação financeira para pessoas físicas no Brasil.
Regras:
- Para qualquer cálculo de juros, use SEMPRE as ferramentas disponíveis. Nunca calcule de cabeça.
- Se faltar algum parâmetro (valor, taxa ou prazo), pergunte antes de calcular.
- Considere taxas informadas como taxas efetivas anuais, salvo se o usuário disser o contrário.
- Responda em português, de forma curta, mostrando valor final e juros ganhos.
- Você não faz recomendação de investimento. Se pedirem, explique conceitos e sugira um profissional certificado."""


# ---------- Ferramentas (lógica de negócio, testável sem a API) ----------

def juros_simples(principal: float, taxa_anual: float, meses: int) -> dict:
    montante = principal * (1 + (taxa_anual / 100) * (meses / 12))
    return {"montante": round(montante, 2), "juros": round(montante - principal, 2)}


def juros_compostos(principal: float, taxa_anual: float, meses: int) -> dict:
    # Converte taxa efetiva anual em taxa mensal equivalente (padrão no mercado brasileiro)
    taxa_mensal = (1 + taxa_anual / 100) ** (1 / 12) - 1
    montante = principal * (1 + taxa_mensal) ** meses
    return {
        "montante": round(montante, 2),
        "juros": round(montante - principal, 2),
        "taxa_mensal_equivalente_pct": round(taxa_mensal * 100, 4),
    }


FERRAMENTAS = {"juros_simples": juros_simples, "juros_compostos": juros_compostos}

PARAMS = {
    "type": "object",
    "properties": {
        "principal": {"type": "number", "description": "Valor inicial em reais"},
        "taxa_anual": {"type": "number", "description": "Taxa anual em %, ex.: 12 para 12% a.a."},
        "meses": {"type": "integer", "description": "Prazo em meses"},
    },
    "required": ["principal", "taxa_anual", "meses"],
}

TOOLS = [
    {"type": "function", "function": {
        "name": "juros_simples",
        "description": "Calcula montante e juros com juros simples.",
        "parameters": PARAMS}},
    {"type": "function", "function": {
        "name": "juros_compostos",
        "description": "Calcula montante e juros com juros compostos (capitalização mensal).",
        "parameters": PARAMS}},
]


# ---------- Orquestração ----------

def executar_ferramenta(nome: str, argumentos_json: str) -> str:
    try:
        args = json.loads(argumentos_json)
        if args["principal"] <= 0 or args["meses"] <= 0:
            return json.dumps({"erro": "Valor e prazo devem ser positivos."})
        return json.dumps(FERRAMENTAS[nome](**args))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
        return json.dumps({"erro": f"Parâmetros inválidos: {e}"})


def responder(client: OpenAI, historico: list) -> str:
    mensagens = [{"role": "system", "content": SYSTEM_PROMPT}] + historico[-MAX_MENSAGENS:]

    # Loop: o modelo pode pedir uma ou mais ferramentas antes de responder
    for _ in range(5):
        resp = client.chat.completions.create(model=MODELO, messages=mensagens, tools=TOOLS)
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return msg.content

        mensagens.append(msg)
        for call in msg.tool_calls:
            resultado = executar_ferramenta(call.function.name, call.function.arguments)
            mensagens.append({"role": "tool", "tool_call_id": call.id, "content": resultado})

    return "Não consegui concluir o cálculo. Pode reformular a pergunta?"


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Defina a variável de ambiente OPENAI_API_KEY antes de executar.")
    client = OpenAI()  # lê OPENAI_API_KEY do ambiente
    print("=== Assistente Financeiro ===  (digite 'sair' para encerrar)\n")
    historico = []
    while True:
        entrada = input("Você: ").strip()
        if entrada.lower() == "sair":
            break
        if not entrada:
            continue
        historico.append({"role": "user", "content": entrada})
        try:
            texto = responder(client, historico)
        except Exception as e:  # rede, chave inválida, limite de uso
            print(f"[erro na API: {e}]\n")
            historico.pop()
            continue
        historico.append({"role": "assistant", "content": texto})
        print(f"Assistente: {texto}\n")


if __name__ == "__main__":
    main()
