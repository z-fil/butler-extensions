from datetime import datetime

with open('./generato_da_script.txt', 'w') as f:
    f.write("Lo script ha creato questo file alle ore {}".format(datetime.now()))
