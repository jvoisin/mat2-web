import hmac
import os
import hashlib
import mimetypes as mtype
import pathlib
import uuid
from typing import Tuple

from flask_restful import abort, current_app
from libmat2 import parser_factory
from werkzeug.utils import secure_filename


def get_allow_origin_header_value():
    return os.environ.get('MAT2_ALLOW_ORIGIN_WHITELIST', '*').split(" ")


def hash_file(filepath: str, secret: str) -> str:
    """
    The goal of the hmac is to ONLY make the hashes unpredictable
    :param filepath: Path of the file
    :param secret: a server side generated secret
    :return: digest, secret
    """
    mac = hmac.new(secret.encode(), None, hashlib.sha256)
    with open(filepath, 'rb') as f:
        while True:
            data = f.read(65536)  # read the file by chunk of 64k
            if not data:
                break
            mac.update(data)
    return mac.hexdigest()


def check_upload_folder(upload_folder):
    if not os.path.exists(upload_folder):
        current_app.logger.info('Upload folder does not exist - creating it')
        os.mkdir(upload_folder)


def return_file_created_response(
        inactive_after_sec: int,
        output_filename: str,
        mime: str,
        key: str,
        secret: str,
        meta: list,
        meta_after: list,
        download_link: str
) -> dict:
    return {
        'inactive_after_sec': inactive_after_sec,
        'output_filename': output_filename,
        'mime': mime,
        'key': key,
        'secret': secret,
        'meta': meta,
        'meta_after': meta_after,
        'download_link': download_link
    }


def get_supported_extensions():
    extensions = set()
    for parser in parser_factory._get_parsers():
        for m in parser.mimetypes:
            extensions |= set(mtype.guess_all_extensions(m, strict=False))
    # since `guess_extension` might return `None`, we need to filter it out
    return sorted(filter(None, extensions))


def save_file(file, upload_folder):
    path = pathlib.Path(file.filename)
    extension = path.suffix
    stem = path.stem

    filename = secure_filename(stem)
    if not filename:
        filename = str(uuid.uuid4())

    if extension:
        filename = str(pathlib.Path(filename).with_suffix(extension))
    filepath = os.path.join(upload_folder, filename)
    file.save(os.path.join(filepath))
    return filename, filepath


def get_file_parser(filepath: str):
    parser, mime = parser_factory.get_parser(filepath)
    return parser, mime


def cleanup(parser, filepath, upload_folder):
    output_filename = os.path.basename(parser.output_filename)
    parser, _ = parser_factory.get_parser(parser.output_filename)
    meta_after = parser.get_meta()
    os.remove(filepath)
    secret = os.urandom(32).hex()
    key = hash_file(os.path.join(upload_folder, output_filename), secret)
    return key, secret, meta_after, output_filename


def get_file_paths(filename, upload_folder):
    filepath = secure_filename(filename)

    complete_path = os.path.join(upload_folder, filepath)
    return complete_path, filepath


def is_valid_api_download_file(filename: str, key: str, secret: str, upload_folder: str) -> Tuple[str, str]:
    if filename != secure_filename(filename):
        current_app.logger.error('Insecure filename %s', filename)
        abort(400, message='Insecure filename')

    complete_path, filepath = get_file_paths(filename, upload_folder)

    if not os.path.exists(complete_path):
        current_app.logger.error('File not found')
        abort(404, message='File not found')

    if hmac.compare_digest(hash_file(complete_path, secret), key) is False:
        current_app.logger.error('The file hash does not match')
        abort(400, message='The file hash does not match')
    return complete_path, filepath


def get_file_removal_max_age_sec() -> int:
    return int(os.environ.get('MAT2_MAX_FILE_AGE_FOR_REMOVAL', 15 * 60))
