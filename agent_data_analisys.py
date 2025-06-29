import os
import json
import re
from pymongo import MongoClient
from datetime import datetime
from core import call_llm, serializar_mongo
from langchain.prompts import PromptTemplate

client = MongoClient(os.environ["MONGO_URI"])
db = client["financebot"]
transactions = db["transactions"]
data_atual = datetime.now().strftime('%Y-%m-%d')
model_llm = "gpt-4o"

# Pega índices da collection dinamicamente
def listar_indices_mongo():
    indices = []
    for idx in transactions.list_indexes():
        campos = list(idx["key"].keys())
        if campos != ['_id']:
            indices.append(campos)
    return indices

indices = listar_indices_mongo()

prompt_pipeline_llm = PromptTemplate(
    input_variables=["data_atual", "indices", "pergunta_usuario"],
    template="""
Considere que a data atual é {data_atual}
Você é um agente financeiro especialista em MongoDB. Sua tarefa é, dado uma pergunta sobre a coleção "transactions" ou "categories", montar uma pipeline válida para consulta no MongoDB via pymongo. Siga sempre as instruções abaixo:

- Os campos da *collection transactions* são:
    - valor: float (positivo para receitas, negativo para despesas)
    - data: datetime (sempre no formato YYYY-MM-DDT00:00:00, ou seja, datas SEMPRE com horário zero)
    - tipo: string ('receita' ou 'despesa')
    - categoria: string
    - estabelecimento: string

- Os campos da *collection categories* são:
    - nome: nome identificador da categoria
    - descricao: descrição detalhada da categoria

- Para consultas, use SEMPRE o pipeline de agregação MongoDB (array de etapas). 
- Utilize as etapas: $match (sempre primeiro, se usado), $group, $count, $sort, $limit (sempre último, se usado).
- Exemplos:
  - Para somar gastos por categoria entre duas datas:
    [
      {{"$match": {{"data": {{"$gte": "2025-05-01T00:00:00", "$lte": "2025-05-31T00:00:00"}}}}}},
      {{"$group": {{"_id": "$categoria", "total": {{"$sum": "$valor"}}}}}},
      {{"$sort": {{"total": -1}}}},
      {{"$limit": 5}}
    ]
  - Para saldo total em 2024:
    [
      {{"$match": {{"data": {{"$gte": "2024-01-01T00:00:00", "$lte": "2024-12-31T00:00:00"}}}}}},
      {{"$group": {{"_id": null, "saldo": {{"$sum": "$valor"}}}}}}
    ]

- O campo 'data' é SEMPRE datetime e deve ter hora zero (00:00:00) para ser compatível com a base.
- Os índices existentes nesta collection são: {indices}
- Despesas têm valor negativo, receitas positivo. Para saldo, apenas some o campo valor. Em sort, considere que receitas deve ser em ordem decrescente e gastos em ordem crescente
- Para reportar ao usuário, quando estiver mencionando apenas despesas, retorne valores absolutos.
- Quando o usuário perguntar por maiores e top de categorias ou estabelecimentos, caso não especifique se é receita, considere que é sobre despesas. 
- Não use campos que não existem.
- Nunca explique, apenas retorne um json no seguinte formado:
{{
 "collection":"NomeDaCollection",
 "pipeline":[...]
}}

Pergunta do usuário: {pergunta_usuario}
"""
)

