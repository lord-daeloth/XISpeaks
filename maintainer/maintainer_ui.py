"""Small Windows/Tk desktop reviewer for community voice contributions."""
from collections import Counter
import json
from pathlib import Path
import queue
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from review_contributions import ROOT, load_official, read_submission, review, merge, save_review
from review_contributions import Registry, DEFAULTS, import_catalog
from voice_preview import VoicePreview

LABELS={'new':'New correction','new_approval':'New approval','matching':'Already matches',
        'conflict':'Conflict','outdated_or_custom_rules':'Older / custom rules'}
ELIGIBLE={'new','new_approval','conflict'}


def describe(sound, profile):
    if sound is None:
        return 'No official entry yet.'
    lines=[f"Voice: {sound['voice']}",f"Speed: {sound['speed']*100:g}%",f"Pitch: {sound['pitch']:+g} semitones"]
    if profile:
        lines += ['',f"Voice preference: {profile['preference']}",
            'Manual voice: '+str(profile['manual_voice'] or 'Automatic'),
            'Manual base speed: '+('Automatic' if profile['manual_speed'] is None else f"{profile['manual_speed']*100:g}%"),
            'Manual base pitch: '+('Automatic' if profile['manual_pitch'] is None else f"{profile['manual_pitch']:+g}"),
            'Presets: '+(', '.join(k[7:].title() for k,v in profile.items() if k.startswith('preset_') and v) or 'None')]
    return '\n'.join(lines)


