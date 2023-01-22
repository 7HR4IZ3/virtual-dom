import os
dir = os.path.dirname(__file__)
with open(dir + "/jyserver.js", "rb") as f:
    JSCRIPT = f.read()