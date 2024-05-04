import PySimpleGUI as default_gui
import PySimpleGUIWeb as web_gui
from PySimpleGUI.PySimpleGUI import WIN_CLOSED
from plyer import notification
import threading
from time import sleep
import base64
import binascii
from io import BytesIO
from PIL import Image, UnidentifiedImageError
import json
import sys
from os.path import abspath, join, exists

from common import log

class NotificationBuilder():
	"""
	Questa classe permette di generare dinamicamente in base ad un dizionario
	un interfaccia grafica strutturata a righe e colonne.
	L'interfaccia può essere una finestra pop-up o una notifica di sistema
	in base ai dati passati, oppure una pagina web:
	la distinzione viene fatta controllando il valore della porta.
	Le interfacce possono essere interattive e avere elementi dinamici,
	anche questi parzialmente gestiti dalla presente classe.
	"""

	FOREGROUND = False
	BACKGROUND = True
	MIN_SIZE = 20

	def __init__(self, port='', scriptManager='', callback='', imagesPath='', logoPath='', testing=False):
		"""
		Istanzia un oggetto NotificationBuilder specificandone la porta web,
		il gestore degli script, una callback e il percorso nel quale cercare
		le eventuali immagini.
		
		:param port (str, opzionale): la porta web sulla quale avviare l'interfaccia.
				Se non è specificata, la finestra apparirà sul desktop.
			Default: ''.
		:param scriptManager (ScriptManager, opzionale): il gestore degli script
				allegati alla finestra (già preconfigurato).
			Default: ''.
		:param callback (func, opzionale): la funzione di callback per notificare
				l'interazione con un'interfaccia.
			Default: ''.
		:param imagesPath (str, opzionale): il percorso assoluto nel quale cercare
				le immagini, se specificate in questo formato e non come base64.
			Default: ''.
		:param logoPath (str, opzionale): il percorso dell'icona per le notifiche di sistema.
			Default: ''.
		:param testing (bool, opzionale): se True, alcune funzionalità legate alla
				notifica (script, blocco completo,...) vengono ignorate.
			Default: False
		"""
		self.interrupt = False
		self.port = port
		self.scriptManager = scriptManager
		self.name = ''
		self.interacted = callback
		self.imagesPath = imagesPath
		self.logoPath = logoPath
		self.windowReady = False
		self.textBlink = threading.Thread()
		self.bgBlink = threading.Thread()
		self.scriptThread = threading.Thread()
		self.testing = testing
		self.activeWindow = False

	def get_image(self, image):
		"""
		Interpreta il parametro image definendo se si tratta di dati base64
		oppure di un percorso locale/di rete.
		
		:param image (str): i dati dell'immagine.
		
		:return: i dati base64 dell'immagine se valida, altrimenti ''.
		"""
		try:
			return self.to_png(image)
		except UnidentifiedImageError:
			pass
		except binascii.Error:
			pass
		try:
			path = abspath(join(sys.path[0], self.imagesPath, image))
			# la decodifica è fallita; i dati vengono considerati come un percorso
			if exists(path):
				with open(path, "r+b") as file:
					data = base64.b64encode(file.read())
					return self.to_png(data)
		except Exception as e:
			log.warning('Dati dell\'immagine della notifica "{}" non validi'.format(self.data['name']))
			pass
		# i dati dell'immagine non sono validi, quindi vengono ignorati
		return ''

	def to_png(self, data):
		"""
		Verifica che l'immagine sia in formato PNG (l'unico accettato).
		Se non lo è, la converte.
		
		:param data (str): i dati dell'immagine.
		
		:return: i dati dell'immagine convertita se necessario.
		"""
		img = Image.open(BytesIO(base64.b64decode(data)))
		buffer = BytesIO()
		if img.format != 'PNG':
			img.save(buffer, format="PNG")
			return base64.b64encode(buffer.getvalue())
		else:
			return data

	def get_window(self, data):
		"""
		Crea la finestra interpretando il contenuto del parametro data.
		
		:param data (dict, str): i dati della finestra. Possono essere un dizionario
			oppure una stringa contente JSON valido.
		
		:return: l'oggetto generato della finestra, le thread di lampeggiamento
			del testo e dello sfondo e la thread per eseguire lo script.
		"""
		try:
			# tenta l'eventuale conversione in dizionario
			data = json.loads(data)
		except TypeError:
			pass

		self.data = data
		text = self.data['text']
		script = self.data['script']
		self.name = data['name']

		window = ''

		
		# solo la thread dello script è inizializzata qua, dato che è l'unica
		# che può essere avviata insieme alle notifiche di sistema
		scriptThread = ''

		if self.valid_val(['program'], script) and self.port == '' and not self.testing:
			scriptThread = threading.Thread(target=self.scriptManager.run, args=[
				script['program'], script['command']])

		if data['osType']:
			# le notifiche si sistema vengono create solo se non si tratta di un'anteprima web
			if self.port == '':
				if scriptThread != '':
					log.warning('Avvio dello script allegato alla notifica')
					scriptThread.start()
					
				log.info('Creazione della notifica di sistema "{}"'.format(self.name))
				window = [text['title'], text['message'][0:256], self.name,
					abspath(join(sys.path[0], self.imagesPath, self.logoPath))]
				self.windowReady = True
				return window, data['osType']
			else:
				log.info('Non è possibile caricare la preview di una notifica di sistema ({})'.format(data['name']))
				return '', ''
		else:
			pass
			log.info('Creazione della notifica pop-up "{}"'.format(self.name))
		style = self.data['style']
		interactivity = self.data['interactivity']

		sg = web_gui if self.port != '' else default_gui
		if self.valid_val(['theme'], style):
			sg.theme(style['theme'])

		bgColor = style['bgColor'] if self.valid_val(['bgColor'], style) else None
		textColor = text['textColor'] if self.valid_val(['textColor'], text) else None

		sg.set_options(
			background_color=bgColor, text_element_background_color=bgColor,
			text_color=textColor, button_color=(bgColor, textColor) if bgColor and textColor else None)

		elements = []

		if self.testing:
			elements.append([sg.Button(key='-BUTTON_CLOSE_TESTING-',
									   button_text='(Chiusura, solo per test)')])

		textStyle = ''

		# stile testo generale
		if self.valid_val(['font', 'textSize'], text) and self.valid_int(['textSize'], text):
			textStyle = text['font']+' '+str(text['textSize'])
		
		# stile titolo
		if self.valid_val(['title'], text):
			titleStyle = ''
			if self.valid_val(['font', 'textSize'], text) and self.valid_int(['textSize'], text):
				titleStyle = text['font']+' '+str(int(text['textSize'])*3)
			elements.append([sg.Text(key='-TEXT_TITLE-', text=text['title'],
									 font=titleStyle)])
		if self.valid_val(['message'], text):
			elements.append([sg.Text(key='-TEXT_MESSAGE-',
									 text=text['message'])])

		if self.valid_val(['image'], style):
			style['image'] = self.get_image(style['image'])
			if style['image'] != '':
				elements.append(
					[sg.Image(key="-IMAGE-", data=self.get_image(style['image']))])
		inputs = []
		if self.valid_val(['buttonText'], interactivity):
			inputs.append(sg.Button(
				key='-BUTTON_INPUT-', button_text=interactivity['buttonText']))
		if self.valid_val(['canClose'], interactivity) and interactivity['canClose']:
			inputs.append(sg.Button(key='-BUTTON_CLOSE-',
									button_text='Chiudi'))

		if inputs != []:
			elements.append(inputs)

		layout = elements

		size = (None, None)
		if self.valid_val(['width', 'height'], style):
			style['width'] = int(style['width']) if int(style['width']) > self.MIN_SIZE else ''
			style['height'] = int(style['height']) if int(style['height']) > self.MIN_SIZE else ''
			size = (style['width'], style['height']) if self.valid_int(
				['width', 'height'], style) else (None, None)

		window = sg.Window(data['name'], layout,
						   keep_on_top=True, alpha_channel=1-(float(style['alpha'])/100 if self.valid_int(['alpha'], style) else 1),
						   font=textStyle, size=size, no_titlebar=True, text_justification='c',
						   grab_anywhere=self.valid_val(['canMove'], interactivity) and interactivity['canMove'],
						   element_justification='c')

		textBlink = ''
		bgBlink = ''
		closeThread = ''

		
		if self.valid_val(['secondTextColor', 'blinkSpeed'], text):
			textBlink = threading.Thread(target=self.blink, args=[
				window, self.FOREGROUND, text['textColor'], text['secondTextColor'],
				text['blinkSpeed']], daemon=True)

		if self.valid_val(['secondBgColor', 'blinkSpeed'], style):
			bgBlink = threading.Thread(target=self.blink, args=[
				window, self.BACKGROUND, style['bgColor'], style['secondBgColor'],
				style['blinkSpeed']], daemon=True)

		if self.valid_val(['timer'], interactivity) and self.port == '':
			closeThread = threading.Thread(target=self.plan_close, args=[interactivity['timer']])

		self.windowReady = True
		return window, textBlink, bgBlink, closeThread, scriptThread

	def run_window(self, window, textBlink='', bgBlink='', closeThread='', scriptThread=''):
		"""
		Prepara ed eseguela finestra e le threads allegate,
		
		:param window (sg.Window): la finestra da avviare.
		:param textBlink (Thread, opzionale): la thread per il lampeggiamento del testo.
			Default: ''.
		:param bgBlink (Thread, opzionale): la thread per il lampeggiamento dello sfondo.
			Default: ''.
		:param scriptThread (str, opzionale): la thread per l'esecuzione dello script,
				eseguito in modo asincrono per non bloccare il resto del programma.
			Default: ''.
		"""

		# le threads vengono assegnate a degli attributi
		if not self.windowReady or self.data['osType'] and self.port != '':
			
			return
		if self.data['osType']:
			log.warning('Avvio della notifica di sistema "{}"'.format(self.name))
			notification.notify(*window)
			return
		blocking = self.data['interactivity']['blocking'] and not self.testing

		if self.port != '':
			window.web_start_browser = False
			window.web_port = self.port
		try:
			if self.activeWindow:
				return
			window.finalize()

		except ValueError:
			return
		log.info('Finestra finalizzata, avvio di "{}"'.format(self.name))

		
		if self.port == '':
			# usando la finestra come modal, è possibile disgnare quella sottostante
			# e simulare l'attributo "bloccate"
			window.make_modal()

		created = False
		backgroundWindow = ''
		backgroundEvent = ''
		backgrounValues = ''
		event = ''

		if self.activeWindow:
			#return
			return
			
		self.activeWindow = True

		if textBlink != '':
			self.textBlink = textBlink
			self.textBlink.start()
		if bgBlink != '':
			self.bgBlink = bgBlink
			self.bgBlink.start()
		if closeThread != '':
			closeThread.start()
		if scriptThread != '' and self.port == '':
			log.warning('Avvio dello script allegato alla notifica')
			scriptThread.start()
		while not self.interrupt:
			# per evitare che multiple finestre web interferiscano,
			# l'attributo è riassegnato ad ogni ciclo
			self.activeWindow = True
			event, values = window.read(500)
			if self.port == '':
				# crea la finestra trasparente a tutto schermo per simulare un
				# blocco del computer
				if blocking and not created:
					backgroundWindow = default_gui.Window(title='', layout=[[default_gui.Text(key='-TEXT_TITLE-', text="")]], keep_on_top=True,
														  no_titlebar=True, alpha_channel=0.01, location=(-1920, -1920), size=(5760,5760), background_color="#000", finalize=True)
					created = True

				if created:
					backgroundEvent, backgrounValues = backgroundWindow.read(
						timeout=0)
				if backgroundEvent == WIN_CLOSED:
					break

				#if self.port == '':
				if event == '-BUTTON_INPUT-':
					# usa la callback per notificare un'interazione
					if self.interacted != '':
						self.interacted(self.name)


				if event is None or event.startswith('-BUTTON_CLOSE') or event == WIN_CLOSED:
					self.interrupt = True
					log.warning('Chiusura della finestra "{}"'.format(self.name))
					break
				
		if self.port == '':
			window.close()
		self.activeWindow = False
		if backgroundEvent is not None and backgroundWindow is not None and hasattr(backgroundWindow, 'close'):
			backgroundWindow.close()

	def blink(self, window, type, firstColor, secondColor, speed):
		"""
		Cambia periodicamente colore a degli elementi della finestra in base
		ai parametri.
		
		:param window (sg.Window): la finestra con gli elementi ai quali cambiare colore.
		:param type (bool): il tipo degli elementi (True = sfondo, False = testo e pulsanti).
		:param firstColor (str): il colore di base degli elementi.
		:param secondColor (str): il secondo colore degli elementi.
		:param speed (float): la velocità di cambio del colore.
		"""
		speed = float(speed)
		try:
			color = firstColor
			while not self.interrupt:
				self.update_style(window, type, color)
				color = firstColor if color == secondColor else secondColor
				sleep(speed)
				
		except RuntimeError as e:
			# PySimpleGUI solleva degli errori non gravi se lo stile degli
			# elementi viene cambiato al di fuori della thread principale
			pass

	def update_style(self, window, type, color):
		"""
		Itera tra gli elementi e ne cambia il colore in base ai parametri.
		
		:param window (sg.Window): la finestra con gli elementi ai quali cambiare colore.
		:param type (bool): il tipo degli elementi (True = sfondo, False = testo e pulsanti).
		:param color (str): il colore da impostare.
		"""
		if type == self.FOREGROUND:
			for key, element in window.AllKeysDict.items():
				# gli elementi sono identificati grazie al "prefisso" delle loro chiavi
				if key.startswith('-TEXT'):
					element.update(text_color=color)
				elif key.startswith('-BUTTON'):
					element.update(
						button_color=(color, element.ButtonColor[1]))
		elif type == self.BACKGROUND:
			for key, element in window.AllKeysDict.items():
				if key.startswith('-TEXT'):
					element.update(background_color=color)
				elif key.startswith('-BUTTON'):
					element.update(
						button_color=(element.ButtonColor[0], color))
				if hasattr(window.TKroot, 'configure'):
					window.TKroot.configure(background=color, bg=color)
				else:
					window.BackgroundColor = color
					window.refresh()

	def plan_close(self, timer):
		"""
		Attende alcuni secondi prima di inviare automaticamente il comando di
		chiusura della notifica. Funge da timer di spegnimento.
		
		:param timer (int): il tempo da attendere, in secondi.
		"""
		try:
			timer = int(timer)
			sleep(timer)
			self.interrupt = True
		except ValueError:
			log.warning('Valore del timer "{}" non valido')
			pass

	def show_window(self, data, port=None):
		"""
		Gestisce la creazione e l'avvio della finestra.
		
		:param data (str): i dati della notifica.
		:param port (int, opzionale): la porta web della finestra.
				Se non è impostata, viene tenuta quella precedente (se presente).
			Default: None.
		"""
		self.stop()
		if self.activeWindow:
			# la finestra ci sta mettendo troppo a chiudersi, non procedere
			self.stop()
			return

		# dopo aver controllato che non ci siano finestre attive, imposta interrupt
		# su False per permettere a una nuova finestra di venir avviata
		self.interrupt = False

		# assegna all'attributo la porta passata come parametro, se valida
		if port is not None:
			self.port = port
		
		# crea e avvia la finestra
		self.run_window(*self.get_window(data))
		self.stop()

	def stop(self, name=''):
		"""
		Gestisce la procedura di chiusua di tutte le threads e della finestra.
		
		:param name (str, opzionale): il nome della finestra da chiudere.
			Default: ''.
		"""
		# interrompe solo se il nome corrisponde, se non è specificato
		# oppure se non è già in corso un'interruzione
		if (name == '' or self.name == name) and not (self.interrupt and self.activeWindow):
			self.interrupt = True
			# ogni thread potrebbe non essere stata specificata, quindi servono
			# molteplici controlli per assicurare la fine di tutte
			try:
				self.textBlink.join()
			except Exception as e:
				pass
			try:
				self.bgBlink.join()
			except Exception as e:
				pass

	def get_themes(self):
		"""
		Ritorna la lista dei temi della finestra disponibili di default.
		
		:return: la lista dei temi.
		"""
		return default_gui.theme_list()

	def valid_int(self, keys, dict):
		"""
		Controlla la validità delle chiavi nel dizionario e la possibilità
		di usarli come valori numerici.
		
		:param keys (list): la lista di chiavi da controllare.
		:param dict (dict): il dizionario nel quale cercare le chiavi.
		
		:return: True se il valore è un int valido, altrimenti False.
		"""
		if self.valid_val(keys, dict):
			for k in keys:
				try:
					int(dict[k])
				except ValueError:
					return False
			return True
		return False

	def valid_val(self, keys, dict):
		"""
		Controlla la validità delle chiavi nel dizionario.
		Permette di verificare che i dati della notifica siano validi
		prima di assegnarsi al layout della finestra.
		
		:param keys (list): la lista di chiavi da controllare.
		:param dict (dict): il dizionario nel quale cercare le chiavi.
		
		:return: True se il valore è valido per l'uso, altrimenti False.
		"""
		for k in keys:
			if k not in dict or dict[k] is None or str.strip(str(dict[k])) == '':
				return False
		return True
