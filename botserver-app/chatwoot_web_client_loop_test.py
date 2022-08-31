import http.client
import time

def test(counter=0):
    conn = http.client.HTTPConnection("rasachatbot.sysang")

    payload = "{\n\t\"message_type\": \"incoming\",\n\t\"conversation\": { \"id\": 1, \"status\": \"pending\" },\n\t\"sender\": { \"id\": 1 },\n\t\"content\": \"hi\"\n}"

    headers = { 'Content-Type': "application/json" }

    conn.request("POST", "/webhooks/chatwoot/cwwebsite", payload, headers)

    res = conn.getresponse()
    data = res.read()

    print('Counter: ', counter)

for i in range(3600):
    test(i)
    time.sleep(1)
