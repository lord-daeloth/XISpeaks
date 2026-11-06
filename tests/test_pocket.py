import sys,json,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'companion'),str(ROOT/'scripts')]
import test_addon as addon_tests

@unittest.skipIf(addon_tests.LuaRuntime is None,'LuaJIT not installed')
class PocketAddonTests(unittest.TestCase):
    def test_commands_port_and_npc_capture(self):
        fixture=addon_tests.AddonTests();fixture.setUp()
        lua=fixture.lua
        lua.execute("""handlers.unload(); sent={}
            local old=package.loaded.socket.udp
            package.loaded.socket.udp=function()
                local socket=old();socket.setpeername=function(self,host,port) selected_port=port;return true end
                return socket
            end""")
        lua.execute((ROOT/'addon/XISpeaksPocket/XISpeaksPocket.lua').read_text())
        lua.execute("""handlers.load(); assert(addon.name=='XISpeaksPocket'); assert(selected_port==49154)
            for _,command in ipairs({'/xis test','/xisp test'}) do
                local e={command=command};handlers.command(e);assert(not e.blocked)
            end
            local e={command='/xispt test'};handlers.command(e);assert(e.blocked)
            handlers.text_in({mode=654,message='Halver : Welcome.'})
            assert(sent[#sent]:find('Halver : Welcome.',1,true))
            handlers.unload()""")

class PocketCatalogTests(unittest.TestCase):
    def test_reject_mismatched_state_model_and_escape(self):
        import tempfile
        import pocket_catalog
        from pocket_paths import MODEL
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);(directory/'voice.safetensors').write_bytes(b'fixture')
            path=directory/'catalog.json'
            value={'am_test':dict(model='voice.safetensors',engine_model=MODEL)}
            path.write_text(json.dumps(value));self.assertIn('am_test',pocket_catalog.load(path))
            value['am_test']['engine_model']='english_7m_2026-10'
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):pocket_catalog.load(path)
            value['am_test'].update(engine_model=MODEL,model='../voice.safetensors')
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):pocket_catalog.load(path)
