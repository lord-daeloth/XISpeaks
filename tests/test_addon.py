"""Ashita event contract checks using LuaJIT, without attaching to the game."""
from pathlib import Path
import unittest

try:
    from lupa.luajit21 import LuaRuntime
except ImportError:
    LuaRuntime = None


@unittest.skipIf(LuaRuntime is None, 'Optional developer dependency: pip install lupa')
class AddonTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''
            addon = {path='C:/test/'}; handlers = {}; sent = {}; printed = {}; saved = 0; now = 1
            captured = ''; file_closed = false
            io.open = function(path, mode) return {
                write = function(self, text) captured = captured .. text; return self end,
                flush = function() return true end,
                close = function() file_closed = true; return true end
            } end
            function print(s) table.insert(printed, s) end
            function T(t) return t end
            bit = require('bit')
            ashita = {events = {register = function(event, name, callback) handlers[event] = callback end}}
            function string:args()
                local result = {}; for word in self:gmatch('%S+') do table.insert(result, word) end
                return result
            end
            package.preload.common = function() return {} end
            package.preload.settings = function() return {
                load = function(t) return t end, register = function() end,
                save = function() saved = saved + 1 end
            } end
            package.preload.socket = function() return {
                gettime = function() return now end,
                udp = function() return {
                    close = function() end, settimeout = function() end,
                    setpeername = function() return true end,
                    send = function(self, text) table.insert(sent, text); return #text end,
                    receive = function() return nil end
                } end
            } end
        ''')
        source = Path(__file__).resolve().parents[1] / 'addon' / 'XISpeaks' / 'XISpeaks.lua'
        self.lua.execute(source.read_text())
        self.lua.execute('handlers.load()')

    def test_only_original_npc_dialogue_and_high_mode_flags(self):
        self.lua.execute('''
            handlers.text_in({mode=150, message='Maat : Original', message_modified='hidden'})
            handlers.text_in({mode=150 + 256, message='Maat : Flagged'})
            handlers.text_in({mode=150, message='Injected', injected=true})
            for _,mode in ipairs({9,10,12,13,14,122,151,214}) do
                handlers.text_in({mode=mode, message='Not NPC speech'})
            end
            assert(#sent == 2)
            assert(sent[1]:find('Maat : Original', 1, true))
            assert(sent[2]:find('Maat : Flagged', 1, true))
        ''')

    def test_disable_system_opt_in_zone_and_test(self):
        self.lua.execute('''
            local event = {command='/xis off'}; handlers.command(event); assert(event.blocked)
            assert(sent[#sent]:find('stop', 1, true))
            handlers.text_in({mode=150, message='Muted'})
            assert(#sent == 1)
            handlers.command({command='/xis test'}); assert(#sent == 2)
            handlers.command({command='/xis on'})
            handlers.command({command='/xis system on'})
            handlers.text_in({mode=151, message='Narration'})
            assert(#sent == 3)
            handlers.packet_in({id=0x00B})
            assert(sent[4]:find('stop', 1, true))
            handlers.unload()
        ''')

    def test_trace_captures_filtered_and_injected_without_speaking_them(self):
        self.lua.execute('''
            handlers.command({command='/xis trace on'})
            handlers.text_in({mode=151, mode_modified=150, message='Halver : Wait.', blocked=true})
            handlers.text_in({mode=150, message='Faurie : Goodbye.', message_modified='[9:54pm] Faurie : Goodbye.'})
            handlers.text_in({mode=150, message='Faurie : Goodbye.', injected=true})
            handlers.packet_in({id=0x034})
            handlers.command({command='/xis trace off'})
            assert(#sent == 1)
            assert(captured:find('mode-filter', 1, true))
            assert(captured:find('injected', 1, true))
            assert(captured:find('metadata-only', 1, true))
            assert(file_closed)
        ''')
        import csv
        import io
        rows = list(csv.DictReader(io.StringIO(self.lua.globals().captured), delimiter='\t'))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['mode_low'], '151')
        self.assertEqual(rows[0]['mode_modified'], '150')
        self.assertEqual(bytes.fromhex(rows[0]['original_hex']), b'Halver : Wait.')

    def test_trace_name_filter_and_timeout(self):
        self.lua.execute('''
            handlers.command({command='/xis trace Halver'})
            handlers.text_in({mode=151, message='Halver : Wait.'})
            handlers.text_in({mode=14, message='Linkshell conversation'})
            now = 122; handlers.d3d_present()
            assert(file_closed)
            local old = captured
            handlers.text_in({mode=151, message='Halver : Later.'})
            assert(captured == old)
            assert(not captured:find('4C696E6B7368656C6C', 1, true))
        ''')

    def test_trace_bounded_buffer_and_byte_truncation(self):
        self.lua.execute('''
            handlers.command({command='/xis trace on'})
            for i=1,200 do handlers.text_in({mode=151, message=string.rep('a', 2048)}) end
            handlers.command({command='/xis trace off'})
            assert(#captured < 150000)
            assert(printed[#printed]:find('137 buffer drops', 1, true))
        ''')

    def test_trace_write_error_closes_capture(self):
        self.lua.execute('''
            io.open = function() return {
                write=function() return nil, 'disk full' end,
                close=function() file_closed=true end
            } end
            handlers.command({command='/xis trace on'})
            handlers.text_in({mode=151, message='Halver : Wait.'})
            now=2; handlers.d3d_present()
            assert(file_closed)
            assert(printed[#printed]:find('write error', 1, true))
        ''')


if __name__ == '__main__':
    unittest.main()
