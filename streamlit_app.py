import streamlit as st
import time, uuid

#Load .env
from dotenv import load_dotenv
load_dotenv(override=True)

# Import functions
from features import (
    agente_consulta_dados,
    rotear_intencao_usuario,
    processar_nova_transacao,
    registrar_erro_mongo,
)

# --- Estilo visual para balões de conversa ---
def mensagem_usuario(mensagem):
    st.markdown(
        f"""
        <div style='background-color:#DCF8C6; border-radius:10px; padding:10px 15px; margin:5px 0; text-align:right; max-width:70%; margin-left:30%;'>
            <span style='color:#222;font-size:16px;'>{mensagem}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

def mensagem_agente(mensagem):
    st.markdown(
        f"""
        <div style='background-color:#F1F0F0; border-radius:10px; padding:10px 15px; margin:5px 0; text-align:left; max-width:70%;'>
            <span style='color:#111;font-size:16px;'>{mensagem}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- Início do app ---
st.set_page_config(page_title="Assistente Financeiro", page_icon="💸", layout="centered")

st.title("💸 Controle financeiro inteligente")
st.caption("Converse sobre finanças. Adicione despesas, consulte dados ou relate problemas.")

# Inicia sessão para histórico
if "historico" not in st.session_state:
    st.session_state.historico = []  # Lista de (autor, mensagem)
    print("Histórico de conversa iniciado.")

# Input de mensagem
with st.form(key="form_chat", clear_on_submit=True):
    user_message = st.text_input("Digite sua mensagem...", max_chars=400)
    enviar = st.form_submit_button("Enviar")

# Processamento ao enviar mensagem
if enviar and user_message.strip():
    print(f"[Usuário] {user_message}")
    st.session_state.historico.append(("usuário", user_message))

    try:
        # --- Integração com suas funções ---
        print("Analisando intenção do usuário...")
        feature = rotear_intencao_usuario(user_message)
        print(f"Intenção identificada: {feature}")

        if feature == "analise":
            print("Chamando agente_consulta_dados...")
            resposta = agente_consulta_dados(user_message)
            print(f"[Agente - consulta]: {resposta}")

        elif feature == "insercao":
            user = "usuario_streamlit"
            timestamp = int(time.time())
            message_id = str(uuid.uuid4())
            print("Chamando processar_nova_transacao...")
            resposta = processar_nova_transacao(user_message, user, timestamp, message_id)
            print(f"[Agente - insercao]: {resposta}")

        elif feature == "reportar_erro":
            print("Chamando registrar_erro_mongo...")
            resposta = registrar_erro_mongo(user_message, "usuario_streamlit", "id", "usuario_streamlit")
            print(f"[Agente - erro]: {resposta}")
            resposta = {"mensagem": "Seu problema foi registrado, obrigado por avisar!"}
        else:
            print("Intenção não reconhecida.")
            resposta = {"mensagem": "Não entendi sua solicitação. Por favor, explique de outra forma."}
            
    except Exception as e:
        print(f"Erro detectado: {e}")
        resposta = f"Ocorreu um erro interno: {str(e)}"
        try:
            registrar_erro_mongo(f"Erro: {e}", "TechnicalError")
            print("Erro registrado no MongoDB.")
        except Exception as er:
            print(f"Falha ao registrar erro: {er}")
            
    st.session_state.historico.append(("agente", resposta))

# Mostra histórico (tudo invertido para chat ficar do mais antigo pro mais novo)
max_mensagens = 10
historico_limitado = st.session_state.historico[-max_mensagens:]
for idx, (autor, conteudo) in enumerate(historico_limitado):
    if isinstance(conteudo, str):
        conteudo = {"mensagem": conteudo, "grafico": None}
    if autor == "usuário":
        mensagem_usuario(conteudo["mensagem"])
    else:
        mensagem_agente(conteudo["mensagem"])
        if conteudo.get("grafico"):
            st.plotly_chart(conteudo["grafico"], use_container_width=True, key=f"grafico_{idx}")
            
# Rodapé
st.markdown("<hr>", unsafe_allow_html=True)
st.caption("Desenvolvido por Felipe Saul Zebulun • Assistente Financeiro 2025")
