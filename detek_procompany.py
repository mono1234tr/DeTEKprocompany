import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import json
from google.oauth2.service_account import Credentials
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Configuración de la página
st.set_page_config(
    page_title="DeTEK PRO COMPANY",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)
# --- AUTENTICACIÓN ---
USUARIO_CORRECTO = "admin"
CONTRASENA_CORRECTA = "1234"

if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.title("Iniciar sesión en DeTEK PRO COMPANY")
    usuario = st.text_input("Usuario")
    contrasena = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if usuario == USUARIO_CORRECTO and contrasena == CONTRASENA_CORRECTA:
            st.session_state['autenticado'] = True
            st.success("Acceso concedido. Cargando app...")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()


# --- VARIABLES DE MODO OFFLINE ---
if 'modo_offline' not in st.session_state:
    st.session_state['modo_offline'] = False
if 'ultimo_error_sheet' not in st.session_state:
    st.session_state['ultimo_error_sheet'] = ''


# --- CACHÉ EN MEMORIA PARA GOOGLE SHEETS (TTL extendido) ---
@st.cache_data(show_spinner=False, ttl=30, max_entries=50)
def cached_get_all_records(sheet_key, worksheet_name):
    try:
        client = get_gspread_client()
        ws = client.open_by_key(sheet_key).worksheet(worksheet_name)
        # Solución robusta: buscar la fila de encabezados correcta en 'Equipos'
        if worksheet_name.lower() == "equipos":
            # Buscar la primera fila que contenga 'Empresa' (ignorando mayúsculas/minúsculas)
            for i in range(1, 11):  # Busca en las primeras 10 filas
                fila = ws.row_values(i)
                if any(str(cell).strip().lower() == "empresa" for cell in fila):
                    header_row = i
                    headers = [h if h else f"col_{idx+1}" for idx, h in enumerate(fila)]
                    break
            else:
                # Si no encuentra, usa la primera fila
                header_row = 1
                headers = ws.row_values(1)
                headers = [h if h else f"col_{idx+1}" for idx, h in enumerate(headers)]
            # Elimina duplicados en headers solo si hay vacíos
            seen = set()
            new_headers = []
            for idx, h in enumerate(headers):
                h_clean = h if h else f"col_{idx+1}"
                while h_clean in seen or h_clean == '':
                    h_clean += f"_{idx+1}"
                seen.add(h_clean)
                new_headers.append(h_clean)
            return ws.get_all_records(expected_headers=new_headers, head=header_row)
        else:
            return ws.get_all_records()
    except Exception as e:
        st.session_state['modo_offline'] = True
        st.session_state['ultimo_error_sheet'] = str(e)
        raise

# --- CACHÉ PARA CLIENTE GSPREAD ---
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    service_account_info = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    SCOPE = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPE)
    return gspread.authorize(creds)

