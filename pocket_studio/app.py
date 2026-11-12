"""Separate Windows workbench for creating Pocket 18M voice profiles."""
import json
from pathlib import Path
import queue
import secrets
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
import webbrowser
import winsound
import studio_engine as engine
from voice_catalog import NPC_TYPES

class Studio:
    def __init__(self,root):
        self.root=root;self.engine=engine.Engine();self.events=queue.Queue();self.busy=False;self.cancel=threading.Event();self.record_stop=threading.Event()
        self.project=None;self.info=None;self.candidates={};self.results={};self.buttons=[];self.drag_start=None;self.regions=[]
        root.title('XISpeaks — Pocket Cloning Studio');root.geometry('1180x860');root.minsize(1000,720)
        main=ttk.Frame(root,padding=12);main.pack(fill='both',expand=True)
        ttk.Label(main,text='Pocket Cloning Studio',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(main,text='Record or import → choose a reference → compare candidates → install the keeper. English 18M.').pack(anchor='w',pady=(0,10))
        self.tabs=ttk.Notebook(main);self.tabs.pack(fill='both',expand=True)
        self.reference=ttk.Frame(self.tabs,padding=12);self.compare=ttk.Frame(self.tabs,padding=12);self.export_tab=ttk.Frame(self.tabs,padding=12);self.setup=ttk.Frame(self.tabs,padding=12)
        for frame,title in [(self.reference,'1  Reference'),(self.compare,'2  Candidates & auditions'),(self.export_tab,'3  Export / install'),(self.setup,'Model setup')]:self.tabs.add(frame,text=title)
        self.source=tk.StringVar(value='Import an audio/video file, or record a volunteer.');self.start=tk.StringVar(value='0');self.end=tk.StringVar(value='26')
        self.denoise=tk.StringVar(value='Off');self.normalize=tk.BooleanVar(value=True);self.candidate_name=tk.StringVar(value='Candidate 1')
        self.stats=tk.StringVar(value='Choose a clean, single-speaker segment of 3–30 seconds.')
        self.mic=tk.StringVar();self.device_map={}
        row=ttk.Frame(self.reference);row.pack(fill='x')
        self.button(row,'New session: import…',self.import_file).pack(side='left',padx=3)
        self.button(row,'Open saved project…',self.open_project).pack(side='left',padx=3)
        self.button(row,'Refresh microphones',self.refresh_mics).pack(side='left',padx=3)
        self.mic_box=ttk.Combobox(row,textvariable=self.mic,state='readonly',width=27);self.mic_box.pack(side='left',padx=4)
        self.button(row,'Record',self.record).pack(side='left',padx=3)
        ttk.Button(row,text='Stop recording',command=self.record_stop.set).pack(side='left',padx=3)
        ttk.Label(self.reference,textvariable=self.source,wraplength=1080).pack(anchor='w',pady=10)
        self.canvas=tk.Canvas(self.reference,height=130,background='#142536',highlightthickness=0);self.canvas.pack(fill='x')
        self.canvas.bind('<Configure>',lambda e:self.draw());self.canvas.bind('<ButtonPress-1>',self.begin_selection);self.canvas.bind('<B1-Motion>',self.drag_selection)
        ttk.Label(self.reference,text='Drag or enter start/end, then Add region for each clean section. Kept regions play in recording order; total must be 3–30 seconds.').pack(anchor='w',pady=5)
        row=ttk.Frame(self.reference);row.pack(fill='x',pady=5)
        for label,var in [('Start (seconds)',self.start),('End (seconds)',self.end)]:
            ttk.Label(row,text=label).pack(side='left',padx=5);ttk.Entry(row,textvariable=var,width=12).pack(side='left',padx=5)
        ttk.Label(row,text='Denoise').pack(side='left',padx=5)
        ttk.Combobox(row,textvariable=self.denoise,values=list(engine.DENoise),state='readonly',width=12).pack(side='left')
        ttk.Checkbutton(row,text='Normalize peak to −3 dBFS (gain capped at +24 dB)',variable=self.normalize).pack(side='left',padx=10)
        for var in (self.start,self.end):var.trace_add('write',lambda *args:self.draw())
        regions_row=ttk.Frame(self.reference);regions_row.pack(fill='x',pady=4)
        self.region_list=tk.Listbox(regions_row,height=3,exportselection=False,width=42)
        self.region_list.pack(side='left',fill='x',expand=True)
        scroll=ttk.Scrollbar(regions_row,command=self.region_list.yview);scroll.pack(side='left',fill='y');self.region_list.configure(yscrollcommand=scroll.set)
        self.region_list.bind('<<ListboxSelect>>',self.region_selected)
        controls=ttk.Frame(regions_row);controls.pack(side='left',padx=8)
        for title,action in [('Add region',self.add_region),('Update selected',self.update_region),('Remove selected',self.remove_region),('Clear regions',self.clear_regions)]:
            self.button(controls,title,action).pack(side='left',padx=2)
        self.region_total=tk.StringVar(value='No regions added: uses the current start/end selection.')
        ttk.Label(self.reference,textvariable=self.region_total).pack(anchor='w')
        ttk.Label(self.reference,text='Denoising is optional. Start with Light; stronger cleanup can change the voice. It does not remove other speakers or restore clipped audio.',wraplength=1060).pack(anchor='w',pady=6)
        row=ttk.Frame(self.reference);row.pack(fill='x',pady=6)
        self.button(row,'Preview current section',self.preview_section).pack(side='left',padx=3)
        self.button(row,'Play combined original',lambda:self.prepare_preview(False)).pack(side='left',padx=3)
        self.button(row,'Play combined prepared',lambda:self.prepare_preview(True)).pack(side='left',padx=3)
        ttk.Button(row,text='Stop audio',command=self.stop_audio).pack(side='left',padx=3)
        ttk.Label(self.reference,textvariable=self.stats,wraplength=1060).pack(anchor='w',pady=8)
        row=ttk.Frame(self.reference);row.pack(fill='x',pady=10)
        ttk.Label(row,text='Candidate name').pack(side='left',padx=3);ttk.Entry(row,textvariable=self.candidate_name,width=38).pack(side='left',padx=5)
        self.button(row,'Create voice candidate',self.clone).pack(side='left',padx=6)
        ttk.Label(self.reference,text='For another candidate, select a different excerpt or cleanup setting. No transcript or training epochs are required.',wraplength=1060).pack(anchor='w')
        self.build_compare();self.build_export();self.build_setup()
        footer=ttk.Frame(main);footer.pack(fill='x',pady=(10,0))
        self.status=tk.StringVar(value='Ready. Recordings, cloning and auditions stay on this computer.')
        ttk.Label(footer,textvariable=self.status,wraplength=960).pack(anchor='w')
        self.progress=ttk.Progressbar(footer,maximum=100);self.progress.pack(side='left',fill='x',expand=True,pady=6)
        ttk.Button(footer,text='Cancel task',command=self.cancel_task).pack(side='left',padx=6)
        root.after(100,self.poll);root.protocol('WM_DELETE_WINDOW',self.close)

    def button(self,parent,text,command):
        button=ttk.Button(parent,text=text,command=lambda:self.guarded(command));self.buttons.append(button);return button
    def guarded(self,fn):
        try:fn()
        except Exception as exc:messagebox.showerror('Pocket Studio',str(exc),parent=self.root)
    def progress_event(self,label,value=None):self.events.put(('progress',label,value))
    def job(self,label,work,done=lambda result:None):
        if self.busy:raise ValueError('Wait for the current task or cancel it first.')
        self.busy=True;self.cancel=threading.Event();self.status.set(label)
        for b in self.buttons:b.configure(state='disabled')
        self.progress.configure(mode='indeterminate');self.progress.start(12)
        def run():
            try:self.events.put(('done',done,work(self.cancel.is_set)))
            except engine.Cancelled:self.events.put(('cancelled',))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=run,daemon=True).start()
    def poll(self):
        while not self.events.empty():
            event=self.events.get()
            if event[0]=='progress':
                _,label,value=event;self.status.set(label)
                if value is None:self.progress.configure(mode='indeterminate');self.progress.start(12)
                else:self.progress.stop();self.progress.configure(mode='determinate',value=value)
                continue
            self.busy=False;self.progress.stop();self.progress.configure(mode='determinate',value=100 if event[0]=='done' else 0)
            for b in self.buttons:b.configure(state='normal')
            if event[0]=='done':
                self.status.set('Ready.');self.guarded(lambda:event[1](event[2]))
            elif event[0]=='error':self.status.set('Task failed: '+event[1]);messagebox.showerror('Pocket Studio',event[1],parent=self.root)
            else:self.status.set('Task cancelled. Existing candidates are unchanged.')
        self.root.after(100,self.poll)
    def cancel_task(self):
        self.cancel.set();self.stop_audio()
        if self.busy:self.status.set('Cancelling; model loading/encoding or downloads finish the current stage first.')
    def stop_audio(self):winsound.PlaySound(None,0)
    def play(self,path):winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC)
    def close(self):
        if self.busy:
            self.cancel_task();self.status.set('Cancelling. Close the window again once the current task finishes.');return
        try:self.save_audition_text()
        except OSError as exc:
            messagebox.showerror('Could not save audition text',str(exc),parent=self.root);return
        self.stop_audio();self.root.destroy()

    def import_file(self):
        file=filedialog.askopenfilename(parent=self.root,title='Import volunteer audio or video',filetypes=[('Audio and video','*.wav *.flac *.mp3 *.m4a *.aac *.ogg *.opus *.wma *.aiff *.aif *.mp4 *.mkv *.mov *.avi *.webm *.m4v *.wmv'),('All files','*.*')])
        if file:self.job('Inspecting media…',lambda cancel:engine.probe(file,cancel),self.choose_track)
    def choose_track(self,info):
        if len(info['tracks'])==1:self.import_track(info,info['tracks'][0]['index']);return
        dialog=tk.Toplevel(self.root);dialog.title('Choose audio track');dialog.transient(self.root);dialog.grab_set()
        labels={f"Track {s['index']} · {s['codec']} · {s['channels']} channels · {s['language']} {s['title']}":s['index'] for s in info['tracks']}
        value=tk.StringVar(value=next(iter(labels)))
        ttk.Label(dialog,text='Select the track containing the volunteer, without music if possible.').pack(padx=20,pady=12)
        ttk.Combobox(dialog,textvariable=value,values=list(labels),state='readonly',width=78).pack(padx=20,pady=10)
        def accept():
            track=labels[value.get()];dialog.destroy();self.import_track(info,track)
        ttk.Button(dialog,text='Extract audio',command=accept).pack(pady=12)
    def import_track(self,info,track):self.job('Converting to working WAV…',lambda cancel:engine.import_media(info,track,cancel,self.progress_event),self.loaded)
    def loaded(self,result):
        self.project,self.info=result;self.stop_audio();self.source.set(str(self.project)+'\nSource: '+Path(self.info['source']['path']).name)
        self.regions=[tuple(r) for r in self.info.get('regions',[])];self.refresh_regions()
        self.start.set('0');self.end.set(str(round(min(26,self.info['summary']['seconds']),3)))
        self.stats.set(self.describe(self.info['summary']));self.refresh_candidates();self.candidate_name.set('Candidate '+str(len(self.candidates)+1));self.draw();self.tabs.select(self.reference)
    def open_project(self):
        file=filedialog.askopenfilename(parent=self.root,title='Open Pocket project',initialdir=engine.OUTPUT,filetypes=[('Pocket project','project.json')])
        if file:
            project=Path(file).parent;info=json.loads(Path(file).read_text());info['summary']=engine.inspect_wav(project/'source.wav');self.loaded((project,info))
    def draw(self):
        self.canvas.delete('all')
        if not self.info:return
        w=self.canvas.winfo_width();h=self.canvas.winfo_height();duration=self.info['summary']['seconds'];points=self.info['summary']['points']
        try:
            start=float(self.start.get());end=float(self.end.get());self.canvas.create_rectangle(max(0,start)/duration*w,0,min(duration,end)/duration*w,h,fill='#254f6a',outline='')
        except ValueError:pass
        for a,b in self.regions:
            self.canvas.create_rectangle(a/duration*w,0,b/duration*w,h,outline='#77dd88',width=2)
        stride=max(1,len(points)//max(1,w))
        for i in range(0,len(points),stride):
            low,high=points[i];x=i/max(1,len(points)-1)*w
            self.canvas.create_line(x,h/2-high*h*.46,x,h/2-low*h*.46,fill='#7ce3f4')
        self.canvas.create_text(8,10,text=f'{duration:.2f} seconds',anchor='nw',fill='white')
    def begin_selection(self,event):
        if self.info and not self.busy:self.drag_start=max(0,min(1,event.x/max(1,self.canvas.winfo_width())))*self.info['summary']['seconds']
    def drag_selection(self,event):
        if self.drag_start is None or self.busy:return
        t=max(0,min(1,event.x/max(1,self.canvas.winfo_width())))*self.info['summary']['seconds'];self.start.set(f'{min(t,self.drag_start):.3f}');self.end.set(f'{max(t,self.drag_start):.3f}')
    def refresh_regions(self):
        self.region_list.delete(0,'end')
        for a,b in self.regions:self.region_list.insert('end',f'{a:.3f} – {b:.3f} s   ({b-a:.3f} s)')
        self.region_total.set(f'{len(self.regions)} kept regions · {sum(b-a for a,b in self.regions):.3f} seconds total (3–30 required)' if self.regions else 'No regions added: uses the current start/end selection.')
        self.draw()
    def save_regions(self,regions):
        if self.project is None:raise ValueError('Import a recording first.')
        regions=engine.clean_regions(regions,self.info['summary']['seconds']) if regions else []
        updated=dict(self.info,regions=regions);engine.atomic_json(self.project/'project.json',updated)
        self.info=updated;self.regions=regions;self.refresh_regions()
    def add_region(self):self.save_regions(self.regions+[(float(self.start.get()),float(self.end.get()))])
    def region_selected(self,event=None):
        selected=self.region_list.curselection()
        if selected:
            a,b=self.regions[selected[0]];self.start.set(str(a));self.end.set(str(b))
    def update_region(self):
        selected=self.region_list.curselection()
        if not selected:raise ValueError('Select a kept region to update.')
        regions=list(self.regions);regions[selected[0]]=(float(self.start.get()),float(self.end.get()));self.save_regions(regions)
    def remove_region(self):
        selected=self.region_list.curselection()
        if selected:self.save_regions([r for i,r in enumerate(self.regions) if i!=selected[0]])
    def clear_regions(self):self.save_regions([])
    def selected_reference(self):
        if self.project is None:raise ValueError('Import or record a reference first.')
        return self.project,float(self.start.get()),float(self.end.get()),self.denoise.get(),self.normalize.get()
    @staticmethod
    def describe(m):
        def db(v):return 'silence' if v is None else f'{v:.2f} dBFS'
        return f"{m['seconds']:.3f}s · Peak {db(m['peak_dbfs'])} · RMS {db(m['rms_dbfs'])} · Near-clipped samples {m['clipped_percent']:.2f}%"
    def preview_section(self):
        project,start,end,_,_=self.selected_reference()
        self.stop_audio()
        self.job('Preparing current section…',lambda cancel:engine.preview_section(project,start,end,cancel),self.play)
    def prepare_preview(self,cleaned):
        args=self.selected_reference();regions=list(self.regions) or None
        def done(result):
            folder,meta=result;self.stats.set('Original: '+self.describe(meta['original'])+'\nPrepared: '+self.describe(meta['prepared'])+f" · Gain {meta['gain_db']:+.1f} dB")
            self.play(folder/('reference.wav' if cleaned else 'original.wav'))
        self.job('Preparing selection…',lambda cancel:engine.prepare(*args,cancel=cancel,regions=regions),done)
    def clone(self):
        args=self.selected_reference();regions=list(self.regions) or None;label=self.candidate_name.get()
        def work(cancel):
            self.progress_event('Preparing reference',None);folder,_=engine.prepare(*args,cancel=cancel,regions=regions)
            return self.engine.clone(args[0],folder,label,cancel,self.progress_event)
        def done(result):
            self.refresh_candidates(result[0].name);self.candidate_name.set('Candidate '+str(len(self.candidates)+1));self.tabs.select(self.compare)
        self.job('Creating candidate…',work,done)
    def refresh_mics(self):
        def done(devices):
            self.device_map={f'{i}: {name}':i for i,name in devices};self.mic_box.configure(values=list(self.device_map))
            if devices:self.mic.set(next(iter(self.device_map)))
            else:self.status.set('No microphone inputs found.')
        self.job('Finding microphones…',lambda cancel:engine.microphones(),done)
    def record(self):
        if self.mic.get() not in self.device_map:raise ValueError('Refresh microphones and select an input first.')
        self.record_stop=threading.Event();device=self.device_map[self.mic.get()]
        def work(cancel):
            file=engine.record(device,self.record_stop,cancel,self.progress_event);return engine.probe(file,cancel)
        self.job('Recording…',work,self.choose_track)

    def build_compare(self):
        ttk.Label(self.compare,text='Select one or more candidates with Ctrl/Shift to compare on the same lines and seeds.').pack(anchor='w')
        self.tree=ttk.Treeview(self.compare,columns=('name','reference','cleanup','size'),show='headings',height=6,selectmode='extended')
        for key,title,width in [('name','Candidate',280),('reference','Reference',140),('cleanup','Denoise',120),('size','Voice size',120)]:self.tree.heading(key,text=title);self.tree.column(key,width=width)
        self.tree.pack(fill='x',pady=8)
        row=ttk.Frame(self.compare);row.pack(fill='x')
        self.button(row,'Play prepared reference',lambda:self.play(self.one_candidate()/'reference.wav')).pack(side='left',padx=3)
        self.button(row,'Play original reference',lambda:self.play(self.one_candidate()/'original.wav')).pack(side='left',padx=3)
        self.button(row,'Rename',self.rename_candidate).pack(side='left',padx=3)
        self.button(row,'Archive selected drafts',self.archive_candidates).pack(side='left',padx=3)
        ttk.Button(row,text='Stop audio',command=self.stop_audio).pack(side='left',padx=3)
        ttk.Label(self.compare,text='Audition text — one test line per row (up to 6). Uses the public playback model, with neutral pitch/speed/volume.').pack(anchor='w',pady=(10,3))
        self.audition_save_timer=None
        self.text=tk.Text(self.compare,height=6,wrap='word');self.text.pack(fill='x');self.text.insert('1.0',engine.load_audition_text())
        self.text.edit_modified(False);self.text.bind('<<Modified>>',self.audition_text_changed)
        self.button(self.compare,'Reset audition text to default',self.reset_audition_text).pack(anchor='w',pady=3)
        row=ttk.Frame(self.compare);row.pack(fill='x',pady=6)
        self.seeds=tk.StringVar(value='42');ttk.Label(row,text='Seeds (comma separated, up to 4)').pack(side='left');ttk.Entry(row,textvariable=self.seeds,width=23).pack(side='left',padx=5)
        self.button(row,'New seed',lambda:self.seeds.set(str(secrets.randbelow(2147483648)))).pack(side='left',padx=3)
        self.button(row,'Audition selected',self.audition).pack(side='left',padx=3)
        self.result_tree=ttk.Treeview(self.compare,columns=('label','line','seed','duration','rms','warnings'),show='headings',height=7)
        for key,title,width in [('label','Candidate',200),('line','Text',350),('seed','Seed',85),('duration','Seconds',75),('rms','RMS dBFS',90),('warnings','Review',90)]:self.result_tree.heading(key,text=title);self.result_tree.column(key,width=width)
        self.result_tree.pack(fill='both',expand=True,pady=6)
        self.button(self.compare,'Play selected audition',self.play_result).pack(anchor='w')
        self.result_tree.bind('<Double-1>',lambda e:self.guarded(self.play_result))
    def audition_text_changed(self,event=None):
        if not self.text.edit_modified():return
        self.text.edit_modified(False)
        if self.audition_save_timer is not None:self.root.after_cancel(self.audition_save_timer)
        self.audition_save_timer=self.root.after(500,lambda:self.guarded(self.save_audition_text))
    def save_audition_text(self):
        if self.audition_save_timer is not None:self.root.after_cancel(self.audition_save_timer)
        self.audition_save_timer=None
        engine.save_audition_text(self.text.get('1.0','end-1c'))
    def reset_audition_text(self):
        self.text.delete('1.0','end');self.text.insert('1.0',engine.DEFAULT_AUDITION_TEXT)
        self.save_audition_text()
    def refresh_candidates(self,selected=None):
        self.tree.delete(*self.tree.get_children());self.candidates={};self.results={};self.result_tree.delete(*self.result_tree.get_children())
        if not self.project:return
        for folder in sorted(self.project.glob('candidate-*')):
            if not (folder/'candidate.json').is_file():continue
            meta=json.loads((folder/'candidate.json').read_text());self.candidates[folder.name]=folder;p=meta['processing']
            self.tree.insert('', 'end',iid=folder.name,values=(meta['label'],f"{p['prepared']['seconds']:.2f}s / {len(p.get('regions', [1]))} regions",p['denoise'],f"{(folder/'voice.safetensors').stat().st_size/1e6:.2f} MB"))
            for file in sorted(folder.glob('preview-*.json')):
                result=json.loads(file.read_text());result.update(candidate=str(folder),file=str(folder/Path(result['file']).name),label=meta['label']);self.add_result(result)
        if selected and selected in self.candidates:self.tree.selection_set(selected)
    def chosen(self):
        items=self.tree.selection()
        if not items:raise ValueError('Select at least one candidate.')
        return [self.candidates[i] for i in items]
    def one_candidate(self):
        items=self.chosen()
        if len(items)!=1:raise ValueError('Select exactly one candidate.')
        return items[0]
    def rename_candidate(self):
        folder=self.one_candidate();p=folder/'candidate.json';meta=json.loads(p.read_text());label=simpledialog.askstring('Candidate name','Name:',initialvalue=meta['label'],parent=self.root)
        if label and label.strip():meta['label']=label.strip()[:100];engine.atomic_json(p,meta);self.refresh_candidates(folder.name)
    def archive_candidates(self):
        items=self.chosen();self.stop_audio();archive=self.project/'archived';archive.mkdir(exist_ok=True)
        for folder in items:folder.rename(archive/folder.name)
        self.refresh_candidates();self.status.set('Drafts moved to the project’s archived folder; no recordings were deleted.')
    def audition(self):
        candidates=self.chosen();texts=[s.strip() for s in self.text.get('1.0','end').splitlines() if s.strip()];seeds=[int(s.strip()) for s in self.seeds.get().split(',')]
        self.job('Generating auditions…',lambda cancel:self.engine.audition(candidates,texts,seeds,cancel,self.progress_event),lambda results:[self.add_result(r) for r in results])
    def add_result(self,result):
        key=self.result_tree.insert('','end',values=(result['label'],result['text'],result['seed'],f"{result['metrics']['seconds']:.3f}",f"{result['metrics']['rms_dbfs']:.2f}" if result['metrics']['rms_dbfs'] is not None else 'silent','Warning' if result['warnings'] else ''))
        self.results[key]=result
    def play_result(self):
        selected=self.result_tree.selection()
        if not selected:raise ValueError('Select an audition from the results table.')
        result=self.results[selected[0]];self.play(result['file']);self.status.set(self.describe(result['metrics'])+(' · '+'; '.join(result['warnings']) if result['warnings'] else ''))

    def build_export(self):
        ttk.Label(self.export_tab,text='Choose the keeper on the Candidates tab, then fill in its catalog information. Choose whether the voice is available for automatic assignment.',wraplength=1050).pack(anchor='w',pady=8)
        form=ttk.Frame(self.export_tab);form.pack(fill='x');form.columnconfigure(1,weight=1)
        self.fields={}
        defaults=[('id','Stable voice ID','xu_new_voice'),('label','Display name','New volunteer'),('gender','Gender','u'),('accent','Accent group','x'),('credit','Speaker credit',''),('permission','Permission / distribution notes',''),('npc','Intended NPC (optional note)','')]
        for row,(key,title,value) in enumerate(defaults):
            var=tk.StringVar(value=value);self.fields[key]=var;ttk.Label(form,text=title).grid(row=row,column=0,sticky='w',padx=6,pady=7)
            if key in ('gender','accent'):widget=ttk.Combobox(form,textvariable=var,state='readonly',values=['m','f','a','u'] if key=='gender' else ['a','b','x'],width=18)
            else:widget=ttk.Entry(form,textvariable=var,width=65)
            widget.grid(row=row,column=1,sticky='ew',pady=7)
        for key in ('label','gender','accent'):
            self.fields[key].trace_add('write',self.update_voice_id)
        self.update_voice_id()
        ttk.Label(self.export_tab,text='Gender: m masculine, f feminine, a androgynous, u unknown. Accent: a US/Canada, b UK/Ireland, x other/unknown.\nIDs use a/b/x + m/f/a/u, an underscore, then lowercase letters/numbers/underscores (for example bm_halver).',wraplength=1060).pack(anchor='w',pady=8)
        self.automatic=tk.BooleanVar(value=False)
        ttk.Checkbutton(self.export_tab,text='Available for automatic assignment',variable=self.automatic).pack(anchor='w',pady=4)
        flags=ttk.LabelFrame(self.export_tab,text='NPC eligibility for automatic assignment',padding=10);flags.pack(fill='x',pady=8)
        self.flags={}
        for i,kind in enumerate(NPC_TYPES):
            var=tk.BooleanVar(value=True);self.flags[kind]=var;ttk.Checkbutton(flags,text=kind.title(),variable=var).grid(row=i//4,column=i%4,sticky='w',padx=18,pady=4)
        default=Path('D:/Games/CatsEyeXi/catseyexi-client/Vanacore/addons/ashita/XISpeaksPocket/companion/pocket_voices/catalog.json')
        self.catalog=tk.StringVar(value=str(default if default.exists() else engine.ROOT/'pocket_voices/catalog.json'))
        row=ttk.Frame(self.export_tab);row.pack(fill='x',pady=10);ttk.Label(row,text='Target catalog').pack(side='left');ttk.Entry(row,textvariable=self.catalog).pack(side='left',fill='x',expand=True,padx=6)
        self.button(row,'Browse…',self.choose_catalog).pack(side='left')
        row=ttk.Frame(self.export_tab);row.pack(fill='x',pady=10)
        self.button(row,'Export voice + metadata…',self.export_voice).pack(side='left',padx=4)
        self.button(row,'Install into catalog',self.install_voice).pack(side='left',padx=4)
        ttk.Label(self.export_tab,text='Exports contain the voice state and catalog metadata, not the original recording or your local paths.\nAfter installing, assign it to the NPC in /xispt voices. Replacing an existing voice requires confirmation; NPC assignments keep the same voice ID.',wraplength=1060).pack(anchor='w',pady=8)
    def entry(self):
        folder=self.one_candidate();f={k:v.get() for k,v in self.fields.items()};flags={k:v.get() for k,v in self.flags.items()}
        return folder,f['id'],engine.profile(folder,f['id'],f['label'],f['gender'],f['accent'],f['credit'],f['permission'],flags,f['npc'],automatic=self.automatic.get())
    def choose_catalog(self):
        file=filedialog.askopenfilename(parent=self.root,title='Select Pocket catalog',filetypes=[('JSON catalog','*.json')])
        if file:self.catalog.set(file)
    def update_voice_id(self,*_):
        self.fields['id'].set(engine.stable_voice_id(self.fields['label'].get(),self.fields['gender'].get(),self.fields['accent'].get()))
    def export_voice(self):
        args=self.entry();folder=filedialog.askdirectory(parent=self.root,title='Export voice and metadata')
        if not folder:return
        existing=[p for p in (Path(folder)/args[2]['model'],Path(folder)/(args[1]+'.json')) if p.exists()]
        overwrite=bool(existing)
        if overwrite and not messagebox.askyesno('Replace exported voice?', 'Replace the existing voice export and metadata?\n\n'+'\n'.join(str(p) for p in existing),parent=self.root,default='no'):return
        self.job('Exporting voice…',lambda cancel:engine.export(*args,folder,overwrite=overwrite),lambda path:self.status.set('Exported '+str(path)))
    def install_voice(self):
        args=self.entry();target=self.catalog.get();store=engine.Store(target)
        overwrite=args[1] in store.catalog or (store.path.parent/args[2]['model']).exists()
        if overwrite and not messagebox.askyesno('Replace catalog voice?', 'Replace voice '+args[1]+' and its metadata in:\n'+str(store.path)+'\n\nNPCs assigned to this ID will use the replacement voice. Automatic assignment and eligibility will use the current checkbox settings.',parent=self.root,default='no'):return
        self.job('Installing voice into catalog…',lambda cancel:engine.install(*args,target,overwrite=overwrite),lambda path:self.status.set('Installed '+str(path)+(' — available for automatic and manual assignment.' if args[2]['automatic'] else ' — available for manual assignment.')))

    def build_setup(self):
        ttk.Label(self.setup,text='One-time model setup',font=('Segoe UI',15,'bold')).pack(anchor='w',pady=10)
        ttk.Label(self.setup,text='This separate studio uses the gated English 18M cloning model to create voice files. Auditions use the public model.\nAccept Kyutai’s access terms and sign in with a Hugging Face read token if the model is not already cached.\nOnly model setup contacts Hugging Face; your recordings are never uploaded. Playback users do not need this access.',wraplength=1050).pack(anchor='w',pady=10)
        self.button(self.setup,'Open model access page',lambda:webbrowser.open('https://huggingface.co/kyutai/pocket-tts')).pack(anchor='w',pady=8)
        ttk.Label(self.setup,text='Hugging Face read token (optional if already signed in; stored only by the local HF credential manager)').pack(anchor='w')
        self.token=tk.StringVar();ttk.Entry(self.setup,textvariable=self.token,show='•',width=70).pack(anchor='w',pady=8)
        self.button(self.setup,'Prepare / download models',self.prepare_models).pack(anchor='w',pady=8)
        self.button(self.setup,'Check cached model files',self.check_models).pack(anchor='w',pady=8)
        self.model_status=tk.StringVar(value='Cache: '+str(engine.CACHE));ttk.Label(self.setup,textvariable=self.model_status,wraplength=1050).pack(anchor='w',pady=10)
        ttk.Label(self.setup,text='FFmpeg handles WAV, FLAC, MP3, AAC/M4A, Ogg/Opus and common video containers. Unsupported codecs or protected files will report an error. Converting a lossy recording to WAV does not restore lost detail.',wraplength=1050).pack(anchor='w',pady=12)
    def check_models(self):
        self.job('Checking local model cache…',lambda cancel:engine.cached_models()[0],lambda found:self.model_status.set('\n'.join(k+': '+('Ready' if v else 'Missing') for k,v in found.items())))
    def prepare_models(self):
        token=self.token.get();self.token.set('')
        def done(result):self.model_status.set('Models ready. Subsequent cloning and auditions work offline.')
        self.job('Preparing models…',lambda cancel:engine.setup_models(token,cancel,self.progress_event),done)

def main():
    root=tk.Tk()
    try:Studio(root)
    except Exception as exc:messagebox.showerror('Pocket Studio',str(exc));root.destroy();raise
    root.mainloop()

if __name__=='__main__':main()
