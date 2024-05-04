
import json
from authlib.jose import jwt
from flask import Flask
from Crypto.PublicKey import ECC
import datetime
from os.path import abspath, join
import sys

from common.authenticate import Authenticate

class BaseAPI():
	"""
	Questa classe contiene la logica di base per le API REST.
	"""

	ACCEPTED = 202
	UNAUTHORIZED = 401
	FORBIDDEN = 403
	BAD_METHOD = 405

	def __init__(self, ip, port, expireTime, sslConf, callbacks=[]):
		"""
		Istanzia un oggetto BaseAPI definendo ip e porta del server,
		tempo di durata dei token e funzioni di callbacks.
		
		:param ip (str): l'ip sul quale avviare l'API.
		:param port (int): la porta dell'API.
		:param expireTime (int): la durata di validità del token, in minuti.
		:param callbacks (dict): il dizionario di funzioni di callback.
		"""
		self.ip = ip
		self.port = port
		self.expireTime = expireTime
		self.sslConf = (abspath(join(sys.path[0],sslConf['certPath'])), abspath(join(sys.path[0],sslConf['keyPath'])))
		self.callbacks = callbacks

	def get_json(self, request, key, default):
		"""
		Permette di ricavare il contenuto della richiesta in base ad una chiave
		che dovrebbe trovarsi nell'attributo di dati JSON gestendo gli errori.
		
		:param request (flask.request): il contesto della richiesta ricevuta.
		:param key (str): la chiave da cercare nel diyizonario.
		:param default (obj): il valore di default da ritornare se la chiave
			non è presente o la richiesta non contiene dati JSON.
		
		:return: il contenuto del dizionario se presente, altrimenti il valore di default.
		"""
		if request.get_json() is not None:
			return request.get_json()[key] if key in request.get_json() else default
		return default


	def standard_response(self, data={}, code=200):
		"""
		Ritorna una risposta HTTP in base ai dati passati occupandosi di
		convertirli in una stringa JSON e allegandoli al codice di stato.
		
		:param data (dict, opzionale): i dati da passare insieme alla risposta.
			Default: {}.
		:param code (int, opzionale): il codice HTTP, risultato dell'operazione.
			Default: 200
		"""

		def obj_dict(obj):
			"""
			Funzione usata da json.dumps come default per ricavare un valore valido
			da oggetti complessi che non hanno una rappresentazione testuale.
			Va definita nello stesso metodo della funzione json.dumps che la sfrutta,
			altrimenti non viene rilevata.
			
			:param obj (obj): l'oggetto da convertire in stringa.
			
			:return: i valori della rappresentazione come dizionario dell'oggetto.
			"""
			return obj.__dict__ if hasattr(obj, '__dict__') else ''

		return self.flask.response_class(
			response=json.dumps(
				data, default=obj_dict).encode('UTF-8'),
			mimetype='application/json', status=code)

	def generate_keys(self):
		"""
		Genera la chiave pubblica e quella privata con l'algoritmo ECDSA
		e la curva ellittica P-256.
		
		:return: entrambe le chiavi generate.
		"""
		key = ECC.generate(curve='P-256')
		publicKey = key.public_key()
		public = publicKey.export_key(format='PEM')
		private = key.export_key(format='PEM')
		return public, private

	def init_token(self):
		"""
		Inizializza l'autenticatore specificando i dati da usare per la decodifica
		e il controllo dei token, che poi genera e ritorna.
		
		:return: il token JWT generato.
		"""
		publicKey, privateKey = self.generate_keys()
		timeLimit = datetime.datetime.utcnow(
		) + datetime.timedelta(minutes=self.expireTime)

		self.auth.key = publicKey

		# i parametri del payload sono issuer, subject, expiration time
		payload = {'iss': self.ip, 'sub': self.sub, 'exp': timeLimit}
		token = jwt.encode({'alg': 'ES256'}, payload, privateKey)
		return {
			'token': token.decode(),
			'expire': f'{timeLimit}',
			'message': 'Autenticazione da parte di "{}" riuscita'.format(self.sub)
		}


	def start_api(self):
		"""
		Avvia l'API definendo unicamente l'endpoint d'errore. 
		"""
		self.flask = Flask(__name__)
		self.auth = Authenticate()

		@self.flask.errorhandler(404)
		def page_not_found(e):
			"""
			Gestisce le richieste con endpoit non trovato (errore 404 not found),
			ritornando un dizionario con le informazioni sull'errore.
			
			:param e (obj): le informazioni sull'errore.
			
			:return: un dizionario JSON con le informazioni sull'evento.
			"""
			returnData = {
				'message': 'Errore nella richiesta',
				'error': e.__str__()
			}
			return self.standard_response(returnData, 404)
