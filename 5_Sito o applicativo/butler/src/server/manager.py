import threading
import base64
import os
import hashlib
from os.path import abspath, isfile, join, basename, exists
from time import sleep, time
from json.decoder import JSONDecodeError
import sys
import copy
import webbrowser

sys.path.append(abspath(join(sys.path[0], '..')))

from common.logger import Logger
from common import log
from common.notificationBuilder import NotificationBuilder
from common.configParser import ConfigParser
from common.argsParser import ArgsParser
from server.controlCenterGUI import ControlCenterGUI
from server.controlCenterAPI import ControlCenterAPI
from server.butlerAPI import ButlerAPI
from server.ipParser import IPParser
from server.butler import Butler
from server.dbHelper import DbHelper

class Manager:
	"""
	Questa classe gestisce la parte server del programma Butler.
	Gestisce la connessione full-duplex dei Butlers e il centro di controllo web.
	"""

	TIMER = 1
	STANDARD_MODEL_MAC = ''
	butlers = {}
	interactions = {}

	collMap = {'connection': 'model', 'phase': 'phase', 'module': 'modules'}

	def start(self):
		"""
		Punto d'entrata del programma.
		- Ascolta le richieste da qualunque Butlers
		- Mette a disposizione l'interfaccia REST di controllo
		- Avvia l'interfaccia web di gestione
		- Legge i buffer di notifiche in sospeso dal database
		"""
		params = [
			{'short': 'c', 'full': 'config', 'args': True, 'default': '.',
			 'help': 'Usa il file di configurazione dal percorso specificato.\nSe non è dato nessun percorso, viene preso quello di avvio del programma.'},
			{'short': 'g', 'full': 'gui', 'args': True, 'default': '', 'help':
			 '''Avvia l\'interfaccia web del centro di controllo solo con alcune sezioni.
I parametri possibili sono:
\tmanager\t  Creazione e gestione delle notifiche
\tpreview\t  Anteprima della notifica (funzione sperimentale)
\tlist\t  Informazioni e gestione dei Butlers collegati'''},
			{'short': 'n', 'full': 'no_gui', 'args': False, 'default': '', 'help':
			 '''Non avvia l'interfaccia web.
Il server rimane raggiungibile attraverso richieste REST.'''},
			{'short': 'p', 'full': 'passive', 'args': False, 'default': '',
			 'help': 'Ignora il buffer delle notifiche.'}
		]
		argsParser = ArgsParser(params)
		args = argsParser.parse()
		try:
			self.configs = ConfigParser().load_configs(args['config'])
		except FileNotFoundError as e:
			log.critical(
				'Impossibile leggere il file di configurazione:\n{}'.format(e.__str__()))
			return
		except JSONDecodeError as e:
			log.critical(
				'Errore nella decodifica del file di configurazione:\n{}'.format(e.__str__()))
			return

		Logger().start(**self.configs['logging'])
		self.ipParser = IPParser()
		self.expireTime = self.configs['expireTime']
		self.protocol = self.configs['protocol']
		self.serverConf = self.configs['server']
		self.controlConf = self.configs['controlCenter']
		self.guiConf = self.configs['gui']
		self.testNotifData = ''

		self.addr = '{}://{}:{}'.format(self.protocol,
										self.serverConf['ip'], self.serverConf['port'])
		self.id = self.serverConf['id']
		log.info('Avvio del server su {}'.format(self.addr))

		# avvio dell'ascoltatore dei Butlers
		butlerCallbacks = {'add_butler': self.add_butler,
					 'disconnect': self.disconnect_client,
					 'interacted': self.interacted, 'update_db_details': self.update_db_details,
					 'butler_exists': self.butler_exists}

		self.butlerApi = ButlerAPI(self.serverConf['ip'], self.serverConf['port'],
							 self.expireTime, self.configs['ssl'], butlerCallbacks,
							 )
		threading.Thread(target=self.butlerApi.start_api, daemon=True).start()

		# imposta e avvia l'API del centro di controllo
		controlCenterAddr = '{}://{}:{}'.format(
			self.protocol, self.controlConf['ip'], self.controlConf['port'])
		self.dbHelper = DbHelper()
		self.dbHelper.login(**self.configs["database"])

		controlCallbacks = {'send_notif': self.send_notif, 'check_butlers': self.check_butlers,
					  'can_disconnect': self.can_disconnect, 'force_disconnect': self.force_disconnect,
					  'get_files': self.get_files_list, 'revoke': self.revoke,
					  'validate_credentials': self.validate_credentials,
					  'test_notif': self.test_notif,
					  'get_butler_details': self.get_butler_details,
					  'set_butler_details': self.set_butler_details,
					  'edit_butler': self.edit_butler, 'apply_standard_model': self.apply_standard_model}

		sections = args['gui'].split(
			',') if args['gui'] != '' else self.guiConf['sections']

		self.controlCenterApi = ControlCenterAPI(self.controlConf['ip'], self.controlConf['port'],
										   self.configs['expireTime'], self.configs['ssl'], controlCallbacks,
										   self.dbHelper, self.configs['imagesPath'], self.controlConf['previewPort'],
										   '{}://{}:{}'.format(self.protocol, self.guiConf['ip'], self.guiConf['port']), sections)
		threading.Thread(target=self.controlCenterApi.start_api, daemon=True).start()

		# avvio del controllo del buffer
		if self.configs['bufferTimer'] >= 1 and not args['passive']:
			threading.Thread(target=self.check_buffer, args=[
				self.configs['bufferTimer']], daemon=True).start()

		# prepara l'interfaccia grafica del server
		guiAddr = '{}://{}:{}'.format(
			self.protocol, self.guiConf['ip'], self.guiConf['port'])

		self.controlCenterGui = ControlCenterGUI(self.guiConf['ip'], self.guiConf['port'],
										   controlCenterAddr, self.configs['ssl'], self.configs['gui']['templatesPath'], self.configs['gui']['resPath'])
		threading.Thread(target=self.controlCenterGui.start_api, daemon=True).start()

		# se necessario, apre una finestra del browser per la GUI
		if not args['no_gui']:
			webbrowser.open(guiAddr, new=2, autoraise=False)

		notifBuilder = NotificationBuilder(
			logoPath=self.configs['logoPath'], testing=True)

		try:
			while True:
				if self.testNotifData != '':
					log.warning('Test reale della notifica "{}"'.format(
						self.testNotifData['name']))
					notifBuilder.interrupt = False
					notifBuilder.show_window(self.testNotifData)
					self.testNotifData = ''
				sleep(self.TIMER)

		except KeyboardInterrupt:
			sys.exit()

	def check_buffer(self, timer):
		"""
		Controlla periodicamente il buffer delle notifiche in sospeso,
		se il parametro è maggiore o uguale a 1 secondo.
		
		:param timer (int): il tempo di attesa tra i controlli (in secondi).
		"""
		log.info('Inizio del controllo del buffer')
		try:
			while True:
				for b in self.dbHelper.get_buffer():
					log.info('Tentativo di invio della notifica "{}" dal buffer'.format(
						b['notification']))
					for addr in self.send_notif(b['notification'], b['recipients'], b['excluded']):
						if self.butlers[addr].ip not in b['excluded']:
							b['excluded'].append(self.butlers[addr].ip)
						log.info('Notifica "{}" inviata a {}'.format(b['notification'], addr))
					self.dbHelper.update_buffer(b)
					sleep(1)
				sleep(timer)
		except KeyboardInterrupt:
			sys.exit()

	def send_notif(self, name, recipients, excluded=[]):
		"""
		Generatore per inviare notifiche e ritornare gli indirizzi di chi ha
		ricevuto i messaggi.
		
		:param name (str): il nome della notifica.
		:param recipients (list): la lista degli indirizzi dei destinatari.
		:param excluded (list): la lista degli indirizzi da non considerare.
			Default: [].
		
		:yield: gli indirizzi di chi ha risposto all'invio della notifica.
		"""
		# la wildcard * viene sostituita da tutti i destinatari
		if recipients == ['*']:
			recipients = [self.butlers[addr].ip for addr in self.butlers]
		# i destinatari vengono rimossi se presenti tra quelli esclusi
		recipients = [addr for addr in recipients if addr not in excluded]

		log.warning('Invio di "{}" a {} Butler'.format(name, len(recipients)))
		for addr in self.butlers:
			if self.butlers[addr].ip not in excluded and self.ipParser.include(recipients, self.butlers[addr].ip):
				data = self.parse_notif_data(self.dbHelper.get_notif_data(name))
				received = self.butlers[addr].send({'notifData': data})
				if received:
					log.info('{} ha ricevuto "{}"'.format(addr, name))
					yield addr

	def validate_credentials(self, user, password):
		"""
		Controlla che le credenziali passate corrispondano a quelle memorizzate
		nel file di configurazione.
		La pasword è salvata come SHA265.
		
		:param user (str): il nome utente dell'amministratore.
		:param password (str): la password dell'amministratore.
		
		:return: True se le credenziali corrispondono.
		"""
		return user == self.configs['username'] and hashlib.sha256(password.lower().encode("utf")).hexdigest() == self.configs['password'].lower()

	def add_butler(self, mac, addr, user):
		"""
		Crea un oggetto Butler e, se è possibile stabilire una connessione,
		lo aggiunge alla lista. 
		
		:param mac (str): l'indirizzo MAC del computer.
		:param addr (str): l'indirizzo IPv4 del Butler.
		:param user (str): il nome dell'utente.
		"""
		if self.addr_exists(addr):
			return self.butlers[addr].get_status()

		b = Butler(self.protocol, mac, addr, user, self.addr, self.id)
		if b.authenticate():
			log.info('Autenticazione con {} riuscita, aggiunto alla lista.'.format(addr))
			# la deepcopy permette di passare una versione dell'oggetto, non un riferimento
			self.butlers[addr] = copy.deepcopy(b)
			threading.Thread(target=self.set_butler_details, args=[addr]).start()
			return True
		else:
			log.warning('Non è possibile stabilire la comunicazione con {}'.format(addr))
			del b
			return False

	def disconnect_client(self, addr):
		"""
		Disconnette un client se ne ha il permesso.

		:param addr (str): l'indirizzo IPv4 e la porta del Butler da disconnettere.

		:return: True è stato possibile rimuovere il Butler dalla lista,
			False in caso sia ancora connesso.
		"""
		if self.addr_exists(addr):
			if self.butlers[addr].canDisconnect:
				log.warning('Disconnessione di {} avvenuta'.format(addr))
				self.butlers[addr].disconnect()
				# se non c'è la chiave, ritorna ''
				self.butlers.pop(addr, '')
			else:
				return False
		return True

	def interacted(self, addr, notifName):
		"""
		Aggiunge il Butler alla lista di host che hanno interagito con una certa notifica.
		
		:param addr (str): l'indirizzo IPv4 e la porta del Butler.
		:param notifName (str): il nome della notifica.
		"""
		if addr != '' and len(self.butlers) > 0:
			self.interactions[notifName].append(self.butlers[addr].address)

	def check_butlers(self, addr=''):
		"""
		Verifica lo stato dei Butlers.
		
		:param addr (str): l'indirizzo IPv4 e la porta del Butler da controllare.
			Default: ''.
		
		:return: la lista con le informazioni dei Butler ancora connessi.
			È sempre ritornato almeno l'indirizzo, ma se questo non è allegato
			ad altri dati significa che il Butler non è attivo: in questo modo
			è possibile verificare chi è andato offline rispetto all'ultimo controllo.
		"""
		if self.addr_exists(addr):
			if self.butlers[addr].get_status():
				return [{'addr': addr, 'user': self.butlers[addr].user,
							'mac': self.butlers[addr].mac,
							'canDisconnect': self.butlers[addr].canDisconnect}]
			else:
				del self.butlers[addr]
		elif addr == '':
			# se l'indirizzo è vuoto, vengono verificati tutti i Butlers
			butlersInfo = []
			try:
				for addr in self.butlers:
					if self.butlers[addr].get_status():
						butlersInfo.append({'addr': addr,
											'user': self.butlers[addr].user,
											'mac': self.butlers[addr].mac,
											'canDisconnect': self.butlers[addr].canDisconnect})
					else:
						butlersInfo.append({'addr': addr})
			except Exception as e:
				log.warning(
					'Errore nella verifica dello stato dei Butlers: {}'.format(e.__str__()))
			for b in butlersInfo:
				if 'user' not in b and b['addr'] in self.butlers:
					del self.butlers[b['addr']]
			return butlersInfo

		return {'addr': addr}

	def can_disconnect(self, addr, permission):
		"""
		Imposta il permesso di disconnessione di un client.
		
		:param addr (str): l'indirizzo IPv4 e la porta del Butler.
		:param permission (bool): il permesso di disconnessione.
		"""
		log.info('Cambio del permesso di disconnessione a {} in {}'.format(addr, permission))
		if self.addr_exists(addr):
			self.butlers[addr].canDisconnect = permission

	def force_disconnect(self, addr):
		"""
		Forza la disconnessione di un Butler impostando il permesso e inviando la richiesta.
		
		:param addr (str): l'indirizzo IPv4 e la porta del Butler.
		"""
		log.info('Richiesta di disconnessione a {}'.format(addr))
		self.can_disconnect(addr, True)
		self.disconnect_client(addr)

	def revoke(self, name):
		"""
		Revoca una notifica da tutti i Butlers, chiedendo la sua chiusura.
		
		:param name (str): il nome della notifica da chiudere.
		"""
		for addr in self.butlers:
			self.butlers[addr].revoke(name)

	def test_notif(self, data):
		"""
		Autoinvia una notifica per testarne unicamente lo stile.
		
		:param data (dict): i dati della notifica da mostrare.
		"""
		self.testNotifData = self.parse_notif_data(data)

	def get_files_list(self, pathKey):
		"""
		Legge un percorso apposito specificato nel file di configurazione e ritorna
		la lista dei file presenti.
		È usato per ricavare la lista di immagini e di scripts.
		
		:param pathKey (str): la chiave della configurazione corrispondente al
			tipo di file richiesto.
		
		:return: la lista dei nomi dei file.
		"""

		return [f for f in os.listdir(abspath(join(sys.path[0], self.configs[pathKey]))) if isfile(join(sys.path[0], self.configs[pathKey], f))]

	def addr_exists(self, addr):
		"""
		Verifica che si possa accedere ai dati del Butler ricercandolo nella lista
		in base al suo indirizzo.
		
		:param addr (str): l'indirizzo IPv4 e la porta del Butler.
		
		:return: True se esistono dati associati all'indirizzo richiesto, False
			in tutti gli altri casi.
		"""
		return len(self.butlers) > 0 and addr != [] and addr != {} and addr in self.butlers

	def parse_notif_data(self, data):
		"""
		Modifica i dati della notifica sostituendo i percorsi relativi al server
		con i dati base64 del file in quel percorso. Se non esiste il file,
		il dato viene comunque passato come percorso assumento si tratti di
		una cartella presente localmente nel client.
		
		:param data (dict): i dati della notifica da modificare.
		
		:return: il dizionario dei dati pronto all'uso.
		"""
		if 'style' in data and data['style']['image'] != '':
			data['style']['image'] = self.get_file_data(
				self.configs['imagesPath'], data['style']['image'])
		if data['script']['program'] != '':
			data['script']['program'] += ' '+basename(data['script']['command'])
			data['script']['command'] = self.get_file_data(
				self.configs['scriptsPath'], data['script']['command'])
		else:
			log.info('Script vuoto')

		return data

	def get_file_data(self, basePath, path):
		"""
		Tenta di leggere i dati del file nel percorso specificato.
		
		:param basePath (str): la base del percorso nel quale cercare.
		:param path (str): il percorso che specifica almeno il nome del file.
		
		:return: i dati base64 del file se esiste, altrimenti il suo percorso.
		"""
		try:
			fullPath = abspath(join(sys.path[0], basePath, path))
			if exists(path):
				pass
			elif exists(fullPath):
				path = fullPath
			with open(path, "r+b") as file:
				log.warning(
					'È stato inviato il file in "{}" insieme ad una notifica'.format(path))
				return base64.b64encode(file.read()).decode()
		except Exception as e:
			log.warning(
				'Il file verrà inviato come percorso a causa del seguente errore: {}'.format(e.__str__()))
		log.warning(
			'È stato inviato il percorso "{}" insieme ad una notifica (non è stato trovato localmente)'.format(path))
		return path

	"""
	#####################################
	Funzioni aggiuntive butler-extensions
	#####################################
	"""

	def edit_butler(self, addr, data, endpoint):
		"""
		Permette di modificare un parametro di un Butler.

		:param addr (str): l'indirizzo IPv4 e la porta del Butler da modificare.
		:param data (str): i dati da modificare.
		:param endpoint (str): l'endpoint del Butler.
		"""
		if self.addr_exists(addr) and endpoint != '' and data != '':
			data['mac'] = self.butlers[addr].mac
			self.dbHelper.upsert_details(data)
			self.butlers[addr].edit(data, endpoint)

	def apply_standard_model(self, addr):
		"""
		Invia i dati del modello standard ad un Butler.
		L'operazione non viene effettuata completamente dal gestore del database,
		poichè alcuni dati devono poi essere inviati al client.
		
		:param addr (str): l'indirizzo IPv4 e la porta del Butler al quale inviare i dati.

		:return: il numero di connessioni applicate.
		"""
		if self.addr_exists(addr):
			# query al modello standard con MAC ""
			standardModel = self.dbHelper.get_computer_data(self.STANDARD_MODEL_MAC)
			if 'model' in standardModel:
				standardModel['mac'] = self.butlers[addr].mac
				self.dbHelper.upsert_details(standardModel)
				self.butlers[addr].update_model(standardModel['model'])
				return len(standardModel['model'])
		return 0

	def get_butler_details(self, addr):
		"""
		Richiede i dettagli al Butler e gestisce i valori vuoti che
		il client ritorna se non ha certi moduli attivi.

		:param addr (str): l'indirizzo IPv4 e la porta del Butler al quale richiedere i dati.

		:return: i dati ricevuti.
		"""
		if self.addr_exists(addr):

			details = self.butlers[addr].get_details()
			# se non ci sono dettagli, verifica che l'host sia ancora connesso
			if details == {}:
				self.check_butlers()
				return {}

			self.set_butler_details(addr, details)
			details = self.dbHelper.get_computer_data(self.butlers[addr].mac)

			if 'inventory' not in details:
				details['inventory'] = {}

			if 'model' not in details:
				details['model'] = {}
				details['phase'] = ''

			# modules non deve essere gestito.
			# Se manca, altre classi si accorgeranno dell'errore

			details['mac'] = self.butlers[addr].mac
			return details
		return {}

	def set_butler_details(self, addr, butlerDetails={}):
		"""
		Sincronizza le informazioni tra database e client
		garantendo la loro consistenza.

		:param addr (str): l'indirizzo e la porta del quale verificare i dati.
		:param butlerDetails (dict): i dati del Butler, se già richiesti.
			Default: {}.
		"""
		# i dettagli vengono presi prima di controllare se l'host esiste
		# dato che questo potrebbe essere rimosso durante la chiamata
		if butlerDetails == {}:
			butlerDetails = self.get_butler_details(addr)
		if self.addr_exists(addr) and butlerDetails != {}:
			# i dati del modello del database hanno la precedenza su quelli del Butler
			dbDetails = self.dbHelper.get_computer_data(self.butlers[addr].mac)

			sameAttr = []
			for attr in butlerDetails:
				# verifica che l'attributo esista in entrambi gli array
				# e che i valori corrispondano, oppure che abbiamo dimensione uguale
				if attr in dbDetails and butlerDetails[attr] == dbDetails[attr]:
					sameAttr.append(attr)
			for attr in sameAttr:
				del butlerDetails[attr]
				del dbDetails[attr]

			# i dati dell'inventario presi dal Butler hanno la precedenza su quelli del database
			if 'inventory' in butlerDetails:
				self.dbHelper.upsert_details(
					{'mac': self.butlers[addr].mac, 'inventory': butlerDetails['inventory']})

			if 'model' in dbDetails:
				if 'model' in butlerDetails and len(butlerDetails['model']) > len(dbDetails['model']):
					self.dbHelper.upsert_details(
						{'mac': self.butlers[addr].mac, 'model': butlerDetails['model']})

				self.butlers[addr].update_model(dbDetails['model'])
				if 'phase' in dbDetails:
					self.butlers[addr].edit({'phase': dbDetails['phase']}, '/phase')
					
			# solo se il database non ha informazioni a riguardo vengono prese
			# direttamente quelle del Butler
			elif 'model' in butlerDetails:
				self.dbHelper.upsert_details(
					{'mac': self.butlers[addr].mac, 'model': butlerDetails['model']})
				# se il database ha tutti i dati, ma manda il modello
				# è probabile che il client non invii anche la fase
				if 'phase' in butlerDetails:
					self.dbHelper.upsert_details(
						{'mac': self.butlers[addr].mac, 'phase': butlerDetails['phase']})

			# anche i moduli hanno la precedenza se presenti nel database
			if 'modules' in dbDetails:
				self.butlers[addr].edit({'modules': dbDetails['modules']}, '/module')
			elif 'modules' in butlerDetails:
				self.dbHelper.upsert_details(
					{'mac': self.butlers[addr].mac, 'modules': butlerDetails['modules']})

	def update_db_details(self, details):
		"""
		Aggiorna le informazioni ricevute dal Butler nel database.

		:param details (dict): i dati da aggiornare.
		"""
		self.dbHelper.upsert_details(details)

	def butler_exists(self, addr):
		"""
		Controlla se l'indirizzo passato fa parte dell'array di Butlers
		
		:param addr (str): l'indirizzo identificativo.
		
		:return True se è presente, altrimenti False.
		"""
		return addr in self.butlers

	"""
	##########################################
	Fine funzioni aggiuntive butler-extensions
	##########################################
	"""


if __name__ == "__main__":
	Manager().start()
