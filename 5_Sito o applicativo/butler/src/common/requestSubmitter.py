import requests
import urllib3

from common.failedRequest import FailedRequest
from common import log

class RequestSubmitter():
	"""
	Questa classe contiene la logica di base per l'invio di richieste REST.
	"""

	GET = 'GET'
	POST = 'POST'
	PUT = 'PUT'
	DELETE = 'DELETE'

	SEE_OTHER = 303
	NOT_ALLOWED = 405

	REQUEST_TIMEOUT = 3

	baseUrl = ''
	headers = {"Accept": "application/json"}

	def __init__(self, baseUrl, authCallback, headers=headers):
		"""
		Inizializza un oggetto RequestSubmitter definendone l'url di base.

		:param url (str): la base dell'url (cioè l'indirizzo del server senza parametri).
		:param authCallback (func): la funzione per la riautenticazione
			in caso di scadenza del token.
		:param headers (dict): i parametri di default dell'header.
				Permette di collegarsi all'attributo della classe figlio, se necessario.
			Default: headers
		"""
		self.baseUrl = baseUrl
		self.authCallback = authCallback
		self.headers = headers
		urllib3.disable_warnings()
		requests.trust_env = False

	def request(self, method=GET, url='', data={}):
		"""
		Precede l'invio della richiesta permettendo di autenticarsi nuovamente
		e rimandarla in caso il token sia scaduto per non avere interruzioni.
		
		:param method (str, opzionale): una stringa identificativa del metodo da usare.
			Default: GET
		:param url (str, opzionale): l'endpoint al quale mandare la richiesta.
			Default: ''.
		:param data (dict, opzionale): il dizionario con i dati che verranno.
			Default: {}.
		
		:return: il risultato della richiesta o un oggetto FailedRequest in caso di errori.
		"""
		response = self.send(method, url, data)
		# SEE_OTHER = autenticazione mancante, ma l'host è conosciuto e può ritentare
		if response.status_code == self.SEE_OTHER:
			log.info('Richiesta a "{}" fallita a causa della chiave scaduta: nuovo tentativo di autenticazione'.format(url))
			if self.authCallback():
				response = self.send(method, url, data)
			else:
				return FailedRequest(message='L\'host ha smesso di rispondere.',
					error='L\'autenticazione automatica in seguito alla scadenza di una chiave non ha funzionato.')
		return response

	def send(self, method=GET, url='', data={}):
		"""
		Permette l'invio dei quattro tipi di richieste più comuni in base ad un
		parametro al posto di usare funzioni diverse come requests,
		e gestisce diversi possibili errori di comunicazione.
		Tutti i dati sono inviati come JSON, e anche la risposta usa questo formato:
		gli altri tipi sono considerati non validi e sollevano un errore.
		
		:param method (str, opzionale): una stringa identificativa del metodo da usare.
			Default: GET
		:param url (str, opzionale): l'endpoint al quale mandare la richiesta.
			Default: ''.
		:param data (dict, opzionale): il dizionario con i dati che verranno.
			Default: {}.
		
		:return: la risposta alla richiesta. Se questa non è di tipo JSON e quindi
			non riportabile ad un dizionario, al suo posto viene ritornato un
			oggetto FailedRequest con le informazioni sull'errore. 
		"""
		try:
			if method == self.GET:
				resp = requests.get(
					url, headers=self.headers, json=data, verify=False, timeout=self.REQUEST_TIMEOUT)
			elif method == self.POST:
				resp = requests.post(
					url, headers=self.headers, json=data, verify=False, timeout=self.REQUEST_TIMEOUT)
			elif method == self.PUT:
				resp = requests.put(
					url, headers=self.headers, json=data, verify=False, timeout=self.REQUEST_TIMEOUT)
			elif method == self.DELETE:
				resp = requests.delete(
					url, headers=self.headers, json=data, verify=False, timeout=self.REQUEST_TIMEOUT)
			else:
				return FailedRequest(message="Metodo non supportato: {}".format(method), error='Il metodo della richiesta non è tra quelli supportati')
			return self.valid_json(resp)
		except TimeoutError as e:
			return FailedRequest(message='Risposta non ricevuta entro il tempo limite', error=e.__str__())
		except NameError as e:
			return FailedRequest(message='Il metodo richiesto non può essere utilizzato', error=e.__str__())
		except requests.ConnectionError as e:
			return FailedRequest(message='Errore di connessione', error=e.__str__())
		except Exception as e:
			return FailedRequest(message='Errore generale nella richiesta', error=e.__str__())

	def valid_json(self, response):
		"""
		Verifica che la risposta ricevuta sia in formato JSON.
		
		:param response (response): la risposta ricevuta dal server.
		
		:return: la risposta se valida, altrimenti un oggetto FailedRequest.
		"""
		try:
			response.json()
			return response
		except ValueError as e:
			return FailedRequest(message='La risposta non contiene JSON valido. Errore di comnuicazione.', error=e.__str__())
