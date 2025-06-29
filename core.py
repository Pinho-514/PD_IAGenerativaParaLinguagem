from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from datetime import datetime, timedelta
from pymongo import MongoClient
import hashlib
import json
import os

mongo_client = MongoClient(os.environ["MONGO_URI"])
db = mongo_client["financebot"]
db_transactions = db["transactions"]
db_categories = db["categories"]

model_llm = "gpt-4.1-mini"


_llm_cache = {}

def get_llm(model: str, temperature: float):
    """
    Retorna um ChatOpenAI já instanciado com model/temperature.
    Reusa o mesmo objeto se os parâmetros forem iguais.
    """
    key = (model, temperature)
    if key not in _llm_cache:
        _llm_cache[key] = ChatOpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            model=model,
            temperature=temperature
        )
    return _llm_cache[key]

def validate_request(requestDescription, response):
    if response.status_code >= 200 and response.status_code < 300:
        return True
    else:
        raise Exception(f"Erro no request {requestDescription}. Status {response.status_code}, Message: {response.text}")

def serializar_mongo(doc):
    doc["_id"] = str(doc["_id"])
    if isinstance(doc.get("data"), datetime):
        doc["data"] = doc["data"].strftime("%Y-%m-%d")
    return doc

def buscar_categoria_por_transacoes(estabelecimento: str, dias: int = 30) -> str | None:
    data_limite = datetime.now() - timedelta(days=dias)
    resultado = db_transactions.find_one(
        {"estabelecimento": estabelecimento.lower(), "data": {"$gte": data_limite}},
        sort=[("data", -1)]
    )
    return resultado.get("categoria") if resultado else None

def buscar_categorias_existentes():
    return list(db_categories.find({}, {"_id": 0, "nome": 1, "descricao": 1}))


def resumir_prompt(prompt_text, n=400):
    head = prompt_text.strip().replace("\n", " ")[:n]
    tam = len(prompt_text)
    hash_prompt = hashlib.md5(prompt_text.encode()).hexdigest()[:8]
    return f"{head}... [len={tam}, hash={hash_prompt}]"

def call_llm(model: str, temperature: float, user_prompt: str, system_role: str = None, debug=False) -> str:
    print("\n[Agente] 🚀 Iniciando execução do agente LLM...")

    extra_instruction = (
        "IMPORTANTE: Caso a solicitação a seguir peça uma resposta em formato JSON, Nunca use blocos markdown, crases (```), comentários ou qualquer formatação extra. "
        "Responda apenas com o JSON puro, sem ```json, sem crases ou qualquer marcação."
    )

    if not system_role or not system_role.strip():
        system_role_final = extra_instruction
    else:
        system_role_final = system_role.strip() + "\n" + extra_instruction

    prompt_template = PromptTemplate(
        input_variables=["system_role", "user_prompt"],
        template="System: {system_role}\nUsuário: {user_prompt}"
    )
    prompt_text = prompt_template.format(system_role=system_role_final, user_prompt=user_prompt)
    
    prompt_resumido = resumir_prompt(prompt_text)
    print(f"[Agente] ✉️ Prompt enviado ao modelo: {prompt_resumido}")
    if debug:
        print(f"[Agente][DEBUG] Prompt completo:\n{prompt_text}\n---")

    llm = get_llm(model, temperature)
    response = llm.invoke(prompt_text)
    final_response = response.content.strip() if hasattr(response, "content") else str(response).strip()
    print(f"[Agente] ✅ Resposta recebida do modelo:\n---\n{final_response}\n---\n")
    return final_response

def insert_transaction_to_mongo(transaction: dict) -> None:
    transaction["estabelecimento"] = transaction["estabelecimento"].lower()
    transaction["data"] = datetime.strptime(transaction["data"], "%Y-%m-%d")
    db_transactions.insert_one(transaction)

def get_existing_category_by_llm(user_message: str, categorias_existentes: list[str]) -> dict:
    user_prompt = f"""Mensagem do usuario: {user_message}\nCategorias existentes:\n"""
    for item in categorias_existentes:
        user_prompt += f"- {item['nome']}: {item['descricao']}\n"

    system_role = """Você analisa se o estabelecimento se encaixa em alguma categoria existente.
                    Retorne:
                    {{
                    "foundCategory": true,
                    "categoryName": "nome_da_categoria"
                    }}
                    Se não for possível, retorne:
                    {{
                    "foundCategory": false,
                    "categoryName": null
                    }}"""

    response = call_llm(model_llm, 0, user_prompt, system_role)
    return json.loads(response)

