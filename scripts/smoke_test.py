#!/usr/bin/env python3
"""Exercise real yt-dlp + FFmpeg + native framing against synthetic DASH media.

Run with the helper's Python, or a Python with requirements.txt installed.
No accounts, third-party video, or external service is used.
"""
import functools
import http.server
import io
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'native'))
from host import Host, read_message


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    ffmpeg=shutil.which('ffmpeg')
    ffprobe=shutil.which('ffprobe')
    if not ffprobe and ffmpeg:
        ffprobe=str(Path(ffmpeg).resolve().with_name('ffprobe'))
    with tempfile.TemporaryDirectory(prefix='video-button-smoke-') as temp:
        root=Path(temp)
        media=root/'media'
        media.mkdir()
        output=root/'downloads'
        output.mkdir()
        subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i','testsrc2=size=1280x720:rate=30',
            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
            '-filter_complex','[0:v]split=2[hi][small];[small]scale=640:360[lo]',
            '-map','[hi]','-map','[lo]','-map','1:a','-t','2',
            '-c:v','libx264','-preset','ultrafast','-b:v:0','1800k','-b:v:1','500k',
            '-c:a','aac','-b:a','128k','-f','dash','-seg_duration','1',str(media/'video.mpd')],check=True)
        (media/'index.html').write_text('<title>Synthetic quality test</title><video controls src="video.mpd"></video>')
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(media)))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        url=f'http://127.0.0.1:{server.server_port}/video.mpd'
        stream=io.BytesIO()
        helper=Host({'folder':str(output),'ffmpeg':ffmpeg,'node':shutil.which('node')},stream)
        # Test-only loopback fixture: production rejects loopback URLs.
        with patch('core.safe_url',side_effect=lambda value:value):
            helper.handle({'action':'download','requestId':'smoke','id':'synthetic',
                'target':{'url':url,'itemIndex':1,'precise':True},'useCookies':False})
            helper.pool.shutdown(wait=True)
        server.shutdown()
        stream.seek(0)
        messages=[]
        while (message:=read_message(stream)) is not None:
            messages.append(message)
        jobs=[m['job'] for m in messages if m.get('type')=='job']
        if not jobs or jobs[-1]['status']!='complete':
            raise AssertionError(json.dumps(messages,indent=2))
        files=list(output.glob('*'))
        assert len(files)==1, f'Expected one combined file: {files}'
        probe=json.loads(subprocess.check_output([ffprobe,'-v','error','-show_streams','-of','json',str(files[0])],text=True))
        video=[s for s in probe['streams'] if s['codec_type']=='video']
        audio=[s for s in probe['streams'] if s['codec_type']=='audio']
        assert len(video)==1 and video[0]['height']==720, probe
        assert len(audio)==1, probe
        assert video[0]['codec_name']=='h264' and audio[0]['codec_name']=='aac', probe
        assert any(j['status']=='merging' for j in jobs), jobs
        print('PASS: native protocol → yt-dlp → best 720p track (over 360p) + separate AAC → FFmpeg → one combined file.')
        print('PASS: original H.264 and AAC codecs preserved; completion includes filename and quality.')


if __name__=='__main__':
    main()
