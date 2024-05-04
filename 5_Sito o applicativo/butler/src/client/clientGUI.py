import PySimpleGUIQt as sg
import webbrowser
import base64
from os.path import abspath, join
import sys

from common import log
from common.notificationBuilder import NotificationBuilder

class ClientGUI:
	"""
	Questa classe gestisce il piccolo menu nella taskbar.
	Inoltre, sfrutta NotificationBuilder per aprire una piccola finestra
	di stato.
	"""

	# gli elementi del menu
	OPEN = "Apri"
	DISCONNECT = "Disconnetti"
	CONNECT = "Connetti al server"
	INFO = "Pagina github"
	HIDE = "Nascondi icona"
	QUIT = "Esci"
	
	def __init__(self, logoPath, status_callback, website):
		"""
		Istanzia un oggetto ClientGUI definendone il logo e la callback lo stato.

		:param logoPath(str): il percorso nel quale cercare il file del logo.
		:param status_callback(func): la callback per le informazioni sullo
			stato del Butler.
		:param website (str): l'URL al sito dell'applicativo.
		"""
		self.logoPath = logoPath
		self.get_status = status_callback
		self.website = website
		self.interrupt = False

	def start_tray(self):
		"""
		Crea il menu nella taskbar e definisce il NotificationBuilder
		che sarà usato per aprire la finestra di stato.
		"""
		menu_def = ['BLANK', [self.OPEN, self.INFO, '---',
							  self.CONNECT, self.DISCONNECT, '---', self.HIDE, self.QUIT]]

		with open(abspath(join(sys.path[0],self.logoPath)), "rb") as file:
			self.tray = sg.SystemTray(
				menu=menu_def, data_base64=base64.b64encode(file.read()), tooltip='Butler Agent')
		#data_base64=base64.b64encode(file.read())
		self.gui = NotificationBuilder(logoPath=self.logoPath)

	def listen_tray(self):
		"""
		Ascolta gli eventi del menu, gestisce alcuni eventi e li ritorna tutti.
		
		:yield: tutti gli eventi.
		"""
		log.info('Avvio del menu')
		while not self.interrupt:
			event = self.tray.read(2000)
			if event == sg.EVENT_SYSTEM_TRAY_ICON_ACTIVATED:
				self.show_status()
			elif event == self.OPEN:
				self.show_gui()
			elif event == self.INFO:
				webbrowser.open(self.website, new=2)
			elif event == self.HIDE:
				self.tray.hide()
				#break
			yield event
		
		# si usano break per non arrivare qui da self.HIDE, che non lo necessita
		self.stop()

	def show_gui(self):
		"""
		Apre la finestra di stato, generata come fosse una normale notifica pop-up.
		Contiene le informazioni sul Butler e sul programma.
		"""
		user, ip, server = self.get_status()
		server = 'connesso a '+server if server is not None else 'non connesso'
		# notifica pop-up
		data = f'''
		{{
			"name": "Butler",
			"osType": false,
			"text": {{
				"title": "Butler extension",
				"message": "Agent per la ricezione di notifiche, la gestione dell'inventario e delle connessioni\\nLPI 4° anno\\nFilippo Zinetti, I4AC\\nScuola Arti e Mestieri Trevano, 2021\\n\\nButler {user}@{ip}\\nStato: {server}",
				"font": "Helvetica",
				"textColor": "#fff",
				"textSize": 12,
				"secondTextColor": "",
				"blinkSpeed": ""
			}},
			"style": {{
				"theme": "DarkRed",
				"bgColor": "",
				"secondBgColor": "",
				"blinkSpeed": "",
				"width": "",
				"height": "",
				"image": "",
				"alpha": 1
			}},
			"interactivity": {{
				"canMove": true,
				"canClose": true,
				"blocking": false,
				"buttonText": ""
			}},
			"script": {{
				"program": "",
				"command": ""
			}}
		}}
		'''
		self.gui.show_window(data)

	def show_status(self):
		"""
		Mostra una notifica si sistema, con solo le informazioni più
		importati sullo stato del Butler.
		"""
		user, ip, server = self.get_status()
		server = 'connesso a '+ server if server is not None else 'non connesso' 
		# notifica di sistema
		data = f'''
		{{
			"name": "Butler Agent",
			"osType": true,
			"text": {{
				"title": "Butler",
				"message": "{user}@{ip}\\nStato: {server}",
				"font": "",
				"textColor": "",
				"textSize": "",
				"secondTextColor": "",
				"blinkSpeed": ""
			}},
			"script": {{
				"program": "",
				"command": ""
			}}
		}}
		'''
		self.gui.show_window(data)

	def stop(self):
		"""
		Chiude la GUI di stato.
		"""
		log.info('Chiusura del menu')
		self.interrupt = True
		self.gui.stop()
