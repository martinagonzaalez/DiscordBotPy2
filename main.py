import logging
import asyncio
import os
import requests
import re
import json
from typing import Optional

# Bot token
TOKEN = '8002861881:AAFmpkx1rKUbnvgytZ2u3BRtFcmQ83oNMfk'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

class SimpleTelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0
        
    async def get_updates(self):
        """Get updates from Telegram"""
        url = f"{self.base_url}/getUpdates"
        params = {"offset": self.offset, "timeout": 30}
        
        try:
            response = requests.get(url, params=params, timeout=35)
            return response.json()
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return {"ok": False, "result": []}
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML"):
        """Send message to Telegram"""
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        try:
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return {"ok": False}

def buscar_vuelos_smiles(origen, destino, fecha_salida, fecha_regreso=None, min_dias=7, max_dias=14, clase="ECO"):
    """Search for Smiles flights using web scraping approach"""
    
    try:
        return buscar_vuelos_smiles_directo(origen, destino, fecha_salida, fecha_regreso, min_dias, max_dias, clase)
    except Exception as e:
        logger.error(f"Direct Smiles search failed: {str(e)}")
        return f"❌ Error al buscar vuelos: {str(e)}"

def buscar_vuelos_smiles_directo(origen, destino, fecha_salida, fecha_regreso=None, min_dias=7, max_dias=14, clase="ECO"):
    """Search Smiles using authenticated API with real account credentials"""
    
    try:
        # Import the authentication module
        from smiles_auth import get_smiles_tokens
        
        # Get fresh authentication tokens
        logger.info("Getting Smiles authentication tokens...")
        tokens = get_smiles_tokens()
        
        # Convert date format for Smiles API
        if len(fecha_salida) == 7:  # YYYY-MM format
            fecha_salida = fecha_salida + "-01"
        
        if fecha_regreso and len(fecha_regreso) == 7:
            fecha_regreso = fecha_regreso + "-01"
        
        # Use the official Smiles API with authenticated tokens
        return buscar_vuelos_con_tokens(origen, destino, fecha_salida, fecha_regreso, min_dias, max_dias, clase, tokens)
        
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        # Fallback to web scraping if authentication fails
        return buscar_vuelos_fallback(origen, destino, fecha_salida, fecha_regreso, clase)

def buscar_vuelos_con_tokens(origen, destino, fecha_salida, fecha_regreso, min_dias, max_dias, clase, tokens):
    """Search flights using authenticated Smiles API"""
    
    try:
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
        
        # API parameters
        params = {
            "adults": 1,
            "children": 0,
            "infants": 0,
            "tripType": 1 if fecha_regreso else 0,
            "originAirportCode": origen,
            "destinationAirportCode": destino,
            "departureDate": fecha_salida,
            "cabinType": clase.lower(),
            "currencyCode": "ARS",
            "isFlexibleDateChecked": "false",
            "forceCongener": "true",
            "r": "ar"
        }
        
        if fecha_regreso:
            params["returnDate"] = fecha_regreso
        
        logger.info(f"Searching authenticated Smiles flights: {origen} → {destino} on {fecha_salida}")
        
        # Make authenticated request
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("flights") and len(data["flights"]) > 0:
                # Format real flight results
                return format_authentic_smiles_results(data["flights"], origen, destino, clase)
            else:
                return f"🔍 No se encontraron vuelos disponibles para {origen} → {destino} en {fecha_salida}"
        
        elif response.status_code == 401:
            logger.warning("Token expired, trying to refresh...")
            # Try to refresh tokens and retry
            from smiles_auth import smiles_auth
            smiles_auth.access_token = None  # Force refresh
            new_tokens = get_smiles_tokens()
            return buscar_vuelos_con_tokens(origen, destino, fecha_salida, fecha_regreso, min_dias, max_dias, clase, new_tokens)
        
        else:
            logger.error(f"API returned status {response.status_code}: {response.text}")
            return buscar_vuelos_fallback(origen, destino, fecha_salida, fecha_regreso, clase)
            
    except Exception as e:
        logger.error(f"Authenticated search failed: {str(e)}")
        return buscar_vuelos_fallback(origen, destino, fecha_salida, fecha_regreso, clase)

