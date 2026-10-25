addon.name = 'XISpeaks'
addon.author = 'Daeloth'
addon.version = '0.1.0'
addon.desc = 'NPC dialogue speech through a local Kokoro companion.'

require('common')
local socket = require('socket')
local settings = require('settings')
local config = settings.load(T{enabled = true, system = false, port = 49152})
local udp, pending_ping, sequence = nil, nil, 0
local session = tostring(os.time()) .. '-' .. tostring(math.random(100000, 999999))
local busy = false

local function report(text)
    print('[XISpeaks] ' .. text)
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
    send('stop')
    if udp then udp:close(); udp = nil end
end)

ashita.events.register('text_in', 'xispeaks_text', function(e)
    if busy or e.injected or not config.enabled then return end
    -- Always use original text: Balloon may hide or reformat message_modified.
    local mode = bit.band(e.mode, 0xFF)
    if mode ~= 150 and not (config.system and mode == 151) then return end
    if type(e.message) ~= 'string' or e.message == '' then return end
    busy = true
    send('speak', mode, e.message)
    busy = false
end)

ashita.events.register('packet_in', 'xispeaks_zone', function(e)
    if e.id == 0x00A or e.id == 0x00B then send('stop') end
end)

ashita.events.register('d3d_present', 'xispeaks_poll', function()
    if not udp or not pending_ping then return end
    -- Bounded work; never wait for the companion on the game thread.
    for _ = 1, 4 do
        local response = udp:receive()
        if not response then break end
        if response:sub(1, 7) == 'XIS1\tOK' then
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
    local command = (args[2] or 'help'):lower()
    if command == 'on' or command == 'off' then
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
        send('speak', 150, 'XISpeaks : Welcome to Vana\'diel. Your voice companion is ready.')
    elseif command == 'port' and tonumber(args[3]) and tonumber(args[3]) % 1 == 0
            and tonumber(args[3]) >= 1024 and tonumber(args[3]) <= 65535 then
        send('stop')
        config.port = tonumber(args[3]); settings.save(); connect()
        report('Port set to ' .. config.port .. '. Match the companion --port option.')
    else
        report('/xispeaks on | off | stop | status | test | system on/off | port <1024-65535>')
    end
end)
