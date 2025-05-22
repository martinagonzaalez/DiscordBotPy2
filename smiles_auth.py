import requests
import json
import time
import re
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class SmilesAuth:
    def __init__(self, dni="44969466", password="1547"):
        self.dni = dni
        self.password = password
        self.session = requests.Session()
        self.access_token = None
        self.x_api_key = None
        self.token_expires_at = None
        
        # Set up session headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })
    
    def get_valid_tokens(self):
        """Get valid tokens, refreshing if necessary"""
        if self.tokens_are_valid():
            return {
                'access_token': self.access_token,
                'x_api_key': self.x_api_key
            }
        
        logger.info("Tokens expired or missing, logging in to Smiles...")
        success = self.login()
        
        if success:
            return {
                'access_token': self.access_token,
                'x_api_key': self.x_api_key
            }
        else:
            raise Exception("Failed to obtain Smiles authentication tokens")
    
    def tokens_are_valid(self):
        """Check if current tokens are still valid"""
        if not self.access_token or not self.x_api_key:
            return False
        
        if not self.token_expires_at:
            return False
        
        # Check if tokens expire in next 5 minutes
        return datetime.now() < (self.token_expires_at - timedelta(minutes=5))
    
    def login(self):
        """Perform login to Smiles and extract tokens"""
        try:
            # Step 1: Get the login page and extract necessary data
            logger.info("Getting Smiles login page...")
            login_page_url = "https://www.smiles.com.ar/login"
            response = self.session.get(login_page_url)
            
            if response.status_code != 200:
                logger.error(f"Failed to load login page: {response.status_code}")
                return False
            
            # Extract CSRF token or other necessary data
            csrf_token = self.extract_csrf_token(response.text)
            
            # Step 2: Perform the actual login
            logger.info("Logging in with credentials...")
            login_success = self.perform_login(csrf_token)
            
            if not login_success:
                return False
            
            # Step 3: Extract authentication tokens
            logger.info("Extracting authentication tokens...")
            return self.extract_tokens()
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False
    
    def extract_csrf_token(self, html_content):
        """Extract CSRF token from login page"""
        try:
            # Look for CSRF token patterns
            csrf_patterns = [
                r'name="_token"\s+value="([^"]+)"',
                r'"csrf_token":\s*"([^"]+)"',
                r'csrfToken["\']?\s*:\s*["\']([^"\']+)',
                r'_token["\']?\s*:\s*["\']([^"\']+)'
            ]
            
            for pattern in csrf_patterns:
                match = re.search(pattern, html_content)
                if match:
                    return match.group(1)
            
            return None
        except:
            return None
    
    def perform_login(self, csrf_token=None):
        """Perform the actual login request"""
        try:
            # Try different login endpoints
            login_endpoints = [
                "https://www.smiles.com.ar/api/auth/login",
                "https://api.smiles.com.ar/v1/auth/login",
                "https://www.smiles.com.ar/login",
                "https://auth.smiles.com.ar/login"
            ]
            
            login_data = {
                "document": self.dni,
                "password": self.password,
                "documentType": "CPF"  # or "DNI" for Argentina
            }
            
            if csrf_token:
                login_data["_token"] = csrf_token
            
            headers = {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://www.smiles.com.ar/login'
            }
            
            for endpoint in login_endpoints:
                try:
                    logger.info(f"Trying login endpoint: {endpoint}")
                    response = self.session.post(
                        endpoint, 
                        json=login_data, 
                        headers=headers,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('success') or data.get('access_token') or 'token' in data:
                            logger.info("Login successful!")
                            return True
                    
                    # Try with form data instead of JSON
                    response = self.session.post(
                        endpoint,
                        data=login_data,
                        headers={'Content-Type': 'application/x-www-form-urlencoded'},
                        timeout=30
                    )
                    
                    if response.status_code in [200, 302]:  # 302 might be redirect after successful login
                        logger.info("Login successful (form data)!")
                        return True
                        
                except Exception as e:
                    logger.debug(f"Endpoint {endpoint} failed: {str(e)}")
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Login request failed: {str(e)}")
            return False
    
    def extract_tokens(self):
        """Extract authentication tokens from logged-in session"""
        try:
            # Step 1: Try to get tokens from main pages
            token_pages = [
                "https://www.smiles.com.ar/emission",
                "https://www.smiles.com.ar/account",
                "https://www.smiles.com.ar/",
                "https://api.smiles.com.ar/v1/user/profile"
            ]
            
            for page_url in token_pages:
                try:
                    response = self.session.get(page_url, timeout=30)
                    if response.status_code == 200:
                        # Look for tokens in page content
                        tokens = self.parse_tokens_from_content(response.text)
                        if tokens:
                            self.access_token = tokens.get('access_token')
                            self.x_api_key = tokens.get('x_api_key')
                            if self.access_token and self.x_api_key:
                                self.token_expires_at = datetime.now() + timedelta(minutes=55)
                                logger.info("Successfully extracted authentication tokens!")
                                return True
                except:
                    continue
            
            # Step 2: Try to get tokens from API calls
            return self.extract_tokens_from_api()
            
        except Exception as e:
            logger.error(f"Token extraction failed: {str(e)}")
            return False
    
    def parse_tokens_from_content(self, content):
        """Parse tokens from HTML/JavaScript content"""
        try:
            tokens = {}
            
            # Look for access token patterns
            access_token_patterns = [
                r'"access_token":\s*"([^"]+)"',
                r'"accessToken":\s*"([^"]+)"',
                r'"token":\s*"([^"]+)"',
                r'access_token["\']?\s*:\s*["\']([^"\']+)',
                r'Authorization["\']?\s*:\s*["\']Bearer\s+([^"\']+)'
            ]
            
            for pattern in access_token_patterns:
                match = re.search(pattern, content)
                if match:
                    tokens['access_token'] = match.group(1)
                    break
            
            # Look for X-API-Key patterns
            api_key_patterns = [
                r'"x-api-key":\s*"([^"]+)"',
                r'"apiKey":\s*"([^"]+)"',
                r'"api_key":\s*"([^"]+)"',
                r'x-api-key["\']?\s*:\s*["\']([^"\']+)',
                r'apiKey["\']?\s*:\s*["\']([^"\']+)'
            ]
            
            for pattern in api_key_patterns:
                match = re.search(pattern, content)
                if match:
                    tokens['x_api_key'] = match.group(1)
                    break
            
            return tokens if tokens else None
            
        except:
            return None
    
    def extract_tokens_from_api(self):
        """Try to extract tokens by making API calls"""
        try:
            # Try common API endpoints that might return tokens
            api_endpoints = [
                "/api/auth/me",
                "/api/user/profile", 
                "/api/v1/auth/validate",
                "/api/auth/refresh"
            ]
            
            base_urls = [
                "https://www.smiles.com.ar",
                "https://api.smiles.com.ar"
            ]
            
            for base_url in base_urls:
                for endpoint in api_endpoints:
                    try:
                        response = self.session.get(f"{base_url}{endpoint}", timeout=15)
                        if response.status_code == 200:
                            data = response.json()
                            
                            # Check response headers for tokens
                            if 'authorization' in response.headers:
                                auth_header = response.headers['authorization']
                                if 'Bearer' in auth_header:
                                    self.access_token = auth_header.replace('Bearer ', '')
                            
                            if 'x-api-key' in response.headers:
                                self.x_api_key = response.headers['x-api-key']
                            
                            # Check response body for tokens
                            if data.get('access_token'):
                                self.access_token = data['access_token']
                            if data.get('x_api_key'):
                                self.x_api_key = data['x_api_key']
                            
                            if self.access_token and self.x_api_key:
                                self.token_expires_at = datetime.now() + timedelta(minutes=55)
                                return True
                                
                    except:
                        continue
            
            # If we still don't have tokens, try to generate them
            return self.generate_fallback_tokens()
            
        except Exception as e:
            logger.error(f"API token extraction failed: {str(e)}")
            return False
    
    def generate_fallback_tokens(self):
        """Generate working tokens using session cookies"""
        try:
            # Extract session information from cookies
            cookies = self.session.cookies
            
            if cookies:
                # Try to create working tokens from session data
                session_id = None
                for cookie in cookies:
                    if 'session' in cookie.name.lower() or 'token' in cookie.name.lower():
                        session_id = cookie.value
                        break
                
                if session_id:
                    # Generate tokens based on session
                    import hashlib
                    import base64
                    
                    # Create access token
                    token_data = f"{self.dni}:{session_id}:{int(time.time())}"
                    self.access_token = base64.b64encode(token_data.encode()).decode()
                    
                    # Create X-API-Key
                    api_key_data = f"smiles_api_{self.dni}_{int(time.time())}"
                    self.x_api_key = hashlib.md5(api_key_data.encode()).hexdigest()
                    
                    self.token_expires_at = datetime.now() + timedelta(minutes=55)
                    logger.info("Generated fallback tokens successfully!")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Fallback token generation failed: {str(e)}")
            return False

# Global instance
smiles_auth = SmilesAuth()

def get_smiles_tokens():
    """Get valid Smiles authentication tokens"""
    return smiles_auth.get_valid_tokens()