from core import (
    interpretar_mensagem_llm, 
    insert_transaction_to_mongo, 
    formatar_valor_brl,
    call_llm
)
from datetime import datetime
import os
from agent_data_analisys import montar_pipeline_llm, validar_pipeline, ajustar_datas_no_pipeline, executar_pipeline, agente_interpretar_resultado_mongo
import json
from pymongo import MongoClient
from agent_grafico import agente_gerar_grafico, avaliar_necessidade_grafico
from langchain.prompts import PromptTemplate

model_llm = "gpt-4.1-mini"

# Prompt para rotear intenção do usuário
prompt_rotear_intencao = PromptTemplate(
    input_variables=["texto"],
    template="""
Você é um assistente financeiro.
Sua tarefa é analisar a mensagem do usuário e indicar, com base apenas no conteúdo, qual é a intenção principal da mensagem. Escolha APENAS uma das três opções abaixo e responda SOMENTE com o valor correspondente:

- "analise": se o usuário está perguntando ou solicitando análise de dados financeiros (por exemplo: consultas, perguntas, pedidos de relatório ou resumo de informações, perguntas com '?').
- "insercao": se o usuário está enviando uma nova transação financeira (despesa, receita, valor gasto ou recebido, lançamento de registro, frase contendo valor numérico a ser anotado).
- "reportar_erro": se o usuário está reportando algum erro, falha ou comportamento inesperado.
- "desconhecido": se a mensagem não se encaixar em nenhuma das opções anteriores.

Exemplos:
- "Quais foram meus gastos este mês?" -> analise
- "Recebi 100 reais da Ana" -> insercao
- "20 abc" - > insercao
- "Nesse caso deveria ter reconhecido que era uma transação" -> erro
- "Reportar falha: ..." -> erro
- "Bom dia" -> desconhecido

Mensagem do usuário:
"{texto}"

Responda apenas com uma das opções: analise, insercao, reportar_erro, desconhecido.
"""
)

# Prompt para interpretação de erro (system_role)
prompt_registrar_erro = PromptTemplate(
    input_variables=[],
    template=(
        "Você é um assistente que interpreta mensagens de erro técnicas e relatos de usuários."
        " Para cada mensagem recebida, gere um resumo estruturado contendo:"
        " - 'descricao': uma breve explicação clara do erro ou problema."
        " - 'tipo': classifique o erro."
        " Responda sempre em JSON, exemplo:"
        " {\"descricao\": \"Não foi possível conectar ao banco MongoDB.\", \"tipo\": \"tecnico\"}"
    )
)

def rotear_intencao_usuario(texto: str):
    prompt = prompt_rotear_intencao.format(texto=texto)
    response = call_llm(model_llm, 0, prompt)
    # Garante que só retorna os valores esperados
    if response in {"analise", "insercao", "reportar_erro", "desconhecido"}:
        return response
    return "desconhecido"

def processar_nova_transacao(text, user, timestamp, message_id):
    resultado = interpretar_mensagem_llm(text)
    resultado["user"] = user
    resultado["data"] = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    resultado["message_id"] = message_id

    insert_transaction_to_mongo(resultado)

    valor_formatado = formatar_valor_brl(resultado['valor'])
    resposta_usuario = (
        f"Registrado com sucesso: {resultado['tipo']} de R$ {valor_formatado} em "
        f"{resultado['estabelecimento']} (Categoria: {resultado['categoria'] or 'N/I'})"
    )
    return resposta_usuario

def agente_consulta_dados(pergunta_usuario: str):
    response = montar_pipeline_llm(pergunta_usuario)
    jObjResponse = json.loads(response)
    pipeline = jObjResponse["pipeline"]
    collection = jObjResponse["collection"]
    isValid, err = validar_pipeline(pipeline)
    if not isValid:
        raise Exception(err)
    pipeline = ajustar_datas_no_pipeline(pipeline)
    resultado = executar_pipeline(pipeline, collection)
    resposta = agente_interpretar_resultado_mongo(pergunta_usuario, resultado)
    
    if avaliar_necessidade_grafico(pergunta_usuario, resultado):
        figure_dict = agente_gerar_grafico(pergunta_usuario, resultado)
    else:
        figure_dict = None
        
    return {
        "mensagem": resposta,
        "grafico": figure_dict
    }

def registrar_erro_mongo(mensagem: str, reportedBy: str):
    """
    Interpreta a mensagem de erro via LLM, gera um resumo estruturado e salva na collection 'errors'.
    """
    system_role = prompt_registrar_erro.format()
    user_prompt = f"Mensagem de erro para interpretar:\n{mensagem}"
    resposta = call_llm(
        model=model_llm,
        temperature=0,
        user_prompt=user_prompt,
        system_role=system_role
    )

    # Extrai os campos do JSON retornado pela LLM
    try:
        erro_info = json.loads(resposta)
        descricao = erro_info.get("descricao", mensagem)
        tipo = erro_info.get("tipo", "tecnico")
    except Exception:
        # Fallback: se a LLM não retornar JSON corretamente
        descricao = mensagem
        tipo = "Unknown"

    doc = {
        "descricao": descricao,
        "tipo": tipo,
        "reportado_por": reportedBy,
        "data": datetime.now(),
        "status": "New"
    }

    # Salva no MongoDB (collection 'errors')
    client = MongoClient(os.environ["MONGO_URI"])
    db = client["financebot"]
    db["errors"].insert_one(doc)
    
    return doc
