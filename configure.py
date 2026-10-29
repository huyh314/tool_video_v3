"""Local configuration window and diagnostics; never prints secret values."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import threading

from shared.config import ROOT, load_config
from shared.runtime import safe_error


def save_settings(values, gemini_key=None):
    config_path=ROOT/'config.json'
    current=json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.exists() else {}
    url=values.get('webhook_url','').strip()
    if url and not re.fullmatch(r'https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec',url):
        raise ValueError('Webhook cần là URL Apps Script kết thúc bằng /exec.')
    for key in ('webhook_url','spreadsheet_id','gemini_model','default_signature','data_dir','cookies_browser'):
        if key in values:
            current[key]=str(values[key]).strip()
    if current.get('cookies_browser','') not in ('','chrome','edge','firefox'):
        raise ValueError('Trình duyệt cookie phải để trống hoặc chrome/edge/firefox.')
    current['width']=int(values.get('width',current.get('width',720)))
    if current['width'] not in (720,1080):
        raise ValueError('Độ phân giải chọn 720 hoặc 1080.')
    current['height']=current['width']*16//9
    current.pop('gemini_api_key',None)
    temp=config_path.with_suffix('.tmp')
    temp.write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(config_path)
    if gemini_key is not None and gemini_key.strip():
        (ROOT/'.local').mkdir(exist_ok=True)
        (ROOT/'.local'/'gemini.key').write_text(gemini_key.strip(),encoding='utf-8')


def doctor(config):
    from shared.media import ffmpeg_path, probe_media
    report={'python_modules':{m:bool(importlib.util.find_spec(m)) for m in ('PIL','requests','yt_dlp','imageio_ffmpeg')},
            'gemini_key_configured':bool(config.get('gemini_api_key')),
            'webhook_configured':bool(config.get('webhook_url')),
            'data_dir':str(config['data_dir']), 'port':8765}
    report['ffmpeg']=ffmpeg_path(config)
    report['background']=probe_media(config['bg_video'],config)
    report['music_exists']=config['music_file'].is_file()
    bundled_font = Path(__file__).resolve().parent / 'assets' / 'fonts' / 'arialbd.ttf'
    report['font_exists'] = (
        bundled_font.is_file() or
        Path('C:/Windows/Fonts/arialbd.ttf').is_file() or
        Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf').is_file() or
        Path('/Library/Fonts/Arial Bold.ttf').is_file() or
        Path('/System/Library/Fonts/Helvetica.ttc').is_file() or
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf').is_file()
    )
    return report


def check_connections(config):
    from collector.gemini import GeminiClient
    from tool1 import check_protocol
    from shared.sheet import SheetClient
    results={}
    try:
        api=GeminiClient(dict(config,gemini_timeout=30,gemini_retries=1))
        result=api.generate_json([{'text':'Trả JSON ok=true để kiểm tra kết nối.'}],
                                 {'type':'OBJECT','properties':{'ok':{'type':'BOOLEAN'}},'required':['ok']})
        if result.get('ok') is not True:
            raise RuntimeError('Phản hồi kiểm tra không đúng.')
        results['gemini']='OK — '+api.model
    except Exception as exc:
        results['gemini']=safe_error(exc,config)
    try:
        check_protocol(SheetClient(config),config)
        results['sheet']='OK — giao thức v3, đúng bảng tính'
    except Exception as exc:
        results['sheet']=safe_error(exc,config)
    return results


def gui():
    import tkinter as tk
    from tkinter import ttk, messagebox
    config=load_config()
    root=tk.Tk()
    root.title('Video Studio v3 — Cấu hình')
    root.geometry('850x690')
    frame=ttk.Frame(root,padding=20)
    frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Cài đặt chung cho hai tool',font=('Segoe UI',17,'bold')).grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,16))
    fields={}
    specs=[('webhook_url','URL Apps Script Web App'),('spreadsheet_id','ID Google Sheet'),
           ('gemini_model','Model Gemini (auto = tự chọn)'),('default_signature','Thương hiệu đầu ra'),
           ('data_dir','Thư mục dữ liệu'),('cookies_browser','Cookie trình duyệt (tùy chọn)'),('width','Chiều rộng 720 / 1080')]
    for row,(key,label) in enumerate(specs,1):
        ttk.Label(frame,text=label).grid(row=row,column=0,sticky='w',pady=5)
        value=config.get(key,'')
        fields[key]=tk.StringVar(value=str(value))
        if key=='width':
            entry=ttk.Combobox(frame,textvariable=fields[key],values=['720','1080'],state='readonly')
        else:
            entry=ttk.Entry(frame,textvariable=fields[key],width=65)
        entry.grid(row=row,column=1,columnspan=2,sticky='ew',padx=10)
    row=len(specs)+1
    key_value=tk.StringVar(value='')
    ttk.Label(frame,text='Gemini key (để trống để giữ)').grid(row=row,column=0,sticky='w',pady=5)
    ttk.Entry(frame,textvariable=key_value,show='•').grid(row=row,column=1,columnspan=2,sticky='ew',padx=10)
    for offset,(key,label) in enumerate([('sheet_token','Mã API cho Apps Script'),('local_api_token','Mã ghép nối Extension')],1):
        ttk.Label(frame,text=label).grid(row=row+offset,column=0,sticky='w',pady=5)
        value=tk.StringVar(value=config[key])
        ttk.Entry(frame,textvariable=value,state='readonly',show='•').grid(row=row+offset,column=1,sticky='ew',padx=10)
        def copy_secret(v=value):
            root.clipboard_clear()
            root.clipboard_append(v.get())
        ttk.Button(frame,text='Sao chép',command=copy_secret).grid(row=row+offset,column=2)
    status=tk.StringVar(value='Gemini key đã lưu: '+('Có' if config.get('gemini_api_key') else 'Chưa'))
    def save():
        try:
            save_settings({k:v.get() for k,v in fields.items()},key_value.get())
            key_value.set('')
            status.set('Đã lưu. Khởi động lại hai tool nếu đang chạy.')
            return True
        except Exception as exc:
            messagebox.showerror('Cấu hình',safe_error(exc,config))
            return False
    def check():
        if not save():
            return
        status.set('Đang kiểm tra kết nối...')
        def background():
            result=check_connections(load_config())
            root.after(0,lambda:status.set('\n'.join(k+': '+v for k,v in result.items())))
        threading.Thread(target=background,daemon=True).start()
    buttons=ttk.Frame(frame)
    buttons.grid(row=row+3,column=0,columnspan=3,sticky='w',pady=18)
    ttk.Button(buttons,text='Lưu cấu hình',command=save).pack(side='left',padx=5)
    ttk.Button(buttons,text='Kiểm tra Gemini và Sheet',command=check).pack(side='left',padx=5)
    ttk.Label(frame,textvariable=status,wraplength=780,justify='left').grid(row=row+4,column=0,columnspan=3,sticky='w')
    ttk.Label(frame,text='Tool 1: theo dõi và tạo nháp. Tool 2: dựng các kịch bản anh đã duyệt trên Sheet.',wraplength=780).grid(row=row+5,column=0,columnspan=3,sticky='w',pady=15)
    frame.columnconfigure(1,weight=1)
    root.mainloop()


def main():
    parser=argparse.ArgumentParser(description='Cài đặt Video Studio v3')
    parser.add_argument('--doctor',action='store_true')
    parser.add_argument('--check-connections',action='store_true')
    args=parser.parse_args()
    try:
        config=load_config()
        if args.doctor:
            print(json.dumps(doctor(config),ensure_ascii=False,indent=2))
        elif args.check_connections:
            results=check_connections(config)
            print(json.dumps(results,ensure_ascii=False,indent=2))
            return 0 if all(v.startswith('OK') for v in results.values()) else 1
        else:
            gui()
        return 0
    except Exception as exc:
        print('Lỗi:',safe_error(exc,locals().get('config',{})))
        return 1


if __name__=='__main__':
    raise SystemExit(main())

