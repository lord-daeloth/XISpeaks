"""Windows GUI for local Piper fine-tuning and blind-to-stage listening comparisons."""
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import winsound
from paths import ROOT,ASSETS,PYTHON,RUNS,VOICES

FLAGS=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0


def parse_stages(value):
    stages=[int(x.strip()) for x in value.split(',')]
    if not stages or stages!=sorted(set(stages)) or any(not 1<=x<=5000 for x in stages):
        raise ValueError('Stages must be increasing unique numbers between 1 and 5000')
    return stages


class App:
    def __init__(self,root):
        self.root=root;root.title('XISpeaks Piper Trainer - experimental');root.geometry('1080x820')
        self.events=queue.Queue();self.process=None;self.busy=False;self.cancel=threading.Event()
        self.pending_manifest=None;self.manifest=None;self.candidates={};self.active_clip=None
        self.recording=tk.StringVar();self.stages=tk.StringVar(value='100,300,1000');self.voice_id=tk.StringVar(value='am_halver_new')
        self.status=tk.StringVar(value='Load a reviewed recording or create a clip list, then train and compare.')
        self.bases=[dict(name='Ryan - US male',path=str(ASSETS/'build/piper-training/ryan.ckpt'),espeak='en-us'),
                    dict(name='Alan - UK male',path=str(ASSETS/'build/piper-training/alan.ckpt'),espeak='en-gb-x-rp')]
        self.base_flags=[]
        outer=ttk.Frame(root,padding=12);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='Piper Voice Trainer',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(outer,text='Local recording → review clips → train several stages → compare → export keeper').pack(anchor='w',pady=(0,8))
        tabs=ttk.Notebook(outer);tabs.pack(fill='both',expand=True)
        prepare=ttk.Frame(tabs,padding=10);train=ttk.Frame(tabs,padding=10);compare=ttk.Frame(tabs,padding=10)
        tabs.add(prepare,text='1. Recording & transcript');tabs.add(train,text='2. Train');tabs.add(compare,text='3. Compare & export')
        row=ttk.Frame(prepare);row.pack(fill='x')
        ttk.Entry(row,textvariable=self.recording).pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='Recording…',command=self.browse_audio).pack(side='left')
        ttk.Button(row,text='Transcribe locally',command=self.transcribe).pack(side='left')
        row=ttk.Frame(prepare);row.pack(fill='x',pady=6)
        ttk.Button(row,text='Load reviewed manifest…',command=self.load_manifest).pack(side='left')
        ttk.Button(row,text='Save manifest…',command=self.save_manifest).pack(side='left')
        ttk.Label(prepare,text='Check the words, especially fantasy names. Times are seconds into the original recording.').pack(anchor='w')
        self.clips=ttk.Treeview(prepare,columns=('start','end','text'),show='headings',height=12,selectmode='browse')
        for col,width in [('start',65),('end',65),('text',780)]:self.clips.heading(col,text=col.title());self.clips.column(col,width=width,stretch=col=='text')
        self.clips.pack(fill='both',expand=True);self.clips.bind('<<TreeviewSelect>>',self.select_clip)
        row=ttk.Frame(prepare);row.pack(fill='x',pady=6)
        self.start=tk.StringVar();self.end=tk.StringVar()
        for label,var in [('Start',self.start),('End',self.end)]:
            ttk.Label(row,text=label).pack(side='left');ttk.Entry(row,textvariable=var,width=10).pack(side='left')
        ttk.Button(row,text='Play clip',command=self.play_clip).pack(side='left',padx=8)
        ttk.Button(row,text='Apply clip edits',command=self.apply_clip).pack(side='left')
        self.clip_text=tk.Text(prepare,height=3,wrap='word');self.clip_text.pack(fill='x')
        self.reviewed=tk.BooleanVar(value=False)
        ttk.Checkbutton(prepare,text='I checked the clip boundaries and transcript against the recording',variable=self.reviewed).pack(anchor='w',pady=6)
        ttk.Label(train,text='Starting checkpoints (train each selected base independently):').pack(anchor='w')
        self.base_frame=ttk.Frame(train);self.base_frame.pack(fill='x');self.draw_bases()
        ttk.Button(train,text='Add trusted local checkpoint…',command=self.add_base).pack(anchor='w',pady=6)
        row=ttk.Frame(train);row.pack(fill='x',pady=6)
        ttk.Label(row,text='Save / audition at batches:').pack(side='left');ttk.Entry(row,textvariable=self.stages,width=35).pack(side='left',padx=8)
        ttk.Label(train,text='Audition text: one passage per line. Include dialogue that is NOT in the recording.').pack(anchor='w')
        self.texts=tk.Text(train,height=8,wrap='word');self.texts.pack(fill='x',pady=6)
        ttk.Label(train,text='Fresh fine-tune for each base; fixed gain to -3 dBFS; low learning rate; CUDA GPU required.\nSnapshots are listening candidates, not resumable full training checkpoints.').pack(anchor='w',pady=6)
        ttk.Button(train,text='Start training comparisons',command=self.train).pack(anchor='w',pady=8)
        ttk.Label(compare,text='Select a candidate. Play the same passage on other stages before choosing a keeper.').pack(anchor='w')
        row=ttk.Frame(compare);row.pack(fill='x',pady=6)
        ttk.Button(row,text='Open completed run…',command=self.open_run).pack(side='left')
        ttk.Button(row,text='Refresh runs',command=self.refresh_runs).pack(side='left')
        self.results=ttk.Treeview(compare,columns=('base','stage','run'),show='headings',height=12,selectmode='browse')
        for col,width in [('base',180),('stage',80),('run',620)]:self.results.heading(col,text=col.title());self.results.column(col,width=width)
        self.results.pack(fill='both',expand=True);self.results.bind('<<TreeviewSelect>>',self.select_candidate)
        self.passage=ttk.Combobox(compare,state='readonly');self.passage.pack(fill='x',pady=6)
        row=ttk.Frame(compare);row.pack(fill='x')
        ttk.Button(row,text='Play candidate',command=self.play_candidate).pack(side='left')
        ttk.Button(row,text='Play untrained base',command=lambda:self.play_candidate(baseline=True)).pack(side='left')
        ttk.Button(row,text='Play recording',command=self.play_reference).pack(side='left')
        ttk.Button(row,text='Stop audio',command=lambda:winsound.PlaySound(None,0)).pack(side='left')
        row=ttk.Frame(compare);row.pack(fill='x',pady=12)
        ttk.Label(row,text='Keeper ID (am_, af_, bm_, bf_):').pack(side='left')
        ttk.Entry(row,textvariable=self.voice_id,width=25).pack(side='left',padx=6)
        ttk.Button(row,text='Export keeper to experimental addon',command=self.export).pack(side='left')
        ttk.Label(compare,text='Custom voices are manual overrides only. Restart the Piper companion after export.\nOriginal recordings and training snapshots stay local; the addon only needs ONNX + JSON.').pack(anchor='w')
        ttk.Separator(outer).pack(fill='x',pady=8)
        ttk.Label(outer,textvariable=self.status,wraplength=1000).pack(anchor='w')
        ttk.Label(outer,text='Current checkpoint / transcription').pack(anchor='w')
        self.progress=ttk.Progressbar(outer,maximum=100);self.progress.pack(fill='x',pady=3)
        ttk.Label(outer,text='All selected checkpoints').pack(anchor='w')
        self.overall=ttk.Progressbar(outer,maximum=100);self.overall.pack(fill='x',pady=3)
        ttk.Button(outer,text='Cancel current operation',command=self.stop).pack(anchor='e')
        self.log=tk.Text(outer,height=6,wrap='word',state='disabled');self.log.pack(fill='x',pady=5)
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(100,self.poll)
        initial=ASSETS/'build/piper-training/new-manifest.json'
        if initial.exists():self.load_manifest(initial)
        self.refresh_runs()

    def guard(self):
        if self.busy:raise ValueError('Wait for the current operation or cancel it first')

    def notify_error(self,exc):messagebox.showerror('Piper Trainer',str(exc),parent=self.root)

    def draw_bases(self):
        for child in self.base_frame.winfo_children():child.destroy()
        previous=[v.get() for v in self.base_flags]
        self.base_flags=[]
        for index,base in enumerate(self.bases):
            flag=tk.BooleanVar(value=previous[index] if index<len(previous) else index==0);self.base_flags.append(flag)
            ttk.Checkbutton(self.base_frame,text=base['name'],variable=flag).pack(anchor='w')

    def add_base(self):
        try:
            self.guard()
            path=filedialog.askopenfilename(filetypes=[('Trusted Piper training checkpoint','*.ckpt')])
            if not path:return
            accent=simpledialog.askstring('Pronunciation','eSpeak language (en-us or en-gb):',initialvalue='en-us')
            if accent not in ('en-us','en-gb','en-gb-x-rp'):raise ValueError('Choose en-us or en-gb')
            self.bases.append(dict(name=Path(path).stem,path=path,espeak=accent));self.draw_bases()
        except Exception as exc:self.notify_error(exc)

    def browse_audio(self):
        path=filedialog.askopenfilename(filetypes=[('Wave audio','*.wav')])
        if path:self.recording.set(path);self.reviewed.set(False)

    def load_manifest(self,path=None):
        try:
            self.guard();path=path or filedialog.askopenfilename(filetypes=[('Reviewed manifest','*.json')])
            if not path:return
            self.manifest=json.loads(Path(path).read_text(encoding='utf-8-sig'))
            self.recording.set(self.manifest['source']);self.stages.set(','.join(map(str,self.manifest.get('stages',[100,300,1000]))))
            self.texts.delete('1.0','end');self.texts.insert('1.0','\n'.join(self.manifest['texts']))
            self.clips.delete(*self.clips.get_children())
            for i,s in enumerate(self.manifest['segments']):self.clips.insert('', 'end',iid=str(i),values=(s['start'],s['end'],s['text']))
            self.reviewed.set(False)
        except Exception as exc:self.notify_error(exc)

    def current_manifest(self):
        if not self.manifest:raise ValueError('Load a manifest or transcribe a recording first')
        source=Path(self.recording.get()).resolve()
        if not source.is_file():raise ValueError('Recording not found')
        rows=[];previous=0
        for iid in self.clips.get_children():
            start,end,text=self.clips.item(iid,'values');start=float(start);end=float(end)
            if not previous<=start<end or not text.strip() or any(c in text for c in '|\r\n'):raise ValueError('Invalid clip boundaries or text')
            previous=end;rows.append(dict(start=start,end=end,text=text))
        if not rows:raise ValueError('No clips')
        import soundfile as sf
        if previous>sf.info(source).duration:raise ValueError('A clip extends past the recording')
        texts=[s.strip() for s in self.texts.get('1.0','end').splitlines() if s.strip()]
        if not texts:raise ValueError('Add audition passages')
        return dict(source=str(source),segments=rows,texts=texts,stages=parse_stages(self.stages.get()),peak_db=-3)

    def save_manifest(self):
        try:
            self.guard();data=self.current_manifest();path=filedialog.asksaveasfilename(defaultextension='.json')
            if path:Path(path).write_text(json.dumps(data,indent=2),encoding='utf-8')
        except Exception as exc:self.notify_error(exc)

    def select_clip(self,event=None):
        selected=self.clips.selection()
        if not selected:return
        self.active_clip=selected[0];start,end,text=self.clips.item(selected[0],'values')
        self.start.set(start);self.end.set(end);self.clip_text.delete('1.0','end');self.clip_text.insert('1.0',text)

    def apply_clip(self):
        if self.active_clip is not None:
            self.clips.item(self.active_clip,values=(self.start.get(),self.end.get(),self.clip_text.get('1.0','end').strip()))
            self.reviewed.set(False)

    def play_clip(self):
        try:
            import soundfile as sf
            audio,rate=sf.read(self.recording.get());start=float(self.start.get());end=float(self.end.get())
            if not 0<=start<end<=len(audio)/rate:raise ValueError('Invalid clip boundary')
            RUNS.mkdir(exist_ok=True);path=RUNS/'preview-clip.wav';winsound.PlaySound(None,0)
            sf.write(path,audio[int(start*rate):int(end*rate)],rate,subtype='PCM_16');self.play(path)
        except Exception as exc:self.notify_error(exc)

    def operation(self,work):
        self.guard();self.busy=True;self.cancel.clear();self.progress['value']=0;self.overall['value']=0
        def target():
            try:work()
            except Exception as exc:self.events.put(('error',str(exc)))
            finally:self.events.put(('done',None))
        threading.Thread(target=target,daemon=True).start()

    def command(self,args,stages=None,index=0,total=1):
        if self.cancel.is_set():raise RuntimeError('Cancelled')
        self.process=subprocess.Popen([str(PYTHON),'-u',*map(str,args)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=FLAGS)
        for line in self.process.stdout:
            self.events.put(('log',line))
            m=re.match(r'BATCH (\d+)',line)
            if m and stages:
                fraction=int(m[1])/stages[-1];self.events.put(('progress',(fraction*100,(index+fraction)/total*100)))
            m=re.match(r'TRANSCRIBE (\d+)',line)
            if m:self.events.put(('progress',(int(m[1]),int(m[1]))))
            if self.cancel.is_set() and self.process.poll() is None:self.process.terminate()
        code=self.process.wait();self.process=None
        if self.cancel.is_set():raise RuntimeError('Cancelled; completed snapshots remain available')
        if code:raise RuntimeError('Operation failed; see the log above')

    def transcribe(self):
        try:
            self.guard();source=Path(self.recording.get()).resolve()
            if not source.is_file():raise ValueError('Select a recording first')
            RUNS.mkdir(exist_ok=True);out=RUNS/f'transcript-{time.time_ns()}.json'
            def work():
                self.events.put(('status','Transcribing locally. Review the resulting clip text before training.'))
                self.command([ROOT/'piper_trainer/transcribe.py',source,out]);self.events.put(('manifest',out))
            self.operation(work)
        except Exception as exc:self.notify_error(exc)

    def train(self):
        try:
            self.guard();data=self.current_manifest()
            if not self.reviewed.get():raise ValueError('Check the transcript and boundaries, then tick the review checkbox')
            bases=[dict(b) for b,f in zip(self.bases,self.base_flags) if f.get()]
            if not bases:raise ValueError('Select at least one checkpoint')
            if any(not Path(b['path']).is_file() for b in bases):raise ValueError('A selected checkpoint is missing')
            run=RUNS/time.strftime('%Y%m%d-%H%M%S');run.mkdir(parents=True,exist_ok=False)
            manifest=run/'manifest.json';manifest.write_text(json.dumps(data,indent=2),encoding='utf-8')
            (run/'bases.json').write_text(json.dumps(bases,indent=2))
            def work():
                for index,base in enumerate(bases):
                    self.events.put(('status',f'Training {index+1}/{len(bases)}: {base["name"]}'))
                    self.command([ROOT/'experiments/piper_training/run.py','--manifest',manifest,'--output',run/f'base-{index+1}',
                        '--base',base['path'],'--assets',ASSETS,'--espeak',base['espeak']],data['stages'],index,len(bases))
                self.events.put(('status','Training complete. Compare the saved stages in the third tab.'))
                self.events.put(('progress',(100,100)))
            self.operation(work)
        except Exception as exc:self.notify_error(exc)

    def add_run(self,path):
        path=Path(path)
        config=path/'results.json'
        if not config.exists():return
        info=json.loads(config.read_text(encoding='utf-8-sig'))
        for stage in info['stages']:
            step=stage['batches']
            if step==0:continue
            key=str(path)+'|'+str(step)
            if key in self.candidates:continue
            if not (path/f'generator-{step}.pt').exists():continue
            iid=self.results.insert('', 'end',values=(info['base'],step,path.name))
            self.candidates[key]=(iid,path,step,info)

    def refresh_runs(self):
        if RUNS.exists():
            for path in RUNS.rglob('results.json'):self.add_run(path.parent)
        self.add_run(ASSETS/'experiments/piper_training/output-new-reference')

    def open_run(self):
        path=filedialog.askdirectory()
        if path:
            self.add_run(path)
            for file in Path(path).rglob('results.json'):self.add_run(file.parent)

    def candidate(self):
        selection=self.results.selection()
        if not selection:raise ValueError('Select a candidate')
        return next(v for v in self.candidates.values() if v[0]==selection[0])

    def select_candidate(self,event=None):
        try:
            _,_,_,info=self.candidate();self.passage['values']=info['audition_texts'];self.passage.current(0)
        except Exception as exc:self.notify_error(exc)

    def play(self,path):winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC)

    def play_candidate(self,baseline=False):
        try:
            _,path,step,_=self.candidate();index=self.passage.current()
            if index<0:raise ValueError('Choose an audition passage')
            self.play(path/f'step-{0 if baseline else step}-{index}.wav')
        except Exception as exc:self.notify_error(exc)

    def play_reference(self):
        try:self.play(self.candidate()[1]/'reference.wav')
        except Exception as exc:self.notify_error(exc)

    def export(self):
        try:
            self.guard();_,path,step,info=self.candidate();key=self.voice_id.get().strip()
            if not re.fullmatch('[ab][fm]_[a-z0-9_]+',key):raise ValueError('Use am_, af_, bm_ or bf_, followed by lowercase letters, digits, underscores')
            output=VOICES/(key+'.onnx')
            if output.exists():raise ValueError('That keeper ID already exists; choose another')
            def work():
                self.events.put(('status',f'Exporting and testing {key}...'))
                self.command([ROOT/'piper_trainer/export_voice.py',path/f'generator-{step}.pt',output])
                catalog_path=VOICES/'catalog.json';catalog=json.loads(catalog_path.read_text()) if catalog_path.exists() else {}
                catalog[key]=dict(model=output.name,automatic=False)
                temporary=catalog_path.with_suffix('.tmp');temporary.write_text(json.dumps(catalog,indent=2));temporary.replace(catalog_path)
                base_path=Path(info.get('base_checkpoint',str(ASSETS/'build/piper-training/ryan.ckpt') if info['base']=='en_US-ryan-medium' else ''))
                card=base_path.with_name(base_path.stem+'-MODEL_CARD') if base_path.name else None
                if card and card.is_file():shutil.copyfile(card,output.with_suffix('.MODEL_CARD'))
                output.with_suffix('.provenance.json').write_text(json.dumps(dict(base=info['base'],batches=step,source_sha256=info['source_sha256'],checkpoint_sha256=info['checkpoint_sha256']),indent=2))
                self.events.put(('status',f'Keeper exported: {key} ({output.stat().st_size/1048576:.1f} MiB). Restart Piper companion and select it as an NPC override.'))
                self.events.put(('progress',(100,100)))
            self.operation(work)
        except Exception as exc:self.notify_error(exc)

    def stop(self):
        self.cancel.set()
        if self.process and self.process.poll() is None:self.process.terminate()

    def close(self):
        self.stop();winsound.PlaySound(None,0);self.root.destroy()

    def poll(self):
        deferred=[]
        while not self.events.empty():
            kind,value=self.events.get()
            if kind=='log':
                self.log.configure(state='normal');self.log.insert('end',value);self.log.see('end');self.log.configure(state='disabled')
            elif kind=='progress':self.progress['value'],self.overall['value']=value
            elif kind=='status':self.status.set(value)
            elif kind=='error':self.status.set(value)
            elif kind=='manifest':self.pending_manifest=value
            elif kind=='done':self.busy=False;self.refresh_runs()
        if not self.busy and self.pending_manifest:
            path=self.pending_manifest;self.pending_manifest=None;self.load_manifest(path)
        self.root.after(100,self.poll)

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