def create_new_category_by_llm(user_message: str) -> dict:
    prompt = f"""Mensagem do usuario: {user_message}"""

    system_role = """Crie uma nova categoria com base na mensagem do usuario. 
                    Retorne:
                    {{
                    "addCategory": true,
                    "categoryName": "nome_da_categoria",
                    "categoryDescription": "descrição da categoria"
                    }}
                    Se não for possível sugerir uma nova categoria, retorne:
                    {{
                    "addCategory": false,
                    "categoryName": null,
                    "categoryDescription": null
                    }}"""

    response = call_llm(model_llm, 0, prompt, system_role)
    return json.loads(response)

def interpretar_mensagem_llm(texto):
    system_role = """Você é um assistente do controle financeiro e deve interpretar as mensagens do usuário.
                    As mensagens representam receitas ou despesas pessoais e podem conter valor, categoria, data e descrição.
                    Regras:
                    - Se houver "+" ou palavras como 'recebi', 'salário', 'entrada', é receita.
                    - Caso contrário, é despesa.
                    - Valores podem vir com ou sem “R$” e com ou sem vírgula e ponto. Caso o valor inclua centavos, ele deve ser separado por vírgula. 
                    - Exemplos válidos: 30, 30,00, 30,80, R$30, R$ 30,50.
                    - Se houver apenas um número, ele É o valor.
                    - Se a palavra "categoria" aparecer, deve atualizar o mapeamento: <estabelecimento> => <categoria>.
                    - Caso não haja "categoria", assuma que as palavras são o estabelecimento.
                    - A categoria pode ser conhecida (mapeada) ou estimada a partir do contexto.
                    - A data, se estiver presente, está no formato dia/mês[/ano] e deve ser usada. Caso contrário, use a data da mensagem.
                    - O valor é um campo obrigatório.
                    - A saída deve ser um JSON com os campos:
                    tipo, valor, estabelecimento, categoria, descricao (opcional), data (AAAA-MM-DD).
                    """
    print(f"Start interpretar_mensagem_llm. Mensagem: {texto}")
    user_prompt = f"Mensagem: \"{texto}\"\nHoje é {datetime.now().strftime('%Y-%m-%d')}. Responda com apenas o JSON no padrão descrito."

    response = call_llm(model_llm, 0, user_prompt, system_role)

    if not response:
        return {"erro": "Não foi possível interpretar."}
    dados = json.loads(response)

    categoria = None

    if "categoria" in texto.lower():
        print("Mensagem contem 'categoria'")
        categoria = dados.get("categoria")
        estabelecimento = dados["estabelecimento"].lower()
        categoryExists = db_categories.find_one({"nome": categoria})
        if not categoryExists:
            print("Categoria não existe, vou pensar em uma descrição")
            user_prompt = f"Crie uma descrição curta para a categoria '{categoria}'. O nome do estabelecimento é '{estabelecimento}', mas só leve em consideração caso seja significativo."
            system_role = "Você gera descrições curtas para categorias de gastos pessoais."
            description = call_llm(model_llm, 0, user_prompt, system_role)
            print("Inserindo categoria no db")
            db_categories.insert_one({
                "nome": categoria,
                "descricao": description
            })
        else:
            print(f"categoria já existe {categoria}")
    else:
        print("Buscando categoria em outras transacoes")
        categoria = buscar_categoria_por_transacoes(dados["estabelecimento"])
        if categoria:
            print(f"categoria encontrada: {categoria}")            
        else:
            print(f"categoria não encontrada, vou tentar reconhecer nas categorias existentes")            
            categoria = None
            categorias_existentes = buscar_categorias_existentes()
            result = get_existing_category_by_llm(dados["estabelecimento"], categorias_existentes)
            if result["foundCategory"]:
                print(f"categoria encontrada: {result['categoryName']}")
                categoria = result["categoryName"]
            else:
                print(f"categoria não encontrada, vou tentar criar uma nova")
                nova_categoria = create_new_category_by_llm(dados["estabelecimento"])
                if nova_categoria["addCategory"]:
                    print(f"criando categoria: {nova_categoria['categoryName']}")
                    categoria = nova_categoria["categoryName"]
                    print(f"Criando nova categoria: {categoria} - {nova_categoria['categoryDescription']}")
                    db_categories.insert_one({
                        "nome": categoria,
                        "descricao": nova_categoria["categoryDescription"]
                    })
    dados["categoria"] = categoria
    return dados

def formatar_valor_brl(valor):
    print(f"formatando valor: {valor}")
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