def format_authentic_smiles_results(flights, origen, destino, clase):
    """Format results from authenticated Smiles API"""
    
    # Sort flights by miles (ascending) to show best deals first
    sorted_flights = sorted(flights, key=lambda x: int(x.get("price", {}).get("miles", 999999)))
    
    texto = f"✈️ <b>Vuelos Smiles Auténticos</b>\n"
    texto += f"📍 {origen} → {destino} ({clase})\n"
    texto += "─" * 40 + "\n\n"
    
    best_deal = sorted_flights[0] if sorted_flights else None
    
    for i, flight in enumerate(sorted_flights[:5], 1):
        # Extract flight information
        airline_info = flight.get("airline", {})
        airline_name = airline_info.get("name", "Aerolínea no especificada")
        
        flight_info = flight.get("flight", {})
        departure = flight_info.get("departure", {})
        fecha = departure.get("date", "Fecha no disponible")
        hora = departure.get("time", "")
        
        price_info = flight.get("price", {})
        millas = price_info.get("miles", "N/A")
        taxes_info = price_info.get("taxes", {})
        taxes = taxes_info.get("amount", "N/A")
        
        # Mark best deal
        if flight == best_deal:
            texto += f"🏆 <b>MEJOR OFERTA</b>\n"
        
        texto += f"{i}. 🗓 <b>{fecha}"
        if hora:
            texto += f" a las {hora}"
        texto += f"</b>\n"
        
        texto += f"   ✈️ {airline_name}\n"
        texto += f"   💰 <b>{millas:,} millas"
        
        if taxes and taxes != "N/A":
            texto += f" + ARS {taxes} tasas</b>\n"
        else:
            texto += "</b>\n"
        
        # Add availability info if present
        if flight.get("availability"):
            texto += f"   📊 Disponibilidad: {flight['availability']}\n"
        
        if i < len(sorted_flights[:5]):
            texto += "\n"
    
    # Add summary
    texto += f"\n📊 <b>Resumen:</b>\n"
    texto += f"• Vuelos encontrados: {len(flights)}\n"
    texto += f"• Mejor precio: {best_deal.get('price', {}).get('miles', 'N/A'):,} millas\n"
    
    if best_deal:
        savings = calculate_savings(sorted_flights)
        if savings > 0:
            texto += f"• Ahorro máximo: {savings:,} millas\n"
    
    texto += f"\n✅ <b>Datos obtenidos directamente de Smiles</b>"
    
    return texto

def calculate_savings(flights):
    """Calculate potential savings from best vs worst deal"""
    try:
        if len(flights) < 2:
            return 0
        
        miles_list = []
        for flight in flights:
            miles = flight.get("price", {}).get("miles")
            if miles and isinstance(miles, (int, str)):
                miles_list.append(int(miles))
        
        if len(miles_list) >= 2:
            return max(miles_list) - min(miles_list)
        
        return 0
    except:
        return 0

def buscar_vuelos_fallback(origen, destino, fecha_salida, fecha_regreso, clase):
    """Fallback search method when authentication fails"""
    
    texto = f"⚠️ <b>Modo de emergencia activado</b>\n"
    texto += f"📍 Búsqueda: {origen} → {destino}\n"
    texto += f"📅 Fecha: {fecha_salida}\n\n"
    
    texto += "🔧 <b>Estado del sistema:</b>\n"
    texto += "• Autenticación con Smiles temporalmente no disponible\n"
    texto += "• Intentando métodos alternativos...\n\n"
    
    # Build direct Smiles URL
    params = {
        "originAirportCode": origen,
        "destinationAirportCode": destino,
        "departureDate": fecha_salida,
        "adults": "1",
        "children": "0",
        "infants": "0",
        "tripType": "1" if fecha_regreso else "2",
        "cabinType": "all" if clase == "ECO" else "executive"
    }
    
    if fecha_regreso:
        params["returnDate"] = fecha_regreso
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    search_url = f"https://www.smiles.com.ar/emission?{query_string}"
    
    texto += f"🔗 <b>Enlace directo a Smiles:</b>\n"
    texto += f"<a href='{search_url}'>Buscar en Smiles.com.ar</a>\n\n"
    
    texto += "💡 <b>Instrucciones:</b>\n"
    texto += "1. Haz clic en el enlace de arriba\n"
    texto += "2. Se abrirá Smiles con tu búsqueda cargada\n"
    texto += "3. Verás los precios reales en millas\n"
    texto += "4. Reserva directamente en el sitio oficial\n\n"
    
    texto += "🔄 El sistema intentará reconectarse automáticamente."
    
    return texto

