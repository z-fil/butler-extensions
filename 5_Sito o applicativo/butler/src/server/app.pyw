import sys
from os import devnull, getenv
from os.path import abspath, join, dirname, basename
sys.path.append(abspath(join(sys.path[0], '..')))

from server.manager import Manager

"""
Avvia il programma server senza terminale.
Può essere avviato automaticamente all'accensione del computer in modo che
il programma funzioni in background.
"""
if __name__ == "__main__":
	if sys.executable.endswith("pythonw.exe"):
		sys.stdout = open(devnull, "w")
		sys.stderr = open(join(getenv("TEMP"), "stderr-"+basename(sys.argv[0])), "w")
	Manager().start()
