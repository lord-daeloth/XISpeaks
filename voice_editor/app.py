"""Standalone editor for Pocket voices, eligibility, calibration and previews."""
import copy
import json
import queue
import secrets
import shutil
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
import winsound
ROOT=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'companion'),str(ROOT/'piper_trainer')]
from pocket_paths import VOICES, MODEL
from voice_catalog import NPC_TYPES,normalize
from pocket_catalog import Store,validate,validate_state
from preview import Renderer

GENDER_LABELS={'m':'Masculine (m)','f':'Feminine (f)','a':'Androgynous (a)','u':'Unknown (u)'}
ACCENT_LABELS={'a':'US / Canada','b':'UK / Ireland','x':'Other / unknown'}
TYPE_LABELS={kind:kind.title() for kind in NPC_TYPES}|{'other':'Other / no NPC preset (includes Hume)'}
OUTPUT=ROOT/'pocket-runtime/catalog-previews'

class Editor:
    def __init__(self,root,path=VOICES/'catalog.json'):
        self.root=root;self.store=Store(path,prune_missing=True);self.catalog=copy.deepcopy(self.store.catalog);self.removed=set(self.store.removed)
        self.selected=None;self.loading=False;self.dirty=False;self.busy=False;self.cancel=threading.Event();self.events=queue.Queue();self.renderer=None;self.generation=0
        root.title('XISpeaks - Pocket Voice Catalog');root.geometry(f'{min(1190,root.winfo_screenwidth()-80)}x{min(860,root.winfo_screenheight()-80)}');root.minsize(960,650)
        self.status=tk.StringVar(value=self.catalog_status('Catalog: '+str(self.store.path)))
        self.stats=tk.StringVar(value='Preview a sample to measure its digital peak level and duration.')
        self.noise_mode=tk.StringVar(value='fixed');self.seed=tk.StringVar(value='42')
        self.search=tk.StringVar();self.gender_filter=tk.StringVar(value='All genders')
        self.accent_filter=tk.StringVar(value='All accent groups')
        self.type_filters={kind:tk.BooleanVar() for kind in NPC_TYPES}
        self.type_filter_label=tk.StringVar(value='All NPC types')
        self.label=tk.StringVar();self.gender=tk.StringVar();self.accent=tk.StringVar();self.automatic=tk.BooleanVar()
        self.speed=tk.StringVar(value='100');self.volume=tk.StringVar(value='100');self.model=tk.StringVar();self.speaker=tk.StringVar(value=MODEL)
        self.flags={kind:tk.BooleanVar(value=True) for kind in NPC_TYPES}
        outer=ttk.Frame(root,padding=12);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='Pocket Voice Catalog',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(outer,text='Edit voice properties, audition a sample, then save. Voice IDs remain stable when gender changes.').pack(anchor='w',pady=(0,10))
        toolbar=ttk.Frame(outer);toolbar.pack(fill='x',pady=(0,8))
        for text,command in [('Add voice…',self.add_voice),('Remove selected',self.remove_voice),('Save catalog',self.save),('Reload from disk',self.reload)]:
            ttk.Button(toolbar,text=text,command=command).pack(side='left',padx=(0,6))
        body=ttk.Panedwindow(outer,orient='horizontal');body.pack(fill='both',expand=True)
        left=ttk.Frame(body);right_shell=ttk.Frame(body)
        canvas=tk.Canvas(right_shell,highlightthickness=0);right_scroll=ttk.Scrollbar(right_shell,command=canvas.yview)
        canvas.configure(yscrollcommand=right_scroll.set);right_scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        right=ttk.Frame(canvas,padding=(14,0,8,8));window=canvas.create_window(0,0,window=right,anchor='nw')
        right.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(window,width=event.width))
        root.bind_all('<MouseWheel>',lambda event:canvas.yview_scroll(-int(event.delta/120),'units') if str(event.widget).startswith(str(right)) else None)
        body.add(left,weight=2);body.add(right_shell,weight=3)
        ttk.Label(left,text='Search labels, IDs or model names').pack(anchor='w')
        ttk.Entry(left,textvariable=self.search).pack(fill='x',pady=4)
        box=ttk.Combobox(left,textvariable=self.gender_filter,values=['All genders',*GENDER_LABELS.values()],state='readonly');box.pack(fill='x',pady=4)
        ttk.Combobox(left,textvariable=self.accent_filter,values=['All accent groups',*ACCENT_LABELS.values()],state='readonly').pack(fill='x',pady=4)
        types_button=ttk.Menubutton(left,textvariable=self.type_filter_label)
        types_button.pack(fill='x',pady=4)
        types_menu=tk.Menu(types_button,tearoff=False)
        types_button.configure(menu=types_menu)
        types_menu.add_command(label='All NPC types (clear selections)',command=self.clear_type_filters)
        types_menu.add_separator()
        for kind,var in self.type_filters.items():
            types_menu.add_checkbutton(label=TYPE_LABELS[kind],variable=var,command=self.refresh)
        ttk.Label(left,text='Ctrl-click individual voices or Shift-click a range to edit together.').pack(anchor='w')
        self.count=tk.StringVar();ttk.Label(left,textvariable=self.count).pack(anchor='w')
        table=ttk.Frame(left);table.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(table,columns=('voice','gender','auto'),show='headings',selectmode='extended')
        for col,label,width in [('voice','Voice / label',270),('gender','Gender',60),('auto','Auto',45)]:
            self.tree.heading(col,text=label);self.tree.column(col,width=width,stretch=col=='voice')
        scroll=ttk.Scrollbar(table,command=self.tree.yview);self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        self.tree.bind('<<TreeviewSelect>>',self.select)
        self.bulk=ttk.Frame(right_shell,padding=14)
        self.bulk_title=tk.StringVar()
        ttk.Label(self.bulk,textvariable=self.bulk_title,font=('Segoe UI',12,'bold')).grid(columnspan=2,sticky='w')
        ttk.Label(self.bulk,text='Choose a value to set it for every selected voice. Save catalog to keep your edits.',wraplength=380).grid(columnspan=2,sticky='w',pady=8)
        switches={True:'Yes',False:'No'}
        self.bulk_fields={}
        fields=[('gender','Gender',GENDER_LABELS),('accent','Accent group',ACCENT_LABELS),
                ('automatic','Available for automatic assignment',switches)]
        fields.extend((kind,TYPE_LABELS[kind],switches) for kind in NPC_TYPES)
        for field,title,choices in fields:
            if field==NPC_TYPES[0]:
                ttk.Label(self.bulk,text='Allowed NPC types for automatic assignment').grid(columnspan=2,sticky='w',pady=(12,2))
            row=self.bulk.grid_size()[1]
            ttk.Label(self.bulk,text=title).grid(row=row,column=0,sticky='w',pady=3)
            box=ttk.Combobox(self.bulk,state='readonly',values=list(choices.values()),width=18)
            box.grid(row=row,column=1,sticky='w',padx=6)
            self.bulk_fields[field]=(box,choices)
            box.bind('<<ComboboxSelected>>',lambda event,name=field:self.edit_group(name))
        self.identity=tk.StringVar(value='No voice selected')
        ttk.Label(right,textvariable=self.identity,font=('Segoe UI',12,'bold')).pack(anchor='w')
        form=ttk.Frame(right);form.pack(fill='x',pady=6);form.columnconfigure(1,weight=1)
        fields=[('Label',self.label),('Voice state file',self.model)]
        for row,(title,var) in enumerate(fields):
            ttk.Label(form,text=title).grid(row=row,column=0,sticky='w',padx=(0,8),pady=3)
            if var is self.model:
                self.model_box=ttk.Combobox(form,textvariable=var,values=self.models(),state='readonly');self.model_box.grid(row=row,column=1,sticky='ew')
            else:ttk.Entry(form,textvariable=var).grid(row=row,column=1,sticky='ew')
        for row,(title,var,values) in enumerate([('Gender',self.gender,list(GENDER_LABELS.values())),('Accent group',self.accent,list(ACCENT_LABELS.values()))],3):
            ttk.Label(form,text=title).grid(row=row,column=0,sticky='w',pady=3)
            ttk.Combobox(form,textvariable=var,values=values,state='readonly').grid(row=row,column=1,sticky='ew')
        ttk.Checkbutton(right,text='Available for automatic assignment',variable=self.automatic).pack(anchor='w',pady=6)
        types=ttk.LabelFrame(right,text='Allowed NPC types for automatic assignment',padding=8);types.pack(fill='x',pady=6)
        for i,kind in enumerate(NPC_TYPES):
            ttk.Checkbutton(types,text=TYPE_LABELS[kind],variable=self.flags[kind]).grid(row=i//2,column=i%2,sticky='w',padx=6,pady=2)
        ttk.Label(right,text='All active NPC presets must be allowed. The catalog flags control eligibility for every NPC type.\nManual NPC overrides can use any catalog voice.',wraplength=570).pack(anchor='w')
        tuning=ttk.LabelFrame(right,text='Voice calibration',padding=8);tuning.pack(fill='x',pady=8)
        for i,(title,var,low,high) in enumerate([('Volume (%)',self.volume,0,300),('Speed (%)',self.speed,50,200)]):
            ttk.Label(tuning,text=title).grid(row=i,column=0,sticky='w',padx=6,pady=3)
            ttk.Spinbox(tuning,from_=low,to=high,increment=1,textvariable=var,width=12).grid(row=i,column=1,sticky='w')
        ttk.Label(tuning,text='100% is neutral. Applied in addition to NPC presets and global controls.\nPreview uses global 100%, no race effect, and native Pocket pace.',wraplength=570).grid(row=2,column=0,columnspan=2,sticky='w',pady=5)
        controls=ttk.Frame(right);controls.pack(fill='x')
        ttk.Button(controls,text='Preview voice',command=self.preview).pack(side='left')
        ttk.Button(controls,text='Stop',command=self.stop).pack(side='left',padx=6)
        ttk.Label(right,textvariable=self.stats,wraplength=570).pack(anchor='w',pady=8)
        ttk.Label(right,text='dBFS measures the generated digital audio, not your Windows speaker volume.\nRMS helps compare sustained loudness when peak levels are similar.',wraplength=570).pack(anchor='w')
        ttk.Label(right,text='Sample text (previews use your unsaved edits)').pack(anchor='w')
        self.text=tk.Text(right,height=4,wrap='word');self.text.pack(fill='x',pady=5)
        self.text.insert('1.0','Welcome, adventurer. There is much we have yet to discover beyond these walls.')
        noise=ttk.LabelFrame(right,text='Preview reference (editor only)',padding=8);noise.pack(fill='x',pady=6)
        ttk.Radiobutton(noise,text='Fixed noise / seed',variable=self.noise_mode,value='fixed').grid(row=0,column=0,sticky='w')
        ttk.Radiobutton(noise,text='Zero noise',variable=self.noise_mode,value='zero').grid(row=0,column=1,sticky='w')
        ttk.Label(noise,text='Seed').grid(row=1,column=0,sticky='w')
        self.seed_entry=ttk.Entry(noise,textvariable=self.seed,width=14);self.seed_entry.grid(row=1,column=1,sticky='w')
        self.seed_button=ttk.Button(noise,text='New seed',command=lambda:self.seed.set(str(secrets.randbelow(2147483648))))
        self.seed_button.grid(row=1,column=2,padx=6)
        def noise_changed(*args):
            state='normal' if self.noise_mode.get()=='fixed' else 'disabled'
            self.seed_entry.configure(state=state);self.seed_button.configure(state=state)
        self.noise_mode.trace_add('write',noise_changed)
        ttk.Label(noise,text='Use the same text, mode and seed across voices. Fixed mode is recommended for comparisons. Zero noise uses temperature 0 and may distort delivery or fail to finish naturally. The model stays loaded.',wraplength=570).grid(row=2,column=0,columnspan=3,sticky='w',pady=4)
        ttk.Separator(outer).pack(fill='x',pady=8)
        ttk.Label(outer,textvariable=self.status,wraplength=1130).pack(anchor='w')
        self.search.trace_add('write',lambda *args:self.refresh())
        self.accent_filter.trace_add('write',lambda *args:self.refresh())
        self.gender_filter.trace_add('write',lambda *args:self.refresh())
        for var in [self.label,self.gender,self.accent,self.automatic,self.volume,self.speed,self.model,self.speaker,*self.flags.values()]:
            var.trace_add('write',self.changed)
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(100,self.poll);self.refresh()

    def models(self):return sorted(p.name for p in self.store.path.parent.glob('*.safetensors'))
    def catalog_status(self,message):
        if self.store.missing_removed:
            return f'Removed {len(self.store.missing_removed)} voices with missing files; original catalog saved in catalog-backups. '+message
        return message
    def error(self,exc):messagebox.showerror('Voice catalog',str(exc),parent=self.root)
    def changed(self,*args):
        if not self.loading and self.selected:
            self.dirty=True;self.status.set('Unsaved edits. Preview uses these settings; Save catalog applies them to the companion.')
    def draft(self):
        if not self.selected:raise ValueError('Select a voice first')
        entry=copy.deepcopy(self.catalog[self.selected])
        entry.update(label=self.label.get().strip(),model=self.model.get(),speaker_id=None,
            gender=next(k for k,v in GENDER_LABELS.items() if v==self.gender.get()),
            accent=next(k for k,v in ACCENT_LABELS.items() if v==self.accent.get()),automatic=self.automatic.get(),
            volume=float(self.volume.get())/100,speed=float(self.speed.get())/100,npc_types={kind:var.get() for kind,var in self.flags.items()})
        return validate({self.selected:entry},self.store.path.parent)[self.selected]
    def stage(self):
        if self.selected:self.catalog[self.selected]=self.draft()
    def clear_type_filters(self):
        for var in self.type_filters.values():var.set(False)
        self.refresh()

    def refresh(self):
        if self.loading:return
        try:self.stage()
        except Exception as exc:self.status.set(str(exc));return
        self.loading=True
        selected=self.tree.selection();query=self.search.get().casefold();gender=self.gender_filter.get()
        accent=self.accent_filter.get()
        required=[kind for kind,var in self.type_filters.items() if var.get()]
        self.type_filter_label.set('Allows: '+' + '.join(kind.title() for kind in required) if required else 'All NPC types')
        self.tree.delete(*self.tree.get_children())
        for key,entry in sorted(self.catalog.items()):
            if query not in (key+' '+entry['label']+' '+entry['model']).casefold():continue
            if gender!='All genders' and GENDER_LABELS[entry['gender']]!=gender:continue
            if accent!='All accent groups' and ACCENT_LABELS[entry['accent']]!=accent:continue
            if any(not entry['npc_types'][kind] for kind in required):continue
            self.tree.insert('','end',iid=key,values=(key+' — '+entry['label'],entry['gender'],'yes' if entry['automatic'] else 'no'))
        self.tree.selection_set([key for key in selected if self.tree.exists(key)])
        self.count.set(f'{len(self.tree.get_children())} shown / {len(self.catalog)} voices')
        self.loading=False
    def show(self,key):
        self.loading=True;self.selected=key;entry=self.catalog[key];self.identity.set(key)
        self.label.set(entry['label']);self.model.set(entry['model']);self.speaker.set('' if entry['speaker_id'] is None else str(entry['speaker_id']))
        self.gender.set(GENDER_LABELS[entry['gender']]);self.accent.set(ACCENT_LABELS[entry['accent']]);self.automatic.set(entry['automatic'])
        self.volume.set(f"{entry['volume']*100:g}");self.speed.set(f"{entry['speed']*100:g}")
        for kind,var in self.flags.items():var.set(entry['npc_types'][kind])
        self.loading=False
    def select(self,event=None):
        if self.loading:return
        selection=self.tree.selection()
        if selection==(self.selected,):
            self.bulk.place_forget()
            return
        try:
            self.stage()
        except Exception as exc:
            if self.selected and self.tree.exists(self.selected):self.tree.selection_set(self.selected)
            self.error(exc)
            return
        self.selected=None
        if len(selection)>1:
            self.bulk_title.set(f'Edit {len(selection):,} selected voices')
            for field,(box,choices) in self.bulk_fields.items():
                values={self.catalog[key]['npc_types'][field] if field in NPC_TYPES else self.catalog[key][field] for key in selection}
                box.set(choices[values.pop()] if len(values)==1 else 'Mixed')
            self.bulk.place(x=0,y=0,relwidth=1,relheight=1)
            self.bulk.lift()
        else:
            self.bulk.place_forget()
            if selection:self.show(selection[0])
            else:self.identity.set('Select a voice')

    def edit_group(self,field):
        selection=self.tree.selection()
        if len(selection)<2:return
        box,choices=self.bulk_fields[field]
        value=next(key for key,label in choices.items() if label==box.get())
        for key in selection:
            entry=self.catalog[key]
            target=entry['npc_types'] if field in NPC_TYPES else entry
            target[field]=value
        self.dirty=True
        self.refresh()
        self.status.set(f'Updated {len(selection):,} voices. Save catalog to keep these edits.')
    def save(self):
        try:
            self.stage();self.store.save(self.catalog,self.removed)
            self.catalog=copy.deepcopy(self.store.catalog);self.removed=set(self.store.removed);self.dirty=False
            self.refresh();self.status.set('Catalog saved with a backup. The updated companion reloads it automatically; the current line finishes first.')
        except Exception as exc:self.error(exc)
    def reload(self):
        if self.dirty and not messagebox.askyesno('Discard unsaved edits?','Reload the catalog from disk and discard unsaved edits?',parent=self.root):return
        try:
            self.store.reload();self.catalog=copy.deepcopy(self.store.catalog);self.removed=set(self.store.removed)
            self.selected=None;self.dirty=False;self.refresh();self.identity.set('Select a voice');self.model_box['values']=self.models()
            self.status.set(self.catalog_status('Catalog reloaded.'))
        except Exception as exc:self.error(exc)
    def remove_voice(self):
        keys=list(self.tree.selection())
        if not keys:return
        if len(keys)>=len(self.catalog):self.error('Keep one catalog entry; you may disable its automatic assignment.');return
        self.stop();self.selected=None
        for key in keys:
            del self.catalog[key];self.removed.add(key)
        self.dirty=True;self.identity.set('No voice selected');self.refresh()
        self.status.set(f'{len(keys)} voices removed from the draft catalog. Save to apply. Voice files are retained.')
    def add_voice(self):
        try:self.stage()
        except Exception as exc:self.error(exc);return
        dialog=tk.Toplevel(self.root);dialog.title('Add Pocket voice');dialog.transient(self.root);dialog.grab_set()
        frame=ttk.Frame(dialog,padding=16);frame.pack(fill='both',expand=True)
        key=tk.StringVar(value='au_new_voice');model=tk.StringVar();speaker=tk.StringVar(value=MODEL)
        for row,(title,var) in enumerate([('Stable ID',key),('Voice state file',model)]):
            ttk.Label(frame,text=title).grid(row=row,column=0,sticky='w',padx=6,pady=6)
            if var is model:
                model_box=ttk.Combobox(frame,textvariable=var,values=self.models(),state='readonly',width=38);model_box.grid(row=row,column=1)
            else:ttk.Entry(frame,textvariable=var,width=40).grid(row=row,column=1)
        help_text=tk.StringVar(value='Import a voice state exported for English 18M (2026-10). Other Pocket models are incompatible.')
        ttk.Label(frame,textvariable=help_text,wraplength=520).grid(row=3,column=0,columnspan=2,sticky='w')
        def model_changed(*args):
            try:
                validate_state(self.store.path.parent/model.get())
                help_text.set('Compatible English 18M state; one voice per file.')
            except Exception as exc:help_text.set(str(exc))
        model.trace_add('write',model_changed)
        def import_model():
            source=filedialog.askopenfilename(parent=dialog,filetypes=[('Pocket 18M voice state','*.safetensors')])
            if not source:return
            try:
                source=Path(source)
                validate_state(source)
                destination=self.store.path.parent/source.name
                if source.resolve()!=destination.resolve():
                    if destination.exists():raise ValueError('A voice state with this filename already exists. Rename the imported file first.')
                    shutil.copyfile(source,destination)
                model_box['values']=self.models();self.model_box['values']=self.models();model.set(destination.name)
            except Exception as exc:self.error(exc)
        def add():
            try:
                identity=key.get().strip()
                if identity in self.catalog:raise ValueError('That voice ID already exists')
                item=normalize(identity,dict(model=model.get(),engine_model=MODEL,speaker_id=None,automatic=False,stock=False))
                item=validate({identity:item},self.store.path.parent)[identity]
                self.catalog[identity]=item;self.removed.discard(identity);self.dirty=True
                self.selected=None;self.clear_type_filters();self.accent_filter.set('All accent groups')
                self.search.set('');self.gender_filter.set('All genders');self.refresh();self.tree.selection_set(identity);self.show(identity)
                self.status.set('Voice added to draft. Set its properties, then save the catalog.');dialog.destroy()
            except Exception as exc:self.error(exc)
        ttk.Button(frame,text='Import model…',command=import_model).grid(row=4,column=0,pady=10)
        ttk.Button(frame,text='Add to catalog',command=add).grid(row=4,column=1,pady=10)
    def preview(self):
        if self.busy:self.error('Stop the current preview before starting another.');return
        try:
            entry=self.draft();key=self.selected;text=self.text.get('1.0','end').strip()
            if not 1<=len(text)<=1200:raise ValueError('Enter 1–1200 characters of sample text')
            mode=self.noise_mode.get();seed=int(self.seed.get()) if mode=='fixed' else 42
            if not 0<=seed<=2147483647:raise ValueError('Seed must be between 0 and 2147483647')
            reference=f'Fixed seed {seed}' if mode=='fixed' else 'Zero noise'
            self.stop();self.cancel=threading.Event();cancel=self.cancel;self.busy=True;generation=self.generation
            OUTPUT.mkdir(parents=True,exist_ok=True);path=OUTPUT/f'preview-{time.time_ns()}.wav'
            self.stats.set(f'Generating {key}…')
            def work():
                try:
                    if self.renderer is None:self.renderer=Renderer()
                    metrics=self.renderer.render(key,entry,self.store.path.parent,text,path,cancel.is_set,mode=mode,seed=seed)
                    self.events.put(('preview',generation,key,path,metrics,reference))
                except Exception as exc:self.events.put(('error',generation,str(exc)))
            threading.Thread(target=work,daemon=True).start()
        except Exception as exc:self.error(exc)
    def stop(self):
        self.cancel.set();self.generation+=1;winsound.PlaySound(None,0)
        # Worker owns the ONNX sessions until it reports completion.
    def poll(self):
        while not self.events.empty():
            event=self.events.get();kind,generation=event[:2];self.busy=False
            if generation!=self.generation:continue
            if kind=='error':self.stats.set('Preview failed: '+event[2]);continue
            _,_,key,path,metrics,reference=event
            if metrics is None:continue
            def level(value):return 'silence' if value is None else f'{value:.2f} dBFS'
            description=f"{key} ({reference}) — Peak: {level(metrics['peak_dbfs'])} ({metrics['peak']*100:.1f}% full scale) | RMS: {level(metrics['rms_dbfs'])}\nDuration: {metrics['seconds']:.3f} seconds ({metrics['milliseconds']} ms)"
            self.stats.set('Playing: '+description)
            try:winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC)
            except RuntimeError as exc:self.stats.set('Playback failed: '+str(exc));continue
            self.root.after(metrics['milliseconds']+100,lambda g=generation,d=description:self.stats.set(d) if g==self.generation else None)
        self.root.after(100,self.poll)
    def close(self):
        if self.dirty and not messagebox.askyesno('Unsaved edits','Close without saving catalog edits?',parent=self.root):return
        self.stop();self.root.destroy()

if __name__=='__main__':
    root=tk.Tk()
    try:
        import argparse
        parser=argparse.ArgumentParser();parser.add_argument('--catalog',type=Path,default=VOICES/'catalog.json')
        Editor(root,parser.parse_args().catalog)
    except Exception as exc:messagebox.showerror('Voice catalog',str(exc));root.destroy();raise
    root.mainloop()
