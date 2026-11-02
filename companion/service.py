"""Local UDP ingress stays responsive while a single worker owns Kokoro."""
import argparse
from collections import deque
import json
import logging
import re
import sqlite3
from pathlib import Path
import socket
import threading
import time

from dialogue import MAX_DATAGRAM, Dialogue, clean_dialogue, parse_frame
from registry import Registry, VOICES, number, apply_presets, validate_voice
from portable import app_root, resource_root, initialize_database

LOG = logging.getLogger('XISpeaks')


def speech_text(text):
    """Normalize short hums and double-dash pauses for playback only."""
    text = re.sub(r'\bhm\b', lambda match: match[0][0] + 'mmmm', text, flags=re.IGNORECASE)
    return re.sub(r'\s*--+\s*', ' [xis_dash] ', text)


class KokoroBackend:
    def __init__(self, config):
        from RealtimeTTS import KokoroEngine, TextToAudioStream
        from audio_effects import EffectsQueue, warm_pitch
        warm_pitch()
        self.engine = KokoroEngine(voice=config['voice'], default_speed=config['speed'])
        # The pinned engine emits complete generated chunks as mono int16 PCM.
        # Processing before queue insertion also affects previews and WAV output.
        self.effects = EffectsQueue()
        self.engine.queue = self.effects
        from stutters import install
        install(self.engine, self.effects)
        self.stream = TextToAudioStream(self.engine, output_device_index=config.get('output_device_index'))
        self.stream.add_pause('xis_dash', 0.18)

    def configure(self, speed, pitch, volume, pitch_engine='rubberband'):
        self.engine.set_speed(speed)
        self.effects.pitch, self.effects.volume = pitch, volume
        self.effects.pitch_engine = pitch_engine
        self.effects.error = None

    def speak(self, dialogue, voice, cancelled):
        self.effects.cancelled = cancelled
        self.engine.set_voice(voice)
        if cancelled():
            return
        # Dialogue is already available: preserve sentence context for prosody
        # instead of yielding early fragments at commas to minimize latency.
        self.stream.feed(speech_text(dialogue.text)).play_async(
            fast_sentence_fragment=False,
            fast_sentence_fragment_allsentences=False,
            fast_sentence_fragment_allsentences_multiple=False,
            force_first_fragment_after_words=100000,
            # Keep even one-word questions/exclamations separate. Otherwise the
            # default 10-character minimum merges "Lion? Lion!?" into one call.
            minimum_sentence_length=1,
            sentence_silence_duration=0.3,
        )
        while self.stream.is_playing():
            if cancelled():
                self.stream.stop()
                return
            time.sleep(0.03)
        if getattr(self.stream, 'error_flag', False):
            raise RuntimeError('RealtimeTTS reported a playback/synthesis failure; see its console log')
        if self.effects.error:
            raise RuntimeError('Audio processing failed') from self.effects.error

    def close(self):
        self.stream.stop()
        self.engine.shutdown()


class DryBackend:
    def __init__(self, config):
        self.parameters = {}

    def configure(self, speed, pitch, volume, pitch_engine='rubberband'):
        self.parameters = dict(speed=speed, pitch=pitch, volume=volume, pitch_engine=pitch_engine)

    def speak(self, dialogue, voice, cancelled):
        if not cancelled():
            LOG.info('[%s %s] %s: %s', voice, self.parameters, dialogue.speaker or 'Narrator', dialogue.text)

    def close(self):
        pass


DEFAULTS = dict(voice='af_heart', speed=1.0, voices={}, queue_limit=12,
                max_age_seconds=30.0, duplicate_seconds=1.0, output_device_index=None,
                voice_pool=VOICES, volume=1.0)


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
    for key, low, high in [('speed', 0.5, 2), ('volume', 0, 3), ('queue_limit', 1, 100),
                           ('max_age_seconds', 1, 300), ('duplicate_seconds', 0, 10)]:
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not low <= value <= high:
            raise ValueError(f'{key} must be between {low} and {high}')
    if not isinstance(config['queue_limit'], int):
        raise ValueError('queue_limit must be an integer')
    device = config['output_device_index']
    if device is not None and (type(device) is not int or device < 0):
        raise ValueError('output_device_index must be null or a nonnegative integer')
    pool = config['voice_pool']
    if not isinstance(pool, list) or not pool or any(v not in VOICES for v in pool):
        raise ValueError('voice_pool must be a nonempty list of supported English voice IDs')
    return config


