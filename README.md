# Speechcad

## Setup
The first thing to do is to clone the repository:

```sh
git clone https://github.com/richbayo/Speechcad-Backend.git
cd Speechcad-Backend
```

Create a virtual environment to install dependencies in and activate it:

```sh
$ python3 -m venv venv
$ source venv/bin/activate
```
Then install the dependencies through the following command:
```sh
pip install -r requirements.txt
```

Once `pip` has finished downloading the dependencies, make migrations using the following command:
```sh
python3 manage.py migrate
```
A sample env file is given for your assistance. create your own .env file through the following command.
```sh
cp sample.env .env
```
Replace the key values with your project variables.

Then run the following commands to start the services.

Start the bot:
```sh
python3 manage.py startbot
```

Then, start your server:
```sh
python3 manage.py runserver
```

To start the celery beat service, run the following command:
```sh
celery -A TelegramBot beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

To start the celery service, run the following command:
```sh
celery -A TelegramBot worker --loglevel=info
```
To start the flower service, run the following command:
```sh
celery -A TelegramBot flower
```

For admin panel, navigate to `http://127.0.0.1:8000/admin/`.
For flower dashboard, visit  `http://0.0.0.0:5555`.