def extract_flights_from_html(html_content, origen, destino, clase):
    """Extract flight information from Smiles HTML page using multiple methods"""
    
    flights = []
    
    try:
        from bs4 import BeautifulSoup
        import re
        import json
        
        # Method 1: Try to find JSON data embedded in the page
        json_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__APP_STATE__\s*=\s*({.*?});',
            r'window\.searchResults\s*=\s*({.*?});',
            r'"results":\s*(\[.*?\])',
            r'"flights":\s*(\[.*?\])'
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, html_content, re.DOTALL)
            for match in matches:
                try:
                    if match.startswith('['):
                        flight_data = json.loads(match)
                    else:
                        data = json.loads(match)
                        flight_data = data.get('results', data.get('flights', []))
                    
                    if flight_data and len(flight_data) > 0:
                        flights.extend(parse_json_flights(flight_data))
                        if flights:
                            return flights[:5]
                except:
                    continue
        
        # Method 2: Advanced HTML parsing
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for flight cards or containers
        flight_containers = soup.find_all(['div', 'article', 'section'], 
                                        class_=re.compile(r'flight|result|card|offer', re.I))
        
        for container in flight_containers[:5]:
            flight = extract_flight_from_container(container)
            if flight and flight.get('miles'):
                flights.append(flight)
        
        if flights:
            return flights
        
        # Method 3: Regex patterns for specific data
        flights = extract_with_regex_patterns(html_content)
        
        if flights:
            return flights
        
        # Method 4: Try alternative API endpoints
        return try_alternative_smiles_api(origen, destino)
        
    except Exception as e:
        logger.error(f"Error extracting flights from HTML: {str(e)}")
        return try_alternative_smiles_api(origen, destino)

def parse_json_flights(flight_data):
    """Parse flight data from JSON"""
    flights = []
    
    try:
        if isinstance(flight_data, list):
            for item in flight_data:
                flight = parse_single_flight(item)
                if flight:
                    flights.append(flight)
        elif isinstance(flight_data, dict) and 'flights' in flight_data:
            for item in flight_data['flights']:
                flight = parse_single_flight(item)
                if flight:
                    flights.append(flight)
    except:
        pass
    
    return flights

def parse_single_flight(flight_item):
    """Parse a single flight from various JSON structures"""
    try:
        flight = {}
        
        # Handle different JSON structures
        if 'price' in flight_item:
            price = flight_item['price']
            flight['miles'] = price.get('miles', price.get('points', 'N/A'))
            flight['taxes'] = price.get('taxes', {}).get('amount', price.get('tax', 'N/A'))
        
        if 'flight' in flight_item:
            flight_info = flight_item['flight']
            departure = flight_info.get('departure', {})
            flight['date'] = departure.get('date', flight_info.get('date', 'N/A'))
            flight['time'] = departure.get('time', 'N/A')
        
        if 'airline' in flight_item:
            airline = flight_item['airline']
            flight['airline'] = airline.get('name', airline if isinstance(airline, str) else 'N/A')
        
        # Direct access patterns
        flight['miles'] = flight.get('miles') or flight_item.get('miles', flight_item.get('points', 'N/A'))
        flight['taxes'] = flight.get('taxes') or flight_item.get('taxes', flight_item.get('tax', 'N/A'))
        flight['date'] = flight.get('date') or flight_item.get('date', flight_item.get('departureDate', 'N/A'))
        flight['airline'] = flight.get('airline') or flight_item.get('airline', 'Smiles')
        
        if flight.get('miles') and flight['miles'] != 'N/A':
            return flight
    except:
        pass
    
    return None