# --- LOGO INICIO ---
import re
def get_drive_thumbnail_url(url):
    """Convierte un enlace de Google Drive a un enlace de thumbnail visualizable."""
    if not isinstance(url, str):
        return url
    patterns = [
        r"/file/d/([\w-]+)",
        r"id=([\w-]+)",
        r"https://drive.google.com/open\?id=([\w-]+)",
        r"https://drive.google.com/uc\?id=([\w-]+)"
    ]
    for pat in patterns:
        match = re.search(pat, url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/thumbnail?id={file_id}"
    return url

logo_url = get_drive_thumbnail_url("https://drive.google.com/uc?export=view&id=1TNWW3yHkS9EGFIL3XbETPCcIDBkbQXTH")
st.markdown(f"""
    <div style='display: flex; justify-content: center; align-items: center; margin-bottom: 1em;'>
        <img src='{logo_url}' width='180' style='display: block;'/>
    </div>
""", unsafe_allow_html=True)
def get_or_create_sheet_tareas(client, SHEET_ID):
    try:
        sheet_tareas = client.open_by_key(SHEET_ID).worksheet("Tareas")
    except:
        sheet_tareas = client.open_by_key(SHEET_ID).add_worksheet(title="Tareas", rows="1000", cols="6")
        sheet_tareas.append_row(["empresa", "tarea", "asignada_por", "fecha_asignacion", "completada", "fecha_completada"])
    return sheet_tareas




# --- CONFIGURACIÓN GOOGLE SHEETS Y DRIVE ---

client = get_gspread_client()
SHEET_ID = "1288rxOwtZDI3A7kuLnR4AXaI-GKt6YizeZS_4ZvdTnQ"
SHEET_ACTAS_ID = "1Vc7XnxhXfuus7WdGOvBjG08cLpW8awO0E7P4b3aLc4A"


# --- INTENTAR CARGAR DATOS DE SHEETS, SI FALLA USAR CACHE Y MODO OFFLINE ---
def cargar_datos_sheet():
    try:
        sheet_registro_data = cached_get_all_records(SHEET_ID, "Hoja 1")
        sheet_empresas_data = cached_get_all_records(SHEET_ID, "Empresas")
        try:
            sheet_chat_data = cached_get_all_records(SHEET_ID, "Chat")
        except:
            ws = client.open_by_key(SHEET_ID).add_worksheet(title="Chat", rows="1000", cols="4")
            ws.append_row(["fecha", "usuario", "mensaje", "empresa"])
            sheet_chat_data = []
        try:
            sheet_tareas_data = cached_get_all_records(SHEET_ID, "Tareas")
        except:
            ws = client.open_by_key(SHEET_ID).add_worksheet(title="Tareas", rows="1000", cols="6")
            ws.append_row(["empresa", "tarea", "asignada_por", "fecha_asignacion", "completada", "fecha_completada"])
            sheet_tareas_data = []
        # Cargar datos de actas de entrega
        try:
            sheet_actas_data = cached_get_all_records(SHEET_ACTAS_ID, "actas de entregas diligenciadas")
        except Exception as e:
            sheet_actas_data = []
            st.session_state['error_actas'] = str(e)
        st.session_state['modo_offline'] = False
        st.session_state['ultimo_error_sheet'] = ''
        return sheet_registro_data, sheet_empresas_data, sheet_chat_data, sheet_tareas_data, sheet_actas_data
    except Exception as e:
        st.session_state['modo_offline'] = True
        st.session_state['ultimo_error_sheet'] = str(e)
        # Intentar usar datos cacheados si existen
        sheet_registro_data = st.cache_data.get_cached_value(cached_get_all_records, (SHEET_ID, "Hoja 1")) or []
        sheet_empresas_data = st.cache_data.get_cached_value(cached_get_all_records, (SHEET_ID, "Empresas")) or []
        sheet_chat_data = st.cache_data.get_cached_value(cached_get_all_records, (SHEET_ID, "Chat")) or []
        sheet_tareas_data = st.cache_data.get_cached_value(cached_get_all_records, (SHEET_ID, "Tareas")) or []
        sheet_actas_data = st.cache_data.get_cached_value(cached_get_all_records, (SHEET_ACTAS_ID, "actas de entregas diligenciadas")) or []
        st.session_state['error_actas'] = str(e)
        return sheet_registro_data, sheet_empresas_data, sheet_chat_data, sheet_tareas_data, sheet_actas_data

sheet_registro_data, sheet_empresas_data, sheet_chat_data, sheet_tareas_data, sheet_actas_data = cargar_datos_sheet()
sheet_tareas = get_or_create_sheet_tareas(client, SHEET_ID)
try:
    sheet_chat = client.open_by_key(SHEET_ID).worksheet("Chat")
except gspread.exceptions.APIError as e:
    st.error(f"Error de API al conectar con la hoja 'Chat': {e}. La funcionalidad del chat puede estar limitada.")
    sheet_chat = None # Continuar sin el objeto sheet_chat
except Exception as e:
    st.error(f"No se pudo abrir la hoja 'Chat': {e}. La funcionalidad del chat puede estar limitada.")
    sheet_chat = None # Continuar sin el objeto sheet_chat

sheet_registro = client.open_by_key(SHEET_ID).worksheet("Hoja 1")
# --- AVISO DE MODO OFFLINE Y BOTÓN DE REINTENTO ---
if st.session_state.get('modo_offline', False):
    st.warning(f"No se pudo conectar con Google Sheets. Estás en modo offline temporal.\n\nError: {st.session_state.get('ultimo_error_sheet','')}")
    if st.button("Reintentar conexión con Google Sheets"):
        st.session_state['modo_offline'] = False
        st.rerun()

# --- AVISO DE ERROR EN HOJA DE ACTAS ---
if st.session_state.get('error_actas'):
    st.error(f"⚠️ **Problema con la hoja de actas:** {st.session_state.get('error_actas')}")
    
    # Mostrar email de la cuenta de servicio para compartir
    try:
        service_account_info = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        email_servicio = service_account_info.get("client_email", "No encontrado")
        st.info(f"📧 **Email de tu cuenta de servicio:** `{email_servicio}`")
        st.markdown("👆 **Comparte la hoja de actas con este email** (permisos de Lector)")
    except:
        st.warning("No se pudo obtener el email de la cuenta de servicio")
    
    st.info("💡 **Pasos para solucionar:**")
    st.markdown("""
    1. **Ve a la hoja:** https://docs.google.com/spreadsheets/d/1Vc7XnxhXfuus7WdGOvBjG08cLpW8awO0E7P4b3aLc4A/edit
    2. **Haz clic en "Compartir"** (botón verde)
    3. **Agrega el email de arriba** con permisos de "Lector"
    4. **Verifica que la pestaña se llame:** `actas de entregas diligenciadas`
    5. **Haz clic en "Enviar"**
    """)
    if st.button("🔄 Reintentar conexión con hoja de actas"):
        if 'error_actas' in st.session_state:
            del st.session_state['error_actas']
        st.rerun()

# --- VIDA ÚTIL POR DEFECTO ---
VIDA_UTIL_DEFECTO = 700

# --- NUEVO MODELO: UNA SOLA HOJA 'Equipos' ---
sheet_equipos_data = cached_get_all_records(SHEET_ID, "Equipos")
equipos_df = pd.DataFrame(sheet_equipos_data)
equipos_df.columns = [col.lower().strip() for col in equipos_df.columns]

# --- EMPRESAS ÚNICAS Y ALERTAS ---
empresas_df = pd.DataFrame(sheet_empresas_data)
empresas_df.columns = [col.lower().strip() for col in empresas_df.columns]
empresas_visible = []
empresa_mapa = {}
for _, row in empresas_df.iterrows():
    if 'empresa' in row:
        nombre = row['empresa']
        alerta = ''
        equipos_empresa = equipos_df[equipos_df["empresa"].str.strip().str.lower() == nombre.strip().lower()]
        for _, eq_row in equipos_empresa.iterrows():
            consumibles = [c.strip() for c in str(eq_row.get('consumibles','')).split(",") if c.strip()]
            vida_util_str = str(eq_row.get('vida_util',''))
            vidas_utiles = [int(v.strip()) if v.strip().isdigit() else 700 for v in vida_util_str.split(";")]
            data_registro = pd.DataFrame(sheet_registro_data)
            data_registro.columns = [col.lower().strip() for col in data_registro.columns]
            data_equipo = data_registro[(data_registro["empresa"].str.strip().str.lower() == nombre.strip().lower()) & (data_registro["codigo"] == eq_row['codigo'])] if not data_registro.empty else pd.DataFrame()
            estado_partes = {parte: 0 for parte in consumibles}
            for _, fila in data_equipo.iterrows():
                horas = fila.get("hora de uso", 0)
                try:
                    horas = float(horas)
                except:
                    horas = 0
                partes_cambiadas = str(fila.get("parte cambiada", "")).split(";")
                for parte in consumibles:
                    if parte in partes_cambiadas:
                        estado_partes[parte] = 0
                    else:
                        estado_partes[parte] += horas
            for idx, parte in enumerate(consumibles):
                usadas = estado_partes.get(parte, 0)
                vida_util_val = vidas_utiles[idx] if idx < len(vidas_utiles) else 700
                restantes = max(vida_util_val - usadas, 0)
                if restantes <= 1:
                    alerta = ' 🔴'
                    break
                elif restantes <= 10 and not alerta:
                    alerta = ' 🟡'
            if alerta:
                break
        empresas_visible.append(f"{nombre}{alerta}")
        empresa_mapa[f"{nombre}{alerta}"] = nombre

import streamlit.components.v1 as components

# --- FUNCION SLUGIFY ---
import urllib.parse
def slugify_empresa(nombre):
    return urllib.parse.quote_plus(nombre.strip().replace(' ', '_').lower())

# --- FUNCIÓN PARA BUSCAR ACTAS DE ENTREGA POR OP ---
def buscar_actas_por_op(numero_op, sheet_actas_data):
    """Busca las imágenes del acta de entrega por número de OP - LIMPIO"""
    if not numero_op or not sheet_actas_data:
        return []
    
    actas_df = pd.DataFrame(sheet_actas_data)
    if actas_df.empty:
        return []
    
    # Normalizar nombres de columnas  
    actas_df.columns = [col.lower().strip() for col in actas_df.columns]
    

    
    # Buscar por número de OP en TODAS las columnas posibles
    op_columns = []
    # Primero buscar columnas obvias de OP
    for col in actas_df.columns:
        if any(term in col for term in ['op', 'orden', 'numero', 'no']):
            op_columns.append(col)
    
    # Si no encuentra columnas obvias, usar todas las columnas
    if not op_columns:
        op_columns = actas_df.columns.tolist()

    
    imagenes = []
    
    for col in op_columns:
        # Mostrar algunos valores de ejemplo

        
        
        # Buscar coincidencias exactas
        matching_rows = actas_df[actas_df[col].astype(str).str.strip() == str(numero_op).strip()]
        
        if not matching_rows.empty:

            
            for idx, row in matching_rows.iterrows():

                urls_encontradas = 0
                
                # Buscar CUALQUIER columna que tenga un link de Drive
                for column in row.index:
                    valor = str(row[column]).strip()
                    if valor and 'drive.google.com' in valor.lower():
                        urls_encontradas += 1
                        nombre_amigable = column.replace('_', ' ').replace('-', ' ').title()
                        
                        imagenes.append({
                            'nombre': f"{nombre_amigable} (Fila {idx + 1})",
                            'url': get_drive_direct_url(valor),
                            'columna_original': column
                        })
                        
                    
                

            
            break  # Si encontramos la OP, no buscar en otras columnas
        else:
            pass  # No se encontraron coincidencias en esta columna
    
    return imagenes





# --- LEER EMPRESA DESDE QUERY PARAM (usando st.query_params, API moderna) ---
empresa_slug_param = st.query_params.get("empresa_slug", None)
empresa_idx = 0

# Mostrar selectbox solo en el Panel
panel_dashboard = st.sidebar.radio("Ir a:", ["Panel", "Dashboard"])
if panel_dashboard == "Panel":
    empresa_slug_param = st.query_params.get("empresa_slug", None)
    empresa_idx = 0
    if empresa_slug_param:
        for idx, visible in enumerate(empresas_visible):
            nombre = empresa_mapa[visible]
            if slugify_empresa(nombre) == empresa_slug_param:
                empresa_idx = idx
                break
    seleccion_empresa = st.selectbox("Selecciona la empresa:", empresas_visible, index=empresa_idx, key="empresa_select")
    empresa = empresa_mapa[seleccion_empresa]
    empresa_slug = slugify_empresa(empresa)
    if empresa_slug_param != empresa_slug:
        st.query_params.update({"empresa_slug": empresa_slug})
        st.rerun()
    link_empresa = f"https://detekprocompany.streamlit.app/?empresa_slug={empresa_slug}"
    # ...existing code for Panel...

elif panel_dashboard == "Dashboard":
    st.markdown("##  Dashboard general")

    # Total de empresas y equipos
    total_empresas = len(equipos_df["empresa"].unique())
    total_equipos = len(equipos_df["codigo"].unique())
    st.markdown(f"-  **Empresas registradas:** `{total_empresas}`")
    st.markdown(f"-  **Equipos registrados:** `{total_equipos}`")

    # Partes más cambiadas
    data_registro = pd.DataFrame(sheet_registro_data)
    data_registro.columns = [col.lower().strip() for col in data_registro.columns]
    cambios = data_registro["parte cambiada"].dropna().str.split(";").explode()
    cambios = cambios[cambios.str.strip() != ""]  # eliminar vacíos
    partes_frecuentes = cambios.value_counts().head(5)

    st.markdown("###  Partes más cambiadas")
    for parte, count in partes_frecuentes.items():
        st.markdown(f"- `{parte}`: `{count}` cambios")

    # Consumibles críticos y cerca de cumplir vida útil
    st.markdown("### Estado General de Consumibles")
    
    consumibles_alertas = []

    for _, row in equipos_df.iterrows():
        empresa_k = row.get("empresa", "")
        codigo_k = row.get("codigo", "")
        descripcion_k = row.get("descripcion", "")
        consumibles = [c.strip() for c in str(row.get("consumibles", "")).split(",") if c.strip()]
        vida_util_str = str(row.get("vida_util", ""))
        vidas_utiles = [int(v.strip()) if v.strip().isdigit() else VIDA_UTIL_DEFECTO for v in vida_util_str.split(";")]

        data_registro = pd.DataFrame(sheet_registro_data)
        if not data_registro.empty:
            data_registro.columns = [col.lower().strip() for col in data_registro.columns]

        estado_partes = {parte: 0 for parte in consumibles}
        data_equipo = data_registro[(data_registro["empresa"].str.strip().str.lower() == empresa_k.strip().lower()) & (data_registro["codigo"] == codigo_k)] if not data_registro.empty else pd.DataFrame()
        
        for _, fila in data_equipo.iterrows():
            horas = fila.get("hora de uso", 0)
            try:
                horas = float(horas)
            except (ValueError, TypeError):
                horas = 0
            partes_cambiadas = str(fila.get("parte cambiada", "")).split(";")
            for parte in estado_partes:
                if parte in partes_cambiadas:
                    estado_partes[parte] = 0
                else:
                    estado_partes[parte] += horas

        for idx, parte in enumerate(consumibles):
            usadas = estado_partes.get(parte, 0)
            vida = vidas_utiles[idx] if idx < len(vidas_utiles) else VIDA_UTIL_DEFECTO
            
            if vida == 0: continue

            horas_restantes = vida - usadas
            
            if horas_restantes <= 72:  # Unificamos la condición
                estado_emoji = "🔴" if horas_restantes <= 0 else "🟡"
                info = {
                    "Estado": estado_emoji,
                    "Consumible": parte,
                    "Empresa": empresa_k,
                    "Equipo": f"{codigo_k} - {descripcion_k}",
                    "Horas Usadas": round(usadas, 1),
                    "Vida Útil (h)": vida,
                    "Horas Restantes": int(horas_restantes)
                }
                consumibles_alertas.append(info)

    if consumibles_alertas:
        alertas_df = pd.DataFrame(consumibles_alertas)
        # Ordenar por horas restantes para ver los más críticos primero
        alertas_df = alertas_df.sort_values(by="Horas Restantes", ascending=True)
        
        st.markdown("Consumibles que requieren atención (críticos y próximos a vencer):")
        st.dataframe(
            alertas_df,
            use_container_width=True,
            column_config={
                "Horas Restantes": st.column_config.ProgressColumn(
                    "Horas Restantes",
                    help="Horas de vida útil que quedan. Las barras negativas indican que se ha sobrepasado la vida útil.",
                    format="%d h",
                    min_value=int(min(0, alertas_df["Horas Restantes"].min())),
                    max_value=72,
                )
            }
        )
    else:
        st.info("✅ No hay consumibles en estado crítico o próximos a vencer.")

    # Equipos con más horas acumuladas
    st.markdown("### ⏱️ Top 5 equipos con más horas acumuladas")
    horas_acumuladas = {}
    detalles_equipo = {}

    for _, fila in data_registro.iterrows():
        empresa_val = fila.get('empresa', '')
        codigo_val = fila.get('codigo', '')
        descripcion_val = fila.get('descripcion', '')
        key = f"{empresa_val} - {codigo_val}"
        horas = fila.get("hora de uso", 0)
        try:
            horas = float(horas)
        except:
            horas = 0
        horas_acumuladas[key] = horas_acumuladas.get(key, 0) + horas
        detalles_equipo[key] = {
            "empresa": empresa_val,
            "codigo": codigo_val,
            "descripcion": descripcion_val
        }

    top_horas = sorted(horas_acumuladas.items(), key=lambda x: x[1], reverse=True)[:5]
    for equipo_key, horas in top_horas:
        info = detalles_equipo.get(equipo_key, {})
        empresa_txt = info.get("empresa", "")
        codigo_txt = info.get("codigo", "")
        descripcion_txt = info.get("descripcion", "")
        st.markdown(f"- 🕒 **Empresa:** `{empresa_txt}` | **Código:** `{codigo_txt}` | **Descripción:** `{descripcion_txt}` | **Horas:** `{horas:.1f}`")

    # Simulación exportación a PDF
    dashboard_text = "Resumen Dashboard DeTEK PRO Company\n\n"
    dashboard_text += f"Empresas registradas: {total_empresas}\n"
    dashboard_text += f"Equipos registrados: {total_equipos}\n\n"
    dashboard_text += "Partes más cambiadas:\n"
    for parte, count in partes_frecuentes.items():
        dashboard_text += f"- {parte}: {count} cambios\n"
    dashboard_text += "\nConsumibles que requieren atención:\n"
    if consumibles_alertas:
        alertas_df_report = pd.DataFrame(consumibles_alertas)
        alertas_df_report = alertas_df_report.sort_values(by="Horas Restantes", ascending=True)
        for _, eq in alertas_df_report.iterrows():
            dashboard_text += f"- {eq['Estado']} Empresa: {eq['Empresa']} | Equipo: {eq['Equipo']} | Consumible: {eq['Consumible']} | Restantes: {int(eq['Horas Restantes'])} h\n"
    else:
        dashboard_text += "No hay consumibles en estado crítico o próximos a vencer.\n"
    dashboard_text += "\nTop 5 equipos por horas acumuladas:\n"
    for equipo, horas in top_horas:
        dashboard_text += f"- {equipo}: {horas:.1f} horas\n"

    st.download_button(
        label=" Exportar informe PDF",
        data=dashboard_text,
        file_name="informe_dashboard.txt",  # PDF simulado, luego se puede convertir
        mime="text/plain"
    )

    st.stop()


# Al cambiar la empresa, actualizar el hash de la URL con JS
empresa_slug = slugify_empresa(empresa)
components.html(f"""
    <script>
        const empresaSlug = '{empresa_slug}';
        if (window.location.hash.replace('#','') !== empresaSlug) {{
            window.location.hash = empresaSlug;
        }}
    </script>
""", height=0)
# 2. Mostrar layout y QR en un expander debajo de la empresa
info_empresa_row = empresas_df[empresas_df["empresa"].str.strip().str.lower() == empresa.strip().lower()]
if not info_empresa_row.empty:
    info_empresa_row = info_empresa_row.squeeze()
    layout_url = info_empresa_row.get("layout_url", "")
    qr_url = info_empresa_row.get("qr_url", "")
    parametrosproce_url = info_empresa_row.get("parametrosproce_url", "")
    
    # Convertir el link de layout, qr y parametrosproce si es de Google Drive
    def get_drive_viewable_url(url):
        if not isinstance(url, str):
            return url
        patterns = [
            r"/file/d/([\w-]+)",
            r"id=([\w-]+)",
            r"https://drive.google.com/open\?id=([\w-]+)",
            r"https://drive.google.com/uc\?id=([\w-]+)"
        ]
        for pat in patterns:
            match = re.search(pat, url)
            if match:
                file_id = match.group(1)
                return f"https://drive.google.com/uc?export=view&id={file_id}"
        return url
    layout_url_view = get_drive_viewable_url(layout_url)
    qr_url_view = get_drive_viewable_url(qr_url)
    parametrosproce_url_view = get_drive_viewable_url(parametrosproce_url)
    
    # Generar link único por empresa (slug amigable)
    import urllib.parse
    empresa_slug = urllib.parse.quote_plus(empresa.strip().replace(' ', '_').lower())
    empresa_link = f"https://detekprocompany.streamlit.app/#{empresa_slug}"
    with st.expander("Layout y QR de la empresa", expanded=True):
        st.markdown(f'''
            <div style="display: flex; justify-content: center; gap: 1em; margin-top: 1em; flex-wrap: wrap;">
                <a href="{layout_url_view}" target="_blank">
                    <button style="background:#0072C6;color:white;padding:0.5em 1.2em;border:none;border-radius:1.5em;font-weight:bold;font-size:1em;cursor:pointer;">Ver Layout</button>
                </a>
                <a href="{qr_url_view}" target="_blank">
                    <button style="background:#00BDAD;color:white;padding:0.5em 1.2em;border:none;border-radius:1.5em;font-weight:bold;font-size:1em;cursor:pointer;">Ver QR</button>
                </a>
                <a href="{parametrosproce_url_view}" target="_blank">
                    <button style="background:#F39C12;color:white;padding:0.5em 1.2em;border:none;border-radius:1.5em;font-weight:bold;font-size:1em;cursor:pointer;">Parámetros de Procesamiento</button>
                </a>
            </div>
        ''', unsafe_allow_html=True)

    # --- NUEVO: Expander para Información Adicional ---
    desprese = info_empresa_row.get("desprese", "No especificado")
    porcentaje_desprese = info_empresa_row.get("porcentaje_desprese", "")
    tipo_pollo = info_empresa_row.get("tipo_pollo", "No especificado")
    peso_min_pollo = info_empresa_row.get("peso_min_pollo", "")
    peso_max_pollo = info_empresa_row.get("peso_max_pollo", "")
    tipo_venta = info_empresa_row.get("tipo_venta", "No especificado")
    marinado = info_empresa_row.get("marinado", "No especificado")

    # Verificar si hay al menos un dato adicional para mostrar el expander
    info_adicional_disponible = any([
        str(desprese).strip().lower() not in ["", "no especificado"],
        str(porcentaje_desprese).strip(),
        str(tipo_pollo).strip().lower() not in ["", "no especificado"],
        str(peso_min_pollo).strip(),
        str(peso_max_pollo).strip(),
        str(tipo_venta).strip().lower() not in ["", "no especificado"],
        str(marinado).strip().lower() not in ["", "no especificado"]
    ])

    if info_adicional_disponible:
        with st.expander("Información Adicional de la Empresa", expanded=False):
            st.markdown(f"**¿Realiza desprese?** `{desprese}`")
            if str(desprese).strip().lower() == 'si' and str(porcentaje_desprese).strip():
                st.markdown(f"**Porcentaje de Desprese:** `{porcentaje_desprese}%`")
            st.markdown(f"**Tipo de Pollo:** `{tipo_pollo}`")
            if str(peso_min_pollo).strip() and str(peso_max_pollo).strip():
                st.markdown(f"**Peso del Pollo:** Entre `{peso_min_pollo}` kg y `{peso_max_pollo}` kg")
            st.markdown(f"**Tipo de Venta:** `{tipo_venta}`")
            st.markdown(f"**¿Se marina el pollo?** `{marinado}`")


# 3. Selección de zona (ahora desde la columna 'zona' de la hoja 'equipos')


# --- ORDEN PERSONALIZADO DE ZONAS ---

# Orden y nombres amigables fijos
orden_zonas = [
    ("zona recibo", "Zona Recibo"),
    ("zona sacrificio", "Zona Sacrificio"),
    ("zona evisceracion", "Zona Evisceracion"),
    ("zona enfriamiento", "Zona Enfriamiento"),
    ("zona empaque", "Zona Empaque"),
    ("transportador_aereo", "Transportador Aéreo")
]

# Normalizar zonas del DataFrame
zonas_unicas = equipos_df["zona"].dropna().unique()
zonas_unicas_norm = [z.strip().lower() for z in zonas_unicas]

# Construir lista ordenada solo con las zonas que existen, usando nombres amigables fijos

# Usar un set para evitar duplicados de zonas amigables
zonas_visibles = []
zonas_alerta_map = {}
zonas_agregadas = set()
for zona_norm, zona_amigable in orden_zonas:
    if zona_norm in zonas_unicas_norm and zona_amigable not in zonas_agregadas:
        zona_real = next((z for z in zonas_unicas if z.strip().lower() == zona_norm), zona_norm)
        equipos_zona = equipos_df[(equipos_df["empresa"].str.strip().str.lower() == empresa.strip().lower()) & (equipos_df["zona"].str.strip().str.lower() == zona_norm)]
        alerta = ''
        if equipos_zona.empty:
            alerta = ' ⚠️'
        visible = f"{zona_amigable}{alerta}"
        zonas_visibles.append(visible)
        zonas_alerta_map[visible] = zona_real
        zonas_agregadas.add(zona_amigable)
# Agregar cualquier zona extra que no esté en el orden predefinido, normalizando a formato amigable
for z in zonas_unicas:
    znorm = z.strip().lower()
    zona_amigable = z.replace('_', ' ').title()
    # Ocultar zonas vacías
    if not znorm or zona_amigable.strip() == '':
        continue
    if znorm not in [o[0] for o in orden_zonas] and zona_amigable not in zonas_agregadas:
        equipos_zona = equipos_df[(equipos_df["empresa"].str.strip().str.lower() == empresa.strip().lower()) & (equipos_df["zona"].str.strip().str.lower() == znorm)]
        alerta = ''
        if equipos_zona.empty:
            alerta = ' ⚠️' 
        visible = f"{zona_amigable}{alerta}"
        zonas_visibles.append(visible)
        zonas_alerta_map[visible] = z
        zonas_agregadas.add(zona_amigable)

zona_visible = st.selectbox("Selecciona la zona:", zonas_visibles, key="zona_select")
nombre_zona = zonas_alerta_map[zona_visible]

# Filtrar equipos por empresa y zona seleccionada
equipos_zona_df = equipos_df[(equipos_df["empresa"].str.strip().str.lower() == empresa.strip().lower()) & (equipos_df["zona"] == nombre_zona)]

# --- EQUIPO: agregar alerta si algún consumible está en estado crítico o advertencia ---
equipos_lista = []
equipos_alerta_map = {}
if not equipos_zona_df.empty:
    for _, row in equipos_zona_df.iterrows():
        nombre = f"{row['codigo']} - {row['descripcion']}"
        # Revisar estado de consumibles si existen
        alerta = ''
        consumibles = [c.strip() for c in str(row.get('consumibles','')).split(",") if c.strip()]
        vida_util_str = str(row.get('vida_util',''))
        vidas_utiles = [int(v.strip()) if v.strip().isdigit() else 700 for v in vida_util_str.split(";")]
        # Buscar registros de uso
        data_registro = pd.DataFrame(sheet_registro_data)
        data_registro.columns = [col.lower().strip() for col in data_registro.columns]
        data_equipo = data_registro[(data_registro["empresa"].str.strip().str.lower() == empresa.strip().lower()) & (data_registro["codigo"] == row['codigo'])] if not data_registro.empty else pd.DataFrame()
        estado_partes = {parte: 0 for parte in consumibles}
        for _, fila in data_equipo.iterrows():
            horas = fila.get("hora de uso", 0)
            try:
                horas = float(horas)
            except:
                horas = 0
            partes_cambiadas = str(fila.get("parte cambiada", "")).split(";")
            for parte in consumibles:
                if parte in partes_cambiadas:
                    estado_partes[parte] = 0
                else:
                    estado_partes[parte] += horas
        for idx, parte in enumerate(consumibles):
            usadas = estado_partes.get(parte, 0)
            vida_util_val = vidas_utiles[idx] if idx < len(vidas_utiles) else 700
            restantes = max(vida_util_val - usadas, 0)
            if restantes <= 0.5 or restantes <= 192:
                alerta = ' 🔴'
                break
            elif restantes <= 360 and not alerta:
                alerta = ' 🟡'
        equipos_lista.append(f"{nombre}{alerta}")
        equipos_alerta_map[f"{nombre}{alerta}"] = nombre
    equipo_seleccionado = st.selectbox("Selecciona el equipo:", equipos_lista, key="equipo_select")
    equipo_sel_nombre = equipos_alerta_map.get(equipo_seleccionado, None)
    # Mostrar cantidad justo debajo del selector de equipo
    if equipo_sel_nombre:
        codigo_sel = equipo_sel_nombre.split(' - ')[0].strip()
        op_row = equipos_zona_df[equipos_zona_df["codigo"] == codigo_sel]
        if "cantidad" in op_row.columns and not op_row.empty:
            cantidad_eq = op_row["cantidad"].values[0]
            # Si el valor es None, NaN, vacío o no numérico, mostrar 0
            try:
                cantidad_eq = int(float(cantidad_eq))
            except (ValueError, TypeError):
                cantidad_eq = 0
        else:
            cantidad_eq = 0
        st.markdown(f"**Cantidad de equipos:** `{cantidad_eq}`")
else:
    equipo_seleccionado = None
    equipo_sel_nombre = None
    st.info("No hay equipos para esta zona.")

# --- EXPANDER CON INFO DEL EQUIPO SELECCIONADO ---

import pytz
from datetime import timedelta

tz = pytz.timezone("America/Bogota")  # Cambia a tu zona horaria si es necesario
now = datetime.now(tz)
today = now.date()
start_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
end_time = now.replace(hour=14, minute=0, second=0, microsecond=0)

modo_auto = True  # Siempre automático

if equipo_sel_nombre:
    codigo_sel = equipo_sel_nombre.split(' - ')[0].strip()
    op_row = equipos_zona_df[equipos_zona_df["codigo"] == codigo_sel]
    op_equipo = op_row["op"].values[0] if "op" in op_row.columns and not op_row.empty else "No disponible"
    descripcion = op_row["descripcion"].values[0] if not op_row.empty else "No disponible"
    if not op_row.empty:
        consumibles_equipo = [c.strip() for c in op_row["consumibles"].values[0].split(",") if c.strip()]
    else:
        consumibles_equipo = []
else:
    op_row = pd.DataFrame()
    op_equipo = "No disponible"
    descripcion = "No disponible"
    consumibles_equipo = []

# --- AVANCE AUTOMÁTICO DE HORAS DE USO ---
if modo_auto:
    if now < start_time:
        st.info("La planta aún no ha arrancado hoy. El conteo inicia a las 7:00am.")
        minutos_avance = 0
    elif now > end_time:
        minutos_avance = 420  # 7 horas * 60 minutos
    else:
        delta = now - start_time
        minutos_avance = min(420, int(delta.total_seconds() / 60))
    horas = minutos_avance // 60
    minutos = minutos_avance % 60
    horas_formato = f"{horas}.{minutos:02d}"
    st.markdown(f"**Horas transcurridas hoy:** `{horas_formato}` / 7.00 h")
    st.progress(minutos_avance / 420)

    # Registro automático MASIVO a las 2pm para TODAS las empresas (optimización API)
    if now > end_time:
        # Verificar si ya se ejecutó el proceso masivo hoy
        batch_key = f"batch_processed_{str(today)}"
        if batch_key not in st.session_state:
            st.session_state[batch_key] = False
        
        if not st.session_state[batch_key]:
            with st.spinner("🔄 Ejecutando registro automático masivo de todas las empresas..."):
                try:
                    sheet_registro = client.open_by_key(SHEET_ID).worksheet("Hoja 1")
                    data_registro = pd.DataFrame(sheet_registro_data)
                    data_registro.columns = [col.lower().strip() for col in data_registro.columns]
                    
                    # Procesar TODAS las empresas
                    total_registros = 0
                    empresas_procesadas = 0
                    todas_las_filas = []  # Batch de todas las filas para insertar
                    
                    # Obtener todas las empresas únicas
                    empresas_unicas = empresas_df["empresa"].unique() if not empresas_df.empty else []
                    
                    for empresa_nombre in empresas_unicas:
                        equipos_empresa = equipos_df[equipos_df["empresa"].str.strip().str.lower() == empresa_nombre.strip().lower()]
                        registros_empresa = 0
                        
                        for _, eq_row in equipos_empresa.iterrows():
                            codigo = eq_row["codigo"]
                            descripcion_eq = eq_row["descripcion"]
                            
                            # Verificar si ya existe registro para hoy
                            existe_registro = False
                            if not data_registro.empty:
                                existe_registro = (
                                    (data_registro["empresa"].str.strip().str.lower() == empresa_nombre.strip().lower()) &
                                    (data_registro["codigo"] == codigo) &
                                    (data_registro["fecha"] == str(today))
                                ).any()
                            
                            if not existe_registro:
                                # Verificar si se cambió alguna parte hoy
                                partes_cambiadas_hoy = []
                                if not data_registro.empty:
                                    registros_hoy = data_registro[
                                        (data_registro["empresa"].str.strip().str.lower() == empresa_nombre.strip().lower()) &
                                        (data_registro["codigo"] == codigo) &
                                        (data_registro["fecha"] == str(today))
                                    ]
                                    if not registros_hoy.empty:
                                        partes_cambiadas_hoy = registros_hoy["parte cambiada"].dropna().tolist()
                                
                                # Determinar horas de uso y parte cambiada
                                if partes_cambiadas_hoy:
                                    parte_cambiada = ";".join([p for p in partes_cambiadas_hoy if p])
                                    horas_uso = 0.0
                                else:
                                    parte_cambiada = ""
                                    horas_uso = 7.0
                                
                                # Agregar fila al batch
                                fila = [
                                    empresa_nombre,
                                    str(today),
                                    codigo,
                                    descripcion_eq,
                                    horas_uso,
                                    parte_cambiada,
                                    "Sin Observaciones"
                                ]
                                todas_las_filas.append(fila)
                                registros_empresa += 1
                        
                        if registros_empresa > 0:
                            empresas_procesadas += 1
                            total_registros += registros_empresa
                    
                    # Insertar todas las filas en una sola operación (BATCH)
                    if todas_las_filas:
                        sheet_registro.append_rows(todas_las_filas)
                        st.success(f"✅ **Registro Masivo Completado**: {total_registros} equipos de {empresas_procesadas} empresas registrados automáticamente")
                        st.info(f"📊 **Optimización API**: Se realizó una sola operación en lote en lugar de {total_registros} llamadas individuales")
                    else:
                        st.info("ℹ️ Todos los registros del día ya estaban completos")
                    
                    # Marcar como procesado para evitar repetición
                    st.session_state[batch_key] = True
                    
                except Exception as e:
                    st.error(f"❌ Error en registro masivo: {str(e)}")
        else:
            st.info("✅ Registro masivo del día ya completado")
    
    # Mostrar registro individual para la empresa actual (solo informativo)
    equipos_empresa = equipos_df[equipos_df["empresa"].str.strip().str.lower() == empresa.strip().lower()]
    data_registro = pd.DataFrame(sheet_registro_data)
    data_registro.columns = [col.lower().strip() for col in data_registro.columns]
    registros_empresa_hoy = 0
    if not data_registro.empty and not equipos_empresa.empty:
        for _, eq_row in equipos_empresa.iterrows():
            codigo = eq_row["codigo"]
            existe_registro = (
                (data_registro["empresa"].str.strip().str.lower() == empresa.strip().lower()) &
                (data_registro["codigo"] == codigo) &
                (data_registro["fecha"] == str(today))
            ).any()
            if existe_registro:
                registros_empresa_hoy += 1
    
    if registros_empresa_hoy > 0 and now > end_time:
        st.success(f"✅ Esta empresa tiene {registros_empresa_hoy} equipo(s) ya registrados hoy")

# --- INFORMACIÓN DEL SISTEMA (sidebar) ---
st.sidebar.markdown("### ⚡ Estado del Sistema API")
batch_key = f"batch_processed_{str(today)}"
batch_status = st.session_state.get(batch_key, False)
if batch_status:
    st.sidebar.success("✅ Registro masivo completado hoy")
elif now > end_time:
    st.sidebar.warning("🔄 Registro masivo pendiente")
else:
    tiempo_restante = end_time - now
    horas_restantes = tiempo_restante.seconds // 3600
    minutos_restantes = (tiempo_restante.seconds % 3600) // 60
    st.sidebar.info(f"⏱️ Registro masivo en: {horas_restantes}h {minutos_restantes}m")

st.sidebar.markdown("---")

# --- INFORMACIÓN DE LA EMPRESA (sidebar) ---
st.sidebar.markdown("### 🏢 Información de la empresa seleccionada")
st.sidebar.markdown(f"**Empresa:** {empresa}")

info_match = empresas_df[empresas_df["empresa"].str.strip().str.lower() == empresa.strip().lower()]
info_empresa = info_match.squeeze() if not info_match.empty else {}

st.sidebar.markdown(f"**Encargado:** {info_empresa.get('encargado', 'No disponible')}")
st.sidebar.markdown(f"**Contacto:** {info_empresa.get('contacto', 'No disponible')}")
st.sidebar.markdown(f"**Ubicación:** {info_empresa.get('ubicacion', 'No disponible')}")
st.sidebar.markdown(f"**Técnico líder Tekpro:** {info_empresa.get('tecnico', 'No disponible')}")

# --- TAREAS DE LA EMPRESA ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 📋 Tareas de la empresa")

# Cargar todas las tareas de la empresa
try:
    tareas_df = pd.DataFrame(sheet_tareas_data)
except:
    tareas_df = pd.DataFrame()
cols_needed = {"empresa", "tarea", "descripcion", "fecha_asignacion", "completada"}
if not tareas_df.empty and cols_needed.issubset(set(tareas_df.columns)):
    tareas_empresa = tareas_df[tareas_df["empresa"].str.strip().str.lower() == empresa.strip().lower()]
    if not tareas_empresa.empty:
        for idx, tarea_row in tareas_empresa.iterrows():
            try:
                tarea_texto = tarea_row["tarea"]
                descripcion = tarea_row["descripcion"]
                fecha_asignacion = tarea_row["fecha_asignacion"]
                completada_val = str(tarea_row["completada"]).strip().lower()
                # Acepta 'si', 'sí', 'SI', 'Sí', etc.
                completada = completada_val in ["si", "sí"]
                estado = "✅ Completada" if completada else "⏳ Pendiente"
                st.sidebar.markdown(f"- **{tarea_texto}**  ")
                st.sidebar.markdown(f"  _Descripción:_ {descripcion}  ")
                st.sidebar.markdown(f"  _Fecha:_ {fecha_asignacion}")
                st.sidebar.markdown(f"  _Estado:_ {estado}")
            except KeyError:
                st.sidebar.warning("Formato de tarea inválido. Verifica las columnas de la hoja Tareas.")
    else:
        st.sidebar.info("No hay tareas registradas para esta empresa.")
else:
    st.sidebar.info("No hay tareas registradas para esta empresa o faltan columnas requeridas.")

# --- Asignar nueva tarea ---
with st.sidebar.expander("➕ Agregar nueva tarea"):
    nueva_tarea = st.text_area("Descripción de la tarea", key="nueva_tarea")
    asignada_por = st.text_input("Asignada por", value="DeTEK PRO Company", key="asignada_por")
    if st.button("Agregar tarea", key="asignar_tarea"):
        if nueva_tarea.strip():
            sheet_tareas.append_row([
                empresa,
                nueva_tarea.strip(),
                asignada_por.strip(),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "No",
                ""
            ])
            st.success("Tarea agregada correctamente.")
            st.rerun()

# --- REGISTRAR NUEVO EQUIPO ---
st.sidebar.markdown("---")
with st.sidebar.expander("🔧 Registrar nuevo equipo"):
    with st.form("form_registro_equipo"):
        nueva_empresa = st.text_input("Empresa", value=empresa)
        
        # Campo de zona con opciones de zonas comunes
        zonas_opciones = ["Zona Recibo", "Zona Sacrificio", "Zona Evisceracion", 
                          "Zona Enfriamiento", "Zona Empaque", "Transportador Aéreo", "General", "Otra"]
        zona_seleccion = st.selectbox("Zona", zonas_opciones)
        
        # Permitir especificar otra zona si selecciona "Otra"
        if zona_seleccion == "Otra":
            nueva_zona = st.text_input("Especificar zona", "")
        else:
            nueva_zona = zona_seleccion
            
        nuevo_codigo = st.text_input("Código del equipo (Ej: RF999)")
        nueva_descripcion = st.text_input("Descripción del equipo")
        nuevos_consumibles = st.text_input("Consumibles (separados por coma)")
        
        # Nuevo campo para horas de uso inicial
        horas_iniciales = st.number_input("Horas de uso iniciales", min_value=0.0, step=0.5, value=0.0)
        
        # Campos opcionales para URLs de documentación
        st.markdown("**Enlaces a documentación (opcional):**")
        nueva_foto_url = st.text_input("URL de la foto del equipo", value="")
        nuevo_manual_url = st.text_input("URL del manual de operación", value="")
        nueva_ficha_url = st.text_input("URL de la ficha técnica", value="")
        
        submitted = st.form_submit_button("Guardar equipo")
    
    if submitted:
        # Convertir nombre de zona al formato usado en la hoja (convertir a lowercase para consistencia)
        zona_norm = nueva_zona.lower()
        
        # Crear una fila para agregar a la hoja de equipos
        fila = [
            nueva_empresa.strip(),
            nuevo_codigo.strip(),
            nueva_descripcion.strip(),
            nuevos_consumibles.strip(),
            "",  # Para descripcion_consumibles
            "",  # Para vida_util
            "sí",  # Para alertas_activas
            zona_norm.strip(),  # Para zona
            "",  # Para numero_op
            nueva_foto_url.strip(),  # Para foto_url
            "",  # Para fecha_instalacion
            nuevo_manual_url.strip(),  # Para manual_url
            nueva_ficha_url.strip(),  # Para ficha_tecnica_url
            str(horas_iniciales)  # Nuevo campo para horas iniciales
        ]
        
        try:
            # Obtener la hoja de equipos y agregar la nueva fila
            sheet_equipos = client.open_by_key(SHEET_ID).worksheet("Equipos")
            sheet_equipos.append_row(fila)
            
            st.success(f"✅ Equipo {nuevo_codigo} registrado correctamente en zona {nueva_zona}.")
            # Recargar la página para ver los cambios
            st.rerun()
        except Exception as e:
            st.error(f"Error al registrar el equipo: {e}")

# --- CHAT EN LÍNEA ENTRE APPS ---
# --- INDICADOR DE MENSAJES NUEVOS ---
chat_df_indicator = pd.DataFrame(sheet_chat_data)
chat_df_indicator.columns = [col.lower().strip() for col in chat_df_indicator.columns]
mensajes_empresa = chat_df_indicator[chat_df_indicator["empresa"] == empresa] if not chat_df_indicator.empty and "empresa" in chat_df_indicator.columns else pd.DataFrame()
ultimo_mensaje = mensajes_empresa["fecha"].max() if not mensajes_empresa.empty and "fecha" in mensajes_empresa.columns else None

# Guardar la fecha del último mensaje leído en session_state
if 'ultimo_mensaje_leido' not in st.session_state or st.session_state.get('empresa_chat_leido') != empresa:
    st.session_state['ultimo_mensaje_leido'] = ultimo_mensaje
    st.session_state['empresa_chat_leido'] = empresa

hay_nuevo = False
if ultimo_mensaje and st.session_state['ultimo_mensaje_leido']:
    hay_nuevo = ultimo_mensaje > st.session_state['ultimo_mensaje_leido']
elif ultimo_mensaje and not st.session_state['ultimo_mensaje_leido']:
    hay_nuevo = True

st.sidebar.markdown("---")
chat_title = "💬 Chat en línea"
if hay_nuevo:
    chat_title += " <span style='color:red;font-size:1.2em;'>●</span>"

with st.sidebar.expander(chat_title, expanded=False):
    chat_df = pd.DataFrame(sheet_chat_data)
    if not chat_df.empty:
        chat_df.columns = [col.lower().strip() for col in chat_df.columns]
        if "empresa" in chat_df.columns and "usuario" in chat_df.columns and "mensaje" in chat_df.columns and "fecha" in chat_df.columns:
            chat_df = chat_df[chat_df["empresa"] == empresa]
            chat_df = chat_df.tail(30)
            for _, row in chat_df.iterrows():
                st.markdown(f"<span style='color:#00BDAD'><b>{row['usuario']}</b></span> <span style='color:gray;font-size:12px'>({row['fecha']})</span>: {row['mensaje']}", unsafe_allow_html=True)
        else:
            st.info("La hoja de chat no tiene el formato esperado. Asegúrate de que las columnas sean: fecha, usuario, mensaje, empresa.")
    else:
        st.info("No hay mensajes en el chat todavía.")
    st.markdown("---")
    mensaje_chat = st.text_input("Mensaje:", value="", key="chat_mensaje_company")
    if st.button("Enviar mensaje", key="chat_enviar_company"):
        if sheet_chat and mensaje_chat.strip():
            sheet_chat.append_row([
                str(datetime.now()),
                "Soporte tecnico",  # Nombre fijo para el chat
                mensaje_chat.strip(),
                empresa
            ])
            st.success("Mensaje enviado!")
            st.session_state['ultimo_mensaje_leido'] = str(datetime.now())
            st.session_state['empresa_chat_leido'] = empresa
            time.sleep(1)
            st.rerun()
        elif not sheet_chat:
            st.error("No se puede enviar el mensaje. La conexión con la hoja de Chat no está disponible.")

# --- INFORMACIÓN MULTIMEDIA DEL EQUIPO EN EXPANDER ---

if equipo_seleccionado and isinstance(equipo_seleccionado, str) and not op_row.empty:
    import re
    def get_drive_direct_url(url):
        """Convierte un enlace de Google Drive tipo /file/d/ID/view o sharing a enlace directo de visualización."""
        if not isinstance(url, str):
            url = str(url) if url is not None else ""
        # Buscar ID en diferentes formatos
        patterns = [
            r"/file/d/([\w-]+)",
            r"id=([\w-]+)",
            r"https://drive.google.com/open\?id=([\w-]+)",
            r"https://drive.google.com/uc\?id=([\w-]+)"
        ]
        for pat in patterns:
            match = re.search(pat, url)
            if match:
                file_id = match.group(1)
                return f"https://drive.google.com/uc?export=view&id={file_id}"
        return url

    equipo_row = op_row.squeeze()
    with st.expander("Información adicional del equipo", expanded=True):
        # Mostrar número de OP si existe
        op_numero = equipo_row.get("op", "No disponible")
        if hasattr(op_numero,'iloc'):
            op_numero = op_numero.iloc[0] if len(op_numero) > 0 else "No disponible"
        st.markdown(f"**Número de OP:** `{op_numero}`")
        
        # Definimos columnas solo si vamos a mostrar botones
        tiene_foto = False
        tiene_manual = False
        
        # Verificación estricta de la foto
        foto_url = equipo_row.get("foto_url", "")
        if isinstance(foto_url, str) and foto_url.strip():
            foto_url = get_drive_direct_url(foto_url)
            tiene_foto = True
        
        # Verificación estricta del manual
        manual_url = equipo_row.get("manual_url", "")
        if isinstance(manual_url, str) and manual_url.strip():
            manual_url = get_drive_direct_url(manual_url)
            tiene_manual = True
        
        # Verificación estricta de la ficha técnica
        ficha_url = equipo_row.get("ficha_tecnica_url", "")
        if isinstance(ficha_url, str) and ficha_url.strip():
            ficha_url = get_drive_direct_url(ficha_url)
        
        # Solo crear columnas si hay al menos un botón para mostrar
        if tiene_foto or tiene_manual:
            col1, col2 = st.columns(2)
            
            # Foto (solo si tiene URL válida)
            if tiene_foto:
                with col1:
                    st.markdown("**Foto del equipo:**")
                    st.markdown(f'''
                        <a href="{foto_url}" target="_blank" style="
                            display: inline-block;
                            padding: 0.5em 1.2em;
                            background: #00BDAD;
                            color: white;
                            border: none;
                            border-radius: 1.5em;
                            text-decoration: none;
                            font-weight: bold;
                            font-size: 1.1em;
                            margin-bottom: 1em;
                            transition: background 0.2s;
                        " onmouseover="this.style.background='#009e90'" onmouseout="this.style.background='#00BDAD'">
                            IMAGEN EQUIPO
                        </a>
                    ''', unsafe_allow_html=True)
            
            # Manual (solo si tiene URL válida)
            if tiene_manual:
                with col2:
                    st.markdown("**Manual del equipo (PDF):**")
                    st.markdown(f'''
                        <a href="{manual_url}" target="_blank" style="
                            display: inline-block;
                            padding: 0.5em 1.2em;
                            background: #0072C6;
                            color: white;
                            border: none;
                            border-radius: 1.5em;
                            text-decoration: none;
                            font-weight: bold;
                            font-size: 1.1em;
                            margin-bottom: 1em;
                            transition: background 0.2s;
                        " onmouseover="this.style.background='#005fa3'" onmouseout="this.style.background='#0072C6'">
                            MANUAL PDF
                        </a>
                    ''', unsafe_allow_html=True)
        
        # Ficha técnica (solo si tiene URL válida)
        if isinstance(ficha_url, str) and ficha_url.strip():
            st.markdown("**Ficha técnica:**")
            st.markdown(f'''
                <a href="{ficha_url}" target="_blank" style="
                    display: inline-block;
                    padding: 0.5em 1.2em;
                    background: #F39C12;
                    color: white;
                    border: none;
                    border-radius: 1.5em;
                    text-decoration: none;
                    font-weight: bold;
                    font-size: 1.1em;
                    margin-bottom: 1em;
                    transition: background 0.2s;
                " onmouseover="this.style.background='#e08e0b'" onmouseout="this.style.background='#F39C12'">
                    FICHA TÉCNICA
                </a>
            ''', unsafe_allow_html=True)
        
        # --- ACTAS DE ENTREGA ---
        # Buscar actas de entrega por número de OP

        
        if op_numero and op_numero != "No disponible":
            imagenes_acta = buscar_actas_por_op(op_numero, sheet_actas_data)
            
            if imagenes_acta:
                st.markdown("---")
                st.markdown("### 📋 **Actas de Entrega**")
                st.markdown(f"**Documentos encontrados para OP:** `{op_numero}`")
                
                # Mostrar los enlaces como una lista ordenada de botones
                for i, documento in enumerate(imagenes_acta, 1):
                    # Crear columnas para mejor distribución
                    col1, col2 = st.columns([1, 4])
                    
                    with col1:
                        st.markdown(f"**{i}.**")
                    
                    with col2:
                        # Determinar el tipo de documento y color del botón
                        nombre = documento['nombre']
                        url = documento['url']
                        
                        # Asignar colores según el tipo de documento
                        if any(palabra in nombre.lower() for palabra in ['foto', 'imagen', 'picture']):
                            color = "#28a745"  # Verde para imágenes
                            icono = "📷"
                        elif any(palabra in nombre.lower() for palabra in ['acta', 'documento', 'pdf']):
                            color = "#007bff"  # Azul para documentos
                            icono = "📄"
                        elif any(palabra in nombre.lower() for palabra in ['video', 'mp4', 'mov']):
                            color = "#6f42c1"  # Púrpura para videos
                            icono = "🎥"
                        else:
                            color = "#fd7e14"  # Naranja para otros
                            icono = "🔗"
                        
                        # Crear botón estilizado
                        st.markdown(f"""
                            <div style="margin-bottom: 0.5em;">
                                <strong>{nombre}:</strong><br>
                                <a href="{url}" target="_blank" style="
                                    display: inline-block;
                                    padding: 0.6em 1.5em;
                                    background: {color};
                                    color: white;
                                    border: none;
                                    border-radius: 25px;
                                    text-decoration: none;
                                    font-weight: bold;
                                    font-size: 0.9em;
                                    margin-top: 0.3em;
                                    transition: all 0.3s ease;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)'" 
                                   onmouseout="this.style.transform='translateY(0px)'; this.style.boxShadow='0 2px 4px rgba(0,0,0,0.1)'">
                                    {icono} Abrir Documento
                                </a>
                            </div>
                        """, unsafe_allow_html=True)
                
                # Resumen al final
                st.markdown("---")
                total_docs = len(imagenes_acta)
                st.info(f"✅ Total de documentos encontrados: **{total_docs}** para la OP **{op_numero}**")
            else:
                st.warning(f"❌ **No se encontraron documentos** para la OP: **{op_numero}**")
                st.markdown("**Posibles causas:**")
                st.markdown("- La OP no existe en la hoja de actas")
                st.markdown("- El formato de la OP no coincide exactamente")
                st.markdown("- No hay columnas con links de Google Drive para esta OP")
        else:
            st.info("ℹ️ **Selecciona un equipo** que tenga un número de OP válido para buscar documentos")
        
        
        # Fecha de instalación
        fecha_inst = equipo_row.get("fecha_instalacion", "No disponible")
        st.markdown(f"**Fecha de instalación:** {fecha_inst}")

        # --- ESTADO DE CONSUMIBLES ---
        if 'codigo_sel' in locals() and codigo_sel:
            st.markdown("### 🔧 Estado de consumibles del proceso seleccionado")
            # Leer registros de uso desde la hoja principal para el equipo seleccionado
            data_registro = pd.DataFrame(sheet_registro_data)
            data_registro.columns = [col.lower().strip() for col in data_registro.columns]
            data_equipo = data_registro[(data_registro["empresa"].str.strip().str.lower() == empresa.strip().lower()) & (data_registro["codigo"] == codigo_sel)] if not data_registro.empty else pd.DataFrame()
            estado_partes = {parte: 0 for parte in consumibles_equipo}

            # Obtener cantidades de consumibles
            cantidad_consu_list = []
            if "cantidad_consu" in op_row.columns and not op_row.empty:
                cantidad_consu_str = str(op_row["cantidad_consu"].values[0])
                cantidad_consu_list = [c.strip() for c in cantidad_consu_str.split(";")]

            for _, fila in data_equipo.iterrows():
                horas = fila.get("hora de uso", 0)
                try:
                    horas = float(horas)
                except:
                    horas = 0
                partes_cambiadas = str(fila.get("parte cambiada", "")).split(";")
                for parte in consumibles_equipo:
                    if parte in partes_cambiadas:
                        estado_partes[parte] = 0
                    else:
                        estado_partes[parte] += horas

            # Mostrar cada consumible y debajo su cantidad
            for idx, parte in enumerate(consumibles_equipo):
                usadas = estado_partes.get(parte, 0)
                vida_util_val = VIDA_UTIL_DEFECTO
                if "vida_util" in op_row.columns and not op_row.empty:
                    vida_util_str = str(op_row["vida_util"].values[0])
                    vidas_utiles = [int(v.strip()) if v.strip().isdigit() else VIDA_UTIL_DEFECTO for v in vida_util_str.split(";")]
                    if idx < len(vidas_utiles):
                        vida_util_val = vidas_utiles[idx]
                restantes = max(vida_util_val - usadas, 0)
                porcentaje = min(usadas / vida_util_val, 1.0) if vida_util_val > 0 else 0

                if restantes <= 1:
                    color, estado_txt = "🔴", "Crítico"
                elif restantes <= 10:
                    color, estado_txt = "🟡", "Advertencia"
                else:
                    color, estado_txt = "🟢", "Bueno"

                cantidad_consu = cantidad_consu_list[idx] if idx < len(cantidad_consu_list) else "No disponible"
                st.markdown(f"{color} **{parte}** - Estado: `{estado_txt}`")
                st.markdown(f"**Uso:** {usadas:.1f} / {vida_util_val} h")
                st.markdown(f"Cantidad: `{cantidad_consu}`")
                st.progress(porcentaje)
        else:
            st.info("Selecciona un equipo para ver el estado de consumibles.")

# --- FORMULARIO DE REGISTRO INFORMACION DEL EQUIPO--------------
with st.form("registro_form"):
    fecha = date.today()
    partes = []
    if consumibles_equipo:
        partes = st.multiselect("Partes cambiadas hoy", consumibles_equipo)
    observaciones = st.text_area("Observaciones")
    # Se elimina la visualización de cantidad y horas de uso
    enviado = st.form_submit_button("Registrar información")

    if enviado:
        # Lógica para guardar registro manual
        parte_cambiada = ";".join(partes) if partes else ""
        horas_uso = 0.0 if partes else 7.0
        fila = [
            empresa,
            str(fecha),
            codigo_sel if 'codigo_sel' in locals() else "",
            descripcion if 'descripcion' in locals() else "",
            horas_uso,
            parte_cambiada,
            observaciones if observaciones else "Sin Observaciones"
        ]
        sheet_registro.append_row(fila)
        # Si se cambió alguna parte, reiniciar la columna 'hora de uso' en la hoja de equipos
        if partes and 'codigo_sel' in locals():
            idx_equipo = equipos_df[(equipos_df["empresa"].str.strip().str.lower() == empresa.strip().lower()) & (equipos_df["codigo"] == codigo_sel)].index
            if len(idx_equipo) > 0:
                idx = idx_equipo[0]
                # Reiniciar 'hora de uso' a 0 (si existe la columna)
                if "hora de uso" in equipos_df.columns:
                    equipos_df.at[idx, "hora de uso"] = 0
                    # Actualizar en Google Sheets
                    sheet_equipos = client.open_by_key(SHEET_ID).worksheet("Equipos")
                    col_idx = list(equipos_df.columns).index("hora de uso") + 1
                    sheet_equipos.update_cell(idx + 2, col_idx, 0)  # +2 por encabezado y 0-index
        # Limpiar los campos del formulario
        st.session_state["registro_form-Partes cambiadas hoy"] = []
        st.session_state["registro_form-Observaciones"] = ""
        st.success("Registro guardado correctamente.")
