"""Local UDP ingress stays responsive while a single worker owns Kokoro."""
import argparse
from collections import deque
import json
import logging
from pathlib import Path
import socket
import threading
import time

from dialogue import MAX_DATAGRAM, clean_dialogue, parse_frame

LOG = logging.getLogger('XISpeaks')


class KokoroBackend:
    def __init__(self, config):
        from RealtimeTTS import KokoroEngine, TextToAudioStream
        self.engine = KokoroEngine(voice=config['voice'], default_speed=config['speed'])
        self.stream = TextToAudioStream(self.engine, output_device_index=config.get('output_device_index'))

    def speak(self, dialogue, voice, cancelled):
        self.engine.set_voice(voice)
        if cancelled():
            return
        self.stream.feed(dialogue.text).play_async()
        while self.stream.is_playing():
            if cancelled():
                self.stream.stop()
                return
            time.sleep(0.03)
        if getattr(self.stream, 'error_flag', False):
            raise RuntimeError('RealtimeTTS reported a playback/synthesis failure; see its console log')

    def close(self):
        self.stream.stop()
        self.engine.shutdown()


class DryBackend:
    def __init__(self, config):
        pass

    def speak(self, dialogue, voice, cancelled):
        if not cancelled():
            LOG.info('[%s] %s: %s', voice, dialogue.speaker or 'Narrator', dialogue.text)

    def close(self):
        pass


DEFAULTS = dict(voice='af_heart', speed=1.0, voices={}, queue_limit=12,
                max_age_seconds=30.0, duplicate_seconds=1.0, output_device_index=None)


def load_config(path):
    config = dict(DEFAULTS)
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict) or set(data) - set(DEFAULTS):
            raise ValueError('Config must be an object containing only documented keys')
        config.update(data)
    if not isinstance(config['voice'], str) or not config['voice'].strip():
        raise ValueError('voice must be a non-empty Kokoro voice name')
    if not isinstance(config['voices'], dict) or not all(
        isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in config['voices'].items()
    ):
        raise ValueError('voices must map NPC names to voice names')
    for key, low, high in [('speed', 0.5, 2), ('queue_limit', 1, 100),
                           ('max_age_seconds', 1, 300), ('duplicate_seconds', 0, 10)]:
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not low <= value <= high:
            raise ValueError(f'{key} must be between {low} and {high}')
    if not isinstance(config['queue_limit'], int):
        raise ValueError('queue_limit must be an integer')
    device = config['output_device_index']
    if device is not None and (type(device) is not int or device < 0):
        raise ValueError('output_device_index must be null or a nonnegative integer')
    return config


class SpeechQueue:
    def __init__(self, config, backend_factory=KokoroBackend):
        self.config = config
        self.factory = backend_factory
        self.condition = threading.Condition()
        self.pending = deque()
        self.generation = 0
        self.closed = False
        self.state = 'starting'
        self.recent = None
        self.worker = threading.Thread(target=self._run, name='speech', daemon=True)
        self.worker.start()

    def submit(self, dialogue):
        now = time.monotonic()
        with self.condition:
            if self.state == 'error' or self.closed:
                return False
            if self.recent and self.recent[0] == dialogue and now - self.recent[1] < self.config['duplicate_seconds']:
                return False
            self.recent = (dialogue, now)
            if len(self.pending) >= self.config['queue_limit']:
                self.pending.popleft()
                LOG.warning('Queue full: dropped oldest waiting line')
            self.pending.append((self.generation, now, dialogue))
            self.condition.notify()
            return True

    def stop(self):
        with self.condition:
            self.generation += 1
            self.pending.clear()
            self.recent = None
            self.condition.notify_all()

    def status(self):
        with self.condition:
            return f'{self.state}; queued={len(self.pending)}'

    def close(self):
        with self.condition:
            self.closed = True
        self.stop()
        self.worker.join(timeout=5)

    def _run(self):
        backend = None
        try:
            backend = self.factory(self.config)
            with self.condition:
                self.state = 'ready'
            LOG.info('Speech engine ready')
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.closed or self.pending)
                    if self.closed:
                        break
                    generation, received, dialogue = self.pending.popleft()
                    if time.monotonic() - received > self.config['max_age_seconds']:
                        LOG.info('Dropped expired dialogue')
                        continue
                    self.state = 'speaking'
                def cancelled():
                    with self.condition:
                        return self.closed or generation != self.generation
                voice = self.config['voices'].get(dialogue.speaker, self.config['voice'])
                backend.speak(dialogue, voice, cancelled)
                with self.condition:
                    self.state = 'ready'
        except Exception:
            LOG.exception('Speech engine failed. Resolve the error and restart the companion.')
            with self.condition:
                self.state = 'error'
                self.pending.clear()
        finally:
            if backend:
                try:
                    backend.close()
                except Exception:
                    LOG.exception('Engine shutdown failed')


class Server:
    def __init__(self, speech, port):
        self.speech = speech
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Do not enable address reuse: two companions must not share the port.
        self.socket.bind(('127.0.0.1', port))
        self.socket.settimeout(0.2)
        self.seen = {}

    def handle(self, data, address):
        try:
            frame = parse_frame(data)
        except (ValueError, UnicodeError):
            return
        if frame.command == 'ping':
            self.socket.sendto(('XIS1\tOK\t' + self.speech.status()).encode('ascii'), address)
            return
        now = time.monotonic()
        key = (address, frame.identity)
        self.seen = {k: t for k, t in self.seen.items() if now - t < 30}
        if key in self.seen:
            return
        if len(self.seen) >= 2048:
            self.seen.clear()
        self.seen[key] = now
        if frame.command == 'stop':
            self.speech.stop()
        else:
            dialogue = clean_dialogue(frame.raw)
            # Mode 142 also carries system notices. Only named dialogue is
            # eligible, even if another local sender bypasses the Lua filter.
            if dialogue and (frame.mode != 142 or dialogue.speaker):
                self.speech.submit(dialogue)

    def run(self, stopped):
        LOG.info('Listening on 127.0.0.1:%d', self.socket.getsockname()[1])
        while not stopped.is_set():
            try:
                data, address = self.socket.recvfrom(MAX_DATAGRAM + 1)
            except socket.timeout:
                continue
            except OSError as exc:
                # Windows can report ICMP failures from clients closed during a reply.
                if getattr(exc, 'winerror', None) == 10054:
                    continue
                raise
            self.handle(data, address)

    def close(self):
        self.socket.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=49152)
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[1] / 'config.json')
    parser.add_argument('--dry-run', action='store_true', help='Print captured dialogue without loading a model')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be 1024..65535')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        config = load_config(args.config)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    speech = SpeechQueue(config, DryBackend if args.dry_run else KokoroBackend)
    server = None
    try:
        server = Server(speech, args.port)
        server.run(threading.Event())
    except KeyboardInterrupt:
        LOG.info('Stopping')
    finally:
        if server:
            server.close()
        speech.close()


if __name__ == '__main__':
    main()
