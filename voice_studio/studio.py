"""Standalone Windows voice creation workbench."""
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import winsound

from engine import Engine, OUTPUT, recording_script


class Studio:
    def __init__(self,root):
        self.root=root;self.engine=Engine();self.events=queue.Queue();self.busy=False
        self.pack=None;self.preview=None;self.reference=None;self.buttons=[]
        root.title('XISpeaks — Voice Studio');root.geometry('960x820');root.minsize(800,700)
        frame=ttk.Frame(root,padding=16);frame.pack(fill='both',expand=True);frame.columnconfigure(1,weight=1)
        ttk.Label(frame,text='Voice Studio',font=('Segoe UI',19,'bold')).grid(row=0,column=0,columnspan=3,sticky='w')
        ttk.Label(frame,text='Create candidate voices from volunteer recordings. No catalogue or game settings are changed.').grid(row=1,column=0,columnspan=3,sticky='w',pady=8)
        self.npc=self.field(frame,2,'NPC','Halver')
        self.identifier=self.field(frame,3,'Voice ID','bm_halver')
        self.credit=self.field(frame,4,'Volunteer credit','')
        self.source=self.field(frame,5,'Recording (WAV / FLAC)','')
        self.button(frame,'Browse…',self.browse_source).grid(row=5,column=2,padx=6)
        crop=ttk.Frame(frame);crop.grid(row=6,column=1,sticky='w',pady=6)
        ttk.Label(crop,text='Start seconds:').pack(side='left');self.start=tk.StringVar(value='0');ttk.Entry(crop,textvariable=self.start,width=7).pack(side='left')
        ttk.Label(crop,text='   Duration (3–30 seconds):').pack(side='left');self.duration=tk.StringVar(value='30');ttk.Entry(crop,textvariable=self.duration,width=7).pack(side='left')
        actions=ttk.Frame(frame);actions.grid(row=7,column=0,columnspan=3,sticky='w',pady=8)
        self.button(actions,'Generate voice pack',self.generate).pack(side='left')
        self.button(actions,'Open existing pack…',self.open_pack).pack(side='left',padx=8)
        self.button(actions,'Open output folder',self.open_output).pack(side='left')
        self.pack_label=tk.StringVar(value='No voice pack selected. First generation downloads the Inno model; recordings stay local.')
        ttk.Label(frame,textvariable=self.pack_label,wraplength=880).grid(row=8,column=0,columnspan=3,sticky='w')
        ttk.Label(frame,text='Audition text — use dialogue the volunteer did not record').grid(row=9,column=0,columnspan=3,sticky='w',pady=(12,4))
        self.text=ScrolledText(frame,height=4,wrap='word');self.text.grid(row=10,column=0,columnspan=3,sticky='nsew');frame.rowconfigure(10,weight=1)
        self.text.insert('1.0','There is much we have yet to discover. Are you ready? Then let us begin!')
        audio=ttk.Frame(frame);audio.grid(row=11,column=0,columnspan=3,sticky='w',pady=8)
        ttk.Label(audio,text='Speed:').pack(side='left');self.speed=tk.StringVar(value='1.0');ttk.Entry(audio,textvariable=self.speed,width=6).pack(side='left',padx=5)
        self.button(audio,'Render audition',self.render).pack(side='left')
        self.button(audio,'Play audition',lambda:self.play(self.preview)).pack(side='left',padx=5)
        self.button(audio,'Play reference',lambda:self.play(self.reference)).pack(side='left')
        ttk.Button(audio,text='Stop audio',command=self.stop).pack(side='left',padx=5)
        ttk.Label(frame,text='Recording script — paste verified NPC dialogue here (manual input; no DAT extraction yet)').grid(row=12,column=0,columnspan=3,sticky='w',pady=(8,4))
        self.script=ScrolledText(frame,height=5,wrap='word');self.script.grid(row=13,column=0,columnspan=3,sticky='nsew');frame.rowconfigure(13,weight=1)
        self.button(frame,'Export volunteer script…',self.export_script).grid(row=14,column=0,columnspan=3,sticky='w',pady=6)
        self.status=tk.StringVar(value='Ready. Use recordings provided with permission for voice synthesis.')
        ttk.Label(frame,textvariable=self.status,wraplength=880).grid(row=15,column=0,columnspan=3,sticky='w',pady=8)
        self.poll_id=root.after(100,self.poll);root.protocol('WM_DELETE_WINDOW',self.close)

    def field(self,frame,row,label,value):
        ttk.Label(frame,text=label).grid(row=row,column=0,sticky='w',padx=(0,10),pady=4)
        variable=tk.StringVar(value=value);ttk.Entry(frame,textvariable=variable).grid(row=row,column=1,sticky='ew')
        return variable

    def button(self,parent,text,command):
        button=ttk.Button(parent,text=text,command=command);self.buttons.append(button);return button

    def browse_source(self):
        path=filedialog.askopenfilename(filetypes=[('Recordings','*.wav *.flac')])
        if path:self.source.set(path)

    def work(self,kind,call):
        if self.busy:return
        self.stop();self.busy=True
        for button in self.buttons:button.configure(state='disabled')
        self.status.set('Generating voice pack…' if kind=='pack' else 'Rendering audition… First use loads/downloads models.')
        def run():
            try:self.events.put((kind,call()))
            except Exception as error:self.events.put(('error',str(error)))
        threading.Thread(target=run,daemon=True).start()

    def generate(self):
        args=(self.source.get(),self.identifier.get(),self.npc.get(),self.credit.get(),self.start.get(),self.duration.get())
        self.work('pack',lambda:self.engine.generate(*args))

    def render(self):
        if not self.pack:messagebox.showinfo('Select a voice','Generate or open a voice pack first.');return
        path,text,speed=self.pack,self.text.get('1.0','end').strip(),self.speed.get()
        self.work('preview',lambda:self.engine.render(path,text,speed))

    def select_pack(self,path):
        self.pack=Path(path);self.preview=None
        reference=self.pack.parent/'reference.wav';self.reference=reference if reference.exists() else None
        self.pack_label.set(str(self.pack))

    def open_pack(self):
        path=filedialog.askopenfilename(filetypes=[('Kokoro voice pack','*.pt')])
        if path:self.select_pack(path)

    def open_output(self):
        OUTPUT.mkdir(parents=True,exist_ok=True);os.startfile(str(OUTPUT))

    def export_script(self):
        try:content=recording_script(self.npc.get(),self.script.get('1.0','end'))
        except ValueError as error:messagebox.showerror('Script',str(error));return
        path=filedialog.asksaveasfilename(defaultextension='.txt',filetypes=[('Recording script','*.txt')])
        if path:
            try:Path(path).write_text(content,encoding='utf-8')
            except OSError as error:messagebox.showerror('Unable to save',str(error))

    def play(self,path):
        if not path:messagebox.showinfo('No audio','Generate a pack or render an audition first.');return
        try:winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
        except RuntimeError as error:messagebox.showerror('Playback failed',str(error))

    def stop(self):winsound.PlaySound(None,0)

    def poll(self):
        try:
            kind,value=self.events.get_nowait();self.busy=False
            for button in self.buttons:button.configure(state='normal')
            if kind=='error':self.status.set('Failed: '+value);messagebox.showerror('Voice Studio',value)
            elif kind=='pack':self.select_pack(value);self.status.set('Voice pack saved. Render an audition to hear it.')
            else:self.preview=value;self.status.set('Audition saved. Click Play audition to listen.')
        except queue.Empty:pass
        self.poll_id=self.root.after(100,self.poll)

    def close(self):
        if self.busy:messagebox.showinfo('Working','Please wait for the current generation to finish before closing.');return
        self.stop();self.root.after_cancel(self.poll_id);self.root.destroy()


if __name__=='__main__':
    root=tk.Tk()
    if 'vista' in ttk.Style(root).theme_names():ttk.Style(root).theme_use('vista')
    Studio(root);root.mainloop()
