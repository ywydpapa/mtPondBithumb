import jwt
import uuid
import time
import requests

# Set API parameters
accessKey = "1deea37ce554fffa65601bbbcf0c77ca8dfe2a662bacee"
secretKey = "MjAxYzg0MjZjZmMyMGY5N2E4N2VlMjUxZmNmODE2MTAxZGI5YzIwMzc5YzA4ZmY2MjU2MDI4YWVlZWMxMQ=="
apiUrl = 'https://api.bithumb.com'

# Generate access token
payload = {
    'access_key': accessKey,
    'nonce': str(uuid.uuid4()),
    'timestamp': round(time.time() * 1000)
}
jwt_token = jwt.encode(payload, secretKey)
authorization_token = 'Bearer {}'.format(jwt_token)
headers = {
  'Authorization': authorization_token
}

try:
    # Call API
    response = requests.get(apiUrl + '/v1/accounts', headers=headers)
    # handle to success or fail
    print(response.status_code)
    print(response.json())
except Exception as err:
    # handle exception
    print(err)
