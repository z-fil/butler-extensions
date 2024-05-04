import psutil
import socket

from common import log

class Behaviour:
	"""
	Questa classe studia e analizza il comportamento del computer
	distinguendo il traffico di rete normale da quello sospetto.
	Nella fase di apprendimento, tutte le nuove connessioni sono considerate
	sicure, mentre durante l'analisi sono tutte sospette.
	"""

	LEARNING = True
	ANALYZING = False
	UNKNOWN_PROTO = 'unknown'

	EXCLUDED_STATUS = [psutil.CONN_TIME_WAIT, psutil.CONN_NONE]

	customProto = {
			8080:'CPT Proxy', 27017: 'Butler MongoDB',
			20210: 'ButlerAPI', 20211: 'Butler Server Control',
			20212: 'Butler Web GUI', 20213: 'Butler live preview',
			20219: 'Butler Client CommandListener'}

	def __init__(self, phase=LEARNING, customProtocols={}):
		"""
		Istanzia un oggetto Behaviour definendone la fase
		e il modello delle connessioni iniziale.

		:param phase (bool, opzionale): la fase (True = apprendimento, False = analisi).
			Default: LEARNING.
		:param customProtocols (dict, opzionale): una lista di nomi di
				protocolli personalizzati e le porte alle quali sono associati.
			Default: {}.
		"""
		self.phase = phase
		self.model = []
		self.customProto.update(customProtocols)

	def get_protocol(self, port, type=''):
		"""
		Ricava il nome del protocollo in base alla porta passata.

		:param port (int): la porta trovata.
		:param type (str, opzionale): il tipo specifico (tcp/udp).
			Default: ''.

		:return: il nome del protocollo se trovato, altrimenti un valore di default.
		"""
		try:
			return socket.getservbyport(port, type)
		except Exception as e:
			return self.customProto[port] if port in self.customProto else self.UNKNOWN_PROTO
	
	def check_connections(self):
		"""
		Legge le connessioni attive e ne salva solo alcuni attributi.
		"""
		data = []
		for id in psutil.pids():
			# un'eccezione è sollevata in caso di permessi non sufficienti
			# o di processo non trovato 
			try:
				p = psutil.Process(id)
				# il processo è ignorato se non ha connessioni o se non è attivo
				if p.connections() == [] or not p.is_running():
					continue
				for conn in range(0, len(p.connections())):
					if p.connections()[conn][5] not in self.EXCLUDED_STATUS:
						# la sicurezza (safe) è impostata ora, ma sarà il server
						# a decidere se mantenere effettivamente questo stato
						c = {'proc': p.name(), 'status': p.connections()[conn][5],
						'source': ['',''], 'dest': ['',''], 'proto': 'unknown', 'safe': self.phase}
						port = p.connections()[conn].laddr.port
						c['source'] = [p.connections()[conn].laddr.ip, port]
						c['proto'] =  self.get_protocol(port)

						# non tutte le connessioni hanno un indirizzo di destinazione
						try:
							if hasattr(p.connections()[conn].raddr, 'ip'):
								# port è una variabile perchè viene usato anche in seguito
								port = p.connections()[conn].raddr.port
								c['dest'] = [p.connections()[conn].raddr.ip, port]
						except:
							pass
						if c['proto'] == self.UNKNOWN_PROTO:
							c['proto'] = self.get_protocol(port)
						data.append(c)
			except Exception:
				pass

		# logga solo se le informazioni sono utili
		if len(data) != len(self.model):
			log.info('Ci sono {} connessioni attive'.format(len(data)))

		# gli array sono scambiati per rispettare l'ordine delle priorità
		originalModel = self.model.copy()
		self.model = data
		self.update_model(originalModel)
		
	def update_model(self, newData):
		"""
		Unisce il modello attuale con le nuove connessioni, senza scartarne
		nessuna e facendo attenzione a non duplicarle.

		:param newData (list): la lista di nuove connessioni da aggiungere.
			Questo parametro ha priorità sull'attributo model, quindi
			all'occorrenza vanno passati in ordine inverso.
		"""
		self.model = self.remove_duplicates(self.model.copy())

		newModel = self.model.copy()
		newData = self.remove_duplicates(newData)
		
		for newConn in newData:
			found = False
			i = 0
			for c in self.model:
				if self.conn_match(newConn, c):
					if len(newModel) > i:
						newModel[i]['safe'] = newConn['safe']
					else:
						# la funzione viene richiamata se ci sono stati cambiamenti
						# in parallelo (dimensioni degli array diverse)
						self.update_model(newData)
					found = True
					break
				i+=1
			if not found:
				newModel.append(newConn)
		# se non ci sono dati, vengono impostati quelli precedenti
		if newData == []:
			newModel = self.model
			
		self.model = newModel.copy()

		# logga solo se le informazioni sono utili
		if len(self.model) != len(newData):
			log.info('Il modello contiene ora {} connessioni. Ne sono state verificate {}'.format(
				len(self.model), len(newData))
			)

	def remove_duplicates(self, model):
		"""
		Rimuove le connessioni simili dal modello passato.

		:param model (list): la lista delle connessioni.

		:return: il modello con le connessioni considerate diverse tra loro.
		"""
		cleanModel = []
		for c in model:
			found = False
			for c2 in cleanModel:
				if self.conn_match(c, c2):
					found = True
					break
			if not found:
				cleanModel.append(c.copy())
		return cleanModel


	def get_model(self):
		"""
		Aggiorna e ritorna il modello delle connessioni.

		:return: il modello aggiornato.
		"""
		self.check_connections()
		return self.model

	def conn_match(self, conn1, conn2):
		"""
		Verifica che le connessioni corrispondano.
		Non esiste un identificativo, quindi vanno controllati
		l'indirizzo e la porta sorgente e quelli di destinazione, se presenti.

		:param conn1 (dict): i dati della prima connessione.
		:param conn2 (list): i dati della seconda connessione.

		:return: True se le connessioni corrispondono, altrimenti False.
		"""
		return (
			# il nome del processo deve corrispondere
			conn1['proc'] == conn2['proc'] and (
			(
				# se entrambe le destinazioni sono vuote, la sorgente deve
				# corrispondere completamente 
				conn1['dest'] == ['',''] and 
				conn2['dest'] == ['','']
				and conn1['source'] == conn2['source']
			) or (
				# se la destinazione non è vuota,
				# 3 su 4 degli altri campi (ip1, porta1, ip2, porta2) devono corrispondere
				conn1['dest'] != ['','']
				and (
					conn1['dest'] == conn2['dest']
					and conn1['source'][0] == conn2['source'][0]
				) or (
					conn1['dest'][0] == conn2['dest'][0]
					and conn1['source'] == conn2['source'])
			))
		)