class SpeechQueue:
    def __init__(self, config, backend_factory=KokoroBackend, registry=None):
        self.config = config
        self.registry = registry
        self.last_error = ''
        self.factory = backend_factory
        self.condition = threading.Condition()
        self.pending = deque()
        self.generation = 0
        self.closed = False
        self.state = 'starting'
        self.recent = None
        self.worker = threading.Thread(target=self._run, name='speech', daemon=True)
        self.worker.start()

    def submit(self, dialogue, voice_override=None):
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
            self.pending.append((self.generation, now, dialogue, voice_override))
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
                    generation, received, dialogue, voice_override = self.pending.popleft()
                    if time.monotonic() - received > self.config['max_age_seconds']:
                        LOG.info('Dropped expired dialogue')
                        continue
                    self.state = 'speaking'
                def cancelled():
                    with self.condition:
                        return self.closed or generation != self.generation
                if self.registry:
                    with self.registry.lock:
                        profile = self.registry.playback(dialogue.speaker, voice_override)
                        review = self.registry.review_candidate(dialogue.speaker) if voice_override is None else None
                else:
                    profile = dict(voice=voice_override or self.config['voices'].get(dialogue.speaker, self.config['voice']),
                                   speed=self.config['speed'], pitch=0, volume=self.config.get('volume', 1.0))
                voice = profile.pop('voice')
                try:
                    if voice is not None and not cancelled():
                        if hasattr(backend, 'configure'):
                            backend.configure(**profile)
                        backend.speak(dialogue, voice, cancelled)
                        self.last_error = ''
                        if self.registry and review and not cancelled() and not isinstance(backend, DryBackend):
                            self.registry.heard_for_review(dialogue.speaker, review['fingerprint'])
                except Exception as exc:
                    # One failed voice download must not disable every NPC.
                    self.last_error = str(exc)[:300]
                    LOG.exception('Voice playback failed: %s', voice)
                    if hasattr(backend, 'stream'):
                        backend.stream.stop()
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
    def __init__(self, speech, port, registry=None):
        self.speech = speech
        self.registry = registry
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Do not enable address reuse: two companions must not share the port.
        self.socket.bind(('127.0.0.1', port))
        self.socket.settimeout(0.2)
        self.seen = {}
        self.ui_replies = {}

    def handle_ui(self, data, address):
        header, separator, body = data.partition(b'\n')
        if not separator or len(data) > MAX_DATAGRAM:
            return
        match = re.fullmatch(rb'XISUI\t([A-Za-z0-9-]{1,80})', header)
        if not match:
            return
        identity = match[1].decode('ascii')
        cache_key = (address, identity)
        now = time.monotonic()
        self.ui_replies = {k: v for k, v in self.ui_replies.items() if now - v[0] < 60}
        if cache_key in self.ui_replies:
            self.socket.sendto(self.ui_replies[cache_key][1], address)
            return
        try:
            request = json.loads(body)
            if not isinstance(request, dict):
                raise ValueError('Expected a request object')
            if self.registry is None:
                raise ValueError('NPC registry is unavailable')
            action = request.get('action')
            if action == 'list':
                result = self.registry.page(request.get('search', ''), request.get('filter', 'all'), request.get('page', 0))
                result['voices'] = VOICES
                result['globals'] = self.registry.globals()
            elif action == 'edit':
                result = {'npc': self.registry.edit(request.get('key'), request.get('edit'), request.get('value'))}
            elif action == 'review_poll':
                result = self.registry.review_state()
            elif action == 'review_toggle':
                self.registry.set_review_enabled(request.get('enabled'))
                result = self.registry.review_state()
            elif action == 'review':
                npc = self.registry.review_action(request.get('key'), request.get('fingerprint'), request.get('decision'))
                result = dict(self.registry.review_state(), npc=npc, voices=VOICES)
            elif action == 'globals':
                result = {'globals': self.registry.set_globals(request.get('speed'), request.get('volume'), request.get('pitch_engine'))}
            elif action == 'preview':
                voice = request.get('voice')
                validate_voice(voice)
                profile = dict(voice=voice,
                               speed=number(request.get('speed', 1.0), 0.7, 1.3, 'NPC speed'),
                               pitch=number(request.get('pitch', 0.0), -4, 4, 'Pitch'))
                profile = apply_presets(profile, request.get('presets', {}))
                self.speech.stop()
                if not self.speech.submit(Dialogue('', "Welcome to Vana'diel. May your travels be safe, my friend."), profile):
                    raise ValueError('Speech engine is unavailable; check the companion console')
                result = {'message': 'Preview queued'}
            else:
                raise ValueError('Unknown UI action')
            if action == 'list':
                result.update(self.registry.review_state())
            result.update(ok=True, status=self.speech.status(), error=self.speech.last_error)
        except (ValueError, TypeError, UnicodeError, sqlite3.Error) as exc:
            result = dict(ok=False, error=str(exc)[:300])
        reply = b'XISUI\t' + identity.encode('ascii') + b'\n' + json.dumps(result, ensure_ascii=False).encode('utf-8')
        if len(reply) > MAX_DATAGRAM:
            reply = b'XISUI\t' + identity.encode('ascii') + b'\n' + b'{"ok":false,"error":"Response too large; narrow the search"}'
        if len(self.ui_replies) >= 256:
            self.ui_replies.clear()
        self.ui_replies[cache_key] = (now, reply)
        self.socket.sendto(reply, address)

    def handle(self, data, address):
        if data.startswith(b'XISUI\t'):
            self.handle_ui(data, address)
            return
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
            if self.registry:
                self.registry.clear_reviews()
        else:
            dialogue = clean_dialogue(frame.raw)
            # Mode 142 also carries system notices. Only named dialogue is
            # eligible, even if another local sender bypasses the Lua filter.
            if dialogue and (frame.mode != 142 or dialogue.speaker):
                if self.registry and dialogue.speaker:
                    try:
                        self.registry.encounter(dialogue.speaker)
                    except (ValueError, sqlite3.Error):
                        LOG.exception('Unable to persist NPC encounter')
                        return
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
    parser.add_argument('--config', type=Path, default=app_root() / 'config.json')
    parser.add_argument('--dry-run', action='store_true', help='Print captured dialogue without loading a model')
    parser.add_argument('--registry', type=Path, help='NPC database path; default beside config.json')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be 1024..65535')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        config = load_config(args.config)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    database = args.registry or args.config.with_name('npcs.sqlite3')
    seed = resource_root() / 'seed.sqlite3'
    if seed.is_file():
        initialize_database(database, seed)
    registry = Registry(database, config)
    speech = SpeechQueue(config, DryBackend if args.dry_run else KokoroBackend, registry)
    server = None
    try:
        server = Server(speech, args.port, registry)
        server.run(threading.Event())
    except KeyboardInterrupt:
        LOG.info('Stopping')
    finally:
        if server:
            server.close()
        speech.close()
        if not speech.worker.is_alive():
            registry.close()


if __name__ == '__main__':
    main()
