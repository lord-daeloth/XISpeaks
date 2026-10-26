local imgui = require('imgui')
local json = require('json')
local M = {}

function M.new(send, clock, session)
    local ui = {visible=false, rows={}, voices={}, total=0, page=0, search='', filter='all',
        selected=nil, draft=nil, pending=nil, next_refresh=0, serial=0,
        draft_speed=100, draft_pitch=0, global_speed=100, global_volume=100, global_dirty=false,
        globals={speed=1,volume=1}, pitch_engine='rubberband',
        message='Start the companion, then Refresh.', status='Not connected'}

    function ui:request(payload)
        if self.pending then return false end
        self.serial = self.serial + 1
        local id = session .. '-ui-' .. self.serial
        local wire = 'XISUI\t' .. id .. '\n' .. json.encode(payload)
        self.pending = {id=id, wire=wire, action=payload.action, query=payload, attempts=1, sent=clock()}
        send(wire)
        return true
    end

    function ui:refresh()
        if self:request({action='list', search=self.search, filter=self.filter, page=self.page}) then
            self.next_refresh = clock() + 3
        end
    end

    function ui:open()
        self.visible = not self.visible
        if self.visible then self.next_refresh = 0 end
    end

    function ui:receive(wire)
        local id, body = wire:match('^XISUI\t([^\n]+)\n(.*)$')
        if not id then return false end
        if not self.pending or id ~= self.pending.id then return true end
        local ok, result = pcall(json.decode, body)
        if not ok or type(result) ~= 'table' or type(result.ok) ~= 'boolean' then return true end
        local action, query = self.pending.action, self.pending.query
        self.pending = nil
        if action == 'list' and (query.search ~= self.search or query.filter ~= self.filter or query.page ~= self.page) then
            self.next_refresh = 0
            return true -- Search changed in flight: don't show an obsolete page.
        end
        if not result.ok then self.message = 'Error: ' .. tostring(result.error); return true end
        self.status = result.status or 'Connected'
        self.message = (result.error and result.error ~= '') and ('Speech error: ' .. result.error) or ''
        if type(result.globals) == 'table' then
            self.globals = result.globals
            if not self.global_dirty or action == 'globals' then
                self.global_speed = math.floor(result.globals.speed*100+0.5)
                self.global_volume = math.floor(result.globals.volume*100+0.5)
                self.pitch_engine = result.globals.pitch_engine or 'rubberband'
                self.global_dirty = false
            end
        end
        if action == 'list' and type(result.rows) == 'table' and type(result.voices) == 'table' then
            self.rows, self.voices = result.rows, result.voices
            self.total, self.page = result.total or 0, result.page or 0
            if self.selected then
                for _, row in ipairs(self.rows) do
                    if row.key == self.selected.key then self.selected = row; break end
                end
            end
        elseif action == 'edit' and type(result.npc) == 'table' then
            self.selected = result.npc
            self.draft = result.npc.voice
            self.draft_speed = math.floor((result.npc.base_speed or result.npc.speed or 1)*100+0.5)
            self.draft_pitch = math.floor((result.npc.base_pitch or result.npc.pitch or 0)*10+0.5)
            self.message = 'Saved.'
            self.next_refresh = 0
        elseif action == 'preview' then
            self.message = 'Preview queued. First use of a voice may download its assets.'
        elseif action == 'globals' then
            self.message = 'Global audio settings saved. Applies to the next line.'
        end
        return true
    end

    function ui:tick()
        local now = clock()
        if self.pending and now - self.pending.sent >= 0.8 then
            if self.pending.attempts < 3 then
                self.pending.attempts = self.pending.attempts + 1
                self.pending.sent = now
                send(self.pending.wire) -- Same ID: companion replays acknowledgement, not the edit/preview.
            else
                self.pending = nil
                self.status = 'No companion response'
                self.message = 'Start/restart the companion. Refresh to confirm any unacknowledged edit.'
                self.next_refresh = now + 5
            end
        end
        if self.visible and not self.pending and now >= self.next_refresh then self:refresh() end
    end

    function ui:edit(action, value)
        if self.selected and not self.pending then
            self:request({action='edit', key=self.selected.key, edit=action, value=value})
        end
    end

    function ui:draw()
        if not self.visible then return end
        imgui.SetNextWindowSize({780, 790}, ImGuiCond_FirstUseEver)
        local open = {self.visible}
        if imgui.Begin('XISpeaks - NPC voices', open) then
            imgui.Text('Companion: ' .. self.status)
            if self.pending then imgui.SameLine(); imgui.TextDisabled('Updating...') end
            local engines = {rubberband='Rubber Band R3 - Higher quality', librosa='Librosa - Faster'}
            imgui.SetNextItemWidth(300)
            if imgui.BeginCombo('Pitch engine', engines[self.pitch_engine]) then
                for _, engine in ipairs({'rubberband','librosa'}) do
                    if imgui.Selectable(engines[engine], engine == self.pitch_engine) then
                        self.pitch_engine=engine; self.global_dirty=true
                    end
                end
                imgui.EndCombo()
            end
            local base, volume = {self.global_speed}, {self.global_volume}
            imgui.SetNextItemWidth(220)
            if imgui.SliderInt('Global speed (%)', base, 50, 200) then self.global_speed=base[1]; self.global_dirty=true end
            imgui.SetNextItemWidth(220)
            if imgui.SliderInt('Voice volume (%)', volume, 0, 300) then self.global_volume=volume[1]; self.global_dirty=true end
            imgui.SameLine()
            if imgui.Button('Apply global audio') and not self.pending then
                self:request({action='globals', speed=self.global_speed/100, volume=self.global_volume/100, pitch_engine=self.pitch_engine})
            end
            imgui.TextDisabled('100% = normal. Boosted peaks are limited. Apply before previewing global changes.')
            imgui.Separator()
            local search = {self.search}
            imgui.SetNextItemWidth(280)
            local cursor = ImGuiCol_InputTextCursor or ImGuiCol_Text
            if cursor then imgui.PushStyleColor(cursor, {1,1,1,1}) end
            local changed = imgui.InputText('Search NPCs', search, 128)
            if cursor then imgui.PopStyleColor() end
            if changed then self.search=search[1]; self.page=0; self.next_refresh=clock()+0.4 end
            imgui.SameLine()
            if imgui.Button('Refresh') then self.next_refresh=0 end
            imgui.SetNextItemWidth(220)
            local filters = {all='All NPCs', recent='Recent (24 hours)', manual='Manual overrides'}
            if imgui.BeginCombo('Show', filters[self.filter]) then
                for _, key in ipairs({'all','recent','manual'}) do
                    if imgui.Selectable(filters[key], key == self.filter) then
                        self.filter=key; self.page=0; self.next_refresh=0
                    end
                end
                imgui.EndCombo()
            end
            imgui.Text(('%d NPCs | Page %d'):format(self.total, self.page+1))
            if imgui.BeginChild('npc_list', {0, 160}, true) then
                for _, row in ipairs(self.rows) do
                    local label = row.name .. '  |  ' .. row.voice .. '  |  ' .. row.source
                        .. (row.muted and '  [muted]' or '') .. '###npc-' .. row.key
                    if imgui.Selectable(label, self.selected and self.selected.key == row.key or false) and not self.pending then
                        self.selected=row; self.draft=row.voice
                        self.draft_speed=math.floor((row.base_speed or row.speed or 1)*100+0.5)
                        self.draft_pitch=math.floor((row.base_pitch or row.pitch or 0)*10+0.5)
                    end
                end
                if #self.rows == 0 then imgui.TextWrapped('No matching NPCs yet. Talk to an NPC with speech capture enabled.') end
            end
            imgui.EndChild()
            if imgui.Button('Previous') and self.page > 0 and not self.pending then self.page=self.page-1; self.next_refresh=0 end
            imgui.SameLine()
            if imgui.Button('Next') and (self.page+1)*12 < self.total and not self.pending then self.page=self.page+1; self.next_refresh=0 end
            imgui.Separator()
            local npc = self.selected
            if npc then
                imgui.Text(npc.name .. ' | Assigned: ' .. npc.voice .. ' (' .. npc.source .. ')')
                local seen = (npc.last_seen or 0) > 0 and os.date('%Y-%m-%d %H:%M', math.floor(npc.last_seen)) or 'Not encountered yet'
                imgui.TextDisabled('Last heard: ' .. seen)
                for i, preset in ipairs({'goblin','child','galka','mithra','tarutaru','elvaan'}) do
                    if i > 1 then imgui.SameLine() end
                    local enabled = {npc.presets and npc.presets[preset] or false}
                    local label = preset:sub(1,1):upper() .. preset:sub(2)
                    if imgui.Checkbox(label, enabled) then self:edit('preset', {name=preset, enabled=enabled[1]}) end
                end
                imgui.TextDisabled('Presets save immediately and stack. Manual voices take priority. Reset keeps presets.')
                imgui.SetNextItemWidth(230)
                local labels = {unknown='Unknown / mixed pool', masculine='Masculine voices', feminine='Feminine voices'}
                if imgui.BeginCombo('Automatic voice preference', labels[npc.preference] or 'Unknown') then
                    for _, preference in ipairs({'unknown','masculine','feminine'}) do
                        if imgui.Selectable(labels[preference], preference == npc.preference) then self:edit('preference', preference) end
                    end
                    imgui.EndCombo()
                end
                local current = self.draft or npc.voice
                local w, a, wb, b = current:match('^(0%.%d+)%*([%w_]+) %+ (0%.%d+)%*([%w_]+)$')
                local blending = a ~= nil
                a = a or current
                b = b or (a == 'af_heart' and 'af_bella' or 'af_heart')
                local ratio = math.floor((tonumber(w) or 0.7)*100+0.5)
                local enabled = {blending}
                if imgui.Checkbox('Blend two voices', enabled) then blending=enabled[1] end
                imgui.SetNextItemWidth(230)
                if imgui.BeginCombo('Voice', a) then
                    for _, voice in ipairs(self.voices) do
                        local style = voice:sub(2,2) == 'm' and 'masculine' or 'feminine'
                        local accent = voice:sub(1,1) == 'a' and 'US' or 'UK'
                        if imgui.Selectable(voice .. ' (' .. accent .. ', ' .. style .. ')', voice == a) then a=voice end
                    end
                    imgui.EndCombo()
                end
                if blending then
                    imgui.SetNextItemWidth(230)
                    if imgui.BeginCombo('Second voice', b) then
                        for _, voice in ipairs(self.voices) do
                            if voice ~= a and imgui.Selectable(voice .. '##blend-second', voice == b) then b=voice end
                        end
                        imgui.EndCombo()
                    end
                    local amount = {ratio}
                    imgui.SetNextItemWidth(230)
                    if imgui.SliderInt('First voice share (%)', amount, 10, 90) then ratio=amount[1] end
                    if a == b then b = a == 'af_heart' and 'af_bella' or 'af_heart' end
                    self.draft = ('%.2f*%s + %.2f*%s'):format(ratio/100,a,(100-ratio)/100,b)
                    imgui.TextDisabled(('Mix: %d%% first / %d%% second. Preview before saving.'):format(ratio,100-ratio))
                else
                    self.draft = a
                end
                local speed, pitch = {self.draft_speed}, {self.draft_pitch/10}
                imgui.SetNextItemWidth(230)
                if imgui.SliderInt('NPC speed (%)', speed, 70, 130) then self.draft_speed=speed[1] end
                imgui.SetNextItemWidth(230)
                if imgui.SliderFloat('Pitch (semitones)', pitch, -4, 4, '%.1f') then
                    self.draft_pitch=math.floor(pitch[1]*10+0.5)
                end
                imgui.Text(('Pitch: %+.1f semitones | Effective speed: %.0f%%'):format(
                    math.max(-4,math.min(4,self.draft_pitch/10+(npc.preset_pitch or 0))), math.max(50,math.min(200,self.globals.speed*self.draft_speed*(npc.preset_speed or 1)))))
                imgui.TextDisabled(('Automatic: %.0f%% speed, %+.1f semitones | Tuning: %s'):format(
                    (npc.auto_speed or 1)*100, npc.auto_pitch or 0, npc.tuning_source or 'automatic'))
                if imgui.Button('Preview voice') and not self.pending then
                    self:request({action='preview', voice=self.draft or npc.voice, speed=self.draft_speed/100, pitch=self.draft_pitch/10, presets=npc.presets})
                end
                imgui.SameLine()
                if imgui.Button('Save override') then
                    self:edit('profile', {voice=self.draft or npc.voice, speed=self.draft_speed/100, pitch=self.draft_pitch/10})
                end
                imgui.SameLine()
                if imgui.Button('Reset to automatic') then self:edit('reset') end
                if imgui.Button('Reset pitch/speed only') then self:edit('reset_tuning') end
                local mute = {npc.muted}
                if imgui.Checkbox('Mute this NPC', mute) then self:edit('mute', mute[1]) end
                imgui.TextWrapped('Preview replaces queued speech. Edits apply to the next line; the current line finishes. Preference affects automatic assignments only.')
            else
                imgui.TextWrapped('Select an NPC above to assign or preview a voice.')
            end
            if self.message ~= '' then imgui.TextWrapped(self.message) end
        end
        imgui.End()
        self.visible = open[1]
    end
    return ui
end

return M
