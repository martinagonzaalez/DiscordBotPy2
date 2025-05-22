#!/usr/bin/env python3
import os
import json
import requests
import time
import logging
from smiles_auth import get_smiles_tokens

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Telegram Bot Token
BOT_TOKEN = "8002861881:AAFmpkx1rKUbnvgytZ2u3BRtFcmQ83oNMfk"

class SimpleTelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0
    
    def get_updates(self):
        """Get updates from Telegram"""
        try:
            url = f"{self.api_url}/getUpdates"
            params = {"offset": self.last_update_id + 1, "timeout": 10}
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok") and data.get("result"):
                    return data["result"]
            return []
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []
    
    def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML"):
        """Send message to Telegram"""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

def buscar_vuelos_smiles_real(origen, destino, fecha_salida, fecha_regreso=None):
    """Search for real Smiles flights using authenticated API"""
    
    try:
        logger.info(f"🔍 Buscando vuelos reales: {origen} → {destino} en {fecha_salida}")
        
        # Get fresh Smiles authentication tokens
        tokens = get_smiles_tokens()
        logger.info("✅ Tokens de autenticación obtenidos")
        
        # Convert date format if needed
        if len(fecha_salida) == 7:  # YYYY-MM format
            fecha_salida = fecha_salida + "-01"
        
        # Official Smiles API endpoint
        api_url = "https://api-air-flightsearch-blue.smiles.com.ar/v1/airlines/search"
        
        headers = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "x-api-key": tokens['x_api_key'],
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://www.smiles.com.ar",
            "Referer": "https://www.smiles.com.ar/"
        }
        
        params = {
            "adults": 1,
            "children": 0,
            "infants": 0,
            "tripType": 1 if fecha_regreso else 0,
            "originAirportCode": origen,
            "destinationAirportCode": destino,
            "departureDate": fecha_salida,
            "cabinType": "economy",
            "currencyCode": "ARS",
            "isFlexibleDateChecked": "false",
            "forceCongener": "true",
            "r": "ar"
        }
        
        if fecha_regreso:
            params["returnDate"] = fecha_regreso
        
        # Make authenticated request to Smiles API
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("flights") and len(data["flights"]) > 0:
                return format_real_smiles_results(data["flights"], origen, destino)
            else:
                return f"🔍 No hay vuelos disponibles para {origen} → {destino} en {fecha_salida}"
        
        elif response.status_code == 401:
            logger.warning("Token expirado, obteniendo nuevos tokens...")
            # Force token refresh and retry
            from smiles_auth import smiles_auth
            smiles_auth.access_token = None
            new_tokens = get_smiles_tokens()
            
            # Retry with new tokens
            headers["Authorization"] = f"Bearer {new_tokens['access_token']}"
            headers["x-api-key"] = new_tokens['x_api_key']
            response = requests.get(api_url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("flights") and len(data["flights"]) > 0:
                    return format_real_smiles_results(data["flights"], origen, destino)
        
        # If API fails, provide fallback with direct link
        return create_smiles_link(origen, destino, fecha_salida, fecha_regreso)
        
    except Exception as e:
        logger.error(f"Error en búsqueda de vuelos: {str(e)}")
        return create_smiles_link(origen, destino, fecha_salida, fecha_regreso)

def format_real_smiles_results(flights, origen, destino):
    """Format real flight results from Smiles API"""
    
    # Sort flights by miles price (ascending)
    sorted_flights = sorted(flights, key=lambda x: int(x.get("price", {}).get("miles", 999999)))
    
    texto = f"✈️ <b>Vuelos Smiles Reales</b>\n"
    texto += f"📍 {origen} → {destino}\n"
    texto += f"🎯 <b>Datos auténticos de Smiles</b>\n"
    texto += "─" * 35 + "\n\n"
    
    best_deal = sorted_flights[0] if sorted_flights else None
    
    for i, flight in enumerate(sorted_flights[:5], 1):
        # Extract flight information
        airline = flight.get("airline", {}).get("name", "Aerolínea")
        flight_info = flight.get("flight", {})
        departure = flight_info.get("departure", {})
        fecha = departure.get("date", "Fecha")
        hora = departure.get("time", "")
        
        price_info = flight.get("price", {})
        millas = price_info.get("miles", 0)
        taxes = price_info.get("taxes", {}).get("amount", 0)
        
        # Mark best deal
        if flight == best_deal:
            texto += f"🏆 <b>MEJOR OFERTA</b>\n"
        
        texto += f"{i}. <b>{fecha}"
        if hora:
            texto += f" - {hora}"
        texto += f"</b>\n"
        
        texto += f"   ✈️ {airline}\n"
        texto += f"   💰 <b>{millas:,} millas"
        
        if taxes > 0:
            texto += f" + ${taxes:,} ARS tasas</b>\n"
        else:
            texto += "</b>\n"
        
        if i < len(sorted_flights[:5]):
            texto += "\n"
    
    # Add summary
    texto += f"\n📊 <b>Resumen:</b>\n"
    texto += f"• Total de vuelos: {len(flights)}\n"
    if best_deal:
        best_miles = best_deal.get("price", {}).get("miles", 0)
        texto += f"• Mejor precio: {best_miles:,} millas\n"
    
    texto += f"\n✅ <b>Precios reales de Smiles</b>"
    
    return texto

def create_smiles_link(origen, destino, fecha_salida, fecha_regreso=None):
    """Create direct Smiles link when API is unavailable"""
    
    params = {
        "originAirportCode": origen,
        "destinationAirportCode": destino,
        "departureDate": fecha_salida,
        "adults": "1",
        "children": "0",
        "infants": "0",
        "tripType": "1" if fecha_regreso else "2",
        "cabinType": "all"
    }
    
    if fecha_regreso:
        params["returnDate"] = fecha_regreso
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    search_url = f"https://www.smiles.com.ar/emission?{query_string}"
    
    texto = f"🔗 <b>Enlace directo a Smiles</b>\n"
    texto += f"📍 {origen} → {destino}\n"
    texto += f"📅 {fecha_salida}\n\n"
    texto += f"<a href='{search_url}'>🚀 Buscar en Smiles.com.ar</a>\n\n"
    texto += "💡 El enlace te llevará directamente a Smiles con tu búsqueda cargada para ver precios reales en millas."
    
    return texto

def parse_flight_input(text):
    """Parse user flight search input"""
    try:
        parts = text.strip().upper().split()
        
        if len(parts) >= 3:
            origen = parts[0]
            destino = parts[1]
            fecha = parts[2]
            
            # Validate airport codes (3 letters)
            if len(origen) == 3 and len(destino) == 3:
                # Validate date format (YYYY-MM or YYYY-MM-DD)
                if len(fecha) in [7, 10] and '-' in fecha:
                    return True, {
                        'origen': origen,
                        'destino': destino,
                        'fecha_salida': fecha,
                        'fecha_regreso': parts[3] if len(parts) > 3 else None
                    }
        
        return False, None
    except:
        return False, None

def handle_message(bot, message):
    """Handle incoming messages"""
    try:
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()
        
        if not chat_id or not text:
            return
        
        # Handle commands
        if text.startswith("/start"):
            welcome_text = """🎉 <b>¡Bienvenido al Bot de Vuelos Smiles!</b>

🔍 <b>Busca vuelos reales con precios auténticos</b>

📝 <b>Formato:</b>
<code>ORIGEN DESTINO FECHA</code>

💡 <b>Ejemplos:</b>
• <code>EZE MAD 2025-06</code>
• <code>BUE NYC 2025-07-15</code>
• <code>SCL MIA 2025-08</code>

✈️ Obtén precios reales en millas directamente de Smiles"""
            
            bot.send_message(chat_id, welcome_text)
            return
        
        elif text.startswith("/help"):
            help_text = """📖 <b>Ayuda - Bot de Vuelos Smiles</b>

🔍 <b>Cómo buscar vuelos:</b>
1. Escribe: ORIGEN DESTINO FECHA
2. Usa códigos de aeropuerto de 3 letras
3. Formato de fecha: YYYY-MM o YYYY-MM-DD

💡 <b>Ejemplos válidos:</b>
• <code>EZE MAD 2025-06</code> (Buenos Aires → Madrid)
• <code>GRU NYC 2025-12-25</code> (São Paulo → Nueva York)
• <code>SCL BCN 2025-09</code> (Santiago → Barcelona)

✅ El bot te mostrará precios reales en millas de Smiles"""
            
            bot.send_message(chat_id, help_text)
            return
        
        # Try to parse as flight search
        is_valid, params = parse_flight_input(text)
        
        if is_valid:
            # Send "searching" message
            bot.send_message(chat_id, f"🔍 Buscando vuelos {params['origen']} → {params['destino']}...")
            
            # Search flights
            resultado = buscar_vuelos_smiles_real(
                params['origen'], 
                params['destino'], 
                params['fecha_salida'],
                params.get('fecha_regreso')
            )
            
            # Send results
            bot.send_message(chat_id, resultado)
        
        else:
            # Invalid input
            error_text = """❌ <b>Formato incorrecto</b>

📝 <b>Usa este formato:</b>
<code>ORIGEN DESTINO FECHA</code>

💡 <b>Ejemplo:</b>
<code>EZE MAD 2025-06</code>

🔤 Los códigos de aeropuerto deben tener 3 letras
📅 La fecha debe ser YYYY-MM o YYYY-MM-DD"""
            
            bot.send_message(chat_id, error_text)
    
    except Exception as e:
        logger.error(f"Error handling message: {e}")

def main():
    """Main bot loop"""
    bot = SimpleTelegramBot(BOT_TOKEN)
    
    print("🤖 Bot de Vuelos Smiles iniciado")
    print("✅ Conectado a la API de Smiles")
    print("🔄 Presiona Ctrl+C para detener")
    
    try:
        while True:
            updates = bot.get_updates()
            
            for update in updates:
                bot.last_update_id = update.get("update_id", 0)
                
                if "message" in update:
                    handle_message(bot, update["message"])
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido")
    except Exception as e:
        logger.error(f"Error en bot: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()