prompt_interpretar_resultado = PromptTemplate(
    input_variables=["data_atual", "pergunta", "resultado"],
    template="""
Considere que a data atual é {data_atual}

Pergunta: {pergunta}

Resultado da consulta no MongoDB (em JSON):
{resultado}

Gere uma resposta em português, para ser exibida em uma interface web Streamlit, utilizando diretamente HTML. Siga as regras abaixo para formatar a resposta:
- Sempre inicie cada frase com a primeira letra maiúscula e as demais em minúsculas (exceto nomes próprios).
- Se a resposta for um valor único, escreva em uma única linha, por exemplo: <b>Gastos totais em maio:</b> -R$ 26.601,27. **Não utilize a tag <p> neste caso.**
- Se for saldo, escreva: <b>Saldo no período:</b> R$ XXXX,XX, também sem a tag <p>.
- Se for uma lista, utilize <ul> e <li>, com títulos ou categorias em <b>. Exemplo:
<b>Top categorias 2025:</b>
<ul>
    <li>Categoria x: R$ 123,45</li>
    <li>Categoria y: R$ 678,90</li>
</ul>
- Sempre use valores no formato de moeda brasileira: R$ 1.234,56 ou -R$ 1.234,56.
- Avalie se é necessário incluir o ano na resposta para melhor compreensão.
- Se não houver resultados, explique que não há dados para esse período, sem usar <p>.
- Não adicione explicações extras, apenas a resposta formatada.
- Não utilize emojis.
- Não utilize a tag <p> para respostas curtas (uma linha). Só utilize <ul>, <li>, <b>, <br> ou texto puro.
"""
)

def montar_pipeline_llm(pergunta_usuario: str):
    prompt = prompt_pipeline_llm.format(
        data_atual=data_atual,
        indices=indices,
        pergunta_usuario=pergunta_usuario
    )

    response = call_llm(model_llm, 0, prompt)

    # Remove quebras de linha para facilitar regex
    response_flat = re.sub(r"\s+", " ", response)

    # Regex espera um JSON com "collection" e "pipeline"
    match = re.search(r'(\{.*"collection"\s*:\s*".+?",\s*"pipeline"\s*:\s*\[.*?\]\s*\})', response_flat)
    if not match:
        raise Exception(f"A LLM não retornou um JSON válido com collection e pipeline. Retorno: {response}")

    print(f"Pipeline gerada: {match.group(1)}")
    return match.group(1)

def ajustar_datas_no_pipeline(pipeline):
    for etapa in pipeline:
        if "$match" in etapa and "data" in etapa["$match"]:
            data_filter = etapa["$match"]["data"]
            if isinstance(data_filter, dict):
                for op in ["$gte", "$lte", "$gt", "$lt", "$eq"]:
                    if op in data_filter and isinstance(data_filter[op], str):
                        dt = datetime.fromisoformat(data_filter[op])
                        data_filter[op] = dt
            elif isinstance(data_filter, str):
                etapa["$match"]["data"] = datetime.fromisoformat(data_filter)
    return pipeline

def validar_pipeline(pipeline):
    # Garante que seja lista de dicts, $match seja primeiro, $limit último (se usado)
    if not isinstance(pipeline, list) or not all(isinstance(e, dict) for e in pipeline):
        return False, "Pipeline deve ser uma lista de etapas dict."
    etapas = list(pipeline)
    if any("$match" in etapa for etapa in etapas):
        if "$match" not in etapas[0]:
            return False, "Se houver, $match deve ser a primeira etapa."
    if any(k not in ["$match", "$group", "$count", "$sort", "$limit","$project"] for etapa in etapas for k in etapa.keys()):
        return False, "Só são permitidos $match, $group, $count, $sort, $limit, $project."
    if any("$limit" in etapa for etapa in etapas[:-1]):
        return False, "$limit só pode ser a última etapa."
    return True, None

def executar_pipeline(pipeline, collection):
    try:       
        resultado = list(db[collection].aggregate(pipeline))
        print(f"Resultado pipeline: {resultado}")
        resultado_serializado = [serializar_mongo(doc.copy()) for doc in resultado]
        print(f"Resultado pipeline serializado: {resultado_serializado}")
        return resultado_serializado
    except Exception as e:
        raise Exception(f"Falha na execução de pipeline no mongoDb. Collection: {collection} | Pipeline: {pipeline}. Mensagem de erro: {e}")

def agente_interpretar_resultado_mongo(pergunta, resultado):
    prompt = prompt_interpretar_resultado.format(
        data_atual=data_atual,
        pergunta=pergunta,
        resultado=json.dumps(resultado, indent=2, ensure_ascii=False)
    )
    resposta = call_llm(model_llm, 0, prompt)
    return resposta
