from flask import request
import threading
from os import _exit

from common import log
from common.notificationBuilder import NotificationBuilder
from common.baseAPI import BaseAPI
from server.ipParser import IPParser

class ControlCenterAPI(BaseAPI):
	"""
	Questa classe permette il controllo del programma server tramite richieste REST.
	Estende da BaseAPI che definisce parte della logica di base.
	"""

	def __init__(self, ip, port, expireTime, sslConf, callbacks, dbHelper, imagesPath, previewPort, guiAddr, guiSections):
		"""
		Istanzia un oggetto ControlCenterAPI definendone ip e porta sul quale lavorare,
		la durata dei token generati, le funzioni di callback disponibili, l'oggetto
		per eseguire query al database, il percorso nel quale trovare le
		immagini delle notifiche, la porta della preview live, l'indirizzo
		dell'interfaccia grafica e le sezioni di default della GUI.
		
		:param ip (str): l'ip sul quale attivare l'API.
		:param port (int): la porta specifica dell'API.
		:param expireTime (float): i minuti di durata dei token.
		:param sslConf (list): il percorso del certificato e della chiave SSL.
		:param callbacks (dict): la lista di callback, identificate da chiavi.
		:param dbHelper (DbHelper): l'oggetto già configurato per la comunicazione
			con il database MongoDB.
		:param imagesPath (str): il percorso di default nel quale trovare le immagini
			delle notifiche, se i dati non dovessero contenere il base64 dell'immagine.
		:param previewAddr (int): la porta sulla quale cercare l'anteprima live.
		:param guiAddr (str): l'indirizzo e la porta dell'interfaccia grafica
			dalla quale accettare richieste anche se riconosciute come cross-domain.
		:param guiSections (list): la lista con i nomi delle sezioni del centro di controllo.
		"""
		super().__init__(ip, port, expireTime, sslConf, callbacks)
		self.sections = guiSections
		self.db = dbHelper
		self.guiAddr = guiAddr
		# la preview funziona solo in HTTP
		self.previewAddr = 'http://'+ip+':'+str(previewPort)
		self.previewPort = previewPort
		self.preview = NotificationBuilder(port=previewPort, imagesPath=imagesPath)
		self.timer = 0

	def start_api(self):
		"""
		Avvia l'API con alcuni endpoints accessibili agli amministratori.
		"""
		super().start_api()

		@self.flask.route('/authenticate', methods=['POST'])
		def authenticate():
			"""
			Permette l'autenticazione per l'uso del centro di controllo.
			
			:return: il token JWT generato.
			"""
			user = self.get_json(request, 'username', '')
			password = self.get_json(request, 'password', '')
			if self.callbacks['validate_credentials'](user, password):
				self.sub = user
				returnData = self.init_token()
				log.info(returnData['message'])
				return self.standard_response(returnData)
			returnData = {'message': 'Credenziali non valide'}
			log.warning(returnData['message'])
			return self.standard_response(returnData, self.UNAUTHORIZED)

		@self.flask.route('/notifData', methods=['POST'])
		@self.auth.token_required
		def get_notif_data():
			"""
			Permette di ricavare i dati di una notifica in base al suo nome.
			
			:return: il nome della notifica da cercare nel database.
			"""
			name = self.get_json(request, 'name', None)
			returnData = {
				'notif': self.db.get_notif_data(name)
			}
			return self.standard_response(returnData)

		@self.flask.route('/notifList', methods=['POST'])
		@self.auth.token_required
		def get_notif_list():
			"""
			Permette di ricavare la lista delle notifiche
			
			:return: la lista dei nomi delle notifiche nel database.
			"""
			returnData = {'notifList': [notif['name'] if 'name' in notif else ''
				for notif in self.db.get_notif(filter={'_id': 0, 'name': 1})] }
			return self.standard_response(returnData)

		@self.flask.route('/butlers', methods=['GET', 'POST'])
		@self.auth.token_required
		def get_butler_list():
			"""
			Controlla lo stato dei Butlers e ritorna i dati di quelli ancora connessi.
			
			:return: la lista con alcune informazioni sui Butlers attivi.
			"""
			addr = self.get_json(request, 'addr', '')
			returnData = {
				'butlers': self.callbacks['check_butlers'](addr),
				'message': 'Lista di Butlers aggiornata.'
			}
			return self.standard_response(returnData)

		@self.flask.route('/imagesList', methods=['POST'])
		@self.auth.token_required
		def get_images_list():
			"""
			Genera la lista di immagini utilizzabili.
			
			:return: la lista delle immagini trovate nel percorso definito
				nella configurazione del programma.
			"""
			returnData = {'imagesList': self.callbacks['get_files']('imagesPath') }
			return self.standard_response(returnData)

		@self.flask.route('/scriptsList', methods=['POST'])
		@self.auth.token_required
		def get_scripts_list():
			"""
			Genera la lista di scripts utilizzabili.
			
			:return: la lista degli scripts trovati nel percorso definito
				nella configurazione del programma.
			"""
			returnData = {'scriptsList': self.callbacks['get_files']('scriptsPath') }
			return self.standard_response(returnData)

		@self.flask.route('/themesList', methods=['POST'])
		@self.auth.token_required
		def get_themes():
			"""
			Genera la lista di temi delle notifice disponibili.
			
			:return: la lista dei nomi dei temi (definiti da PySimpleGUI).
			"""
			returnData = {'themesList': self.preview.get_themes() }
			return self.standard_response(returnData)

		@self.flask.route('/canDisconnect', methods=['POST'])
		@self.auth.token_required
		def set_can_disconnect():
			"""
			Imposta il permesso di disconnessione per un determinato Butler.
			
			:return: il risultato dell'operazione.
			"""
			addr = self.get_json(request, 'addr', '')
			permission = self.get_json(request, 'permission', '')
			self.callbacks['can_disconnect'](addr, permission)

			returnData = {
				'addr': addr,
				'message': '{} {} disconnettersi.'.format(
					addr, 'può ora' if permission else 'non può più')
			}
			log.info(returnData['message'])
			return self.standard_response(returnData)

		@self.flask.route('/disconnect', methods=['POST'])
		@self.auth.token_required
		def disconnect_host():
			"""
			Forza la disconnessione di un Butler.
			
			:return: il risultato dell'operazione.
			"""
			addr = self.get_json(request, 'addr', '')
			self.callbacks['force_disconnect'](addr)

			returnData = {
				'butlers': {'addr': addr},
				"message": '{} disconnesso.'.format(addr)
			}
			log.info(returnData['message'])
			return self.standard_response(returnData)

		@self.flask.route('/saveNotif', methods=['PUT'])
		@self.auth.token_required
		def save_notif():
			"""
			Salva una notifica in base ai dati passati.
			
			:return: il risultato dell'operazione.
			"""
			notifData = self.get_json(request, 'notif', [])
			if 'name' in notifData and notifData['name'] != '':
				self.db.upsert_notif(notifData)
				returnData = {
					'message': 'Notifica "{}" salvata'.format(notifData['name'])
				}
				log.info(returnData['message'])
				return self.standard_response(returnData)
			returnData = {'message': 'La notifica non è stata salvata poichè sprovvista di nome.'}
			log.warning(returnData['message'])
			return self.standard_response({'message': 'Dati mancanti'}, self.UNAUTHORIZED)

		@self.flask.route('/sendNotif', methods=['PUT'])
		@self.auth.token_required
		def send_notif():
			"""
			Permette di inviare una notifica ai Butlers.
			La notifica è accettata solo se ha dei destinatari validi, un nome
			e dei dati a questo associati. 
			
			:return: il risultato dell'operazione.
			"""
			name = self.get_json(request, 'name', None)
			deliveryData = self.get_json(request, 'buffer', [])
			returnData = {'message': 'Dati della notifica non validi o mancanti.'}
			status = self.UNAUTHORIZED

			if 'recipients' in deliveryData and len(deliveryData['recipients']) > 0 and self.db.get_notif_data(name) != []:
				if deliveryData['recipients'] == '*':
					# '*' non è accettato nel buffer, poichè creerebbe problemi
					# con la rimozione dei destinatari
					deliveryData['recipients'] = [
						addr for addr in self.callbacks['check_butlers']()]
				if deliveryData['start'] != '':
					self.db.add_buffered_notif(
						name, deliveryData['recipients'], deliveryData['start'])
					returnData['message'] = 'Buffer della notifica "{}" salvato con inizio della consegna {}'.format(
						name, deliveryData['start'])
				else:
					returnData['message'] = 'Notifica inviata a: {}'.format(
						[addr for addr in self.callbacks['send_notif'](name, deliveryData['recipients'])])
				status = self.ACCEPTED
			log.info(returnData['message'])
			return self.standard_response(returnData, status)

		@self.flask.route('/deleteNotif', methods=['DELETE'])
		@self.auth.token_required
		def delete_notif():
			"""
			Permette di eliminare una notifica in base al nome.
			
			:return: il risultato dell'operazione.
			"""
			name = self.get_json(request, 'name', '')
			if name != '':
				self.db.delete_notif(name)
				returnData = {'message': 'Notifica "{}" eliminata'.format(name)}
				log.info(returnData['message'])
				return self.standard_response(returnData)
			returnData = {'message': 'Nome non specificato'}
			log.warning(returnData['message'])
			return self.standard_response(returnData, self.UNAUTHORIZED)


		@self.flask.route('/revoke', methods=['DELETE'])
		@self.auth.token_required
		def revoke_notif():
			"""
			Permette di forzare la chiusura di una notifica su tutti i Butlers.
			
			:return: il risultato dell'operazione.
			"""
			name = self.get_json(request, 'name', '')
			self.callbacks['revoke'](name)

			returnData = { 'message': 'Notifica "{}" revocata da tutti i Butlers'.format(name) }
			return self.standard_response(returnData)

		@self.flask.route('/verifyList', methods=['POST'])
		@self.auth.token_required
		def verify_recipients_list():
			"""
			Permette di verificare in anticipo la lista di destinatari,
			usando l'apposita classe.
			
			:return: la lista di indirizzi IP validi nella lista
				(non ritorna gli host attivi che riceverebbero la notifica).
			"""
			recipients = self.get_json(request, 'recipients', [])
			returnData = IPParser().sanitize_ips(recipients) if recipients != '*' else ['*']
			return self.standard_response(returnData)
			
		@self.flask.route('/refreshPreview', methods=['POST'])
		@self.auth.token_required
		def refresh_preview():
			"""
			Gestisce e aggiorna l'anteprima live in base ai dati ricevuti.
			
			:return: i secondi da attendere prima della prossima richiesta.
				È in questo modo che la sezione della preview informa ufficialmente
				l'editor che deve mandare i dati aggiornati al server.
			"""
			notifData = self.get_json(request, 'notif', {'name':''})
			if 'name' in notifData and notifData['name'] != '':
				try:
					threading.Thread(
						target=self.preview.show_window, args=[notifData]).start()
				except Exception as e:
					self.preview.stop()
					log('Errore nell\'anteprima live: {}'.format(e.__str__()))
				
			returnData = {'timer': self.timer}
			return self.standard_response(returnData)
			
		@self.flask.route('/setTimer', methods=['POST'])
		@self.auth.token_required
		def set_timer():
			"""
			Permette di impostare la cadenza di aggiornamento dei dati delle notifiche.
			
			:return: una risposta vuota di successo.
			"""
			self.timer = self.get_json(request, 'timer', '')

			return self.standard_response()
	  
		@self.flask.route('/testNotif', methods=['POST'])
		@self.auth.token_required
		def test_notif():
			notifData = self.get_json(request, 'notif', {'name': ''})
			if 'name' in notifData and notifData['name'] != '':
				self.callbacks['test_notif'](notifData)
			return self.standard_response({'message': 'Notifica di test "{}" autoinviata'.format(notifData['name'])})

		@self.flask.route('/previewAddr', methods=['GET'])
		@self.auth.token_required
		def get_addr():
			"""
			Permette di ricavare l'indirizzo per raggiungere l'anteprima della notifica.
			
			:return: l'indirizzo sul quale raggiungere l'anteprima.
			"""
			log.info('Preview della notifica sull\'indirizzo {}'.format(self.previewAddr))
			returnData = {'addr': self.previewAddr}
			return self.standard_response(returnData)

		@self.flask.route('/sections', methods=['GET', 'POST'])
		@self.auth.token_required
		def get_sections():
			"""
			Permette di ricavare le sezioni dell'interfaccia da caricare.
			
			:return: la lista di nomi delle sezioni.
			"""
			log.info('Caricate le sezioni grafiche {}'.format(self.sections))
			return self.standard_response(self.sections)

		@self.flask.after_request
		def after_request(response):
			"""
			Viene richiamata prima della ricezione della richiesta.
			Imposta alcuni parametri per permettere di accettare richieste sicure
			da porte diverse da quella di questa API.
			
			:param response (response): la risposta da modificare.
			
			:return: la risposta modificata.
			"""
			response.headers["Access-Control-Allow-Origin"] = '{}'.format(self.guiAddr)
			#response.headers["Access-Control-Allow-Credentials"] = "true"
			response.headers["Access-Control-Allow-Methods"] = 'POST, GET, PUT, DELETE'
			response.headers["Access-Control-Allow-Headers"] = 'Accept, Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, token, sub'
			return response


		"""
		#####################################
		Funzioni aggiuntive butler-extensions
		#####################################
		"""

		@self.flask.route('/details', methods=['GET', 'POST'])
		@self.auth.token_required
		def get_details():
			"""
			Permette di ricavare i dettagli su un Butler.

			:return: i dettagli ricevuti.
			"""
			addr = self.get_json(request, 'addr', '')
			details = self.callbacks['get_butler_details'](addr)
			status = self.ACCEPTED
			# se i dettagli sono vuoti, il Butler non ha risposto
			if details == {}:
				status = self.UNAUTHORIZED
				details = {'message': 'Il Butler {} non ha risposto alla richiesta: potrebbe essere offline'.format(addr)}
			# se dei dettagli mancano i moduli, il database non ha ritornato dati
			elif 'modules' not in details:
				status = self.UNAUTHORIZED
				details = {'message': 'Errore nella lettura del database: potrebbe essere offline'}


			return self.standard_response(details, code=status)

		@self.flask.route('/module', methods=['PUT'])
		@self.auth.token_required
		def toggle_module():
			"""
			Permette di modificare lo stato dei moduli dei Butlers.

			:return: una risposta vuota di successo, ritornata da un'altra funzione.
			"""
			return self.edit_butler(request)

		@self.flask.route('/phase', methods=['PUT'])
		@self.auth.token_required
		def toggle_phase():
			"""
			Permette di modificare la fase del modulo di comportamento dei Butlers.

			:return: una risposta vuota di successo, ritornata da un'altra funzione.
			"""
			return self.edit_butler(request)

		@self.flask.route('/connection', methods=['PUT'])
		@self.auth.token_required
		def edit_connection():
			"""
			Permette di modificare la sicurezza delle connessioni dei Butlers.

			:return: una risposta vuota di successo, ritornata da un'altra funzione.
			"""
			return self.edit_butler(request)

		@self.flask.route('/standardModel', methods=['PUT'])
		@self.auth.token_required
		def apply_standard_model():
			"""
			Permette di modificare la sicurezza delle connessioni dei Butlers.

			:return: una risposta vuota di successo, ritornata da un'altra funzione.
			"""
			addr = self.get_json(request, 'addr', '')
			editNum = self.callbacks['apply_standard_model'](addr)
			returnData = {'message': '{} connessioni applicate a {}'.format(editNum, addr)}
			return self.standard_response(returnData)

		"""
		##########################################
		Fine funzioni aggiuntive butler-extensions
		##########################################
		"""
		

		try:
			log.info('API di controllo avviata su {}:{}'.format(self.ip, self.port))
			self.flask.run(host=self.ip, port=self.port, ssl_context=self.sslConf)
		except OSError as e:
			log.critical('Non è stato possibile avviare il centro di controllo su "{}": {}'.format(self.ip, e.__str__()))
			_exit(1)


	"""
	#####################################
	Funzioni aggiuntive butler-extensions
	#####################################
	"""

	def edit_butler(self, request):
		"""
		Permette di modificare un parametro di un Butler,
		usando l'attributo "data" per ricavare le informazioni passate.

		:param request (flask.request): il contesto della richiesta ricevuta.

		:return: una risposta vuota di successo.
		"""
		addr = self.get_json(request, 'addr', '')
		data = self.get_json(request, 'data', [])
		# request.path corrisponde sia all'endpoint appena raggiunto che a quello del client
		self.callbacks['edit_butler'](addr, data, request.path)
		return self.standard_response()
		
	"""
	##########################################
	Fine funzioni aggiuntive butler-extensions
	##########################################
	"""
