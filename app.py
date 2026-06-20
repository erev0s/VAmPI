from config import vuln_app
import os

'''
 Decide if you want to server a vulnerable version or not!
 DO NOTE: some functionalities will still be vulnerable even if the value is set to 0
          as it is a matter of bad practice. Such an example is the debug endpoint.
'''
vuln = int(os.getenv('vulnerable', 1))
# vuln=1
# token alive for how many seconds?
alive = int(os.getenv('tokentimetolive', 60))
# default to original 5000 but make easy to use a different one when running standalone
# example `export port=5050; python3 app.py`
port = int(os.getenv('port', 5000))

# start the app with port 5000 (unless explicitly overridden) and debug on!
if __name__ == '__main__':
    vuln_app.run(host='0.0.0.0', port=port, debug=True)
