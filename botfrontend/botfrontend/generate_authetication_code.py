import random
import string
import base64
import hashlib

code_verifier = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(random.randint(43, 128)))
code_verifier = base64.urlsafe_b64encode(code_verifier.encode('utf-8'))

code_challenge = hashlib.sha256(code_verifier).digest()
code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8').replace('=', '')
print('code_verifier: ', code_verifier)  # QlZDRFhBNFhLOFZEVFMxTlFUU0RDQzdIUENTMURCVEVITlZZRkJDMDQyTFpONUpKRUtTTjlDVU5aNzE=
print('code_challenge: ', code_challenge)  # SvDHn491oJJ6kCOcGuRuZ-V0eg19NVI4q0yJDfj8B3M

OAUTH2_APP_ID='SAv9oQXjRP6Dfa08o4EPUVjuLMbEHXiemfI67av4'
# OAUTH2_APP_SECRET='JYYxLsXMRNfvkKvQfc8RLzxCtNsykiN8jqgVhoANQHtbNP9QGvyuyy1FMjOh2puivkVgZJuhnHTGuACCayZAASe6Fn8GlTVAamTs8iBIBFZEWLZX8LSgLquBKtrZHFcQ'

url = f"http://rasachatbot.sysang/dialogue/o/authorize/?response_type=code&code_challenge={code_challenge}&client_id={OAUTH2_APP_ID}"
print('url: ', url)
