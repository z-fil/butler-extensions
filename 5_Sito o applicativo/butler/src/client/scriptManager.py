import base64
from os.path import join, abspath, isfile
import subprocess
import sys

from common import log

class ScriptManager():
	"""
	Questa classe gestisce l'esecuzione di scripts e il loro output.
	"""

	def __init__(self, scriptsPath):
		"""
		Istanzia un oggetto ScriptManager definendo il percorso degli script.
		
		:param scriptsPath (str): il percorso nel quale salvare gli script.
		"""
		self.scriptsPath = scriptsPath

	def get_file_or_path(self, program, script):
		"""
		Analizza i parametri e sceglie se creare un file nel quale salvare il
		codice dello script oppure eseguirlo direttamente.
		
		:param program (str): il programma con il quale avviare lo script
			e il nome del file effettivo da avviare:
			es. "java myscript.java".
		:param script (str): i dati in base64 del file
			oppure il percorso di un file da avviare.
		:return: il nome del file da eseguire.
		"""

		try:
			# usa la seconda parola dopo lo spazio come nome del file
			# es. da "java myscript.java", prende "myscript.java".
			# Se non c'è una seconda parola, interpreta i dati dello script come
			# nome del file: significa che il parser a livello server non ha trovato
			# un file, quindi ritorna il percorso al posto dei dati base64
			programArgs = program.split(' ')
			if script == '':
				return ' '.join(programArgs[1:])
			fileName = ' '.join(programArgs[1:]) if len(
				programArgs) > 1 else script
			if not isfile(abspath(fileName)):
				script = script.encode()
				fullPath = abspath(join(sys.path[0], self.scriptsPath, fileName))
				with open(fullPath, "wb") as fh:
					fh.write(base64.decodebytes(script))
					log.warning('Creato il file "{}"'.format(fullPath))
					pass
			fileName = abspath(join(sys.path[0], self.scriptsPath, fileName))
			return fileName
			
		except Exception as e:
			log.warning(
				'Errore non grave nel parse del comando {}: {}.\nÈ usato invece: {}'.format(
					program, e, fileName))
			return fileName

	def run(self, program, scriptData):
		"""
		Esegue uno script in base ai parametri passati
		
		:param program (str): il programma con il quale avviare lo script.
		:param scriptData (str): i dati base64 dello script o il suo percorso.
		"""
		log.warning('Esecuzione di uno script con il comando di base: "{}"'.format(program))
		scriptData = self.get_file_or_path(program, scriptData)
		program = program.split(' ')[0]

		result = subprocess.Popen([program, scriptData], stdout=subprocess.PIPE)
		output = result.communicate()
		if result.returncode != 0:
			log.warning('Errore nell\'esecuzione dello script "{}": {}'.format(
				program, output[0].decode()))
		else:
			log.info('Comando "{}" eseguito correttamente. Output:\n{}'.format(
				program, output[0].decode()))
