```
                 _   ___                     _     
                | | |__ \                   | |    
 _ __ ___   __ _| |_   ) | ___ __      _____| |__   Trashing your meta,
| '_ ` _ \ / _` | __| / / |___|\ \ /\ / / _ \ '_ \    keeping your data,
| | | | | | (_| | |_ / /_       \ V  V /  __/ |_) |     within your browser.
|_| |_| |_|\__,_|\__|____|       \_/\_/ \___|_.__/ 
```

This is an online version of [mat2](https://0xacab.org/jvoisin/mat2).
Keep in mind that this is a beta version, don't rely on it for anything
serious, yet.

# Introduction

Mat2-web offers a Restful API which enables consumers to upload their files
which will be cleaned using [mat2](https://0xacab.org/jvoisin/mat2) and can 
be downloaded afterward.

Therefore this project has two components:



* Restful API [Mat2-web](https://0xacab.org/jvoisin/mat2-web)
* Single Page Application Frontend [mat2-quasar-frontend](https://0xacab.org/jfriedli/mat2-quasar-frontend)

**To setup the application you'll need to deploy both parts.**

There are several ways for deployment:

1) [Manually](#manually)
2) [Ansible](#deploy-via-ansible)
3) [Containers](#container)

# Table Of Contents

[[_TOC_]]

# Demo instance

There is a demo instance deployed a [mat2web.dev](https://mat2web.dev/).
Please don't upload any sensitive files to it.


# Vue Frontend
![Frontend GIF Preview](https://0xacab.org/jfriedli/mat2-quasar-frontend/raw/2dd5de537088d67fe4167bf5b2e1f5dacf2fa537/mat-frontend.gif?inline=true)
There is a SPA Frontend available at https://0xacab.org/jfriedli/mat2-quasar-frontend. It consumes
the RESTful API of this project. As a fallback for non JS users it redirects to this web app.
To set it up checkout the [Readme](https://0xacab.org/jfriedli/mat2-quasar-frontend/blob/master/README.md).

# How to deploy it?

## Manually

mat2 is available in [Debian stable](https://packages.debian.org/stable/mat2).

```
# apt install uwsgi uwsgi-plugin-python3 git mat2
# apt install nginx-light  # if you prefer nginx
# apt install apache2 libapache2-mod-proxy-uwsgi  # if you prefer Apache2
# cd /var/www/
# git clone https://0xacab.org/jvoisin/mat2-web.git
# mkdir ./mat2-web/uploads/
# chown -R www-data:www-data ./mat2-web
```
### Build the CSS file

```bash
npm i
npm install --global postcss postcss-cli
npm run build:css
```

Since [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/) isn't fun to
configure, feel free to copy
[this file](https://0xacab.org/jvoisin/mat2-web/tree/master/config/uwsgi.config)
to `/etc/uwsgi/apps-enabled/mat2-web.ini` and
[this one](https://0xacab.org/jvoisin/mat2-web/tree/master/config/nginx-default.conf)
to `/etc/nginx/sites-enabled/mat2-web`.

Nginx is the recommended web engine, but you can also use Apache if you prefer,
by copying [this file](https://0xacab.org/jvoisin/mat2-web/tree/master/config/apache2.config)
to your `/etc/apache2/sites-enabled/mat2-web` file.

Make sure you configured the necessary [environment variables](#configuration).
 
Finally, restart uWSGI and your web server:

```
systemctl restart uwsgi
systemctl restart nginx/apache/…
```

It should now be working.

Note for reverse proxies: Include the Host header to ensure all generated urls are correct.
e.g. for Nginx: `proxy_set_header Host $host;`

## Deploy via Ansible

If you happen to be using [Ansible](https://www.ansible.com/), there's an
Ansible role to deploy mat2-web on Debian, thanks to the amazing
[systemli](https://www.systemli.org/en/index.html) people:
[ansible-role-mat2-web](https://github.com/systemli/ansible-role-mat2-web)

The role installs mat2-web as a uWSGI service, and runs it as a dedicated
system user, installs bubblewrap to sandbox mat2 and creates a garbage
collector cronjob to remove leftover files. Besides, it can create a
[dm-crypt](https://en.wikipedia.org/wiki/Dm-crypt) volume with random key for
the uploads folder, to ensure that the uploaded files won't be recoverable
between reboots.

## Container

There are two Dockerfiles present in this repository. 
The file called `Dockerfile.development` is used for development 
and `Dockerfile.production` is used for production deployments.

You can find the automated container builds in the registry of this 
repository: https://0xacab.org/jvoisin/mat2-web/container_registry

Make sure you configured the necessary [environment variables](#configuration).


### Building the production image using Docker
Build command: `docker build -f Dockerfile.production -t mat-web .`

Run it: `docker run -ti -p8181:8080 --read-only --tmpfs=/tmp --tmpfs=/run/uwsgi --tmpfs=/app/upload --security-opt=no-new-privileges --security-opt=seccomp=./config/seccomp.json mat-web:latest`

This does mount the upload folder as tmpfs and server the app on `localhost:8181`.

### Building the production image using Podman
Build: `podman build -f Dockerfile.production -t matweb-podman .`

Run: `podman run -ti -p8181:8080 --read-only  --tmpfs /tmp --tmpfs /run/uwsgi --tmpfs=/app/upload  --security-opt=no-new-privileges --security-opt=seccomp=./config/seccomp.json matweb-podman:latest`


# Configuration

The default settings from `main.py` may be overridden by adding a `config.py`
file and add custom values for the relevant flask config variables. E.g.:

```
MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB
```
## Configurable Environment Variables

| Env Variable                  | Default Value | Explanation                                                                                                                                                                                                                                                                                                                                  |
|-------------------------------|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| MAT2_ALLOW_ORIGIN_WHITELIST   | *             | Define which hosts are included in the Access-Control-Allow-Origin header. Note that you can add multiple hosts from which you want to accept API requests e.g. https://myhost1.org https://myhost2.org. These need to be separated by a space. **IMPORTANT**: The default value if the variable is not set is: `Access-Control-Allow-Origin: *` |
| MAT2_MAX_FILES_BULK_DOWNLOAD  |            10 | Max number of files that can be grouped for a bulk download                                                                                                                                                                                                                                                                                  |
| MAT2_MAX_FILE_AGE_FOR_REMOVAL |           900 | Seconds a file in the upload folder is kept. After that it will be deleted                                                                                                                                                                                                                                                                   |
| MAT2_WEB_DOWNLOAD_FOLDER      | ./uploads/    | Define the upload folder path.                                                                                                                                                                                                                                                                                                               |
## Custom templates

You can override the default templates from `templates/` by putting replacements
into the directory path that's configured in `app.config['CUSTOM_TEMPLATES_DIR']`
(default `custom_templates/`).

# RESTful API

If you go to https://api.mat2web.dev/apidocs/ you can find a Swagger documentation.

<p>
<details>
<summary>Click this for API Endpoints explanation</summary>

## Upload Endpoint

**Endpoint:** `/api/upload`

**HTTP Verbs:**  POST

**Body:** 
```json
{
	"file_name": "my-filename.jpg",
	"file": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
}
```

The `file_name` parameter takes the file name.
The `file` parameter is the base64 encoded file which will be cleaned.

**Example Response:**
```json
{
    "inactive_after_sec": 120,
    "output_filename": "fancy.cleaned.jpg",
    "mime": "image/jpg",
    "key": "81a541f9ebc0233d419d25ed39908b16f82be26a783f32d56c381559e84e6161",
    "secret": "44deb60b5febbd466e042f4172d36bcc5f7eb2eb6791d6e93191c378a381ae7c",
    "meta": {
        "BitDepth": 8,
        "ColorType": "RGB with Alpha",
        "Compression": "Deflate/Inflate",
        "Filter": "Adaptive",
        "Interlace": "Noninterlaced"
    },
    "meta_after": {},
    "download_link": "http://localhost:5000/download/81a541f9ebc0233d419d25ed39908b16f82be26a783f32d56c381559e84e6161/44deb60b5febbd466e042f4172d36bcc5f7eb2eb6791d6e93191c378a381ae7c/fancy.cleaned.jpg"
}
```

## Supported Extensions Endpoint

**Endpoint:** `/api/extension`

**HTTP Verbs:**  GET

**Example Response (shortened):**
```json
[
    ".asc",
    ".avi",
    ".bat",
    ".bmp",
    ".brf",
    ".c",
    ".css",
    ".docx",
    ".epub"
]
```

**Endpoint:** `/api/download/bulk`

This endpoint allows you to bulk download several files
which you uploaded beforehand. Note that the `download_list`
MUST contain more than two files. The max length is configurable
(default is 10).

**HTTP Verbs:**  POST

**Body:** 
```json
{
  "download_list": [
    {
        "file_name": "uploaded_file_name.jpg",
        "key": "uploaded_file_key",
        "secret": "uploaded_file_secret"
    }
  ]
}
```

The `file_name` parameter takes the file name from a previously uploaded file.
The `key` parameter is the key from a previously uploaded file.

**Example Response:**
```json
{
    "inactive_after_sec": 120,
    "output_filename": "files.2cd225d5-2d75-44a2-9f26-e120a87e4279.cleaned.zip",
    "mime": "application/zip",
    "key": "5ee4cf8821226340d3d5ed16bd2e1b435234a9ad218f282b489a85d116e7a4c4",
    "secret": "44deb60b5febbd466e042f4172d36bcc5f7eb2eb6791d6e93191c378a381ae7c",
    "meta_after": {},
    "download_link": "http://localhost/api/download/5ee4cf8821226340d3d5ed16bd2e1b435234a9ad218f282b489a85d116e7a4c4/files.2cd225d5-2d75-44a2-9f26-e120a87e4279.cleaned.zip"
}
```

**Endpoint:** `/api/remove_metadata`

**HTTP Verbs:**  POST

**CURL Example:** 
```bash
 curl -F 'file=@/path/to/my/test.txt' http://localhost:5000/api/remove_metadata
```
The `file` parameter is the file which will be cleaned.

**Example Response:**
The cleaned file

</details>
</p>


# Development / Contribute
Install docker and docker-compose and then run `docker-compose up` to setup
the docker dev environment. Mat2-web is now accessible on your host machine at `localhost:5000`.
Every code change triggers a restart of the app. 
If you want to add/remove dependencies you have to rebuild the container.
See [Flask configuration docs](http://exploreflask.com/en/latest/configuration.html)
for further information.


# Threat model

- An attacker in possession of the very same file that a user wants to clean,
	along with its names, can't perform a denial of service by continually
	requesting this file.
- An attacker in possession of only the name of a file that a user wants to
	clean can't perform a denial of service attack, since the path to download
	the cleaned file is not only dependent of the name, but also the content.
- The server should do its very best to delete files as soon as possible.

# Licenses

- mat2-web is under MIT
- The [raleway](https://github.com/impallari/Raleway/) font is under OFL1.1
- [normalize.css](https://github.com/necolas/normalize.css/) is under MIT
- [skeleton](http://getskeleton.com/) is under MIT
