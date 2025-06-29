import json
from langchain.prompts import PromptTemplate
from core import call_llm

model_llm = "gpt-4o"

# --- PromptTemplate para gerar gráfico Plotly ---
PROMPT_GERAR_GRAFICO = PromptTemplate(
    input_variables=["pergunta", "dados"],
    template="""
Pergunta do usuário: {pergunta}

Aqui estão os dados agregados do MongoDB (em Python dict/JSON):
{dados}

Sua tarefa:
1. Analise os dados e decida o tipo de gráfico mais adequado (ex: bar, line, scatter, pie, etc).
2. Montar um dicionário JSON válido que represente o `figure` no estilo Plotly (sem o 'layout' se quiser simplificar).
    - Use a seguinte estrutura mínima:
            {{
                "data": [
                    {{
                        "type": "<tipo_de_grafico>",
                        "x": [...],
                        "y": [...],
                        "name": "Series Name",
                        "marker": {{"color": "blue"}}
                    }}
                ],
                "layout": {{
                    "title": "<Título do gráfico>",
                    "xaxis": {{"title": "<nome eixo X>"}},
                    "yaxis": {{"title": "<nome eixo Y>"}}
                }}
            }}
3. Não inclua nada fora do JSON, nem explicações, só o objeto JSON!

IMPORTANTÍSSIMO:
- Sua resposta deve ser APENAS o JSON do dicionário Plotly, sem markdown ou texto adicional.
- Não use crases, nem aspas simples fora do lugar. Responda unicamente com JSON válido.
- não use ```json se fizer isso, vai dar erro
"""
)

# --- PromptTemplate para avaliar necessidade de gráfico ---
PROMPT_AVALIAR_GRAFICO = PromptTemplate(
    input_variables=["pergunta", "dados"],
    template="""
Você é um assistente que avalia se um gráfico ajudaria a explicar os dados ao usuário.

Pergunta do usuário:
{pergunta}

Resultado da consulta (em JSON):
{dados}

O gráfico deve ser gerado apenas se ele ajudar na visualização dos dados (ex: listas, variações ao longo do tempo, categorias, proporções).
Quando se trata apenas de despesas retorne valores absolutos.

Responda apenas com "true" ou "false".
"""
)

def agente_gerar_grafico(pergunta, dados, model=model_llm):
    prompt = PROMPT_GERAR_GRAFICO.format(
        pergunta=pergunta,
        dados=json.dumps(dados, ensure_ascii=False)
    )
    print("Iniciando agente_gerar_grafico")
    response = call_llm(model, 0, prompt)
    response = response.strip()
    print(f"Resposta agente_gerar_grafico: {response}")
    try:
        figure_dict = json.loads(response)
        return figure_dict
    except json.JSONDecodeError:
        print(f"Erro: LLM não retornou JSON válido. Retorno LLM: {response}")
        return None

def avaliar_necessidade_grafico(pergunta: str, dados: list) -> bool:
    print("Analisando se devo criar um gráfico")
    if not dados:
        return False

    user_prompt = PROMPT_AVALIAR_GRAFICO.format(
        pergunta=pergunta,
        dados=json.dumps(dados, indent=2, ensure_ascii=False)
    )
    system_prompt = "Você avalia se faz sentido gerar um gráfico para o usuário com base na pergunta e nos dados retornados."
        
    response = call_llm(
        model=model_llm,
        temperature=0,
        user_prompt=user_prompt,
        system_role=system_prompt
    )
    
    should_create_graphic = response.strip().lower() in ["sim", "true", "yes"]
    print(f"Criar gráfico: {response}. Retorno função: {should_create_graphic}")
    return should_create_graphic