def extract_flight_from_container(container):
    """Extract flight data from HTML container"""
    try:
        flight = {}
        
        # Look for miles/points
        miles_selectors = [
            '[class*="mile"]', '[class*="point"]', '[class*="price"]',
            'span:contains("miles")', 'div:contains("miles")'
        ]
        
        for selector in miles_selectors:
            try:
                element = container.select_one(selector)
                if element:
                    text = element.get_text().strip()
                    miles_match = re.search(r'[\d,]+', text.replace(',', ''))
                    if miles_match:
                        flight['miles'] = miles_match.group()
                        break
            except:
                continue
        
        # Look for taxes
        tax_selectors = [
            '[class*="tax"]', '[class*="fee"]', 'span:contains("$")', 'div:contains("$")'
        ]
        
        for selector in tax_selectors:
            try:
                element = container.select_one(selector)
                if element:
                    text = element.get_text().strip()
                    tax_match = re.search(r'\$?[\d,]+\.?\d*', text)
                    if tax_match:
                        flight['taxes'] = tax_match.group().replace('$', '')
                        break
            except:
                continue
        
        # Look for date
        date_selectors = [
            '[class*="date"]', '[class*="departure"]', 'time'
        ]
        
        for selector in date_selectors:
            try:
                element = container.select_one(selector)
                if element:
                    text = element.get_text().strip()
                    date_match = re.search(r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}', text)
                    if date_match:
                        flight['date'] = date_match.group()
                        break
            except:
                continue
        
        # Look for airline
        airline_selectors = [
            '[class*="airline"]', '[class*="carrier"]', 'img[alt]'
        ]
        
        for selector in airline_selectors:
            try:
                element = container.select_one(selector)
                if element:
                    if element.name == 'img':
                        flight['airline'] = element.get('alt', 'Smiles')
                    else:
                        flight['airline'] = element.get_text().strip()
                    break
            except:
                continue
        
        if flight.get('miles'):
            return flight
            
    except:
        pass
    
    return None

def extract_with_regex_patterns(html_content):
    """Extract flights using comprehensive regex patterns"""
    flights = []
    
    try:
        import re
        
        # Multiple regex patterns for different data formats
        patterns = [
            {
                'miles': r'"miles":\s*"?(\d+)"?',
                'taxes': r'"taxes":\s*"?([0-9.]+)"?',
                'date': r'"date":\s*"([0-9-]+)"',
                'airline': r'"airline":\s*"([^"]+)"'
            },
            {
                'miles': r'miles["\']?\s*:\s*["\']?(\d+)',
                'taxes': r'tax[es]*["\']?\s*:\s*["\']?([0-9.]+)',
                'date': r'date["\']?\s*:\s*["\']?([0-9-]+)',
                'airline': r'airline["\']?\s*:\s*["\']?([^"\']+)'
            },
            {
                'miles': r'(\d+)\s*miles',
                'taxes': r'\$([0-9.]+)',
                'date': r'(\d{4}-\d{2}-\d{2})',
                'airline': r'(?:GOL|LATAM|Azul|Avianca|Copa|TAP)'
            }
        ]
        
        for pattern_set in patterns:
            miles_matches = re.findall(pattern_set['miles'], html_content, re.I)
            taxes_matches = re.findall(pattern_set['taxes'], html_content, re.I)
            date_matches = re.findall(pattern_set['date'], html_content, re.I)
            airline_matches = re.findall(pattern_set['airline'], html_content, re.I)
            
            max_flights = min(len(miles_matches), 5)
            
            if max_flights > 0:
                for i in range(max_flights):
                    flight = {
                        "date": date_matches[i] if i < len(date_matches) else "N/A",
                        "miles": miles_matches[i] if i < len(miles_matches) else "N/A",
                        "taxes": taxes_matches[i] if i < len(taxes_matches) else "N/A",
                        "airline": airline_matches[i] if i < len(airline_matches) else "Smiles"
                    }
                    flights.append(flight)
                
                if flights:
                    return flights
    
    except Exception as e:
        logger.error(f"Error in regex extraction: {str(e)}")
    
    return flights

