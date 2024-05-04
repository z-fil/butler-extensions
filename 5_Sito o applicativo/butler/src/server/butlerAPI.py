from authlib.jose import jwt
from flask import request
from os import _exit

from common import log
from common.baseAPI import BaseAPI


class ButlerAPI(BaseAPI):
	"""
	Questa classe permette di interpretare le richieste originate dai Butler.
	Estende da BaseAPI che definisce parte della logica di base. 
	"""

	def __init__(self, ip, port, expireTime, sslConf, callbacks):
		"""
		Istanzia un oggetto ButlerAPi definendone ip e porta sul quale lavorare,
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
		Avvia l'API con alcuni endpoints accessibili ai Butlers.
		"""
		super().start_api()

		@self.flask.route('/authenticate', methods=['POST'])
		def authenticate():
			"""
			Permette l'autenticazione per accettare risposte dai Butlers.
			
			:return: il token JWT generato.
			"""
			mac = self.get_json(request, 'mac', '')
			addr = self.get_json(request, 'addr', '')
			user = self.get_json(request, 'user', '')

			if addr != '' and user != '':
				self.sub = user
				returnData = self.init_token()
				log.info(returnData['message'])
				status = self.ACCEPTED if self.callbacks['add_butler'](mac, addr, user) else self.BAD_METHOD
				return self.standard_response(returnData, status)
			returnData = {'message': 'Credenziali "{}", "{}" non valide.'}
			log.warning(returnData['message'])
			return self.standard_response(returnData, self.UNAUTHORIZED)

		@self.flask.route('/status', methods=['GET'])
		@self.auth.token_required
		def status():
			"""
			Permette di ricavare lo stato del server.
			Se questo metodo è stato raggiunto il server è sicuramente attivo,
			quindi viene ritornato la stessa risposta in ogni caso.
			
			:return: una risposta vuota di successo.
			"""
			addr = self.get_json(request, 'addr', '')
			status = self.ACCEPTED if self.callbacks['butler_exists'](addr) else self.FORBIDDEN
			return self.standard_response(code=status)

		@self.flask.route('/interacted', methods=['GET'])
		@self.auth.token_required
		def interacted():
			"""
			Viene richiamato all'interazione con il bottone apposito della notifica.
			
			:return: una risposta vuota di successo.
			"""
			notifName = self.get_json(request, 'name', '')
			ip = self.get_json(request, 'ip', '')
			self.callbacks['interacted'](ip, notifName)
			return self.standard_response()


		@self.flask.route('/disconnect', methods=['GET'])
		@self.auth.token_required
		def disconnect():
			"""
			Viene richiamato al tentativo di disconnessione di un Butler.
			
			:return: le informazioni sul permesso di disconnettersi.
			"""
			addr = self.get_json(request, 'addr', '')
			canDisconnect = self.callbacks['disconnect'](addr)
			status = self.BAD_METHOD
			if canDisconnect:
				status = self.ACCEPTED
				log.warning('Butler "{}" disconnesso manualmente da un utente')
			return self.standard_response(code=status)


		"""
		#####################################
		Funzioni aggiuntive butler-extensions
		#####################################
		"""

		@self.flask.route('/details', methods=['PUT'])
		@self.auth.token_required
		def details():
			"""
			Viene richiamato alla ricezione dei dettagli di un Butler.
			
			:return: una risposta vuota di successo.
			"""
			details = self.get_json(request, 'details', {})
			self.callbacks['update_db_details'](details)
			return self.standard_response()

		"""
		##########################################
		Fine funzioni aggiuntive butler-extensions
		##########################################
		"""


		try:
			log.info('API per i Butlers avviata su {}:{}'.format(self.ip, self.port))
			self.flask.run(host=self.ip, port=self.port, ssl_context=self.sslConf)
		except OSError as e:
			log.critical('Non è stato possibile ascoltare i client su "{}": {}'.format(self.ip, e.__str__()))
			_exit(1)
