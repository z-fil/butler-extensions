import psutil
import datetime
import platform

from common import log

class Inventory():
	"""
	Questa classe esegue un inventario dei componenti del computer.
	"""

	MAC_LENGTH = 17

	def __init__(self, ip='127.0.0.1'):
		"""
		Istanzia un oggetto Inventory definendone l'indirizzo IP.

		:param ip (str): l'indirizzo da usare.
			Default: '127.0.0.1'
		"""
		self.ip = ip
		self.mac = None
		self.data = {}

	def get_mac(self):
		"""
		Trova il MAC address della scheda con l'ip specificato

		:return: l'indirizzo MAC corrispondente
		"""
		addrs = psutil.net_if_addrs()
		mac = ''
		# controlla ogni interfaccia
		for name in psutil.net_if_addrs():
			for interface in addrs[name]:
				if interface.address == self.ip:
					for c in addrs[name]:
						# molti attributi "address" non corrispondono al MAC:
						# quello richiesto viene riconosciuto in base alla lunghezza
						if len(c.address) == self.MAC_LENGTH:
							mac = c.address
							break
					# esegue il log solo se non era già conosciuto
					if self.mac == mac:
						break
					log.info('L\'ip usato {} è legato alla scheda {} con MAC Address {}'.format(
						self.ip, name, mac))
					break
		self.mac = mac
		return mac
	
	def get_inventory(self, attr=[]):
		"""
		Trova diverse informazioni sul PC.

		:param attr (list, optional): gli attributi aggiuntivi da allegare
				Deve essere una lista testuale di nomi di funzioni.
				Quelli non validi saranno ignorati.
			Default: [].
		"""
		
		data = {
			'os': [platform.system(), platform.release(), platform.version(), platform.architecture()[0]],
			'hostname': platform.node(),
			'mac': self.mac if self.mac is not None else self.get_mac(),
			'last_ip': self.ip,
			'last_users': [user.name for user in psutil.users()],
			'last_boot': datetime.datetime.fromtimestamp(
				psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
			'cpu': {
				'model':platform.processor(),
				'freq': psutil.cpu_freq().current if hasattr(psutil.cpu_freq(), 'current') else psutil.cpu_freq(),
				'cores': psutil.cpu_count(logical=False),
				'threads':psutil.cpu_count()
			},
			'interfaces': [name for name in psutil.net_if_stats()],
			'ram': psutil.virtual_memory().total/1024/1024,
			'swap': psutil.swap_memory().total/1024/1024,
			'disk': []
		}

		# prova a prendere le informazioni degli attributi aggiuntivi
		for key in attr:
			try:
				data[key] = getattr(psutil, key)()
			except:
				# se non è una funzione, prova ad eseguirlo come attributo
				try:
					data[key] = getattr(psutil, key)
				except:
					pass

		# prende le informazioni sui dischi ne migliora la presentazione
		for disk in psutil.disk_partitions():
			partition = {'device':disk.device, 'file system': disk.fstype, 'options': disk.opts}
			try:
				# i dati sono convertiti in megabytes
				partition['size'] = psutil.disk_usage(disk[0]).total/1024/1024
				partition['used'] = psutil.disk_usage(disk[0]).used/1024/1024
			except Exception as e:
				log.warning(e.__str__())
				pass
			data['disk'].append(partition)

		# logga solo se le informazioni sono utili
		if self.data != data:
			self.data = data
			log.info('Informazioni inventario {} ({}) aggiornate'.format(data['hostname'], data['mac']))

		return data