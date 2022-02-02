import os

import asyncio

import requests
from aiohttp import web
import hashlib

from multidict import MultiDict

# Папка для хранения кеша
DIR_BASE = "cache"
# URL для перенаправления запросов пользователей, если кеш не найден или для обновления кеша
URL_BASE = "http://127.0.0.1:8000"


# Получить путь до кеша по ключу
def get_path(key):
    filename = hashlib.md5(key.encode()).hexdigest()
    dir = hashlib.md5(filename.encode()).hexdigest()[:3]
    return f"{DIR_BASE}/{dir}/{filename}"


# Получение ключа по данным запроса
def get_key(request):
    request_method = request.method
    scheme = request.scheme
    http_currency = request.match_info.get('url', "Anonymous")
    language = request.headers.get("Accept-Language")
    if language is None:
        language = "ru"

    user = request.headers.get("Authorization")
    if user is None:
        user = "Anonymous"

    currency = request.headers.get("Currency")
    if currency is None:
        currency = "USD"

    host = request.headers.get("Host")
    if host is None:
        host = "localhost"

    if request_method == "POST":
        args = request.text()
    else:
        args = request.query_string

    key = http_currency + "$" + request_method + "$" + args + "$" + language + "$" + user + "$" + currency + "$" \
        + scheme + "$" + host
    return key


# Получение кеша страницы из файла
def get_cash(path, key):
    try:
        dir = '/'.join(path.split('/')[:-1])
        if not os.path.exists(dir):
            os.mkdir(dir)

        if os.path.exists(path):
            f = open(path)
            lines = f.readlines()
            key_cache = lines[0].replace("\n", "")
            headers = MultiDict()

            ind = 1
            while lines[ind] != "--------------------\n":
                header = lines[ind].replace("\n", "").split(":")
                headers.add(header[0], header[1])
                ind += 1

            if len(lines) == ind + 1:
                text = ""
            else:
                text = '\n'.join(lines[ind + 1:])
            f.close()
            if key == key_cache:
                return text, headers
    except Exception as e:
        print(f'Error {path}, {e}')
    return None


# Получение страницы по url
def get_page(request):
    headers = {}

    for key in request.headers:
        headers[key] = request.headers[key]

    if request.method == "GET":
        return requests.get(URL_BASE + request.path_qs, headers=headers)
    elif request.method == "POST":
        body = request.text()
        return request.post(URL_BASE + request.path_qs, headers=headers, body=body)
    else:
        return requests.options(URL_BASE + request.path_qs, headers=headers)


# Запись полученной страницы по пути
def get_cache(request, path, key):
    result = get_page(request)
    headers = MultiDict()

    for header in result.headers:
        headers.add(header, result.headers[header])

    if result.status_code == 200:
        my_file = open(path, "w+")
        my_file.write(key + "\n")
        for key in result.headers:
            my_file.write(f"{key}:{result.headers[key]}\n")
        my_file.write("--------------------\n")
        my_file.write(result.text)
        my_file.close()
    return (result.text, headers)


# Обновление кеша
async def get_update(request, path, key):
    get_cache(request, path, key)


async def handle(request):
    key = get_key(request)
    path = get_path(key)
    cache = get_cash(path, key)
    if cache is None:
        cache = get_cache(request, path, key)
    else:
        asyncio.ensure_future(get_update(request, path, key))

    text, headers = cache
    return web.Response(text=text, headers=headers)


app = web.Application()
app.add_routes([web.get(r'/{url:\S+}', handle),
                web.post(r'/{url:\S+}', handle),
                web.options(r'/{url:\S+}', handle)
                ])

if __name__ == '__main__':
    web.run_app(app)
