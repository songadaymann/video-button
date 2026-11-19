import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'native'))
from core import make_options, safe_error, safe_url
from host import Host, MAX_MESSAGE, read_message


class NativeTests(unittest.TestCase):
    def test_untrusted_urls_cannot_be_local_files_or_commands(self):
        for url in ['file:///etc/passwd', 'javascript:alert(1)', 'https://user:secret@example.org/video',
                    'http://127.0.0.1/a', 'http://[::1]/a', 'http://192.168.0.1/a', 'http://localhost/a',
                    'http://printer.local/a', 'https://example.org/\n--exec=evil']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                safe_url(url)
        self.assertEqual(safe_url('https://example.org/a?quality=best'), 'https://example.org/a?quality=best')

    def test_protocol_rejects_oversized_truncated_and_non_object_messages(self):
        for body in [struct.pack('=I', MAX_MESSAGE+1), struct.pack('=I', 10)+b'{}', struct.pack('=I',2)+b'[]']:
            with self.assertRaises(ValueError):
                read_message(io.BytesIO(body))
        data=json.dumps({'action':'hello'}).encode()
        self.assertEqual(read_message(io.BytesIO(struct.pack('=I',len(data))+data)), {'action':'hello'})

    def test_quality_is_not_capped_or_reencoded_and_cookies_are_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            config={'folder':folder,'ffmpeg':'/bin/ffmpeg','node':'/bin/node'}
            args=(config, {'itemIndex':2}, False, '', lambda *_:None, lambda *_:None, lambda *_:None, None)
            options=make_options(*args)
            self.assertEqual(options['format'], 'bestvideo*+bestaudio/best')
            self.assertEqual(options['playlist_items'], '2')
            self.assertNotIn('cookiesfrombrowser', options)
            self.assertNotIn('recodevideo', options)
            self.assertNotIn('merge_output_format', options)
            self.assertEqual(options['format_sort'], ['res','fps'])
            options=make_options(config, {'itemIndex':1}, True, 'Profile 1', None,None,None,None)
            self.assertEqual(options['cookiesfrombrowser'], ('chrome','Profile 1',None,None))

    def test_browser_cannot_choose_arbitrary_profile_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            for profile in ['../../private', '/Users/other', 'Default; echo bad']:
                with self.assertRaises(ValueError):
                    make_options({'folder':folder}, {}, True, profile, None,None,None,None)

    def test_errors_do_not_expose_signed_urls(self):
        message=safe_error('ERROR: Failed https://cdn.example.org/a?token=private at /Users/test/private/file')
        self.assertNotIn('token',message)
        self.assertNotIn('/Users/',message)

    def test_helper_rejects_unknown_actions_without_running_processes(self):
        helper=Host({},io.BytesIO())
        try:
            with self.assertRaises(ValueError):helper.handle({'action':'exec','command':'echo bad'})
        finally:helper.close()


if __name__=='__main__':unittest.main()
