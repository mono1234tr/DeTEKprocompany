"""
Módulo de Chat en Tiempo Real con Firebase Firestore
=====================================================
Este módulo maneja la conexión y operaciones del chat usando Firebase.
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import json
import os

# Variable global para controlar la inicialización
_firebase_initialized = False
_firebase_last_error = ""


def inicializar_firebase(credentials_path: str = "firebase_credentials.json"):
    """
    Inicializa Firebase. Solo se ejecuta una vez.
    Soporta tanto archivo local como Streamlit Secrets.
    
    Args:
        credentials_path: Ruta al archivo de credenciales JSON de Firebase
    
    Returns:
        Cliente de Firestore o None si hay error
    """
    global _firebase_initialized, _firebase_last_error
    
    try:
        if firebase_admin._apps:
            _firebase_initialized = True
            _firebase_last_error = ""
            return firestore.client()

        if not _firebase_initialized:
            secrets_error = None
            # Intentar primero con Streamlit Secrets (para Streamlit Cloud)
            try:
                import streamlit as st
                if "FIREBASE_CREDENTIALS" in st.secrets:
                    # Usar credenciales desde Streamlit Secrets
                    raw_firebase_credentials = st.secrets["FIREBASE_CREDENTIALS"]
                    if isinstance(raw_firebase_credentials, str):
                        firebase_config = json.loads(raw_firebase_credentials)
                    else:
                        firebase_config = dict(raw_firebase_credentials)

                    if "private_key" in firebase_config:
                        firebase_config["private_key"] = (
                            firebase_config["private_key"].replace("\\n", "\n").replace("\\r", "\r")
                        )

                    cred = credentials.Certificate(firebase_config)
                    firebase_admin.initialize_app(cred)
                    _firebase_initialized = True
                    _firebase_last_error = ""
                    return firestore.client()
            except Exception as e:
                if firebase_admin._apps:
                    _firebase_initialized = True
                    _firebase_last_error = ""
                    return firestore.client()
                # Si falla, intentar con archivo local
                secrets_error = e
            
            # Usar archivo local (para desarrollo)
            if not os.path.isabs(credentials_path):
                base_dir = os.path.dirname(os.path.abspath(__file__))
                credentials_path = os.path.join(base_dir, credentials_path)
            
            if os.path.exists(credentials_path):
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                _firebase_last_error = ""
            else:
                if secrets_error:
                    _firebase_last_error = (
                        f"No se pudo inicializar con Streamlit Secrets ni con archivo local. "
                        f"Archivo no encontrado: {credentials_path}. Error de secrets: {secrets_error}"
                    )
                else:
                    _firebase_last_error = f"Archivo de credenciales no encontrado: {credentials_path}"
                print(_firebase_last_error)
                return None
        
        return firestore.client()
    
    except Exception as e:
        _firebase_last_error = f"Error al inicializar Firebase: {e}"
        print(_firebase_last_error)
        return None


def firebase_disponible() -> bool:
    """Devuelve True si hay cliente de Firestore disponible."""
    return obtener_db() is not None


def obtener_ultimo_error_firebase() -> str:
    """Devuelve el último error capturado al intentar conectar u operar con Firebase."""
    return _firebase_last_error


def obtener_db():
    """
    Obtiene el cliente de Firestore.
    
    Returns:
        Cliente de Firestore
    """
    if not _firebase_initialized:
        return inicializar_firebase()
    return firestore.client()


def normalizar_nombre_empresa(empresa):
    """
    Normaliza el nombre de la empresa para usarlo como clave en Firebase.
    Firebase no permite ciertos caracteres en las claves.
    """
    # Reemplazar caracteres no permitidos en Firebase
    caracteres_prohibidos = ['.', '#', '$', '[', ']', '/']
    nombre_normalizado = empresa
    for char in caracteres_prohibidos:
        nombre_normalizado = nombre_normalizado.replace(char, '_')
    return nombre_normalizado


def enviar_mensaje(empresa: str, usuario: str, mensaje: str) -> bool:
    """
    Envía un mensaje al chat de una empresa.
    
    Args:
        empresa: Nombre de la empresa (identificador del chat)
        usuario: Nombre del usuario que envía el mensaje
        mensaje: Contenido del mensaje
    
    Returns:
        True si se envió correctamente, False si hubo error
    """
    global _firebase_last_error
    try:
        db = obtener_db()
        if db is None:
            return False
        
        # Usar la misma normalización que el lado CLIENTE
        empresa_key = normalizar_nombre_empresa(empresa)
        
        # Usar la misma colección 'chat' que el lado CLIENTE
        nuevo_mensaje = {
            'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'timestamp': datetime.now().timestamp(),
            'usuario': usuario,
            'mensaje': mensaje,
            'empresa': empresa,
            'origen': 'detek_procompany'  # Identificar de dónde viene el mensaje
        }
        
        # Agregar mensaje a la colección
        doc_ref = db.collection('chats').document(empresa_key).collection('mensajes').add(nuevo_mensaje)
        
        print(f"Mensaje enviado con ID: {doc_ref[1].id}")
        _firebase_last_error = ""
        return True
    
    except Exception as e:
        _firebase_last_error = f"Error al enviar mensaje: {e}"
        print(_firebase_last_error)
        return False


def obtener_mensajes(empresa: str, limite: int = 50) -> list:
    """
    Obtiene los mensajes del chat de una empresa.
    
    Args:
        empresa: Nombre de la empresa
        limite: Número máximo de mensajes a obtener
    
    Returns:
        Lista de diccionarios con los mensajes
    """
    global _firebase_last_error
    try:
        db = obtener_db()
        if db is None:
            return []
        
        # Usar la misma normalización que el lado CLIENTE
        empresa_key = normalizar_nombre_empresa(empresa)
        
        # Usar la colección 'chats'
        mensajes_ref = db.collection('chats').document(empresa_key).collection('mensajes')
        mensajes = mensajes_ref.order_by('timestamp').limit(limite).stream()
        
        resultado = []
        for msg in mensajes:
            data = msg.to_dict()
            data['id'] = msg.id
            resultado.append(data)
        
        _firebase_last_error = ""
        return resultado
    
    except Exception as e:
        _firebase_last_error = f"Error al obtener mensajes: {e}"
        print(_firebase_last_error)
        return []


def obtener_ultimo_mensaje(empresa: str) -> dict:
    """
    Obtiene el último mensaje del chat de una empresa.
    
    Args:
        empresa: Nombre de la empresa
    
    Returns:
        Diccionario con el último mensaje o None
    """
    try:
        db = obtener_db()
        if db is None:
            return None
        
        # Usar la misma normalización que el lado CLIENTE
        empresa_key = normalizar_nombre_empresa(empresa)
        
        # Usar la colección 'chats'
        mensajes_ref = db.collection('chats').document(empresa_key).collection('mensajes')
        mensajes = mensajes_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1).stream()
        
        for msg in mensajes:
            data = msg.to_dict()
            data['id'] = msg.id
            return data
        
        return None
    
    except Exception as e:
        print(f"Error al obtener último mensaje: {e}")
        return None


def marcar_mensajes_leidos(empresa: str):
    """
    Marca todos los mensajes de un chat como leídos.
    
    Args:
        empresa: Nombre de la empresa
    """
    try:
        db = obtener_db()
        if db is None:
            return
        
        # Usar la misma normalización que el lado CLIENTE
        empresa_key = normalizar_nombre_empresa(empresa)
        
        # Usar la colección 'chats'
        mensajes_ref = db.collection('chats').document(empresa_key).collection('mensajes')
        
        # Obtener todos los mensajes (ya que CLIENTE no usa campo 'leido')
        mensajes = mensajes_ref.stream()
        
        # Para compatibilidad, podríamos agregar el campo 'leido' si no existe
        for msg in mensajes:
            data = msg.to_dict()
            if 'leido' not in data:
                msg.reference.update({'leido': True})
    
    except Exception as e:
        print(f"Error al marcar mensajes como leídos: {e}")


def contar_mensajes_no_leidos(empresa: str) -> int:
    """
    Cuenta los mensajes no leídos de una empresa.
    Nota: CLIENTE no usa campo 'leido', así que cuenta mensajes sin este campo.
    
    Args:
        empresa: Nombre de la empresa
    
    Returns:
        Número de mensajes no leídos (sin campo 'leido')
    """
    try:
        db = obtener_db()
        if db is None:
            return 0
        
        # Usar la misma normalización que el lado CLIENTE
        empresa_key = normalizar_nombre_empresa(empresa)
        
        # Usar la colección 'chats'
        mensajes_ref = db.collection('chats').document(empresa_key).collection('mensajes')
        mensajes = mensajes_ref.stream()
        
        # Contar mensajes que no tienen el campo 'leido' (compatibilidad con CLIENTE)
        count = 0
        for msg in mensajes:
            data = msg.to_dict()
            if 'leido' not in data or not data.get('leido', False):
                count += 1
        
        return count
    
    except Exception as e:
        print(f"Error al contar mensajes: {e}")
        return 0


def obtener_chats_activos() -> list:
    """
    Obtiene la lista de todos los chats activos (empresas con mensajes).
    
    Returns:
        Lista de diccionarios con información de cada chat
    """
    try:
        db = obtener_db()
        if db is None:
            return []
        
        # Obtener todas las empresas que tienen mensajes en la colección 'chats'
        empresas_ref = db.collection('chats')
        empresas = empresas_ref.stream()
        
        resultado = []
        for empresa_doc in empresas:
            # Verificar si tiene mensajes
            mensajes_ref = empresa_doc.reference.collection('mensajes')
            mensajes_count = sum(1 for _ in mensajes_ref.limit(1).stream())
            
            if mensajes_count > 0:
                # Obtener el último mensaje para info
                ultimo_msg = None
                for msg in mensajes_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1).stream():
                    ultimo_msg = msg.to_dict()
                    ultimo_msg['id'] = msg.id
                    break
                
                resultado.append({
                    'empresa_key': empresa_doc.id,
                    'empresa': ultimo_msg.get('empresa', empresa_doc.id) if ultimo_msg else empresa_doc.id,
                    'ultimo_mensaje': ultimo_msg,
                    'activo': True
                })
        
        return resultado
    
    except Exception as e:
        print(f"Error al obtener chats activos: {e}")
        return []


# Función de prueba
if __name__ == "__main__":
    print("Probando conexión a Firebase...")
    db = inicializar_firebase()
    if db:
        print("✅ Conexión exitosa a Firebase!")
        
        # Prueba de envío
        if enviar_mensaje("Empresa_Test", "Sistema", "Mensaje de prueba desde EMPRESA"):
            print("✅ Mensaje enviado correctamente")
        
        # Prueba de lectura
        mensajes = obtener_mensajes("Empresa_Test")
        print(f"✅ Mensajes obtenidos: {len(mensajes)}")
        for msg in mensajes:
            print(f"   - {msg.get('usuario')}: {msg.get('mensaje')}")
    else:
        print("❌ Error al conectar con Firebase")
        print("❌ Error al conectar con Firebase")
