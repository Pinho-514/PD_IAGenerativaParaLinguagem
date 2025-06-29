from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.environ["MONGO_URI"])
db = client["financebot"]

#Collection transactions
transactions = db["transactions"]

# Índices simples
transactions.create_index("message_id", unique=True)
transactions.create_index("estabelecimento")
transactions.create_index("categoria")

# Índices compostos: data sempre primeiro
transactions.create_index([("data", 1), ("categoria", 1)])
transactions.create_index([("data", 1), ("estabelecimento", 1)])

#Collection errors
errors = db["errors"]
errors.create_index("tipo")

#Collection categories
categories = db["categories"]
categories.create_index("nome")

print("Índices criados com sucesso!")