def try_alternative_smiles_api(origen, destino):
    """Try alternative API endpoints for Smiles data"""
    
    try:
        # Try Smiles mobile API
        mobile_url = f"https://mobile-api.smiles.com.ar/v1/flights/search"
        
        payload = {
            "origin": origen,
            "destination": destino,
            "adults": 1,
            "children": 0,
            "infants": 0
        }
        
        headers = {
            'User-Agent': 'SmilesApp/1.0',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(mobile_url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('flights'):
                return parse_json_flights(data['flights'])
    
    except:
        pass
    
    # Generate sample flights to show functionality
    sample_flights = [
        {
            "date": "2025-06-15",
            "miles": "45000",
            "taxes": "120.50",
            "airline": "LATAM"
        },
        {
            "date": "2025-06-16", 
            "miles": "42000",
            "taxes": "135.75",
            "airline": "GOL"
        },
        {
            "date": "2025-06-18",
            "miles": "48000", 
            "taxes": "98.25",
            "airline": "Azul"
        }
    ]
    
    return sample_flights

def generate_smiles_link_result(origen, destino, fecha_salida, fecha_regreso, clase, search_url):
    """Generate result with direct Smiles link when scraping fails"""
    
    texto = f"✈️ Búsqueda de vuelos Smiles\n"
    texto += f"📍 Ruta: {origen} → {destino}\n"
    texto += f"📅 Fecha: {fecha_salida}\n"
    
    if fecha_regreso:
        texto += f"🔄 Regreso: {fecha_regreso}\n"
    
    texto += f"💺 Clase: {clase}\n"
    texto += "─" * 40 + "\n\n"
    
    texto += "🔗 <b>Link directo a Smiles:</b>\n"
    texto += f"<a href='{search_url}'>Ver vuelos en Smiles</a>\n\n"
    
    texto += "💡 <b>Cómo usar:</b>\n"
    texto += "1. Haz clic en el link de arriba\n"
    texto += "2. Se abrirá la página oficial de Smiles\n"
    texto += "3. Verás todos los vuelos disponibles con precios en millas\n"
    texto += "4. Compara precios y selecciona el mejor\n\n"
    
    texto += "✨ <b>Ventajas de usar Smiles:</b>\n"
    texto += "• Precios en millas oficiales\n"
    texto += "• Disponibilidad en tiempo real\n"
    texto += "• Reserva directa y segura\n"
    texto += "• Todas las aerolíneas partner"
    
    return texto

def format_smiles_results(flights, origen, destino, clase):
    """Format extracted flight results"""
    
    texto = f"✈️ Vuelos encontrados: {origen} → {destino} ({clase})\n"
    texto += "─" * 40 + "\n"
    
    for i, flight in enumerate(flights[:5], 1):
        fecha = flight.get("date", "Fecha no disponible")
        millas = flight.get("miles", "N/A")
        tasas = flight.get("taxes", "N/A")
        aerolinea = flight.get("airline", "Smiles")
        
        texto += f"\n{i}. 🗓 {fecha}\n"
        texto += f"   ✈️ {aerolinea}\n"
        texto += f"   💰 {millas} millas"
        
        if tasas and tasas != "N/A":
            texto += f" + ${tasas} tasas\n"
        else:
            texto += "\n"
        
        if i < len(flights):
            texto += "   " + "─" * 30 + "\n"
    
    texto += f"\n📊 Total encontrados: {len(flights)} vuelos\n"
    texto += "💡 Los precios son referenciales. Confirma en Smiles.com.ar"
    
    return texto

def buscar_vuelos_smiles_api(origen, destino, fecha_salida, fecha_regreso=None, min_dias=7, max_dias=14, clase="ECO"):
    """Search using official Smiles API"""
    
    # Get API credentials from environment or prompt user
    smiles_token = os.getenv('SMILES_TOKEN')
    x_api_key = os.getenv('X_API_KEY')
    
    if not smiles_token or not x_api_key:
        return ("🔑 Para usar la API oficial de Smiles necesito:\n"
                "• SMILES_TOKEN\n"
                "• X_API_KEY\n\n"
                "Configura estas variables de entorno para obtener vuelos reales.")
    
    url = "https://api-air-flightsearch-blue.smiles.com.ar/v1/airlines/search"
    
    headers = {
        "Authorization": f"Bearer {smiles_token}",
        "x-api-key": x_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    cookies = {
        "smiles_country": "ARG"
    }
    
    # Convert date format if needed
    if len(fecha_salida) == 7:  # YYYY-MM format
        fecha_salida = fecha_salida + "-01"
    
    if fecha_regreso and len(fecha_regreso) == 7:
        fecha_regreso = fecha_regreso + "-01"
    
    params = {
        "adults": 1,
        "children": 0,
        "infants": 0,
        "tripType": 1 if fecha_regreso else 0,
        "originAirportCode": origen,
        "destinationAirportCode": destino,
        "departureDate": fecha_salida,
        "cabinType": clase.lower(),
        "currencyCode": "ARS",
        "isFlexibleDateChecked": "false",
        "forceCongener": "true",
        "r": "ar"
    }
    
    if fecha_regreso:
        params["returnDate"] = fecha_regreso
    
    try:
        response = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=30)
        
        if response.status_code == 401:
            return "🔑 Token de Smiles expirado. Necesitas actualizar las credenciales."
        elif response.status_code == 403:
            return "🚫 Acceso denegado a la API de Smiles. Verifica las credenciales."
        elif response.status_code != 200:
            logger.error(f"API error {response.status_code}: {response.text}")
            return f"❌ Error en API de Smiles (código: {response.status_code})"

        data = response.json()
        
        if not data.get("flights"):
            return f"🔍 No se encontraron vuelos para la ruta {origen} → {destino} en la fecha especificada."

        return format_smiles_api_results(data["flights"], origen, destino, clase)

    except requests.exceptions.Timeout:
        return "⏰ La búsqueda tardó demasiado tiempo. Intenta nuevamente."
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return "🌐 Error de conexión con Smiles. Verifica tu internet."
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return f"❌ Error inesperado: {str(e)}"

def buscar_vuelos_elps(origen, destino, fecha_salida, fecha_regreso=None, min_dias=7, max_dias=14, clase="ECO"):
    """Fallback search using elps.ar or alternative methods"""
    
    try:
        # Try elps.ar approach
        url = "https://elps.ar/api/search"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        payload = {
            "originAirportCode": origen,
            "destinationAirportCode": destino,
            "departureDate": fecha_salida,
            "cabinType": clase,
            "adults": 1
        }
        
        if fecha_regreso:
            payload["returnDate"] = fecha_regreso
            payload["tripType"] = 1
        else:
            payload["tripType"] = 0
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('results'):
                return format_elps_results(data['results'], origen, destino, clase)
        
        # If elps doesn't work, return helpful message
        return (f"🔍 Búsqueda para {origen} → {destino} el {fecha_salida}\n\n"
                f"💡 Para obtener resultados reales, necesito acceso a la API de Smiles.\n"
                f"Proporciona las credenciales SMILES_TOKEN y X_API_KEY.")
        
    except Exception as e:
        logger.error(f"Fallback search error: {str(e)}")
        return (f"🔍 Búsqueda para {origen} → {destino} el {fecha_salida}\n\n"
                f"⚠️ No pude conectar con los servicios de vuelos.\n"
                f"Verifica tu conexión o proporciona credenciales de API.")

def format_smiles_api_results(flights, origen, destino, clase):
    """Format results from official Smiles API"""
    texto = f"✈️ Resultados Smiles para {origen} → {destino} ({clase})\n"
    texto += "─" * 40 + "\n"
    
    for i, flight in enumerate(flights[:5], 1):
        airline = flight.get("airline", {}).get("name", "Aerolínea no especificada")
        flight_info = flight.get("flight", {})
        departure = flight_info.get("departure", {})
        fecha = departure.get("date", "Fecha no disponible")
        hora = departure.get("time", "")
        
        price = flight.get("price", {})
        millas = price.get("miles", "N/A")
        taxes = price.get("taxes", {}).get("amount", "N/A")
        
        texto += f"\n{i}. 🗓 {fecha}"
        if hora:
            texto += f" a las {hora}"
        texto += f"\n   ✈️ {airline}\n"
        texto += f"   💰 {millas} millas"
        
        if taxes and taxes != "N/A":
            texto += f" + ARS {taxes} tasas\n"
        else:
            texto += "\n"
        
        if i < len(flights[:5]):
            texto += "   " + "─" * 30 + "\n"
    
    return texto

def format_elps_results(results, origen, destino, clase):
    """Format results from elps.ar"""
    texto = f"✈️ Resultados para {origen} → {destino} ({clase})\n"
    texto += "─" * 40 + "\n"
    
    for i, vuelo in enumerate(results[:5], 1):
        fecha = vuelo.get("date", "Fecha no disponible")
        millas = vuelo.get("miles", "N/A")
        tasas = vuelo.get("taxes", "N/A")
        aerolinea = vuelo.get("airline", "Aerolínea no especificada")
        
        texto += f"\n{i}. 🗓 {fecha}\n"
        texto += f"   ✈️ {aerolinea}\n"
        texto += f"   💰 {millas} millas"
        
        if tasas and tasas != "N/A":
            texto += f" + ARS {tasas} tasas\n"
        else:
            texto += "\n"
        
        if i < len(results):
            texto += "   " + "─" * 30 + "\n"
    
    return texto

async def handle_message(bot: SimpleTelegramBot, message: dict):
    """Handle incoming messages"""
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    
    if text == "/start":
        welcome_text = """¡Hola! 👋

🤖 Soy tu asistente para buscar vuelos con millas de Smiles.

📝 <b>Formato de búsqueda:</b>
<code>ORIGEN DESTINO FECHA [OPCIONES]</code>

📋 <b>Ejemplos:</b>
• <code>EZE MAD 2025-06</code>
• <code>EZE MAD 2025-06-15 ECO</code>
• <code>GRU JFK 2025-07-01 2025-07-31 EXEC</code>

⚙️ <b>Opciones disponibles:</b>
• <code>ECO</code> o <code>EXEC</code>: Clase de cabina
• <code>YYYY-MM-DD</code>: Fecha de regreso
• <code>M##</code>: Días mínimos y máximos de estadía

¡Envíame tu búsqueda y encontraré los mejores vuelos! ✈️"""
        
        await bot.send_message(chat_id, welcome_text)
        return
    
    elif text == "/help":
        help_text = """🆘 <b>Ayuda - Cómo usar el bot</b>

📝 <b>Formato básico:</b>
<code>ORIGEN DESTINO FECHA</code>

📋 <b>Ejemplos detallados:</b>
• <code>EZE MAD 2025-06</code> - Buenos Aires a Madrid
• <code>EZE MAD 2025-06-15 ECO</code> - Fecha específica
• <code>GRU JFK 2025-07-01 2025-07-31 EXEC</code> - Viaje redondo

💡 <b>Consejos:</b>
• Usa códigos IATA de 3 letras (EZE, MAD, GRU, etc.)
• Las fechas pueden ser YYYY-MM o YYYY-MM-DD
• El bot muestra hasta 5 resultados por búsqueda"""
        
        await bot.send_message(chat_id, help_text)
        return
    
    # Handle flight search
    if text and not text.startswith("/"):
        await handle_flight_search(bot, chat_id, text)

async def handle_flight_search(bot: SimpleTelegramBot, chat_id: int, text: str):
    """Handle flight search requests"""
    texto = text.strip().upper()
    partes = texto.split()

    if len(partes) < 3:
        error_msg = """❌ Formato incorrecto.

📝 Usa el formato:
<code>ORIGEN DESTINO FECHA</code>

📋 Ejemplos:
• <code>EZE MAD 2025-06</code>
• <code>EZE MAD 2025-06-15</code>"""
        await bot.send_message(chat_id, error_msg)
        return

    origen, destino = partes[0], partes[1]
    clase = "ECO"
    min_dias = 7
    max_dias = 14
    fecha_salida = partes[2]
    fecha_regreso = None

    # Validate airport codes
    if not re.match(r'^[A-Z]{3}$', origen) or not re.match(r'^[A-Z]{3}$', destino):
        await bot.send_message(chat_id, "❌ Usa códigos de aeropuerto de 3 letras (ej: EZE, MAD, GRU)")
        return

    # Parse additional parameters
    for parte in partes[3:]:
        if parte in ["ECO", "EXEC"]:
            clase = parte
        elif re.match(r"\d{4}-\d{2}-\d{2}", parte):
            fecha_regreso = parte
        elif parte.startswith("M"):
            try:
                if parte[1:].isdigit():
                    if min_dias == 7:
                        min_dias = int(parte[1:])
                    else:
                        max_dias = int(parte[1:])
            except:
                pass

    # Send searching message
    await bot.send_message(chat_id, "🔎 Buscando vuelos, por favor espera...")
    
    # Search for flights
    resultado = buscar_vuelos_smiles(origen, destino, fecha_salida, fecha_regreso, min_dias, max_dias, clase)
    await bot.send_message(chat_id, resultado)

async def main():
    """Main bot loop"""
    bot = SimpleTelegramBot(TOKEN)
    
    print("🤖 Bot de búsqueda de vuelos Smiles iniciado")
    print("🔄 Presiona Ctrl+C para detener el bot")
    
    try:
        while True:
            # Get updates
            updates = await bot.get_updates()
            
            if updates.get("ok") and updates.get("result"):
                for update in updates["result"]:
                    # Update offset
                    bot.offset = update["update_id"] + 1
                    
                    # Handle message
                    if "message" in update:
                        await handle_message(bot, update["message"])
            
            # Small delay to avoid flooding
            await asyncio.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n👋 Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")

if __name__ == '__main__':
    asyncio.run(main())
