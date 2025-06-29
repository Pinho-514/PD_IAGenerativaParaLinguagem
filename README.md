# Assistente de Controle Financeiro

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.34.0-brightgreen.svg)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas%2Flocal-green.svg)
![LangChain](https://img.shields.io/badge/LangChain-0.1-green.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-API-blue.svg)
![Plotly](https://img.shields.io/badge/Plotly-5.x-lightgrey.svg)

---

## 1. Descrição da Aplicação e Objetivo

O **chat financeiro** é voltado para registro, consulta e análise de receitas e despesas pessoais. A interface com o usuário é feita pelo **Streamlit**, a persistência dos dados no **MongoDB** e a interpretação de linguagem natural e processamento de dados feita por **LLM** (OpenAI via LangChain).

Permite:
- Registrar transações financeiras via texto livre.
- Consultar análises e relatórios financeiros por linguagem natural.
- Responder ao usuário com gráficos automáticos.
- Faz o controle de erros da aplicação de forma automática e, também, a partir do input do usuário.

**Objetivos principais:**
- Automatizar o controle financeiro pessoal de modo simples e interativo.
- Permitir consulta e registro usando linguagem natural, sem comandos rígidos, focando principalmente na praticidade de uso.
- Visualizar resultados e gráficos, auxiliando numa percepção mais aprofundada das transações financeiras.

---

## 2. Arquitetura e Componentes

**a) Interface de Usuário (Streamlit)**
- `streamlit_app.py`: O streamlit foi usado para realizar a interação com o usuário. O objetivo por trás dessa aplicação é ter um uso muito simples e direto. Por isso há somente um campo de input e o agente fica com a responsabilidade de interpretar a mensagem e entender a intenção.
O histórico de mensagens aparece com as últimas 10 apenas. A ideia é de uma consulta rápida e imediata, os dados persistem no banco, mas a interação não.
 
**b) Agente Inteligente (LLM via LangChain/OpenAI)**
- Interpreta mensagens para:
    - Identificar intenção (registrar transação, consulta sobre os dados e reportar um erro)
    - Gerar transações estruturadas (Interpretando o valor, se é receita ou despesa, nome do estabelecimento e categoria)
    - Montar pipelines MongoDB (Dessa forma, o agente é capaz de realizar análises complexas não planejadas)
    - Explicar/formatar resultados (HTML/Markdown)
    - Gerar gráficos automaticamente (O agente prepara o JSON de input para o Plotly, de forma que não tem alto consumo de tokens para gerar imagem)

**c) Banco de Dados (MongoDB)**
- Três coleções: `transactions`, `categories`, `errors`
- Índices garantidos via script Python
- Consultas dinâmicas via pipelines gerados pelo LLM

**d) Organização do Código**

```
├── streamlit_app.py         # Interface web (chat)
├── features.py              # Funções principais do agente
├── agent_data_analisys.py   # Lógica de análise, montagem e execução de pipelines de consulta no banco e formatação de resposta
├── agent_grafico.py         # Geração de gráficos
├── core.py                  # Utilitários LLM e MongoDB
├── setup_mongodb.py         # Script de criação de índices/coleções
├── requirements.txt         # Dependências
├── example.env              # Exemplo de configuração do .env
```
---

## 3. Configuração do Ambiente

### Pré-requisitos
- Python >= 3.10
- Conta no MongoDB Atlas ou instância local
- Chave de API da OpenAI

### Passos para configurar

#### a) Clone o repositório:
```bash
git clone <url_do_repositorio>
cd <pasta_do_projeto>
```

#### b) Crie e ative um ambiente virtual:
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

#### c) Instale as dependências:
```bash
pip install -r requirements.txt
```

#### d) Configure o arquivo `.env`:
Crie um arquivo `.env` na raiz com o seguinte conteúdo (edite com suas credenciais):
```env
MONGO_URI=mongodb+srv://USUARIO:SENHA@CLUSTER.mongodb.net/?retryWrites=true&w=majority
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxx
```
(Veja o arquivo `example.env` para referência)

#### e) Configure o MongoDB com índices/coleções:
No MongoDB as collections são criadas automaticamente com a inserção de novos dados, mas é indicado a criação prévia com configuração de índices para garantir o bom funcionamento e eficiencia das consultas.
Execute o script de setup para criar collections e índices necessários:
```bash
python setup_mongodb.py
```
---

## 4. Como Executar

Com o ambiente ativado e configurado, execute o app:
```bash
streamlit run streamlit_app.py
```
- Acesse [http://localhost:8501](http://localhost:8501) no navegador.
- Use o chat para registrar despesas, consultar relatórios ou reportar erros em linguagem natural.

---

## 5. Observações

- Toda manipulação e parsing de prompt LLM usa LangChain e PromptTemplate.
- Toda persistência é feita no MongoDB.
- Não há autenticação de usuário implementada (identificador padrão: "usuario_streamlit").
- Gráficos são exibidos automaticamente no chat quando o agente entender que agregam valor. Caso queira definir explicitamente se contém ou não gráfico e, qual tipo de gráfico, basta instruir na consulta de dados.
- O histórico da conversa é armazenado somente na sessão Streamlit, não em banco.


## 6. Demonstração

Veja exemplos reais de uso do chat:

![Chat interagindo - Registro de dados](docs/demo_insert_data.png)

*Registro de receitas e despesas*

![Consulta de dados](docs/demo_analisis_1.png)

*Consulta de saldo do dia e top 3 categorias*

![Consulta de dados](docs/demo_analisis_2.png)

*Comparativo de categorias. Gráfico automático*

![Consulta de dados](docs/demo_analisis_3.png)

*Comparativo de categorias. Gráfico escolhido pelo usuário*

## 7. Análise de resultados

O uso de LLM para interpretar as mensagens do usuário permite uma interface mais simples. Eu, pessoalmente, nunca consegui usar ferramentas de controle financeiro por ter muitos campos para preencher.
O ganho fica ainda maior na análise da dados, não sendo necessário prever que consultas os usuários desejam e como deve ser retornado os dados, deixando para a LLM interpretar se deve incluir gráficos e qual tipo de gráfico.
Mas claro, nem sempre a LLM vai ter a melhor escolha de gráficos, o que é facilmente resolvido com uma instrução simples junto com a consulta.

## 8. Melhorias previstas

- Interface com UX mais amigável e instruções gerais do que pode ser feito com a aplicação;
- Refatoração da solução adaptando para o conceito de Clean Architecture;
- Desacoplamento da interface, banco de dados e LLM, possibilitando a migração para outras ferramentas no futuro como WhatsApp, PostgreSQL e Gemini;
- Inclusão de loop de retry na execução geral, considerando que a LLM não tem resultado determinístico;
- Destrinchar as categorias em 2 níveis, categoria e sub-categoria;
- Implementar autenticação para garantir a segurança dos dados, uso de diferentes usuários e persistencia dos dados independente da interface;