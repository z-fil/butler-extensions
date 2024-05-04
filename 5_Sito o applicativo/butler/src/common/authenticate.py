import json
from authlib.jose import jwt
import authlib.jose
from flask import Flask, request
from functools import wraps

from common import log


class Authenticate():
	"""
	Middleware utilizzato per la gestione, la decodifica e la verifica dei token JWT.
	Le richieste ritornano lo stato 401 se manca l'autenticazione,
	oppure 303 se l'identità della richiesta è nota ma il token non ê valido.
	"""

	UNAUTHORIZED = 401
	SEE_OTHER = 303
	INTERNAL_ERROR = 500

	def __init__(self):
		"""
		Istanzia un oggetto Authenticate inizializzando la chiave.
		"""
		self.flask = Flask(__name__)
		self.key = ''

	def token_required(self, caller, *args, **kwargs):
		"""
		Implementa la funzione di controllo del token.
		
		:param caller (func): la funzione che include questo decorator.
		
		:return: la funzione wrap.
		"""
		@wraps(caller, *args,  **kwargs)
		def wrap():
			"""
			Decodifica il token e ne verifica la validità.
			
			:return: la risposta con le informazioni sull'errore se presente,
				altrimenti ''.
			"""
			try:
				if request.content_type != 'application/json':
					returnData = {
						'error': 'Tipo della richiesta diverso da application/json',
						'message': 'Sono accettati solo valori in formato JSON'
					}
					log.warning('{}: {}'.format(returnData['error'], returnData['message']))
					return self.standard_response(returnData, self.UNAUTHORIZED)
				if 'token' not in request.headers or request.headers['token'] == '':
					returnData = {
						'error': 'Parametro "token" non trovato nell\'header: operazione bloccata',
						'message': 'È richiesto un token per questa operazione',
						'invalidToken': True
					}
					log.warning('{}: {}'.format(returnData['error'], returnData['message']))
					return self.standard_response(returnData, self.UNAUTHORIZED)
				if self.key == '':
					returnData = {
						'error': 'Chiave non inizializzata. Autenticazione mancante',
						'message': 'Chiave di decodifica mancante',
						'invalidToken': True
					}
					log.warning('{}: {}'.format(returnData['error'], returnData['message']))
					return self.standard_response(returnData, self.SEE_OTHER) 

				token = request.headers['token']
				requestSub = request.headers['sub']
				if 'sub' not in request.headers:
					returnData = {
						'error': 'Il parametro "sub" {} della richiesta non corrisponde a quello richiesto'.format(requestSub),
						'message': 'Parametro "sub" invalido'
					}
					log.warning('{}: {}'.format(returnData['error'], returnData['message']))
					return self.standard_response(returnData, self.UNAUTHORIZED)
				
				options = {
					'sub': {
						'essential': True,
						'value': request.headers['sub']
					}
				}
				claims = jwt.decode(token, self.key, claims_options=options)
				claims.validate()

				return caller()
			except authlib.jose.errors.JoseError as e:
				returnData = {
					'error': e.__str__(),
					'message': 'Token non valido',
					'invalidToken': True
				}
				log.warning('{}: {}'.format(returnData['error'],returnData['message']))
				return self.standard_response(returnData, self.SEE_OTHER)
			'''except Exception as e:
				returnData = {
					'error': getattr(e, 'message', repr(e)),
					'message': 'Errore interno della gestione della richiesta'
				}
				log.critical(returnData['error']+' : '+returnData['message'])
				return self.standard_response(returnData, self.INTERNAL_ERROR)
			'''
		return wrap

	def standard_response(self, data={}, code=UNAUTHORIZED):
		"""
		Ritorna una risposta HTTP in base ai dati passati occupandosi di
		convertirli in una stringa JSON e allegandoli al codice di stato.
		
		:param data (dict, opzionale): i dati da passare insieme alla risposta.
			Default: {}.
		:param code (int, opzionale): il codice HTTP, risultato dell'operazione.
			Default: UNAUTHORIZED (401)
		"""
		return self.flask.response_class(
			response=json.dumps(data).encode('UTF-8'), mimetype='application/json', status=code)
