from common import log
from common.requestSubmitter import RequestSubmitter

class Messenger(RequestSubmitter):
	"""
	Questa classe permette di inviare messaggi per comunicare con il server.
	Estende da RequestSubmitter per usare alcune funzioni.
	"""

	def __init__(self, baseUrl, authCallback):
		"""
		Istanzia un oggetto Messenger per inviare richieste al server.
		
		:param url (str): la base dell'url (l'indirizzo del server) al quale connettersi.
		:param authCallback (func): la funzione di callback per ritentare l'autenticazione.
		"""
		super().__init__(baseUrl, authCallback)

	def authenticate(self, mac, addr, user, endpoint="/authenticate"):
		"""
		Tenta di autenticarsi al server.
		
		:param addr (str): l'indirizzo IPv4 e la porta del Butler da mandare come parametro aggiuntivo.
		:param mac (str): l'indirizzo MAC del Butler da mandare come parametro aggiuntivo.
		:param user (str): il nome dell'utente da mandare come parametro aggiuntivo.
		:param endpoint (str, opzionale): l'endpoint del server al quale inviare i dati.
			Default: "/authenticate"
		
		:return: lo stato "ok" della risposta (True se il server è stato raggiunto
			e l'autenticazione è avvenuta, False in tutti gli altri casi).
		"""
		url = self.baseUrl + endpoint
		self.addr = addr
		self.mac = mac
		payload = {'mac': mac, 'addr': addr, 'user': user}
		response = self.request(self.POST, url, data=payload)

		result = response.json() if hasattr(response, 'json') else response
		if response.ok and self.baseUrl != '':
			self.headers['token'] = result['token']
			self.headers['sub'] = user
			log.info('Connessione stabilita con "{}"'.format(self.baseUrl))
		else:
			result = result['message']
		return response.ok

	def server_online(self, addr, endpoint="/status"):
		"""
		Richiede lo stato del server.
		
		:param endpoint (str, opzionale): l'endpoint del server.
			Default: "/status"
		
		:return: lo stato "ok" della risposta (True se il server è stato raggiunto,
			False in tutti gli altri casi).
		"""
		url = self.baseUrl + endpoint
		payload = {'addr': addr}
		response = self.request(self.GET, url, data=payload)
		log.info('Stato del server: {}'.format('online' if response.ok else 'offline'))
		return response.ok

	def can_disconnect(self, addr, endpoint="/disconnect"):
		"""
		Richiede al server se è possibile disconnettersi.
		
		:param addr (str): l'indirizzo identificativo del Butler che desidera disconnettersi.
		:param endpoint (str, opzionale): l'endpoint del server al quale inviare i dati.
			Default: "/disconnect"
		
		:return: lo stato "ok" della risposta (True se il server è stato raggiunto,
			False in tutti gli altri casi).
		"""
		url = self.baseUrl + endpoint
		payload = {'addr': addr}
		response = self.request(self.GET, url, payload)
		result = response.json() if response.ok and hasattr(response, 'json') else response
		# se non c'ê l'attributo il server non ha risposto
		# oppure se il codice non è 405 (non permesso)
		#return not hasattr(result, 'status_code') or result.status_code != 405
		return response.status_code != self.NOT_ALLOWED

	def interacted(self, name, endpoint="/interacted"):
		"""
		Invia l'informazione che l'utente ha interagito con il pulsante apposito
		di una notifica.
		
		:param name (str, opzionale): il nome della notifica che ha ricevuto l'interazione.
		:param endpoint (str, opzionale): l'endpoint del server al quale inviare i dati.
			Default: "/interacted"
		
		:return: lo stato "ok" della risposta (True se il server è stato raggiunto,
			False in tutti gli altri casi).
		"""
		log.info('Interazione con {}'.format(name))
		url = self.baseUrl + endpoint
		payload = {'name': name}
		response = self.request(self.GET, url, data=payload)
		return response.ok

	def disconnect(self):
		"""
		Cancella il token e l'URL di base, simulando una disconnessione.
		Deve essere chiamato solo in seguito alla richiesta di disconnessione.
		"""
		# non loggare se già disconnesso
		if self.baseUrl == '':
			return
		log.warning('Disconnessione da {}'.format(self.baseUrl))
		self.headers['token'] = ''
		self.headers['sub'] = ''
		self.baseUrl = ''


	"""
	#####################################
	Funzioni aggiuntive butler-extensions
	#####################################
	"""

	def send_details(self, details, endpoint="/details"):
		"""
		Invia i dettagli dell'host al server.

		:param details (dict): i dettagli ricavati.
		:param endpoint (str, opzionale): l'endpoint del server al quale inviare i dati.
			Default: "/details".
		"""
		url = self.baseUrl + endpoint
		payload = {'details': details}
		response = self.request(self.PUT, url, payload)
		return response.ok
		
	"""
	##########################################
	Fine funzioni aggiuntive butler-extensions
	##########################################
	"""