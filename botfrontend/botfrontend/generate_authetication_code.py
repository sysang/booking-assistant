import random
import string
import base64
import hashlib

code_verifier = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(random.randint(43, 128)))
code_verifier = base64.urlsafe_b64encode(code_verifier.encode('utf-8'))

code_challenge = hashlib.sha256(code_verifier).digest()
code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8').replace('=', '')
print('code_challenge: ', code_challenge)  # Mysp4UxsX669Ub6zRP1xuH0ub9V4aT16DVlLad2KYSI

# export ID=hr1KELDoCLue5AAbtNHaTSmwGyqBp341GVT6Upqn
# export SECRET=0ITbfqrVbrhqBnvaZdUkdDAq4WmKVXNlfgnBsf5iCZO0qeO3n6vQHKvXBAs9tu5OXfJDCZpvgpCNNOk0S7d3ZGIdNeR9qQvNh2YyMXxoXd5EGLAM62t2sv7VWbn8BdOb

# http://rasachatbot.sysang/dialogue/o/authorize/?response_type=code&code_challenge=Mysp4UxsX669Ub6zRP1xuH0ub9V4aT16DVlLad2KYSI&client_id=hr1KELDoCLue5AAbtNHaTSmwGyqBp341GVT6Upqn&redirect_uri=http://rasachatbot.sysang/dialogue/noexist/callback
