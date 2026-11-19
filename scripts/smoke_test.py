#!/usr/bin/env python3
"""Exercise real yt-dlp + FFmpeg + native framing against synthetic DASH media.

Run with the helper's Python, or a Python with requirements.txt installed.
No accounts, third-party video, or external service is used.
"""
import functools
import array
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


def native_download(config, url):
    stream=io.BytesIO()
    helper=Host(config,stream)
    # Test-only loopback fixture: production rejects loopback URLs.
    with patch('core.safe_url',side_effect=lambda value:value):
        helper.handle({'action':'download','requestId':'smoke','id':'synthetic',
            'target':{'url':url,'itemIndex':1,'precise':True},'useCookies':False})
        helper.pool.shutdown(wait=True)
    stream.seek(0)
    messages=[]
    while (message:=read_message(stream)) is not None:
        messages.append(message)
    return [m['job'] for m in messages if m.get('type')=='job']


def assert_sound(ffmpeg, path):
    samples=array.array('f',subprocess.check_output([ffmpeg,'-v','error','-i',str(path),
        '-map','0:a:0','-ac','1','-ar','8000','-t','1','-f','f32le','pipe:1']))
    assert samples and max(abs(s) for s in samples)>.01, f'No audible signal in {path}'


def assert_pair(config, jobs, folder, height, codec):
    if not jobs or jobs[-1]['status']!='complete':
        raise AssertionError(json.dumps(jobs,indent=2))
    files=list(folder.glob('*'))
    assert sorted(f.suffix for f in files)==['.mp3','.mp4'], files
    assert not list(folder.glob('.video-button-*')), 'Temporary source files were not cleaned up'
    mp4=folder/jobs[-1]['filename']
    mp3=folder/jobs[-1]['audioFilename']
    assert mp4.stem==mp3.stem
    probe=json.loads(subprocess.check_output([config['ffprobe'],'-v','error','-show_streams','-of','json',str(mp4)],text=True))
    video=[s for s in probe['streams'] if s['codec_type']=='video']
    audio=[s for s in probe['streams'] if s['codec_type']=='audio']
    assert len(video)==1 and video[0]['height']==height and video[0]['codec_name']==codec, probe
    assert len(audio)==1 and audio[0]['codec_name']=='aac', probe
    audio_probe=json.loads(subprocess.check_output([config['ffprobe'],'-v','error','-show_streams','-of','json',str(mp3)],text=True))
    assert len(audio_probe['streams'])==1 and audio_probe['streams'][0]['codec_name']=='mp3', audio_probe
    assert int(audio_probe['streams'][0]['bit_rate'])==320000, audio_probe
    assert_sound(config['ffmpeg'],mp4)
    assert_sound(config['ffmpeg'],mp3)
    assert any(j['status']=='exporting' for j in jobs), jobs


def main():
    ffmpeg=shutil.which('ffmpeg')
    ffprobe=shutil.which('ffprobe')
    if not ffprobe and ffmpeg:
        ffprobe=str(Path(ffmpeg).resolve().with_name('ffprobe'))
    with tempfile.TemporaryDirectory(prefix='video-button-smoke-') as temp:
        root=Path(temp)
        media=root/'media'
        media.mkdir()
        subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i','testsrc2=size=1280x720:rate=30',
            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
            '-filter_complex','[0:v]split=2[hi][small];[small]scale=640:360[lo]',
            '-map','[hi]','-map','[lo]','-map','1:a','-t','2',
            '-c:v','libx264','-preset','ultrafast','-b:v:0','1800k','-b:v:1','500k',
            '-c:a','aac','-b:a','128k','-f','dash','-seg_duration','1',str(media/'video.mpd')],check=True)
        (media/'index.html').write_text('<title>Synthetic quality test</title><video controls src="video.mpd"></video>')
        # WebM is often the highest-quality source. Preserve VP9 video while
        # converting its Opus audio to AAC for MP4, and separately to MP3.
        for codec, encoder in [('vp9','libvpx-vp9'),('vp8','libvpx')]:
            subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y',
                '-f','lavfi','-i','testsrc2=size=320x180:rate=24',
                '-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
                '-t','1','-c:v',encoder,'-deadline','realtime','-cpu-used','8',
                '-c:a','libopus',str(media/f'{codec}.webm')],check=True)
        subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(media/'vp9.webm'),
            '-map','0:v:0','-c:v','copy','-an',str(media/'silent.webm')],check=True)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(media)))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            for name,resource,height,codec in [('dash','video.mpd',720,'h264'),('webm-vp9','vp9.webm',180,'vp9'),('webm-vp8','vp8.webm',180,'h264')]:
                output=root/name
                output.mkdir()
                config={'folder':str(output),'ffmpeg':ffmpeg,'ffprobe':ffprobe,'node':shutil.which('node')}
                url=f'http://127.0.0.1:{server.server_port}/{resource}'
                jobs=native_download(config,url)
                assert_pair(config,jobs,output,height,codec)
                print(f'PASS: {name} → {height}p MP4 with audible AAC sound + audible 320 kbps MP3; only two finished files.')
                if name=='dash':
                    assert any(j['status']=='merging' for j in jobs),jobs
                    again=native_download(config,url)
                    assert again[-1]['status']=='complete',again
                    assert again[-1]['filename']!=jobs[-1]['filename']
                    assert len(list(output.glob('*.mp4')))==2 and len(list(output.glob('*.mp3')))==2
                    print('PASS: retry preserves existing files and saves a matching numbered MP4/MP3 pair.')
            silent=root/'silent'
            silent.mkdir()
            config={'folder':str(silent),'ffmpeg':ffmpeg,'ffprobe':ffprobe,'node':shutil.which('node')}
            jobs=native_download(config,f'http://127.0.0.1:{server.server_port}/silent.webm')
            assert jobs[-1]['status']=='error',jobs
            assert not list(silent.iterdir()),'Incomplete files were left behind'
            print('PASS: silent source does not claim to have saved sound; incomplete exports are cleaned up.')
        finally:
            server.shutdown()


if __name__=='__main__':
    main()
