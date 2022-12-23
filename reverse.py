def reverse():
	a = open("backup.txt", "r")
	c = a.read()
	a.close()
	with open("db.json", "w") as file:
    		file.write(c.replace("\'", "\"").replace("True", "true").replace("False", "false"))
