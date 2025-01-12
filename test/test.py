import base64
import unittest
import tempfile
import shutil
import io
import os

from unittest.mock import patch
from flask_testing import TestCase

import main


class Mat2WebTestCase(TestCase):
    def create_app(self):
        os.environ.setdefault('MAT2_ALLOW_ORIGIN_WHITELIST', 'origin1.gnu origin2.gnu')
        self.upload_folder = tempfile.mkdtemp()
        app = main.create_app(
            test_config={
                'TESTING': True,
                'UPLOAD_FOLDER': self.upload_folder
            }
        )
        return app

    def tearDown(self):
        shutil.rmtree(self.upload_folder)

    def test_get_root(self):
        rv = self.client.get('/')
        self.assertIn(b'mat2-web', rv.data)

    def test_check_mimetypes(self):
        rv = self.client.get('/')
        self.assertIn(b'.torrent', rv.data)
        self.assertIn(b'.ods', rv.data)

    def test_get_download_dangerous_file(self):
        rv = self.client.get('/download/1337/aabb/\..\filename')
        self.assertEqual(rv.status_code, 302)

    def test_get_download_without_key_file(self):
        rv = self.client.get('/download/non_existant')
        self.assertEqual(rv.status_code, 404)

    def test_get_download_nonexistant_file(self):
        rv = self.client.get('/download/1337/aabb/non_existant')
        self.assertEqual(rv.status_code, 302)

    def test_get_upload_without_file(self):
        rv = self.client.post('/')
        self.assertEqual(rv.status_code, 302)

    def test_get_upload_empty_file(self):
        rv = self.client.post('/',
                data=dict(
                    file=(io.BytesIO(b""), 'test.pdf'),
                    ), follow_redirects=False)
        self.assertEqual(rv.status_code, 302)

    def test_get_upload_bad_file_type(self):
        rv = self.client.post('/',
                data=dict(
                    file=(io.BytesIO(b"1,2,3 \n 4,5,6"), 'test.csv'),
                    ), follow_redirects=False)
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'The type text/csv could not be cleaned', rv.data)

    def test_get_upload_empty_file_redir(self):
        rv = self.client.post('/',
                data=dict(
                    file=(io.BytesIO(b""), 'test.pdf'),
                    ), follow_redirects=True)
        self.assertIn(b'The filetype is not supported',
                rv.data)
        self.assertEqual(rv.status_code, 200)

    def test_get_upload_no_selected_file(self):
        rv = self.client.post('/',
                           data=dict(
                               file=(io.BytesIO(b""), ''),
                           ), follow_redirects=True)
        self.assertIn(b'No selected file',
                      rv.data)
        self.assertEqual(rv.status_code, 200)

    def test_failed_cleaning(self):
        zip_file_bytes = base64.b64decode(
            'UEsDBBQACAAIAPicPE8AAAAAAAAAAAAAAAAXACAAZmFpbGluZy5ub3Qtd29ya2luZy1le'
            'HRVVA0AB+Saj13kmo9d5JqPXXV4CwABBOkDAAAE6QMAAAMAUEsHCAAAAAACAAAAAAAAAFBL'
            'AwQUAAgACAD6nDxPAAAAAAAAAAAAAAAACQAgAHRlc3QuanNvblVUDQAH6JqPXeiaj13omo9d'
            'dXgLAAEE6QMAAATpAwAAAwBQSwcIAAAAAAIAAAAAAAAAUEsBAhQDFAAIAAgA+Jw8TwAAAAACA'
            'AAAAAAAABcAIAAAAAAAAAAAAKSBAAAAAGZhaWxpbmcubm90LXdvcmtpbmctZXh0VVQNAAfkmo9'
            'd5JqPXeSaj111eAsAAQTpAwAABOkDAABQSwECFAMUAAgACAD6nDxPAAAAAAIAAAAAAAAACQAgA'
            'AAAAAAAAAAApIFnAAAAdGVzdC5qc29uVVQNAAfomo9d6JqPXeiaj111eAsAAQTpAwAABOkDAAB'
            'QSwUGAAAAAAIAAgC8AAAAwAAAAAAA'
        )
        rv = self.client.post('/',
                           data=dict(
                               file=(io.BytesIO(zip_file_bytes), 'test.zip'),
                           ), follow_redirects=True)
        self.assertIn(b'Unable to clean', rv.data)
        self.assertEqual(rv.status_code, 200)

    def test_get_upload_no_file_name(self):
        rv = self.client.post('/',
                data=dict(
                    file=(io.BytesIO(b"aaa")),
                    ), follow_redirects=True)
        self.assertIn(b'No file part', rv.data)
        self.assertEqual(rv.status_code, 200)

    def test_get_upload_harmless_file(self):
        rv = self.client.post(
            '/',
            data=dict(
                file=(io.BytesIO(b"Some text"), 'test.txt'),
            ),
            follow_redirects=True
        )
        download_uri = self.get_context_variable('download_uri')
        self.assertIn('/test.cleaned.txt', download_uri)
        self.assertEqual(rv.status_code, 200)
        self.assertNotIn('Access-Control-Allow-Origin', rv.headers)

        rv = self.client.get(download_uri)
        self.assertEqual(rv.status_code, 200)

        rv = self.client.get(download_uri)
        self.assertEqual(rv.status_code, 302)

    def test_upload_wrong_hash_or_secret(self):
        rv = self.client.post(
            '/',
            data=dict(
                file=(io.BytesIO(b"Some text"), 'test.txt'),
            ),
            follow_redirects=True
        )

        download_uri = self.get_context_variable('download_uri')

        self.assertIn('/test.cleaned.txt', download_uri)
        self.assertIn('/download', download_uri)
        self.assertEqual(rv.status_code, 200)

        uri_parts = download_uri.split("/")
        self.assertEqual(len(uri_parts[2]), len(uri_parts[3]))
        self.assertEqual(64, len(uri_parts[2]))

        key_uri_parts = uri_parts
        key_uri_parts[2] = '70623619c'
        rv = self.client.get("/".join(key_uri_parts))
        self.assertEqual(rv.status_code, 302)

        key_uri_parts = uri_parts
        key_uri_parts[3] = '70623619c'
        rv = self.client.get("/".join(key_uri_parts))
        self.assertEqual(rv.status_code, 302)

    @patch('matweb.file_removal_scheduler.random.randint')
    def test_upload_leftover(self, randint_mock):
        randint_mock.return_value = 0
        os.environ['MAT2_MAX_FILE_AGE_FOR_REMOVAL'] = '0'
        app = main.create_app()
        self.upload_folder = tempfile.mkdtemp()
        app.config.update(
            TESTING=True,
            UPLOAD_FOLDER=self.upload_folder
        )
        app = app.test_client()

        request = self.client.post('/',
                           data=dict(
                               file=(io.BytesIO(b"Some text"), 'test.txt'),
                           ), follow_redirects=True)
        self.assertEqual(request.status_code, 200)

        request = app.get(self.get_context_variable('download_uri'))
        self.assertEqual(302, request.status_code)
        os.environ['MAT2_MAX_FILE_AGE_FOR_REMOVAL'] = str(15*60)

    def test_info_page(self):
        rv = self.client.get('/info')
        self.assertIn(b'What are metadata?', rv.data)
        self.assertIn(b'.jpg', rv.data)
        self.assertIn(b'.mp2', rv.data)
        self.assertEqual(rv.status_code, 200)

    def test_get_upload_no_ascii_no_ext_input(self):
        rv = self.client.post(
            '/',
            data=dict(
                file=(io.BytesIO(b"a"), '﷽.txt'),
            ),
            follow_redirects=True
        )
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'.cleaned.txt', rv.data)

    def test_get_upload_no_ascii_stem_input(self):
        pdfBytes = b"%PDF-1.\n 1 0 obj<</Pages 2 0 R>>endobj\n2 0 obj<</Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Parent 2 0 R>>endobj\ntrailer <</Root 1 0 R>>"
        rv = self.client.post(
            '/',
            data=dict(
                file=(io.BytesIO(pdfBytes), '한국어.pdf'),
            ),
            follow_redirects=True
        )
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'.cleaned.pdf', rv.data)

if __name__ == '__main__':
    unittest.main()

