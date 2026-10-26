addon.name = 'XISpeaks'
addon.author = 'Daeloth'
addon.version = '0.8.0'
addon.desc = 'NPC dialogue speech through a local Kokoro companion.'

require('common')
local socket = require('socket')
local settings = require('settings')
local config = settings.load(T{enabled = true, system = false, port = 49152})
local udp, pending_ping, sequence = nil, nil, 0
local session = tostring(os.time()) .. '-' .. tostring(math.random(100000, 999999))
local busy = false
local trace, trace_sequence = nil, 0
local voice_ui

local function editor()
    if not voice_ui then
        voice_ui = require('voice_ui').new(function(wire)
            if udp then return udp:send(wire) end
        end, socket.gettime, session)
    end
    return voice_ui
end

local function report(text)
    print('[XISpeaks] ' .. text)
end

local function is_named_dialogue(message)
    if type(message) ~= 'string' then return false end
    local plain = message:gsub('[\030\031].', '')
    local name, body = plain:match('^%s*(.-)%s+:%s+(.+)$')
    return name ~= nil and #name > 0 and #name <= 48 and body:find('%S') ~= nil
end

-- Tracing precedes all speech filters. Buffer writes until present so text_in
-- only copies bounded data. Original game bytes are preserved as hex.
local function hex(text)
    if type(text) ~= 'string' then return '' end
    return (text:sub(1, 1024):gsub('.', function(c) return ('%02X'):format(c:byte()) end))
end

local function flush_trace()
    if not trace or #trace.lines == 0 then return true end
    local ok, result = pcall(function()
        local written = trace.file:write(table.concat(trace.lines))
        if not written then return false end
        return trace.file:flush() ~= nil
    end)
    trace.lines = {}
    trace.flushed = socket.gettime()
    return ok and result
end

local function stop_trace(reason)
    if not trace then return end
    local ok = flush_trace()
    local old = trace
    trace = nil -- Ignore report text even if another addon reinjects it.
    old.file:close()
    report(('Trace %s: %d records, %d buffer drops. %s%s'):format(
        reason or 'saved', old.count, old.dropped, old.path, ok and '' or ' (write failed)'))
end

local function start_trace(filter)
    stop_trace('saved')
    trace_sequence = trace_sequence + 1
    local root = addon.path
    if type(root) ~= 'string' or root == '' then report('Addon path unavailable; cannot trace.'); return end
    local path = root:gsub('[/\\]+$', '') .. '/trace-' .. os.date('%Y%m%d-%H%M%S')
        .. '-' .. session .. '-' .. trace_sequence .. '.tsv'
    local file, err = io.open(path, 'wb')
    if not file then report('Cannot create trace: ' .. tostring(err)); return end
    local now = socket.gettime()
    trace = {file=file, path=path, started=now, flushed=now, count=0, dropped=0,
        filter=filter and filter:lower(), lines={
            'elapsed_ms\tkind\tmode_or_packet\tmode_low\tmode_modified\tinjected\tblocked\tdecision\toriginal_bytes\tmodified_bytes\toriginal_hex\tmodified_hex\n'}}
    report('Tracing for 120 seconds' .. (filter and ('; text filter: ' .. filter) or '; all chat text')
        .. '. Talk to the NPCs, then /xis trace off. File: ' .. path)
end

local function trace_event(kind, e, decision)
    if not trace or socket.gettime() - trace.started >= 120 or trace.count >= 1000 then return end
    local original, modified = e.message or '', e.message_modified or ''
    if kind == 'text' and trace.filter and not original:lower():find(trace.filter, 1, true)
            and not modified:lower():find(trace.filter, 1, true) then return end
    if #trace.lines >= 64 then trace.dropped = trace.dropped + 1; return end
    local mode = kind == 'text' and e.mode or e.id
    trace.count = trace.count + 1
    trace.lines[#trace.lines + 1] = table.concat({
        tostring(math.floor((socket.gettime() - trace.started) * 1000)), kind,
        tostring(mode), kind == 'text' and tostring(bit.band(mode, 0xFF)) or '',
        tostring(e.mode_modified or ''), tostring(e.injected or false), tostring(e.blocked or false),
        decision, tostring(#original), tostring(#modified), hex(original), hex(modified),
    }, '\t') .. '\n'
end

local function connect()
    if udp then udp:close() end
    udp = nil
    local s, err = socket.udp()
    if s then
        s:settimeout(0)
        local ok
        ok, err = s:setpeername('127.0.0.1', config.port)
        if ok then udp = s else s:close() end
    end
    if not udp then report('Local connection failed: ' .. tostring(err)) end
end

local function send(command, mode, message)
    if not udp then return false end
    sequence = sequence + 1
    local frame = ('XIS1\t%s\t%s-%d\t%d\n%s'):format(
        command, session, sequence, mode or 0, message or '')
    if #frame > 12000 then
        report('Dialogue exceeds transport limit; skipped.')
        return false
    end
    local ok = udp:send(frame)
    return ok ~= nil
