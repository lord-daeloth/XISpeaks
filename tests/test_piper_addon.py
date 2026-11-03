"""Exercise the separate Ashita entry point using the existing LuaJIT fixtures."""
from pathlib import Path
import unittest
import test_addon as addon_tests
import test_voice_ui as ui_tests
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipIf(addon_tests.LuaRuntime is None,'Optional developer dependency: lupa')
class PiperAddonTests(unittest.TestCase):
    def test_separate_command_port_and_npc_capture(self):
        fixture=addon_tests.AddonTests();fixture.setUp();lua=fixture.lua
        lua.execute('''handlers.unload(); sent={}
            local old=package.loaded.socket.udp
            package.loaded.socket.udp=function()
                local socket=old();socket.setpeername=function(self,host,port) selected_port=port;return true end
                return socket
            end
        ''')
        lua.execute((ROOT/'addon/XISpeaksPiper/XISpeaksPiper.lua').read_text())
        lua.execute('''handlers.load(); assert(addon.name=='XISpeaksPiper'); assert(selected_port==49153)
            local old={command='/xis test'};handlers.command(old);assert(not old.blocked)
            local new={command='/xisp test'};handlers.command(new);assert(new.blocked)
            handlers.text_in({mode=654,message='Halver : Welcome.'})
            assert(sent[#sent]:find('Halver : Welcome.',1,true))
            handlers.unload()
        ''')

    def test_piper_editor_does_not_offer_blends_or_contributions(self):
        fixture=ui_tests.VoiceUITests();fixture.setUp();lua=fixture.lua
        module=lua.execute((ROOT/'addon/XISpeaksPiper/voice_ui.lua').read_text())
        lua.globals().piper_module=module
        lua.execute("ui=piper_module.new(function(wire) table.insert(sent,wire) end,function() return now end,'test'); ui.visible=true")
        fixture.load_list()
        before=len(lua.globals().sent)
        lua.execute("clicks['Contribute voices']=true; clicks['Blend two voices']=true; ui:draw(); assert(depth==0)")
        self.assertEqual(len(lua.globals().sent),before)

if __name__=='__main__':unittest.main()
