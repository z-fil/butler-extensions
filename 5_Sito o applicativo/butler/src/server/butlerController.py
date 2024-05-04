from common import log
from common.requestSubmitter import RequestSubmitter
import copy

class ButlerController(RequestSubmitter):
	"""
	Questa classe permette di inviare messaggi ai Butlers.
	Estende da RequestSubmitter per usare alcune funzioni.
	"""
	
	headers = {"Accept": "application/json"}

	def __init__(self, baseUrl, authCallback):
		"""
		Istanzia un oggetto ButlerController per inviare richieste ad un Butler.

		:param baseUrl (str): la base dell'url (l'indirizzo del client) al quale connettersi.
		:param authCallback (func): la funzione di callback per ritentare l'autenticazione.
		"""
		# passare "headers" evita che i Butlers condividano i token
		super().__init__(baseUrl, authCallback, self.headers)
 
	def authenticate(self, addr, id, endpoint="/authenticate"):
		"""
		Tenta di autenticarsi al Butler.
		
		:param addr (str): l'indirizzo e la porta del server da mandare come parametro aggiuntivo.
		:param id (str): l'id del server da mandare come parametro aggiuntivo.
		:param endpoint (str, opzionale): l'endpoint del server al quale inviare i dati.
			Default: "/authenticate"
		
		:return: lo stato "ok" della risposta (True se il Butler è stato raggiunto
			e l'autenticazione è avvenuta, False in tutti gli altri casi).
		"""
		url = self.baseUrl + endpoint
		payload = {'addr': addr, 'id': id}
		response = self.request(self.POST, url, data=payload)
		result = response.json() if hasattr(response, 'json') else response
		if response.ok:
			self.headers['token'] = result['token']
			self.headers['sub'] = addr
			log.info('Connessione stabilita con {}'.format(self.baseUrl))
		else:
			result = result['message']
		return response.ok

	def status(self, endpoint="/status"):
		"""
		Richiede lo stato del Butler.
		
		:param endpoint (str, opzionale): l'endpoint del Butler.
			Default: "/status"
		
		:return: lo stato "ok" della risposta (True se il Butler è stato raggiunto,
			False in tutti gli altri casi).
		"""
		url = self.baseUrl + endpoint
		response = self.request(self.GET, url)
		log.info('Stato del Butler: {}'.format(
			'online' if response.ok else 'offline'))
		return response.ok

	def notify(self, notif, endpoint="/notify"):
		"""
		Invia una notifica al Butler.
		
		:param notif (dict, opzionale): i dati della notifica.
		:param endpoint (str, opzionale): l'endpoint del Butler.
			Default: "/notify"
		
		:return: lo stato "ok" della risposta (True se il Butler è stato raggiunto,
			False in tutti gli altri casi).
		"""
		url = self.baseUrl + endpoint
		response = self.request(self.PUT, url, data=notif)
		log.warning('Stato della notifica "{}" inviata a {}: {}'.format(
			notif['notifData']['name'], self.baseUrl, response.ok))
		return response.ok

	def revoke(self, name='', endpoint="/revoke"):
		"""
		Richiede la chiusura di una notifica.
		
		:param name (str, opzionale): il nome della notifica da revocare.
				Se il valore è vuoto, qualunque notifica verrà chiusa).
				Le notifiche di sistema sono immuni a questa funzione, ma hanno una durata breve.
			Default: ''.
		:param endpoint (str, opzionale): l'endpoint del Butler.
			Default: "/revoke"
		
		:return: il risultato della richiesta.
		"""
		url = self.baseUrl + endpoint
		response = self.request(self.DELETE, url, data={'name': name})
		return response.ok

	def disconnect(self, endpoint="/disconnect"):
		"""
		Forza la disconnessione del Butler.
		
		:param endpoint (str, opzionale): l'endpoint del Butler.
			Default: "/disconnect"
		
		:return: il risultato della richiesta.
		"""
		url = self.baseUrl + endpoint
		response = self.request(self.DELETE, url)
		return response.ok


	"""
	#####################################
	Funzioni aggiuntive butler-extensions
	#####################################
	"""

	def get_details(self, endpoint="/details"):
		"""
		Permette di ricavare i dettagli di un Butler.

		:param endpoint (str, opzionale): l'endpoint del Butler.
			Default: "/details".

		:return: i dettagli, in base ai moduli attivi sul Butler.
		"""
		url = self.baseUrl + endpoint
		response = self.request(self.GET, url)
		return response.json() if response.ok and hasattr(response, 'json') else {}

	def edit(self, payload, endpoint):
		"""
		Permette di modificare un parametro di un Butler.

		:param data (str): i dati modificati.
		:param endpoint (str, opzionale): l'endpoint del Butler.

		:return: il risultato della richiesta.
		"""
		url = self.baseUrl + endpoint
		response = self.request(self.PUT, url, data=payload)
		return response.ok

	def update_model(self, model, phase='', endpoint="/model"):
		"""
		Permette di aggiornare il modello delle connessioni ad un Butler.

		:param model (dict): il dizionario con i valori delle connessioni.
		:param phase (bool, opzionale): la fase da applicare al Butler
				Se viene lasciato il valore di default, non viene modificato.
			Default: ''.
		:param endpoint (str, opzionale): l'endpoint del Butler.
			Default: "/model".

		:return: il risultato della richiesta.
		"""
		url = self.baseUrl + endpoint
		payload = {'model': model, 'phase': phase}
		response = self.request(self.PUT, url, data=payload)
		return response.ok

	"""
	##########################################
	Fine funzioni aggiuntive butler-extensions
	##########################################
	"""
