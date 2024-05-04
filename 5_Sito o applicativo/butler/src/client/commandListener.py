from flask import request
from os import _exit

from common import log
from common.baseAPI import BaseAPI

class CommandListener(BaseAPI):
	"""
	Questa classe funge da API REST per le richieste del server.
	Estende da BaseAPI che definisce parte della logica di base. 
	"""

	def __init__(self, ip, port, expireTime, sslConf, callbacks):
		"""
		Istanzia un oggetto CommandListener definendone ip e porta sul quale lavorare,
		la durata dei token generati e le funzioni di callback disponibili.

		:param ip (str): l'ip sul quale attivare l'API.
		:param port (int): la porta specifica dell'API.
		:param expireTime (float): i minuti di durata dei token.
		:param sslConf (list): il percorso del certificato e della chiave SSL.
		:param callbacks (dict): la lista di callback, identificate da chiavi.
		"""
		super().__init__(ip, port, expireTime, sslConf, callbacks)

	def start_api(self):
		"""
		Avvia l'API con alcuni endpoints accessibili al server.
		"""
		super().start_api()

		@self.flask.route('/authenticate', methods=['POST'])
		def authenticate():
			"""
			Endpoint per l'autenticazione e la generazione del token.
			
			:return: il token JWT generato.
			"""

			serverAddr = self.get_json(request, 'addr', '')
			serverId = self.get_json(request, 'id', '')

			returnData = {'message': 'Credenziali non valide'}
			status = self.UNAUTHORIZED
			if self.callbacks['validate_credentials'](serverAddr, serverId):
				self.sub = serverAddr
				returnData = self.init_token()
				log.info('Connessione accettata dal server "{}" su "{}"'.format(serverId, serverAddr))
				status = self.ACCEPTED
			return self.standard_response(returnData, status)


		@self.flask.route('/status', methods=['GET'])
		@self.auth.token_required
		def status():
			"""
			Endpoint per il controllo dello stato del Butler.
			Se questo metodo è stato raggiunto il Butler è sicuramente attivo,
			quindi viene ritornato lo stesso oggetto in ogni caso.
			
			:return: una risposta vuota di successo.
			"""
			log.info('Richiesta dello stato da parte del server')
			return self.standard_response()

		@self.flask.route('/notify', methods=['PUT'])
		@self.auth.token_required
		def notify():
			"""
			Endpoint per l'invio di notifiche.
			I dati vengono inviati alla classe chiamante per la gestione.
			
			:return: il codice di stato 202 (accepted).
			"""
			notifData = self.get_json(request, 'notifData', '')
			log.info('Notifica "{}" ({}) ricevuta da {}'.format(
				notifData['name'],
				'pop-up' if notifData['osType'] else 'di sistema',
				self.ip))
			self.callbacks['show_notif'](notifData)
			return self.standard_response(self.ACCEPTED) # accettato

		@self.flask.route('/revoke', methods=['DELETE'])
		@self.auth.token_required
		def revoke_notification():
			"""
			Endpoint per l'annullamento di notifiche.
			
			:return: il codice di stato 202 (accepted).
			"""
			name = self.get_json(request, 'name', '')
			log.warning('Il server ha ritirato la notifica "{}"'.format(name))
			self.callbacks['revoke'](name)
			return self.standard_response(self.ACCEPTED)

		@self.flask.route('/disconnect', methods=['DELETE'])
		@self.auth.token_required
		def disconnect():
			"""
			Endpoint per la disconnessione del Butler.
			
			:return: il codice di stato 202 (accepted).
			"""
			log.warning('Il server {} ha richiesto la disconnessione'.format(self.ip))
			self.callbacks['disconnect']()
			return self.standard_response(self.ACCEPTED)

		@self.flask.route('/shutdown', methods=['DELETE'])
		@self.auth.token_required
		def shutdown():
			"""
			Endpoint per lo spegnimento del Butler.
			
			:return: il codice di stato 202 (accepted).
			"""
			log.warning(
				'Il server "{}" ha richiesto lo spegnimento'.format(self.ip))
			self.callbacks['shutdown']()
			return self.standard_response(self.ACCEPTED)


		"""
		#####################################
		Funzioni aggiuntive butler-extensions
		#####################################
		"""

		@self.flask.route('/details', methods=['GET'])
		@self.auth.token_required
		def get_details():
			"""
			Endpoint per richiede i dettagli del Butler.

			:return: i dettagli ricavati.
			"""
			returnData = self.callbacks['get_details']()
			return self.standard_response(returnData)

		@self.flask.route('/module', methods=['PUT'])
		@self.auth.token_required
		def toggle_module():
			"""
			Endpoint per modificare lo stato di un modulo.

			:return: una risposta vuota di successo.
			"""
			module = self.get_json(request, 'modules', '')
			self.callbacks['toggle_module'](module)
			return self.standard_response()

		@self.flask.route('/phase', methods=['PUT'])
		@self.auth.token_required
		def toggle_phase():
			"""
			Endpoint per modificare la fase del comportamento.

			:return: una risposta vuota di successo.
			"""
			status = self.get_json(request, 'phase', False)
			self.callbacks['toggle_phase'](status)
			return self.standard_response()

		@self.flask.route('/connection', methods=['PUT'])
		@self.auth.token_required
		def edit_model():
			"""
			Endpoint per modificare la sicurezza di una connessione.

			:return: una risposta vuota di successo.
			"""
			conn = self.get_json(request, 'model', [])
			self.callbacks['update_model']([conn])
			return self.standard_response()

		@self.flask.route('/model', methods=['PUT'])
		@self.auth.token_required
		def update_model():
			"""
			Endpoint per impostare il modello delle connessioni ad un Butler.

			:return: una risposta vuota di successo.
			"""
			model = self.get_json(request, 'model', [])
			self.callbacks['update_model'](model)
			return self.standard_response()

		"""
		##########################################
		Fine funzioni aggiuntive butler-extensions
		##########################################
		"""


		try:
			log.info('Attesa di comandi su {}:{}'.format(self.ip, self.port))
			self.flask.run(host=self.ip, port=self.port, ssl_context=self.sslConf, use_evalex=False)
		except OSError as e:
			log.critical('Non è stato possibile ascoltare il server su "{}": {}'.format(self.ip, e.__str__()))
			_exit(1)
