from config import vuln_app

'''
 Decide if you want to server a vulnerable version or not!
 DO NOTE: some functionalities will still be vulnerable even if the value is set to 0
          as it is a matter of bad practice. Such an example is the debug endpoint.
'''
vuln = 1

# token alive for how many seconds?
alive = 10

if __name__ == '__main__':
    vuln_app.run(host='0.0.0.0', port=5000, debug=True)
