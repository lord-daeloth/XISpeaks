import json
from pathlib import Path
import unittest

try:
    from lupa.luajit21 import LuaRuntime
except ImportError:
    LuaRuntime = None


@unittest.skipIf(LuaRuntime is None, 'Optional developer dependency: pip install lupa')
class VoiceUITests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        def native(value):
            if hasattr(value, 'items'):
                return {key: native(item) for key, item in value.items()}
            return value
        self.lua.globals().py_encode = lambda value: json.dumps(native(value))
        self.lua.globals().py_decode = lambda value: self.lua.table_from(json.loads(value), recursive=True)
        self.lua.execute('''
            now=0; sent={}; clicks={}; texts={}; depth=0
            package.preload.json=function() return {encode=py_encode,decode=py_decode} end
            local function clicked(label)
                if clicks[label] then clicks[label]=nil; return true end
                return false
            end
            package.preload.imgui=function() return {
                SetNextWindowSize=function() end, SetNextItemWidth=function() end,
                Begin=function() depth=depth+1; return true end, End=function() depth=depth-1 end,
                BeginChild=function() depth=depth+1; return true end, EndChild=function() depth=depth-1 end,
                BeginCombo=function() depth=depth+1; return true end, EndCombo=function() depth=depth-1 end,
                InputText=function() return false end, SameLine=function() end, Separator=function() end,
                SliderInt=function() return false end,
                SliderFloat=function(label,value) if next_pitch then value[1]=next_pitch; next_pitch=nil; return true end; return false end,
                Text=function(text) table.insert(texts,text) end, TextDisabled=function() end,
                TextWrapped=function() end, Button=clicked, Selectable=clicked,
                Checkbox=function(label,value) if clicked(label) then value[1]=not value[1]; return true end; return false end
            } end
        ''')
        module = self.lua.execute((Path(__file__).resolve().parents[1] / 'addon/XISpeaks/voice_ui.lua').read_text())
        self.lua.globals().ui = module.new(self.lua.eval('function(wire) table.insert(sent,wire) end'),
                                          self.lua.eval('function() return now end'), 'test')
        self.npc = dict(key='halver', name='Halver', voice='am_michael', auto_voice='am_michael',
                        preference='unknown', source='automatic', muted=False, last_seen=1)

    def last_request(self):
        wire = self.lua.globals().sent[len(self.lua.globals().sent)]
        header, body = wire.split('\n', 1)
        return header, json.loads(body)

    def respond(self, data):
        header, _ = self.last_request()
        self.lua.globals().reply = header + '\n' + json.dumps(dict(ok=True, status='ready', error='', **data))
        self.lua.execute('ui:receive(reply)')

    def load_list(self):
        self.lua.execute('ui:open(); ui:tick()')
        self.respond(dict(rows=[self.npc], voices=['af_heart','am_michael'], total=1, page=0))

    def test_retry_same_id_ignores_old_replies_and_reports_timeout(self):
        self.lua.execute('ui:open(); ui:tick(); now=1; ui:tick(); now=2; ui:tick()')
        sent = self.lua.globals().sent
        self.assertEqual(sent[1], sent[2])
        self.assertEqual(sent[2], sent[3])
        self.lua.execute('ui:receive(\'XISUI\\twrong\\n{"ok":true}\'); assert(ui.pending ~= nil); now=3; ui:tick()')
        self.assertEqual(self.lua.globals().ui.status, 'No companion response')
        self.assertIsNone(self.lua.globals().ui.pending)

    def test_render_select_save_and_reset_only_after_ack(self):
        self.load_list()
        self.lua.execute('''
            clicks['Halver  |  am_michael  |  automatic###npc-halver']=true
            ui:draw(); assert(depth==0)
            clicks['af_heart (US, feminine)']=true; ui:draw()
            clicks['Save override']=true; ui:draw(); assert(depth==0)
            assert(ui.selected.voice=='am_michael')
        ''')
        self.assertEqual(self.last_request()[1], dict(action='edit',key='halver',edit='profile',value=dict(voice='af_heart',speed=1,pitch=0)))
        self.respond(dict(npc=dict(self.npc, voice='af_heart', source='manual')))
        self.lua.execute("clicks['Reset to automatic']=true; ui:draw()")
        self.assertEqual(self.last_request()[1]['edit'], 'reset')
        self.assertEqual(self.lua.globals().ui.selected.voice, 'af_heart')

    def test_preview_and_preference_and_mute_controls(self):
        self.load_list()
        self.lua.execute("clicks['Halver  |  am_michael  |  automatic###npc-halver']=true; ui:draw(); clicks['Preview voice']=true; ui:draw()")
        self.assertEqual(self.last_request()[1], dict(action='preview', voice='am_michael',speed=1,pitch=0))
        self.respond(dict(message='Preview queued'))
        self.lua.execute("clicks['Feminine voices']=true; ui:draw()")
        self.assertEqual(self.last_request()[1]['value'], 'feminine')
        self.respond(dict(npc=dict(self.npc, preference='feminine',voice='af_heart')))
        self.lua.execute("clicks['Mute this NPC']=true; ui:draw()")
        self.assertEqual(self.last_request()[1], dict(action='edit',key='halver',edit='mute',value=True))

    def test_failed_edit_does_not_claim_success(self):
        self.load_list()
        self.lua.execute("ui.selected=ui.rows[1]; ui:edit('mute',true)")
        header, _ = self.last_request()
        self.lua.globals().reply = header + '\n' + json.dumps(dict(ok=False,error='Database is read-only'))
        self.lua.execute('ui:receive(reply)')
        self.assertFalse(self.lua.globals().ui.selected.muted)
        self.assertIn('read-only', self.lua.globals().ui.message)

    def test_search_change_discards_obsolete_page(self):
        self.lua.execute("ui:open(); ui.page=2; ui:tick(); ui.search='Faurie'; ui.page=0")
        self.respond(dict(rows=[self.npc], voices=['af_heart'], total=50, page=2))
        self.assertEqual(self.lua.globals().ui.page, 0)
        self.assertEqual(len(self.lua.globals().ui.rows), 0)
        self.lua.execute('ui:tick()')
        self.assertEqual(self.last_request()[1]['search'], 'Faurie')
        self.assertEqual(self.last_request()[1]['page'], 0)

    def test_preset_toggle_and_preview_uses_base_tuning(self):
        self.load_list()
        self.lua.execute("ui.selected=ui.rows[1]; clicks['Goblin']=true; ui:draw()")
        self.assertEqual(self.last_request()[1], dict(action='edit', key='halver', edit='preset', value=dict(name='goblin', enabled=True)))
        self.respond(dict(npc=dict(self.npc, presets=dict(goblin=True), speed=1.15, pitch=3.5,
                                  base_speed=1, base_pitch=0, preset_speed=1.15, preset_pitch=3.5)))
        self.assertEqual(self.lua.globals().ui.draft_speed, 100)
        self.assertEqual(self.lua.globals().ui.draft_pitch, 0)
        self.lua.execute("clicks['Preview voice']=true; ui:draw()")
        self.assertEqual(self.last_request()[1], dict(action='preview', voice='am_michael', speed=1, pitch=0, presets=dict(goblin=True)))

    def test_elvaan_toggle_sends_saved_preset(self):
        self.load_list()
        self.lua.execute("ui.selected=ui.rows[1]; clicks['Elvaan']=true; ui:draw()")
        self.assertEqual(self.last_request()[1],dict(action='edit',key='halver',edit='preset',value=dict(name='elvaan',enabled=True)))

    def test_blend_controls_preview_and_disable(self):
        self.load_list()
        self.lua.execute("ui.selected=ui.rows[1]; ui.draft='0.70*am_michael + 0.30*am_fenrir'; clicks['Preview voice']=true; ui:draw()")
        self.assertEqual(self.last_request()[1]['voice'],'0.70*am_michael + 0.30*am_fenrir')
        self.respond(dict(message='Preview queued'))
        self.lua.execute("clicks['Blend two voices']=true; clicks['Save override']=true; ui:draw()")
        self.assertEqual(self.last_request()[1]['value']['voice'],'am_michael')

    def test_pitch_engine_selection_saves_with_globals(self):
        self.load_list()
        self.lua.execute("clicks['Librosa - Faster']=true; ui:draw(); clicks['Apply global audio']=true; ui:draw()")
        self.assertEqual(self.last_request()[1]['pitch_engine'], 'librosa')
        self.respond({'globals':dict(speed=1,volume=1,pitch_engine='librosa')})
        self.assertEqual(self.lua.globals().ui.pitch_engine, 'librosa')
        self.assertFalse(self.lua.globals().ui.global_dirty)

    def test_global_audio_and_tuned_preview(self):
        self.load_list()
        self.lua.execute("ui.global_speed=120; ui.global_volume=180; ui.global_dirty=true; clicks['Apply global audio']=true; ui:draw()")
        self.assertEqual(self.last_request()[1],dict(action='globals',speed=1.2,volume=1.8,pitch_engine='rubberband'))
        self.respond({'globals':dict(speed=1.2,volume=1.8)})
        self.assertFalse(self.lua.globals().ui.global_dirty)
        self.lua.execute("ui.selected=ui.rows[1]; ui.draft_speed=105; next_pitch=-.5; clicks['Preview voice']=true; ui:draw()")
        self.assertEqual(self.last_request()[1],dict(action='preview',voice='am_michael',speed=1.05,pitch=-.5))


if __name__ == '__main__':
    unittest.main()