end

settings.register('settings', 'xispeaks_settings', function(updated)
    if updated then config = updated; connect() end
end)

ashita.events.register('load', 'xispeaks_load', function()
    connect()
    report('Loaded. Start the companion, then use /xispeaks status.')
end)

ashita.events.register('unload', 'xispeaks_unload', function()
    stop_trace('saved on unload')
    send('stop')
    if udp then udp:close(); udp = nil end
end)

ashita.events.register('text_in', 'xispeaks_text', function(e)
    if busy then return end
    -- Always use original text: Balloon may hide or reformat message_modified.
    local mode = bit.band(e.mode, 0xFF)
    local decision = 'speech'
    if e.injected then decision = 'injected'
    elseif not config.enabled then decision = 'disabled'
    elseif mode == 142 and not is_named_dialogue(e.message) then decision = 'unnamed-mode-142'
    elseif mode ~= 142 and mode ~= 150 and not (config.system and mode == 151) then decision = 'mode-filter'
    elseif type(e.message) ~= 'string' or e.message == '' then decision = 'empty' end
    trace_event('text', e, decision)
    if decision ~= 'speech' then return end
    busy = true
    send('speak', mode, e.message)
    busy = false
end)

ashita.events.register('packet_in', 'xispeaks_zone', function(e)
    -- Correlation only: never record packet payloads or infer dialogue from them.
    if e.id == 0x017 or e.id == 0x032 or e.id == 0x033 or e.id == 0x034
            or e.id == 0x052 or e.id == 0x00A or e.id == 0x00B then
        trace_event('packet', e, 'metadata-only')
    end
    if e.id == 0x00A or e.id == 0x00B then send('stop') end
end)

ashita.events.register('d3d_present', 'xispeaks_poll', function()
    if trace then
        if socket.gettime() - trace.started >= 120 or trace.count >= 1000 then
            stop_trace('saved at capture limit')
        elseif socket.gettime() - trace.flushed >= 0.5 and not flush_trace() then
            stop_trace('stopped after write error')
        end
    end
    if voice_ui then voice_ui:tick(); voice_ui:draw() end
    if not udp then return end
    -- Bounded work; never wait for the companion on the game thread.
    for _ = 1, 4 do
        local response = udp:receive()
        if not response then break end
        if voice_ui and response:sub(1,6) == 'XISUI\t' then
            voice_ui:receive(response)
        elseif pending_ping and response:sub(1, 7) == 'XIS1\tOK' then
            report(response:sub(9):gsub('[%c]', ' '))
            pending_ping = nil
            break
        end
    end
    if pending_ping and socket.gettime() - pending_ping > 2 then
        report('No companion response. Check run.cmd and port ' .. config.port .. '.')
        pending_ping = nil
    end
end)

ashita.events.register('command', 'xispeaks_command', function(e)
    local args = e.command:args()
    if #args == 0 or (args[1]:lower() ~= '/xispeaks' and args[1]:lower() ~= '/xis') then return end
    e.blocked = true
    local command = (args[2] or 'voices'):lower()
    if command == 'voices' or command == 'ui' then
        editor():open()
    elseif command == 'trace' then
        local option = (args[3] or ''):lower()
        if option == 'off' then stop_trace('saved')
        elseif option == 'on' then start_trace()
        elseif option ~= '' then start_trace(table.concat(args, ' ', 3))
        else report('/xis trace on | off | <NPC name>; capture lasts up to 120 seconds.') end
    elseif command == 'on' or command == 'off' then
        config.enabled = command == 'on'
        if not config.enabled then send('stop') end
        settings.save()
        report(config.enabled and 'Speech enabled.' or 'Speech disabled.')
    elseif command == 'stop' then
        send('stop')
    elseif command == 'system' and (args[3] == 'on' or args[3] == 'off') then
        config.system = args[3] == 'on'
        settings.save()
        report('System narration ' .. args[3] .. '. This includes non-dialogue notices.')
    elseif command == 'status' then
        connect()
        send('ping')
        pending_ping = socket.gettime()
        report(('Addon %s; system %s; port %d.'):format(
            config.enabled and 'on' or 'off', config.system and 'on' or 'off', config.port))
    elseif command == 'test' then
        send('speak', 150, 'Welcome to Vana\'diel. Your voice companion is ready.')
    elseif command == 'port' and tonumber(args[3]) and tonumber(args[3]) % 1 == 0
            and tonumber(args[3]) >= 1024 and tonumber(args[3]) <= 65535 then
        send('stop')
        config.port = tonumber(args[3]); settings.save(); connect()
        report('Port set to ' .. config.port .. '. Match the companion --port option.')
    else
        report('/xispeaks voices | on | off | stop | status | test | system on/off | port <1024-65535> | trace on/off/<NPC>')
    end
end)
