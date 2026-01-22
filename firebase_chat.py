"""
Módulo de Chat en Tiempo Real con Firebase Firestore
=====================================================
Este módulo maneja la conexión y operaciones del chat usando Firebase.
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os

# Variable global para controlar la inicialización
_firebase_initialized = False


def inicializar_firebase(credentials_path: str = "firebase_credentials.json"):
    """
    Inicializa Firebase. Solo se ejecuta una vez.
    Soporta tanto archivo local como Streamlit Secrets.
    
    Args:
        credentials_path: Ruta al archivo de credenciales JSON de Firebase
    
    Returns:
        Cliente de Firestore o None si hay error
    """
    global _firebase_initialized
    
    try:
        if not _firebase_initialized:
            # Intentar primero con Streamlit Secrets (para Streamlit Cloud)
            try:
                import streamlit as st
                if "FIREBASE_CREDENTIALS" in st.secrets:
                    # Usar credenciales desde Streamlit Secrets
                    firebase_config = dict(st.secrets["FIREBASE_CREDENTIALS"])
                    cred = credentials.Certificate(firebase_config)
                    firebase_admin.initialize_app(cred)
                    _firebase_initialized = True
                    return firestore.client()
            except Exception:
                pass  # Si falla, intentar con archivo local
            
            # Usar archivo local (para desarrollo)
            if not os.path.isabs(credentials_path):
                base_dir = os.path.dirname(os.path.abspath(__file__))
                credentials_path = os.path.join(base_dir, credentials_path)
            
            if os.path.exists(credentials_path):
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
            else:
                print(f"Archivo de credenciales no encontrado: {credentials_path}")
                return None
        
        return firestore.client()
    
    except Exception as e:
        print(f"Error al inicializar Firebase: {e}")
        return None


def obtener_db():
    """
    Obtiene el cliente de Firestore.
    
    Returns:
        Cliente de Firestore
    """
    if not _firebase_initialized:
        return inicializar_firebase()
    return firestore.client()


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
    try:
        db = obtener_db()
        if db is None:
            return False
        
        # Crear ID del chat basado en el nombre de la empresa (limpio)
        chat_id = empresa.strip().lower().replace(" ", "_")
        
        # Agregar mensaje a la colección
        db.collection('chats').document(chat_id).collection('mensajes').add({
            'usuario': usuario,
            'mensaje': mensaje,
            'empresa': empresa,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'leido': False
        })
        
        # Actualizar info del chat
        db.collection('chats').document(chat_id).set({
            'empresa': empresa,
            'ultimo_mensaje': firestore.SERVER_TIMESTAMP,
            'activo': True
        }, merge=True)
        
        return True
    
    except Exception as e:
        print(f"Error al enviar mensaje: {e}")
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
    try:
        db = obtener_db()
        if db is None:
            return []
        
        chat_id = empresa.strip().lower().replace(" ", "_")
        
        # Obtener mensajes ordenados por timestamp
        mensajes_ref = db.collection('chats').document(chat_id).collection('mensajes')
        mensajes = mensajes_ref.order_by('timestamp').limit(limite).stream()
        
        resultado = []
        for msg in mensajes:
            data = msg.to_dict()
            data['id'] = msg.id
            resultado.append(data)
        
        return resultado
    
    except Exception as e:
        print(f"Error al obtener mensajes: {e}")
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
        
        chat_id = empresa.strip().lower().replace(" ", "_")
        
        mensajes_ref = db.collection('chats').document(chat_id).collection('mensajes')
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
        
        chat_id = empresa.strip().lower().replace(" ", "_")
        
        # Obtener mensajes no leídos
        mensajes_ref = db.collection('chats').document(chat_id).collection('mensajes')
        mensajes_no_leidos = mensajes_ref.where('leido', '==', False).stream()
        
        # Marcar como leídos
        for msg in mensajes_no_leidos:
            msg.reference.update({'leido': True})
    
    except Exception as e:
        print(f"Error al marcar mensajes como leídos: {e}")


def contar_mensajes_no_leidos(empresa: str) -> int:
    """
    Cuenta los mensajes no leídos de una empresa.
    
    Args:
        empresa: Nombre de la empresa
    
    Returns:
        Número de mensajes no leídos
    """
    try:
        db = obtener_db()
        if db is None:
            return 0
        
        chat_id = empresa.strip().lower().replace(" ", "_")
        
        mensajes_ref = db.collection('chats').document(chat_id).collection('mensajes')
        mensajes_no_leidos = mensajes_ref.where('leido', '==', False).stream()
        
        return sum(1 for _ in mensajes_no_leidos)
    
    except Exception as e:
        print(f"Error al contar mensajes: {e}")
        return 0


def obtener_chats_activos() -> list:
    """
    Obtiene la lista de todos los chats activos.
    
    Returns:
        Lista de diccionarios con información de cada chat
    """
    try:
        db = obtener_db()
        if db is None:
            return []
        
        chats = db.collection('chats').where('activo', '==', True).stream()
        
        resultado = []
        for chat in chats:
            data = chat.to_dict()
            data['id'] = chat.id
            resultado.append(data)
        
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
        if enviar_mensaje("Empresa_Test", "Sistema", "Mensaje de prueba"):
            print("✅ Mensaje enviado correctamente")
        
        # Prueba de lectura
        mensajes = obtener_mensajes("Empresa_Test")
        print(f"✅ Mensajes obtenidos: {len(mensajes)}")
        for msg in mensajes:
            print(f"   - {msg.get('usuario')}: {msg.get('mensaje')}")
    else:
        print("❌ Error al conectar con Firebase")
