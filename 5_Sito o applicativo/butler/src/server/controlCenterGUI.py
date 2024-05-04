from flask import Flask, render_template
from os.path import abspath, join
from os import _exit
import sys

from common import log
from common.baseAPI import BaseAPI

class ControlCenterGUI(BaseAPI):
	"""
	Questa classe funge da webserver per l'interfaccia web del
	centro di controllo del programma server.
	Estende da BaseAPI che definisce parte della logica di base. 
	"""

	def __init__(self, ip, port, controlApiAddr, sslConf, templatesPath, resPath):
		"""
		Istanzia un oggetto ControlCenterGUI definendone l'ip, la porta
		e l'indirizzo dell'API del centro di controllo.
		
		:param ip (str): l'IP sul quale avviare il webserver.
		:param port (int): la porta specifica del webserver.
		:param controlApiAddr (str): l'indirizzo e la porta dell'API del centro di controllo,
			in modo che la pagina web possa chiedere a questo server verso
			dove inviare i comandi di controllo ed evitare parametri hard-coded.
		:param sslConf (list): il percorso del certificato e della chiave SSL.
		:param templatesPath (str): il percorso dei file HTML dell'interfaccia.
		:param resPath (str): il percorso delle risorse statiche (CSS, JS,...) dell'interfaccia.
		"""
		super().__init__(ip, port, 1, sslConf)
		self.ip = ip
		self.port = port
		self.controlApiAddr = controlApiAddr
		self.templatesPath = templatesPath
		self.resPath = resPath
	
	def start_api(self):
		"""
		Avvia il server con alcuni endpoint che ritornano pagine HTML
		e uno per la richiesta dell'indirizzo del centro di controllo.
		"""
		super().start_api()
		self.flask = Flask(__name__,
			template_folder=abspath(join(sys.path[0],self.templatesPath)),
			static_folder=abspath(join(sys.path[0],self.resPath)))

		@self.flask.route("/")
		def index():
			"""
			Fornisce la pagina di base "index.html".
			
			:return: il file richiesto.
			"""
			log.info('Nuova connessione all\'intrefaccia web')
			return render_template("index.html")

		@self.flask.route("/status")
		def status():
			"""
			Fornisce la pagina di base "status.html".
			
			:return: il file richiesto.
			"""
			return render_template("status.html")

		@self.flask.route("/manager")
		def manager():
			"""
			Fornisce la pagina di base "notificationManager.html".
			
			:return: il file richiesto.
			"""
			return render_template("notificationManager.html")

		@self.flask.route("/preview")
		def preview():
			"""
			Fornisce la pagina di base "livePreivew.html".
			
			:return: il file richiesto.
			"""
			return render_template("livePreview.html")

		@self.flask.route("/list")
		def list():
			"""
			Fornisce la pagina di base "butlerList.html".
			
			:return: il file richiesto.
			"""
			return render_template("butlerList.html")

		@self.flask.route('/api', methods=['GET'])
		def get_control_addr():
			"""
			Permette di ricavare l'indirizzo dell'API del centro di controllo.
			
			:return: l'indirizzo dell'API di controllo.
			"""
			log.info('Il centro di controllo si trova su {}'.format(self.controlApiAddr))
			return self.standard_response({'addr': self.controlApiAddr})

		try:
			log.info('Interfaccia web del server avviata su {}:{}'.format(self.ip, self.port))
			self.flask.run(host=self.ip, port=self.port, ssl_context=self.sslConf)
		except OSError as e:
			log.critical('Non è stato possibile avviare l\'interfaccia web su "{}": {}'.format(self.ip, e.__str__()))
			_exit(1)


if __name__ == "__main__":
	#app.run(host='127.0.0.1', port=20213, debug=True)
	#serve(app, host='127.0.0.1', port=20213, url_scheme='https')
	ControlCenterGUI([]).start()
