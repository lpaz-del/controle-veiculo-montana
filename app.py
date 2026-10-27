import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# ==================================================
# CONFIGURAÇÕES
# ==================================================
st.set_page_config(page_title="Controle de Veículo Granado", layout="centered")
st.title("Controle de Veículo Granado")

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
NOME_PLANILHA = "CONTROLE DE UTILIZAÇÃO DO VEÍCULO MONTANA 2026"
ID_PLANILHA = "1GJ6mor6s3-2CKxU_Rlt9_Dtv-b_G0t5atRW5QY1gZ2c"
NOME_ABA_POLITICA = "Política de Uso de Veículos"

# Colunas da planilha:
# A DATA | B MOTORISTA | C DESTINO | D HORA SAÍDA | E KM SAÍDA
# F HORA CHEGADA | G KM CHEGADA | H PROBLEMAS SAÍDA
# I PROBLEMAS RETORNO | J ACEITE POLÍTICA | K VERSÃO POLÍTICA
# L DATA/HORA ACEITE | M reservado (sem envio de e-mail por enquanto)
# N NÍVEL DE COMBUSTÍVEL NA CHEGADA

NOME_ABA_AUTORIZADOS = "Autorizados "  # Espaço final presente no nome real da guia
OPCAO_MOTORISTA = "Selecione o motorista..."
OPCAO_COMBUSTIVEL = "Selecione o nível de combustível..."
NIVEIS_COMBUSTIVEL = [
    OPCAO_COMBUSTIVEL,
    "Vazio (Reserva)",
    "Menos de meio Tanque 1/4",
    "Meio Tanque (1/2)",
    "Mais de meio Tanque 3/4",
    "Cheio",
]



# ==================================================
# CONEXÃO COM GOOGLE SHEETS
# ==================================================
@st.cache_resource
def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    # No Streamlit Cloud, as credenciais ficam em Settings > Secrets.
    # Localmente, continua usando o arquivo credenciais.json.
    if "gcp_service_account" in st.secrets:
        dados_credenciais = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            dados_credenciais, scope
        )
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "credenciais.json", scope
        )
    client = gspread.authorize(creds)
    planilha = client.open_by_key(ID_PLANILHA)
    aba_controle = planilha.sheet1
    aba_politica = planilha.worksheet(NOME_ABA_POLITICA)
    aba_autorizados = planilha.worksheet(NOME_ABA_AUTORIZADOS)
    return aba_controle, aba_politica, aba_autorizados


# ==================================================
# MOTORISTAS AUTORIZADOS
# ==================================================
def carregar_motoristas(aba_autorizados):
    nomes = aba_autorizados.col_values(2)[6:]
    lista = [OPCAO_MOTORISTA]
    vistos = set()
    for valor in nomes:
        nome = " ".join(str(valor).split())
        if nome and nome not in vistos and nome != OPCAO_MOTORISTA:
            vistos.add(nome)
            lista.append(nome)
    return lista


# ==================================================
# POLÍTICA
# ==================================================
def carregar_politica(aba_politica):
    dados_politica = aba_politica.get_all_values()
    linhas = []
    for linha in dados_politica:
        texto_linha = " ".join(
            str(celula).strip() for celula in linha if str(celula).strip()
        )
        if texto_linha:
            linhas.append(texto_linha)
    texto_completo = "\n\n".join(linhas).strip()
    if not texto_completo:
        raise ValueError("A aba da política está vazia. Preencha a política no Google Sheets.")
    versao = hashlib.sha256(texto_completo.encode("utf-8")).hexdigest()
    return texto_completo, versao


# ==================================================
# QUILOMETRAGEM / PENDÊNCIA
# ==================================================
def buscar_ultimo_km_retorno(dados):
    for indice, linha in reversed(list(enumerate(dados[1:], start=2))):
        if len(linha) <= 6:
            continue
        km_texto = str(linha[6]).strip()
        if not km_texto:
            continue
        try:
            return int(float(km_texto.replace(",", "."))), indice
        except (ValueError, TypeError):
            continue
    return 0, 0


def buscar_saida_pendente(dados):
    # Procura da linha mais recente para a mais antiga.
    for indice, linha in reversed(list(enumerate(dados[1:], start=2))):
        if not linha or not (linha[0].strip() if len(linha) > 0 else ""):
            continue
        hora_chegada = linha[5].strip() if len(linha) > 5 else ""
        if not hora_chegada:
            motorista = linha[1] if len(linha) > 1 else ""
            return linha, motorista, indice
    return None, "", None


