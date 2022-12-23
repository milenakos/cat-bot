from replit import db
import json
file = open("backup.json", "w")
stuff = {}

def convert(thing):
  if str(thing).startswith("ObservedDict"):
    thing = dict(thing)
  if str(thing).startswith("ObservedList"):
    thing = list(thing)
  return thing

for key, value in db.items():
  value = convert(value)
  if isinstance(value, dict):
    for k,v in value.items():
      value[k] = convert(v)
      if isinstance(value, dict):
        try:
          for kk,vv in v.items():
            value[k][kk] = convert(vv)
        except:
          pass
  #print(key, value)
  stuff[key] = value

print(stuff)
json.dump(stuff, file)
file.close()