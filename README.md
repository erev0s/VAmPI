# VAmPI
**The Vulnerable API** *(Based on OpenAPI 3)*
![vampi](https://i.imgur.com/zR0quKf.jpg)


VAmPI is a vulnerable API made with Flask and it includes vulnerabilities from the OWASP top 10 vulnerabilities for APIs. It was created as I wanted a vulnerable API to evaluate the efficiency of tools used to detect security issues in APIs. It includes a switch on/off to allow the API to be vulnerable or not while testing. This allows to cover better the cases for false positives/negatives. VAmPI can also be used for learning/teaching purposes. You can find a bit more details about the vulnerabilities in [erev0s.com](https://erev0s.com/blog/vampi-vulnerable-api-security-testing/).


#### Features
 - Based on OWASP Top 10 vulnerabilities for APIs.
 - OpenAPI3 specs and Postman Collection included.
 - Global switch on/off to have a vulnerable environment or not.
 - Token-Based Authentication (Adjust lifetime from within app.py)

VAmPI's flow of actions is going like this: an unregistered user can see minimal information about the dummy users included in the API. A user can register and then login to be allowed using the token received during login to post a book. For a book posted the data accepted are the title and a secret about that book. Each book is unique for every user and only the owner of the book should be allowed to view the secret.

A quick rundown of the actions included can be seen in the following table:

| **Action** |            **Path**           |                     **Details**                    |
|:----------:|:-----------------------------:|:--------------------------------------------------:|
|     GET    |           /createdb           | Creates and populates the database with dummy data |
|     GET    |               /               |                     VAmPI home                     |
|     GET    |           /users/v1           |      Displays all users with basic information     |
|     GET    |        /users/v1/_debug       |         Displays all details for all users         |
|    POST    |       /users/v1/register      |                  Register new user                 |
|    POST    |        /users/v1/login        |                   Login to VAmPI                   |
|     GET    |      /users/v1/{username}     |              Displays user by username             |
|   DELETE   |      /users/v1/{username}     |       Deletes user by username (Only Admins)       |
|     PUT    |   /users/v1/{username}/email  |             Update a single users email            |
|     PUT    | /users/v1/{username}/password |                Update users password               |
|     GET    |           /books/v1           |                 Retrieves all books                |
|    POST    |           /books/v1           |                    Add new book                    |
|     GET    |        /books/v1/{book}       |      Retrieves book by title along with secret     |

For more details you can use a service like the [swagger editor](https://editor.swagger.io) supplying it the OpenAPI specification which can be found in the directory `openapi_specs`.


#### List of Vulnerabilities
 - SQLi Injection
 - Unauthorized Password Change
 - Broken Object Level Authorization
 - Mass Assignment
 - Excessive Data Exposure through debug endpoint
 - User and Password Enumeration
 - RegexDOS (Denial of Service)
 - Lack of Resources & Rate Limiting



 ## Run it
It is a Flask application so in order to run it you can install all requirements and then run the `app.py`.
To install all requirements simply run `pip3 install -r requirements.txt` and then `python3 app.py`.

Or if you prefer you can also run it through docker or docker compose.

 #### Run it through Docker

 - Available in [Dockerhub](https://hub.docker.com/r/erev0s/vampi)

**Build with**
~~~~
docker build -t vampi_docker:latest .
~~~~
 **and Run** *(remove the -d if you want to see the output in your terminal)*
 ~~~~
docker run -d -p 5000:5000 vampi_docker:latest
 ~~~~

[Note: if you run Docker on newer versions of the MacOS, use `-p 5001:5000` to avoid conflicting with the AirPlay Receiver service. Alternatively, you could disable the AirPlay Receiver service in your System Preferences -> Sharing settings.]

  #### Run it through Docker Compose
`docker-compose` contains two instances, one instance with the secure configuration on port 5001 and another with insecure on port 5002:
~~~~
docker-compose up -d
~~~~

## Customizing token timeout and vulnerable environment or not
If you would like to alter the timeout of the token created after login or if you want to change the environment **not** to be vulnerable then you can use a few ways depending how you run the application.

 - If you run it like normal with `python3 app.py` then all you have to do is edit the `alive` and `vuln` variables defined in the `app.py` itself. The `alive` variable is measured in seconds, so if you put `100`, then the token expires after 100 seconds. The `vuln` variable is like boolean, if you set it to `1` then the application is vulnerable, and if you set it to `0` the application is not vulnerable.
 - If you run it through Docker, then you must either pass environment variables to the `docker run` command or edit the `Dockerfile` and rebuild. 
   - Docker run example: `docker run -d -e vulnerable=0 -e tokentimetolive=300 -p 5000:5000 vampire_docker:latest`
     - One nice feature to running it this way is you can startup a 2nd container with `vulnerable=1` on a different port and flip easily between the two.

   - In the Dockerfile you will find two environment variables being set, the `ENV vulnerable=1` and the `ENV tokentimetolive=60`. Feel free to change it before running the docker build command.


 [Picture from freepik - www.freepik.com](https://www.freepik.com/vectors/party)