# ==================================================
# EXECUÇÃO
# ==================================================
try:
    sheet, aba_politica, aba_autorizados = conectar_sheets()
    LISTA_MOTORISTAS = carregar_motoristas(aba_autorizados)
    dados = sheet.get_all_values()
    politica_texto, versao_politica = carregar_politica(aba_politica)
    linha_pendente, motorista_pendente, index_pendente = buscar_saida_pendente(dados)
    ultimo_km_retorno, linha_km_referencia = buscar_ultimo_km_retorno(dados)

    aba_saida, aba_retorno = st.tabs(["Saída", "Retorno"])

    # --------------------------------------------------
    # SAÍDA
    # --------------------------------------------------
    with aba_saida:
        st.subheader("Registro de Saída")

        if linha_pendente:
            st.error("⚠️ VEÍCULO EM USO!")
            hora_saida_pendente = linha_pendente[3] if len(linha_pendente) > 3 else ""
            km_saida_pendente = linha_pendente[4] if len(linha_pendente) > 4 else ""
            st.warning(
                f"O veículo está em uso por **{motorista_pendente}** "
                f"(saída às {hora_saida_pendente}, KM {km_saida_pendente})."
            )
            st.info("O motorista anterior precisa registrar o retorno antes de uma nova saída.")
        else:
            with st.form("form_saida", clear_on_submit=True):
                st.markdown("### Dados da utilização")
                agora = datetime.now(FUSO_HORARIO)
                st.text_input("Data da Saída", value=agora.strftime("%d/%m/%Y"), disabled=True)
                st.text_input("Hora de Saída", value=agora.strftime("%H:%M:%S"), disabled=True)

                motorista = st.selectbox("Nome do Motorista:", LISTA_MOTORISTAS)
                st.markdown("### Quilometragem")
                st.caption(
                    "O KM inicial é preenchido com o último retorno registrado. "
                    "Confira o painel do veículo e ajuste se necessário."
                )
                km_saida = st.number_input(
                    "KM de Saída:", min_value=0, value=ultimo_km_retorno,
                    step=1, key=f"km_saida_{linha_km_referencia}"
                )
                if linha_km_referencia:
                    st.info(f"Último KM de retorno registrado: {ultimo_km_retorno:,}".replace(",", "."))
                else:
                    st.info("Ainda não existe KM de retorno registrado. Informe o KM atual do veículo.")

                destino = st.text_input("Destino:")
                problemas_saida = st.text_area("Problemas / Observações na saída:")

                st.markdown("---")
                st.markdown("### Política de Uso de Veículos")
                with st.expander("📄 Ver política de utilização do veículo"):
                    st.text(politica_texto)

                aceite = st.checkbox(
                    "Declaro estar ciente das políticas de utilização do veículo."
                )
                submetido_saida = st.form_submit_button("Registrar Saída")

                if submetido_saida:
                    if motorista == OPCAO_MOTORISTA:
                        st.warning("Selecione o motorista.")
                    elif not destino.strip():
                        st.warning("Informe o destino.")
                    elif not aceite:
                        st.warning("É necessário aceitar a política para continuar.")
                    elif km_saida < ultimo_km_retorno:
                        st.warning("O KM de saída não pode ser menor que o último KM de retorno registrado.")
                    else:
                        agora_oficial = datetime.now(FUSO_HORARIO)
                        nova_linha = [
                            agora_oficial.strftime("%d/%m/%Y"),  # A DATA
                            motorista,                           # B MOTORISTA
                            destino.strip(),                     # C DESTINO
                            agora_oficial.strftime("%H:%M:%S"),  # D HORA SAÍDA
                            int(km_saida),                       # E KM SAÍDA
                            "",                                  # F HORA CHEGADA
                            "",                                  # G KM CHEGADA
                            problemas_saida.strip(),             # H PROBLEMAS SAÍDA
                            "",                                  # I PROBLEMAS RETORNO
                            "SIM",                               # J ACEITE POLÍTICA
                            versao_politica,                     # K VERSÃO POLÍTICA
                            agora_oficial.strftime("%d/%m/%Y %H:%M:%S"),  # L DATA/HORA ACEITE
                            "",                                  # M STATUS EMAIL
                        ]
                        sheet.append_row(nova_linha, value_input_option="USER_ENTERED")
                        st.success("Saída registrada com sucesso!")
                        st.rerun()

    # --------------------------------------------------
    # RETORNO
    # --------------------------------------------------
    with aba_retorno:
        st.subheader("Registro de Retorno")
        if not linha_pendente:
            st.info("Não há registros de saída pendentes de retorno no momento.")
        else:
            st.write(f"**Finalizar utilização em aberto de:** {motorista_pendente}")
            km_saida_registrado = linha_pendente[4] if len(linha_pendente) > 4 else "0"
            st.info(f"KM registrado na saída: {km_saida_registrado}")

            with st.form("form_retorno", clear_on_submit=True):
                agora_retorno = datetime.now(FUSO_HORARIO)
                st.text_input("Hora do Retorno", value=agora_retorno.strftime("%H:%M:%S"), disabled=True)
                km_chegada = st.number_input("KM de Retorno:", min_value=0, step=1)
                problemas_retorno = st.text_area("Problemas/Avarias constatados no retorno (se houver):")
                nivel_combustivel = st.selectbox("Nível de Combustível na Chegada", NIVEIS_COMBUSTIVEL)
                submetido_retorno = st.form_submit_button("Registrar Retorno")

                if submetido_retorno:
                    try:
                        km_saida_numero = int(float(str(km_saida_registrado).replace(",", ".")))
                    except (ValueError, TypeError):
                        km_saida_numero = 0

                    if km_chegada < km_saida_numero:
                        st.error("O KM de retorno não pode ser menor que o KM de saída.")
                    elif nivel_combustivel == OPCAO_COMBUSTIVEL:
                        st.warning("Selecione o nível de combustível na chegada.")
                    else:
                        hora_retorno_oficial = datetime.now(FUSO_HORARIO).strftime("%H:%M:%S")

                        # Atualiza apenas F, G, I e N, preservando as demais colunas.
                        sheet.batch_update([
                            {"range": f"F{index_pendente}:G{index_pendente}", "values": [[hora_retorno_oficial, int(km_chegada)]]},
                            {"range": f"I{index_pendente}", "values": [[problemas_retorno.strip()]]},
                            {"range": f"N{index_pendente}", "values": [[nivel_combustivel]]},
                        ], value_input_option="USER_ENTERED")

                        st.success("Retorno registrado com sucesso!")
                        st.rerun()

except Exception as e:
    st.error(f"Erro ao conectar com a planilha ou carregar os dados: {e}")
