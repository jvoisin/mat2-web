import json
import os
import shutil
import tempfile
import unittest
import zipfile
import io

from unittest.mock import patch

from openapi_spec_validator import validate_spec
from six import BytesIO

import main


class Mat2APITestCase(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault('MAT2_ALLOW_ORIGIN_WHITELIST', 'origin1.gnu origin2.gnu')
        self.upload_folder = tempfile.mkdtemp()
        app = main.create_app(
            test_config={
                'TESTING': True,
                'UPLOAD_FOLDER': self.upload_folder
            }
        )

        self.app = app.test_client()

    def tearDown(self):
        shutil.rmtree(self.upload_folder)
        if os.environ.get('MAT2_ALLOW_ORIGIN_WHITELIST'):
            del os.environ['MAT2_ALLOW_ORIGIN_WHITELIST']

    def test_api_upload_valid(self):
        request = self.app.post(
            '/api/upload',
            data='{"file_name": "test_name.jpg", '
                 '"file": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8'
                 'UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDi6KKK+ZP3E//Z"}',
            headers={'content-type': 'application/json'}
        )
        self.assertEqual(request.headers['Content-Type'], 'application/json')
        self.assertEqual(request.headers['Access-Control-Allow-Origin'], 'origin1.gnu')
        self.assertEqual(request.status_code, 201)

        data = request.get_json()
        self.assertEqual(data['inactive_after_sec'], 15 * 60)
        self.assertEqual(data['output_filename'], 'test_name.cleaned.jpg')
        self.assertEqual(data['mime'], 'image/jpeg')
        self.assertEqual(len(data['secret']), 64)
        self.assertEqual(len(data['key']), 64)
        self.assertNotEqual(data['key'], data['secret'])
        self.assertTrue('http://localhost/api/download/' in data['download_link'])
        self.assertTrue('test_name.cleaned.jpg' in data['download_link'])

    def test_api_upload_serializes_binary_metadata(self):
        with patch('matweb.rest_api.utils.get_file_parser') as get_file_parser, \
                patch('matweb.utils.parser_factory.get_parser') as get_output_parser:
            parser = get_file_parser.return_value[0]
            get_file_parser.return_value = (parser, 'application/octet-stream')
            get_output_parser.return_value = (parser, 'application/octet-stream')
            parser.remove_all.return_value = True
            parser.get_meta.return_value = {'binary': b'metadata'}
            parser.output_filename = os.path.join(self.upload_folder, 'test.cleaned.bin')
            with open(parser.output_filename, 'wb') as output_file:
                output_file.write(b'cleaned')

            request = self.app.post(
                '/api/upload',
                data='{"file_name": "test.bin", "file": "dGVzdA=="}',
                headers={'content-type': 'application/json'},
            )

        self.assertEqual(request.status_code, 201)
        self.assertEqual(request.get_json()['meta']['binary'], 'metadata')

    def test_api_upload_missing_params(self):
        request = self.app.post('/api/upload',
                                data='{"file_name": "test_name.jpg"}',
                                headers={'content-type': 'application/json'}
                                )
        self.assertEqual(request.headers['Content-Type'], 'application/json')

        self.assertEqual(request.status_code, 400)
        error = request.get_json()['message']
        self.assertEqual(error['file'], 'Post parameter is not specified: file')

        request = self.app.post('/api/upload',
                                data='{"file_name": "test_name.jpg", "file": "invalid base46 string"}',
                                headers={'content-type': 'application/json'}
                                )
        self.assertEqual(request.headers['Content-Type'], 'application/json')

        self.assertEqual(request.status_code, 400)
        error = request.get_json()['message']
        self.assertEqual(error, 'Failed decoding file')

    def test_api_not_supported(self):
        request = self.app.post('/api/upload',
                                data='{"file_name": "test_name.pdf", '
                                     '"file": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8'
                                     'UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDi6KKK+ZP3E//Z"}',
                                headers={'content-type': 'application/json'}
                                )
        self.assertEqual(request.headers['Content-Type'], 'application/json')
        self.assertEqual(request.status_code, 415)

        error = request.get_json()['message']
        self.assertEqual(error, 'The filetype is not supported')

    def test_api_not_supported_extension(self):
        request = self.app.post('/api/upload',
                                data='{"file_name": "test_name.csv", '
                                     '"file": "MSwyLDMKNCw1LDY="}',
                                headers={'content-type': 'application/json'}
                                )
        self.assertEqual(request.headers['Content-Type'], 'application/json')
        self.assertEqual(request.status_code, 415)

        error = request.get_json()['message']
        self.assertEqual(error, 'The filetype is not supported')

    def test_api_supported_extensions(self):
        rv = self.app.get('/api/extension')
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.headers['Content-Type'], 'application/json')
        self.assertEqual(rv.headers['Access-Control-Allow-Origin'], 'origin1.gnu')

        extensions = json.loads(rv.data.decode('utf-8'))
        self.assertIn('.pot', extensions)
        self.assertIn('.jpg', extensions)
        self.assertIn('.png', extensions)
        self.assertIn('.zip', extensions)

    def test_api_cors_not_set(self):
        del os.environ['MAT2_ALLOW_ORIGIN_WHITELIST']
        app = main.create_app()
        app.config.update(
            TESTING=True
        )
        app = app.test_client()

        rv = app.get('/api/extension')
        self.assertEqual(rv.headers['Access-Control-Allow-Origin'], '*')

    def test_api_cors(self):
        rv = self.app.get('/api/extension')
        self.assertEqual(rv.headers['Access-Control-Allow-Origin'], 'origin1.gnu')

        rv = self.app.get('/api/extension', headers={'Origin': 'origin2.gnu'})
        self.assertEqual(rv.headers['Access-Control-Allow-Origin'], 'origin2.gnu')

        rv = self.app.get('/api/extension', headers={'Origin': 'origin1.gnu'})
        self.assertEqual(rv.headers['Access-Control-Allow-Origin'], 'origin1.gnu')

    def test_api_cleaning_failed(self):
        request = self.app.post('/api/upload',
                                data='{"file_name": "test_name.zip", '
                                     '"file": "UEsDBBQACAAIAPicPE8AAAAAAAAAAAAAAAAXACAAZmFpbGluZy5ub3Qt'
                                     'd29ya2luZy1leHRVVA0AB+Saj13kmo9d5JqPXXV4CwABBOkDAAAE6QMAAAMAUEsHCAAA'
                                     'AAACAAAAAAAAAFBLAwQUAAgACAD6nDxPAAAAAAAAAAAAAAAACQAgAHRlc3QuanNvblVUD'
                                     'QAH6JqPXeiaj13omo9ddXgLAAEE6QMAAATpAwAAAwBQSwcIAAAAAAIAAAAAAAAAUEsBAhQD'
                                     'FAAIAAgA+Jw8TwAAAAACAAAAAAAAABcAIAAAAAAAAAAAAKSBAAAAAGZhaWxpbmcubm90LXd'
                                     'vcmtpbmctZXh0VVQNAAfkmo9d5JqPXeSaj111eAsAAQTpAwAABOkDAABQSwECFAMUAAgACAD6'
                                     'nDxPAAAAAAIAAAAAAAAACQAgAAAAAAAAAAAApIFnAAAAdGVzdC5qc29uVVQNAAfomo9d6JqPXe'
                                     'iaj111eAsAAQTpAwAABOkDAABQSwUGAAAAAAIAAgC8AAAAwAAAAAAA"}',
                                headers={'content-type': 'application/json'}
                                )
        error = request.get_json()['message']
        self.assertEqual(request.status_code, 400)
        self.assertEqual(error, 'Unable to clean application/zip')

    def test_api_download(self):
        request = self.app.post('/api/upload',
                                data='{"file_name": "test_name.jpg", '
                                     '"file": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8'
                                     'UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDi6KKK+ZP3E//Z"}',
                                headers={'content-type': 'application/json'}
                                )
        print(request.get_json())
        self.assertEqual(request.status_code, 201)
        data = request.get_json()

        request = self.app.get('http://localhost/api/download/161/'
                               '81a541f9ebc0233d419d25ed39908b16f82be26a783f32d56c381559e84e6161/test name.cleaned.jpg')
        self.assertEqual(request.status_code, 400)
        error = request.get_json()['message']
        self.assertEqual(error, 'Insecure filename')

        request = self.app.get(data['download_link'].replace('test_name', 'wrong_test'))
        self.assertEqual(request.status_code, 404)
        error = request.get_json()['message']
        self.assertEqual(error, 'File not found')

        uri_parts = data['download_link'].split("/")
        self.assertEqual(len(uri_parts[5]), len(uri_parts[6]))
        self.assertEqual(64, len(uri_parts[5]))

        key_uri_parts = uri_parts
        key_uri_parts[5] = '70623619c'
        request = self.app.get("/".join(key_uri_parts))
        self.assertEqual(request.status_code, 400)

        error = request.get_json()['message']
        self.assertEqual(error, 'The file hash does not match')

        key_uri_parts = uri_parts
        key_uri_parts[6] = '70623619c'
        request = self.app.get("/".join(key_uri_parts))
        self.assertEqual(request.status_code, 400)
        error = request.get_json()['message']
        self.assertEqual(error, 'The file hash does not match')

        request = self.app.head(data['download_link'])
        self.assertEqual(request.status_code, 200)
        self.assertIn('Content-Length', request.headers)
        content_length = int(request.headers['Content-Length'])
        self.assertGreater(content_length, 0)

        request = self.app.get(data['download_link'])
        self.assertEqual(request.status_code, 200)
        self.assertEqual(len(request.data), content_length)
        self.assertIn('attachment; filename=test_name.cleaned.jpg', request.headers['Content-Disposition'])

        request = self.app.get(data['download_link'])
        self.assertEqual(request.status_code, 404)

    def test_api_bulk_download(self):
        request = self.app.post('/api/upload',
                                data='{"file_name": "test_name.jpg", '
                                     '"file": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8'
                                     'UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDi6KKK+ZP3E//Z"}',
                                headers={'content-type': 'application/json'}
                                )
        upload_one = request.get_json()
        self.assertEqual(request.status_code, 201)

        request = self.app.post('/api/upload',
                                data='{"file_name": "test_name_two.jpg", '
                                     '"file": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8'
                                     'UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDi6KKK+ZP3E//Z"}',
                                headers={'content-type': 'application/json'}
                                )
        self.assertEqual(request.status_code, 201)
        upload_two = request.get_json()

        post_body = {
            u'download_list': [
                {
                    u'file_name': upload_one['output_filename'],
                    u'key': upload_one['key'],
                    u'secret': upload_one['secret']
                },
                {
                    u'file_name': upload_two['output_filename'],
                    u'key': upload_two['key'],
                    u'secret': upload_two['secret']
                }
            ]
        }
        request = self.app.post('/api/download/bulk',
                                data=json.dumps(post_body),
                                headers={'content-type': 'application/json'}
                                )

        response = request.get_json()
        self.assertEqual(request.status_code, 201)

        self.assertIn(
            "http://localhost/api/download/",
            response['download_link']
        )
        self.assertIn(
            ".cleaned.zip",
            response['download_link']
        )

        self.assertIn('files.', response['output_filename'])
        self.assertIn('cleaned.zip', response['output_filename'])
        self.assertEqual(15 * 60, response['inactive_after_sec'])
        self.assertIn(response['mime'], 'application/zip')
        self.assertEqual(response['meta_after'], {})

        request = self.app.head(response['download_link'])
        self.assertEqual(request.status_code, 200)
        self.assertTrue(request.headers['Content-Length'])

        request = self.app.get(response['download_link'])
        self.assertIn('attachment; filename=files.', request.headers['Content-Disposition'])
        zip_response = zipfile.ZipFile(BytesIO(request.data))
        self.assertEqual(2, len(zip_response.namelist()))
        for name in zip_response.namelist():
            self.assertIn('.cleaned.jpg', name)
        self.assertEqual(request.status_code, 200)

        request = self.app.get(response['download_link'])
        self.assertEqual(request.status_code, 404)

        request = self.app.get(upload_one['download_link'])
        self.assertEqual(request.status_code, 404)

        request = self.app.get(upload_two['download_link'])
        self.assertEqual(request.status_code, 404)

    def test_api_bulk_empty_body(self):
        request = self.app.post(
            '/api/download/bulk',
        )
        self.assertEqual(415, request.status_code)
        error_message = request.get_json()['message']
        self.assertEqual("Did not attempt to load JSON data because the request Content-Type was not 'application/json'.", error_message)

    def test_api_bulk_download_validation(self):
        post_body = {
            u'download_list': [
                {
                    u'file_name': 'invalid_file_name',
                    u'key': 'invalid_key',
                    u'secret': 'invalid_secret'
                }
            ]
        }
        request = self.app.post('/api/download/bulk',
                                data=json.dumps(post_body),
                                headers={'content-type': 'application/json'}
                                )

        response = request.get_json()
        self.assertEqual(response['message']['download_list'][0], 'min length is 2')
        self.assertEqual(request.status_code, 400)

        post_body = {
            u'download_list': [{}, {}]
        }
        request = self.app.post('/api/download/bulk',
                                data=json.dumps(post_body),
                                headers={'content-type': 'application/json'}
                                )

        response = request.get_json()
        self.assertEqual(response['message']['download_list'][0]['0'][0]['file_name'][0], 'required field')
        self.assertEqual(response['message']['download_list'][0]['0'][0]['key'][0], 'required field')
        self.assertEqual(request.status_code, 400)

        post_body = {
            u'download_list': [
                {
                    u'file_name': 'test.jpg',
                    u'key': 'key'
                },
                {
                    u'file_name': 'test.jpg',
                    u'key': 'key'
                },
                {
                    u'file_name': 'test.jpg',
                    u'key': 'key'
                },
                {
                    u'file_name': 'test.jpg',
                    u'key': 'key'
                },
                {
                    u'file_name': 'test.jpg',
                    u'key': 'key'
                },
                {
                    u'file_name': 'test.jpg',
                    u'key': 'key'
                },
                {
                    u'file_name': 'test.jpg',
                    u'key': 'key'
                },
                {
                    u'file_name': 'test.jpg',
                    u'key': 'key'
                },
                {
                    u'file_name': 'test.jpg',
                    u'key': 'key'
                },
                {
                    u'file_name': 'test.jpg',
                    u'key': 'key'
                },
                {
                    u'file_name': 'test.jpg',
                    u'key': 'key'
                }
            ]
        }
        request = self.app.post('/api/download/bulk',
                                data=json.dumps(post_body),
                                headers={'content-type': 'application/json'}
                                )

        response = request.get_json()
        self.assertEqual(response['message']['download_list'][0], 'max length is 10')
        self.assertEqual(request.status_code, 400)

        post_body = {
            u'download_list': [
                {
                    u'file_name': 'invalid_file_name1',
                    u'key': 'invalid_key1',
                    u'secret': 'invalid_secret1'
                },
                {
                    u'file_name': 'invalid_file_name2',
                    u'key': 'invalid_key2',
                    u'secret': 'invalid_secret2'
                }
            ]
        }
        request = self.app.post('/api/download/bulk',
                                data=json.dumps(post_body),
                                headers={'content-type': 'application/json'}
                                )
        response = request.get_json()
        self.assertEqual('File not found', response['message'])

    @patch('matweb.file_removal_scheduler.random.randint')
    def test_api_upload_leftover(self, randint_mock):
        os.environ['MAT2_MAX_FILE_AGE_FOR_REMOVAL'] = '0'
        self.upload_folder = tempfile.mkdtemp()
        app = main.create_app(
            test_config={
                'TESTING': True,
                'UPLOAD_FOLDER': self.upload_folder
            }
        )
        app = app.test_client()
        randint_mock.return_value = 1
        self.upload_download_test_jpg_and_assert_response_code(app, 200)
        randint_mock.return_value = 0
        self.upload_download_test_jpg_and_assert_response_code(app, 404)

        os.environ['MAT2_MAX_FILE_AGE_FOR_REMOVAL'] = str(15 * 60)

    def upload_download_test_jpg_and_assert_response_code(self, app, code):
        request = app.post('/api/upload',
                           data='{"file_name": "test_name.jpg", '
                                '"file": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8'
                                'UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDi6KKK+ZP3E//Z"}',
                           headers={'content-type': 'application/json'}
                           )
        download_link = request.get_json()['download_link']
        request = app.get(download_link)
        self.assertEqual(code, request.status_code)

    def test_download_naughty_input(self):
        request = self.app.get(
            '/api/download/%F2%8C%BF%BD%F1%AE%98%A3%E4%B7%B8%F2%9B%94%BE%F2%A7%8B%83%F1%B1%80%9F%F3%AA%89%A6/1p/str'
        )
        error_message = request.get_json()['message']
        self.assertEqual(404, request.status_code)
        self.assertEqual("File not found", error_message)

    def test_download_bulk_naughty_input(self):
        request = self.app.post(
            '/api/download/bulk',
            data='\"\'\'\'&type %SYSTEMROOT%\\\\win.ini\"',
            headers={'content-type': 'application/json'}
        )
        error_message = request.get_json()['message']
        self.assertEqual(400, request.status_code)
        self.assertEqual("Invalid Post Body", error_message)

    def test_upload_naughty_input(self):
        request = self.app.post('/api/upload',
                           data='{"file_name": "\\\\", '
                                '"file": "\\\\"}',
                           headers={'content-type': 'application/json'}
                           )
        error_message = request.get_json()['message']
        self.assertEqual(415, request.status_code)
        self.assertEqual("The filetype is not supported", error_message)

        request = self.app.post('/api/upload',
                                data='{"file_name": "﷽", '
                                     '"file": "﷽"}',
                                headers={'content-type': 'application/json'}
                                )
        error_message = request.get_json()['message']
        self.assertEqual(400, request.status_code)
        self.assertEqual("Failed decoding file", error_message)

        request = self.app.post('/api/upload',
                                data="\"\'\'\'&&cat$z $z/etc$z/passwdu0000\"",
                                headers={'content-type': 'application/json'}
                                )
        error_message = request.get_json()['message']
        self.assertEqual(400, request.status_code)
        self.assertEqual("Failed parsing body", error_message)

    def test_valid_opena_api_spec(self):
        spec = self.app.get('apispec_1.json').get_json()
        # Test workaround due to https://github.com/flasgger/flasgger/issues/374
        validate_spec(spec)

    def test_remove_metadata(self):
        r = self.app.post(
            '/api/remove_metadata',
            data=dict(
                file=(io.BytesIO(b""), 'test.txt'),
            ),
            follow_redirects=False
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Content-Disposition'], 'attachment; filename=test.cleaned.txt')
        self.assertEqual(r.headers['Content-Type'], 'text/plain; charset=utf-8')
        self.assertEqual(r.data, b'')

    def test_remove_metadata_not_supported_extension(self):
        r = self.app.post(
            '/api/remove_metadata',
            data=dict(
                file=(io.BytesIO(b"1,2,3 \n 4,5,6"), 'test.csv'),
            ),
            follow_redirects=False
        )
        self.assertEqual(
            r.get_json()['message'],
            'The filetype is not supported'
        )
        self.assertEqual(r.status_code, 415)

    def test_remove_metdata_validation(self):
        r = self.app.post(
            '/api/remove_metadata',
            data=dict(
                fileNotExisting=(io.BytesIO(b""), 'test.random'),
            ),
            follow_redirects=False
        )
        self.assertEqual(
            r.get_json()['message'],
            'File part missing: Multipart filename and non-chunked-transfer-encoding required'
        )
        self.assertEqual(r.status_code, 400)

        r = self.app.post(
            '/api/remove_metadata',
            data=dict(
                file=(io.BytesIO(b""), ''),
            ),
            follow_redirects=False
        )
        self.assertEqual(r.get_json()['message'], 'No selected `file`')
        self.assertEqual(r.status_code, 400)

        r = self.app.post(
            '/api/remove_metadata',
            data=dict(
                file=(io.BytesIO(b""), '../../'),
            ),
            follow_redirects=False
        )
        self.assertEqual(r.get_json()['message'], 'The filetype is not supported')
        self.assertEqual(r.status_code, 415)

        r = self.app.post(
            '/api/remove_metadata',
            data=dict(
                file=(io.BytesIO(b""), 'test.random'),
            ),
            follow_redirects=False
        )
        self.assertEqual(r.get_json()['message'], 'The filetype is not supported')
        self.assertEqual(r.status_code, 415)


if __name__ == '__main__':
    unittest.main()
