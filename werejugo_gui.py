import argparse
import PySimpleGUI as sg
import itertools
import os
import pathlib
import ctypes
import config
from core import LocationItem, LocationList, Event, EventList
import webbrowser
import resolver
import sys
import tempfile
import subprocess



if getattr(sys, 'frozen', False):
    program_dir = pathlib.Path(sys.executable)  
elif __file__:
    program_dir = pathlib.Path(__file__)

program_dir = program_dir.resolve().parent
config_path = "Path to werejugo.yaml"
if (program_dir / "werejugo.yaml").exists():
    config_path = str(program_dir / "werejugo.yaml")


esentutl_path = pathlib.Path(os.environ.get("COMSPEC")).parent / "esentutl.exe"
if not esentutl_path.exists():
    print("ESENTUTL Not found. Automatic extraction is not available.")


def extract_live_file():

    def extract_file(src,dst, ese = esentutl_path):
        cmdline = rf"{str(ese)} /y {str(src)} /vss /d {str(dst)}"
        print(cmdline)
        phandle = subprocess.Popen(cmdline, shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out1,_ = phandle.communicate()
        if (b"returned error" in out1) or (b"Init failed" in out1):
            print("ERROR\n File Extraction: {}\n".format(out1.decode()))
            return "Error Extracting File"
        return dst
        
    try:
        tmp_dir = tempfile.mkdtemp()
        extracted_soft = pathlib.Path(tmp_dir) / "SOFTWARE"
        extracted_srum = pathlib.Path(tmp_dir) / "srudb.dat"
        extracted_sys = pathlib.Path(tmp_dir) / "system.evtx"
        extracted_wlan = pathlib.Path(tmp_dir) / "wlan.evtx"
        soft = extract_file(r"\windows\system32\config\SOFTWARE", extracted_soft)
        srum = extract_file(r"\windows\system32\sru\srudb.dat", extracted_srum)
        sys  = extract_file(r"\windows\system32\Winevt\Logs\System.evtx", extracted_sys)
        wlan = extract_file(r"\windows\system32\Winevt\Logs\Microsoft-Windows-WLAN-AutoConfig%4Operational.evtx", extracted_wlan)
        #wlan= "blah"
    except Exception as e:
        print(f"Error occured {str(e)}")

    return soft,srum,sys,wlan
        

layout = [[sg.Text('Required: Path to System Events c:\windows\system32\Winevt\Logs\System.evtx')],
[sg.Input(key="_SYSTEMEVENTS_", enable_events=True), sg.FileBrowse(target="_SYSTEMEVENTS_")], 
[sg.Text('Required: SOFTWARE registry file c:\windows\system32\config\SOFTWARE')],
[sg.Input(key="_SOFTWARE_"), sg.FileBrowse(target="_SOFTWARE_")],
[sg.Text('Required: WLAN Event Logs c:\windows\system32\Winevt\Logs\Microsoft-Windows-WLAN-AutoConfig perational.evtx')],
[sg.Input(key="_WLANEVENTS_"), sg.FileBrowse(target="_WLANEVENTS_")],
[sg.Text('Required: SRUDB.DAT c:\windows\system32\sru\srudb.dat')],
[sg.Input(key="_SRU_"), sg.FileBrowse(target="_SRU_")],
[sg.Text('REQUIRED: Configuration file with API keys. .\werejugo.yaml')],
[sg.Input(config_path,key='_APIKEYS_'), sg.FileBrowse(target='_APIKEYS_')],
[sg.Text('REQUIRED: Output folder for results.')],
[sg.Input(os.getcwd(),key='_OUTDIR_'), sg.FolderBrowse(target='_OUTDIR_')],
[sg.Text("Click here for support via Twitter @MarkBaggett",enable_events=True, key="_SUPPORT_", text_color="Blue")],
[sg.OK(), sg.Cancel()]] 

if ctypes.windll.shell32.IsUserAnAdmin() == 1:
    layout[-1].append(sg.Button("Auto Acquire Files"))
else:
    sg.PopupOK('Run this tool with Admin priviliges to acquire files from this system.')
    
# Create the Window
window = sg.Window('werejugo 0.1', layout)
while True:             
    event, values = window.Read()
    if event is None:
        break
    if event == "_SUPPORT_":
        webbrowser.open("https://twitter.com/MarkBaggett")
    if event == 'Cancel':
        sys.exit(0)
    if event == "Auto Acquire Files":
        result = extract_live_file()
        if result:
            window.Element("_SYSTEMEVENTS_").Update(result[2])
            window.Element("_SRU_").Update(result[1])
            window.Element("_SOFTWARE_").Update(result[0])
            window.Element("_WLANEVENTS_").Update(result[3])
        continue

    if event == 'OK':
        sys_path = pathlib.Path(values.get("_SYSTEMEVENTS_"))
        if not sys_path.exists() or not sys_path.is_file() or str(sys_path).lower().startswith("c:\windows\system32"):
            sg.PopupOK("System Event log not found or locked by OS.")
            continue
        soft_path = pathlib.Path(values.get("_SOFTWARE_"))
        if not soft_path.exists() or not soft_path.is_file() or str(soft_path).lower().startswith("c:\windows\system32"):
            sg.PopupOK("SOFTWARE registry file is not found or locked by OS.")
            continue
        wlan_path = pathlib.Path(values.get("_WLANEVENTS_"))
        if not wlan_path.exists() or not wlan_path.is_file() or str(wlan_path).lower().startswith("c:\windows\system32"):
            sg.PopupOK("WLAN Event Log is not found or locked by OS.")
            continue
        sru_path = pathlib.Path(values.get("_SRU_"))
        if not sru_path.exists() or not sru_path.is_file() or str(sru_path).lower().startswith("c:\windows\system32"):
            sg.PopupOK("SRUM database is not found or locked by OS.")
            continue
        config_path = pathlib.Path(values.get("_APIKEYS_"))
        if not config_path.exists() or not config_path.is_file():
            sg.PopupOK("Configuration File is not found.")
            continue
        out_path = pathlib.Path(values.get("_OUTDIR_"))
        if not out_path.exists() or not out_path.is_dir():
            sg.PopupOK("The output directory does not seem to be correct.")
            continue
        break

window.Close()

config_path = str(config_path)
soft_path = str(soft_path)
sys_path = str(sys_path)
sru_path = str(sru_path)
config = config.config(config_path)
resolver.config = config
mylocations = LocationList()
myevents = EventList(mylocations)

if pathlib.Path("locations.cache").exists() and input("A cache of locations was found from a previous run of this tool. Would you like to reload that information?").lower().startswith("y"):
    myevents.Locations.load("locations.cache")

print("Discovering networks via wifi diagnostic logs...")
myevents.load_wifi_diagnostics(sys_path)

if input(f"\n{len(mylocations)} locations discovered.  Would you like to discover more locations by performing Wigle lookups of known Wireless (PNL)?").lower().startswith("y"):
    mylocations.load_registry_wigle(soft_path)
if input(f"\n{len(mylocations)} locations discovered.  Would you like to discover more locations by performing an exaustive (very slow) location search? ").lower().startswith("y"):
    mylocations.load_registry_triangulations(soft_path)

#myevents.Locations.save("locations.cache")

print(f"Working with {len(mylocations)} locations")

#Begin Loading Events
myevents.load_srum_wifi(sru_path, soft_path)
myevents.load_wlan_autoconfig(soft_path, wlan_path)
myevents.load_reg_history(soft_path)
myevents.to_files(out_path / "results.html", out_path / "result.kml", program_dir / "template.html")
webbrowser.open(out_path / "results.html")
