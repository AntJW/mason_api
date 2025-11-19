## Local Development

### Firebase Emulator 
<!-- Specifying FIREBASE_AUTH_EMULATOR_HOST enables this api to connect to the flutter app repo's auth emulator. -->
export FIREBASE_AUTH_EMULATOR_HOST="127.0.0.1:9099" && firebase emulators:start

Note: Use `.env.local` and `.secret.local` to define environment variables and secrets for local development. Those local files are automatically used when calling `firebase emulators:start`.

#### REST Client
[REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) allows you to send HTTP request and view the response in Visual Studio Code directly. This is great for testing api endpoints/functions without having to go through a UI. Start by downloading the REST Client Visual Code plugin. Then create a `test.http` (or any file name with extention .http), and start sending requests. 

Example test.http: 

```bash
GET http://127.0.0.1:5001/mason-b4c0a/us-central1/api/hello-world
content-type: application/json

{}
```