class MaintainerUI:
    def __init__(self, root, official=None, catalog=None, backup_dir=None):
        self.root=root
        self.official=Path(official or ROOT/'data/release_npc_overrides.json')
        self.catalog=Path(catalog or ROOT/'data/npc_associations.json')
        self.backup_dir=backup_dir
        self.document=None; self.rows={}; self.selected=set(); self.busy=False
        self.messages=queue.Queue(); self.source=''; self.original=b''; self.curated=None
        self.preview_busy=False
        self.preview=VoicePreview(lambda action,payload:self.messages.put((action,payload)))
        root.title('XISpeaks — Maintainer')
        root.geometry('1120x760'); root.minsize(850,600)
        root.columnconfigure(0,weight=1); root.rowconfigure(0,weight=1)
        frame=ttk.Frame(root,padding=16); frame.grid(sticky='nsew')
        frame.columnconfigure(0,weight=1); frame.rowconfigure(4,weight=1); frame.rowconfigure(6,weight=1)
        ttk.Label(frame,text='Community voice contributions',font=('Segoe UI',17,'bold')).grid(sticky='w')
        ttk.Label(frame,text='Review a submission, select NPCs, then merge into the curated catalogue. Your live NPC database is never edited.').grid(row=1,sticky='w',pady=(4,12))
        toolbar=ttk.Frame(frame); toolbar.grid(row=2,sticky='ew')
        self.open_button=ttk.Button(toolbar,text='Open contribution file…',command=self.open_file); self.open_button.pack(side='left')
        ttk.Label(toolbar,text='  GitHub issue:').pack(side='left')
        self.issue=tk.StringVar(); self.issue_entry=ttk.Entry(toolbar,textvariable=self.issue,width=25); self.issue_entry.pack(side='left',padx=6)
        self.issue_button=ttk.Button(toolbar,text='Load issue',command=self.load_issue); self.issue_button.pack(side='left')
        self.issue_entry.bind('<Return>',lambda _: self.load_issue())
        self.source_label=ttk.Label(frame,text='Open a JSON export, a saved issue body, or an issue number/URL. Attachment issues: download the JSON first.')
        self.source_label.grid(row=3,sticky='w',pady=10)
        table=ttk.Frame(frame); table.grid(row=4,sticky='nsew'); table.columnconfigure(0,weight=1); table.rowconfigure(0,weight=1)
        self.tree=ttk.Treeview(table,columns=('accept','name','status','kind'),show='headings',selectmode='extended',height=10)
        for key,title,width in [('accept','Merge?',70),('name','NPC',300),('status','Review result',220),('kind','Contribution',140)]:
            self.tree.heading(key,text=title);self.tree.column(key,width=width,stretch=key!='accept')
        self.tree.grid(sticky='nsew');scroll=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview);scroll.grid(row=0,column=1,sticky='ns');self.tree.configure(yscrollcommand=scroll.set)
        self.tree.tag_configure('conflict',foreground='#a34200');self.tree.tag_configure('outdated_or_custom_rules',foreground='#7e4040')
        self.tree.bind('<<TreeviewSelect>>',lambda _:self.show_details())
        self.tree.bind('<Double-1>',lambda _:self.toggle_selection())
        self.tree.bind('<space>',lambda _:self.toggle_selection())
        controls=ttk.Frame(frame);controls.grid(row=5,sticky='ew',pady=8)
        self.toggle_button=ttk.Button(controls,text='Toggle highlighted',command=self.toggle_selection);self.toggle_button.pack(side='left')
        self.new_button=ttk.Button(controls,text='Select new entries',command=self.select_new);self.new_button.pack(side='left',padx=6)
        self.clear_button=ttk.Button(controls,text='Clear selection',command=self.clear_selection);self.clear_button.pack(side='left')
        self.allow=tk.BooleanVar(value=False)
        self.conflict_check=ttk.Checkbutton(controls,text='Allow selected conflicts to replace official profiles',variable=self.allow);self.conflict_check.pack(side='left',padx=12)
        details=ttk.Panedwindow(frame,orient='horizontal');details.grid(row=6,sticky='nsew')
        self.details=[]
        for title in ('Official profile','Proposed profile'):
            group=ttk.LabelFrame(details,text=title,padding=6);group.columnconfigure(0,weight=1);group.rowconfigure(0,weight=1)
            text=ScrolledText(group,height=9,wrap='word',font=('Segoe UI',10),state='disabled');text.grid(sticky='nsew')
            details.add(group,weight=1);self.details.append(text)
        previews=ttk.LabelFrame(frame,text='Listen to highlighted NPC — Rubber Band R3, 100% global speed and volume',padding=6)
        previews.grid(row=7,sticky='ew',pady=(8,0));previews.columnconfigure(0,weight=1)
        self.sample=tk.StringVar(value="There is much we have yet to discover. May your travels be safe, my friend!")
        ttk.Entry(previews,textvariable=self.sample).grid(row=0,column=0,sticky='ew',columnspan=4)
        self.preview_buttons={}
        for column,(kind,title) in enumerate((('automatic','Play automatic'),('override','Play current override'),('proposed','Play submitted'))):
            button=ttk.Button(previews,text=title,command=lambda k=kind:self.play_preview(k))
            button.grid(row=1,column=column,pady=6,sticky='w');self.preview_buttons[kind]=button
        self.stop_button=ttk.Button(previews,text='Stop',command=self.preview.stop);self.stop_button.grid(row=1,column=3)
        self.preview_status=tk.StringVar(value='Current override comes from the curated release JSON, not the live game database.')
        ttk.Label(previews,textvariable=self.preview_status,wraplength=1000).grid(row=2,column=0,columnspan=4,sticky='w')
        bottom=ttk.Frame(frame);bottom.grid(row=8,sticky='ew',pady=(12,0));bottom.columnconfigure(0,weight=1)
        self.status=tk.StringVar(value='Ready. Nothing is selected automatically.')
        ttk.Label(bottom,textvariable=self.status,wraplength=800).grid(sticky='w')
        self.merge_button=ttk.Button(bottom,text='Merge selected…',command=self.merge_selected);self.merge_button.grid(row=0,column=1,padx=(12,0))
        ttk.Label(frame,text='Writes: '+str(self.official),wraplength=1000).grid(row=9,sticky='w',pady=(8,0))
        self.update_controls();self.poll_id=root.after(100,self.poll)
        root.protocol('WM_DELETE_WINDOW',self.close)

    def close(self):
        self.preview.close()
        self.root.after_cancel(self.poll_id);self.root.destroy()

    def update_controls(self):
        for widget in (self.open_button,self.issue_button,self.issue_entry):
            widget.configure(state='disabled' if self.busy else 'normal')
        for widget in (self.toggle_button,self.new_button,self.clear_button,self.conflict_check):
            widget.configure(state='normal' if self.document and not self.busy else 'disabled')
        self.merge_button.configure(state='normal' if self.selected and not self.busy else 'disabled')
        highlighted=self.tree.selection()
        row=self.rows.get(highlighted[0]) if highlighted else None
        for kind,button in self.preview_buttons.items():
            available=row and (row.get('has_override') if kind=='override' else row.get(kind))
            button.configure(state='normal' if available and not self.busy and not self.preview_busy else 'disabled')
        self.stop_button.configure(state='normal' if self.preview_busy else 'disabled')

    def play_preview(self, kind):
        if self.busy or self.preview_busy:return
        selected=self.tree.selection()
        row=self.rows.get(selected[0]) if selected else None
        if not row or (kind=='override' and not row.get('has_override')):return
        sound=row.get('official' if kind=='override' else kind)
        text=self.sample.get().strip()
        if not sound or not text:
            self.preview_status.set('Enter sample text first.');return
        if len(text)>2000:
            self.preview_status.set('Keep the sample under 2,000 characters.');return
        self.preview_busy=True;self.update_controls()
        self.preview_status.set(f"Loading / playing {kind}: {row['name']} — {sound['voice']}, {sound['speed']*100:g}%, {sound['pitch']:+g} semitones. First preview loads the model.")
        self.preview.play(row['name'],text,sound)

    def open_file(self):
        path=filedialog.askopenfilename(title='Open voice contribution',filetypes=[('Contribution / issue body','*.json *.md *.txt'),('All files','*.*')])
        if path:self.start_load(file=Path(path))

    def load_issue(self):
        value=self.issue.get().strip()
        match=re.fullmatch(r'(?:https://github\.com/lord-daeloth/XISpeaks/issues/|#)?([1-9][0-9]*)/?',value)
        if not match:
            messagebox.showerror('Invalid issue','Enter an issue number or a lord-daeloth/XISpeaks issue URL.',parent=self.root);return
        self.start_load(issue=int(match[1]))

    def start_load(self, file=None, issue=None, document=None):
        if self.busy:return
        self.busy=True;self.update_controls();self.status.set('Loading and comparing profiles…')
        def work():
            registry=None;automatic=None
            try:
                incoming=document if document is not None else read_submission(file,issue)
                original=self.official.read_bytes()
                registry,curated=load_official(self.official,self.catalog)
                automatic=Registry(':memory:',dict(DEFAULTS,voices={}))
                import_catalog(automatic,json.loads(self.catalog.read_text(encoding='utf-8')))
                report=review(incoming,registry,curated,automatic)
                # Approvals alone are not overrides; race/preference corrections are.
                for row in report:
                    row['has_override']=row['has_override'] and (row['official']!=row['automatic'] or any(row['official_profile'][f] is not None for f in ('manual_voice','manual_speed','manual_pitch')))
                if self.official.read_bytes()!=original:raise ValueError('Official catalogue changed during loading. Try again.')
                source=self.source if document is not None else (f'GitHub issue #{issue}' if issue else str(file))
                self.messages.put(('loaded',(incoming,original,curated,report,source)))
            except Exception as error:
                self.messages.put(('error',str(error)))
            finally:
                if registry:registry.close()
                if automatic:automatic.close()
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            while True:
                action,payload=self.messages.get_nowait()
                if action.startswith('preview_'):
                    self.preview_busy=False;self.preview_status.set(payload if action=='preview_done' else 'Preview failed: '+payload)
                    self.update_controls();continue
                self.busy=False
                if action=='error':
                    self.status.set('Unable to load submission. Previous review retained.')
                    messagebox.showerror('Load failed',payload,parent=self.root)
                else:
                    self.document,self.original,self.curated,report,self.source=payload
                    self.rows={str(i):row for i,row in enumerate(report)}
                    self.selected.clear();self.allow.set(False)
                    for item in self.tree.get_children():self.tree.delete(item)
                    for iid,row in self.rows.items():
                        self.tree.insert('', 'end',iid=iid,values=('',row['name'],LABELS[row['status']],row['entry']['kind']),tags=(row['status'],))
                    self.source_label.configure(text=self.source)
                    self.show_details();self.selection_status()
                self.update_controls()
        except queue.Empty:pass
        self.poll_id=self.root.after(100,self.poll)

    def show_details(self):
        highlighted=self.tree.selection()
        row=self.rows.get(highlighted[0]) if highlighted else None
        contents=['Select an NPC to compare its profiles.']*2 if not row else [
            describe(row['official'],row['official_profile'])+'\n\nAutomatic baseline:\n'+describe(row.get('automatic'),None),
            LABELS[row['status']]+'\n\n'+describe(row['proposed'],row['entry']['profile'])]
        for widget,value in zip(self.details,contents):
            widget.configure(state='normal');widget.delete('1.0','end');widget.insert('1.0',value);widget.configure(state='disabled')
        self.update_controls()

    def selection_status(self):
        counts=Counter(row['status'] for row in self.rows.values())
        self.status.set(f'{len(self.selected)} selected / {len(self.rows)} NPCs. '+', '.join(f'{count} {LABELS[key].lower()}' for key,count in counts.items()))
        for iid,row in self.rows.items():self.tree.set(iid,'accept','Yes' if row['key'] in self.selected else '')
        self.update_controls()

    def toggle_selection(self):
        if self.busy:return
        for iid in self.tree.selection():
            row=self.rows[iid]
            if row['status'] in ELIGIBLE:
                if row['key'] in self.selected:self.selected.remove(row['key'])
                else:self.selected.add(row['key'])
        self.selection_status()

    def select_new(self):
        self.selected={r['key'] for r in self.rows.values() if r['status'] in ('new','new_approval')};self.selection_status()

    def clear_selection(self):
        self.selected.clear();self.selection_status()

    def merge_selected(self):
        if self.busy or not self.selected:return
        try:
            updated=merge(self.document,list(self.rows.values()),self.curated,self.selected,self.allow.get())
            chosen=[r['name']+(' [CONFLICT]' if r['status']=='conflict' else '') for r in self.rows.values() if r['key'] in self.selected]
            summary='\n'.join(chosen[:12])+ ('\n…' if len(chosen)>12 else '')
            if not messagebox.askyesno('Merge selected profiles?',f'Merge {len(chosen)} NPCs into the curated catalogue?\n\n{summary}\n\nA backup is created first. The live game database is not changed.',parent=self.root):return
            backup=save_review(self.official,self.original,self.curated,updated,self.backup_dir)
            messagebox.showinfo('Merge complete','No changes needed.' if backup is None else f'Saved {len(chosen)} selected NPCs.\n\nBackup: {backup}\n\nReview the Git diff before committing or packaging.',parent=self.root)
            self.start_load(document=self.document)
        except Exception as error:
            messagebox.showerror('Merge not saved',str(error),parent=self.root)


def main():
    root=tk.Tk()
    if 'vista' in ttk.Style(root).theme_names():ttk.Style(root).theme_use('vista')
    MaintainerUI(root);root.mainloop()


if __name__=='__main__':main()
